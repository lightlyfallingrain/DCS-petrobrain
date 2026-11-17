---
name: bl17-collision-check-recalibration-exact-tie-rule
description: BL-17 Stage 4 follow-up (2026-11-17) — audio-adapter's rule collision check was recalibrated from "any hit at or above the floor" to a ratio/SEPARATION_MIN comparison; the exact-tie (both sides at clean 1.0) special case is load-bearing and easy to omit.
metadata:
  type: project
---

`audio-adapter/src/rule_patterns.py`'s collision check (D9/D13, `_is_genuine_collision`) compares
a sample's own rule's `match_pattern_with_ratio` score against the competing rule/legacy
resolution's own ratio on that *same* sample, instead of the old binary "did it match at all
above `_WORD_REPAIR_FLOOR`" criterion.

**The three-way split, and why the exact-tie branch exists:**
- `own_ratio >= 1.0 and other_ratio >= 1.0` → still a collision, even though the gap is `0` (which
  literally reads as "within `SEPARATION_MIN`"). This is deliberate, not an oversight: a flat tie
  at full confidence means the *clean, unperturbed* sample parses identically on both sides, every
  single time it is spoken — not an occasional near-miss. That is the literal "two rules claiming
  the same wording" case from the user's own settled decision (U10, `body-layer/ROADMAP/BL-17.md`),
  and two existing tests (`test_two_rules_that_can_both_match_are_both_disabled`,
  `test_rule_colliding_with_legacy_is_disabled`) pin exactly this scenario. Treating it as an
  ordinary "near tie, leave it to the runtime confirm band" would have silently reversed both.
- `other_ratio - own_ratio >= SEPARATION_MIN` (and not an exact tie) → a genuine confident-wrong
  collision — saying the rule's own wording would make Petrovich act on something else.
- Anything else (gap under `SEPARATION_MIN`, neither side at a clean `1.0`) → a fuzzy near-tie,
  logged at `INFO`, **not** a collision — this is exactly the gap
  `command_matcher.match_transcript`/`_match_rules` already turns into a runtime confirm question
  (E3), a rare mis-hearing rather than a deterministic clash.

**Why:** `own_ratio` is always exactly `1.0` on a rule's own *clean* sample (every literal/word-set
element matches its own canonical word exactly) and always `< 1.0` on a *perturbed* sample (the
probe word is chosen specifically to score below `1.0` against the original). So "both sides at
`1.0`" can only ever happen on a clean sample, and it is the only case where the ambiguity is
deterministic rather than occasional — that is the actual dividing line, not "gap size" alone.

**Measured, real-world consequence** (`plans/speech-rules/plan.md` D9, `plans/speech-rules/
implementation.md` "Stage 4 follow-ups"): running the real 19-rule flight set through the
recalibrated check rescued `set_speed`/`altitude_step`/`level_off` (own `1.0` clearly beats a
fuzzy `0.5`/`0.75` resolution) but kept `straight`/`hvrt_translate_right` rejected — not from the
*clean* "straight" sample (which is rescued, own `1.0` vs `0.77`), but from `straight`'s own
*perturbed* sample ("right," its `_best_probe_word` for "straight"), which matches
`hvrt_translate_right`'s bare-word pattern at an exact `1.0`, confidently beating `straight`'s own
`0.769` self-match on that same sample.

If you touch this check again: run the real 19-rule set and get actual numbers
(`rule_patterns._own_ratio`/`match_pattern_with_ratio` directly) rather than hand-deriving ratios —
`difflib.SequenceMatcher` ratios are not always intuitive (e.g. `ratio("scam","scan") == 0.75`,
`ratio("light","right") == 0.8`), and the *perturbed* sample is frequently the one that actually
drives a real collision, not the clean one the original writeup assumed.
