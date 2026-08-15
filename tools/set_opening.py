#!/usr/bin/env python3
"""Set the authored opening message in data/world.json.

Written to the rules in `opening message rules and guidelines.txt`:

  1. Never address or describe the protagonist directly. No "you", no "your",
     no naming him, no describing him from outside. The camera sits behind his
     eyes rather than watching him — so the prose reports what is perceived and
     never the perceiver.
  2. Tone through sensory environment. Horror: oppressive atmosphere, uncanny
     detail, dread built rather than stated.
  3. Character cards as setting rules. The village's actual rules — faith as
     infrastructure, the Lords' claim on people, strangers as an event — are
     shown through how people behave in space, never explained.
  4. Prose density matched to genre. Atmospheric, accumulating.
  5. Ground the altered reality naturally. No exposition.
  6. End on a pause, not a prompt. No "what do you do?".

Brief: wake outside the village, wander in, be accosted by someone with the
authority to drag him in front of Lady Dimitrescu.

    python tools/set_opening.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OPENING = """\
Cold, first. Not the clean cold of altitude — the wet kind that has already \
got past wool and stopped being a feeling on the skin and started being a fact \
in the bone.

Snow packed against one cheek, gritty where it had melted and frozen again. \
Grey sky through black branches, moving. Somewhere close, water running under \
ice, and under that, nothing. No birds. The kind of quiet that is not peaceful \
because something has produced it.

Fingers worked. Then a hand. Then the whole arm, badly.

Army surplus coat, soaked through and stiffening. A holster at the hip, empty, \
the leather worn pale in the shape of something that had lived in it for years. \
No memory of putting it on. No memory of anything before the cold, and pushing \
at that absence produced no edge to it at all — not a wall, not a door. Just \
snow, and the sky, and the taste of iron.

Downhill there was a bell. Not a church bell. Something smaller and flatter, \
hung in a doorway to be struck by hand.

The village came out of the trees in pieces. A fence line first, staked with \
sharpened wood and strung with wire that had been mended too many times. Then \
a roof. Then the rest of it, crouched in the bowl of the valley with its back \
to the mountain: thirty houses, maybe fewer, smoke standing straight up from \
half of them and not at all from the others.

Above every door, something nailed. Not crosses. Small bundles of dried \
flowers, bound tight, the same arrangement on every house — and beneath each \
one, scratched into the lintel or burned there, the same four-lobed mark.

A woman was crossing the road with a bucket. She stopped when the treeline \
gave up its shape, looked for a long moment, and then went back the way she \
had come, still carrying the water. A door closed. Then another, further off, \
that had not been open.

The road ran east and ended at a gate. The gate was barred from the inside.

Nothing moved in the village at all after that, except smoke, and the flowers \
above the doors turning slightly where the wind got under them.

Then, from the top of the road, a sound that did not belong to any of it — a \
low buzzing hum, like a wasp nest in August, wrong in the cold. It arrived \
before its owner did.

She came down the road unhurried, in a dark hooded cloak stiff with old \
stains, and stopped six feet away, and looked with the particular attention of \
someone doing arithmetic. Gold eyes. A sickle held down along her leg the way \
a tool is carried rather than a weapon.

The humming stopped.

"Oh," she said, delighted. "Something new."

She tilted her head, and the movement went slightly too far.

"Mother will want to see this one. Don't run — I'd like it, and you wouldn't."\
"""


def main() -> int:
    path = ROOT / "data" / "world.json"
    world = json.loads(path.read_text(encoding="utf-8"))
    world["opening_text"] = OPENING
    # The narrator must be told the register, because it is not the default for
    # the genre and the opening establishes it.
    world["prose_convention"] = (
        "NARRATION never addresses or describes the protagonist. No 'you', no "
        "'your', no name, no description of his face or body from a vantage he "
        "could not have. The camera sits behind his eyes: report what is "
        "perceived, never the perceiver. Sentence fragments are acceptable and "
        "often correct. His involuntary physical responses may be reported as "
        "facts of the world — a held breath, hands that will not work, cold "
        "that has stopped being a feeling — but never his decisions.\n\n"
        "DIALOGUE is exempt. Characters speaking to him say 'you' like anyone "
        "would; the prohibition is on the narrating voice, not on the people in "
        "the room. An NPC may also describe him aloud — that is their "
        "observation, which he can hear, rather than the camera stepping "
        "outside his head."
    )
    path.write_text(json.dumps(world, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  opening_text set ({len(OPENING)} chars)")
    print("  prose_convention set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
