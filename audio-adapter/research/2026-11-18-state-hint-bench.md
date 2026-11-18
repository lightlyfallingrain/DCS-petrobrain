# State-dependent prompt hint: bench on the Stage 3c corpus

**Date:** 2026-11-18 · whisper.cpp (Homebrew `whisper-cli`), `ggml-small.en`, Apple Silicon · 164
clips (41 phrases × 4 takes), the user's own voice, recorded 2026-11-18 · real matcher
(`command_matcher.match_transcript`) with the 18 rules `body-layer/config/rules/flight.lua` pushes
at `main` `b7424113` · tool: `tools/phrase_bench.py`

Answers `[[BL-17]]` Stage 3c's measurement (D17, U23) before any of 3c is built. The user confirmed
every clip is complete; background noise in them is normal and expected.

## Headline

| prompt | ok | miss ("say again") | WRONG command |
|---|---|---|---|
| **A — today's full prompt** | **141** | 22 | **1** |
| B — flight words first | 138 | 24 | 2 |
| C — out-of-state words removed | 129 | 32 | 3 |

**Reordering buys nothing and removing words costs accuracy and safety.** Both B and C add a new
wrong command, which fails U23's threshold outright. Whisper already has every command word in the
prompt; moving them earlier does not change what it hears, and removing words drops bias the
non-flight phrases rely on.

## Wrong commands

| prompt | clip | heard | matched |
|---|---|---|---|
| A, C | `right_3` | "alright" | `point` |
| B | `level_flight_1` | "flight" | `point` |
| B, C | `level_flight_2` | "pilot flight" | `report` |
| C | `altitude_three_two_zero_radar_1` | "altitude 3 to 0 radar" | `set_altitude` (wrong value) |

## What the full prompt still misses — specific words, not ordering

| phrase | ok/4 | heard as |
|---|---|---|
| turn left thirty | 0 | "turn left" — "thirty" dropped every time |
| heading two seven zero | 1 | "heading to seven zero" ×3 |
| hold alt | 2 | "hold out" |
| speed max | 2 | "speed x", "speed maximum" |
| forward | 2 | "from what", "from about" |
| level off | 2 | "a medal off", "well off" |
| right | 3 | "alright" (→ `point`, the one wrong command) |
| left | 3 | "lift" |

Composed number words are deliberately absent from the prompt (`rule_patterns.rule_words`
docstring); "thirty" is the first measurement of that gap on the user's voice. Digit-by-digit
("turn left three zero") scores 3/4.

## Caveats

- One voice, four takes per phrase, one model, no cockpit noise beyond what was recorded.
- The corpus predates the user's 13:53 wording change in `flight.lua`: "heading 315" now needs
  "turn/fly heading", and "level off" is now "stop turn". Those clips were scored against what the
  phrase triggers *today* (legacy `scan_bearing_deg` and `observ_off`), so their rows measure
  hearing, not the flight command.

## Decision

User, 2026-11-18: 3c deferred — the improvement is minimal or negative; it may be needed once the
vocabulary grows past whisper's 224-token prompt cap, when ordering decides which words survive the
truncation. The misses above are taken on as targeted fixes instead.

## Follow-up — the user's answers on the misses (2026-11-18, verbatim)

> - "alt" -> use "altitude" that's what I'll say
> - numbers as words -> either get whisper to STT the to numbers ditecly or then we use individual
>   digits like "three zero" to say 30.
> - when numeric input is expected (heading <number>, speed <number>, etc) fuzzy match the part
>   after the verb to numbers since that is expected there.
> - "alright" is not a word we use -> map to "right"

## `[[BL-B129]]` implementation: before/after bench

Re-run `tools/phrase_bench.py`, same corpus (`data/corpus/bl17-stage3c/`, `ggml-small.en`), on the
same 18 `flight.lua` rules before and after D1/D3/D4/D5's matcher/rule-file changes (D2 shipped no
code change, see below). "Before" is the matcher/rules at this plan's own base commit (`c59087f8`);
"after" is the implementation branch.

| prompt | ok (before → after) | miss (before → after) | WRONG (before → after) |
|---|---|---|---|
| A — today's full prompt | 141 → 139 | 22 → 25 | **1 → 0** |
| B — flight words first | 138 → 136 | 24 → 26 | 2 → 2 |
| C — out-of-state words removed | 129 → 128 | 32 → 34 | 3 → 2 |

