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
from engine.wall import Wall  # noqa: E402


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


class GameAPI:
    """The JS bridge. Every method returns fast."""

    def __init__(self, wall: Wall):
        self.wall = wall
        self.commands = CommandRouter(wall)
        self.window: webview.Window | None = None
        self._outbox: queue.Queue[dict] = queue.Queue()
        self._pump: threading.Thread | None = None

    # ── plumbing ──

    def attach(self, window: webview.Window) -> None:
        self.window = window
        self._pump = threading.Thread(target=self._drain, daemon=True, name="valley-pump")
        self._pump.start()

    def _drain(self) -> None:
        """Single writer into the page.

        Serialising events through one thread means evaluate_js is never
        called concurrently, which some webview backends do not tolerate.
        """
        while True:
            event = self._outbox.get()
            if self.window is None:
                continue
            try:
                self.window.evaluate_js(f"window.valley.recv({json.dumps(event)})")
            except Exception:
                # The window is gone or mid-teardown. Dropping a UI event is
                # never worth killing the pump over.
                pass

    def emit(self, event: dict) -> None:
        self._outbox.put(event)

    # ── called from JS ──

    def boot(self) -> str:
        warnings = self.wall.warnings()
        return json.dumps(
            {
                "banner": self.wall.banner(),
                "warnings": warnings,
                "preset": self.wall.presets.active,
                "dev_mode": self.wall.dev_mode,
                "turn": self.wall.state.turn_count,
                "opening": self.wall.state.world_card.get("opening_text", ""),
                "history": self.wall.state.chat_history[-6:],
            }
        )

    def submit(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return json.dumps({"ok": False})

        if self.commands.is_command(text):
            handled, payload = self.commands.execute(text)
            if handled:
                self.emit({"type": "system", "text": payload})
                self.emit({"type": "done", "elapsed": 0})
                self.emit({"type": "meta", "preset": self.wall.presets.active})
                return json.dumps({"ok": True})
            # /retry and friends fall through with the action to replay.
            text = payload

        threading.Thread(
            target=self.wall.run_turn,
            args=(text, self.emit),
            daemon=True,
            name="valley-turn",
        ).start()
        return json.dumps({"ok": True, "echo": text})

    def quicksave(self) -> str:
        path = self.wall.state.save("quicksave")
        return json.dumps({"ok": True, "text": f"saved → {path.name}"})


def main() -> None:
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
    api.attach(window)
    webview.start(debug=bool(config.get("dev_mode")))


if __name__ == "__main__":
    main()
