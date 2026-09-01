#!/usr/bin/env python3
"""Prove character.schema.json v0 accepts a full principal and rejects
the specific authoring sins it exists to catch. Offline, no API, no cost.

The golden character below exercises EVERY module once — it doubles as
the worked example for stage 0's compile target.

    python tools/test_schema.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from validate_schema import validate_package  # noqa: E402

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(label)


GOLDEN = {
    "meta": {"schema_version": "0", "rung": "principal"},
    "public": {
        "identity": "Sofia Albescu | 44, midwife | female | village: 'Sofia' · court: not addressed at all",
        "look": "broad-handed, quick-eyed; moves like someone counting exits",
        "capacity": "enters any village house unasked at a birth | needs Luiza's nod for the granary key | proxy: none | cannot read",
        "languages": "valley Romanian 5 child — default. No second tongue. Fence: none to leak.",
        "voice": {
            "style": "flat, midwife-practical; instructions before comfort",
            "examples": ["Boil that. Then we talk.", "The child decides, not us."]
        },
        "quirk": "keeps a tally of every birth on a knotted cord she will not explain",
        "stated_faces": {
            "the_ceremony": "calls it a mercy and a blessing, same as anyone"
        },
        "fences": {
            "never_says": ["I'm afraid", "trust me"],
            "never_does": ["asks the church for anything"]
        }
    },
    "private": {
        "sections": {
            "lost_ledger": {
                "sensitivity": "high",
                "truth": "half the infants she delivered for the church's blessing never came back; her cord counts them.",
                "rumor": "some say the midwife keeps a grudge older than the reservoir.",
                "learnable_from": ["the knotted cord, if examined", "roxana, drunk"]
            }
        },
        "seed_beliefs": {
            "ceremony": "a tithe dressed as a blessing; the valley pays in children",
            "miranda.attention": "falls on families who complain; silence keeps a house safe"
        },
        "reputation_sensitivity": "high",
        "internalization": "soft",
        "actual_faces": {
            "the_ceremony": "counts its cost by name, knot by knot, and means to be believed one day"
        },
        "self_concept": {
            "actual": "the one who counts",
            "ideal": "the one who saved them",
            "ought": "a quiet, useful woman",
            "feared": "the madwoman with the string"
        },
        "drives": [
            {
                "name": "witness",
                "want": "the count survives her, in someone's hands who believes it",
                "away": "the cord dismissed as grief-craft (never shows it uninvited)",
                "meter": {"value": 6, "low_state": "cornered"}
            }
        ],
        "logic_weight": 0.6,
        "defense_filters": [
            {
                "mechanism": "compartmentalization",
                "defends": ["self.actual", "ceremony"],
                "strength": "strong"
            }
        ],
        "states": [
            {
                "name": "cornered",
                "trigger": "the cord is touched by anyone else",
                "fragment": "Put it down. Now.",
                "behavior": "goes physically between the person and the cord; will not explain"
            }
        ],
        "energy_map": {
            "births": "level",
            "church_present": "hushed",
            "alone_with_roxana": "animated"
        },
        "tells": {
            "watched": "hands folded over the apron pocket that holds the cord",
            "unwatched": "thumbs the knots in order, lips moving"
        },
        "escalation": {
            "only": "someone reads the count back to her, name by name, and does not look away",
            "cost": "the belief that no one will ever carry it with her",
            "after": "begins teaching the names aloud; cannot stop once started"
        },
        "carry_over": "any scene where the count was doubted -> she arrives early to the next one, cord visible for the first time",
        "monologue": "They call it a blessing and I nod, because a midwife who argues delivers no one. Forty-one knots. I don't grieve — grief is for people who lost count, and I have never once lost count. The church says the children go up the mountain to be holy. Fine. Then the mountain owes me forty-one receipts. My mother said a woman's memory is her only land. I farm mine. This is who you are."
    }
}


def main() -> int:
    schema = json.loads((ROOT / "data" / "character.schema.json").read_text(encoding="utf-8"))

    print("\ngolden principal (every module exercised)")
    problems = validate_package(GOLDEN, schema)
    check("full package validates", not problems, "; ".join(problems))

    print("\nauthoring sins are caught")
    p = copy.deepcopy(GOLDEN)
    del p["private"]["actual_faces"]
    check("stated face without an actual behind it fails",
          any("mask of something" in x for x in validate_package(p, schema)))

    p = copy.deepcopy(GOLDEN)
    p["private"]["drives"][0]["meter"]["low_state"] = "nonexistent"
    check("meter threshold into an unwritten state fails",
          any("names no entry in states" in x for x in validate_package(p, schema)))

    p = copy.deepcopy(GOLDEN)
    del p["private"]["escalation"]
    check("principal without escalation fails",
          any("requires private.escalation" in x for x in validate_package(p, schema)))

    p = copy.deepcopy(GOLDEN)
    p["private"]["states"][0]["fragment"] = "x" * 120
    check("fragment over the C2 budget fails",
          any("fragment" in x for x in validate_package(p, schema)))

    p = copy.deepcopy(GOLDEN)
    p["private"]["defense_filters"][0]["mechanism"] = "vibes"
    check("unknown defense mechanism fails",
          any("mechanism" in x or "vibes" in x for x in validate_package(p, schema)))

    print("\npromotion adds, never forbids")
    p = copy.deepcopy(GOLDEN)
    p["meta"]["rung"] = "walk_on"
    check("walk_on with extra modules still validates",
          not validate_package(p, schema))

    p = {"meta": {"schema_version": "0", "rung": "walk_on"},
         "public": {"identity": "a carter | passing through"},
         "private": {}}
    check("bare walk_on (identity only) validates", not validate_package(p, schema))

    p["meta"]["rung"] = "recurring"
    check("bare card at recurring rung fails",
          any(x.startswith("rung:") for x in validate_package(p, schema)))

    print()
    if failures:
        print(f"{len(failures)} FAILED: " + "; ".join(failures))
        return 1
    print("all checks passed — the schema accepts souls and rejects fog.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
