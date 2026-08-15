#!/usr/bin/env python3
"""Move character cards between The Valley and SillyTavern.

STATUS: groundwork, not yet exercised. Written alongside the world-card export
and left here deliberately, but no run has been made against a real card yet
and there is no test for it. Try it on a copy before trusting it.

    python tools/valley_card.py export moreau
    python tools/valley_card.py export moreau --private --avatar art.png
    python tools/valley_card.py import "path/to/Some Character.png"
    python tools/valley_card.py list

WHAT CROSSES, AND WHAT DOES NOT

Exporting is lossy in one direction on purpose. A Valley character is split in
two: public.json is what an encounter shows you, private.json is what the GM
knows and releases through the Wall. A SillyTavern card has no Wall — whatever
is in it is in the model's context. So export writes the PUBLIC half only
unless you pass --private, and says which it did in creator_notes.

Importing is lossy the other way. A SillyTavern card is prose written for one
model to read; the engine wants fielded data and discovery routes. So an import
lands as a structurally valid character with the prose parked in the closest
matching fields and a _needs_review flag on it. It will play. It will not be as
good as a hand-authored card until someone reads it through.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.stcard import CardError, read_any, write_png  # noqa: E402

CHARS = ROOT / "data" / "characters"
OUT = ROOT / "exports" / "cards"


# ── Valley → SillyTavern ───────────────────────────────────────────────────

def load_valley(slug: str) -> tuple[dict, dict]:
    folder = CHARS / slug
    pub_path, priv_path = folder / "public.json", folder / "private.json"
    if not pub_path.exists():
        raise SystemExit(f"no character '{slug}' — {pub_path} does not exist")
    public = json.loads(pub_path.read_text(encoding="utf-8"))
    private = (json.loads(priv_path.read_text(encoding="utf-8"))
               if priv_path.exists() else {})
    return public, private


def display_name(public: dict, slug: str) -> str:
    """First clause of `identity` is the name: 'Salvatore Moreau | age ...'."""
    identity = str(public.get("identity") or "")
    head = identity.split("|")[0].strip()
    return head or slug.replace("_", " ").title()


def paragraphs(*parts: object) -> str:
    out = []
    for part in parts:
        if not part:
            continue
        if isinstance(part, dict):
            part = "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in part.items() if v)
        elif isinstance(part, (list, tuple)):
            part = "\n".join(f"- {v}" for v in part if v)
        text = str(part).strip()
        if text:
            out.append(text)
    return "\n\n".join(out)


def labelled(label: str, value: object) -> str:
    body = paragraphs(value)
    return f"[{label}]\n{body}" if body else ""


def to_st_card(slug: str, public: dict, private: dict, include_private: bool) -> dict:
    name = display_name(public, slug)

    description = paragraphs(
        labelled("IDENTITY", public.get("identity")),
        labelled("APPEARANCE", public.get("look")),
        labelled("DRESS", public.get("wears")),
        labelled("SCENT", public.get("scent")),
        labelled("CARRIES", public.get("props")),
        labelled("AUTHORITY", public.get("authority")),
        labelled("HOW HE OR SHE ADDRESSES OTHERS", public.get("addresses_others")),
        labelled("LIKES", public.get("likes")),
        labelled("DISLIKES", public.get("dislikes")),
        labelled("TELLS", public.get("tells")),
        labelled("LANGUAGES", public.get("languages")),
    )

    personality = paragraphs(
        labelled("VOICE", public.get("voice")),
        labelled("DEFAULT STATE", public.get("default_state")),
        labelled("STATES", public.get("states")),
    )

    # ST reads examples as blocks separated by <START>, with {{char}} speaking.
    examples = public.get("speech_examples") or []
    if isinstance(examples, dict):
        examples = list(examples.values())
    mes_example = "\n".join(
        f"<START>\n{{{{char}}}}: {str(line).strip()}" for line in examples if line
    )

    # never_says is a hard voice guardrail, so it goes where recency is highest.
    post_history = labelled("NEVER SAYS", public.get("never_says"))

    book = None
    withheld = 0
    if include_private:
        book = private_to_book(name, private)
    else:
        withheld = len((private.get("sections") or {}))

    notes = [
        f"Exported from The Valley (tools/valley_card.py) — data/characters/{slug}/.",
    ]
    if include_private:
        entries = len(((book or {}).get("entries") or []))
        notes.append(
            f"INCLUDES THE PRIVATE HALF: {entries} GM-only sections are embedded as a "
            "character book. There is no Wall here — a single model can read all of "
            "it, and will leak it when the conversation leans that way. That is the "
            "point if you are A/B testing; it is a problem if you are not."
        )
    elif withheld:
        notes.append(
            f"Public half only. {withheld} private sections were NOT exported — they "
            "are what the engine releases through discovery routes. Re-run with "
            "--private if you want the whole character in one context."
        )
    if public.get("carry_over"):
        notes.append(f"Carry-over: {public['carry_over']}")

    card = {
        "name": name,
        "description": description,
        "personality": personality,
        "scenario": "",
        "first_mes": "",
        "mes_example": mes_example,
        "creator_notes": "\n\n".join(notes),
        "system_prompt": "",
        "post_history_instructions": post_history,
        "alternate_greetings": [],
        "tags": ["the valley", "re8", slug],
        "creator": "Marridreg",
        "character_version": "1.0",
        "extensions": {"valley": {"slug": slug, "private_included": include_private}},
    }
    if book:
        card["character_book"] = book
    return card


def private_to_book(name: str, private: dict) -> dict:
    """Turn GM-only sections into an embedded character book.

    Each section becomes an entry keyed on the character's name plus the section
    key, which means it only fires when that subject actually comes up rather
    than dumping every secret into every message.
    """
    entries = []
    for i, (key, section) in enumerate((private.get("sections") or {}).items()):
        if not isinstance(section, dict):
            continue
        truth = section.get("truth") or section.get("rumor")
        if not truth:
            continue
        words = [w for w in re.split(r"[^a-zA-Z]+", key) if len(w) > 3]
        entries.append({
            "keys": [name.split()[0]] + words,
            "content": f"[{key}]\n{truth}",
            "extensions": {},
            "enabled": True,
            "insertion_order": 50,
            "case_sensitive": False,
            "name": key,
            "priority": 50,
            "id": i,
            "comment": "GM-only in The Valley",
            "selective": False,
            "secondary_keys": [],
            "constant": False,
            "position": "before_char",
        })
    return {
        "name": f"{name} — private",
        "description": "Sections the engine keeps behind the Wall.",
        "scan_depth": 3,
        "token_budget": 1200,
        "recursive_scanning": False,
        "extensions": {},
        "entries": entries,
    }


# ── SillyTavern → Valley ───────────────────────────────────────────────────

def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "imported"


def to_valley(card: dict) -> tuple[dict, dict]:
    """Best-effort split of a SillyTavern card into the engine's two halves.

    No guessing dressed up as authority: the prose goes into the closest field,
    the rest is left empty, and _needs_review says so out loud. A silently
    half-filled card would play badly for reasons nobody could see.
    """
    name = card["name"]
    description = card.get("description") or ""
    personality = card.get("personality") or ""

    examples = []
    for block in re.split(r"<START>", card.get("mes_example") or ""):
        for line in block.splitlines():
            line = re.sub(r"^\s*\{\{char\}\}\s*:\s*", "", line).strip()
            if line and "{{user}}" not in line:
                examples.append(line)

    public = {
        "_note": (
            "Imported from a SillyTavern card. The prose below came in as one block "
            "and was parked in the closest matching fields — read it through and "
            "split it properly before trusting it."
        ),
        "_needs_review": True,
        "_imported_from": card.get("spec", "unknown"),
        "identity": f"{name} | imported | " + first_sentence(description),
        "addresses_others": {},
        "look": description,
        "wears": "",
        "scent": "",
        "props": "",
        "languages": "",
        "voice": personality or "not specified in the source card",
        "speech_examples": examples[:8],
        "default_state": first_sentence(personality) or "neutral",
        "states": {},
        "tells": "",
        "likes": "",
        "dislikes": "",
        "authority": "",
        "never_says": (card.get("post_history_instructions") or ""),
        "carry_over": "",
    }

    sections: dict[str, dict] = {}
    book = card.get("character_book") or {}
    for i, e in enumerate(book.get("entries") or []):
        content = (e.get("content") or "").strip()
        if not content:
            continue
        key = slugify(e.get("name") or e.get("comment") or f"section_{i}")
        # Every private section needs at least one route in, or it is content
        # the game can never surface. Observation is the honest default for
        # imported material: no author decided who else knows this.
        sections[key] = {
            "truth": content,
            "learnable_from": [{"type": "observation", "source": "in scene", "variant": "truth"}],
        }

    private = {
        "_note": f"Imported from a SillyTavern card ({name}). Routes are placeholders.",
        "_schema": "sections{key:{truth, rumor?, learnable_from[]}}",
        "sections": sections,
    }
    return public, private


def first_sentence(text: str) -> str:
    flat = " ".join((text or "").split())
    m = re.match(r"(.{0,180}?[.!?])(\s|$)", flat)
    return (m.group(1) if m else flat[:180]).strip()


# ── commands ───────────────────────────────────────────────────────────────

def cmd_list(args) -> int:
    slugs = sorted(p.name for p in CHARS.iterdir()
                   if p.is_dir() and (p / "public.json").exists())
    print(f"{len(slugs)} characters in data/characters/:\n")
    for slug in slugs:
        public, private = load_valley(slug)
        n = len(private.get("sections") or {})
        print(f"  {slug:14} {display_name(public, slug):28} {n:>3} private sections")
    return 0


def cmd_export(args) -> int:
    slugs = args.who or sorted(p.name for p in CHARS.iterdir()
                               if p.is_dir() and (p / "public.json").exists())
    OUT.mkdir(parents=True, exist_ok=True)
    for slug in slugs:
        public, private = load_valley(slug)
        card = to_st_card(slug, public, private, args.private)
        stem = card["name"].replace("/", "-")
        json_path = OUT / f"{stem}.json"
        json_path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")

        avatar = Path(args.avatar) if args.avatar else default_portrait(slug)
        png_path = write_png(card, OUT / f"{stem}.png", avatar=avatar)

        tokens = sum(len(str(card.get(k) or "")) for k in
                     ("description", "personality", "mes_example")) // 4
        art = avatar.name if avatar and avatar.exists() else "no portrait found"
        print(f"  {slug:14} -> {png_path.name:34} ~{tokens:>5,} est. tokens   [{art}]")
        if args.private:
            print(f"                 {'':34} + private half embedded")
    print(f"\nwritten to {OUT}")
    print("Import into SillyTavern with Characters -> Import Character.")
    return 0


def default_portrait(slug: str) -> Path | None:
    folder = CHARS / slug / "portraits"
    if not folder.is_dir():
        return None
    for name in ("default.png", "neutral.png"):
        if (folder / name).exists():
            return folder / name
    pics = sorted(folder.glob("*.png")) + sorted(folder.glob("*.jpg"))
    return pics[0] if pics else None


def cmd_import(args) -> int:
    try:
        card = read_any(Path(args.path))
    except CardError as exc:
        print(f"cannot read that card: {exc}")
        return 1

    slug = args.name or slugify(card["name"])
    folder = CHARS / slug
    if folder.exists() and not args.force:
        print(f"data/characters/{slug}/ already exists — pass --force to overwrite")
        return 1

    public, private = to_valley(card)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "public.json").write_text(
        json.dumps(public, indent=2, ensure_ascii=False), encoding="utf-8")
    (folder / "private.json").write_text(
        json.dumps(private, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"imported '{card['name']}' -> data/characters/{slug}/")
    print(f"  spec             {card.get('spec')}")
    print(f"  private sections {len(private['sections'])} (from its character book)")
    print(f"  speech examples  {len(public['speech_examples'])}")
    print("\n  _needs_review is set on the public half. The prose arrived as one")
    print("  block; look/voice/tells were filled best-effort and the rest is empty.")
    print("\nRun: python tools/validate_cards.py")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="show the engine's characters")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("export", help="Valley character -> SillyTavern card")
    p.add_argument("who", nargs="*", help="slugs; omit for all")
    p.add_argument("--private", action="store_true",
                   help="also embed the GM-only half (no Wall on the other side)")
    p.add_argument("--avatar", help="portrait image to use for every card written")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("import", help="SillyTavern card (.png/.json) -> Valley character")
    p.add_argument("path")
    p.add_argument("--name", help="slug to write to (default: from the card name)")
    p.add_argument("--force", action="store_true", help="overwrite an existing character")
    p.set_defaults(fn=cmd_import)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
