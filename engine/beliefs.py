"""Belief resolution and disclosure posture. GM-side only.

The three-tier epistemic stack, resolved lazily:

    tier 3   runtime ledger        state.beliefs — perception updates and
                                   generate-and-commit fills; saves carry it
    tier 2   seed_beliefs          private card, top-level block beside
                                   `sections` — the load-bearing DIVERGENT
                                   beliefs only; where this person departs
                                   from their faction's default
    tier 1   faction chain         data/factions.json — defaults by
                                   population, nearest faction first

Resolution walks 3 -> 2 -> 1 and returns the first hit. A total miss is not
an error; it is the signal to generate-and-commit: the lazy-instantiation
pass writes a new tier-3 entry from the character's card and ledger (never
the vault) and the miss never recurs. A generated belief that happens to be
true is a lucky guess, not a leak — the generator could not see the truth,
and neither can the narrator, so the prose cannot confirm it.

Nothing in this module may be imported by narrator.py. Faction orthodoxies
are honest about what groups collectively know (see the court), which makes
factions.json vault-adjacent. Only the resolved output for characters in
the scene crosses the Wall, carried by the briefing.

DIVERGENCE is computed, not authored: a belief diverges when it differs
from what the faction chain alone would have said. That makes the
disclosure math run without anyone hand-marking heresies — and it means a
character can be wrong about the room, because pressure is computed from
who is actually listening, while the character acts on their *beliefs*
about those listeners. Miscalibration is just an inaccurate belief, and
inaccurate beliefs are first-class.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Disclosure postures, ordered from open to closed. Bands, not scalars, so a
# posture is loggable, testable, and directly usable as an acting note.
POSTURES = (
    "volunteers",
    "states_if_relevant",
    "admits_if_pressed",
    "deflects",
    "lies",
)

_ENFORCEMENT = {"none": 0, "soft": 1, "hard": 2, "lethal": 3}
_SENSITIVITY = {"low": -1, "normal": 0, "high": 1}


@dataclass
class Belief:
    npc: str
    subject: str
    text: str
    source: str        # "ledger" | "seed" | "faction:<id>"
    divergent: bool    # differs from what the faction chain alone would say


class BeliefResolver:
    def __init__(self, data_dir: Path, state):
        self.state = state
        raw = json.loads((Path(data_dir) / "factions.json").read_text(encoding="utf-8"))
        self.factions: dict = raw["factions"]
        self.members: dict = raw["members"]
        self.default_member_of: str | None = raw.get("default_member_of")

        # tier 3. StateManager grows this when the ledger lands; until then a
        # resolver on a bare state still works, it just has an empty tier.
        if not hasattr(state, "beliefs"):
            state.beliefs = {}

    # ── the chain ──

    def faction_chain(self, npc_id: str) -> list[str]:
        """Every faction binding this character, nearest first.

        Membership lists the most specific faction; parents are implied and
        walked here. Multiple memberships keep list order as precedence. An
        explicit empty list means parentless — the Duke and Miranda — and the
        default membership does NOT apply to them: absence from the members
        map is what invokes the catch-all, not an empty entry.
        """
        if npc_id in self.members:
            nearest = self.members[npc_id]
        else:
            nearest = [self.default_member_of] if self.default_member_of else []

        # Breadth-first, so "nearest first" survives multiple memberships:
        # every direct membership outranks any parent, and a shared ancestor
        # lands at its shallowest depth. Walking each membership to the root
        # in turn would let the first membership's ROOT outrank the second
        # membership itself — a church-going farmer whose doubt about the
        # harvest was answered by the valley instead of his own plot.
        chain: list[str] = []
        frontier = list(nearest)
        while frontier:
            parents: list[str] = []
            for fid in frontier:
                if fid is None or fid in chain:
                    continue
                chain.append(fid)
                parent = (self.factions.get(fid) or {}).get("parent")
                if parent is not None:
                    parents.append(parent)
            frontier = parents
        return chain

    # ── resolution ──

    def _chain_default(self, npc_id: str, subject: str) -> tuple[str, str] | None:
        """(faction_id, belief) from the chain alone, or None."""
        for fid in self.faction_chain(npc_id):
            orth = (self.factions.get(fid) or {}).get("orthodoxies") or {}
            if subject in orth:
                return fid, orth[subject]
        return None

    def _seed(self, npc_id: str, subject: str) -> str | None:
        private = self.state._card(npc_id)["private"]
        seeds = private.get("seed_beliefs") or {}
        return seeds.get(subject)

    def resolve(self, npc_id: str, subject: str) -> Belief | None:
        """Ledger -> seed -> chain. None means generate-and-commit."""
        default = self._chain_default(npc_id, subject)

        ledger = (self.state.beliefs.get(npc_id) or {})
        if subject in ledger:
            text = ledger[subject]
            return Belief(npc_id, subject, text, "ledger",
                          divergent=default is not None and text != default[1])

        seed = self._seed(npc_id, subject)
        if seed is not None:
            return Belief(npc_id, subject, seed, "seed",
                          divergent=default is not None and seed != default[1])

        if default is not None:
            fid, text = default
            return Belief(npc_id, subject, text, f"faction:{fid}", divergent=False)

        return None

    # ── disclosure ──

    def _sensitivity(self, npc_id: str) -> int:
        private = self.state._card(npc_id)["private"]
        return _SENSITIVITY.get(private.get("reputation_sensitivity", "normal"), 0)

    def posture(self, speaker: str, belief: Belief, listeners: list[str]) -> str:
        """How openly the speaker treats this belief in this company.

        v1 of the apple-pie math. Pressure is the worst clash in the room:
        for each listener whose own chain holds an orthodoxy on the subject
        that the speaker's belief contradicts, take the enforcement weight of
        the faction holding that orthodoxy; keep the max; add the speaker's
        reputation sensitivity; clamp to the posture table.

        Orthodoxy is a shield: a belief that CONFORMS to the speaker's own
        order is freely spoken no matter who disagrees — the village prays in
        front of Heisenberg, and his contempt is not pressure. But the shield
        belongs to the order, not to the speaker. Someone whose chain says
        nothing on the subject — the parentless above all — stands behind no
        one, and their belief is measured against the room like any heresy.
        The Duke does not float "Miranda is a parasite" past Eugen merely
        because no faction ever told the Duke what to think.

        Deliberately NOT modelled yet: listener power over the speaker
        (Miranda outranks the enforcement table), personal-history modifiers,
        and the speaker's possibly-wrong beliefs about the listeners — the
        honest v2 feeds this function tier-3 beliefs about each listener
        instead of ground truth. The signature already permits that swap.
        """
        default = self._chain_default(speaker, belief.subject)
        if default is not None and belief.text == default[1]:
            return "volunteers" if belief.source != "ledger" else "states_if_relevant"

        pressure = 0
        for lid in listeners:
            if lid == speaker:
                continue
            hit = self._chain_default(lid, belief.subject)
            if hit is None:
                continue
            fid, text = hit
            if text == belief.text:
                continue  # they share the heresy, or the belief matches
            # The listener enforces with their own order's zeal, not the
            # holder's: Eugen punishes doubt in the COMMON faith at church
            # intensity, though the orthodoxy itself is the village's. Weight
            # is therefore the max enforcement along the listener's chain from
            # their nearest faction through the faction holding the orthodoxy.
            weight = 0
            for cid in self.faction_chain(lid):
                w = _ENFORCEMENT.get((self.factions.get(cid) or {}).get("enforcement", "none"), 0)
                weight = max(weight, w)
                if cid == fid:
                    break
            pressure = max(pressure, weight)

        pressure += self._sensitivity(speaker)
        pressure = max(0, min(pressure, len(POSTURES) - 1))
        return POSTURES[pressure]
