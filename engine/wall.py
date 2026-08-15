"""The Wall — the turn loop that keeps the two models apart.

Synchronous by design. It runs on a worker thread and reports progress through
an `emit` callback, which is what keeps the UI responsive and lets prose stream
in token by token. The original design ran a fresh asyncio loop inside the
pywebview bridge on every action, which blocks the UI thread for the full
duration of two chained API calls — a dead window for the length of a turn,
with no streaming possible.
"""

from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .gm import GameMaster
from .narrator import Narrator
from .presets import PresetManager
from .providers import ProviderError, build
from .state import StateManager

Emit = Callable[[dict], None]


def _second_person_slips(prose: str) -> int:
    """Count second-person pronouns in narration, ignoring quoted dialogue.

    The convention bans them in the narrating voice only — characters address
    the protagonist normally — so speech has to come out before counting or
    every conversation reads as a violation.
    """
    import re

    narration = re.sub(r'"[^"]*"', "", prose)
    narration = re.sub(r"[“”][^“”]*[“”]", "", narration)
    return len(re.findall(r"\b(you|your|yours|yourself)\b", narration, re.I))


@dataclass
class _LastTurn:
    """What a swipe needs to re-tell the current moment.

    The packet is kept verbatim on purpose. Re-running the GM would decide the
    turn again — different events, different state — and that is a different
    feature. Holding the briefing fixed is what makes a swipe a swipe.
    """

    player_input: str
    packet: dict
    feedback: list[str]
    swipes: list[str] = field(default_factory=list)
    index: int = 0


def _mood_key(raw) -> str:
    """Reduce a portrait_state to something usable as a filename.

    The schema asks for a short key like 'cowering', and models will sometimes
    hand back a paragraph of stage direction instead. Taking the first word
    means a verbose answer still resolves to the right portrait rather than
    silently falling through to no image at all.
    """
    if not isinstance(raw, str) or not raw.strip():
        return "default"
    first = raw.strip().split()[0]
    cleaned = "".join(c for c in first.lower() if c.isalnum() or c == "_")
    return cleaned or "default"


