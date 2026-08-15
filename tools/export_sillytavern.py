#!/usr/bin/env python3
"""Export the RE8 RPG source documents as a SillyTavern card + lorebook.

For A/B testing: same material, same opening, one model instead of two, and no
Wall. What SillyTavern does well on its own versus what The Valley does with the
GM/narrator split.

Layout follows "SILLYTAVERN ARCHITECTURE — FULL LAYOUT.txt" in the source folder,
which is the authored plan for this:

  system prompt   laws that never change (voice, turn structure, HUD, pillars)
  character card  THE WORLD, not a person. The valley is the character.
  lorebook        everything else, injected on keyword

Two deliberate departures from that document, both noted where they happen:
the feedback system is a triggered entry rather than always-on system prompt
text, and first_mes is the opening The Valley actually ships so the two engines
start from an identical first message.

    python tools/export_sillytavern.py            # write to exports/sillytavern/
    python tools/export_sillytavern.py --install  # also copy into SillyTavern
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent  # the "RE8 RPG" folder holding the authored .txt documents
OUT = ROOT / "exports" / "sillytavern"


# ── source reading ─────────────────────────────────────────────────────────

def read(name: str) -> str:
    path = SRC / name
    if not path.exists():
        raise SystemExit(f"missing source document: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def strip_rules(text: str) -> str:
    """Drop the ═══ divider lines. They are visual furniture, not content."""
    lines = [ln for ln in text.splitlines() if not re.fullmatch(r"[═─]{5,}\s*", ln)]
    return "\n".join(lines).strip()


def band(text: str, header: str) -> str:
    """Pull one '══ HEADER ══' band out of a document, up to the next one."""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("══ ") and header.upper() in ln.upper():
            start = i
            break
    if start is None:
        raise SystemExit(f"section not found: {header}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("══ "):
            end = j
            break
    title = re.sub(r"^══\s*|\s*═+$", "", lines[start]).strip()
    body = strip_rules("\n".join(lines[start + 1:end]))
    return f"[{title}]\n{body}"


def bands(text: str, *headers: str) -> str:
    return "\n\n".join(band(text, h) for h in headers)


def sub_band(text: str, header: str, stop: tuple[str, ...]) -> str:
    """Pull a bare-header subsection (e.g. 'TURN STRUCTURE:') from a layer."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.strip().upper().startswith(header.upper())), None)
    if start is None:
        raise SystemExit(f"subsection not found: {header}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j].strip().upper()
        if s.startswith("══ ") or any(s.startswith(x.upper()) for x in stop):
            end = j
            break
    return strip_rules("\n".join(lines[start:end]))


def caps_sections(text: str) -> dict[str, str]:
    """Split a document on ALL-CAPS heading lines (the location roster shape)."""
    out: dict[str, str] = {}
    current, buf = None, []
    for ln in text.splitlines():
        stripped = ln.strip()
        is_head = (
            stripped
            and stripped == stripped.upper()
            and re.fullmatch(r"[A-Z0-9 ,'’&()./—-]{6,}", stripped)
            and not re.fullmatch(r"[═─]{5,}", stripped)
        )
        if is_head:
            if current:
                out[current] = strip_rules("\n".join(buf))
            current, buf = stripped, []
        elif current:
            buf.append(ln)
    if current:
        out[current] = strip_rules("\n".join(buf))
    return out


def dash_sections(text: str) -> dict[str, str]:
    """Split on 'NAME — Title' headings (the village sketch shape)."""
    out: dict[str, str] = {}
    current, buf = None, []
    for ln in text.splitlines():
        m = re.match(r"^([A-Z][A-Z'’ -]{2,})\s+[—-]\s+(.+)$", ln.strip())
        if m:
            if current:
                out[current] = strip_rules("\n".join(buf))
            current, buf = m.group(1).strip(), [ln.strip()]
        elif current:
            buf.append(ln)
    if current:
        out[current] = strip_rules("\n".join(buf))
    return out


def nice(head: str) -> str:
    """Title-case without str.title()'s habit of capitalising after apostrophes."""
    return re.sub(r"[A-Za-z']+", lambda m: m.group(0).capitalize(), head.lower())


def find_block(text: str, needle: str) -> str:
    """Take from the line containing `needle` to the next band header."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if needle.upper() in ln.upper()), None)
    if start is None:
        raise SystemExit(f"block not found: {needle}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("══ "):
            end = j
            break
    return strip_rules("\n".join(lines[start:end]))


# ── lorebook entry construction ────────────────────────────────────────────

# Field set copied from a live lorebook in this SillyTavern install, so imports
# do not silently fall back to defaults on a field the app expects.
def entry(uid: int, name: str, keys: list[str], content: str, *,
          order: int, position: int = 1, constant: bool = False,
          depth: int = 4, comment_extra: str = "") -> dict:
    return {
        "uid": uid,
        "key": keys,
        "keysecondary": [],
        "comment": f"{name}{comment_extra}",
        "content": content,
        "constant": constant,
        "vectorized": False,
        "selective": True,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": order,
        "position": position,
        "disable": False,
        "ignoreBudget": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "matchPersonaDescription": False,
        "matchCharacterDescription": False,
        "matchCharacterPersonality": False,
        "matchCharacterDepthPrompt": False,
        "matchScenario": False,
        "matchCreatorNotes": False,
        "delayUntilRecursion": False,
        "probability": 100,
        "useProbability": True,
        "depth": depth,
        "outletName": "",
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "matchWholeWords": None,
        "useGroupScoring": False,
        "automationId": "",
        "role": 0,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "triggers": [],
        "displayIndex": uid,
        "extensions": {},
    }


# Trigger keywords are the ones the architecture document specifies. Ambient
# words are deliberately absent from the heavy character entries: "castle" must
# not drag in four thousand tokens of Alcina every time a wall is mentioned.
CHARACTERS = [
    ("Alcina Dimitrescu", "ALCINA DIMITRESCU.txt", ["Alcina", "Lady Dimitrescu", "Mistress"]),
    ("Bela Dimitrescu", "Bela Dimitrescu.txt", ["Bela", "eldest daughter", "castellan"]),
    ("Cassandra Dimitrescu", "CASSANDRA DIMITRESCU.txt", ["Cassandra", "middle daughter", "huntress"]),
    ("Daniela Dimitrescu", "DANIELA DIMITRESCU.txt", ["Daniela", "youngest daughter", "little one"]),
    ("Mother Miranda", "MOTHER MIRANDA.txt", ["Miranda", "Mother Miranda", "the Hag", "old woman"]),
    ("Karl Heisenberg", "KARL HEISENBERG.txt", ["Heisenberg", "Karl"]),
    ("Donna Beneviento & Angie", "DONNA BENEVIENTO & ANGIE.txt", ["Donna", "Beneviento", "Angie", "doll"]),
    ("Salvatore Moreau", "SALVATORE MOREAU.txt", ["Moreau", "Salvatore"]),
    ("The Duke", "THE DUKE.txt", ["Duke", "merchant", "buying", "selling"]),
    ("Elena Lupu", "ELENA LUPU.txt", ["Elena", "Lupu"]),
]

LOCATION_KEYS = {
    "THE MAIN VILLAGE": ["village", "houses", "church", "well", "village center"],
    "THE FALLOW PLOT": ["Fallow Plot", "outskirts", "fence"],
    "THE STRONGHOLD": ["Stronghold", "gate", "barricade"],
    "CASTLE DIMITRESCU": ["castle", "east wing", "wine cellar", "tower", "courtyard"],
    "HOUSE BENEVIENTO": ["villa", "Beneviento house", "fog", "mist", "workshop"],
    "MOREAU'S RESERVOIR": ["reservoir", "lake", "frozen water", "shrine"],
    "HEISENBERG'S FACTORY": ["factory", "machinery", "Soldats", "smokestack"],
    "OTTO'S MILL": ["mill", "Otto", "windmill"],
    "THE FORBIDDEN WOODS": ["woods", "forest", "Forbidden Woods", "treeline"],
    "THE CEREMONY SITE": ["ceremony site", "altar", "ceremony ground"],
    "THE CAVE CHURCH": ["cave", "cave church", "underground", "Megamycete"],
    "MIRANDA'S LABORATORY": ["laboratory", "lab", "specimens"],
}

VILLAGER_KEYS = {
    "LEONARDO": ["Leonardo", "Elena's father"],
    "LUIZA": ["Luiza", "safe house"],
    "VASILE": ["Vasile", "missing husband"],
    "IULIAN": ["Iulian", "sentinel", "guard"],
    "ANTON": ["Anton", "drunk"],
    "ROXANA": ["Roxana", "widow"],
    "SEBASTIAN": ["Sebastian", "crippled"],
    "EUGEN": ["Eugen", "errand"],
}


def build_lorebook() -> tuple[dict, list[tuple[str, int]]]:
    entries: dict[str, dict] = {}
    sizes: list[tuple[str, int]] = []
    uid = 0

    def add(name, keys, content, **kw):
        nonlocal uid
        if not content.strip():
            return
        entries[str(uid)] = entry(uid, name, keys, content, **kw)
        sizes.append((name, len(content) // 4))
        uid += 1

    harness = read("GAME HARNESS-ZORK MEETS RE8.txt")
    addendum = read("ADDENDUM TO GAME HARNESS-HUD & FEEDBACK SYSTEM.txt")
    world = read("OPENING STATE.txt")
    daniela = read("DANIELA DIMITRESCU.txt")

    # ── always active ──
    # State templates and the sister block, per the architecture document.
    # These are the heaviest always-on cost in the whole export; disable them
    # in SillyTavern if context gets tight and let the HUD carry state instead.
    add("STATE — PC template (always on)", [], band(harness, "LAYER 1"),
        order=100, position=4, constant=True, depth=4)
    add("STATE — world template (always on)", [], band(harness, "LAYER 3"),
        order=100, position=4, constant=True, depth=4)
    add("Sister dynamics (always on)", [], find_block(daniela, "SISTER DYNAMICS"),
        order=80, position=1, constant=True)

    # ── characters ──
    for name, filename, keys in CHARACTERS:
        add(name, keys, strip_rules(read(filename)), order=90, position=1)

    # ── locations ──
    roster = caps_sections(read("LOCATION ROSTER.txt"))
    for head, keys in LOCATION_KEYS.items():
        body = roster.get(head)
        if body:
            add(f"LOC — {nice(head)}", keys, f"[{head}]\n{body}", order=80, position=1)

    # ── village ──
    village_doc = read("THE VILLAGE — POPULATION & NAMED NPCs.txt")
    sketches = dash_sections(village_doc)
    for head, keys in VILLAGER_KEYS.items():
        # Headings carry surnames ("LEONARDO LUPU — The Father"), so match on
        # the first word rather than the whole line.
        body = next((v for k, v in sketches.items() if k.split()[0] == head), None)
        if body:
            add(f"NPC — {nice(head)}", keys, body, order=30, position=1)
    add("Village — general population", ["villagers", "crowd", "locals", "gathering"],
        band(village_doc, "GENERAL POPULATION"), order=40, position=1)
    add("Village — behavioural rules", ["villager", "villagers", "village"],
        band(village_doc, "VILLAGE DYNAMICS"), order=40, position=1)

    # ── systems, triggered ──
    stop = ("TURN STRUCTURE", "DEATH & FAILURE", "WORLD PROGRESSION", "TIME & REST",
            "STEALTH", "COMPANION SYSTEM", "DISCOVERY & SECRETS", "GENERATION TEMPLATE")
    add("SYS — combat & encounters",
        ["combat", "fight", "attack", "weapon", "shoot", "lycan"],
        bands(harness, "LAYER 2", "LAYER 6"), order=60, position=0)
    add("SYS — items & loot", ["item", "loot", "search", "container", "pick up"],
        band(harness, "LAYER 4"), order=60, position=0)
    add("SYS — stealth & attention", ["sneak", "stealth", "hide", "quiet", "unseen"],
        sub_band(harness, "STEALTH", stop), order=60, position=0)
    add("SYS — rest & time", ["rest", "sleep", "camp", "recover", "wait"],
        sub_band(harness, "TIME & REST", stop), order=60, position=0)
    add("SYS — companions", ["companion", "follow me", "together", "escort"],
        sub_band(harness, "COMPANION SYSTEM", stop), order=60, position=0)
    add("SYS — discovery & secrets", ["secret", "discover", "learn", "ask about"],
        sub_band(harness, "DISCOVERY & SECRETS", stop), order=60, position=0)
    add("SYS — world moves without you", ["meanwhile", "elsewhere", "days pass"],
        sub_band(harness, "WORLD PROGRESSION", stop), order=50, position=0)
    add("SYS — game over", ["game over", "died", "killed", "bleeding out"],
        band(harness, "LAYER 7"), order=60, position=0)
    add("SYS — the Mold", ["mold", "spores", "whispers", "exposure", "infection"],
        band(world, "THE MOLD"), order=60, position=0)
    # Departure from the document: the feedback system triggers on its own tags
    # instead of sitting in the system prompt every message. It is a hundred
    # lines that only matter when a tag is actually used.
    add("SYS — feedback & correction tags", ["[FEEDBACK]", "[CORRECTION]", "feedback", "correction"],
        band(addendum, "FEEDBACK SYSTEM"), order=70, position=0)

    return {"entries": entries, "originalData": None}, sizes


# ── character card ─────────────────────────────────────────────────────────

PERSONALITY = (
    "You are the valley. You are patient. You present your forces without "
    "judgment. You enforce your rules without mercy. You reward the attentive "
    "and punish the careless. You are beautiful and you are dying and you do "
    "not care if the player saves you."
)

CARDINAL = """[CARDINAL RULES]
- No character is labelled ally or enemy in narration. Present forces with
  motivations and let the player decide what they are to him.
- Describe, don't direct. Never tell the player what he feels or decides.
- Reward specificity. A precise action gets a precise result.
- The world doesn't wait. Time passes and factions act whether he does or not.
- The world remembers. Nothing resets."""


def build_card(lorebook_note: str) -> dict:
    world = read("OPENING STATE.txt")
    harness = read("GAME HARNESS-ZORK MEETS RE8.txt")
    addendum = read("ADDENDUM TO GAME HARNESS-HUD & FEEDBACK SYSTEM.txt")

    # The world card minus its opening-state band; that band becomes `scenario`.
    description = bands(world, "WORLD IDENTITY", "TIMELINE ANCHOR", "GEOGRAPHY",
                        "FACTIONS", "VILLAGE CULTURE", "NARRATIVE RULES")
    scenario = band(world, "OPENING STATE")

    stop = ("TURN STRUCTURE", "DEATH & FAILURE", "WORLD PROGRESSION", "TIME & REST",
            "STEALTH", "COMPANION SYSTEM", "DISCOVERY & SECRETS", "GENERATION TEMPLATE")

    # Laws only: things that are true on every single turn regardless of scene.
    system_prompt = "\n\n".join([
        "You are the narrator and game engine for a gothic horror-romance survival "
        "sandbox set in a remote Eastern European mountain village in 1958. You "
        "manage all NPCs, environments, encounters, and world state.",
        strip_rules(read("NARRATOR VOICE.txt")),
        prose_convention(),
        strip_rules(read("ZORK DESIGN PILLARS.txt")),
        sub_band(harness, "TURN STRUCTURE", stop),
        sub_band(harness, "DEATH & FAILURE", stop),
        strip_rules(read("ENVIRONMENTAL MECHANICS.txt")),
        strip_rules(read("INVENTORY LIMITS.txt")),
        strip_rules(read("SPECIFICITY REWARD.txt")),
        strip_rules(read("WORLD PERSISTENCE RULES.txt")),
        strip_rules(read("DEATH PHILOSOPHY.txt")),
        band(addendum, "MINI HUD"),
        CARDINAL,
    ])

    # High-recency reminders. The two things that decay first in a long session
    # are the HUD habit and the prose voice.
    post_history = (
        "[REMINDERS]\n"
        "Append the Mini HUD at the end of every response.\n"
        "Narration never says \"you\" or \"your\", never names the protagonist, and "
        "never describes him from outside. Dialogue is exempt — characters speak "
        "to him normally.\n"
        "Do not decide what he feels, thinks, or does next."
    )

    first_mes = opening_text()

    data = {
        "name": "The Valley",
        "description": description,
        "personality": PERSONALITY,
        "scenario": scenario,
        "first_mes": first_mes,
        "mes_example": "",
        "creator_notes": lorebook_note,
        "system_prompt": system_prompt,
        "post_history_instructions": post_history,
        "alternate_greetings": [],
        "tags": ["text adventure", "gothic horror", "re8", "survival", "the valley"],
        "creator": "Marridreg",
        "character_version": "1.0",
        "extensions": {},
    }
    # V3 cards carry the legacy flat fields too; SillyTavern reads `data` but
    # other tools still look at the top level.
    return {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": data,
        "name": data["name"],
        "description": data["description"],
        "personality": data["personality"],
        "scenario": data["scenario"],
        "first_mes": data["first_mes"],
        "mes_example": "",
        "creator_notes": data["creator_notes"],
        "tags": data["tags"],
        "talkativeness": "0.5",
        "fav": False,
    }


def prose_convention() -> str:
    """The engine's authored voice rule, so both sides are told the same thing."""
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    rule = world.get("prose_convention")
    if isinstance(rule, dict):
        rule = "\n".join(f"- {v}" for v in rule.values())
    return "[PROSE CONVENTION]\n" + (rule or "").strip()


def opening_text() -> str:
    """The opening The Valley ships, so the A/B starts from the same words."""
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    return (world.get("opening_text") or "").strip()


# ── main ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true",
                    help="also copy into the SillyTavern data directory")
    ap.add_argument("--st", default=r"C:\Users\lukas\Documents\sillytavern2\sillytavern",
                    help="SillyTavern root")
    ap.add_argument("--user", default="default-user")
    args = ap.parse_args()

    lorebook, sizes = build_lorebook()
    total = sum(t for _, t in sizes)
    always = sum(t for n, t in sizes if "always on" in n)

    note = (
        "Exported from The Valley (tools/export_sillytavern.py). Same source "
        "documents the engine uses.\n\n"
        f"Companion lorebook: 'The Valley' ({len(sizes)} entries, ~{total:,} est. "
        f"tokens if everything fired at once; ~{always:,} of that is always-on).\n"
        "Import it under World Info and attach it to this card.\n\n"
        "Recommended settings, from the architecture document:\n"
        "  scan depth 3 (characters drop out of scope below 2)\n"
        "  set a max-lorebook-token cap and let insertion order do the trimming\n"
        "  the two STATE templates are the heaviest always-on cost — disable them\n"
        "  first if context gets tight\n\n"
        "The heavy character entries trigger on names only, never on ambient words "
        "like 'castle' or 'wine'."
    )
    card = build_card(note)

    OUT.mkdir(parents=True, exist_ok=True)
    book_path = OUT / "The Valley.json"
    card_path = OUT / "The Valley - card.json"
    book_path.write_text(json.dumps(lorebook, indent=2, ensure_ascii=False), encoding="utf-8")
    card_path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"lorebook  {book_path}")
    print(f"          {len(sizes)} entries, ~{total:,} est. tokens total, "
          f"~{always:,} always-on")
    print(f"card      {card_path}")
    for label, field in (("system_prompt", "system_prompt"), ("description", "description"),
                         ("scenario", "scenario"), ("first_mes", "first_mes")):
        print(f"          {label:22} ~{len(card['data'][field]) // 4:,} est. tokens")

    print("\nheaviest lorebook entries:")
    for name, tok in sorted(sizes, key=lambda x: -x[1])[:8]:
        print(f"          {tok:>6,}  {name}")

    if args.install:
        # The lorebook only. SillyTavern lists characters by enumerating PNGs in
        # characters/ and reading an embedded payload out of them, so a .json
        # dropped in that folder is never shown — the card has to go in through
        # the app's own import, which writes the PNG and lets you pick the
        # portrait.
        st = Path(args.st) / "data" / args.user
        worlds = st / "worlds"
        if not worlds.is_dir():
            print(f"\n! not a SillyTavern worlds dir: {worlds}")
            return 1
        dest = worlds / "The Valley.json"
        if dest.exists():
            backup = dest.with_suffix(".json.bak")
            backup.write_bytes(dest.read_bytes())
            print(f"\n  existing {dest.name} backed up to {backup.name}")
        dest.write_bytes(book_path.read_bytes())
        print(f"  lorebook installed -> {dest}")
        print(f"\n  card: import '{card_path.name}' via")
        print("        SillyTavern -> Characters -> Import Character")
    else:
        print("\n--install drops the lorebook into SillyTavern's worlds folder.")
        print("The card goes in via Characters -> Import Character.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
