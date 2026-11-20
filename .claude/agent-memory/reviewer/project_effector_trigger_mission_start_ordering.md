---
name: effector-trigger-mission-start-ordering
description: How to verify a new effector-sequence trigger does not fire at mission start, when there is no dedicated test for it
metadata:
  type: project
---

body-layer's effector-sequence triggers that watch a belief-state edge (e.g.
`EffectorTrigger.CONTROLS_TO_PLAYER`, watching `belief.flight_authority.controls_to_player_edge`)
usually rely on *reset ordering*, not a dedicated test, to guarantee they don't fire spuriously at
a DCS mission (re)start: `body.py`'s poll loop calls `_check_for_new_mission` (→
`_reset_mission_state` → `crew_console.reset_for_new_mission()`, which re-runs `__init__` and
resets any field not in the explicit pass-through list, e.g. `flight_authority_state`, back to
its dataclass default) **before** the trigger's own "capture previous, advance, compare" block
later in the same poll. So even if the pre-restart state had Petrovich mid-flight, this poll's
`previous_*` is captured post-reset, and the edge check only ever sees `default → default` (no
edge) for the first poll after a restart.

**How to verify this on review**: read `body.py`'s poll-loop body top-to-bottom once, confirm
`_check_for_new_mission` precedes the trigger's own capture line, and confirm the relevant state
field is *not* in `CrewConsole.reset_for_new_mission`'s pass-through `self.__init__(...)` kwargs
list (that docstring enumerates every passed-through field by name — if the field you care about
isn't named there, it resets to its declared default).

**Found while reviewing `feature/bl16-sau-handover` (BL-16, 2026-11-20)**: this reasoning held for
`controls_to_player_edge`/`flight_authority_state`, and the diff's own tests didn't cover this
case directly (the mission-restart-while-flying scenario). Flagged as an optional refinement, not
a required fix — this appears to be the standing pattern across this codebase's belief-edge
triggers (e.g. `seat-pilot`/`seat-copilot` look to rely on the same reasoning), not a defect
specific to this change. Worth proposing a shared regression-test helper for "mission restart
while trigger-precondition-state was non-default, assert no write" if a future trigger's ordering
ever turns out to be wrong — that would be the actual cost of this gap materializing.

See [[feedback_verify_effector_registry_against_raw_dump]] for the companion check used in the
same review (cross-checking a curated effector against the raw dump + an independent research
note, when no live DCS install is reachable from the review worktree).
