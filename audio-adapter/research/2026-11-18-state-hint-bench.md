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
