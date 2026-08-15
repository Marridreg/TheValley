#!/usr/bin/env python3
"""Check both backends answer before launching the window.

Cheaper and far easier to read than discovering a bad key or a wrong model id
through a GUI error. Makes one tiny call per configured role.

    python tools/preflight.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from engine.providers import GenParams, ProviderError, SystemBlock, build  # noqa: E402


def check(role: str, block: dict) -> bool:
    print(f"\n{role.upper()}")
    if not block:
        print(f"  ! no '{role}' block in config.yaml")
        return False

    print(f"  provider : {block.get('provider')}")
    print(f"  model    : {block.get('model')}")

    try:
        provider = build(dict(block), role=role)
    except ProviderError as exc:
        print(f"  ! {exc}")
        return False

    print(f"  caps     : {provider.caps.describe()}")

    system = [SystemBlock("You are a test harness. Answer with one word.")]
    messages = [{"role": "user", "content": "Reply with the single word: ready"}]
    # Generous ceiling: on always-thinking models max_tokens covers thinking too,
    # and a tight cap would return an empty string and look like a failure.
    params = GenParams(max_tokens=2000)

    t0 = time.time()
    try:
        got = "".join(provider.stream_text(system, messages, params)).strip()
    except ProviderError as exc:
        print(f"  ! {exc}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  ! unexpected: {type(exc).__name__}: {exc}")
        return False

    elapsed = time.time() - t0
    u = provider.last_usage
    print(f"  reply    : {got[:70]!r}  ({elapsed:.1f}s)")
    print(f"  usage    : {u.line()}")
    if not got:
        print("  ! empty reply — if this is a thinking model, raise max_tokens")
        return False
    print("  OK")
    return True


def main() -> int:
    path = ROOT / "config.yaml"
    if not path.exists():
        print("no config.yaml")
        return 1
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"config.yaml does not parse:\n{exc}")
        return 1

    # Catch the blank-placeholder case with a clear message rather than a 401.
    for role in ("gm", "narrator"):
        block = cfg.get(role) or {}
        provider = (block.get("provider") or "").lower()
        needs_key = provider not in ("ollama", "local", "anthropic")
        if needs_key and not (block.get("api_key") or "").strip():
            import os

            envs = {"openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY"}
            if not os.environ.get(envs.get(provider, "")):
                print(
                    f"\n{role.upper()}: api_key is still blank and "
                    f"{envs.get(provider, 'the provider env var')} is unset.\n"
                    f"  Paste your key between the quotes on the api_key line in "
                    f"config.yaml and run this again."
                )
                return 1

    ok = all(check(role, cfg.get(role) or {}) for role in ("gm", "narrator"))
    print("\n" + ("PREFLIGHT PASSED — safe to launch." if ok else "PREFLIGHT FAILED."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