class Wall:
    def __init__(self, config: dict, root: Path):
        self.root = Path(root)
        self.config = config
        self.data_dir = self.root / "data"

        # Saves live outside the project tree by default — see
        # state.default_saves_dir() for why. Blank or absent means the default.
        self.state = StateManager(self.data_dir, config.get("saves_dir") or None)
        self.presets = PresetManager(self.data_dir / "presets")
        self.dev_mode = bool(config.get("dev_mode"))

        # Pick the story back up. An autosave nobody loads protects nothing, so
        # resuming is the default and starting over is the explicit act: delete
        # the slot, or /load another one. resumed_from feeds the banner, because
        # silently continuing someone else's session would be its own surprise.
        # Swipes belong to the moment you are in, so they live in memory and
        # start empty on launch — a resumed session has a transcript, not a set
        # of alternates for a turn taken yesterday.
        self.last_turn: _LastTurn | None = None

        self.resumed_from: str | None = None
        if (self.state.saves_dir / "_autosave.json").exists():
            try:
                self.state.load("_autosave")
                self.resumed_from = f"turn {self.state.turn_count}"
            except (OSError, ValueError) as exc:
                # A corrupt autosave must not block launch — say so and start fresh.
                self.resumed_from = f"autosave unreadable ({type(exc).__name__}), starting fresh"

        gm_block = dict(config.get("gm") or {})
        nar_block = dict(config.get("narrator") or {})

        self.gm = GameMaster(
            build(gm_block, role="GM"),
            max_tokens=int(gm_block.get("max_tokens") or 4000),
            dev_mode=self.dev_mode,
            max_scene_cards=int(gm_block.get("max_scene_cards") or 3),
        )
        self.narrator = Narrator(
            build(nar_block, role="narrator"),
            max_tokens=int(nar_block.get("max_tokens") or 4000),
            history_turns=int(config.get("history_turns") or 20),
        )

        self.feedback: list[str] = []
        self.last_input: str | None = None
        self.busy = False

    # ── introspection ──

    def banner(self) -> str:
        g, n = self.gm.provider, self.narrator.provider
        lines = [
            f"GM       {g.name} / {g.model}",
            f"         {g.caps.describe()}",
            f"NARRATOR {n.name} / {n.model}",
            f"         {n.caps.describe()}",
            f"SAVES    {self.state.saves_dir}",
        ]
        if self.resumed_from:
            lines.append(f"RESUMED  {self.resumed_from}")
        return "\n".join(lines)

    def warnings(self) -> list[str]:
        """Things worth telling the player before they start."""
        out = []
        if not self.gm.provider.caps.schema_forcing:
            out.append(
                "GM has no schema forcing on this backend — briefing packets will be "
                "validated and repaired if malformed. Watch for repair warnings."
            )
        if self.gm.provider.caps.caching == "none":
            out.append(
                "GM backend does not cache — the secret vault is re-sent every turn. "
                "Fine locally; expensive on a paid API."
            )
        if not self.state.vault:
            out.append("data/vault.json is empty — the GM has no secrets to gate.")
        if not self.state.known_npcs():
            out.append("no character cards found under data/characters/.")
        return out

    # ── the turn ──

    def run_turn(self, player_input: str, emit: Emit) -> None:
        if self.busy:
            emit({"type": "system", "text": "still working on the last turn."})
            return
        self.busy = True
        started = time.time()
        try:
            self._turn(player_input, emit)
        except ProviderError as exc:
            emit({"type": "error", "text": str(exc)})
        except Exception as exc:  # noqa: BLE001 - surface anything to the UI
            emit({"type": "error", "text": f"{type(exc).__name__}: {exc}"})
            if self.dev_mode:
                emit({"type": "debug", "text": traceback.format_exc()})
        finally:
            self.busy = False
            # In the finally, not after a clean _turn: a turn that produced
            # prose and then failed still advanced the state, and that progress
            # is worth keeping. If it fails, SAY SO in the window — a save that
            # silently stops working is how a session gets lost twice.
            saved = self.state.autosave()
            if saved is None:
                emit({"type": "error", "text": "autosave failed — this turn is not on disk."})
            elif self.dev_mode:
                emit({"type": "debug", "text": f"autosaved → {saved}"})
            emit({"type": "done", "elapsed": round(time.time() - started, 1)})

    def _turn(self, player_input: str, emit: Emit) -> None:
        self.last_input = player_input
        feedback = list(self.feedback)
        self.feedback.clear()

        # ── 1. GM adjudicates behind the Wall ──
        emit({"type": "status", "text": "the valley considers"})
        packet = self.gm.evaluate(self.state, player_input, feedback)
        if self.dev_mode:
            self._log_packet(packet)
            emit({"type": "briefing", "packet": packet})
        emit({"type": "usage", "role": "gm", "text": self.gm.provider.last_usage.line()})

        scene = packet.get("scene_context") or {}
        npcs = scene.get("npcs_present") or []

        # ── 2. Apply what the GM decided ──
        applied = self.state.apply_updates(packet.get("state_updates") or [])
        if applied and self.dev_mode:
            emit({"type": "debug", "text": "state:\n" + "\n".join(applied)})

        for entry in packet.get("information_release", {}).get("reveal_this_turn") or []:
            if entry not in self.state.revelation_log:
                self.state.revelation_log.append(entry)

        unlock = (packet.get("information_release") or {}).get("discovery_unlock")
        if unlock and unlock not in self.state.discovered:
            self.state.discovered.append(unlock)
            emit({"type": "discovery", "text": unlock})

        for ev in packet.get("offscreen_events") or []:
            self.state.offscreen.append(ev)

        # HUD and portraits land before the prose so the panels update while
        # the narrator is still writing.
        if packet.get("hud"):
            emit({"type": "hud", "hud": packet["hud"]})
        emit({"type": "portraits", "portraits": self._portraits(packet, npcs)})

        # ── 3. Narrator writes, in front of the Wall ──
        emit({"type": "status", "text": "…"})
        emit({"type": "prose_start"})
        prose = self._narrate(packet, player_input, feedback, emit)
        emit({"type": "prose_end"})

        # ── 4. Commit the turn ──
        self.state.chat_history.append({"role": "user", "content": player_input})
        self.state.chat_history.append({"role": "assistant", "content": prose})
        self.state.current_npcs = npcs
        self.state.turn_count += 1

        fragment = (packet.get("information_release") or {}).get("fragment_trigger")
        if fragment:
            emit({"type": "fragment", "text": fragment})

        # Everything a re-roll needs, and nothing else. Held in memory only: a
        # swipe is a "give me that again" about the moment you are in.
        self.last_turn = _LastTurn(player_input, packet, feedback, [prose])

    # ── swipes ──

    def run_swipe(self, direction: int, emit: Emit) -> None:
        """Re-roll the narration, or step between takes already generated.

        Prose only. The GM's briefing is reused exactly as it was, so the same
        things happened — they are just told differently. Nothing re-applies:
        no second helping of state updates, no re-logged discovery, no second
        turn on the clock. Only the words change.

        Direction +1 past the newest take generates a new one, which is how a
        swipe reads in every other client. -1 walks back through takes already
        paid for, and costs nothing.
        """
        if self.busy:
            emit({"type": "system", "text": "still working on the last turn."})
            emit({"type": "done", "elapsed": 0})
            return

        lt = self.last_turn
        if lt is None:
            emit({"type": "system", "text": "nothing to swipe yet — take a turn first."})
            emit({"type": "done", "elapsed": 0})
            return

        target = lt.index + direction
        if 0 <= target < len(lt.swipes):
            lt.index = target
            self._commit_swipe(lt, emit, regenerated=False)
            return
        if direction < 0:
            emit({"type": "system", "text": "that's the first take."})
            emit({"type": "done", "elapsed": 0})
            return

        self.busy = True
        started = time.time()
        try:
            emit({"type": "swipe_begin"})
            prose = self._narrate(lt.packet, lt.player_input, lt.feedback, emit, held_back=1)
            lt.swipes.append(prose)
            lt.index = len(lt.swipes) - 1
            self._commit_swipe(lt, emit, regenerated=True, elapsed=time.time() - started)
        except ProviderError as exc:
            emit({"type": "error", "text": str(exc)})
            self._show_swipe(lt, emit)  # put the take that still exists back on screen
            emit({"type": "done", "elapsed": 0})
        except Exception as exc:  # noqa: BLE001
            emit({"type": "error", "text": f"{type(exc).__name__}: {exc}"})
            if self.dev_mode:
                emit({"type": "debug", "text": traceback.format_exc()})
            self._show_swipe(lt, emit)
            emit({"type": "done", "elapsed": 0})
        finally:
            self.busy = False

    def _commit_swipe(self, lt: "_LastTurn", emit: Emit, regenerated: bool,
                      elapsed: float = 0.0) -> None:
        """Point the transcript at the selected take and persist it.

        The chat history is what the narrator reads next turn and what the save
        holds, so the selected swipe has to replace the assistant message rather
        than sit beside it. Otherwise the story continues from a take you
        swiped away from.
        """
        chosen = lt.swipes[lt.index]
        for msg in reversed(self.state.chat_history):
            if msg.get("role") == "assistant":
                msg["content"] = chosen
                break
        if not regenerated:
            self._show_swipe(lt, emit)
        else:
            emit({"type": "swipe_info", "index": lt.index, "total": len(lt.swipes)})
        saved = self.state.autosave()
        if saved is None:
            emit({"type": "error", "text": "autosave failed — this swipe is not on disk."})
        emit({"type": "done", "elapsed": round(elapsed, 1)})

    def _show_swipe(self, lt: "_LastTurn", emit: Emit) -> None:
        emit({
            "type": "swipe_set",
            "text": lt.swipes[lt.index],
            "index": lt.index,
            "total": len(lt.swipes),
        })

    # ── helpers ──

    def _narrate(self, packet: dict, player_input: str, feedback: list[str],
                 emit: Emit, held_back: int = 0) -> str:
        """Stream one take of narration. The only place prose is generated.

        held_back exists for swipes. The narrator reads state.chat_history for
        context, and by the time a swipe runs, this turn's own exchange is
        already in there — so a re-roll would be shown its own previous take as
        history and asked to continue from it. Lifting that exchange out for the
        duration puts the model in exactly the position it was in the first
        time.
        """
        stash: list[dict] = []
        if held_back:
            stash = self.state.chat_history[-held_back * 2:]
            del self.state.chat_history[-held_back * 2:]
        try:
            style = self.presets.style
            params = self.presets.gen_params(self.narrator.max_tokens)
            chunks: list[str] = []
            for piece in self.narrator.stream(
                self.state, packet, player_input, style=style, params=params, feedback=feedback
            ):
                chunks.append(piece)
                emit({"type": "delta", "text": piece})
        finally:
            self.state.chat_history.extend(stash)

        prose = "".join(chunks)
        for banned in self.presets.banned_strings():
            if banned and banned in prose:
                prose = prose.replace(banned, "")

        # Voice drift check. The prose convention forbids second person in
        # narration but not in dialogue, so quoted speech is excluded before
        # counting. Reported, never rewritten — silently editing a model's prose
        # would hide the problem and read worse than the slip does.
        if self.dev_mode:
            slips = _second_person_slips(prose)
            if slips:
                emit({
                    "type": "debug",
                    "text": f"voice drift: {slips} second-person use(s) in narration "
                            f"(dialogue excluded). swipe, or raise effort.",
                })

        emit({"type": "usage", "role": "narrator", "text": self.narrator.provider.last_usage.line()})
        return prose

    def _portraits(self, packet: dict, npcs: list[str]) -> list[dict]:
        """Resolve portrait paths, falling back to default then to nothing.

        The UI hides any image that fails to load, so a missing art file
        degrades to a name and a mood label rather than a broken layout.
        """
        out = []
        states = {
            d.get("npc"): d.get("portrait_state", "default")
            for d in packet.get("npc_direction") or []
        }
        for npc in npcs:
            mood = _mood_key(states.get(npc))
            folder = self.data_dir / "characters" / npc / "portraits"
            path = None
            for candidate in (f"{mood}.webp", f"{mood}.png", "default.webp", "default.png"):
                if (folder / candidate).exists():
                    path = f"data/characters/{npc}/portraits/{candidate}"
                    break
            out.append({"npc": npc, "mood": mood, "src": path})
        return out

    def _log_packet(self, packet: dict) -> None:
        path = self.state.saves_dir / "_briefings.jsonl"
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps({"turn": self.state.turn_count + 1, "packet": packet}) + "\n"
                )
        except OSError:
            pass  # logging is a convenience, never a reason to lose a turn
