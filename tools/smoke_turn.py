#!/usr/bin/env python3
"""Run ONE real turn against the configured providers, headless and verbose.

This is the test the GUI can't be: every stage is printed, so when something
fails you can see which of the two models did it and what it actually returned.
Run this before ever launching main.py against a new backend.

    python tools/smoke_turn.py
    python tools/smoke_turn.py "I put my back to the chapel wall and listen."

Nothing is saved. State is mutated in memory only, so this never touches your
save files.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from engine.providers import ProviderError  # noqa: E402
from engine.wall import Wall  # noqa: E402

DEFAULT_ACTION = (
    "I head down toward the reservoir, keeping to the treeline, and stop at the "
    "edge of the water to look at the drowned chapel before going closer."
)

BAR = "─" * 72


def est_gm_prompt_tokens(wall) -> int:
    """Rough size of the GM request we just built, chars/4."""
    from engine.gm import GM_INSTRUCTIONS

    try:
        chars = (
            len(GM_INSTRUCTIONS)
            + len(wall.gm._secret_block(wall.state))
            + len(wall.gm._turn_block(wall.state, "", []))
        )
        return chars // 4
    except Exception:
        return 0


def main() -> int:
    action = " ".join(sys.argv[1:]) or DEFAULT_ACTION

    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        print("no config.yaml — copy config.example.yaml and fill it in")
        return 1
    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    print(BAR)
    try:
        wall = Wall(config, ROOT)
    except ProviderError as exc:
        print(f"configuration problem:\n  {exc}")
        return 1
    print(wall.banner())
    for w in wall.warnings():
        print(f"  ! {w}")
    print(BAR)

    # Seed the scene so the GM has somewhere to put us. Without this the very
    # first turn has an empty cast and the GM has to invent the location.
    wall.state.current_npcs = ["moreau"]
    wall.state.pc.setdefault("location", {})
    wall.state.pc["location"] = {"current": "reservoir", "sub_location": "the shore path"}

    print(f"\nPLAYER: {action}\n")

    stages: dict[str, float] = {}
    t0 = time.time()
    prose_chars = 0
    first_token_at: float | None = None
    errors: list[str] = []

    def emit(ev: dict) -> None:
        nonlocal prose_chars, first_token_at
        kind = ev["type"]
        if kind == "status":
            stages.setdefault("gm_start", time.time() - t0)
            print(f"[{time.time()-t0:5.1f}s] {ev['text']}")
        elif kind == "briefing":
            stages["gm_done"] = time.time() - t0
            p = ev["packet"]
            sc = p.get("scene_context", {})
            ar = p.get("action_resolution", {})
            ir = p.get("information_release", {})
            print(f"\n{BAR}\nGM BRIEFING  (packet received in {stages['gm_done']:.1f}s)\n{BAR}")
            print(f"  location    : {sc.get('location')} / {sc.get('sub_location')}")
            print(f"  time/weather: {sc.get('time_of_day')} / {sc.get('weather')}")
            print(f"  present     : {sc.get('npcs_present')}")
            print(f"  ambient     : {str(sc.get('ambient'))[:150]}")
            print(f"\n  ADJUDICATION: {str(ar.get('mechanical_result'))[:300]}")
            print(f"  GUIDANCE    : {str(ar.get('narration_guidance'))[:300]}")
            print(f"\n  releases    : {ir.get('reveal_this_turn')}")
            print(f"  fragment    : {ir.get('fragment_trigger')}")
            print(f"  discovery   : {ir.get('discovery_unlock')}")
            for d in p.get("npc_direction") or []:
                print(f"\n  {str(d.get('npc')).upper()} [{d.get('portrait_state')}]")
                print(f"    feeling: {str(d.get('psyche_summary'))[:200]}")
                print(f"    does   : {str(d.get('behavioral_instruction'))[:200]}")
            for u in p.get("state_updates") or []:
                v = u.get("number") if u.get("number") is not None else u.get("text")
                print(f"  state: {u.get('path')} {u.get('op')} {v!r}  ({u.get('reason')})")
            for o in p.get("offscreen_events") or []:
                print(f"  offscreen (GM-only): {str(o.get('summary'))[:110]}")
        elif kind == "hud":
            h = ev["hud"]
            print(
                f"\n  HUD: hp {h.get('hp')} sta {h.get('stamina')} mold {h.get('mold')} "
                f"| {h.get('weapon')} | {h.get('location')} | {h.get('time')} "
                f"| day-to-ceremony {h.get('days_to_ceremony')}"
            )
        elif kind == "portraits":
            print(f"  portraits: {[(p['npc'], p['mood'], bool(p['src'])) for p in ev['portraits']]}")
        elif kind == "prose_start":
            stages["prose_start"] = time.time() - t0
            print(f"\n{BAR}\nNARRATOR\n{BAR}")
        elif kind == "delta":
            if first_token_at is None:
                first_token_at = time.time() - t0
            prose_chars += len(ev["text"])
            sys.stdout.write(ev["text"])
            sys.stdout.flush()
        elif kind == "prose_end":
            stages["prose_done"] = time.time() - t0
        elif kind == "fragment":
            print(f"\n\n  [FRAGMENT] {ev['text']}")
        elif kind == "discovery":
            print(f"\n  [DISCOVERY] {ev['text']}")
        elif kind == "usage":
            print(f"\n  usage [{ev['role']}]: {ev['text']}")
            # Silent truncation check. Some backends — Ollama's OpenAI endpoint
            # among them — quietly drop whatever does not fit the context window
            # instead of returning an error. The model then answers confidently
            # from a fragment, which is far worse than a failure. If the
            # reported input is a fraction of what we sent, say so loudly.
            if ev["role"] == "gm":
                sent = est_gm_prompt_tokens(wall)
                got = wall.gm.provider.last_usage.input_tokens
                if got and sent and got < sent * 0.6:
                    msg = (
                        f"prompt appears TRUNCATED — sent ~{sent:,} est. tokens, "
                        f"backend counted {got:,}. Raise the context window; the "
                        f"model is answering from a fragment."
                    )
                    errors.append(msg)
                    print(f"  !! {msg}")
                elif got:
                    print(f"  (sent ~{sent:,} est.; backend counted {got:,} — no truncation)")
        elif kind == "debug":
            print(f"\n  debug: {ev['text'][:600]}")
        elif kind == "system":
            print(f"\n  {ev['text']}")
        elif kind == "error":
            errors.append(ev["text"])
            print(f"\n\n  !! ERROR: {ev['text']}")
        elif kind == "done":
            print(f"\n\n{BAR}")
            print(f"turn complete in {ev['elapsed']}s")

    wall.run_turn(action, emit)

    print("\nTIMING")
    print(f"  GM briefing        : {stages.get('gm_done', float('nan')):.1f}s")
    if first_token_at:
        print(f"  first prose token  : {first_token_at:.1f}s")
    if "prose_done" in stages and "prose_start" in stages:
        dur = stages["prose_done"] - stages["prose_start"]
        rate = prose_chars / dur if dur else 0
        print(f"  prose streamed     : {prose_chars} chars in {dur:.1f}s ({rate:.0f} ch/s)")

    print("\nTHE WALL — post-turn audit")
    # The narrator just wrote a scene. Confirm nothing it received was gated.
    nar_seen = wall.narrator._world_block(
        wall.state, wall.state.current_npcs
    ) + wall.narrator._briefing_text(wall.gm.last_packet or {})
    leaks = []
    for npc in wall.state.current_npcs:
        for name in wall.state.locked_sections(npc):
            sec = wall.state._private_sections(npc)[name]
            body = sec.get("truth") if isinstance(sec, dict) else sec
            if isinstance(body, dict):
                body = " ".join(str(v) for v in body.values())
            if isinstance(body, list):
                body = " ".join(str(v) for v in body)
            if isinstance(body, str) and len(body) > 80 and body[30:90] in nar_seen:
                leaks.append(f"{npc}.{name}")
    print(f"  locked sections leaked into narrator context: {leaks or 'none'}")
    if wall.state.vault.get("_warning", "") in nar_seen:
        leaks.append("vault")
        print("  !! VAULT TEXT PRESENT IN NARRATOR CONTEXT")

    print(f"\n  revelations now held : {len(wall.state.revelation_log)}")
    print(f"  turn count           : {wall.state.turn_count}")

    ok = not errors and not leaks and prose_chars > 0
    print(f"\n{'SMOKE TEST PASSED' if ok else 'SMOKE TEST FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
