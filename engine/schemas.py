"""The briefing packet schema.

This is the Wall's contract. The GM is constrained to this shape at the
sampling layer via output_config.format, so a malformed packet is not a
failure mode we have to handle — the model physically cannot emit one.

Two shape changes from the original design doc, both forced by the schema
constraints of structured outputs:

  1. Objects keyed by NPC id (npc_direction, psyche_updates) become arrays
     of objects carrying an `npc` field. Structured outputs require
     additionalProperties: false on every object, which rules out
     arbitrary-key maps.

  2. state_updates becomes a flat list of path/op/value edits rather than a
     nested dict to deep-merge. Turned out to be the better design anyway:
     every mutation is individually inspectable and loggable, and there is
     no ambiguity about whether a nested dict replaces or merges.
"""


def _obj(properties: dict, **kw) -> dict:
    """An object schema with every key required and no extras.

    Structured outputs demand additionalProperties: false and a complete
    `required` list. Optional fields are expressed as nullable types, not
    omitted keys.
    """
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": False,
        **kw,
    }


STR = {"type": "string"}
NUM = {"type": "number"}
INT = {"type": "integer"}
NULLABLE_STR = {"type": ["string", "null"]}
STR_LIST = {"type": "array", "items": STR}


BRIEFING_SCHEMA = _obj(
    {
        "scene_context": _obj(
            {
                "location": STR,
                "sub_location": NULLABLE_STR,
                "time_of_day": STR,
                "weather": STR,
                "npcs_present": {
                    **STR_LIST,
                    "description": "Character ids of NPCs physically in the scene. "
                    "Must match directory names under data/characters/.",
                },
                "npcs_nearby": {
                    **STR_LIST,
                    "description": "Audible or visible but not interactable yet.",
                },
                "ambient": {
                    **STR,
                    "description": "Sensory detail the narrator should build the "
                    "scene from. Concrete, not atmospheric filler.",
                },
            }
        ),
        "action_resolution": _obj(
            {
                "player_action": {
                    **STR,
                    "description": "Your reading of what the player is attempting.",
                },
                "mechanical_result": {
                    **STR,
                    "description": "The adjudication in plain terms: which stat was "
                    "checked, against what difficulty, and what happened. The "
                    "narrator writes this outcome; it does not re-roll it.",
                },
                "narration_guidance": {
                    **STR,
                    "description": "HOW to present the result without revealing WHY. "
                    "'Describe the tripwire through environmental detail', not "
                    "'Moreau set a tripwire because he is frightened'.",
                },
            }
        ),
        "information_release": _obj(
            {
                "reveal_this_turn": {
                    **STR_LIST,
                    "description": "Facts the narrator is now authorised to use. "
                    "These become permanent — they enter the revelation log.",
                },
                "fragment_trigger": {
                    **NULLABLE_STR,
                    "description": "Verbatim content of a memory fragment firing this "
                    "turn, or null. The narrator receives the flash without knowing "
                    "what it means or where it leads.",
                },
                "discovery_unlock": {
                    **NULLABLE_STR,
                    "description": "Id of a secret the player has just discovered, or null.",
                },
            }
        ),
        "npc_direction": {
            "type": "array",
            "description": "One entry per NPC in npcs_present.",
            "items": _obj(
                {
                    "npc": STR,
                    "portrait_state": {
                        **STR,
                        "description": "Emotional state key. Selects the portrait "
                        "file; falls back to 'default' if no image exists.",
                    },
                    "psyche_summary": {
                        **STR,
                        "description": "What this NPC is feeling and wanting right "
                        "now, in one or two sentences.",
                    },
                    "behavioral_instruction": {
                        **STR,
                        "description": "Concretely, what they do if the player engages.",
                    },
                }
            ),
        },
        "state_updates": {
            "type": "array",
            "description": "Mutations to apply. Dotted paths rooted at 'pc' or "
            "'world', e.g. pc.vitals.stamina.current or world.calendar.days_to_ceremony.",
            "items": _obj(
                {
                    "path": STR,
                    "op": {
                        "type": "string",
                        "enum": ["set", "add"],
                        "description": "'add' is a delta; use it for drains and gains.",
                    },
                    "number": {
                        "type": ["number", "null"],
                        "description": "Numeric value. Null if this is a text edit.",
                    },
                    "text": {
                        **NULLABLE_STR,
                        "description": "String value. Null if this is a numeric edit.",
                    },
                    "reason": {
                        **STR,
                        "description": "Why, for the debug log.",
                    },
                }
            ),
        },
        "offscreen_events": {
            "type": "array",
            "description": "Things that happened elsewhere this turn. These are "
            "recorded but NOT sent to the narrator — it cannot foreshadow what it "
            "does not know. They surface only when the player acts to reveal them.",
            "items": _obj({"summary": STR, "surfaces_when": STR}),
        },
        "hud": _obj(
            {
                "hp": NUM,
                "stamina": NUM,
                "mold": NUM,
                "weapon": STR,
                "ammo": NULLABLE_STR,
                "lei": INT,
                "location": STR,
                "time": STR,
                "weather": STR,
                "days_to_ceremony": INT,
                "attention_dimitrescu": NUM,
                "attention_village": NUM,
                "threat_lycan": NUM,
                "companion": NULLABLE_STR,
                "key_items": STR_LIST,
                "active_quest": STR,
            }
        ),
    }
)
