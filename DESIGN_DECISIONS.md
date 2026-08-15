# Design decisions and why

The reasoning behind non-obvious choices in this codebase, written down because
reasoning is the part that gets lost. If a future change looks like an obvious
improvement, check here first — several of these were tried the obvious way and
reverted for a reason.

Companion to `README.md` (what it does) and the design docs in the parent
directory (where the game came from).

---

## The Wall is context shape, not instruction

The narrator never receives the vault, the fragment map, offscreen events, or
unreleased card sections. Not "is told not to use them" — never receives them.

This is the whole architecture. Every other RP setup hands one model everything
and instructs it to pretend; models leak that knowledge through emphasis, word
choice, and which details they linger on, because suppression is not something
a language model does reliably.

**Consequence for maintenance:** any change that puts secret material into the
narrator's context "just so it can avoid it" defeats the design. `narrator.py`
deliberately never calls `state.get_gm_card()`, never reads `state.vault`, and
never reads `state.fragments`. `tools/test_wall.py` asserts this and must keep
passing.

## Dropped the GM's `withhold` list

The original design had the GM emit a list of things the narrator must not
mention. Removed deliberately.

Naming a secret in order to forbid it *puts the secret in the context* — the
exact failure mode the architecture exists to prevent. A model told "do not
mention the cave church below" now knows there is a cave church below, and that
knowledge shapes its prose whether or not it names the thing.

Omission is the only reliable withholding. The GM's discipline is about what it
*includes*, and there is no field for exclusions.

## `state_updates` is a flat path/op/value list

Not a nested dict to deep-merge, as originally designed.

Forced initially by structured-output schema constraints (arbitrary-key objects
can't satisfy `additionalProperties: false`), but kept because it is better:
every mutation is individually loggable, and there is no ambiguity about
whether a nested dict replaces or merges into existing state.

Objects keyed by NPC id became arrays with an `npc` field for the same reason.

## Schema forcing replaced the retry layer

The original design's biggest stated risk was the GM emitting malformed JSON,
and it budgeted a validation-and-retry layer for it.

Where the backend supports constrained decoding (`output_config.format` on
Anthropic, `response_format: json_schema` on OpenAI-compatible), that risk is
gone at the sampling layer — the packet *cannot* come back malformed, and the
"output ONLY valid JSON, no markdown" prompt-begging is unnecessary.

The repair layer still exists in `providers/openai_compat.py`, because local
models and some routed models can't force a schema. It is the **fallback**, not
the primary path: extract → validate → one repair attempt with the specific
errors quoted back. A failure costs one turn, never the save.

## Presets carry samplers AND style — and that reversed once

First decision: style + effort only, no samplers, because `temperature`,
`top_p` and `top_k` are **rejected outright (HTTP 400)** on frontier Claude —
not ignored, rejected.

Reversed when multi-provider support arrived: on OpenRouter, OpenAI, and local
models those knobs work exactly as they always did, and `min_p` /
`repetition_penalty` are genuinely useful on local models.

So a preset carries both, and `Provider.filter_params()` emits only what the
target model accepts. One `horror.yaml` resolves to `effort: high` with zero
samplers on Claude, and three samplers with no effort on a local Mistral. This
is why the capability table exists at all.

**Do not "simplify" by removing either half.** Removing samplers breaks local
setups; removing effort/style breaks Claude setups.

## Capability negotiation, not provider branching

Nothing above `providers/` branches on a provider name. The engine asks
`caps.schema_forcing`, `caps.caching`, `caps.mid_conversation_system`. Adding a
backend means adding an adapter, never editing the engine.

Three capabilities vary and each degrades rather than breaking:

| | best case | worst case |
|---|---|---|
| schema forcing | packet cannot be malformed | prompted JSON + one repair |
| caching | explicit breakpoints, ~10% billing on the vault | full price every turn |
| samplers | all knobs | prompt and effort only |

## Prompt layout is stable-first, for caching

Every caching scheme is a prefix match, so the ordering is load-bearing
regardless of backend:

- **GM:** instructions, then vault + fragments + full cards (cache breakpoint),
  then the turn's volatile state in the message.
- **Narrator:** instructions, then style, then world + present NPCs' cards
  (cache breakpoint), then history, then the briefing.

The vault and cards are byte-identical for a whole session. Anything that
interpolates a timestamp, a turn number, or a UUID *above* a breakpoint
invalidates the cache and silently triples the input bill. Volatile content
goes below the breakpoint, always.

## The briefing rides a mid-conversation system message

`{"role": "system"}` appended after the history, where the model supports it.
It is an operator instruction arriving mid-conversation, and putting it there
means the cached conversation prefix survives — rewriting the top-level system
prompt every turn would invalidate everything.

Backends that don't honour a mid-array system role get it folded into the user
turn by `openai_compat._normalise_roles()`. Silently dropping it would remove
the Wall's briefing from the narrator's context, so that path must never be
allowed to no-op.

## Synchronous engine on a worker thread

The original design ran `asyncio.new_event_loop()` inside the pywebview JS
bridge on every action. pywebview's bridge is synchronous, so that blocks the
UI thread for the duration of two chained model calls — a dead window for the
whole turn, and streaming impossible.

Now: the bridge returns immediately, a worker thread runs the turn, and events
are pushed to the page via `evaluate_js`. A single pump thread serialises those
calls because some webview backends don't tolerate concurrent `evaluate_js`.

No asyncio anywhere. The SDKs' sync clients stream fine, and dropping async
removed a lot of machinery for no loss.

## `ensure_ascii=False` in prompt JSON (`promptfmt.dump`)

Em-dashes and Romanian diacritics go through as themselves rather than
`\uXXXX`. An escape sequence costs several tokens where the character costs
one, and this JSON is a vault plus a dozen character cards resent every turn.
It also reads better to the model.

Lives in its own module so neither side of the Wall imports the other — a
`narrator.py` importing from `gm.py` would be exactly the coupling this design
avoids, even for a two-line helper.

## Trust gates are strings in the revelation log

The GM writes `"moreau.capability"` into `reveal_this_turn`; from the next turn
`state.get_narrator_card()` includes that private section permanently.

The effect worth protecting: the narrator's understanding of a character
deepens at the same rate the player's does, so the prose becomes more complex
as a relationship develops. That isn't a mechanic bolted on — it falls out of
the card split, and it is the most interesting emergent property of the design.

## `/undo` does not roll back state

It removes the last exchange from history only. State changes and revelations
stand, because once the narrator has been told something it *has been told* —
un-telling it is not possible, and pretending otherwise would silently corrupt
the Wall's guarantee. Saves are the clean rewind.

---

## Things deliberately not built yet

Named because they were considered and deferred, not forgotten:

- **Psyche engine** (drives decaying, emotions drifting to baseline). The GM
  currently reports psyche per turn in `npc_direction`, which covers the
  narrator's needs. A tick-based engine is worth adding only if NPC emotional
  continuity across many turns proves weak in play.
- **Memory engine** (episodic/semantic/emotional banks with relevance
  scoring). Deferred because it was a third blocking API call per turn. If
  added, make it fire-and-forget or batch every N turns.
- **Lorebook** (keyword-triggered context injection). The card split already
  does the load-bearing part. Add if authoring grows past what present-NPC
  cards cover.
- **Story / freeform modes.** Easy to add — `Narrator` already takes its
  instructions as a parameter.

## Verification

`python tools/test_wall.py` — offline, free, 27 checks. Run it after touching
anything in `engine/`. It asserts secrets are absent from the narrator's
context *and* present for the GM, so it cannot pass vacuously.
