"""Slash commands.

Meta-actions that control the engine rather than playing the game. Everything
here is instant and local except the ones that deliberately fall through to a
normal turn.

Returns (handled, text). handled=False means "this wasn't a command, play it
as an action".
"""

from __future__ import annotations

import json

HELP = """\
═══ COMMANDS ═══
  GAME     /save [slot]  /load [slot]  /saves  /preset [name]  /status
  INFO     /inventory  /journal  /providers  /where
  META     /note <text>  /feedback <text>  /retry  /undo  /help
  SWIPE    /swipe        re-tell the last turn (same events, new prose)
           /swipe back   step back through takes already written
           Ctrl+Right / Ctrl+Left do the same thing
  MODEL    /model gm <name>       switch the GM's model
           /model narrator <name> switch the narrator's model
  DEBUG    /state [pc|world]  /vault  /briefing  /reveal <key>

  Anything not starting with / is an action your character takes."""


class CommandRouter:
    def __init__(self, wall):
        self.wall = wall

    def is_command(self, text: str) -> bool:
        return text.strip().startswith("/")

    def execute(self, text: str) -> tuple[bool, str]:
        parts = text.strip().split()
        cmd, args = parts[0].lower(), parts[1:]
        handler = getattr(self, f"cmd_{cmd[1:]}", None)
        if handler is None:
            return True, f"unknown command {cmd} — try /help"
        try:
            return handler(args)
        except Exception as exc:  # noqa: BLE001
            return True, f"{cmd} failed: {type(exc).__name__}: {exc}"

    # ── game ──

    def cmd_save(self, args):
        slot = args[0] if args else "quicksave"
        path = self.wall.state.save(slot)
        return True, f"saved → {path.name}  (turn {self.wall.state.turn_count})"

    def cmd_load(self, args):
        slot = args[0] if args else "quicksave"
        self.wall.state.load(slot)
        return True, f"loaded {slot} — turn {self.wall.state.turn_count}. /where to reorient."

    def cmd_saves(self, args):
        slots = self.wall.state.list_saves()
        return True, "saves: " + (", ".join(slots) if slots else "(none)")

    def cmd_preset(self, args):
        pm = self.wall.presets
        if not args:
            lines = [
                f"  {'*' if active else ' '} {key:12} {desc}"
                for key, desc, active in pm.listing()
            ]
            return True, "presets:\n" + "\n".join(lines)
        if args[0] == "reload":
            return True, f"reloaded {pm.reload()} presets from disk"
        if pm.set_active(args[0]):
            p = pm.get()
            return True, f"preset → {p.get('name', args[0])} (effort {p.get('effort','-')})"
        return True, f"no preset '{args[0]}'"

    def cmd_status(self, args):
        pc = self.wall.state.pc
        v, s = pc.get("vitals", {}), pc.get("stats", {})

        def g(d, *keys, default="?"):
            cur = d
            for k in keys:
                if not isinstance(cur, dict):
                    return default
                cur = cur.get(k)
            return cur if cur is not None else default

        return True, (
            f"═══ {pc.get('name', 'the soldier')} ═══\n"
            f"  hp {g(v,'health','current')}   stamina {g(v,'stamina','current')}   "
            f"mold {g(v,'mold_exposure','level')}\n"
            f"  STR {s.get('strength','?')}  SPD {s.get('speed','?')}  "
            f"PER {s.get('perception','?')}\n"
            f"  WIL {s.get('willpower','?')}  CHA {s.get('charisma','?')}  "
            f"KNO {s.get('knowledge','?')}\n"
            f"  turn {self.wall.state.turn_count}"
        )

    def cmd_inventory(self, args):
        pc = self.wall.state.pc
        eq = pc.get("equipped", {})
        lines = [
            "═══ CARRYING ═══",
            f"  weapon: {eq.get('weapon', 'nothing')}",
            f"  armour: {eq.get('armor', 'nothing')}",
            "  ───",
        ]
        items = pc.get("inventory", [])
        lines += [
            f"  • {it.get('name', it) if isinstance(it, dict) else it}" for it in items
        ] or ["  (empty)"]
        return True, "\n".join(lines)

    def cmd_journal(self, args):
        st = self.wall.state
        lines = ["═══ JOURNAL ═══"]
        if st.discovered:
            lines += [f"  ★ {d}" for d in st.discovered]
        else:
            lines.append("  (nothing discovered yet)")
        prose = [r for r in st.revelation_log if "." not in r.split(" ")[0]]
        if prose:
            lines += ["  ───", "  known:"]
            lines += [f"    - {r}" for r in prose[-25:]]
        return True, "\n".join(lines)

    def cmd_where(self, args):
        st = self.wall.state
        npcs = ", ".join(st.current_npcs) if st.current_npcs else "no one"
        loc = st.pc.get("location", {})
        where = loc.get("current", "unknown") if isinstance(loc, dict) else loc
        return True, f"{where} — with {npcs} (turn {st.turn_count})"

    def cmd_providers(self, args):
        return True, self.wall.banner()

    def cmd_model(self, args):
        """Hot-swap a model without restarting.

        Only changes the model string on the existing provider, so it stays
        within the same backend — which is the useful case on OpenRouter, where
        trying a different narrator is a one-word change.
        """
        if len(args) < 2:
            return True, "usage: /model [gm|narrator] <model-name>"
        role, name = args[0].lower(), " ".join(args[1:])
        target = {"gm": self.wall.gm, "narrator": self.wall.narrator}.get(role)
        if target is None:
            return True, "first argument must be 'gm' or 'narrator'"
        old, target.provider.model = target.provider.model, name
        # Capabilities are model-derived, so re-detect if the backend supports it.
        if hasattr(target.provider, "_detect"):
            try:
                target.provider._caps = target.provider._detect(
                    {} if role != "gm" else {}
                )
            except TypeError:
                target.provider._caps = target.provider._detect()
        return True, (
            f"{role}: {old} → {name}\n  {target.provider.caps.describe()}\n"
            "  (config.yaml is unchanged — this lasts for this session)"
        )

    # ── meta ──

    def cmd_note(self, args):
        self.wall.state.authors_note = " ".join(args)
        return True, "author's note updated" if args else "author's note cleared"

    def cmd_feedback(self, args):
        if not args:
            return True, "usage: /feedback <what to do more or less of>"
        note = " ".join(args)
        self.wall.feedback.append(note)
        return True, f"queued for next turn: {note}"

    def cmd_retry(self, args):
        st = self.wall.state
        if len(st.chat_history) < 2:
            return True, "nothing to retry"
        st.chat_history.pop()
        last = st.chat_history.pop()
        st.turn_count = max(0, st.turn_count - 1)
        return False, last["content"]  # falls through to a fresh turn

    def cmd_undo(self, args):
        st = self.wall.state
        if len(st.chat_history) < 2:
            return True, "nothing to undo"
        st.chat_history.pop()
        st.chat_history.pop()
        st.turn_count = max(0, st.turn_count - 1)
        return True, (
            "last exchange removed from history.\n"
            "  note: state changes and revelations are NOT rolled back — "
            "/load a save for a clean rewind."
        )

    def cmd_help(self, args):
        return True, HELP

    # ── debug ──

    def cmd_state(self, args):
        st = self.wall.state
        target = args[0] if args else "pc"
        data = {"pc": st.pc, "world": st.world}.get(target)
        if data is None:
            return True, "usage: /state [pc|world]"
        return True, json.dumps(data, indent=2)[:4000]

    def cmd_vault(self, args):
        if not self.wall.dev_mode:
            return True, "dev_mode is off — /vault is disabled."
        return True, json.dumps(self.wall.state.vault, indent=2)[:4000]

    def cmd_briefing(self, args):
        packet = self.wall.gm.last_packet
        if not packet:
            return True, "no briefing yet"
        return True, json.dumps(packet, indent=2)[:6000]

    def cmd_reveal(self, args):
        """Force a card section open, for testing the trust gates."""
        if not self.wall.dev_mode:
            return True, "dev_mode is off — /reveal is disabled."
        if not args:
            return True, "usage: /reveal <npc>.<section>   e.g. /reveal moreau.drives"
        key = args[0]
        if key not in self.wall.state.revelation_log:
            self.wall.state.revelation_log.append(key)
        return True, f"released to narrator: {key}"
