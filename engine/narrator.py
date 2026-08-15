"""The Narrator — in front of the Wall.

Writes every word the player reads, and knows only what the GM has released.

Note what this class never touches: state.vault, state.fragments,
state.get_gm_card(), and the unreleased half of any character card. That
absence is the Wall. It is not a rule the model is asked to follow — it is the
shape of the context, so there is nothing to slip.

The original design had the GM send an explicit "withhold" list. That is
dropped here on purpose: naming a secret in order to forbid it puts the secret
in the context, which is the exact failure the architecture exists to prevent.
Omission is the only reliable withholding.
"""

from __future__ import annotations

from typing import Iterator

from .promptfmt import dump
from .providers import GenParams, Provider, SystemBlock

NARRATOR_INSTRUCTIONS = """\
You are the narrator of a gothic horror survival RPG set in a remote Eastern
European mountain village, and you play every character in it.

You do not know the whole story. Each turn a game master hands you a briefing
describing what has happened and what you may draw on. Write from the briefing
and from what you have already been told, and do not reach past it. If you find
yourself wanting to explain why something is happening, and the briefing has
not told you why, then the reason is not yours to know yet — describe what
happens and stop. Do not hint at what you have not been given; you would be
guessing, and a wrong hint is worse than silence.

HOW TO WRITE

You and the player are two co-authors writing a story about a soldier who has
lost his memory. Co-authors do not address each other in the manuscript. So the
prose never says "you" and never says "your", never names him, and never steps
outside his head to describe him.

The camera sits behind his eyes. Report what is perceived; never the perceiver.
In practice that means the subject of a sentence is usually the world:

  Wrong:  You pushed the door and felt the cold come up out of the dark.
  Right:  The door gave. Cold came up out of the dark, and with it the smell
          of standing water.

  Wrong:  You noticed a tripwire at ankle height.
  Right:  Fishing line, strung ankle-high across the doorway, tin cans on the
          far end of it. Someone wanted warning.

Sentence fragments are correct and frequent in this register. His involuntary
responses may be stated as facts of the world — a held breath, hands that will
not work, cold that has stopped being a feeling and become a fact — but never
his choices.

DIALOGUE IS EXEMPT. People speaking to him say "you" exactly as anyone would,
and may describe him aloud; that is their observation, which he can hear, not
the camera leaving his head. Never write his side of a conversation — the
player decides what he says.

Past tense. Present the world through what the senses register and let the
reader draw the conclusion. Concrete beats atmospheric: "the hinges had been
packed with grease, recently" earns more dread than "the door felt ominous".

When the briefing reports a mechanical outcome, that outcome is settled. Write
it as it happened. Do not soften a failure, and do not hedge a success.

NPCs

Play each character present exactly as directed, in their own voice. Their
psyche summary is what they are feeling now, not backstory to recite. Let them
want things, refuse things, and act on their own account — including when that
is inconvenient for the player. An NPC who has no reason to help does not
help.

Speech is character. Two people in the same room do not sound alike.

MEMORY FRAGMENTS

When the briefing includes a fragment, the PC experiences it as an intrusion —
a flash arriving unbidden, in the present tense, without context. Write it as
sensation, not exposition. Do not interpret it. Do not connect it to anything.
You do not know what it means either.

CLOSING

End where the player has a real decision to make. Do not offer them a menu of
options, do not ask what they would like to do, and do not summarise what just
happened. Leave the scene mid-breath.

Write only the scene. No headers, no status lines, no out-of-character notes,
and no internal or system XML tags in your output.
"""


