---
name: project-sight-head-holds-not-boresight
description: body-layer's advance_sight_head already enforces "zero/None aim means hold, not boresight" independently of OpticState — check there before assuming a None-aim leak is unguarded.
metadata:
  type: project
---

When reviewing a 9K113/sight-aim fix in `body-layer/src/belief/sight_head.py`/`optic_policy.py`,
`advance_sight_head` (`sight_head.py`) is a second, independent enforcement point for "a missing
desired aim means hold current direction, never snap to boresight" — not just a property of
`OpticState.look_azimuth_deg`/`look_elevation_deg`'s own None-handling in `optic_policy.py`.

Specifically: when `desired_body_az_deg`/`desired_body_el_deg` are both `None` and `aim_source ==
"belief"` (nothing sight-tier desired this poll, no seen/held track), the head holds its own
current world direction (`goal_az_deg, goal_el_deg = current_world_az, current_world_el`) rather
than converging toward a fabricated `(0, 0)` belief goal. Only `not observ_observed` (OBSERV
genuinely off) returns a fresh all-`None` `SightHead()` — the real boresight reset.

**Why this matters for review**: if an `optic_policy.py` fix leaves a transient internal `None` on
`OpticState` that never escapes as an `OpticDecision` (e.g. a look-finished commit that nulls the
aim then immediately re-picks a target in the same call), it's worth checking whether `sight_head.py`
would have caught a leak anyway — it's a second line of defense for rule 3 ("a zero/None read is
stop-moving/hold, not recentre"), not reliant on `optic_policy.py` getting every internal `None`
right. Found while reviewing `[[BL-B98]]`'s fix (`plans/9k113-scan-procedure/review-bl-b98.md`,
2026-10-25) — the fix only touched `optic_policy.py`/`body.py`, and confirming `sight_head.py`'s
own independent hold-not-snap logic was the fast way to rule out a class of leaks without having
to mutation-test every transient `None` assignment in `optic_policy.py` individually.

See also [[project_docstring_vs_own_measured_discovery]] for this codebase's habit of keeping
pre-fix behaviour described in docstrings alongside the fix, which is what made tracing this fast.
