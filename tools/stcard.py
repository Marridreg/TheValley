"""Read and write SillyTavern character cards.

A SillyTavern card is a PNG with the card JSON base64'd into a tEXt chunk. That
is the whole trick, and it is why cards can be shared as images. Two chunk keys
are in use:

    chara   V1/V2 payload. Every tool reads this.
    ccv3    V3 payload. Preferred by clients that understand it.

Three card generations exist in the wild and this module flattens all of them to
one shape so callers never branch on spec:

    V1   flat fields at the top level, no `spec`
    V2   {"spec": "chara_card_v2", "data": {...}}
    V3   {"spec": "chara_card_v3", "spec_version": "3.0", "data": {...}}

Nothing here is Valley-specific — it is the interchange layer. Mapping to and
from the engine's own public/private split lives in valley_card.py.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

# Every field a V2/V3 card can carry, with the empty value of the right type.
# Used to normalise, so downstream code can read a key without guarding it.
CARD_FIELDS: dict[str, object] = {
    "name": "",
    "description": "",
    "personality": "",
    "scenario": "",
    "first_mes": "",
    "mes_example": "",
    "creator_notes": "",
    "system_prompt": "",
    "post_history_instructions": "",
    "alternate_greetings": [],
    "tags": [],
    "creator": "",
    "character_version": "",
    "extensions": {},
}


class CardError(Exception):
    """A card that cannot be read, with a reason worth printing."""


def normalise(raw: dict) -> dict:
    """Flatten any card generation to the V2/V3 `data` shape.

    A V1 card has its fields at the top level; V2 and V3 nest them under `data`
    while often *also* mirroring some at the top level. Preferring `data` and
    falling back per-field means a card that only mirrors half of them still
    comes out whole.
    """
    if not isinstance(raw, dict):
        raise CardError(f"card is {type(raw).__name__}, expected an object")

    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    out: dict = {}
    for key, empty in CARD_FIELDS.items():
        value = data.get(key, raw.get(key, empty))
        if value is None:
            value = empty
        # Tolerate the common type slips rather than dying on them: tags as a
        # comma string, greetings as a single string.
        if isinstance(empty, list) and isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        if isinstance(empty, str) and not isinstance(value, str):
            value = str(value)
        out[key] = value

    book = data.get("character_book") or raw.get("character_book")
    out["character_book"] = book if isinstance(book, dict) else None
    out["spec"] = raw.get("spec") or "chara_card_v1"
    if not out["name"]:
        raise CardError("card has no name")
    return out


def to_v3(card: dict) -> dict:
    """Wrap a flat card in the V3 envelope, mirroring the legacy flat fields.

    The mirror matters: SillyTavern reads `data`, but plenty of other tools
    still read the top level, and a card that only fills one looks half-empty
    depending on what opens it.
    """
    data = {k: card.get(k, v) for k, v in CARD_FIELDS.items()}
    if card.get("character_book"):
        data["character_book"] = card["character_book"]
    envelope = {"spec": "chara_card_v3", "spec_version": "3.0", "data": data}
    for key in ("name", "description", "personality", "scenario", "first_mes",
                "mes_example", "creator_notes", "tags"):
        envelope[key] = data[key]
    envelope["talkativeness"] = "0.5"
    envelope["fav"] = False
    return envelope


def read_png(path: Path) -> dict:
    """Pull a card out of a PNG's tEXt chunks, newest spec first."""
    from PIL import Image

    with Image.open(path) as img:
        chunks = dict(img.text or {})
    raw = chunks.get("ccv3") or chunks.get("chara")
    if not raw:
        keys = ", ".join(sorted(chunks)) or "none"
        raise CardError(f"no card data in {path.name} (tEXt keys present: {keys})")
    try:
        decoded = base64.b64decode(raw)
    except Exception as exc:  # noqa: BLE001
        raise CardError(f"{path.name}: chunk is not valid base64 ({exc})") from exc
    try:
        return normalise(json.loads(decoded))
    except json.JSONDecodeError as exc:
        raise CardError(f"{path.name}: embedded payload is not JSON ({exc})") from exc


def read_any(path: Path) -> dict:
    """Read a card from a .png or a .json."""
    path = Path(path)
    if path.suffix.lower() == ".png":
        return read_png(path)
    return normalise(json.loads(path.read_text(encoding="utf-8", errors="replace")))


def write_png(card: dict, path: Path, avatar: Path | None = None) -> Path:
    """Write a card as a PNG, embedding it in both chunk keys.

    A bare .json in SillyTavern's characters folder is never listed — the app
    enumerates PNGs and reads the embed. So this is what makes a card actually
    appear. `avatar` supplies real art; without it the plate is a plain dark
    gradient, which reads as "no portrait yet" rather than as a broken image.
    """
    from PIL import Image, PngImagePlugin

    envelope = to_v3(card)
    payload = base64.b64encode(
        json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")

    if avatar and Path(avatar).exists():
        with Image.open(avatar) as src:
            img = src.convert("RGB")
    else:
        img = Image.new("RGB", (400, 600))
        for y in range(img.height):
            shade = 10 + int(14 * y / img.height)
            for x in range(img.width):
                img.putpixel((x, y), (shade, shade, shade + 5))

    info = PngImagePlugin.PngInfo()
    info.add_text("chara", payload)
    info.add_text("ccv3", payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", pnginfo=info)

    # Read it straight back. An unreadable embed produces a file that looks
    # exactly like a working card until SillyTavern silently ignores it.
    check = read_png(path)
    if check.get("name") != card.get("name"):
        raise CardError(f"{path.name}: embed did not round-trip")
    return path
