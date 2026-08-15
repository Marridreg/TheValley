#!/usr/bin/env python3
"""Structural validation for every character card.

Checks the things that are easy to get subtly wrong when authoring cards by
hand or in bulk, and which would fail silently at runtime:

  - both halves parse, and the private half has a usable shape
  - the public half carries no routing metadata and no obvious secret markers
  - every learnable_from route is well-formed and yields truth or rumor
  - a route promising `rumor` has a rumor actually authored to hand over
  - documents' `reveals` keys resolve to sections that exist
  - nothing is an empty shell

Exit code is nonzero if anything fails, so it can gate a commit.

    python tools/validate_cards.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.state import StateManager  # noqa: E402

VALID_ROUTES = {"person", "document", "possession", "observation", "place"}
VALID_YIELDS = {"truth", "rumor"}

# Strings that should never appear in a public card. If authoring drifts and a
# secret lands on the public side, this is the cheapest place to catch it.
PUBLIC_SMELLS = ("learnable_from", "_schema", "gm_notes", "GM ONLY")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


def validate_card(npc: str, state: StateManager, r: Report) -> dict:
    d = state.chars_dir / npc
    stats = {"sections": 0, "routes": 0, "rumors": 0, "public_keys": 0}

    for half in ("public", "private"):
        p = d / f"{half}.json"
        if not p.exists():
            r.error(npc, f"missing {half}.json")
            return stats
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            r.error(npc, f"{half}.json does not parse — line {exc.lineno}: {exc.msg}")
            return stats

    public = json.loads((d / "public.json").read_text(encoding="utf-8"))
    stats["public_keys"] = len([k for k in public if not k.startswith("_")])

    if stats["public_keys"] < 6:
        r.warn(npc, f"public card is thin ({stats['public_keys']} keys)")
    for smell in PUBLIC_SMELLS:
        if smell in json.dumps(public, ensure_ascii=False):
            r.error(npc, f"public card contains '{smell}' — that belongs on the GM side")

    # A card the narrator can't voice is not usable.
    for expected in ("identity", "voice", "default_state"):
        if expected not in public:
            r.warn(npc, f"public card has no '{expected}'")
    if not public.get("speech_examples"):
        r.warn(npc, "public card has no speech_examples — the narrator has no voice to copy")

    sections = state._private_sections(npc)
    stats["sections"] = len(sections)
    if not sections:
        r.error(npc, "private card has no sections")
        return stats

    for name, section in sections.items():
        where = f"{npc}.{name}"
        if not isinstance(section, dict):
            # v1 flat form: a bare value is truth-only and legal.
            if not section:
                r.error(where, "empty section")
            continue

        if not section.get("truth"):
            r.error(where, "no 'truth' authored")
        if section.get("rumor"):
            stats["rumors"] += 1

        routes = section.get("learnable_from")
        if not routes:
            r.warn(where, "no learnable_from routes — unreachable except by GM fiat")
            continue

        for i, route in enumerate(routes):
            rw = f"{where}.learnable_from[{i}]"
            if not isinstance(route, dict):
                r.error(rw, "route is not an object")
                continue
            stats["routes"] += 1

            kind = route.get("route")
            if kind not in VALID_ROUTES:
                r.error(rw, f"route type {kind!r} not in {sorted(VALID_ROUTES)}")

            y = route.get("yields")
            if y not in VALID_YIELDS:
                r.error(rw, f"yields {y!r} not in {sorted(VALID_YIELDS)}")
            elif y == "rumor" and not section.get("rumor"):
                # The route promises a distorted version; without one authored,
                # get_narrator_card falls back to the truth and the route
                # silently becomes a first-hand disclosure.
                r.error(rw, "yields 'rumor' but the section has no rumor authored")

            if kind == "person" and not route.get("who"):
                r.error(rw, "person route with no 'who'")
            if kind in ("document", "possession", "observation", "place") and not route.get("what"):
                r.error(rw, f"{kind} route with no 'what'")

    return stats


def main() -> int:
    state = StateManager(ROOT / "data")
    r = Report()
    npcs = state.known_npcs()
    if not npcs:
        print("no character cards found under data/characters/")
        return 1

    print(f"{'character':16} {'pub keys':>8} {'sections':>8} {'routes':>7} {'rumors':>7}")
    print("-" * 52)
    totals = {"sections": 0, "routes": 0, "rumors": 0}
    for npc in npcs:
        s = validate_card(npc, state, r)
        for k in totals:
            totals[k] += s[k]
        print(f"{npc:16} {s['public_keys']:>8} {s['sections']:>8} {s['routes']:>7} {s['rumors']:>7}")
    print("-" * 52)
    print(f"{'TOTAL':16} {'':>8} {totals['sections']:>8} {totals['routes']:>7} {totals['rumors']:>7}")

    # Documents must point at sections that exist.
    print(f"\ndocuments: {len(state.documents)}")
    known = {npc: set(state._private_sections(npc)) for npc in npcs}
    for doc in state.documents:
        for key in doc.get("reveals") or []:
            npc, _, sec = key.partition(".")
            sec = sec.split("#")[0]
            if npc not in known:
                r.error(doc["id"], f"reveals '{key}' — no such character")
            elif sec not in known[npc]:
                r.error(doc["id"], f"reveals '{key}' — no such section on {npc}")
        if not doc.get("reveals"):
            r.warn(doc["id"], "document reveals nothing")

    if r.warnings:
        print(f"\n{len(r.warnings)} warning(s):")
        for w in r.warnings:
            print(f"  ~ {w}")
    if r.errors:
        print(f"\n{len(r.errors)} ERROR(S):")
        for e in r.errors:
            print(f"  ! {e}")
        return 1
    print("\nall cards structurally valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
