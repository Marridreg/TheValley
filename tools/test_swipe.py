#!/usr/bin/env python3
"""Prove a swipe changes the words and nothing else. No API key, no cost.

A swipe re-tells the turn you are already in. That means the GM must not run
again, the state must not move again, the clock must not tick again, and the
transcript must end up pointing at the take you actually chose. It also means
the narrator has to be put back in the position it was in the first time —
without this turn's own exchange in the history it reads, or the re-roll is
being asked to continue from the take it is supposed to replace.

    python tools/test_swipe.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Runs real turns, and turns autosave. Keep it out of the live saves directory.
os.environ["VALLEY_SAVES_DIR"] = tempfile.mkdtemp(prefix="valley_swipe_")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.gm import GameMaster  # noqa: E402
from engine.narrator import Narrator  # noqa: E402
from engine.presets import PresetManager  # noqa: E402
from engine.providers.base import Capabilities, Provider  # noqa: E402
from engine.state import StateManager  # noqa: E402
from engine.wall import Wall  # noqa: E402

PACKET = {
    "scene_context": {"npcs_present": ["moreau"], "location": "the chapel"},
    "state_updates": [
        {"path": "pc.vitals.health.current", "op": "add", "value": -0.05, "reason": "cold"},
        {"path": "world.attention.dimitrescu", "op": "add", "value": 0.1, "reason": "noise"},
    ],
    "information_release": {
        "reveal_this_turn": ["moreau.capability"],
        "discovery_unlock": "moreau.loneliness",
    },
    "hud": {"hp": 0.8},
    "npc_direction": [{"npc": "moreau", "portrait_state": "wary"}],
}


class CountingProvider(Provider):
    """Fake provider. Counts calls and returns a different take each time."""

    def __init__(self, name: str, packet: dict | None = None):
        super().__init__(f"fake-{name}")
        self.name = name
        self.packet = packet
        self.json_calls = 0
        self.stream_calls = 0
        self.histories: list[list[dict]] = []

    @property
    def caps(self) -> Capabilities:
        return Capabilities(schema_forcing=True, caching="none", effort=False)

    def complete_json(self, system, messages, schema, params):
        self.json_calls += 1
        return self.packet

    def stream_text(self, system, messages, params):
        self.stream_calls += 1
        # Record the user/assistant history this call was shown.
        self.histories.append([m for m in messages])
        yield f"take {self.stream_calls}."

    def context_text(self) -> str:
        return ""


def build_wall() -> Wall:
    wall = Wall.__new__(Wall)
    wall.root = ROOT
    wall.config = {}
    wall.data_dir = ROOT / "data"
    wall.state = StateManager(wall.data_dir)
    wall.presets = PresetManager(wall.data_dir / "presets")
    wall.dev_mode = False
    wall.feedback = []
    wall.last_input = None
    wall.busy = False
    wall.last_turn = None
    wall.resumed_from = None
    wall.gm = GameMaster(CountingProvider("gm", packet=PACKET), max_tokens=4000)
    wall.narrator = Narrator(CountingProvider("narrator"), max_tokens=3000, history_turns=20)
    wall.state.current_npcs = ["moreau"]
    return wall


def main() -> int:
    wall = build_wall()
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            failures.append(f"{label}{': ' + detail if detail else ''}")

    events: list[dict] = []
    wall.run_turn("I approach the chapel, keeping low.", events.append)

    hp_after_turn = wall.state.pc["vitals"]["health"]["current"]
    attention_after_turn = wall.state.world["attention"]["dimitrescu"]
    revelations_after_turn = list(wall.state.revelation_log)
    discovered_after_turn = list(wall.state.discovered)

    print("\nafter one turn")
    check("a take was recorded", wall.last_turn is not None and len(wall.last_turn.swipes) == 1)
    check("transcript holds the take", wall.state.chat_history[-1]["content"] == "take 1.")
    check("turn count is 1", wall.state.turn_count == 1)

    # ── swipe forward: generates a new take ──
    print("\nswipe forward")
    events.clear()
    wall.run_swipe(1, events.append)
    types = [e["type"] for e in events]

    check("GM was NOT called again", wall.gm.provider.json_calls == 1,
          f"{wall.gm.provider.json_calls} calls")
    check("narrator WAS called again", wall.narrator.provider.stream_calls == 2)
    check("two takes now held", len(wall.last_turn.swipes) == 2)
    check("index moved to the new take", wall.last_turn.index == 1)
    check("transcript points at the new take",
          wall.state.chat_history[-1]["content"] == "take 2.")
    check("no duplicate transcript entry", len(wall.state.chat_history) == 2,
          f"{len(wall.state.chat_history)} messages")
    check("turn count did NOT advance", wall.state.turn_count == 1)
    check("state updates were NOT re-applied",
          wall.state.pc["vitals"]["health"]["current"] == hp_after_turn
          and wall.state.world["attention"]["dimitrescu"] == attention_after_turn,
          f"health {wall.state.pc['vitals']['health']['current']} vs {hp_after_turn}")
    check("revelations were NOT re-logged", wall.state.revelation_log == revelations_after_turn)
    check("discoveries were NOT re-logged", wall.state.discovered == discovered_after_turn)
    check("UI told to rewrite in place, not append",
          "swipe_begin" in types and "prose_start" not in types)
    check("counter sent to UI", any(e["type"] == "swipe_info" for e in events))
    check("turn released the input", types[-1] == "done")

    # The invariant that is easy to get wrong: the re-roll must not see the take
    # it is replacing.
    second_call_history = wall.narrator.provider.histories[1]
    seen = "\n".join(str(m.get("content")) for m in second_call_history)
    check("re-roll was NOT shown its own previous take", "take 1." not in seen)
    check("re-roll still saw the player's action", "chapel" in seen)

    # ── swipe back: free, no generation ──
    print("\nswipe back")
    events.clear()
    wall.run_swipe(-1, events.append)
    check("no new model call", wall.narrator.provider.stream_calls == 2)
    check("index moved back", wall.last_turn.index == 0)
    check("transcript points at the first take",
          wall.state.chat_history[-1]["content"] == "take 1.")
    check("UI given the full text to swap in",
          any(e["type"] == "swipe_set" and e["text"] == "take 1." for e in events))

    print("\nswipe back past the first")
    events.clear()
    wall.run_swipe(-1, events.append)
    check("refuses politely", any("first take" in str(e.get("text", "")) for e in events))
    check("index unchanged", wall.last_turn.index == 0)

    # ── forward again from the middle: re-uses take 2 rather than regenerating ──
    print("\nswipe forward into an existing take")
    events.clear()
    wall.run_swipe(1, events.append)
    check("no new model call", wall.narrator.provider.stream_calls == 2)
    check("index at take 2", wall.last_turn.index == 1)

    # ── a fresh turn resets the swipe set ──
    print("\nnext turn")
    events.clear()
    wall.run_turn("I step inside.", events.append)
    check("swipes reset for the new moment", len(wall.last_turn.swipes) == 1)
    check("turn count advanced", wall.state.turn_count == 2)
    check("GM ran for the new turn", wall.gm.provider.json_calls == 2)

    # ── swiping before any turn ──
    print("\nswipe with nothing to swipe")
    fresh = build_wall()
    events.clear()
    fresh.run_swipe(1, events.append)
    check("says so instead of crashing",
          any("nothing to swipe" in str(e.get("text", "")) for e in events))
    check("input released anyway", events[-1]["type"] == "done")

    print()
    if failures:
        print(f"{len(failures)} FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all checks passed — a swipe changes the words and nothing else.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