**WRONG drops to 0 on A_full** (`right_3`'s "alright" → `point` is fixed by D4) and C_full's own
WRONG drops by one too (`altitude_three_two_zero_radar_1`'s "altitude 3 to 0 radar" now parses to
the *correct* value, 320, via D3's "to"→"two" homophone, rather than a wrong one).

**A_full's own `ok` count drops by 2, not up** — traced clip by clip (`bench_before.json`/
`bench_after.json`, not committed, see this implementer's report for the exact diff): every
kind-change (`ok`↔`miss`↔`WRONG`) between the two runs is one of —

- `right_3`: `WRONG` → `ok` (D4's own fix).
- `heading_three_one_five_0`: `miss` → `ok`; `forward_0`: `ok` → `miss`. Both clips' own spoken
  words are untouched by this plan — the *only* difference in `A_full`'s prompt text between the
  two runs is "alt" dropped from `set_altitude`/`hold_altitude`'s own `rule_words` (D1's own
  mechanism: the prompt bias follows the grammar automatically). Whisper's prompt-conditioned
  decoding is sensitive to the whole prompt, not just the words relevant to a given clip, so
  removing one word measurably shifts decoding on *unrelated* audio too — a known property of this
  mechanism (`vocabulary.to_prompt`'s own docstring already measures a similar effect from
  reordering), not a defect in D1.
- `hold_alt_0`, `hold_alt_2`, `alt_one_five_zero_3`: `ok` → `miss`. All three are recordings of the
  deprecated "alt" phrasing D1 explicitly retires (the user: *"'alt' -> use 'altitude' that's what
  I'll say"*) — losing ground on a phrasing the plan deliberately stops biasing the recogniser
  toward is the intended, foreseen cost of D1, not a regression to fix. These clips no longer
  represent the spoken form the user commits to using.

Net: the two `ok` count drops and the two `ok` count gains cancel except for a net -2, entirely
attributable to the three deprecated-"alt" clips (partially offset by the unrelated prompt-shift
noise, which washes out to zero here). **Flagged rather than silently reported as "ok count up"**,
since the plan's own acceptance line names that direction and this run does not meet it literally
— the three-clip loss is the direct, intended consequence of D1, not a new defect introduced
alongside it.

## D2: no prompt change shipped

Tried the prompt experiment per D2 step 1 — `_PROMPT_FRAMING` widened to `"Helicopter crew
intercom, pilot to gunner. Numbers are read as numerals, for example 270, 30, 320."` — and
re-benched (`A_full`: 136 ok / 27 miss / 1 WRONG, worse on every count than the unmodified "after"
136→139/27→25/1→0, and `turn_left_thirty` stayed 0/4, "thirty" still dropped every time: one clip's
heard text changed slightly, "turn left at 30.", but still an unconsumed extra word with no match).
**Fails D2's own ship condition** ("improve... and no drop on any other phrase") on both halves —
no improvement on the targeted phrase, and a drop elsewhere. **No prompt change shipped.** The
spoken form for composed numbers stays individual digits ("three zero" for 30), which already
scores 3/4 on this corpus and is unaffected by anything in this plan — the user should keep saying
digits rather than "thirty"-style number words.

## D5: added mid-implementation (user-approved 2026-11-18, "as recommended")

`research/2026-11-18-whisper-model-sweep-flight-corpus.md` (on `main`) found a bare direction word
plus a number ("right 45"/"right forty five", from whisper dropping "turn") resolving to `point` on
`base.en`/`medium.en` -- the same mechanism as `right_3`'s "alright" → `point` above, generalised:
`_parse_point_slots`'s four parsers each scan the whole transcript independently, so a `relative`
slot resolving on its own left a trailing, unaccounted-for number unchecked. Fixed by
`command_matcher._has_unaccounted_number` (a number not immediately followed by its own unit
marker, "km"/"kilometres"/"o'clock", blocks the `point`/`"what"` branches from resolving) --
verified against this corpus (A_full unaffected, `small.en` does not exhibit this specific drop
here) and against `right 45`/`right forty five`/`left 30` directly (now `token=None`, "say again"),
with a counterfactual confirming a legitimate `relative`+distance phrase ("look right 5
kilometres") still resolves.
