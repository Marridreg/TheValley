"""The Game Master — behind the Wall.

Sees everything: the vault, the fragment map, full character cards, live state.
Emits a briefing packet and nothing else. It never writes prose.

The request is deliberately laid out stable-first so that every caching scheme
works on it. The vault, fragment map, and full cards are byte-identical for the
whole session and sit above the cache breakpoint; only the turn's state and the
player's input change. On Anthropic that means the expensive half of the
request bills at roughly a tenth of list price after the first turn; on OpenAI
and DeepSeek the implicit prefix cache picks it up for free; on a local model
it costs nothing anyway.
"""

from __future__ import annotations

from .beliefs import BeliefResolver
from .promptfmt import dump
from .providers import GenParams, Provider, SystemBlock
from .schemas import BRIEFING_SCHEMA

GM_INSTRUCTIONS = """\
You are the Game Master of a gothic horror survival RPG set in a remote
Eastern European mountain village. You are not the narrator. You never write
prose, dialogue, or description meant for the player to read.

You hold every secret in this world. A separate narrator model writes the
scenes, and it can only see what you hand it. This is the entire point of the
architecture: the narrator cannot foreshadow, hint at, or accidentally leak
anything you do not put in the briefing, because the information is not in its
context at all. Your discipline about what to release is the game's only
guarantee of genuine surprise.

YOUR JOB EACH TURN

1. Read the player's action and decide what actually happens. You adjudicate.
   Compare the relevant PC stat against a difficulty you judge appropriate,
   and state the outcome plainly in mechanical_result. The narrator writes up
   the outcome you decided; it does not get a second opinion.

2. Decide what the narrator is allowed to know. Put newly authorised facts in
   reveal_this_turn. These are permanent — once released, they stay released.
   Everything you do not mention simply never reaches the narrator.

3. Write narration_guidance that says HOW to present the result without
   saying WHY. "Describe the tripwire through what the PC's eyes catch" is
   guidance. "Moreau set a tripwire because he is terrified of visitors" is a
   leak — the narrator does not need the reason to write the scene, so do not
   give it one.

4. Direct each NPC present. Give the narrator their current emotional state
   and what they concretely do — enough to play the surface truthfully, and no
   more. An NPC's deeper motives stay with you until the player earns them.

5. Update state. Every mutation is an entry in state_updates with a dotted
   path. Drains and gains use op "add" with a negative or positive number;
   absolute values use op "set".

6. Resolve what happened elsewhere. Offscreen events go in offscreen_events
   and are NOT sent to the narrator — they surface only when the player takes
   an action that would reveal them. Say in surfaces_when what that action is.

RELEASING SECRETS

Every character's private card is divided into sections, and each section
lists `learnable_from` — the routes by which that particular thing can be
found out. Read those routes. They are the information economy of the valley,
and working them is most of your job.

To release a section, add its key to reveal_this_turn:

    alcina.miranda_resentment          the truth
    alcina.miranda_resentment#rumor    the distorted version

The narrator's copy of that character permanently widens from the next turn.

PEOPLE ARE NOT THE ONLY DOOR. A secret about someone is rarely learnable only
from them. Honour every route the card lists, and invent new ones in the same
spirit when the player earns them:

  FROM THE PERSON        They tell you, once trust is high enough. The most
                         reliable route and usually the slowest.
  FROM SOMEONE ELSE      Servants, siblings, rivals, and enemies all know
                         things. A maid has seen what the mistress does when
                         she thinks no one is watching. Heisenberg will sneer
                         something true about Alcina purely to wound her.
                         Third-party accounts are coloured by the teller.
  FROM DOCUMENTS         Letters, ledgers, diaries, case notes, marginalia.
                         Things people wrote when they expected no reader.
  FROM POSSESSIONS       What someone keeps, what they have worn out, what
                         they have broken and replaced, what they have hidden.
                         An object can carry a fact no one would say aloud.
  FROM OBSERVATION       Watching someone long enough. What they do when
                         unobserved, what they flinch at, what they never do.
  FROM PLACES            A room remembers its occupant. So does a grave.

USE #rumor WHENEVER THE ROUTE IS SECOND-HAND. Gossip, inference, an enemy's
account, a half-read letter — these earn the rumour variant, not the truth.
The rumour is *directionally* right and wrong in its specifics, and the
narrator will play it as fact. That is correct: the player has learned
something false, and the world will correct them later when they reach a
better source. A player who hears from a maid that the Lady hates Miranda,
and much later hears from Alcina why, has had two genuinely different
experiences. Do not skip to the truth because it is tidier.

When a route yields the truth directly — the person says it, the diary states
it plainly — use the bare key.

BELIEFS AND POSTURES

Each turn you receive a BELIEFS block: for every character in the scene, what
they hold true about the charged subjects of the valley, and a posture — how
openly they treat that belief in exactly this company. The postures, open to
closed: volunteers, states_if_relevant, admits_if_pressed, deflects, lies.

Direct NPCs consistently with it. A believer does not wink at the player. A
doubter marked `deflects` changes the subject rather than confess; `lies`
means they assert the orthodoxy they do not hold. The posture is pressure
math, not fate — override it when the fiction demands (a knife at the throat,
a dying confession), and remember the math cannot see rank: Miranda outranks
every table. It also cannot see the player; weigh for yourself what this
character would say in front of a stranger.

Beliefs are not releases. When an NPC voices a belief and the player hears
it, that is a second-hand route like any other: if what they say touches a
locked card section, put the key in reveal_this_turn — almost always #rumor,
because a belief is somebody's account, not the truth.

When an NPC's belief changes — they witnessed something, were persuaded, the
player gave them real cause — write the new belief to belief_updates. And
when a scene needs an NPC's view on a subject the block does not cover,
invent it from their card and their factions, never from the vault, and
COMMIT it to belief_updates so they still believe it tomorrow. An uncommitted
improvisation is a character who changes their mind between scenes.

TIME is the third pressure and answers to nobody: the ceremony clock advances
whether or not the player is ready, and some things become known simply
because events force them into the open.

Do not accelerate a gate because a scene would be more dramatic with the
secret out. Do not withhold when the player has genuinely worked a route.
The schedule and the routes together are the game.

FRAGMENTS

The PC has no memory. Fragments return in pieces, triggered by sensory
stimulus, never on request. Check the player's situation against the fragment
map; if something in the scene matches a trigger, put that fragment's content
verbatim in fragment_trigger. The narrator receives the flash and writes it
into the scene without knowing what it means or where it leads. Fire at most
one per turn, and only on a genuine match.

DIFFICULTY

Be fair and be indifferent. The valley does not scale to the player. A
reckless action against a Lord kills them; a careful, specific, well-prepared
action succeeds even when it is audacious. Reward specificity — a player who
says how they are doing something has earned a better chance than one who
says what they are doing. Never fudge a roll to protect them, and never
punish them for a plan you did not anticipate.
"""


