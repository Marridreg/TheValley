"""Anthropic native backend.

The premium path. Two things only available here:

  - Constrained decoding via output_config.format, so the briefing packet
    cannot come back malformed. No repair loop ever runs.
  - Explicit cache breakpoints, so the secret vault and the full character
    cards — which are byte-identical every turn — bill at roughly a tenth of
    list price after the first call.

Frontier Claude rejects temperature/top_p/top_k rather than ignoring them, so
the capability table reports them off and filter_params drops them.
"""

from __future__ import annotations

from typing import Iterator

from .base import (
    Capabilities,
    GenParams,
    Provider,
    ProviderError,
    SystemBlock,
    Usage,
)

# Prefix families, so a config naming a dated snapshot still matches.
_MODERN = (
    "claude-fable-5",
    "claude-mythos-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
)
_XHIGH = (
    "claude-fable-5",
    "claude-mythos-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-5",
)
_MID_SYSTEM = (
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-fable-5",
    "claude-mythos-5",
)
_STRUCTURED = _MODERN + ("claude-haiku-4-5", "claude-opus-4-5", "claude-opus-4-1")


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None = None, base_url: str | None = None):
        super().__init__(model)
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise ProviderError(
                "the `anthropic` package is required for provider=anthropic "
                "(pip install anthropic)"
            ) from exc

        self._sdk = anthropic
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        # With no api_key the SDK resolves ANTHROPIC_API_KEY, then an
        # `ant auth login` profile. Both are fine.
        self.client = anthropic.Anthropic(**kwargs)
        self._caps = self._detect()

    def _detect(self) -> Capabilities:
        m = self.model
        modern = any(m.startswith(p) for p in _MODERN)
        return Capabilities(
            schema_forcing=any(m.startswith(p) for p in _STRUCTURED),
            caching="explicit",
            # Deliberately all False on modern models: these are 400s, not
            # no-ops. See the module docstring.
            temperature=not modern,
            top_p=not modern,
            top_k=not modern,
            min_p=False,
            repetition_penalty=False,
            frequency_presence_penalty=False,
            effort=modern or m.startswith("claude-opus-4-5"),
            effort_levels=(
                ("low", "medium", "high", "xhigh", "max")
                if any(m.startswith(p) for p in _XHIGH)
                else ("low", "medium", "high", "max")
                if modern
                else ("low", "medium", "high")
            ),
            mid_conversation_system=any(m.startswith(p) for p in _MID_SYSTEM),
            streaming=True,
        )

    @property
    def caps(self) -> Capabilities:
        return self._caps

    # ── request assembly ──

    def _system_param(self, system: list[SystemBlock]) -> list[dict]:
        """System blocks with cache breakpoints where requested.

        Anthropic renders tools -> system -> messages, and we send no tools,
        so a breakpoint on the last stable system block caches everything
        above it. Max 4 breakpoints per request; we use at most 2.
        """
        blocks = []
        for b in system:
            if not b.text.strip():
                continue
            block: dict = {"type": "text", "text": b.text}
            if b.cache:
                block["cache_control"] = {"type": "ephemeral"}
            blocks.append(block)
        return blocks

    def _base_kwargs(self, system: list[SystemBlock], params: GenParams) -> dict:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": params.max_tokens,
            "system": self._system_param(system),
        }
        kwargs.update(self.filter_params(params))
        if params.stop:
            kwargs["stop_sequences"] = params.stop

        effort = self.resolve_effort(params.effort)
        if effort:
            kwargs["output_config"] = {"effort": effort}
        return kwargs

    def _record(self, usage) -> None:
        self.last_usage = Usage(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_write=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )

    # ── the two calls ──

    def complete_json(
        self,
        system: list[SystemBlock],
        messages: list[dict],
        schema: dict,
        params: GenParams,
    ) -> dict:
        from .base import extract_json

        kwargs = self._base_kwargs(system, params)
        kwargs["messages"] = messages
        if self._caps.schema_forcing:
            kwargs["output_config"] = {
                **kwargs.get("output_config", {}),
                "format": {"type": "json_schema", "schema": schema},
            }

        try:
            resp = self.client.messages.create(**kwargs)
        except self._sdk.APIStatusError as exc:
            raise ProviderError(
                f"{self.model}: {exc.status_code} {getattr(exc, 'message', exc)}",
                retryable=exc.status_code in (408, 409, 429) or exc.status_code >= 500,
            ) from exc
        except self._sdk.APIConnectionError as exc:
            raise ProviderError(f"could not reach Anthropic: {exc}", retryable=True) from exc

        self._record(resp.usage)

        if resp.stop_reason == "refusal":
            raise ProviderError(
                "the GM model declined this request "
                f"({getattr(resp.stop_details, 'category', 'unspecified')})"
            )

        text = "".join(b.text for b in resp.content if b.type == "text")
        if resp.stop_reason == "max_tokens":
            raise ProviderError(
                "briefing packet truncated — raise gm_max_tokens in config.yaml "
                "(on thinking models max_tokens covers thinking plus output)"
            )
        return extract_json(text)

    def stream_text(
        self,
        system: list[SystemBlock],
        messages: list[dict],
        params: GenParams,
    ) -> Iterator[str]:
        kwargs = self._base_kwargs(system, params)
        kwargs["messages"] = messages

        try:
            with self.client.messages.stream(**kwargs) as stream:
                for chunk in stream.text_stream:
                    yield chunk
                final = stream.get_final_message()
                self._record(final.usage)
                if final.stop_reason == "refusal":
                    yield (
                        "\n\n[The narrator declined to continue this scene. "
                        "Try steering the action elsewhere.]"
                    )
        except self._sdk.APIStatusError as exc:
            raise ProviderError(
                f"{self.model}: {exc.status_code} {getattr(exc, 'message', exc)}",
                retryable=exc.status_code in (408, 409, 429) or exc.status_code >= 500,
            ) from exc
        except self._sdk.APIConnectionError as exc:
            raise ProviderError(f"could not reach Anthropic: {exc}", retryable=True) from exc

    def supports_role_system(self) -> bool:
        return self._caps.mid_conversation_system
