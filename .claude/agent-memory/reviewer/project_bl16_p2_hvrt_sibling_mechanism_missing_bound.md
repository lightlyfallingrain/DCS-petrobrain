---
name: bl16-p2-hvrt-sibling-mechanism-missing-bound
description: BL-16 Stage P2 review -- when two mode-exclusive channels share a mode-cycle shape (bounded attempts + "mode_blocked" report), check that BOTH got it, not just the one named first; also: a test that demonstrates a "stuck forever" result is evidence of a bug, not proof the behaviour is intended, if the plan's own words promise retry.
metadata:
  type: project
---

Stage P2a (FLT/HVR goal channel) and Stage P2b (HVRT translate) are sibling mode-exclusive
mechanisms in `ai_pilot_wheel.lua`, both needing "cycle the wheel into the mode I need, bounded,
report if it never arrives." P2a's `ai_pilot_goal_tick` got exactly that
(`MODE_CYCLE_MAX_ATTEMPTS`, `"mode_blocked"`, spoken "unable, not ready"). P2b's
`ai_pilot_goal_tick_hvrt` got an unbounded, unreported mode-cycle tap loop instead — the comment
justified it as "only ever reached from `HVR` or already `HVRT`," i.e. "should always converge in
one press," which is the *exact same* one-hop reasoning `MODE_CYCLE_MAX_ATTEMPTS` already exists
to not trust for P2a's own one/two-hop cycles. Worse, the voice-level cancel ("Hold") for the stuck
channel is gated behind the same readiness check that is failing, so there is no recovery path at
all short of unparking.

**How to apply**: when a plan or implementation builds the same shape twice for two sibling
mode-exclusive mechanisms (here: "cycle-then-press, bounded, reported"), grep for the bound
constant's *name* across both call sites, not just read the plan's prose claiming symmetry. A
sibling built without the bound reads as "simpler, because this one's easier" in the diff; it is
actually "the one nobody double-checked got the same safety net."

**Second, separate lesson from the same review**: `ai_pilot_goal_tick`'s own
`mode_cycle_attempts` never resets itself once it reaches the bound (only a *different* `param`
arriving resets it) — so with exactly one goal outstanding, `"mode_blocked"` is a **permanent**
state, zero further presses, ever. The plan's own words ("the goal itself is not dropped --
retried next poll") and the pilot's own answer ("spoken once per exhausted attempt" — implying
more than one attempt-episode is possible) both describe ongoing retry. The implementer's own
test, `test_mode_cycles_before_pressing_then_blocks_after_the_bound`, ticks a 4th time *after* the
bound and asserts **no new press happens** — that assertion is direct proof of the "stuck forever"
behaviour, written as if it were the intended contract, with no Notable Discovery flagging the gap
against the plan's "retried" language. **Read a test's own assertions against the plan's prose,
not just against "does this pass"** — a green test can encode the bug as its own expected value
when nobody compared it back to what was promised. The multi-goal case masks this: `decide_
ai_pilot_wheel`'s rotation changes `active_param` periodically, which resets the counter as a side
effect, so the bug is invisible whenever ≥2 goals are outstanding and only bites the plain
single-goal case — the one nobody thinks to stress since it looks like the easy path.

See also [[feedback_regression_test_empirical_check]] and
[[feedback_test_the_reverse_direction_not_just_the_reported_one]] — same family of "a test exists,
but does its own assertion match the documented contract" check.
