# The Valley

A terminal-aesthetic RPG engine built around one idea: **the model writing the
prose is not allowed to know the secrets.**

Every other RP frontend hands one model the whole setting and hopes it pretends
not to know the twist. Models are bad at that — the knowledge leaks through
word choice, emphasis, and which details get lingered on. So this runs two
models with an information barrier between them:

- **The GM** holds the vault, the fragment map, and the full character cards.
  It adjudicates actions, decides what may be released, and emits a structured
  briefing packet. It never writes a word the player reads.
- **The narrator** writes every word the player reads, and sees only the
  briefing plus what has already been released.

The barrier isn't a prompt instruction the model might drift from. The secrets
are simply not in the narrator's context, so there is nothing to leak.
`tools/test_wall.py` asserts exactly that, and it runs offline for free.

## Setup

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml   # then edit it
python tools/seed_data.py            # writes starting data files
python tools/test_wall.py            # optional: verify the barrier holds
python main.py
```

## Providers

The GM and the narrator are configured independently and can run on entirely
different backends. That isn't a novelty — it's the recommended setup. The GM
fills in a fixed schema; the narrator writes. A cheap fast model does the first
job well, and the second is worth paying for.

| Provider | Notes |
|---|---|
| `anthropic` | Claude direct. Only backend with both guaranteed schema forcing and explicit prompt caching. |
| `openrouter` | One key, every model. Samplers work. Schema forcing depends on the model routed to. |
| `openai`, `deepseek`, `groq`, `together` | Direct, OpenAI wire format. |
| `local` | llama.cpp, LM Studio, text-generation-webui, vLLM, TabbyAPI. |
| `ollama` | Ollama's OpenAI-compatible endpoint. |
| `custom` | Anything else with `/v1/chat/completions`. Set `base_url`. |

Three capabilities vary by backend, and each degrades rather than breaking:

**Schema forcing.** Where the backend supports constrained decoding, the
briefing packet *cannot* come back malformed. Where it doesn't, the GM is asked
for JSON, the result is validated, and one repair attempt is made with the
specific errors quoted back. A failure costs one turn, never the save.

**Prompt caching.** The vault and character cards are byte-identical every turn
and sit above a cache breakpoint. Anthropic bills that at roughly a tenth of
list after the first call; OpenAI and DeepSeek pick it up implicitly; local
models don't care. Set `caching: explicit` when routing to Claude through
OpenRouter, which passes breakpoints upstream.

**Sampler knobs.** `temperature`, `top_p`, `top_k`, `min_p`,
`repetition_penalty` work on OpenRouter, OpenAI, and local models — and are
*rejected outright* by frontier Claude, which steers via prompt and `effort`
instead. Presets carry both, and the provider layer sends only what the target
accepts, so one preset file works everywhere.

## Presets

A preset is a **voice**, not a sampler config: prose style instructions, a
reasoning effort level, a token budget, and optionally samplers. Editable YAML
in `data/presets/`. Built-ins: `balanced`, `horror`, `intimate`, `combat`,
`terse`. Switch mid-session with `/preset horror`.

## Authoring

The engine is done; the game is the data. In rough order of leverage:

1. **`data/vault.json`** — fill in the TODOs. The game is exactly as
   interesting as what is hidden here, because this is the only thing the
   narrator can be surprised by.
2. **`data/characters/<id>/public.json` + `private.json`** — split each
   character. Public is what you'd know after five minutes in a room with
   them; private is everything that has to be earned. `moreau` is the worked
   example.
3. **`data/fragment_map.json`** — sensory triggers and what each memory leads
   to. Include dead ends; not every thread should go somewhere.
4. **Portraits** — drop `<mood>.webp` into `data/characters/<id>/portraits/`.
   The GM picks a mood each turn via `portrait_state`; missing art degrades to
   a name and a label rather than a broken layout.

Trust gates are the mechanism that makes the narrator's understanding deepen
alongside the player's. When the GM writes `moreau.capability` into
`reveal_this_turn`, that private section joins the narrator's card permanently.
Before that moment the narrator has never seen it — so its prose genuinely
cannot hint at it.

## Layout

```
main.py                  pywebview shell + threaded bridge
engine/
  wall.py                the turn loop
  gm.py                  GM prompt + briefing request
  narrator.py            narrator prompt + streaming
  schemas.py             the briefing packet schema (the Wall's contract)
  state.py               state, saves, and the public/private card split
  presets.py             voices
  commands.py            slash commands
  promptfmt.py           shared prompt JSON formatting
  providers/
    base.py              Provider interface + capability model
    anthropic_provider.py
    openai_compat.py     OpenRouter / OpenAI / local / everything else
    validate.py          JSON Schema subset checker for the repair path
ui/                      index.html, style.css, app.js
data/                    world, PC, vault, fragments, characters, presets, saves
tools/
  seed_data.py           write starting data files
  test_wall.py           verify the barrier — offline, free
```

## Commands

`/help` in-app. `/save`, `/load`, `/preset`, `/status`, `/journal`,
`/providers`, `/model narrator <name>` to hot-swap without restarting,
`/feedback` to steer the next turn. F1–F5 for panels, F9 quicksave, F5 shows
the GM's raw briefing packet when `dev_mode: true`.

## Notes

`/undo` removes the last exchange from history but does **not** roll back state
changes or revelations — once the narrator has been told something, it has been
told. Use a save for a clean rewind.
