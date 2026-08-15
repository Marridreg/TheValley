"""OpenAI-compatible backend — covers OpenRouter, OpenAI, and local servers.

One adapter handles every `/v1/chat/completions` endpoint: OpenRouter, OpenAI
proper, Together, Groq, DeepSeek, and anything local (llama.cpp, Ollama,
LM Studio, text-generation-webui, vLLM, TabbyAPI). They differ only in base_url
and which knobs they honour.

Two things behave differently from the Anthropic path:

  SCHEMA FORCING is per-model rather than guaranteed. Where the endpoint
  supports response_format json_schema we use it and get the same hard
  guarantee. Where it doesn't, we ask for JSON in the prompt, then validate
  and give the model exactly one repair attempt with the validation errors
  quoted back at it. That repair loop is the thing the original design doc was
  worried about; here it is real, but it is the fallback rather than the
  primary path, and a failure degrades one turn instead of corrupting state.

  CACHING is usually implicit — OpenAI, DeepSeek and friends cache long
  prefixes automatically with no markers. Set caching: explicit in config when
  routing to Anthropic models through OpenRouter, which passes cache_control
  breakpoints upstream.

Capabilities cannot be reliably introspected across this many backends, so
they are declared in config with permissive defaults. Sending an unsupported
sampler to OpenRouter is harmless — it drops what the upstream doesn't take.
"""

from __future__ import annotations

import json
from typing import Iterator

from .base import (
    Capabilities,
    GenParams,
    Provider,
    ProviderError,
    SystemBlock,
    Usage,
    extract_json,
)

# Endpoints known to honour strict response_format json_schema.
_SCHEMA_HINTS = ("gpt-4o", "gpt-4.1", "gpt-5", "o3", "o4", "grok", "gemini-2", "gemini-3")

# Reasoning models that take an effort level.
_EFFORT_HINTS = (
    "o1", "o3", "o4", "gpt-5",
    "claude-opus", "claude-sonnet", "claude-fable", "claude-mythos",
    "grok-4", "deepseek-r",
)

# Frontier Claude REJECTS temperature/top_p/top_k with a 400 rather than
# ignoring them, and that is true whether you reach it directly or route to it
# through OpenRouter. Routing does not change what the upstream model accepts,
# so these have to be recognised here too — otherwise a preset written for a
# local model kills the first turn on Claude with a confusing error.
_NO_SAMPLER_HINTS = (
    "claude-fable-5",
    "claude-mythos-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-5",
    "claude-fable",
    "claude-4-8",
    "claude-4-7",
)


