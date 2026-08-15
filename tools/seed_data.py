#!/usr/bin/env python3
"""Write the starting data files.

Run once: python tools/seed_data.py

Deliberately minimal. These are scaffolds with the right SHAPE — enough for the
engine to run end to end and for you to see the Wall working. The real content
lives in the design docs next door; converting those character .txt files into
public/private pairs is the actual authoring work, and the split is the whole
game: public is what you'd know after five minutes in a room with them,
private is everything you have to earn.

Existing files are never overwritten, so re-running this is safe.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def write(rel: str, payload: dict) -> None:
    path = DATA / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"  = {rel} (exists, left alone)")
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  + {rel}")


# ── narrator-visible world ────────────────────────────────────────────────

WORLD = {
    "setting": "A remote valley in the Eastern European mountains, early 1980s. "
               "One village, snowed in, ringed by forest. A castle on the north "
               "ridge, a reservoir west, a derelict factory east, a house in the "
               "woods south. The valley has one road out and it is not passable.",
    "tone": "Gothic horror. Cold, wet, and physical. The supernatural is "
            "mundane here — the villagers have theology for it, not disbelief.",
    "language": "Villagers speak Romanian among themselves and broken English to "
                "outsiders. The nobility speak both fluently.",
    "the_village": {
        "population": "Forty-odd, down from three hundred. Everyone is armed and "
                      "nobody goes out after dark.",
        "faith": "They venerate Mother Miranda. Not metaphorically — she is the "
                 "church, and the church is the only building maintained.",
        "economy": "Barter, plus lei for the Duke, who is the only merchant and "
                   "arrives when he chooses.",
    },
    "locations": {
        "village_center": "Well, church, a dozen houses. The gate east is barred.",
        "castle": "Castle Dimitrescu on the north ridge. Lit at night.",
        "reservoir": "West. A drowned chapel stands in the shallows.",
        "factory": "East, past the fence. Machinery still runs some nights.",
        "house": "South, in the woods. Nobody talks about it.",
        "cave_church": "Rumoured. Below.",
    },
    "the_mold": "Something in the soil and water. Long exposure makes people "
                "compliant, then something else. Everyone here has some.",
    "opening_text": (
        "Cold woke you before the pain did.\n\n"
        "Snow, packed against one cheek. Grey sky through black branches. Your "
        "coat was army surplus and soaked through, and there was a weight on "
        "your hip that turned out to be a holster, empty. You could not "
        "remember lying down here. You could not remember standing up "
        "anywhere else, either.\n\n"
        "Somewhere below, downhill, a cart wheel was complaining about a rut. "
        "The sound stopped. Then a voice, unhurried, pitched to carry:\n\n"
        "\"Ahh — a new face! And still attached to the body. Come down, "
        "friend, before the cold makes the introduction for me.\""
    ),
}

# ── PC ────────────────────────────────────────────────────────────────────

PC = {
    "name": None,
    "known_as": "the soldier",
    "note": "name is null on purpose — it is a quest reward, held in the vault",
    "vitals": {
        "health": {"current": 0.85, "max": 1.0},
        "stamina": {"current": 0.7, "max": 1.0},
        "mold_exposure": {"level": 0.04},
    },
    "stats": {
        "strength": 0.6,
        "speed": 0.55,
        "perception": 0.7,
        "willpower": 0.65,
        "charisma": 0.45,
        "knowledge": 0.5,
    },
    "location": {"current": "village_outskirts", "sub_location": "the treeline"},
    "equipped": {"weapon": "nothing", "armor": "wet army coat"},
    "inventory": [
        {"name": "empty holster", "note": "the weapon is gone; the wear pattern is not"},
        {"name": "field dressing", "uses": 1},
    ],
    "lei": 0,
    "fragments_recovered": [],
    "conditions": ["cold", "amnesia"],
}

# ── live world state ──────────────────────────────────────────────────────

WORLD_STATE = {
    "calendar": {
        "days_to_ceremony": 18,
        "time_of_day": "late morning",
        "weather": "heavy snow",
    },
    "threat": {"lycan": 0.2, "moroaica": 0.0},
    "attention": {"dimitrescu": 0.0, "village": 0.05, "miranda": 0.0},
    "factions": {
        "village": {"regard": 0.0},
        "dimitrescu": {"regard": 0.0},
        "duke": {"regard": 0.1},
    },
    "flags": {},
    "_scene_npcs": [],
}

# ── GM ONLY: the vault ────────────────────────────────────────────────────
# Everything here is invisible to the narrator. Fill it in — the game is only
# as good as what is hidden in this file.

VAULT = {
    "_warning": "GM ONLY. If any of this reaches the narrator, the Wall is down.",
    "pc_truth": {
        "true_name": "TODO — decide now, reveal around day 8",
        "service": "TODO",
        "why_he_is_here": "TODO — the load-bearing secret",
        "miranda_connection": "TODO — decide whether she recognises him, and lock it",
    },
    "revelation_schedule": {
        "name": "not before day 8",
        "why_he_is_here": "not before day 12",
        "miranda_connection": "not before day 15, or the final act",
    },
    "npc_secrets": {
        "moreau": {
            "loyalty": "absolute, and unreciprocated. He knows it and cannot stop.",
            "capability": "he can enter the water and change. He is ashamed of it.",
            "knows": "the cave church entrance is behind the drowned chapel",
        },
    },
    "world_secrets": {
        "ceremony_true_requirements": "TODO — what Miranda actually needs, versus "
                                     "what she tells the Lords she needs",
        "megamycete_agenda": "TODO — or decide it has none. Deepest secret either way.",
    },
}

# ── GM ONLY: fragments ────────────────────────────────────────────────────

FRAGMENTS = {
    "_warning": "GM ONLY. The narrator receives one fragment's content at a "
                "time and never learns what it connects to.",
    "fragments": [
        {
            "id": "frag_001",
            "trigger": "seeing military insignia, uniforms, or ordered rows of equipment",
            "content": "Hands on a rifle that is not this rifle. Someone laughing "
                       "to your left. The taste of dust and the smell of hot oil.",
            "leads_to": "frag_007",
            "dead_end": False,
        },
        {
            "id": "frag_002",
            "trigger": "antiseptic, bleach, or any clean chemical smell indoors",
            "content": "A white room. A table with a channel cut down the middle "
                       "of it. A voice, very calm: hold still.",
            "leads_to": "frag_012",
            "dead_end": False,
        },
        {
            "id": "frag_003",
            "trigger": "church bells, or hearing Miranda's name spoken in reverence",
            "content": "Kneeling. Not praying — the floor is cold and your knees "
                       "hurt and you are being made to wait.",
            "leads_to": None,
            "dead_end": True,
            "note": "deliberate dead end; not every thread goes somewhere",
        },
    ],
}

# ── an example character, split ───────────────────────────────────────────

MOREAU_PUBLIC = {
    "identity": "Salvatore Moreau | male | keeper of the reservoir",
    "look": "Small and badly stooped, one shoulder higher than the other. Hooded. "
            "What shows of his face does not sit right — one eye far larger than "
            "the other, skin slack and wet-looking.",
    "wears": "A soaked oilskin cloak over layers that were once a Lord's clothes.",
    "scent": "Lake water, fish, and something faintly sweet underneath.",
    "voice": "Stammering, apologetic, too fast. Interrupts himself to apologise "
             "for talking. Goes quiet mid-sentence when he thinks he has annoyed you.",
    "speech_examples": [
        "\"O-oh. You're — you're here. Do you want me to go? I can go.\"",
        "\"I wasn't doing anything. I was just — it's my lake. I'm allowed.\"",
        "\"Mother says I'm — she says I'll be better. Soon. She said soon.\"",
    ],
    "default_state": "cowering — expects to be told to leave his own home",
    "states": {
        "cowering": "hood up, shoulders hunched, apologising pre-emptively",
        "hopeful": "talks too much and too fast, offers things he cannot spare",
        "wounded": "goes silent and still; will not look up",
    },
    "likes": ["being spoken to as a person", "fish", "being told he did well"],
    "dislikes": ["mirrors", "being laughed at", "the other Lords"],
    "never_says": [
        "anything critical of Mother Miranda",
        "anything that would make him sound proud",
    ],
}

MOREAU_PRIVATE = {
    "_note": "Sections here unlock when the GM writes 'moreau.<section>' into "
             "reveal_this_turn. Until then the narrator has never seen them.",
    "drives": "To be seen as one of the Lords rather than the failure among them. "
              "Beneath that, and stronger: to be told once, plainly, that he is "
              "loved. He will trade anything for it, including his own safety.",
    "context": "Miranda's least successful surviving experiment. The others "
               "despise him for it, and he agrees with them.",
    "capability": "He can enter deep water and take another form — enormous, "
                  "and not remotely pitiable. He avoids it because of what he "
                  "sees on people's faces afterwards.",
    "knows": "The cave church entrance lies behind the drowned chapel. He has "
             "never told anyone because nobody has ever asked him anything.",
    "weaknesses": ["direct kindness", "any mention of being useful to Miranda"],
    "loss_of_control": "If mocked at length, or if someone he has started to "
                       "trust turns on him, he goes into the water. What comes "
                       "back out is not interested in apologising.",
    "trust_gates": {
        "1": "does not flee when approached",
        "3": "will answer direct questions",
        "5": "volunteers something he was not asked — release 'knows'",
        "7": "shows the water form willingly — release 'capability'",
    },
}


def main() -> None:
    print(f"seeding {DATA}")
    write("world.json", WORLD)
    write("pc.json", PC)
    write("world_state.json", WORLD_STATE)
    write("vault.json", VAULT)
    write("fragment_map.json", FRAGMENTS)
    write("characters/moreau/public.json", MOREAU_PUBLIC)
    write("characters/moreau/private.json", MOREAU_PRIVATE)
    (DATA / "characters" / "moreau" / "portraits").mkdir(parents=True, exist_ok=True)
    (DATA / "saves").mkdir(parents=True, exist_ok=True)
    print(
        "\ndone.\n"
        "  next: fill in the TODOs in data/vault.json — the game is only as\n"
        "  interesting as what is hidden there.\n"
        "  then: split the other character .txt docs into public/private pairs\n"
        "  under data/characters/<id>/, using moreau as the template.\n"
        "  portraits are optional; drop <mood>.webp files in each portraits/ dir\n"
        "  and the GM's portrait_state will select them."
    )


if __name__ == "__main__":
    main()
