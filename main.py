#!/usr/bin/env python3
"""The Valley — entry point.

The threading model is the important part. pywebview's JS bridge is
synchronous: whatever a bridge method does, the UI thread waits for. A turn is
two chained model calls, so doing the work inline freezes the window for the
whole turn and makes streaming impossible.

So the bridge does almost nothing. submit() hands the input to a worker thread
and returns immediately; the worker pushes events back into the page with
evaluate_js as they happen. The window stays live, prose streams in, and
Ctrl-C still works.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
from pathlib import Path

import webview
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from engine.commands import CommandRouter  # noqa: E402
from engine.providers import ProviderError  # noqa: E402
from engine.state import default_saves_dir  # noqa: E402
from engine.wall import Wall  # noqa: E402


def open_log() -> Path:
    """Send diagnostics to a file, whatever launched us.

    Two reasons this lives in Python rather than the launcher:

    Under pythonw.exe there is no console at all, so sys.stdout can be None and
    a bare print() raises. And `start "" prog > file` in a .cmd redirects the
    start command's own output, not the child's — it looks like logging is on
    and produces an empty file, which is worse than no logging.

    So the app opens its own log and tees to the console when one exists. Every
    [bridge] line survives a double-click launch. Never in the project folder:
    the repo is inside OneDrive.
    """
    log_dir = default_saves_dir().parent
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "launch.log"
    handle = path.open("a", encoding="utf-8", errors="replace")
    handle.write(f"\n{'=' * 60}\nlaunch\n{'=' * 60}\n")

    class Tee:
        def __init__(self, console):
            self._console = console

        def write(self, text: str) -> int:
            handle.write(text)
            handle.flush()  # unbuffered: a crash must not eat the last line
            if self._console is not None:
                try:
                    self._console.write(text)
                    self._console.flush()
                except Exception:  # noqa: BLE001 - a dead console must not kill logging
                    self._console = None
            return len(text)

        def flush(self) -> None:
            handle.flush()

        def isatty(self) -> bool:
            return False

    sys.stdout = Tee(sys.stdout)
    sys.stderr = Tee(sys.stderr)
    return path


def load_config() -> dict:
    for name in ("config.yaml", "config.yml"):
        path = ROOT / name
        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    example = ROOT / "config.example.yaml"
    raise SystemExit(
        "No config.yaml found.\n\n"
        f"  copy {example.name} to config.yaml and set your provider, model, and key.\n"
        "  The default block uses OpenRouter; there are Claude-direct, fully local,\n"
        "  and mixed setups commented at the bottom of the file."
    )


# The window is held at module level, NOT on the API object.
#
# pywebview introspects the js_api object's graph to decide what to expose to
# JavaScript. If the API holds a reference to the window, that walk reaches
# window.native -> the WinForms Form -> .Bounds -> a .NET Rectangle, and then
# pywebview's own `if obj in exposed_objects` comparison raises:
#
#   TypeError: No method matches given arguments for Rectangle.op_Equality
#
# On pywebview 6 the same doorway produced a wall of recursion errors during
# injection and left window.pywebview.api empty, which looked exactly like a
# frozen UI. Keeping the window out of reach of that walk is the fix.
_WINDOW: "webview.Window | None" = None


class GameAPI:
    """The JS bridge. Every method returns fast.

    Anything public on this class is exposed to JavaScript, so keep the surface
    to the three calls the page actually makes.
    """

    def __init__(self, wall: Wall):
        self._wall = wall
        self._commands = CommandRouter(wall)
        self._outbox: queue.Queue[dict] = queue.Queue()
        self._bridge_ok = False
        self._bridge_failures = 0

    def _drain(self) -> None:
        """Single writer into the page.

        Serialising events through one thread means evaluate_js is never
        called concurrently, which some webview backends do not tolerate.

        Failures are LOGGED, not swallowed. An earlier version caught and
        discarded them, which turned any evaluate_js problem into a perfect
        imitation of a hung application: the turn ran, the events were dropped,
        the input never re-enabled, and nothing anywhere said why.
        """
        while True:
            event = self._outbox.get()
            if _WINDOW is None:
                print("[bridge] no window yet, dropped:", event.get("type"))
                continue
            try:
                _WINDOW.evaluate_js(f"window.valley.recv({json.dumps(event)})")
                self._bridge_ok = True
            except Exception as exc:  # noqa: BLE001
                self._bridge_failures += 1
                if self._bridge_failures <= 5:
                    print(
                        f"[bridge] evaluate_js FAILED on {event.get('type')!r}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    if self._bridge_failures == 5:
                        print("[bridge] (further failures suppressed)")

    def _emit(self, event: dict) -> None:
        self._outbox.put(event)

    # ── called from JS ──

    def boot(self) -> str:
        print("[bridge] boot() called from JS — the JS->Python direction works")
        # Prove the Python->JS direction too, before a turn depends on it.
        self._emit({"type": "system", "text": "bridge online."})
        threading.Timer(1.0, self._report_bridge).start()
        warnings = self._wall.warnings()
        return json.dumps(
            {
                "banner": self._wall.banner(),
                "warnings": warnings,
                "preset": self._wall.presets.active,
                "dev_mode": self._wall.dev_mode,
                "turn": self._wall.state.turn_count,
                "opening": self._wall.state.world_card.get("opening_text", ""),
                "history": self._wall.state.chat_history[-6:],
            }
        )

    def _report_bridge(self) -> None:
        if self._bridge_ok:
            print("[bridge] Python->JS confirmed working")
        else:
            print(
                "[bridge] WARNING: no successful evaluate_js yet. The UI will "
                "look frozen because events cannot reach the page."
            )

    def submit(self, text: str) -> str:
        text = (text or "").strip()
        print(f"[bridge] submit({text[:60]!r})")
        if not text:
            return json.dumps({"ok": False})

        # /swipe is a model call, not an instant command, so it cannot go
        # through the router — that path returns a string synchronously.
        low = text.lower()
        if low.startswith("/swipe"):
            back = any(w in low for w in ("back", "prev", "left", "<"))
            return self.swipe(-1 if back else 1)

        if self._commands.is_command(text):
            handled, payload = self._commands.execute(text)
            if handled:
                self._emit({"type": "system", "text": payload})
                self._emit({"type": "done", "elapsed": 0})
                self._emit({"type": "meta", "preset": self._wall.presets.active})
                return json.dumps({"ok": True})
            # /retry and friends fall through with the action to replay.
            text = payload

        threading.Thread(
            target=self._wall.run_turn,
            args=(text, self._emit),
            daemon=True,
            name="valley-turn",
        ).start()
        return json.dumps({"ok": True, "echo": text})

    def swipe(self, direction: int) -> str:
        """Re-roll the last narration, or step between takes already generated.

        Same shape as submit(): hand off to a worker and return at once, because
        the JS bridge is synchronous and a swipe is a model call.
        """
        print(f"[bridge] swipe({direction})")
        threading.Thread(
            target=self._wall.run_swipe,
            args=(int(direction), self._emit),
            daemon=True,
            name="valley-swipe",
        ).start()
        return json.dumps({"ok": True})

    def quicksave(self) -> str:
        path = self._wall.state.save("quicksave")
        return json.dumps({"ok": True, "text": f"saved → {path.name}"})


def start_pump(api: GameAPI, window: "webview.Window") -> None:
    """Record the window and start the single writer into the page.

    A module function rather than a GameAPI method: anything public on the API
    class gets exposed to JavaScript, and a method taking a Window argument is
    both useless from JS and a route back into the GUI object graph.
    """
    global _WINDOW
    _WINDOW = window
    threading.Thread(target=api._drain, daemon=True, name="valley-pump").start()


def main() -> None:
    log_path = open_log()
    print(f"log      {log_path}")
    config = load_config()
    try:
        wall = Wall(config, ROOT)
    except ProviderError as exc:
        raise SystemExit(f"\nconfiguration problem:\n  {exc}\n")

    print(wall.banner())
    for warning in wall.warnings():
        print(f"  ! {warning}")

    api = GameAPI(wall)
    window = webview.create_window(
        "The Valley",
        url=str(ROOT / "ui" / "index.html"),
        js_api=api,
        width=1200,
        height=820,
        min_size=(900, 600),
        background_color="#0a0a0f",
    )
    start_pump(api, window)
    webview.start(debug=bool(config.get("dev_mode")))


if __name__ == "__main__":
    main()
