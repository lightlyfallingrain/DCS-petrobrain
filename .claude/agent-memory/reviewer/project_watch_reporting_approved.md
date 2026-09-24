---
name: project_watch_reporting_approved
description: watch-reporting (feature/watch-reporting) reviewed APPROVED clean — all four flagged judgement calls verified true against source, plus one recurring ROADMAP-timing observation.
metadata:
  type: project
---

`feature/watch-reporting` (head `0b1e394`) reviewed against `plans/watch-reporting/plan.md` —
APPROVED, no required fixes. All four orchestrator-flagged judgement calls held up under direct
source inspection, not just the implementer's summary:

- **Watched-only event kinds** (`CONTACT_MOTION_CHANGED`/`CONTACT_RANGE_CROSSED`/
  `CONTACT_ENGAGEMENT_CHANGED`) are correctly forced singleton in `belief/callouts.py`'s
  `group_candidates` (alongside the pre-existing `CONTACT_CLASSIFICATION_CHANGED` precedent) and
  still reach speech via the singleton `_render_group` → `route_event` path — not silently dropped.
- **`follow`'s slot parsing runs before the generic phrase table** in
  `audio-adapter/src/command_matcher.py` — real collision avoided (`"follow two o'clock"` vs.
  `"report"/"scan two o'clock"`), and the reorder doesn't shadow `"follow nearest"`/bare `"follow"`
  because those parse to zero slots and still fall through.
- **`FOLLOW_MATCH_FLOOR=3.0`/`W_FOLLOW_CLOCK=0.6`** are self-consistent: worst-case clock-only score
  is `6 * 0.6 = 3.6 > 3.0`, correctly refused.
- **The threat class-rollup's low join rate degrades honestly**: `threat.py`'s `envelope_for`
  returns `None` when a class has no surviving row (dict `.get`, no default), and `contacts.py`'s
  seventh block treats `None` as "skip the whole engagement test" — silence, never a wrong default
  in either direction.

Also independently verified: the `bearing_degrees`→`slots` migration survives a confirm-band round
trip (`PendingConfirmation.slots` is populated and threaded through `handle_command` on affirm);
`belief/threat.py` imports nothing from `perception.source` and only accepts `ClassificationBelief`;
Decision 5a-i's uncertainty-derived deadband and 5a-ii's asymmetric LOS dwell match the plan's
described Schmitt-trigger shape exactly, read directly in `contacts.py`'s sixth/seventh `tick`
blocks (not just inferred from passing tests).

**One recurring process pattern worth watching for on future reviews**: this project's Stage-5
"prose and roadmap" commits write `ROADMAP.md`/`todo.md` entries claiming a feature is
"merged"/"DONE" *before* the actual merge (Reviewer/DoD/user approval still pending) — harmless
once the branch does merge, but worth flagging rather than treating as a factual error, and worth
checking these entries don't get taken as done if a review sends work back to Implementer for
revision. First noticed here; check for the same pattern on future features' Stage-N "prose and
roadmap" commits.
