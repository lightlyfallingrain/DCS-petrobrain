# Whisper model sweep on the flight-command corpus

**Date:** 2026-11-18 · whisper.cpp (Homebrew `whisper-cli`), Apple Silicon · corpus: 164 clips (41
phrases × 4), the user's own voice, `data/corpus/bl17-stage3c/` · today's full prompt
(`vocabulary.to_prompt` with every pushed rule word) · real matcher with the 18 `flight.lua` rules
at `main` `b7424113` · scored as in `2026-11-18-state-hint-bench.md` (ok / miss = "say again" /
WRONG = a different command or value). Clips run one at a time after a warm-up call; another
whisper bench was running concurrently, so absolute latencies read slightly high — the ratios hold.

Follows `2026-09-19-whisper-model-sweep.md`, which picked `small.en` on the old scan/watch
vocabulary. This corpus is flight commands with spoken numbers, which that one never had.

| model | ok | miss | **WRONG** | latency med / p90 / max |
|---|---|---|---|---|
| `tiny.en` | 120 | 34 | **10** | 0.23 / 0.25 / 0.29 s |
| `base.en` | 126 | 28 | **10** | 0.29 / 0.33 / 0.52 s |
| **`small.en`** | **141** | 22 | **1** | 0.49 / 0.51 / 1.50 s |
| `medium.en` | 142 | 15 | **7** | 1.12 / 1.16 / 1.43 s |

**`small.en` stays.** The user's priority is correctness, then speed (2026-11-18). `medium.en`
gains one correct clip and converts seven "say again"s into commands, but six of those are *wrong*
commands, at 2.3× the latency. `tiny.en`/`base.en` are faster by ~0.2 s and ten times as unsafe.

## Where the wrong commands come from

Mostly **wrong numbers**, not wrong verbs — the larger model hears a number more confidently and is
more often confidently wrong:

- `medium.en`: "turn right one two zero" → "one two **three**" ×2; "altitude three zero zero
  barometric" → "three zero barometric" (30); "speed two two zero" → "speed to to show"
  (→ `speed_step`); "scan ahead" → "scan right".
- `base.en`: "speed two two zero" → "speed two **to** zero" / "2 to 0" (→ a wrong value);
  "speed two hundred" → "speed 202".

**A matcher safety issue, independent of the model:** whenever whisper drops "turn" from "turn
right forty five", the remainder "right forty five" resolves to **`point`** (`base` ×2, `medium` ×1;
`small`'s one wrong command is "alright" → `point` too). A bare direction plus a number becoming a
point command is a wrong command the pilot did not intend.

## Caveat

`[[BL-B129]]` (in progress) changes the matcher: numeric-slot homophones ("to" → two), "alright" →
"right", "alt" dropped. Its fixes remove some of the rows above for every model (base's "two to
zero"), so the sweep should be re-run once it merges — the ranking is not expected to change, since
`small`'s lead is in wrong commands that are mostly misheard digits rather than homophones.
