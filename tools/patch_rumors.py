#!/usr/bin/env python3
"""Author the missing rumour variants flagged by validate_cards.py.

Every entry here fills a section whose learnable_from promised a `rumor` that
was never written. With the fail-closed behaviour in state.py those routes were
dead ends; before the fail-closed fix they silently handed over the truth.

The rule each rumour follows: the distortion comes from the *source's own blind
spot*, not from random noise. Miranda cannot imagine someone wanting her role
rather than merely resenting it, so her account of Heisenberg's ambition gets
the direction exactly wrong. Moreau needs Miranda to still be good, so his
account of the cage blames Heisenberg for provoking her. That is what makes a
rumour worth carrying around and worth correcting later.

Idempotent — skips any section that already has a rumour.

    python tools/patch_rumors.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RUMORS: dict[str, dict[str, str]] = {
    "bela": {
        "gated_states": (
            "Cassandra will tell you, delightedly, that Bela comes apart if you open a "
            "window on her, and she will offer to show you. She has the trigger right and "
            "everything else wrong: she presents it as squeamishness, a fussy sister who "
            "cannot take the cold, a joke that has been funny for sixty years. It has never "
            "occurred to her that what she is demonstrating is her sister failing to hold "
            "herself together, or that Bela does not refer to it afterwards because there is "
            "nothing to say about it."
        )
    },
    "cassandra": {
        "gated_states": (
            "Bela calls it 'when she goes off' and treats it as a scheduling problem — after "
            "a hunt Cassandra is useless for an hour, so do not plan anything for that hour. "
            "The pattern is exactly right. What Bela has never considered is that the empty "
            "hour is not a lapse in Cassandra's character but the only time she is not "
            "performing one, and that the thing sitting slack-faced in the cellar afterwards "
            "was underneath the whole time."
        )
    },
    "daniela": {
        "loss_of_control": (
            "Everyone in the castle knows the rule and nobody knows the reason. The maids "
            "will tell you, quietly and quickly, that you never shut a door in front of the "
            "youngest one — not locked, simply shut. Bela will confirm it in the language of "
            "logistics, as a standing constraint she has stopped querying. Alcina calls her "
            "daughter sensitive. All of them have the behaviour precisely and read it as "
            "temper, a spoiled child's outburst at being denied. None of them has connected "
            "a closed door to being left."
        )
    },
    "donna": {
        "the_veil": (
            "You may notice the veil has stopped being pinned properly on the left, and the "
            "obvious reading is that she has grown careless, or that the fog has got into "
            "her the way it gets into everything in that house. It is the opposite of "
            "carelessness. Nothing about her dress has been careless in twenty years. But "
            "the reading is available, and most people take it, and Angie will encourage "
            "them to — loudly, and about something else."
        )
    },
    "duke": {
        "gated_states": (
            "Everyone has asked once. The villagers will tell you he is simply a private "
            "man, and then change the subject themselves without noticing they are doing "
            "it, which is the more interesting half of the answer. Heisenberg has tried it "
            "drunk, sober and holding a wrench, and reports only that it is the single most "
            "irritating conversation available in the valley. Both accounts agree the Duke "
            "does not discuss himself and both treat this as reticence — a man with a dull "
            "past, or a sad one, keeping it to himself out of ordinary preference."
        )
    },
    "heisenberg": {
        "the_cage": (
            "Moreau was made to watch part of it and cannot get through a sentence about it "
            "without apologising for having been there. What comes out in fragments is that "
            "Mother Miranda had to correct Karl once, that it was terrible, and that Karl "
            "had brought it upon himself by refusing her — which is the only version of the "
            "story in which Miranda is still good, and therefore the only version Moreau can "
            "hold. He has the event. He has the cause exactly backwards, and he will defend "
            "the backwards version if pressed."
        ),
        "megamycete_ambition": (
            "Miranda speculates about his intentions freely, being the only other person who "
            "understands what the Megamycete can be used for. Her conclusion is that he "
            "wants to destroy it — that his rebellion is vandalism, an ungrateful animal "
            "wanting to break the thing it was made from. She is certain enough to say it "
            "aloud. It has never entered her consideration that he might want to *use* it, "
            "because she cannot picture anyone coveting her position rather than merely "
            "resenting it, and that blind spot is the widest gap in her defences."
        ),
        "betrayal_prevention": (
            "The Duke has noticed a third of it and drawn a confident wrong conclusion, "
            "which he will sell you cheaply: hit him once, properly, and he will love you "
            "for it. The first part is real — matching Karl physically does change how he "
            "files you. The Duke has not seen the two steps after it, and does not know "
            "there are two steps after it, so anyone who buys this and stops there has "
            "bought a man's respect and left his plan entirely intact."
        ),
        "weaknesses": (
            "Alcina knows condescension works on him and deploys it at every gathering "
            "without ever having wondered why it works; her account is that he is a "
            "thin-skinned mechanic who can be reduced to shouting by being spoken to "
            "slowly. Donna, who has watched him from a distance for years, has the stranger "
            "and closer read — that being handled kindly does something worse to him than "
            "being handled badly — but she cannot articulate it, and what reaches you "
            "through Angie is mangled into an insult."
        ),
        "loss_of_control": (
            "There is a section of factory plating torn outward from the inside and bolted "
            "back on crooked, never properly repaired, and anyone who has been that deep "
            "into the building has seen it. Moreau saw the thing that did it and describes "
            "it in fragments, badly, still frightened years later: that Karl went wrong, "
            "that the metal came off the walls, that it was not aimed at anybody. The "
            "conclusion drawn from the wall and the stammering together is that Heisenberg "
            "has a temper that occasionally takes the building with it — a big man's rage, "
            "scaled up. Nobody outside that room knows it was panic."
        ),
        "gated_states": (
            "He denies both of them exist, in exactly the same tone, which is the most "
            "informative thing he does. Ask whether anything gets under his guard and you "
            "get the same flat sardonic dismissal you get for asking whether he has ever "
            "respected anyone — and the identical delivery for two very different questions "
            "is itself a tell, if you are counting."
        ),
    },
    "iulian": {
        "weaknesses": (
            "Sebastian has watched people fail at this for months and can describe the "
            "failure precisely: they thank him, or they tell him he is doing well, and he "
            "goes stiff and finds somewhere else to be. Sebastian's conclusion is that "
            "Iulian cannot take kindness. It is nearly right and it points the wrong way — "
            "the thing that undoes him is not being thanked but being *believed*, and no one "
            "has tried that, so no one has seen what it does."
        ),
        "loss_of_control": (
            "Luiza has physically stood in a doorway to stop him going out past the wire at "
            "night and will admit that it happened, without saying what set him off. Anton "
            "calls it the sentry's tantrum and is genuinely frightened while calling it "
            "that. Between them the village has settled on a reading: the watchman is "
            "cracking, he has been awake too long, one night he will walk out and not come "
            "back. They have the outcome right. Not one of them has connected it to the "
            "warnings he gave that nobody acted on."
        ),
    },
    "leonardo": {
        "weaknesses": (
            "Luiza has been feeding him for forty years and can tell you exactly how to get "
            "a yes out of him: do not offer to help, ask him to show you how it is done. "
            "She is completely right about the method and treats it as an old man's pride — "
            "the vanity of a man who likes to be the one who knows the fence. She has never "
            "said the other part out loud, possibly because she has worked it out and "
            "decided not to: that what he actually wants is evidence that the fence will "
            "hold after him."
        ),
        "loss_of_control": (
            "There is a thirty-year-old story about a dispute over animals that ended with a "
            "man leaving the valley and not coming back, and the village tells it as a story "
            "about Leonardo Lupu having been formidable once. Elena saw something herself as "
            "a child and has never asked him about it, which is its own kind of testimony. "
            "The version that circulates is about a strong young man's temper, safely in the "
            "past. Nobody has noticed that the trigger was never temper, and that it has not "
            "gone anywhere, and that Elena is the trigger now."
        ),
    },
    "luiza": {
        "the_cost_of_shelter": (
            "Iulian has had the argument with her a dozen times and lost it a dozen times, "
            "and will tell you flatly that she does not understand the risk. Anton says "
            "nightly that the woman will get them all killed with kindness. Both of them "
            "have decided she is soft — an old woman who cannot say no, sleepwalking the "
            "village into a reckoning. Neither has grasped that she has understood the risk "
            "from the beginning, counts it every time, and takes the stranger in anyway, "
            "which is a different thing entirely and much harder to argue with."
        ),
        "weaknesses": (
            "The village's advice about Luiza reduces to: eat what she gives you, and eat a "
            "lot of it. This is true, useful, and about a tenth of the picture. It gets you "
            "her goodwill and it will never get you anything that costs her something."
        ),
        "loss_of_control": (
            "Iulian saw it once, will not describe it, and it is the reason he guards her "
            "house rather than the other way round. Sebastian was in his corner, as he "
            "always is, and what he remembers is not the event but the scrubbing afterwards "
            "— hours of it, long past clean. What the village has assembled from those two "
            "silences is that something happened in Luiza's house once and that it was bad. "
            "They have no idea it was her."
        ),
    },
}


def main() -> int:
    written = skipped = 0
    for npc, sections in RUMORS.items():
        path = ROOT / "data" / "characters" / npc / "private.json"
        if not path.exists():
            print(f"  ! {npc}: no private.json")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        container = data.get("sections") if isinstance(data.get("sections"), dict) else data
        changed = False
        for name, rumor in sections.items():
            sec = container.get(name)
            if not isinstance(sec, dict):
                print(f"  ! {npc}.{name}: not a v2 section, skipped")
                continue
            if sec.get("rumor"):
                skipped += 1
                continue
            # Insert directly after `truth` so the file stays readable.
            rebuilt = {}
            for k, v in sec.items():
                rebuilt[k] = v
                if k == "truth":
                    rebuilt["rumor"] = rumor
            if "rumor" not in rebuilt:
                rebuilt["rumor"] = rumor
            container[name] = rebuilt
            changed = True
            written += 1
            print(f"  + {npc}.{name}")
        if changed:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
    print(f"\n{written} rumour(s) authored, {skipped} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
