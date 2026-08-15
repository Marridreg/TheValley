#!/usr/bin/env python3
"""Complete the village cards the failed conversion run didn't reach.

Writes anton's private half, three whole cards (roxana, sebastian, eugen), and
data/villagers.json for the population-level material that isn't about any one
person.

Vasile is deliberately NOT a card. He is absent at timeline start and his fate
is unresolved — that belongs in the vault, not in a narrator-visible file, so
this script adds it there instead.

Idempotent: existing files are left alone.

    python tools/finish_villagers.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARS = ROOT / "data" / "characters"

PUB_NOTE = "What one encounter with them shows you. No secrets. The narrator starts here."
PRIV_NOTE = (
    "GM ONLY. Each section carries the truth, an optional rumour for second-hand "
    "routes, and learnable_from — every way this can be found out. Release with "
    "'<id>.<section>' for truth or '<id>.<section>#rumor' for the distorted version. "
    "learnable_from NEVER crosses the Wall."
)


def priv(sections: dict) -> dict:
    return {"_note": PRIV_NOTE, "_schema": "v2", "sections": sections}


# ── ANTON — private half only; public already exists ────────────────────────

ANTON_PRIVATE = priv({
    "the_drinking_is_fear": {
        "truth": "The drink is fear with a label change, and he knows it. He has been "
                 "watching this village die by subtraction for years — counting, the way "
                 "Iulian counts, except he started earlier and never told anyone he was "
                 "doing it — and he has no coping mechanism beyond rage and țuică. The "
                 "cruelty is not a character flaw sitting on top of a frightened man. It "
                 "is the frightened man, load-bearing. Take the drink away and what is "
                 "underneath does not improve; it simply stops being able to speak.",
        "rumor": "The village's read is the obvious one: a drunk who turned nasty, in that "
                 "order. Iulian will tell you Anton was always like this and the brandy "
                 "only removed the lid. Everyone has the causation backwards, and it is a "
                 "comfortable backwards, because a man who was always cruel requires "
                 "nothing of them.",
        "learnable_from": [
            {"route": "person", "who": "anton", "how": "only in the lucid window, only if you are already sitting there and have not been kind about it", "yields": "truth"},
            {"route": "person", "who": "luiza", "how": "she has fed him for years and will say quietly that he was not always this and will not elaborate", "yields": "truth"},
            {"route": "person", "who": "iulian", "how": "he argues with Anton nightly and has a confident theory", "yields": "rumor"},
            {"route": "observation", "what": "the schedule — he arranges his entire day around the hour the tremor stops, which is planning, and planning is not what despair looks like", "yields": "rumor"},
            {"route": "place", "what": "his plot at the village edge, unworked but not abandoned: the tools are inside and oiled", "yields": "rumor"},
        ],
    },
    "who_he_lost": {
        "truth": "A wife and a son, four winters ago, in the same month. Neither died of "
                 "wolves. Both 'went to serve Mother Miranda' and did not come back, and "
                 "Anton was the one who agreed to let them go, because at the time that was "
                 "what faith looked like and he had plenty. He has never said either name "
                 "aloud since. When he savages someone for praying, he is not attacking "
                 "their faith. He is attacking the man he was when he had it.",
        "rumor": "People know he lost family and assume wolves, because that is what "
                 "everyone loses family to now. Luiza knows better and will not correct "
                 "the record in front of him.",
        "learnable_from": [
            {"route": "document", "what": "village_parish_register", "yields": "truth"},
            {"route": "person", "who": "luiza", "how": "she was there when he agreed to it, and she will tell you if you have earned her and if he is not in the room", "yields": "truth"},
            {"route": "person", "who": "sebastian", "how": "he was in his corner and remembers which month the shouting stopped", "yields": "rumor"},
            {"route": "person", "who": "villagers", "how": "general account of his losses", "yields": "rumor"},
            {"route": "possession", "what": "the good coat gone bad — it was decent wool, cut for a man with a wife who cared what he looked like", "yields": "rumor"},
        ],
    },
    "why_he_is_right": {
        "truth": "He is right about almost everything because he is the only person in the "
                 "room paying full attention, and he pays full attention because he is "
                 "terrified. Terror is an excellent instrument. He noticed the Enescus were "
                 "gone before anyone said it, he knows which houses are dark, he knows "
                 "bringing a stranger in shifts the odds. He delivers all of it in a package "
                 "designed to be rejected — and that is not accident either. If they took "
                 "him seriously he would have to do something about it.",
        "rumor": "Sebastian, who watches everything, has worked out that Anton is usually "
                 "correct and will say so flatly if asked. His conclusion is that Anton is "
                 "cleverer than he pretends. He has not got as far as why the delivery is "
                 "built the way it is.",
        "learnable_from": [
            {"route": "person", "who": "sebastian", "how": "asked directly whether Anton is ever right; he has an answer ready and nobody has ever wanted it", "yields": "rumor"},
            {"route": "observation", "what": "checking his claims against what you find — the dark houses are dark, the count is correct, the fences are not enough", "yields": "truth"},
            {"route": "person", "who": "anton", "how": "in the lucid window, if you tell him he was right about something specific and do not soften it", "yields": "truth"},
        ],
    },
    "the_luiza_exception": {
        "truth": "He calls her 'woman' and there is no cruelty in it, and it is the only "
                 "address he uses that does not carry any. He knows exactly what she is "
                 "doing — that she takes people in knowing the cost, that she is not soft "
                 "but choosing, that the feeding is how she keeps a roof over a village "
                 "that has stopped being able to do it for itself. He will never say so. He "
                 "will savage anyone else who calls her soft, and then savage her too, "
                 "immediately, so nobody notices the first part.",
        "rumor": "Nobody has noticed. Ask anyone at that table whether Anton respects Luiza "
                 "and you will be laughed at, and the last person to be at the receiving end "
                 "of his mouth about her hospitality will offer the counter-evidence.",
        "learnable_from": [
            {"route": "observation", "what": "counting the addresses — everyone in that house has a cruel name and she does not", "yields": "truth"},
            {"route": "observation", "what": "what happens when someone else calls her soft in front of him", "yields": "truth"},
            {"route": "person", "who": "luiza", "how": "she knows, and will say only that Anton has never once refused to eat what she put in front of him", "yields": "rumor"},
            {"route": "person", "who": "villagers", "how": "the general view of Anton's opinion of his host", "yields": "rumor"},
        ],
    },
    "weaknesses": {
        "truth": "Being sat with. Not talked to, not reasoned with, not out-argued — sat "
                 "beside, without flinching, for long enough that the performance runs out "
                 "of fuel. It takes real endurance and he will make it as unpleasant as he "
                 "can. Also: being agreed with, which he has no reply to; being poured for "
                 "without comment; and someone else being crueller than him in the room, "
                 "which shames him into silence faster than any rebuke.",
        "rumor": "The village's working method is to ignore him or shout back, and both are "
                 "wrong. Iulian recommends the second and has never once succeeded with it.",
        "learnable_from": [
            {"route": "person", "who": "iulian", "how": "he will confidently tell you how to shut Anton up, having failed at it for a year", "yields": "rumor"},
            {"route": "person", "who": "luiza", "how": "she does the correct thing nightly without describing it as a technique", "yields": "truth"},
            {"route": "observation", "what": "watching what makes him stop mid-sentence versus what makes him louder", "yields": "truth"},
        ],
    },
    "loss_of_control": {
        "truth": "Trigger: hearing either of his dead named aloud, or the roof itself "
                 "failing — a death inside Luiza's house, or being told to leave it. During: "
                 "the volume goes, which is the frightening part, since volume is all he "
                 "has. He goes white and very still and then he begins telling the room the "
                 "truth without any of the armour on it — who is already dead, who is next, "
                 "what nobody has said. It is unbearable and it is accurate and it empties "
                 "the room. Afterwards he drinks until he cannot form the sentences and "
                 "sleeps where he sits, and in the morning he behaves as though nothing "
                 "happened and is crueller than usual for two days.",
        "rumor": "It has happened twice that anyone remembers. Both times the village "
                 "recorded it as Anton finally going too far and had to be told to leave, "
                 "which is not what happened; both times he was already leaving.",
        "learnable_from": [
            {"route": "person", "who": "sebastian", "how": "he was there both times and remembers the order of events correctly, which nobody else does", "yields": "truth"},
            {"route": "person", "who": "villagers", "how": "the standard account of the two occasions", "yields": "rumor"},
            {"route": "person", "who": "luiza", "how": "she can tell you what was said and will not tell you the names that started it", "yields": "rumor"},
        ],
    },
    "handling": {
        "truth": "Works: sitting down beside him without an agenda, pouring without comment, "
                 "agreeing with him out loud when he is right and naming the specific thing, "
                 "and never once being kind where the room can see. Fails: prayer offered as "
                 "a plan, optimism, pity, being told to be quiet, and public kindness — he "
                 "reads that as an attack, correctly, because it is an attempt to make him "
                 "look like something he cannot afford to look like in front of these "
                 "people.",
        "rumor": "Common wisdom is that Anton cannot be handled, only endured. It has the "
                 "advantage of requiring nothing.",
        "learnable_from": [
            {"route": "person", "who": "villagers", "how": "the consensus", "yields": "rumor"},
            {"route": "observation", "what": "trial and error across several evenings at that table", "yields": "truth"},
            {"route": "person", "who": "luiza", "how": "asked directly how she does it, after she trusts you", "yields": "truth"},
        ],
    },
    "gated_states": {
        "truth": {
            "sober": "The middle of a night when the bottle ran out and nobody replaced it. "
                     "He is quiet, grey, and shaking, and he does not perform at all. This "
                     "is the only state in which he asks a question rather than answering "
                     "one, and the question is usually about whether somebody is still "
                     "alive.",
            "seen": "Someone has sat with him long enough, often enough, without flinching, "
                    "and he has stopped waiting for it to turn into pity. The cruelty stays "
                    "— it is the only register he has — but it stops being aimed at the "
                    "person beside him, and he begins saving the accurate things for them "
                    "specifically, delivered sideways and under his breath, as gifts he "
                    "will deny giving.",
        },
        "learnable_from": [
            {"route": "observation", "what": "each is learned by causing it; there is no other route to either", "yields": "truth"},
        ],
    },
})

# ── ROXANA ─────────────────────────────────────────────────────────────────

ROXANA_PUBLIC = {
    "_note": PUB_NOTE,
    "identity": "Roxana | thirties | female | widow, as of days ago. Her husband was a "
                "shepherd and died of wounds taken from the wolves. She has not left "
                "Luiza's front room since they brought him in.",
    "addresses_others": {
        "everyone": "She does not, mostly. She answers direct questions with the fewest "
                    "words that will end them.",
        "luiza": "'Doamna Luiza', the only formality anybody in that house still uses.",
    },
    "look": "Gaunt in the specific way of someone who has not eaten in four days rather "
            "than four months. Eyes swollen almost shut, the skin around them raw from "
            "being wiped. Hair unbound and uncombed, which in this village is its own "
            "announcement. She sits on the floor beside the couch rather than on a chair, "
            "with one hand resting on it, and she has been in that position long enough "
            "that people step around her without looking.",
    "wears": "What she was wearing when they brought him in. Nobody has persuaded her to "
             "change it.",
    "scent": "Cold sweat, unwashed hair, and the tallow of the candle somebody keeps "
             "replacing beside her.",
    "voice": "Almost nothing, and when it comes it is flat and level and does not shake, "
             "which is worse than if it did. Short sentences. Long gaps she does not appear "
             "to notice. Underneath the flatness the accent is soft and rural and she "
             "pronounces her husband's name the way he pronounced it himself.",
    "speech_examples": [
        "\"He's cold. I know. I know he is.\"",
        "\"Don't. Please don't say she has a plan.\"",
        "\"You can sit. If you're going to sit, sit.\"",
        "\"He kept saying it and I kept telling him to rest.\"",
    ],
    "default_state": "On the floor at the head of the couch, one hand on it, keening — not "
                     "loudly, a low continuous sound she is not aware of making and does "
                     "not stop when spoken to. She is the noise in the background of every "
                     "scene in that house and she is the reason the room is quiet.",
    "states": {
        "keening": "Default. Present, unreachable, continuous. Conversation happens over "
                   "her and she does not react to it.",
        "answering": "Someone has asked her something directly and gently. Flat, brief, "
                     "accurate answers, eyes on the couch throughout. Ends the moment the "
                     "questions stop.",
        "flaring": "Somebody has offered her Mother Miranda's plan, or told her he is at "
                   "peace. Very fast, very quiet, and it empties the room's confidence — "
                   "she does not raise her voice and she does not stop until they leave.",
    },
    "likes": "Being sat with in silence. Being asked about him rather than about herself. "
             "Anyone who says his name.",
    "dislikes": "Being told he is at peace. Being told Mother Miranda has a plan. Being "
                "moved. Anton, whom she does not look at.",
    "role": "The cost, made audible. She is the reminder of what the wolves take in human "
            "terms, sitting in the middle of the room where the village makes its plans. "
            "Most scenes she is texture rather than a participant. She is also, and nobody "
            "has realised it, holding the most useful tactical information in the valley.",
    "never_says": [
        "her husband's name in the past tense",
        "anything about her own state",
        "'thank you' — it does not reach her",
    ],
    "carry_over": "If someone sat with her last scene without asking for anything, she "
                  "knows precisely who it was, and the next time they come in she moves "
                  "her hand off the couch, which is the only invitation she has left.",
}

ROXANA_PRIVATE = priv({
    "the_observations": {
        "truth": "Her husband was a shepherd and he watched the attacks for two months "
                 "before they killed him. He had a pattern: they come from the north-east "
                 "and the treeline above the Fallow Plot, never across the open ground by "
                 "the reservoir; they strike between the last light and full dark, not at "
                 "the dead of night; they avoid the ground near the church entirely; and in "
                 "the last three weeks they stopped taking sheep and started taking only "
                 "people, which is not what animals do. His conclusion, which he said aloud "
                 "to her more than once, was that they were being directed. She told him to "
                 "stop talking like that. She told him to rest. This is the single most "
                 "actionable piece of intelligence in the village and it will die with her "
                 "unless somebody sits with her first and then asks what he told her.",
        "rumor": "It is known that the shepherd had theories and that his wife told him to "
                 "stop. Iulian has heard third-hand that somebody was saying the wolves were "
                 "organised and agrees with it entirely, having reached it himself, but he "
                 "does not know who said it or that the details still exist.",
        "learnable_from": [
            {"route": "person", "who": "roxana", "how": "she will only tell someone who has sat with her first, in silence, asking for nothing — and then only if they ask about him rather than about the wolves", "yields": "truth"},
            {"route": "person", "who": "iulian", "how": "he has the conclusion without the data and will trade what he has", "yields": "rumor"},
            {"route": "person", "who": "villagers", "how": "the shepherd's theories, remembered as a dying man's raving", "yields": "rumor"},
            {"route": "possession", "what": "his tally stick, still in his coat on the couch — notches in groups, dated, with the last three weeks marked differently", "yields": "truth"},
            {"route": "person", "who": "sebastian", "how": "he heard the shepherd say it in Luiza's front room and remembers it verbatim, as he remembers everything", "yields": "truth"},
        ],
    },
    "the_guilt": {
        "truth": "She does not believe she killed him and she cannot stop arranging the "
                 "facts as though she did. He told her the wolves were being directed; she "
                 "told him to rest; he rested, and he went back out the next evening anyway "
                 "because the sheep needed moving, and that is where they took him. The "
                 "line she keeps returning to is not that she disbelieved him. It is that "
                 "she told him to stop *talking* about it, and so the last two days of his "
                 "life were spent silent about the only thing he was certain of.",
        "rumor": "The house's reading is straightforward grief and everyone is being kind "
                 "about it. Luiza has noticed there is something specific underneath and has "
                 "not pried.",
        "learnable_from": [
            {"route": "person", "who": "roxana", "how": "she will say the whole thing in four sentences to anyone who asks about him twice", "yields": "truth"},
            {"route": "person", "who": "luiza", "how": "she has noticed the shape of it without the content", "yields": "rumor"},
            {"route": "observation", "what": "she repeats one exchange verbatim, unprompted, in slightly different words each time", "yields": "truth"},
        ],
    },
    "weaknesses": {
        "truth": "Being sat with, in silence, by somebody who does not fill it. Hearing his "
                 "name spoken by another person — she has not heard anyone else say it since "
                 "he died and it will stop her mid-sound. Being asked a practical question "
                 "she can answer, which is the only thing that gets her off the floor. And "
                 "the opposite of a weakness but worth knowing: being handed something to "
                 "do that matters.",
        "rumor": "The village's approach is condolence, and condolence bounces off her "
                 "entirely. Luiza's is food, which also does not work, though Luiza will not "
                 "stop trying.",
        "learnable_from": [
            {"route": "observation", "what": "watching every well-meant approach fail, and noticing which one does not", "yields": "truth"},
            {"route": "person", "who": "villagers", "how": "how one is supposed to behave toward a widow", "yields": "rumor"},
            {"route": "person", "who": "luiza", "how": "she will admit she cannot reach her", "yields": "rumor"},
        ],
    },
    "gated_states": {
        "truth": {
            "useful": "Somebody has given her a task connected to the wolves — carrying "
                      "her husband's observations to whoever needs them, marking a map, "
                      "identifying a direction. She stands up. The keening stops and does "
                      "not come back while she is working. She is precise, quick and "
                      "unsentimental about the details, and she will not thank anybody for "
                      "it, because being useful is not a kindness done to her, it is the "
                      "first hour since he died that has had a shape.",
        },
        "learnable_from": [
            {"route": "observation", "what": "caused rather than learned about; give her the task and watch it happen", "yields": "truth"},
        ],
    },
})

# ── SEBASTIAN ──────────────────────────────────────────────────────────────

SEBASTIAN_PUBLIC = {
    "_note": PUB_NOTE,
    "identity": "Sebastian | age hard to place, somewhere between thirty-five and sixty | "
                "male | no role the village recognises. His left leg does not work and has "
                "not for years. He occupies the corner seat by the window in Luiza's front "
                "room, and has the best view of the road in the village.",
    "addresses_others": {
        "everyone": "By name, correctly, including people who have never told him theirs.",
        "anton": "He does not respond to Anton at all, which is the closest thing to an "
                 "opinion he expresses in public.",
    },
    "look": "Thin, still, and easy to miss — he has the particular stillness of a man who "
            "learned years ago that moving costs him and watching does not. The left leg is "
            "held out straight and turned slightly wrong at the knee; a stick leans against "
            "the wall beside him within reach. Face narrow, clean-shaven in a village that "
            "mostly is not, dark eyes that track the door and the window in a steady "
            "unhurried rotation. His hands are the only part of him that is idle.",
    "wears": "Clean, mended, unremarkable. Somebody launders for him and he does not "
             "discuss the arrangement.",
    "scent": "Soap, woodsmoke from the corner nearest the fire, and cold from the window "
             "at his shoulder.",
    "voice": "Quiet, level, and infrequent. He speaks in complete sentences with no filler "
             "and stops the moment he has finished, which people find unnerving because "
             "they are still waiting for more. Never raised. Never hurried. He will "
             "sometimes answer a question asked to the room in general, several beats after "
             "everyone else has stopped talking, and be correct.",
    "speech_examples": [
        "\"The house at the end of the east row. The light went out four nights ago. No one went in. No one came out. ...No one's checked.\"",
        "\"You came in from the north. There's snow on your left shoulder and not your right.\"",
        "\"Ask me again when you actually want the answer.\"",
        "\"Ninety-one. Iulian says ninety-three. Iulian is counting the Enescus.\"",
    ],
    "default_state": "In the corner chair with his back to the wall and the window at his "
                     "shoulder, hands still, watching the door. He has been part of the "
                     "furniture of that room for so long that people discuss things in "
                     "front of him that they would not discuss in front of each other.",
    "states": {
        "watching": "Default. Silent, attentive, apparently uninvolved. He is cataloguing.",
        "answering": "Somebody asked him something directly, which is rare. Precise, brief, "
                     "complete, and volunteering nothing beyond what was asked.",
        "offering": "He has decided something matters enough to say without being asked. "
                    "Quiet, aimed at one person specifically rather than the room, and he "
                    "will not repeat it if it is ignored.",
    },
    "likes": "Being asked. Being asked twice. Precision. Somebody who notices he was right "
             "and says so.",
    "dislikes": "Being helped without being consulted first. Being talked over. Pity, "
                "which he treats as an error of fact rather than an insult.",
    "role": "The village's passive intelligence network, entirely unrecognised as such. He "
            "cannot move freely, so he sits, and he sees: who comes and goes, which "
            "direction the sounds come from at night, which houses have gone dark this "
            "month, who is lying about where they have been. Nobody has thought to ask him "
            "because nobody thinks the man in the corner has anything to contribute.",
    "never_says": [
        "anything about his leg",
        "an opinion nobody requested",
        "a guess presented as a fact — he marks the difference every time",
    ],
    "carry_over": "He has been watching since the last scene and will have one specific "
                  "observation ready about whatever the PC did in it, offered to them alone "
                  "and only if they were the kind of person who says hello to him.",
}

SEBASTIAN_PRIVATE = priv({
    "what_he_knows": {
        "truth": "An enormous amount, all of it accurate and none of it volunteered. The "
                 "true population count and which of Iulian's figures are wrong and why. "
                 "Which houses have gone dark and in what order, which is a direction. That "
                 "Eugen leaves before dawn twice a week and comes back with a covered "
                 "basket and takes the long way round to avoid passing the window. Who "
                 "visits Luiza's after dark and who avoids being seen doing it. That the "
                 "sounds at night come from the north-east and have been getting nearer at "
                 "a measurable rate he can state. He has never written any of it down and "
                 "does not need to.",
        "rumor": "The village thinks of him, when it thinks of him, as a quiet invalid who "
                 "keeps to himself. Anton calls him worthless out loud, nightly, and the "
                 "room's failure to disagree is the village's actual position.",
        "learnable_from": [
            {"route": "person", "who": "sebastian", "how": "ask him. That is the entire gate. He answers precisely and completely, and the reason nobody has this information is that nobody has asked", "yields": "truth"},
            {"route": "observation", "what": "noticing that he answered something correctly that nobody else in the room could have, and going back to him", "yields": "truth"},
            {"route": "person", "who": "villagers", "how": "the general view of the man in the corner", "yields": "rumor"},
            {"route": "person", "who": "anton", "how": "his assessment, delivered nightly and loudly", "yields": "rumor"},
        ],
    },
    "why_he_does_not_offer": {
        "truth": "He offered, for about a year, and was talked over every time. He has "
                 "since arrived at a position that is not bitterness so much as accounting: "
                 "information given to people who will not act on it is wasted, and he has "
                 "a finite amount of attention and one leg. So he waits to be asked, and "
                 "when he is asked he answers completely, and the first person to ask him "
                 "twice becomes the person he tells things to unprompted for the rest of "
                 "the story.",
        "rumor": "Read as sullenness, or as the natural quietness of a man in his position. "
                 "Luiza believes he is shy and has spent years being gently encouraging in "
                 "a way that has never once addressed the actual problem.",
        "learnable_from": [
            {"route": "person", "who": "sebastian", "how": "he will say it plainly, once, if asked why he does not speak up", "yields": "truth"},
            {"route": "person", "who": "luiza", "how": "her long-held theory about him", "yields": "rumor"},
            {"route": "observation", "what": "watching him start to say something in a crowded room and stop", "yields": "rumor"},
        ],
    },
    "the_leg": {
        "truth": "A Lycan, four years ago, on the road below the Fallow Plot at dusk. He "
                 "got away because somebody else did not, and he knows exactly who and has "
                 "never said so, because the family still lives here and has been told a "
                 "different story that is kinder to everyone including him. This is the one "
                 "subject on which he will lie to a direct question, and he lies badly, and "
                 "it is the only time his sentences run on.",
        "rumor": "The account in circulation is a farm accident, and it has been in "
                 "circulation long enough to be believed by people who were alive when it "
                 "happened. Anton's version is that he was careless.",
        "learnable_from": [
            {"route": "person", "who": "villagers", "how": "the farm-accident account, which everyone repeats", "yields": "rumor"},
            {"route": "person", "who": "iulian", "how": "he has never believed it and will say the timing does not work", "yields": "rumor"},
            {"route": "observation", "what": "the scarring, if he is ever seen with the leg uncovered, which does not resemble any machine", "yields": "truth"},
            {"route": "person", "who": "sebastian", "how": "only after real trust, and he will tell it looking out of the window rather than at you", "yields": "truth"},
            {"route": "document", "what": "village_parish_register", "yields": "truth"},
        ],
    },
    "weaknesses": {
        "truth": "Being asked. Being asked a second time, which converts him permanently. "
                 "Being told he was right in front of other people. Being consulted before "
                 "he is helped rather than after. And the thing nobody has tried: being "
                 "given something to do that uses what he has instead of working around "
                 "what he lacks.",
        "rumor": "The village's approach is kindness of the wrong kind — moving his chair "
                 "for him, fetching things, speaking slightly louder. All of it lands as "
                 "the same error and none of it costs him enough to complain about.",
        "learnable_from": [
            {"route": "observation", "what": "the difference between how he responds to being helped and to being asked", "yields": "truth"},
            {"route": "person", "who": "luiza", "how": "she has been doing the wrong kind of kindness for years and can describe it in detail without recognising it", "yields": "rumor"},
        ],
    },
})

# ── EUGEN ──────────────────────────────────────────────────────────────────

EUGEN_PUBLIC = {
    "_note": PUB_NOTE,
    "identity": "Eugen | thirties to forties | male | errand runner for the church. He "
                "fetches and carries for Mother Miranda's needs, which the village "
                "considers an honour and does not enquire into.",
    "addresses_others": {
        "everyone": "Politely, briefly, and by name, while already moving past them.",
        "miranda": "'Mother Miranda', with the correct devotion and no elaboration.",
        "outsiders": "'friend', which he uses to avoid learning a name.",
    },
    "look": "The kind of face that is difficult to describe immediately after seeing it — "
            "medium everything, no distinguishing feature, the sort of man who is "
            "remembered as having been present rather than as having been there. Neat, "
            "unremarkable, tidy hair. He is always carrying something, and the something is "
            "always covered.",
    "wears": "Plain and clean and slightly better than a farmer's, with a coat that has "
             "deep inside pockets. Good boots, better than anyone else's in the village, "
             "well worn on the uppers from walking rather than working.",
    "scent": "Clean cloth, cold air, and — faintly, if you are close and you know what you "
             "are smelling — carbolic and something chemical and sharp that does not belong "
             "in a village.",
    "voice": "Level, mild, and economical. He deflects rather than refuses, and he does it "
             "so smoothly that people do not notice they have been steered until later. "
             "Ends conversations by having somewhere to be, which he genuinely always does.",
    "speech_examples": [
        "\"Church business. You know how it is.\"",
        "\"I bring what she asks for. That's the whole of it.\"",
        "\"You'd be better asking someone else. Truly.\"",
        "\"I'd not go up there. That's all I'll say about it.\"",
    ],
    "default_state": "Passing through — on the road, on the church steps, at the edge of a "
                     "gathering with a covered basket, about to be elsewhere. He is present "
                     "in more scenes than anybody notices, and he never sits down.",
    "states": {
        "passing": "Default. Polite, brief, already leaving. Answers one question and not two.",
        "deflecting": "Asked about the errands or the contents. Mild, unbothered, and "
                      "immovable — he offers three different ways of not answering and each "
                      "sounds like an answer at the time.",
        "unnerved": "Somebody has asked something specific and correct. The mildness stays "
                    "but he stops moving, which he otherwise never does, and looks at "
                    "whoever asked it for slightly too long before recovering.",
    },
    "likes": "Being left alone. Predictable routes. People who accept 'church business' "
             "the first time.",
    "dislikes": "Specific questions. Being followed. Being asked what is in the basket. "
                "Anyone who has been to the church at night.",
    "role": "The supply line. He brings Mother Miranda what she asks for and takes the "
            "long way round doing it. A thread which, if pulled, leads directly to the "
            "laboratory — and the only person in the village who walks between the "
            "settlement and the place under the church as a matter of routine.",
    "never_says": [
        "what is in the basket",
        "where he goes before dawn",
        "'I don't know' — he says 'I'd not be the one to ask'",
    ],
    "carry_over": "If he was questioned last scene he takes a different route this scene, "
                  "and if he was questioned twice he stops appearing in the open at all and "
                  "must be found.",
}

EUGEN_PRIVATE = priv({
    "what_he_carries": {
        "truth": "Surgical instruments, sutures, glassware, ether, morphine, and latterly "
                 "restraints. He collects them from the Duke, from the mill, and twice from "
                 "a crate left at the treeline by nobody he has ever seen, and he delivers "
                 "them to the church and leaves them inside the door at the top of the "
                 "stair down. He has never been further than that door. He has heard things "
                 "through it.",
        "rumor": "The village understands that Eugen fetches medical supplies for the "
                 "church, that the church tends the sick, and that this is entirely proper. "
                 "Several people will tell you Mother Miranda healed someone they know, and "
                 "they are not lying.",
        "learnable_from": [
            {"route": "person", "who": "villagers", "how": "the accepted account of the church's medical work", "yields": "rumor"},
            {"route": "person", "who": "duke", "how": "he has sold Eugen most of it and will itemise the list for a price, having noted that it is not the list a sick village needs", "yields": "truth"},
            {"route": "person", "who": "sebastian", "how": "he has logged the schedule, the covered basket, and the deliberately long route past his window", "yields": "truth"},
            {"route": "possession", "what": "the coat's inside pockets, and the carbolic smell that will not come out of the lining", "yields": "rumor"},
            {"route": "observation", "what": "following him, which he will notice", "yields": "truth"},
            {"route": "person", "who": "eugen", "how": "only if cornered with something specific and correct, and only if he has decided the PC is more dangerous to him than she is", "yields": "truth"},
        ],
    },
    "which_man_he_is": {
        "truth": "GM: choose one at session start and lock it. Do not leave it floating and "
                 "do not change it later; the whole value of this thread is that it resolves "
                 "into a specific person.\n\nCOMPLICIT — he knows precisely what she does "
                 "with what he brings, and he serves out of ambition or because he decided "
                 "long ago which side survives. Can be exposed to the village, which "
                 "destroys him, or turned, which is expensive.\n\nCOERCED — he knows enough "
                 "to be permanently frightened. It was explained to him once, in detail, "
                 "with an example. He does what he is told and takes the long way round the "
                 "window so that nobody develops an interest in him. This read is the most "
                 "playable and the most sympathetic.\n\nIGNORANT — he believes he serves the "
                 "church's medical needs and has never connected the restraints to anything, "
                 "because connecting them is a thing his mind refuses to do. A useful idiot, "
                 "and the cruellest version for the player to be the one who tells him.",
        "rumor": "Nobody in the village has considered the question. He is Eugen, he runs "
                 "errands for the church, and that is the whole of the village's model of "
                 "him. Iulian distrusts him on general principle and cannot say why, which "
                 "irritates Iulian considerably.",
        "learnable_from": [
            {"route": "person", "who": "iulian", "how": "an instinct with no evidence behind it, correct in direction", "yields": "rumor"},
            {"route": "person", "who": "eugen", "how": "the read reveals itself under specific pressure — a complicit man negotiates, a coerced man warns you, an ignorant man is confused. Which one he does IS the answer", "yields": "truth"},
            {"route": "observation", "what": "how he behaves at the church door: does he go in, hesitate, or refuse to look at it", "yields": "truth"},
            {"route": "document", "what": "miranda_supply_requisitions", "yields": "truth"},
        ],
    },
    "the_route": {
        "truth": "He leaves before dawn twice a week, takes the east track rather than the "
                 "road, and crosses to the church from behind rather than up the steps. The "
                 "reason is not secrecy about the church — everyone knows he serves it — but "
                 "that the east track does not pass Luiza's window. He has arranged his "
                 "entire working week around not being watched by a man he has never spoken "
                 "to.",
        "rumor": "Anyone who has noticed assumes he takes the east track because it is "
                 "shorter, which it is not, or to keep out of the wind, which it does.",
        "learnable_from": [
            {"route": "person", "who": "sebastian", "how": "the entire schedule, unprompted, to anyone who has asked him anything twice", "yields": "truth"},
            {"route": "observation", "what": "walking the east track and finding it longer", "yields": "truth"},
            {"route": "person", "who": "villagers", "how": "the assumed reason", "yields": "rumor"},
        ],
    },
    "weaknesses": {
        "truth": "Specificity. He has a prepared deflection for every general question and "
                 "nothing at all for a precise one — name the ether, name the restraints, "
                 "name the day of the week, and the mildness holds while the movement stops. "
                 "Also: being offered a way out that is more frightening to refuse than to "
                 "accept, which is the only currency he understands, because it is the "
                 "currency he was bought with.",
        "rumor": "He is generally held to be a closed door and not worth pushing on, which "
                 "is exactly the impression he has spent years cultivating.",
        "learnable_from": [
            {"route": "observation", "what": "the difference between how he answers a general question and a specific one", "yields": "truth"},
            {"route": "person", "who": "villagers", "how": "the impression he has cultivated", "yields": "rumor"},
            {"route": "person", "who": "duke", "how": "he has watched Eugen buy things and formed a view of what moves him", "yields": "rumor"},
        ],
    },
})

# ── population-level reference (narrator-visible, no secrets) ──────────────

VILLAGERS = {
    "_note": "Narrator-visible population reference. Contains NO secrets — anything gated "
             "belongs in an individual's private card or in the vault. Loaded as world "
             "material rather than as a character.",
    "population": {
        "size": "Between eighty and a hundred and fifty souls at the start, and falling. "
                "Iulian says ninety-three six months ago. He is counting the Enescus, who "
                "are gone.",
        "character": "Agrarian, insular, and centuries old by deliberate isolation. No "
                     "newspapers — Mother Miranda outlawed them. No outside contact. "
                     "Technology runs from medieval to early twentieth century depending on "
                     "the household and on what the Duke has been willing to sell.",
        "competence": "Uneducated by outside standards and extremely capable by local ones: "
                      "farming, animal husbandry, building, herbalism, basic metalwork. "
                      "Nobody here needs help with anything practical and everybody needs "
                      "help.",
    },
    "faith": "Faith in Mother Miranda is not a belief the village holds; it is the "
             "infrastructure it runs on. It replaces government, law and medicine. Most "
             "villagers would describe themselves as faithful by choice and would be "
             "largely right — the Mold in the soil and the water produces a subtle "
             "compliance bias, not mind control, and the distinction matters. Questioning "
             "her publicly costs everything instantly. Privately, with the right person, it "
             "is possible.",
    "what_they_know_and_do_not_say": [
        "Neighbours 'go to serve Mother Miranda' and do not come back. Most do not ask. "
        "The few who ask stop asking.",
        "The Lycans are 'wolves' or 'the cursed ones'. The village knows something is in "
        "the woods; the official account is divine punishment for the unfaithful.",
        "The fishermen work the reservoir edges, know to stay in the shallows, and "
        "sometimes see something they do not discuss.",
        "The elders remember traditions that predate the cult and will not speak of them "
        "where they can be overheard.",
    ],
    "strangers": "Rare enough to be an event. Suspicion first and hospitality grudgingly "
                 "second, and mountain culture genuinely holds both. Trust is built by "
                 "helping with tangible problems — the fence, the livestock, a sighting — "
                 "by sharing food or drink, and by being seen with Elena or Luiza. It is "
                 "lost by getting somebody killed, by open association with the Lords, and "
                 "by entering homes uninvited.",
    "how_information_moves": "Through Luiza's house, and nowhere else. Gossip, warnings and "
                             "plans all happen at that table. Being welcome there is the key "
                             "to the entire social network of the valley, and the corner by "
                             "the window has heard all of it.",
    "the_fallow_plot": "The outermost section of the settlement, where the attacks land "
                       "first and hardest. Elena and Leonardo live there. If the Fallow "
                       "Plot goes, the village knows it is next, and everybody in it knows "
                       "that too.",
    "the_clock": "As the ceremony approaches, people disappear and the population shrinks. "
                 "The NPCs notice. The mood moves from fearful-but-functional through "
                 "desperate to collapsing. Iulian counts aloud. Anton counted first and has "
                 "never told anyone he was doing it.",
    "unnamed_roles": {
        "_note": "Generate in scene as needed. Each carries what it plausibly knows.",
        "farmers": "The majority. Practical, exhausted, and unwilling to discuss the woods.",
        "shepherds": "Losing animals. The raids start with them, so they see the pattern "
                     "first and are believed last.",
        "the_miller": "At Otto's Mill, near the Stronghold. He hears things at night and "
                      "has stopped mentioning it.",
        "fishermen": "The reservoir edges. They stay shallow for a reason they will not give.",
        "the_blacksmith": "The only one. Repairs tools, and weapons if he decides he likes you.",
        "midwives_and_herbalists": "Village medicine and herb gardens. Some of their "
                                   "knowledge is Mold-adjacent and none of them know it.",
        "the_brewer": "Somebody makes the țuică, and the țuică is the social lubricant of "
                      "the whole valley.",
        "children": "Play where they should not, see what adults dismiss. Information "
                    "sources and potential victims in the same breath.",
        "elders": "Remember what came before the cult. Will not say so publicly.",
    },
    "vasile": "Luiza's husband. Left the village to seek help and has not returned, which "
              "everybody knows and nobody raises in front of her. Absent at the start — not "
              "a character in play so much as a hole in one.",
}


def write(rel: str, payload: dict) -> None:
    path = ROOT / "data" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"  = {rel} (exists, left alone)")
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  + {rel}")


def main() -> int:
    write("characters/anton/private.json", ANTON_PRIVATE)
    write("characters/roxana/public.json", ROXANA_PUBLIC)
    write("characters/roxana/private.json", ROXANA_PRIVATE)
    write("characters/sebastian/public.json", SEBASTIAN_PUBLIC)
    write("characters/sebastian/private.json", SEBASTIAN_PRIVATE)
    write("characters/eugen/public.json", EUGEN_PUBLIC)
    write("characters/eugen/private.json", EUGEN_PRIVATE)
    write("villagers.json", VILLAGERS)

    # Vasile's fate is GM-only and unresolved. It belongs in the vault.
    vault_path = ROOT / "data" / "vault.json"
    vault = json.loads(vault_path.read_text(encoding="utf-8"))
    ws = vault.setdefault("world_secrets", {})
    if "vasile_fate" not in ws:
        ws["vasile_fate"] = (
            "UNRESOLVED — choose at session start and lock it. Luiza's husband, who left "
            "to seek help. ALIVE: hiding injured at Otto's Mill or the outskirts, waiting "
            "for an opening; the hardest outcome to reach and the most rewarding, and "
            "Luiza's reaction alone justifies the quest. TRANSFORMED: bitten on the "
            "journey, now among the Lycans in the Stronghold with his identity gone. DEAD: "
            "killed in the Forbidden Woods, body discoverable. CAPTURED: taken by "
            "Heisenberg's scouts for Soldat conversion. Whichever the player discovers "
            "first becomes canon; do not pre-resolve it in narration before then."
        )
        vault_path.write_text(
            json.dumps(vault, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print("  + vault.json: world_secrets.vasile_fate")
    else:
        print("  = vault.json vasile_fate (exists)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
