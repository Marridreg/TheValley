"""State, saves, and the public/private card split.

get_narrator_card() is where the Wall physically exists. Everything else in
this file is bookkeeping.
"""

from __future__ import annotations

import json
from pathlib import Path


class StateManager:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.chars_dir = self.data_dir / "characters"
        self.saves_dir = self.data_dir / "saves"
        self.saves_dir.mkdir(parents=True, exist_ok=True)

        # Narrator-visible. Public geography, culture, tone. No secrets.
        self.world_card = self._load("world.json")

        # Live mechanical state. The GM sees all of it; the narrator sees none
        # of it directly — only the slice the briefing's hud and scene_context
        # expose.
        self.pc = self._load("pc.json")
        self.world = self._load("world_state.json")

        # GM only. If any of these ever reaches the narrator, the Wall is down.
        self.vault = self._load("vault.json")
        self.fragments = self._load("fragment_map.json")

        # Readable things placed in the world — letters, ledgers, diaries,
        # case notes. Each declares which card sections reading it releases,
        # which makes "I found it written down" a real route to a secret
        # rather than something the GM has to improvise.
        self.documents = self._load_documents()

        self.chat_history: list[dict] = []
        self.revelation_log: list[str] = []
        self.discovered: list[str] = []
        self.offscreen: list[dict] = []
        self.authors_note = ""
        self.turn_count = 0

        self._card_cache: dict[str, dict] = {}

    # ── loading ──

    def _load(self, filename: str) -> dict:
        path = self.data_dir / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _load_documents(self) -> list[dict]:
        """Every readable in-world text, from data/documents/*.json."""
        d = self.data_dir / "documents"
        if not d.is_dir():
            return []
        out = []
        for path in sorted(d.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                doc.setdefault("id", path.stem)
                out.append(doc)
            except json.JSONDecodeError as exc:
                print(f"[documents] skipping {path.name}: {exc}")
        return out

    def _card(self, npc_id: str) -> dict:
        """Both halves of a character card, cached per process."""
        if npc_id in self._card_cache:
            return self._card_cache[npc_id]
        d = self.chars_dir / npc_id
        card = {"public": {}, "private": {}}
        for half in ("public", "private"):
            p = d / f"{half}.json"
            if p.exists():
                card[half] = json.loads(p.read_text(encoding="utf-8"))
        self._card_cache[npc_id] = card
        return card

    def known_npcs(self) -> list[str]:
        if not self.chars_dir.exists():
            return []
        return sorted(p.name for p in self.chars_dir.iterdir() if p.is_dir())

    # ── THE WALL ──

    def get_narrator_card(self, npc_id: str) -> dict:
        """The narrator's version of an NPC: the public card, plus whichever
        private sections have been unlocked, in whichever *version* the route
        that unlocked them yields.

        Unlock keys live in the revelation log:

            alcina.miranda_resentment          -> the truth
            alcina.miranda_resentment#rumor    -> the distorted version

        Truth wins if both are present, because learning something properly
        should supersede having heard a rumour about it.

        Why two versions: information about a person is learnable by many
        routes — from them, from someone who knows them, from a letter, from
        their possessions — and those routes are not equally reliable. A maid's
        gossip about why Lady Dimitrescu breaks things after Miranda visits is
        *directionally* true and wrong in the specifics. Giving the narrator
        the rumour means the prose can carry a believable falsehood the player
        may later correct, which is how learning about people actually works.

        Note what is stripped: `learnable_from` never crosses the Wall. Those
        routes are the GM's routing table — telling the narrator "this could
        be learned from Bela" hands it the secret's existence and its shape.
        Only the content of unlocked sections is passed through.
        """
        card = self._card(npc_id)
        # Underscore keys are authoring notes to whoever edits the file, not
        # character content. They cost tokens and tell the narrator nothing.
        out = {k: v for k, v in card["public"].items() if not k.startswith("_")}
        sections = self._private_sections(npc_id)

        prefix = f"{npc_id}."
        wanted: dict[str, str] = {}  # section -> "truth" | "rumor"
        for entry in self.revelation_log:
            if not entry.startswith(prefix):
                continue
            key = entry[len(prefix) :]
            variant = "truth"
            if "#" in key:
                key, _, variant = key.partition("#")
                variant = variant or "truth"
            if key in sections:
                # Truth is sticky: a later rumour never downgrades it.
                if wanted.get(key) != "truth":
                    wanted[key] = variant

        for section, variant in wanted.items():
            value = self._section_content(sections[section], variant)
            if value is not None:
                out[section] = value
        return out

    def get_gm_card(self, npc_id: str) -> dict:
        """Everything, including every discovery route. GM side only."""
        card = self._card(npc_id)
        return {**card["public"], **card["private"]}

    # ── private-section plumbing ──

    def _private_sections(self, npc_id: str) -> dict:
        """The section map from a private card, tolerating both layouts.

        v2 nests content under a `sections` key so the file can also carry
        metadata; v1 (and hand-written cards) put sections at the top level.
        Keys starting with `_` are notes, never content.
        """
        private = self._card(npc_id)["private"]
        if isinstance(private.get("sections"), dict):
            return private["sections"]
        return {k: v for k, v in private.items() if not k.startswith("_")}

    @staticmethod
    def _section_content(section, variant: str):
        """Pull the requested variant out of a section.

        A section is either a bare value (string/list — truth only, which is
        what a simple hand-written card looks like) or a dict carrying
        `truth`/`rumor` plus GM-only routing metadata.
        """
        if not isinstance(section, dict):
            return section
        if variant == "rumor":
            # FAIL CLOSED. If a route promised a distorted version and none was
            # authored, release nothing — do NOT fall back to the truth.
            #
            # Falling back was the original behaviour and it was a silent Wall
            # breach: a player who merely overheard gossip would have had the
            # real secret handed to the narrator, with no error anywhere. A
            # missing rumour is an authoring gap, and an authoring gap must
            # cost the player a dead end rather than costing the game its
            # central guarantee. tools/validate_cards.py fails on exactly this
            # so the gap is caught before play, not during it.
            return section.get("rumor")
        return section.get("truth") or section.get("rumor")

    def discovery_routes(self, npc_id: str) -> list[dict]:
        """Every way this character's secrets can be learned, flattened.

        GM-side only — this is what lets it recognise that rifling a desk or
        pressing a servant is a legitimate route to a secret, not just
        befriending its owner.
        """
        routes = []
        for name, section in self._private_sections(npc_id).items():
            if not isinstance(section, dict):
                continue
            for route in section.get("learnable_from") or []:
                routes.append({"section": f"{npc_id}.{name}", **route})
        return routes

    def locked_sections(self, npc_id: str) -> list[str]:
        """Section names not yet released, for the GM's awareness."""
        card = self.get_narrator_card(npc_id)
        return [s for s in self._private_sections(npc_id) if s not in card]

    # ── mutation ──

    def apply_updates(self, updates: list[dict]) -> list[str]:
        """Apply the briefing's state_updates. Returns a human-readable log.

        Unknown roots and unparseable paths are skipped and reported rather
        than raising — a GM typo should cost one stat change, not the turn.
        """
        applied: list[str] = []
        roots = {"pc": self.pc, "world": self.world}

        for u in updates or []:
            path = (u.get("path") or "").strip()
            if not path:
                continue
            parts = path.split(".")
            root = roots.get(parts[0])
            if root is None or len(parts) < 2:
                applied.append(f"  ! skipped unknown path: {path}")
                continue

            obj = root
            for key in parts[1:-1]:
                nxt = obj.get(key)
                if not isinstance(nxt, dict):
                    nxt = {}
                    obj[key] = nxt
                obj = nxt

            leaf = parts[-1]
            value = u.get("number") if u.get("number") is not None else u.get("text")
            if value is None:
                continue

            before = obj.get(leaf)

            # Structure guard. A GM will sometimes target a container rather
            # than its leaf — `pc.vitals.stamina` instead of
            # `pc.vitals.stamina.current`. Writing a scalar there replaces the
            # whole {current, max} dict with a float and silently destroys the
            # schema for the rest of the session. Descend to the obvious leaf
            # instead, and say so in the log.
            if isinstance(before, dict) and not isinstance(value, dict):
                for candidate in ("current", "level", "value"):
                    if candidate in before:
                        obj = before
                        leaf = candidate
                        before = obj.get(leaf)
                        path = f"{path}.{candidate}"
                        applied.append(f"  ~ corrected path to {path} (target was a container)")
                        break
                else:
                    applied.append(
                        f"  ! skipped {path}: would overwrite a structure with {value!r}"
                    )
                    continue

            if u.get("op") == "add" and isinstance(value, (int, float)):
                base = before if isinstance(before, (int, float)) else 0
                obj[leaf] = round(base + value, 4)
            else:
                obj[leaf] = value

            applied.append(f"  {path}: {before!r} -> {obj[leaf]!r}  ({u.get('reason', '')})")

        return applied

    # ── saves ──

    def save(self, slot: str) -> Path:
        payload = {
            "pc": self.pc,
            "world": self.world,
            "vault": self.vault,
            "fragments": self.fragments,
            "chat_history": self.chat_history,
            "revelation_log": self.revelation_log,
            "discovered": self.discovered,
            "offscreen": self.offscreen,
            "authors_note": self.authors_note,
            "turn_count": self.turn_count,
        }
        path = self.saves_dir / f"{_safe_slot(slot)}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load(self, slot: str) -> None:
        path = self.saves_dir / f"{_safe_slot(slot)}.json"
        if not path.exists():
            raise FileNotFoundError(f"no save in slot '{slot}'")
        s = json.loads(path.read_text(encoding="utf-8"))
        self.pc = s.get("pc", self.pc)
        self.world = s.get("world", self.world)
        self.vault = s.get("vault", self.vault)
        self.fragments = s.get("fragments", self.fragments)
        self.chat_history = s.get("chat_history", [])
        self.revelation_log = s.get("revelation_log", [])
        self.discovered = s.get("discovered", [])
        self.offscreen = s.get("offscreen", [])
        self.authors_note = s.get("authors_note", "")
        self.turn_count = s.get("turn_count", 0)

    def list_saves(self) -> list[str]:
        return sorted(
            p.stem for p in self.saves_dir.glob("*.json") if not p.stem.startswith("_")
        )

    # ── scene tracking ──

    @property
    def current_npcs(self) -> list[str]:
        return self.world.get("_scene_npcs", [])

    @current_npcs.setter
    def current_npcs(self, npcs: list[str]) -> None:
        self.world["_scene_npcs"] = list(npcs)


def _safe_slot(slot: str) -> str:
    keep = "-_"
    cleaned = "".join(c for c in slot if c.isalnum() or c in keep)
    return cleaned or "quicksave"
