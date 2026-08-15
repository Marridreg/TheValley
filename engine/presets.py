"""Presets — a voice, expressed as whatever the backend understands.

A preset carries three kinds of setting, and the provider layer emits only the
ones the target model accepts:

    style      prose instructions appended to the narrator's system prompt.
               Works on every backend, always. This is the part that actually
               does the work.
    effort     reasoning depth. Claude and the reasoning-model families take
               it; clamped to the nearest available level elsewhere; dropped
               on models without it.
    samplers   temperature, top_p, top_k, min_p, repetition_penalty. These are
               live on OpenRouter, OpenAI, and local models, and REJECTED
               outright by frontier Claude — so one preset file can target both
               without editing, because Provider.filter_params() strips what
               would 400.

That last point is why samplers are here at all. The original design assumed
SillyTavern-style sampler presets; on Claude those knobs are gone, but on the
OpenRouter and local backends they are exactly as useful as they ever were.
Carrying both and filtering per-model is the only way one preset works
everywhere.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .providers import GenParams

DEFAULTS: dict[str, dict] = {
    "balanced": {
        "name": "Balanced",
        "description": "Default. Clear, unhurried prose.",
        "effort": "medium",
        "max_tokens": 3000,
        "style": "",
        "temperature": 0.9,
        "top_p": 0.95,
        "repetition_penalty": 1.05,
    },
    "horror": {
        "name": "Horror",
        "description": "Tuned for dread — slower, more deliberate.",
        "effort": "high",
        "max_tokens": 3500,
        "style": (
            "Build dread through specificity and restraint. Name what the "
            "senses actually register — a sound's texture, a smell's source, "
            "the exact wrongness of a detail — and let the reader assemble the "
            "threat. Never state that something is terrifying; describe the "
            "thing and stop. Withhold the shape of a danger longer than is "
            "comfortable. Short sentences when something moves."
        ),
        "temperature": 0.85,
        "top_p": 0.92,
        "repetition_penalty": 1.1,
    },
    "intimate": {
        "name": "Intimate",
        "description": "Tuned for emotional and physical closeness.",
        "effort": "high",
        "max_tokens": 3500,
        "style": (
            "Slow the clock. Attention narrows to the person in front of the "
            "PC: what their face does before they speak, what their hands do "
            "while they talk, what they avoid saying. Physicality is specific "
            "and unhurried. Silence is dialogue. Let a scene turn on a single "
            "gesture rather than a declaration."
        ),
        "temperature": 0.95,
        "top_p": 0.96,
        "repetition_penalty": 1.05,
    },
    "combat": {
        "name": "Combat",
        "description": "Punchy, fast, decisive.",
        "effort": "low",
        "max_tokens": 1600,
        "style": (
            "Short paragraphs. Concrete physical cause and effect — what hit "
            "what, what gave way, where the PC's body is now. No interiority "
            "mid-exchange; the PC has no time to reflect. End on the state of "
            "the fight, not a summary of it."
        ),
        "temperature": 0.75,
        "top_p": 0.9,
        "repetition_penalty": 1.15,
    },
    "terse": {
        "name": "Terse",
        "description": "Zork-tight. For exploration and travel.",
        "effort": "low",
        "max_tokens": 1000,
        "style": (
            "Two or three sentences unless something is genuinely happening. "
            "Room, exits, anything that has changed since last look. No "
            "atmosphere for its own sake."
        ),
        "temperature": 0.7,
        "top_p": 0.9,
    },
}

# Keys read straight into GenParams. Anything else in the YAML is metadata.
_SAMPLER_KEYS = (
    "temperature",
    "top_p",
    "top_k",
    "min_p",
    "repetition_penalty",
    "frequency_penalty",
    "presence_penalty",
)


class PresetManager:
    def __init__(self, presets_dir: Path):
        self.dir = Path(presets_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.presets: dict[str, dict] = {}
        self.active = "balanced"
        self._seed_defaults()
        self.reload()

    def _seed_defaults(self) -> None:
        """Write built-ins to disk once so they are editable, then never
        overwrite — the file on disk wins from then on."""
        for key, preset in DEFAULTS.items():
            path = self.dir / f"{key}.yaml"
            if not path.exists():
                path.write_text(
                    yaml.safe_dump(preset, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )

    def reload(self) -> int:
        self.presets = {}
        for path in sorted(self.dir.glob("*.yaml")):
            try:
                self.presets[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                print(f"[presets] skipping {path.name}: {exc}")
        if self.active not in self.presets:
            self.active = "balanced" if "balanced" in self.presets else next(iter(self.presets), "balanced")
        return len(self.presets)

    def get(self) -> dict:
        return self.presets.get(self.active, DEFAULTS["balanced"])

    def set_active(self, key: str) -> bool:
        if key in self.presets:
            self.active = key
            return True
        return False

    def listing(self) -> list[tuple[str, str, bool]]:
        return [
            (key, p.get("description", ""), key == self.active)
            for key, p in sorted(self.presets.items())
        ]

    @property
    def style(self) -> str:
        return (self.get().get("style") or "").strip()

    def gen_params(self, fallback_max_tokens: int) -> GenParams:
        """Build a full request. The provider strips what it can't use."""
        p = self.get()
        kwargs: dict = {
            "max_tokens": int(p.get("max_tokens") or fallback_max_tokens),
            "effort": p.get("effort"),
        }
        for key in _SAMPLER_KEYS:
            if p.get(key) is not None:
                kwargs[key] = p[key]
        if p.get("stop"):
            kwargs["stop"] = list(p["stop"])
        return GenParams(**kwargs)

    def banned_strings(self) -> list[str]:
        """Post-generation filter. Mostly useful on local models, which still
        occasionally emit assistant-isms mid-scene."""
        return list(self.get().get("banned_strings") or [])
