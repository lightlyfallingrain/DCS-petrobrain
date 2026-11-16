---
name: feedback-tuning-clamp-covers-one-branch-not-both
description: a tunable constant's docstring claimed to bound "any single write regardless of a bad gain estimate," but the clamp was only wired into the gain-based branch of an if/else -- the no-gain-yet branch wrote an unclamped sibling constant, invisible because every test ran at default values where the two constants happen to be ordered correctly
metadata:
  type: feedback
---

BL-B118 (`plans/bl16-qnh-mission-start/plan.md`, `body-layer/src/belief/altimeter_qnh_sync.py`)
review: `advance_altimeter_qnh_sync`'s delta computation is an if/else -- a gain-based branch
wrapped in `_clamp(..., -ALTIMETER_QNH_MAX_STEP, ALTIMETER_QNH_MAX_STEP)`, and a no-gain-yet
branch (`delta = sign(error) * ALTIMETER_QNH_CALIBRATION_STEP`) that is **not** clamped at all.
`ALTIMETER_QNH_MAX_STEP`'s own docstring/rendered `defaults.toml` comment states it "bounds any
single write regardless of a bad gain estimate -- the real safety net against a runaway delta."
That claim is false for the second branch. It happened to hold only because the two constants'
**defaults** satisfy `CALIBRATION_STEP (0.05) < MAX_STEP (0.3)` -- their declared `lo`/`hi` bounds
do not (`CALIBRATION_STEP` up to 0.2, `MAX_STEP` down to 0.05), so a legal tuning-file override
could invert the relationship and send a write 4x the stated cap. No test caught it because every
test in the file runs at code defaults, which is exactly the one combination that masks the gap.

**Why this is worth a general lesson:** this is the project's named "cross-key coupling" risk
(`body-layer/CLAUDE.md`'s "Tuning" section, `.claude/agents/reviewer.md`'s own checklist item) in
a new, cheaper-to-miss shape -- not two *existing* constants gaining a new relationship, but **two
new constants in the same commit, where the plan's own tunables table names the ordering in prose
("must be well under") and the code never enforces it.** A docstring that says a clamp is
unconditional is a testable claim; "regardless of X" is the tell to check against the actual
branches, not just the one branch under discussion when the sentence was written.

**How it was caught:** read every branch of the delta computation line by line against the
`MAX_STEP` docstring's own wording, independently of the implementer's own log (which stated "no
coupling function added... trusting the plan's stated check" -- the plan's "no cross-key
relationship" line and its own tunables table's "must be well under" phrasing for a *different*
pair of the same eight constants directly contradict each other, which only shows up if you read
the table, not just the implementer's summary of it).

**How to apply:** when a module declares a tunable whose docstring claims to bound "every
write"/"any single Y" unconditionally, grep every call site of the value it is meant to bound
(not just the one the surrounding prose is discussing) and check each one is actually passed
through the clamp -- an if/else with the clamp in only one branch is the exact shape this misses.
Then check whether the two constants' own `lo`/`hi` ranges, not just their defaults, preserve the
stated ordering; if not, say whether anything (`tuning._check_*_coupling`, or a clamp around the
unclamped branch) actually enforces it, per `.claude/agents/reviewer.md`'s own cross-key-coupling
instruction. See also [[feedback_bounded_magnitude_isnt_optional_severity]] for the sibling lesson
that a magnitude bound violated only under a deliberate manual override is still a real finding,
not a dismissable one.
