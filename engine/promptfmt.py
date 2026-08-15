"""Shared prompt formatting.

Lives on its own so that neither side of the Wall has to import the other —
narrator.py importing from gm.py would be exactly the coupling this
architecture exists to avoid, even for a two-line helper.
"""

from __future__ import annotations

import json


def dump(obj) -> str:
    """JSON for a prompt, not for a wire.

    ensure_ascii=False keeps em-dashes and Romanian diacritics as themselves
    instead of \\uXXXX escapes — easier for a model to read, and materially
    cheaper, since an escape sequence costs several tokens where the character
    costs one. Over a vault and a dozen character cards resent every turn, that
    adds up.
    """
    return json.dumps(obj, indent=2, ensure_ascii=False)