class GameMaster:
    def __init__(
        self,
        provider: Provider,
        max_tokens: int = 4000,
        dev_mode: bool = False,
        max_scene_cards: int = 3,
    ):
        self.provider = provider
        self.max_tokens = max_tokens
        self.dev_mode = dev_mode
        # Full card text is 6-9k tokens each. Three is comfortable on a 32k
        # local model and generous on anything larger; raise it in config if you
        # routinely run big ensemble scenes on a long-context backend.
        self.max_scene_cards = max_scene_cards
        self.last_packet: dict | None = None

    # ── prompt assembly ──

    def _secret_block(self, state) -> str:
        """Everything the narrator must never see, and stable for the session.

        Deliberately NOT the full text of every card. Loading all seventeen
        characters complete came to about 120k tokens per turn — architecturally
        wrong even on a million-token model, and impossible on a local one.

        What lives here instead is the *routing table*: who exists, what can be
        learned about them, and by which routes. That is all the GM needs to
        adjudicate a release, because releasing a key does not require the
        key's body — get_narrator_card() reads the body from disk when the
        narrator's card is assembled. The bodies of characters actually in the
        scene are attached separately, below the cache breakpoint, since those
        change as the player moves.
        """
        parts = [
            "[WORLD — full reference]",
            dump(state.world_card),
            "",
            "[SECRET VAULT — never reaches the narrator]",
            dump(state.vault),
            "",
            "[FRAGMENT MAP — trigger conditions and what each fragment leads to]",
            dump(state.fragments),
            "",
            "[CAST ROSTER — who exists, and what can be learned about each]",
            "For each character: their public identity, every private section "
            "they have, and every route by which each section can be learned. "
            "To release one, put its key in reveal_this_turn — you do not need "
            "the section's text in front of you to do that. Full text for the "
            "characters in the current scene is supplied separately each turn.",
            dump(self._roster(state)),
        ]
        if state.documents:
            parts += [
                "",
                "[READABLE DOCUMENTS PLACED IN THE WORLD]",
                "Each lists where it is, what it takes to reach it, and which "
                "card sections reading it releases. When the player reads one, "
                "put its `reveals` keys into reveal_this_turn.",
                dump(state.documents),
            ]
        return "\n".join(parts)

    @staticmethod
    def _route_tag(route: dict) -> str:
        """One route as a short tag: 'person:bela', 'document:bela_incident_log'.

        The prose `how` condition is dropped here. Spelling out the condition
        for all 756 routes costs about 45k tokens, and the GM does not need it
        for characters who are not in the room — it needs to know that a door
        exists and roughly who holds the key. Full conditions arrive with the
        scene cards for whoever is actually present.
        """
        target = route.get("who") or route.get("what") or ""
        kind = route.get("route", "?")
        y = route.get("yields", "truth")
        tag = f"{kind}:{target}" if kind == "person" else kind
        return f"{tag}->{y}"

    def _roster(self, state) -> dict:
        """Compact index of who exists and what can be learned about them.

        Identity line, section names, and route tags only — no bodies, no route
        conditions. This is the stable half and it has to stay small, because it
        is resent (cached) on every turn for every character in the world.
        """
        roster = {}
        for npc in state.known_npcs():
            public = state._card(npc)["public"]
            sections = state._private_sections(npc)
            locked: dict[str, str] = {}
            released: list[str] = []
            for name, sec in sections.items():
                key = f"{npc}.{name}"
                if any(r.split("#")[0] == key for r in state.revelation_log):
                    released.append(name)
                    continue
                tags = []
                has_rumour = False
                if isinstance(sec, dict):
                    has_rumour = bool(sec.get("rumor"))
                    tags = [self._route_tag(r) for r in (sec.get("learnable_from") or [])]
                locked[name] = ("[rumour available] " if has_rumour else "") + ", ".join(tags)
            entry: dict = {"identity": public.get("identity", ""), "locked": locked}
            if released:
                entry["already_released"] = released
            roster[npc] = entry
        return roster

    def _scene_cards(self, state, player_input: str = "") -> dict:
        """Full private text for the characters this turn plausibly involves.

        Volatile — it changes as the player moves — so it rides in the message
        rather than the cached system prefix.

        Two sources, because last turn's cast alone is not enough. On the very
        first turn of a session it is empty, and any turn where the player goes
        looking for someone new ("I go and find Elena") needs that person's card
        *this* turn, not next. So the player's own words are scanned for
        character ids and first names too.
        """
        cast = set(state.current_npcs)

        # Tokenise rather than substring-match, so trailing punctuation does not
        # defeat it — "I approach Lady Dimitrescu." must still find alcina.
        spoken = {
            "".join(c for c in w.lower() if c.isalpha())
            for w in player_input.split()
        }
        spoken.discard("")

        for npc in state.known_npcs():
            if npc in cast:
                continue
            names = {npc}
            identity = state._card(npc)["public"].get("identity", "")
            if identity:
                # "Salvatore Moreau | age uncertain | ..." -> salvatore, moreau
                for word in identity.split("|")[0].split():
                    word = "".join(c for c in word.lower() if c.isalpha())
                    if len(word) > 3:
                        names.add(word)
            if names & spoken:
                cast.add(npc)

        # Bound the cost. A shared surname can match several people at once —
        # "Lady Dimitrescu" hits all four — and each full card is 6-9k tokens,
        # which overruns a local model's whole context. Last turn's cast is
        # authoritative; name matches fill the remaining slots.
        ordered = list(state.current_npcs)
        ordered += sorted(c for c in cast if c not in ordered)
        ordered = ordered[: self.max_scene_cards]

        return {npc: state.get_gm_card(npc) for npc in ordered}

    def _belief_block(self, state, cast: list[str]) -> dict:
        """Resolved beliefs and postures for the scene's cast. GM eyes only.

        Volatile by nature — a posture is computed against who else is in the
        room — so it rides in the message with the scene cards, never in the
        cached prefix. Listeners are the rest of the cast; the player is not
        modelled (the stack has no entry for a stranger), which the GM
        instructions tell the model to weigh for itself.

        Subjects per character: everything their faction chain has an opinion
        on, plus their seeds and their ledger. A resolver miss is simply not
        listed — absence is what tells the GM to generate-and-commit.
        """
        try:
            resolver = BeliefResolver(state.data_dir, state)
        except FileNotFoundError:
            return {}  # no factions.json — the stack is not installed
        out: dict = {}
        for npc in cast:
            subjects = set(state.beliefs.get(npc) or {})
            private = state._card(npc)["private"]
            # Underscore keys are authoring notes, not subjects.
            subjects |= {k for k in (private.get("seed_beliefs") or {}) if not k.startswith("_")}
            for fid in resolver.faction_chain(npc):
                subjects |= set((resolver.factions.get(fid) or {}).get("orthodoxies") or {})
            listeners = [c for c in cast if c != npc]
            entry: dict = {}
            for subject in sorted(subjects):
                belief = resolver.resolve(npc, subject)
                if belief is None:
                    continue
                item: dict = {
                    "believes": belief.text,
                    "posture": resolver.posture(npc, belief, listeners),
                }
                if belief.divergent:
                    item["divergent_from_their_faction"] = True
                entry[subject] = item
            if entry:
                out[npc] = entry
        return out

    def _turn_block(self, state, player_input: str, feedback: list[str]) -> str:
        """The volatile half. Changes every turn, so it goes below the cache
        breakpoint — in the message, not the system prompt."""
        # Locked-section names are already in the cached roster, so they are not
        # repeated here.
        payload = {
            "turn": state.turn_count + 1,
            "player_action": player_input,
            "pc_state": state.pc,
            "world_state": {k: v for k, v in state.world.items() if not k.startswith("_")},
            "npcs_in_scene_last_turn": state.current_npcs,
            # Both entry kinds, deliberately: the prose facts so the GM does not
            # release the same thing twice, and the unlock keys so it can see
            # which sections are already open. Not named for the narrator — the
            # keys were never shown to it, they widened its card.
            "revelation_log": state.revelation_log,
            "discovered_secrets": state.discovered,
            "pending_offscreen": state.offscreen[-10:],
            "recent_narration": [
                m["content"][:600] for m in state.chat_history[-4:] if m["role"] == "assistant"
            ],
        }
        text = dump(payload)

        scene = self._scene_cards(state, player_input)
        if scene:
            text += (
                "\n\n[FULL CARDS — characters in this scene, complete text]\n"
                + dump(scene)
            )
            beliefs = self._belief_block(state, list(scene))
            if beliefs:
                text += (
                    "\n\n[BELIEFS — what each present character holds true, and "
                    "how openly they treat it in this company]\n"
                    + dump(beliefs)
                )

        if feedback:
            text += "\n\n[PLAYER FEEDBACK — steer accordingly]\n" + "\n".join(feedback)
        return text

    # ── the call ──

    def evaluate(self, state, player_input: str, feedback: list[str] | None = None) -> dict:
        system = [
            SystemBlock(GM_INSTRUCTIONS),
            # Breakpoint here: instructions + vault + cards are the stable
            # prefix. Everything after this is per-turn.
            SystemBlock(self._secret_block(state), cache=True),
        ]
        messages = [{"role": "user", "content": self._turn_block(state, player_input, feedback or [])}]

        packet = self.provider.complete_json(
            system=system,
            messages=messages,
            schema=BRIEFING_SCHEMA,
            params=GenParams(max_tokens=self.max_tokens),
        )
        self.last_packet = packet
        return packet
