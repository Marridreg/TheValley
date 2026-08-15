"""Provider factory.

`build(role, config)` turns a config block into a live Provider. The GM and the
narrator are built independently, so mixing backends is a first-class setup
rather than a hack — running the GM on something cheap and local while the
narrator runs on Claude is a genuinely good configuration: the GM's job is
bookkeeping and gating against a fixed schema, the narrator's job is prose.
"""

from __future__ import annotations

import os

from .base import (
    Capabilities,
    GenParams,
    Provider,
    ProviderError,
    SystemBlock,
    Usage,
    extract_json,
)

__all__ = [
    "Capabilities",
    "GenParams",
    "Provider",
    "ProviderError",
    "SystemBlock",
    "Usage",
    "extract_json",
    "build",
    "PRESETS",
]


# Known backends. `kind` picks the adapter; everything else is defaults the
# user's config block can override.
PRESETS: dict[str, dict] = {
    "anthropic": {
        "kind": "anthropic",
        "base_url": None,
        "env_key": "ANTHROPIC_API_KEY",
        "label": "anthropic",
    },
    "openrouter": {
        "kind": "openai_compat",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "label": "openrouter",
        # Ranking headers. Harmless, and OpenRouter asks for them.
        "extra_headers": {
            "HTTP-Referer": "https://github.com/the-valley-rpg",
            "X-Title": "The Valley",
        },
        # Route only to upstreams that honour what we send, so a schema-forced
        # request is not silently downgraded to unconstrained generation.
        "extra_body": {"provider": {"require_parameters": True}},
    },
    "openai": {
        "kind": "openai_compat",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "label": "openai",
    },
    "deepseek": {
        "kind": "openai_compat",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "label": "deepseek",
    },
    "groq": {
        "kind": "openai_compat",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "label": "groq",
    },
    "together": {
        "kind": "openai_compat",
        "base_url": "https://api.together.xyz/v1",
        "env_key": "TOGETHER_API_KEY",
        "label": "together",
    },
    # Local servers: llama.cpp, LM Studio, text-generation-webui, vLLM,
    # TabbyAPI, Ollama's OpenAI shim. No key, no caching, but every sampler.
    "local": {
        "kind": "openai_compat",
        "base_url": "http://localhost:5000/v1",
        "env_key": None,
        "label": "local",
        "capabilities": {"caching": "none", "schema_forcing": False},
    },
    "ollama": {
        "kind": "openai_compat",
        "base_url": "http://localhost:11434/v1",
        "env_key": None,
        "label": "ollama",
        "capabilities": {"caching": "none"},
    },
    # Anything else with a /v1/chat/completions endpoint. Set base_url yourself.
    "custom": {
        "kind": "openai_compat",
        "base_url": None,
        "env_key": None,
        "label": "custom",
    },
}


def _merge(preset: dict, block: dict) -> dict:
    """Config block over preset defaults, merging the nested dicts."""
    out = dict(preset)
    for key, value in block.items():
        if key in ("extra_headers", "extra_body", "capabilities") and isinstance(value, dict):
            out[key] = {**out.get(key, {}), **value}
        elif value is not None:
            out[key] = value
    return out


def build(block: dict, *, role: str = "model") -> Provider:
    """Instantiate a provider from a resolved config block.

    Expected keys: provider, model, and optionally api_key, base_url,
    capabilities, extra_headers, extra_body.
    """
    provider_name = (block.get("provider") or "anthropic").strip().lower()
    if provider_name not in PRESETS:
        raise ProviderError(
            f"unknown provider '{provider_name}' for the {role}. "
            f"Known: {', '.join(sorted(PRESETS))}. "
            "Use provider: custom with a base_url for anything else."
        )

    cfg = _merge(PRESETS[provider_name], block)
    model = cfg.get("model")
    if not model:
        raise ProviderError(f"no model set for the {role} (provider: {provider_name})")

    api_key = cfg.get("api_key") or None
    if not api_key and cfg.get("env_key"):
        api_key = os.environ.get(cfg["env_key"]) or None

    if cfg["kind"] == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(model, api_key=api_key, base_url=cfg.get("base_url"))

    from .openai_compat import OpenAICompatProvider

    base_url = cfg.get("base_url")
    if not base_url:
        raise ProviderError(
            f"provider '{provider_name}' needs a base_url for the {role} "
            "(e.g. http://localhost:8080/v1)"
        )
    if not api_key and provider_name not in ("local", "ollama", "custom"):
        raise ProviderError(
            f"no API key for {provider_name}. Set {cfg.get('env_key')} in your "
            f"environment, or api_key under {role} in config.yaml."
        )

    return OpenAICompatProvider(
        model,
        api_key=api_key,
        base_url=base_url,
        capability_overrides=cfg.get("capabilities"),
        extra_headers=cfg.get("extra_headers"),
        extra_body=cfg.get("extra_body"),
        label=cfg.get("label"),
    )
