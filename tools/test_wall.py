#!/usr/bin/env python3
"""Prove the Wall holds. No API key, no network, no cost.

Runs a real turn through the real engine with both providers replaced by fakes
that record exactly what they were handed. Then asserts the thing the whole
architecture exists to guarantee:

    nothing from the vault, the fragment map, or the unreleased half of any
    character card appears anywhere in the narrator's context.

Run this after touching anything under engine/. If it fails, the narrator can
leak, and no amount of prompt instruction will reliably stop it.

    python tools/test_wall.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.providers.base import Capabilities, GenParams, Provider, SystemBlock  # noqa: E402
from engine.providers.validate import validate  # noqa: E402
from engine.schemas import BRIEFING_SCHEMA  # noqa: E402


class RecordingProvider(Provider):
    """Captures requests; replays a canned response."""

    def __init__(self, name: str, packet: dict | None = None, prose: str = ""):
        super().__init__(f"fake-{name}")
        self.name = name
        self.packet = packet
        self.prose = prose
        self.seen_system: list[SystemBlock] = []
        self.seen_messages: list[dict] = []

    @property
    def caps(self) -> Capabilities:
        return Capabilities(
            schema_forcing=True, caching="explicit", effort=True,
            effort_levels=("low", "medium", "high"), mid_conversation_system=True,
        )

    def _record(self, system, messages):
        self.seen_system = list(system)
        self.seen_messages = list(messages)

    def complete_json(self, system, messages, schema, params):
        self._record(system, messages)
        return self.packet

    def stream_text(self, system, messages, params):
        self._record(system, messages)
        yield self.prose

    def context_text(self) -> str:
        """Everything this model was shown, as one string."""
        parts = [b.text for b in self.seen_system]
        for m in self.seen_messages:
            content = m.get("content")
            if isinstance(content, list):
                parts.extend(p.get("text", "") for p in content)
            else:
                parts.append(str(content))
        return "\n".join(parts)


def StateManager_section_text(section) -> str:
    """Flatten a private section to searchable text, whatever shape it is.

    Sections are either a bare value (v1) or a dict with truth/rumor plus
    routing metadata (v2), and `truth` itself may be a string or a nested dict
    of gated states. Only the *content* is returned — route descriptions are
    excluded, since those are expected to be absent from the narrator anyway
    and are checked separately.
    """
    if isinstance(section, str):
        return section
    if isinstance(section, list):
        return " ".join(str(x) for x in section)
    if isinstance(section, dict):
        truth = section.get("truth", section)
        if isinstance(truth, str):
            return truth
        if isinstance(truth, list):
            return " ".join(str(x) for x in truth)
        if isinstance(truth, dict):
            return " ".join(str(v) for v in truth.values())
    return ""


PACKET = {
    "scene_context": {
        "location": "Moreau's Reservoir", "sub_location": "chapel shore",
        "time_of_day": "evening", "weather": "freezing rain",
        "npcs_present": ["moreau"], "npcs_nearby": [],
        "ambient": "Grey water lapping broken stone. The chapel window glows faintly.",
    },
    "action_resolution": {
        "player_action": "approach the chapel cautiously",
        "mechanical_result": "perception 0.7 vs difficulty 0.4 — SUCCESS. Notices "
                             "fishing line at ankle height across the doorway.",
        "narration_guidance": "let the soldier's instincts catch it; environmental "
                              "detail only, do not name who lives here",
    },
    "information_release": {
        "reveal_this_turn": ["the chapel has been lived in recently"],
        "fragment_trigger": None, "discovery_unlock": None,
    },
    "npc_direction": [{
        "npc": "moreau", "portrait_state": "cowering",
        "psyche_summary": "frightened, heard footsteps, debating whether to flee",
        "behavioral_instruction": "in the corner, hood up. Speaks first because "
                                 "silence is worse. First word is an apology.",
    }],
    "state_updates": [
        {"path": "pc.vitals.stamina.current", "op": "add", "number": -0.05,
         "text": None, "reason": "travel in freezing rain"},
        {"path": "world.calendar.time_of_day", "op": "set", "number": None,
         "text": "evening", "reason": "time passed"},
    ],
    "offscreen_events": [{
        "summary": "Leonardo checked the east fence at dusk and was not attacked",
        "surfaces_when": "if the player asks Elena about her father",
    }],
    "hud": {
        "hp": 0.85, "stamina": 0.65, "mold": 0.07, "weapon": "nothing", "ammo": None,
        "lei": 0, "location": "Moreau's Reservoir", "time": "Evening",
        "weather": "Freezing Rain", "days_to_ceremony": 18,
        "attention_dimitrescu": 0.0, "attention_village": 0.05, "threat_lycan": 0.2,
        "companion": None, "key_items": [], "active_quest": "Explore the reservoir",
    },
}


def main() -> int:
    from engine.wall import Wall

    config = {"gm": {"provider": "anthropic", "model": "x"},
              "narrator": {"provider": "anthropic", "model": "y"},
              "dev_mode": False, "history_turns": 20}

    # Build the Wall without touching the provider factory.
    wall = Wall.__new__(Wall)
    wall.root = ROOT
    wall.config = config
    wall.data_dir = ROOT / "data"

    from engine.presets import PresetManager
    from engine.state import StateManager
    from engine.gm import GameMaster
    from engine.narrator import Narrator

    wall.state = StateManager(wall.data_dir)
    wall.presets = PresetManager(wall.data_dir / "presets")
    wall.dev_mode = False
    wall.feedback = []
    wall.last_input = None
    wall.busy = False

    gm_provider = RecordingProvider("gm", packet=PACKET)
    nar_provider = RecordingProvider("narrator", prose="The chapel door hung open.")
    wall.gm = GameMaster(gm_provider, max_tokens=4000)
    wall.narrator = Narrator(nar_provider, max_tokens=3000, history_turns=20)

    # Model a continuing scene rather than turn one. The GM only receives full
    # card text for characters already in the cast or named in the player's
    # input — so a fresh state with an action that names nobody would correctly
    # give it no bodies at all, and the "GM must see the secrets" assertions
    # below would fail for the right reason but the wrong cause.
    wall.state.current_npcs = ["moreau"]

    events: list[dict] = []
    wall.run_turn("I approach the chapel, keeping low.", events.append)

    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  — {detail}" if detail and not ok else ""))
        if not ok:
            failures.append(label)

    print("\nschema")
    check("canned packet validates against BRIEFING_SCHEMA",
          not validate(PACKET, BRIEFING_SCHEMA), str(validate(PACKET, BRIEFING_SCHEMA)))

    print("\nturn ran")
    kinds = [e["type"] for e in events]
    check("no errors raised", "error" not in kinds,
          next((e["text"] for e in events if e["type"] == "error"), ""))
    check("prose streamed", "delta" in kinds)
    check("hud emitted", "hud" in kinds)
    check("portraits emitted", "portraits" in kinds)
    check("turn committed", wall.state.turn_count == 1)

    print("\nstate applied")
    stamina = wall.state.pc["vitals"]["stamina"]["current"]
    check("op=add applied as delta", abs(stamina - 0.65) < 1e-9, f"stamina={stamina}")
    check("op=set applied", wall.state.world["calendar"]["time_of_day"] == "evening")
    check("revelation recorded",
          "the chapel has been lived in recently" in wall.state.revelation_log)
    check("scene cast tracked", wall.state.current_npcs == ["moreau"])

    print("\nTHE WALL — narrator context")
    narrator_ctx = gm_ctx = ""
    narrator_ctx = nar_provider.context_text()
    gm_ctx = gm_provider.context_text()

    # Distinctive strings that live only on the GM's side.
    #
    # Probes are derived from whatever is actually on disk rather than hardcoded
    # to particular section names. Cards get rewritten and renamed constantly
    # during authoring, and a leak test that breaks when a section is renamed is
    # a test that gets deleted. This version keeps working.
    fragments = json.loads((wall.data_dir / "fragment_map.json").read_text(encoding="utf-8"))

    secrets = {
        "vault warning banner": wall.state.vault["_warning"],
        "fragment content (untriggered)": fragments["fragments"][0]["content"][:50],
        "offscreen event (GM-only)": "Leonardo checked the east fence",
    }

    # Take a distinctive slice from every still-locked section on the NPC in
    # the scene. All of it must be absent from the narrator's context.
    locked = wall.state.locked_sections("moreau")
    sections = wall.state._private_sections("moreau")
    probed = 0
    for name in locked:
        content = StateManager_section_text(sections[name])
        if content and len(content) > 70:
            secrets[f"moreau.{name} (locked)"] = content[30:90]
            probed += 1
    check("derived probes from locked sections", probed >= 3, f"only {probed} usable")
    for label, needle in secrets.items():
        check(f"absent from narrator: {label}", needle not in narrator_ctx)

    # And confirm the GM *did* see them, so the test isn't passing vacuously.
    print("\nGM context (sanity — these must be present)")
    for label, needle in secrets.items():
        if label.startswith("offscreen"):
            continue  # the GM generated it this turn; it isn't in its input
        check(f"present for GM: {label}", needle in gm_ctx)

    print("\nnarrator got what it needed")
    check("public card present", "keeper of the reservoir" in narrator_ctx)
    check("briefing present", "perception 0.7 vs difficulty 0.4" in narrator_ctx)
    check("guidance present", "do not name who lives here" in narrator_ctx)
    check("released fact present", "chapel has been lived in" in narrator_ctx)

    print("\ntrust gate (single-section release — moreau)")
    before = wall.state.get_narrator_card("moreau")
    wall.state.revelation_log.append("moreau.knows")
    after = wall.state.get_narrator_card("moreau")
    check("locked section hidden before release", "knows" not in before)
    check("locked section visible after release", "knows" in after)
    check("still hides other sections", "capability" not in after)

    print("\ndiscovery routes (v2 card with rumour variants — alcina)")
    st = wall.state
    if "alcina" not in st.known_npcs():
        print("  SKIP  alcina card not present")
    else:
        SECTION = "alcina.miranda_resentment"
        check("starts locked", "miranda_resentment" not in st.get_narrator_card("alcina"))

        # Second-hand route: a maid's gossip. Directionally right, wrong in
        # specifics — the narrator must get the rumour, not the truth.
        st.revelation_log.append(f"{SECTION}#rumor")
        got = st.get_narrator_card("alcina").get("miranda_resentment", "")
        check("second-hand route yields the rumour", got.startswith("The staff say"))
        check("rumour is not the truth", "inability to kill her" not in got)

        # First-hand route later. Truth must supersede.
        st.revelation_log.append(SECTION)
        got = st.get_narrator_card("alcina").get("miranda_resentment", "")
        check("first-hand route supersedes the rumour", "inability to kill her" in got)

        # Order independence: hearing the rumour again must not downgrade.
        st.revelation_log.append(f"{SECTION}#rumor")
        got = st.get_narrator_card("alcina").get("miranda_resentment", "")
        check("truth survives a later rumour", "inability to kill her" in got)

        card = st.get_narrator_card("alcina")
        blob = str(card)
        # The routing table is the GM's map of where secrets can be found.
        # Handing it to the narrator would disclose every secret's existence
        # and shape without disclosing its content — worse than useless.
        check("learnable_from never crosses the Wall", "learnable_from" not in blob)
        check("route descriptions absent", "pressed gently" not in blob)
        check("v2 wrapper keys absent", "sections" not in card and "_schema" not in card)
        check("authoring notes stripped", not any(k.startswith("_") for k in card))
        for probe, label in (("Pallboys", "pre_mutation_life"),
                             ("chiropteran", "dragon_nature"),
                             ("forty years", "cadou_degeneration")):
            check(f"still-locked section absent: {label}", probe not in blob)

        gm = str(st.get_gm_card("alcina"))
        check("GM sees the routes", "learnable_from" in gm)
        check("GM sees locked content", "Pallboys" in gm)

    print("\nin-world documents")
    docs = {d["id"]: d for d in wall.state.documents}
    check("documents loaded", bool(docs), f"{len(docs)} found")
    for doc in docs.values():
        keys = doc.get("reveals") or []
        check(f"{doc['id']} declares reveals", bool(keys))
        # A reveals key that names a section nobody has must be a typo.
        for key in keys:
            npc, _, sec = key.partition(".")
            sec = sec.split("#")[0]
            known = sec in wall.state._private_sections(npc) if npc in wall.state.known_npcs() else False
            check(f"  -> {key} resolves", known)

    print("\ncaching")
    cached = [b for b in nar_provider.seen_system if b.cache]
    check("narrator has a cache breakpoint", len(cached) == 1)
    check("GM has a cache breakpoint",
          len([b for b in gm_provider.seen_system if b.cache]) == 1)

    print()
    if failures:
        print(f"{len(failures)} FAILED: " + "; ".join(failures))
        return 1
    print("all checks passed — the Wall holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
