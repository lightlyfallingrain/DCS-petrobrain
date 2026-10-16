---
name: watchdog-fix-pass-confirmed-by-mutation-roadmap-lag
description: re-review of the AC-B8/BL-B73 FIRING_WATCHDOG_S fix -- both new tests confirmed by reverting the constant and re-running (both fail for the stated reason); also found the roadmap entries (AC-B8.md, BL-B73.md) still state the exact conflation the fix corrected in the source, because the fix touched the source docstring, plan.md and implementation.md but not the roadmap files
metadata:
  type: feedback
---

Fix-pass re-review of `feature/emitter-events` commit `1e6c697` (addressing
[[feedback_watchdog_backstop_conflates_failure_modes]]). APPROVED.

**Mutation check held.** Reverted `FIRING_WATCHDOG_S` 180.0 -> 10.0 and re-ran
`test_firing_receiver.py`: both new tests
(`test_a_unit_still_firing_past_the_former_ten_second_floor_stays_visible`,
`test_dead_during_a_sustained_burst_removes_the_entry_immediately`) failed for the stated reason,
15 others unaffected. Restored, 17/17 pass. The two-test shape
([[feedback_watchdog_timeout_owns_only_the_cases_death_doesnt]] describes it from the implementer
side) really does need both halves — a single test proves only one side of the distinction.

**New finding, not a blocker: a fix that rewrites a claim in several places can still miss one.**
The fix rewrote the conflated "destroyed mid-burst" framing in `firing_receiver.py`'s constant
comment, its module docstring, and added context to `plan.md`'s Risks & Unknowns — but
`aircraft-layer/ROADMAP/AC-B8.md` and `body-layer/ROADMAP/BL-B73.md` still describe the watchdog
using the exact same conflated framing the fix corrected everywhere else ("a watchdog, because a
START whose END never arrives (a unit destroyed mid-burst) must not leave a unit firing forever").
`git log` on both files shows only the original Architect-stage filing (`4b29c8a`) touched them —
neither Stage B commit did. Not a required fix here (status still `#status/open`, nothing reads
roadmap prose as code), but worth a check at milestone-completion time: when a fix corrects a
docstring claim repeated in several documents, grep for the claim's distinctive phrase across
*all* docs the feature touched (plan, implementation notes, roadmap entries), not just the ones the
fix's own diff already lists -- a roadmap entry filed before the defect was found inherits the
wrong account and nothing forces it to be revisited.

**How to apply:** on any fix-pass review of a "docstring/comment was wrong about X" finding, (1)
mutate the fixed value at the source and confirm the new tests actually fail for the stated reason
-- do not trust the names; (2) grep the distinctive wrong phrase project-wide, not just across the
files the fix commit touched, since a roadmap entry minted before the defect was found is a likely
place for the same wrong claim to still live.
