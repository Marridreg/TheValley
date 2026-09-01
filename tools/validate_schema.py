#!/usr/bin/env python3
"""Validate character packages against data/character.schema.json.

Three layers, because JSON Schema alone can't hold all the law:

  1. structure  — jsonschema against character.schema.json
  2. rung       — which modules the character's ladder position requires
                  (promotion ADDS modules, never forbids extras)
  3. cross-field laws:
       - every public.stated_faces key has a private.actual_faces
         counterpart (a stated face with no actual behind it is noise;
         a mask must be a mask OF something)
       - every drives[].meter.low_state names an entry in states
         (a threshold that fires into a state nobody wrote is a dead end)

Existing cast cards predate the module system: a character directory with
no meta.json validates at walk_on requirements (structure only), so the
whole valley stays green today and characters opt into rungs by adding
meta.json. Runtime state is deliberately out of scope — saves are the
appraisal pass's territory, not authoring's.

    python tools/validate_schema.py            # all of data/characters/
    python tools/validate_schema.py moreau     # one character
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent

RUNG_REQUIREMENTS: dict[str, list[str]] = {
    "walk_on": [],
    "named": ["public.voice", "public.quirk"],
    "recurring": ["public.voice", "public.quirk",
                  "private.seed_beliefs|private.drives",
                  "private.states", "private.tells"],
    "principal": ["public.voice", "public.quirk",
                  "private.seed_beliefs|private.drives",
                  "private.states", "private.tells",
                  "private.self_concept", "private.defense_filters",
                  "private.escalation", "private.monologue"],
}


def _get(package: dict, dotted: str):
    cur = package
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if cur not in ({}, [], "") else None


def load_package(char_dir: Path) -> dict:
    package: dict = {"meta": {"schema_version": "0", "rung": "walk_on"}}
    meta_path = char_dir / "meta.json"
    if meta_path.exists():
        package["meta"] = json.loads(meta_path.read_text(encoding="utf-8"))
    package["public"] = json.loads((char_dir / "public.json").read_text(encoding="utf-8"))
    package["private"] = json.loads((char_dir / "private.json").read_text(encoding="utf-8"))
    return package


def validate_package(package: dict, schema: dict) -> list[str]:
    """Return a list of problems; empty means valid."""
    problems: list[str] = []

    validator = jsonschema.Draft202012Validator(schema)
    for err in validator.iter_errors(package):
        problems.append(f"structure: {'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}")

    rung = package.get("meta", {}).get("rung", "walk_on")
    for requirement in RUNG_REQUIREMENTS.get(rung, []):
        if not any(_get(package, alt) is not None for alt in requirement.split("|")):
            problems.append(f"rung: {rung} requires {requirement}")

    stated = (package.get("public") or {}).get("stated_faces") or {}
    actual = (package.get("private") or {}).get("actual_faces") or {}
    for subject in stated:
        if subject not in actual:
            problems.append(
                f"faces: stated_faces[{subject!r}] has no actual_faces counterpart "
                "— a mask must be a mask of something")

    state_names = {s.get("name") for s in (package.get("private") or {}).get("states") or []}
    for drive in (package.get("private") or {}).get("drives") or []:
        low = (drive.get("meter") or {}).get("low_state")
        if low and low not in state_names:
            problems.append(
                f"drives: {drive.get('name')!r} meter.low_state {low!r} names no entry in states")

    return problems


def main(argv: list[str]) -> int:
    schema = json.loads((ROOT / "data" / "character.schema.json").read_text(encoding="utf-8"))
    chars_dir = ROOT / "data" / "characters"
    targets = [chars_dir / argv[0]] if argv else sorted(
        d for d in chars_dir.iterdir() if (d / "public.json").exists())

    failed = 0
    for char_dir in targets:
        problems = validate_package(load_package(char_dir), schema)
        status = "PASS" if not problems else "FAIL"
        print(f"  {status}  {char_dir.name}")
        for p in problems:
            print(f"          - {p}")
        failed += bool(problems)

    print()
    if failed:
        print(f"{failed} character(s) failed validation.")
        return 1
    print("all characters validate — the schema holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
