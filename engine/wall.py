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
from pathlib import Path
from typing import Callable

from .gm import GameMaster
from .narrator import Narrator
from .presets import PresetManager
from .providers import ProviderError, build
from .state import StateManager

Emit = Callable[[dict], None]


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

        self.state = StateManager(self.data_dir)
        self.presets = PresetManager(self.data_dir / "presets")
        self.dev_mode = bool(config.get("dev_mode"))

        gm_block = dict(config.get("gm") or {})
        nar_block = dict(config.get("narrator") or {})

        self.gm = GameMaster(
            build(gm_block, role="GM"),
            max_tokens=int(gm_block.get("max_tokens") or 4000),
            dev_mode=self.dev_mode,
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
        return (
            f"GM       {g.name} / {g.model}\n"
            f"         {g.caps.describe()}\n"
            f"NARRATOR {n.name} / {n.model}\n"
            f"         {n.caps.describe()}"
        )

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

        style = self.presets.style
        params = self.presets.gen_params(self.narrator.max_tokens)
        chunks: list[str] = []
        for piece in self.narrator.stream(
            self.state, packet, player_input, style=style, params=params, feedback=feedback
        ):
            chunks.append(piece)
            emit({"type": "delta", "text": piece})

        prose = "".join(chunks)
        for banned in self.presets.banned_strings():
            if banned and banned in prose:
                prose = prose.replace(banned, "")

        emit({"type": "prose_end"})
        emit({"type": "usage", "role": "narrator", "text": self.narrator.provider.last_usage.line()})

        # ── 4. Commit the turn ──
        self.state.chat_history.append({"role": "user", "content": player_input})
        self.state.chat_history.append({"role": "assistant", "content": prose})
        self.state.current_npcs = npcs
        self.state.turn_count += 1

        fragment = (packet.get("information_release") or {}).get("fragment_trigger")
        if fragment:
            emit({"type": "fragment", "text": fragment})

    # ── helpers ──

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
