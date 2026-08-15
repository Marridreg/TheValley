#!/usr/bin/env python3
"""Check the SillyTavern export before importing it. No API key, no cost.

The exporter reads authored .txt documents by looking for headings. Edit a
heading and an entry stops being found — and the export still succeeds, just
missing a character. That already happened once: Leonardo's heading carries a
surname ("LEONARDO LUPU — The Father"), an exact-match lookup missed him, and
the export was quietly one villager short.

So this asserts the shape: everything expected is present, nothing is empty,
nothing collides, and the field set still matches what the installed
SillyTavern actually writes.

    python tools/validate_st_export.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXPORT = ROOT / "exports" / "sillytavern"
ST_DEFAULT = Path(r"C:\Users\lukas\Documents\sillytavern2\sillytavern\data\default-user\worlds")

EXPECT_CHARACTERS = ["Alcina", "Bela", "Cassandra", "Daniela", "Miranda",
                     "Heisenberg", "Donna", "Moreau", "Duke", "Elena"]
EXPECT_VILLAGERS = ["Leonardo", "Luiza", "Vasile", "Iulian", "Anton", "Roxana",
                    "Sebastian", "Eugen"]
EXPECT_LOCATIONS = 12


def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            failures.append(f"{label}{': ' + detail if detail else ''}")

    book_path = EXPORT / "The Valley.json"
    card_path = EXPORT / "The Valley - card.json"
    if not book_path.exists() or not card_path.exists():
        print("no export found — run tools/export_sillytavern.py first")
        return 1

    book = json.loads(book_path.read_text(encoding="utf-8"))
    card = json.loads(card_path.read_text(encoding="utf-8"))
    entries = book.get("entries") or {}
    names = [e.get("comment", "") for e in entries.values()]

    print("lorebook structure")
    check("entries present", bool(entries), "none")
    check("uids match their dict keys",
          sorted(int(k) for k in entries) == sorted(e["uid"] for e in entries.values()))
    check("no entry is empty", all(e["content"].strip() for e in entries.values()),
          str([e["comment"] for e in entries.values() if not e["content"].strip()]))
    check("every entry can fire (has keys, or is always-on)",
          all(e["key"] or e["constant"] for e in entries.values()),
          str([e["comment"] for e in entries.values() if not e["key"] and not e["constant"]]))
    check("no duplicate entry names", len(set(names)) == len(names))
    check("keys are plain latin text",
          all(all(ord(c) < 0x2100 for k in e["key"] for c in k) for e in entries.values()))

    print("\ncoverage")
    for who in EXPECT_CHARACTERS:
        check(f"character: {who}", any(who in n for n in names))
    for who in EXPECT_VILLAGERS:
        check(f"villager: {who}", any(who in n for n in names))
    check(f"{EXPECT_LOCATIONS} locations",
          sum(1 for n in names if n.startswith("LOC")) == EXPECT_LOCATIONS,
          str(sum(1 for n in names if n.startswith("LOC"))))
    check("always-on set is small", sum(1 for e in entries.values() if e["constant"]) <= 4,
          str([e["comment"] for e in entries.values() if e["constant"]]))

    print("\nheavy entries do not fire on ambient words")
    ambient = {"castle", "wine", "snow", "cold", "door", "window", "woman", "girl"}
    for e in entries.values():
        if len(e["content"]) > 6000:
            hits = ambient.intersection({k.lower() for k in e["key"]})
            check(f"{e['comment'][:28]} keyed on names only", not hits, str(hits))

    print("\ncard")
    data = card.get("data") or {}
    check("spec is chara_card_v3", card.get("spec") == "chara_card_v3")
    check("the world is the character", data.get("name") == "The Valley")
    for field in ("description", "personality", "scenario", "first_mes", "system_prompt"):
        check(f"{field} filled", bool((data.get(field) or "").strip()))
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    check("first_mes matches the engine's opening, for a fair A/B",
          data.get("first_mes") == (world.get("opening_text") or "").strip())
    check("legacy flat fields mirror data",
          card.get("description") == data.get("description"))

    print("\nno duplicated content between card and lorebook")
    for banded in ("[GEOGRAPHY]", "[FACTIONS]", "[VILLAGE CULTURE]"):
        in_card = banded in (data.get("description") or "")
        in_book = any(banded in e["content"] for e in entries.values())
        check(f"{banded} in exactly one place", in_card != in_book,
              f"card={in_card} book={in_book}")

    print("\nschema still matches the installed SillyTavern")
    live = sorted(ST_DEFAULT.glob("*.json")) if ST_DEFAULT.is_dir() else []
    if not live:
        print("  SKIP  no local SillyTavern worlds found to compare against")
    else:
        ref = json.loads(live[0].read_text(encoding="utf-8", errors="replace"))
        ref_entry = next(iter((ref.get("entries") or {}).values()), None)
        if not ref_entry:
            print("  SKIP  reference lorebook has no entries")
        else:
            mine = next(iter(entries.values()))
            missing = set(ref_entry) - set(mine)
            extra = set(mine) - set(ref_entry)
            check("no fields missing vs live", not missing, str(sorted(missing)))
            check("no unknown fields vs live", not extra, str(sorted(extra)))

    total = sum(len(e["content"]) for e in entries.values()) // 4
    always = sum(len(e["content"]) for e in entries.values() if e["constant"]) // 4
    print(f"\n  {len(entries)} entries, ~{total:,} est. tokens if all fired, "
          f"~{always:,} always-on")

    print()
    if failures:
        print(f"{len(failures)} FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("export is importable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
