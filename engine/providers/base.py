"""Provider abstraction.

The engine talks to models through this interface only. Nothing above this
layer knows whether it is speaking to Anthropic, OpenRouter, OpenAI, or a
llama.cpp server on localhost.

Two calls are all The Valley needs:

    complete_json()  — the GM. Must return a dict matching a JSON schema.
    stream_text()    — the narrator. Yields prose token by token.

Everything else is capability negotiation. Providers differ in three ways that
actually matter to us, and each has a defined degradation path:

    schema forcing   — native constrained decoding, else prompt + validate +
                       one repair attempt. Never crashes the turn.
    prompt caching   — explicit breakpoints, implicit prefix caching, or none.
                       Worst case you pay full price for the vault every turn.
    sampling knobs   — frontier Claude rejects temperature/top_p/top_k
                       outright; most other models accept them and several
                       accept min_p and repetition_penalty too. We send only
                       what the target advertises.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


class ProviderError(RuntimeError):
    """Anything that went wrong talking to a model, normalised across SDKs."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class Capabilities:
    """What a given provider+model pair will actually accept.

    Populated per provider; the engine branches on these rather than on
    provider names, so adding a backend never means touching the engine.
    """

    # Constrained decoding. When False the GM falls back to prompted JSON
    # plus validate-and-repair, which is what the original design feared.
    schema_forcing: bool = False

    # "explicit" — we mark cache breakpoints ourselves (Anthropic)
    # "implicit" — the backend caches long prefixes on its own (OpenAI,
    #              DeepSeek, and OpenRouter for those upstreams)
    # "none"     — no caching; the vault is re-billed every turn
    caching: str = "none"

    # Classic sampler knobs. Frontier Claude 400s on these; most everything
    # else wants them.
    temperature: bool = False
    top_p: bool = False
    top_k: bool = False
    min_p: bool = False
    repetition_penalty: bool = False
    frequency_presence_penalty: bool = False

    # Reasoning depth. Anthropic spells it output_config.effort; OpenAI-style
    # endpoints spell it reasoning_effort or OpenRouter's `reasoning` object.
    effort: bool = False
    effort_levels: tuple[str, ...] = ()

    # Whether a {"role": "system"} entry mid-conversation is honoured. When
    # False the GM briefing is folded into the user turn instead.
    mid_conversation_system: bool = False

    # Server-side streaming.
    streaming: bool = True

    def describe(self) -> str:
        bits = []
        bits.append("schema: forced" if self.schema_forcing else "schema: prompted+repair")
        bits.append(f"cache: {self.caching}")
        knobs = [
            n
            for n, on in (
                ("temp", self.temperature),
                ("top_p", self.top_p),
                ("top_k", self.top_k),
                ("min_p", self.min_p),
                ("rep_pen", self.repetition_penalty),
            )
            if on
        ]
        bits.append("samplers: " + (",".join(knobs) if knobs else "none"))
        if self.effort:
            bits.append("effort: " + "/".join(self.effort_levels))
        return " | ".join(bits)


@dataclass
class SystemBlock:
    """A chunk of system-level context.

    `cache` marks the end of a stable prefix. Providers with explicit caching
    place a breakpoint here; providers with implicit or no caching ignore it.
    Ordering is load-bearing regardless of backend: stable blocks first,
    volatile blocks last, because every caching scheme is a prefix match.
    """

    text: str
    cache: bool = False


@dataclass
class GenParams:
    """A generation request, before any provider-specific filtering."""

    max_tokens: int = 3000
    effort: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    repetition_penalty: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: list[str] = field(default_factory=list)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0

    def line(self) -> str:
        cached = ""
        if self.cache_read or self.cache_write:
            cached = f"  (cache r{self.cache_read} w{self.cache_write})"
        return f"in {self.input_tokens} / out {self.output_tokens}{cached}"


class Provider(ABC):
    """Base class for all backends."""

    name: str = "provider"

    def __init__(self, model: str):
        self.model = model
        self.last_usage = Usage()

    @property
    @abstractmethod
    def caps(self) -> Capabilities: ...

    @abstractmethod
    def complete_json(
        self,
        system: list[SystemBlock],
        messages: list[dict],
        schema: dict,
        params: GenParams,
    ) -> dict:
        """Return a dict conforming to `schema`. Raises ProviderError if it
        cannot, after exhausting its fallback path."""

    @abstractmethod
    def stream_text(
        self,
        system: list[SystemBlock],
        messages: list[dict],
        params: GenParams,
    ) -> Iterator[str]:
        """Yield text fragments as they arrive."""

    # ── shared helpers ──

    def filter_params(self, params: GenParams) -> dict:
        """Reduce GenParams to the subset this model accepts.

        This is the whole point of the capability table: a config file written
        for a local Mistral can be pointed at Claude Opus without the request
        becoming a 400, and vice versa. Unsupported knobs are dropped
        silently — they are preferences, not requirements.
        """
        caps = self.caps
        out: dict = {}
        pairs = (
            ("temperature", params.temperature, caps.temperature),
            ("top_p", params.top_p, caps.top_p),
            ("top_k", params.top_k, caps.top_k),
            ("min_p", params.min_p, caps.min_p),
            ("repetition_penalty", params.repetition_penalty, caps.repetition_penalty),
            ("frequency_penalty", params.frequency_penalty, caps.frequency_presence_penalty),
            ("presence_penalty", params.presence_penalty, caps.frequency_presence_penalty),
        )
        for key, value, supported in pairs:
            if value is not None and supported:
                out[key] = value
        return out

    def resolve_effort(self, effort: str | None) -> str | None:
        caps = self.caps
        if not effort or not caps.effort:
            return None
        effort = effort.lower()
        if effort in caps.effort_levels:
            return effort
        # Clamp to the nearest level this model actually has rather than
        # failing: a preset written for Claude's `xhigh` should still mean
        # "work hard" on a backend that only knows low/medium/high.
        order = ("low", "medium", "high", "xhigh", "max")
        if effort not in order:
            return caps.effort_levels[-1] if caps.effort_levels else None
        wanted = order.index(effort)
        best, best_dist = None, 99
        for level in caps.effort_levels:
            if level in order:
                dist = abs(order.index(level) - wanted)
                if dist < best_dist:
                    best, best_dist = level, dist
        return best


def extract_json(text: str) -> dict:
    """Pull an object out of a model response that may be wrapped in prose.

    Needed only on the prompted-JSON fallback path. Handles the three things
    models actually do: fenced code blocks, a bare object with chatter around
    it, and clean output.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("empty response")

    if text.startswith("```"):
        body = text.split("```", 2)
        if len(body) >= 2:
            candidate = body[1]
            if candidate.lstrip().startswith("json"):
                candidate = candidate.lstrip()[4:]
            text = candidate.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Brace matching, string-aware so a `}` inside a value doesn't fool us.
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unterminated JSON object in response")