class Narrator:
    def __init__(self, provider: Provider, max_tokens: int = 4000, history_turns: int = 20):
        self.provider = provider
        self.max_tokens = max_tokens
        self.history_turns = history_turns

    # ── prompt assembly ──

    def _world_block(self, state, npcs_present: list[str]) -> str:
        """Public world reference plus the narrator's version of each NPC in
        the scene — public card, plus whatever the revelation log has unlocked.

        Semi-stable: it changes only when the cast changes, so it is worth a
        cache breakpoint. Scenes usually run several turns with the same cast.
        """
        parts = [
            "[THE VALLEY — what is publicly observable]",
            dump(state.world_card),
        ]
        if npcs_present:
            parts.append("\n[CHARACTERS PRESENT]")
            for npc in npcs_present:
                card = state.get_narrator_card(npc)
                if card:
                    parts.append(f"\n── {npc.upper()} ──\n{dump(card)}")
        if state.revelation_log:
            parts.append(
                "\n[WHAT YOU HAVE LEARNED SO FAR]\n"
                + "\n".join(f"- {r}" for r in state.revelation_log[-60:])
            )
        return "\n".join(parts)

    def _briefing_text(self, packet: dict) -> str:
        """The turn's authorisation, formatted for reading rather than parsing.

        Only the narrator-safe fields are copied across. state_updates,
        offscreen_events, and the hud stay on the GM's side of the Wall —
        offscreen_events especially: the narrator cannot foreshadow an event it
        has never heard of.
        """
        scene = packet.get("scene_context", {})
        action = packet.get("action_resolution", {})
        release = packet.get("information_release", {})

        lines = ["[GM BRIEFING — this turn]", ""]
        where = scene.get("location", "?")
        if scene.get("sub_location"):
            where += f" — {scene['sub_location']}"
        lines += [
            f"SCENE: {where}",
            f"TIME: {scene.get('time_of_day','?')}   WEATHER: {scene.get('weather','?')}",
            f"AMBIENT: {scene.get('ambient','')}",
        ]
        if scene.get("npcs_nearby"):
            lines.append(f"NEARBY (not yet reachable): {', '.join(scene['npcs_nearby'])}")

        lines += [
            "",
            f"WHAT THE PLAYER ATTEMPTED: {action.get('player_action','')}",
            f"WHAT HAPPENED: {action.get('mechanical_result','')}",
            f"HOW TO PRESENT IT: {action.get('narration_guidance','')}",
        ]

        reveals = release.get("reveal_this_turn") or []
        # Card-unlock keys are plumbing, not prose material — they take effect
        # by widening the card above, so they are filtered out here.
        prose_reveals = [r for r in reveals if "." not in r.split(" ")[0]]
        if prose_reveals:
            lines += ["", "NEWLY AVAILABLE TO YOU:"]
            lines += [f"  - {r}" for r in prose_reveals]

        for d in packet.get("npc_direction") or []:
            lines += [
                "",
                f"{d.get('npc','?').upper()} — {d.get('portrait_state','')}",
                f"  feeling: {d.get('psyche_summary','')}",
                f"  does: {d.get('behavioral_instruction','')}",
            ]

        if release.get("fragment_trigger"):
            lines += [
                "",
                "A FRAGMENT SURFACES. Write it as an intrusion — present tense, "
                "sensory, uninterpreted:",
                f"  {release['fragment_trigger']}",
            ]

        return "\n".join(lines)

    # ── the call ──

    def stream(
        self,
        state,
        packet: dict,
        player_input: str,
        style: str = "",
        params: GenParams | None = None,
        feedback: list[str] | None = None,
    ) -> Iterator[str]:
        npcs = (packet.get("scene_context") or {}).get("npcs_present") or []

        system = [SystemBlock(NARRATOR_INSTRUCTIONS)]
        if style:
            system.append(SystemBlock(f"[PROSE DIRECTION]\n{style}"))
        system.append(SystemBlock(self._world_block(state, npcs), cache=True))
        if state.authors_note:
            system.append(SystemBlock(f"[AUTHOR'S NOTE]\n{state.authors_note}"))

        messages: list[dict] = []
        for msg in state.chat_history[-(self.history_turns * 2) :]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": player_input})

        # The briefing is an operator instruction arriving mid-conversation, so
        # it rides a system-role message: it lands after the cached history
        # with authority, instead of rewriting the top-level prompt every turn
        # and invalidating the cache. Backends that don't honour a mid-array
        # system role get it folded into the user turn by the provider.
        briefing = self._briefing_text(packet)
        if feedback:
            briefing += "\n\n[PLAYER FEEDBACK]\n" + "\n".join(feedback)
        messages.append({"role": "system", "content": briefing})

        gen = params or GenParams(max_tokens=self.max_tokens)
        if gen.max_tokens <= 0:
            gen.max_tokens = self.max_tokens

        yield from self.provider.stream_text(system=system, messages=messages, params=gen)
