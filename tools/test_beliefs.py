#!/usr/bin/env python3
"""Prove the belief stack resolves. No API key, no network, no cost.

Loads the real factions.json and real character cards, then asserts the
resolution order (ledger -> seed -> chain -> miss), computed divergence, the
parentless exceptions, the unnamed-villager catch-all, and the v1 disclosure
postures — including Anton's doubt, which must be spoken freely alone, held
close at Luiza's hearth, and buried in front of Eugen.

    python tools/test_beliefs.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["VALLEY_SAVES_DIR"] = tempfile.mkdtemp(prefix="valley_test_")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.beliefs import BeliefResolver, POSTURES  # noqa: E402
from engine.state import StateManager  # noqa: E402

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(label)


def main() -> int:
    state = StateManager(ROOT / "data")
    r = BeliefResolver(ROOT / "data", state)

    print("\nchains")
    check("bela walks house -> court -> valley",
          r.faction_chain("bela") == ["castle_dimitrescu", "court", "valley"])
    check("eugen walks church -> village -> valley",
          r.faction_chain("eugen") == ["church", "village", "valley"])
    check("duke is parentless", r.faction_chain("duke") == [])
    check("miranda is parentless", r.faction_chain("miranda") == [])
    check("unnamed villager gets the catch-all",
          r.faction_chain("vasile") == ["village", "valley"])

    print("\nresolution order")
    b = r.resolve("bela", "miranda")
    check("nearest orthodoxy wins", b is not None and b.source == "faction:court")
    check("chain default is not divergent", b is not None and not b.divergent)
    b = r.resolve("anton", "lycans")
    check("villager inherits village default", b is not None and b.source == "faction:village")
    b = r.resolve("bela", "woods_at_night")
    check("root bedrock reaches everyone", b is not None and b.source == "faction:valley")
    check("no orthodoxy, no seed, no ledger -> miss (generate-and-commit)",
          r.resolve("duke", "ceremony") is None)
    check("subject nobody covers -> miss",
          r.resolve("bela", "the_cellar_ledger") is None)

    print("\nledger overrides (tier 3 beats tier 1)")
    state.beliefs["anton"] = {
        "miranda": "the Holy Mother let my plot die; her providence has holes in it"
    }
    b = r.resolve("anton", "miranda")
    check("ledger wins", b is not None and b.source == "ledger")
    check("divergence is computed, not authored", b is not None and b.divergent)

    print("\npostures — anton's doubt, three rooms")
    doubt = r.resolve("anton", "miranda")
    check("alone: no clash pressure applies",
          r.posture("anton", doubt, []) in POSTURES[:2])
    at_hearth = r.posture("anton", doubt, ["luiza", "roxana"])
    check("village company: hard enforcement -> admits_if_pressed",
          at_hearth == "admits_if_pressed", at_hearth)
    before_church = r.posture("anton", doubt, ["luiza", "eugen"])
    check("eugen present: lethal enforcement -> deflects",
          before_church == "deflects", before_church)
    conforming = r.resolve("luiza", "miranda")
    check("a conforming belief is freely spoken anywhere",
          r.posture("luiza", conforming, ["eugen", "miranda"]) == "volunteers")

    print("\npostures — the shield belongs to the order")
    # Conforming to your own orthodoxy protects you even from a rival order
    # that despises it: the village prays in front of Heisenberg.
    check("orthodoxy shields against a rival court",
          r.posture("luiza", conforming, ["heisenberg"]) == "volunteers")
    # But HAVING no orthodoxy is not conforming. A parentless speaker stands
    # behind no one; their belief is measured against the room like any heresy.
    state.beliefs["duke"] = {"miranda": "a parasite wearing a saint's face"}
    heresy = r.resolve("duke", "miranda")
    check("parentless heresy resolves from the ledger, non-divergent",
          heresy is not None and heresy.source == "ledger" and not heresy.divergent)
    in_room = r.posture("duke", heresy, ["eugen"])
    check("parentless speaker feels the room: deflects before eugen",
          in_room == "deflects", in_room)
    check("and speaks freely alone", r.posture("duke", heresy, []) == "volunteers")

    print("\ntier 2 — seeds (injected via the card cache; no authored card has one yet)")
    state._card("anton")["private"]["seed_beliefs"] = {
        "ceremony": "the blessing takes more than it gives back"
    }
    b = r.resolve("anton", "ceremony")
    check("seed beats chain", b is not None and b.source == "seed")
    check("seed divergence is computed", b is not None and b.divergent)
    state.beliefs.setdefault("anton", {})["ceremony"] = "a culling, whatever the church calls it"
    b = r.resolve("anton", "ceremony")
    check("ledger beats seed", b is not None and b.source == "ledger")

    print("\nchains — multiple memberships stay nearest-first")
    r.members["_test_dual"] = ["church", "fallow_plot"]
    chain = r.faction_chain("_test_dual")
    check("both memberships precede any parent",
          chain == ["church", "fallow_plot", "village", "valley"], str(chain))
    del r.members["_test_dual"]

    print("\ntier 3 survives a save")
    state.save("_belief_roundtrip")
    fresh = StateManager(ROOT / "data")
    fresh.load("_belief_roundtrip")
    check("generate-and-commit does not recur across sessions",
          fresh.beliefs.get("anton", {}).get("miranda")
          == state.beliefs["anton"]["miranda"])

    print("\nwall hygiene")
    import engine.narrator as narrator
    src = (ROOT / "engine" / "narrator.py").read_text(encoding="utf-8")
    check("narrator.py never imports beliefs", "beliefs" not in src)
    check("narrator module has no resolver attribute",
          not hasattr(narrator, "BeliefResolver"))

    print()
    if failures:
        print(f"{len(failures)} FAILED: " + "; ".join(failures))
        return 1
    print("all checks passed — beliefs resolve, postures hold, the Wall stands.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