class OpenAICompatProvider(Provider):
    name = "openai_compat"

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        capability_overrides: dict | None = None,
        extra_headers: dict | None = None,
        extra_body: dict | None = None,
        label: str | None = None,
    ):
        super().__init__(model)
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise ProviderError(
                "the `openai` package is required for OpenAI-compatible providers "
                "(pip install openai). It talks to OpenRouter and local servers too."
            ) from exc

        import openai

        self._sdk = openai
        if label:
            self.name = label

        # Local servers usually want no key but the SDK insists on a string.
        self.client = OpenAI(
            api_key=api_key or "not-needed",
            base_url=base_url or "https://api.openai.com/v1",
        )
        self._extra_headers = dict(extra_headers or {})
        self._extra_body = dict(extra_body or {})
        self._caps = self._detect(capability_overrides or {})

    def _detect(self, overrides: dict) -> Capabilities:
        m = self.model.lower()
        samplers_ok = not any(h in m for h in _NO_SAMPLER_HINTS)
        caps = Capabilities(
            # Optimistic: most modern endpoints do support this, and when they
            # don't the repair loop catches it. Set schema_forcing: false in
            # config to skip straight to prompted JSON.
            schema_forcing=any(h in m for h in _SCHEMA_HINTS) or "/" in m,
            caching="implicit",
            temperature=samplers_ok,
            top_p=samplers_ok,
            top_k=samplers_ok,
            min_p=samplers_ok,
            repetition_penalty=samplers_ok,
            frequency_presence_penalty=samplers_ok,
            effort=any(h in m for h in _EFFORT_HINTS),
            effort_levels=("low", "medium", "high"),
            mid_conversation_system=False,
            streaming=True,
        )
        for key, value in overrides.items():
            if hasattr(caps, key):
                if key == "effort_levels" and isinstance(value, list):
                    value = tuple(value)
                setattr(caps, key, value)
        return caps

    @property
    def caps(self) -> Capabilities:
        return self._caps

    # ── request assembly ──

    def _prepend_system(self, system: list[SystemBlock], messages: list[dict]) -> list[dict]:
        """Fold system blocks into a leading system message.

        With explicit caching the content becomes an array of parts so the
        breakpoint survives; otherwise a single joined string keeps the
        request simple and maximally portable to older local servers.
        """
        blocks = [b for b in system if b.text.strip()]
        if not blocks:
            return list(messages)

        if self._caps.caching == "explicit":
            parts = []
            for b in blocks:
                part: dict = {"type": "text", "text": b.text}
                if b.cache:
                    part["cache_control"] = {"type": "ephemeral"}
                parts.append(part)
            head = {"role": "system", "content": parts}
        else:
            head = {"role": "system", "content": "\n\n".join(b.text for b in blocks)}

        return [head, *messages]

    def _normalise_roles(self, messages: list[dict]) -> list[dict]:
        """Fold mid-conversation system messages into the neighbouring user
        turn where the backend won't honour them.

        The GM briefing rides on such a message. On backends that ignore or
        reject it, dropping it would silently take the Wall's briefing out of
        the narrator's context — so it gets merged into the user turn instead,
        clearly delimited.
        """
        if self._caps.mid_conversation_system:
            return list(messages)

        out: list[dict] = []
        for msg in messages:
            if msg.get("role") == "system" and out:
                text = msg.get("content") or ""
                if isinstance(text, list):
                    text = "\n".join(p.get("text", "") for p in text)
                if out[-1]["role"] == "user":
                    prior = out[-1]["content"]
                    if isinstance(prior, list):
                        prior = "\n".join(p.get("text", "") for p in prior)
                    out[-1] = {"role": "user", "content": f"{prior}\n\n{text}"}
                else:
                    out.append({"role": "user", "content": text})
            else:
                out.append(dict(msg))
        return out

    def _kwargs(self, system: list[SystemBlock], messages: list[dict], params: GenParams) -> dict:
        msgs = self._normalise_roles(messages)
        kwargs: dict = {
            "model": self.model,
            "messages": self._prepend_system(system, msgs),
            "max_tokens": params.max_tokens,
        }

        sampling = self.filter_params(params)
        # top_k, min_p and repetition_penalty are not in the OpenAI schema;
        # OpenRouter and most local servers read them from the request body.
        body = dict(self._extra_body)
        for key in ("top_k", "min_p", "repetition_penalty"):
            if key in sampling:
                body[key] = sampling.pop(key)
        kwargs.update(sampling)

        effort = self.resolve_effort(params.effort)
        if effort:
            # OpenRouter normalises `reasoning`; OpenAI uses reasoning_effort.
            if "openrouter" in str(self.client.base_url):
                body["reasoning"] = {"effort": effort}
            else:
                kwargs["reasoning_effort"] = effort

        if params.stop:
            kwargs["stop"] = params.stop
        if body:
            kwargs["extra_body"] = body
        if self._extra_headers:
            kwargs["extra_headers"] = self._extra_headers
        return kwargs

    def _record(self, usage) -> None:
        if not usage:
            return
        cached = 0
        details = getattr(usage, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0
        self.last_usage = Usage(
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cache_read=cached,
        )

    def _wrap(self, exc: Exception) -> ProviderError:
        status = getattr(exc, "status_code", None)
        retryable = bool(status and (status in (408, 409, 429) or status >= 500))
        if isinstance(exc, self._sdk.APIConnectionError):
            return ProviderError(
                f"could not reach {self.client.base_url}: {exc}. "
                "If this is a local server, check that it is running.",
                retryable=True,
            )
        return ProviderError(f"{self.model}: {exc}", retryable=retryable)

    # ── the two calls ──

    def complete_json(
        self,
        system: list[SystemBlock],
        messages: list[dict],
        schema: dict,
        params: GenParams,
    ) -> dict:
        from .validate import describe_errors, validate

        kwargs = self._kwargs(system, messages, params)

        if self._caps.schema_forcing:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "briefing_packet",
                    "strict": True,
                    "schema": schema,
                },
            }
        else:
            # No constrained decoding available. Ask plainly, then verify.
            kwargs["messages"] = kwargs["messages"] + [
                {
                    "role": "user",
                    "content": (
                        "Reply with a single JSON object matching this schema. "
                        "No prose, no markdown fences, no commentary.\n\n"
                        + json.dumps(schema, indent=2)
                    ),
                }
            ]

        text = self._once(kwargs)
        try:
            data = extract_json(text)
            errors = validate(data, schema)
            if not errors:
                return data
            problem = describe_errors(errors)
        except ValueError as exc:
            data, problem = None, str(exc)

        # One repair attempt, quoting the specific failures. Models are good
        # at this when told exactly what is wrong.
        repair = list(kwargs["messages"]) + [
            {"role": "assistant", "content": text[:4000]},
            {
                "role": "user",
                "content": (
                    "That response was not valid against the schema:\n"
                    f"{problem}\n\n"
                    "Reply with the corrected JSON object only."
                ),
            },
        ]
        retry_kwargs = {**kwargs, "messages": repair}
        text2 = self._once(retry_kwargs)
        try:
            data2 = extract_json(text2)
        except ValueError as exc:
            raise ProviderError(
                f"{self.model} could not produce a valid briefing packet: {exc}. "
                "Consider a model with JSON schema support, or set "
                "schema_forcing: true for this provider in config.yaml."
            ) from exc

        errors2 = validate(data2, schema)
        if errors2:
            raise ProviderError(
                f"{self.model} produced a briefing packet that still fails "
                f"validation after one repair: {describe_errors(errors2)}"
            )
        return data2

    def _once(self, kwargs: dict) -> str:
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise self._wrap(exc) from exc
        self._record(getattr(resp, "usage", None))
        if not resp.choices:
            raise ProviderError(f"{self.model} returned no choices")
        return resp.choices[0].message.content or ""

    def stream_text(
        self,
        system: list[SystemBlock],
        messages: list[dict],
        params: GenParams,
    ) -> Iterator[str]:
        kwargs = self._kwargs(system, messages, params)
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}

        try:
            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                if getattr(chunk, "usage", None):
                    self._record(chunk.usage)
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None)
                if piece:
                    yield piece
        except Exception as exc:
            # stream_options is not universal on local servers; retry plainly
            # rather than failing the turn over a telemetry field.
            if "stream_options" in str(exc):
                kwargs.pop("stream_options", None)
                try:
                    for chunk in self.client.chat.completions.create(**kwargs):
                        if chunk.choices:
                            piece = getattr(chunk.choices[0].delta, "content", None)
                            if piece:
                                yield piece
                    return
                except Exception as inner:
                    raise self._wrap(inner) from inner
            raise self._wrap(exc) from exc
