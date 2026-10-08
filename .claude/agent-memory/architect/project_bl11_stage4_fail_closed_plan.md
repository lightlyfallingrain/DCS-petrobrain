---
name: bl11-stage4-fail-closed-plan
description: BL-11 Stage 4 steps 3-4 (fail-closed LOS, coverage counter) planning decisions and the measured test blast radius
type: project
---

Planned 2026-10-08 (`plans/bl11-stage4-fail-closed/plan.md`). Worth remembering for any future
pass on `body-layer/src/perception/visibility.py` gate 4 or its test fixtures:

- **Measured, not guessed, blast radius of removing the `elif line_of_sight_clear(...)` fallback**:
  70 of 1540 body-layer tests fail, concentrated entirely in `test_visibility.py` (29),
  `test_vision_calibration.py` (4), `test_naked_eye_source.py` (7), `test_player_bubble.py` (2).
  Measured by editing `visibility.py` in a worktree, running the full suite, then restoring via
  `git checkout -- <path>` (never `git stash` — shared stash stack across worktrees).
- **Three of the four files share one fixture factory each** (`_candidate()` in
  `test_visibility.py`; a `FakeAircraftClient`/`_world_object` pair, independently duplicated, in
  `test_naked_eye_source.py` and `test_player_bubble.py`), so ~68 of the 70 failures are a one-line
  default change, not a rewrite. Only `test_vision_calibration.py` builds `WorldObjectCandidate(...)`
  literally at each call site with no shared helper.
- **`FakeAircraftClient.get_line_of_sight_latest` in both naked-eye-channel test files always
  returns `None`**, and the raw `_world_object()` fixture dicts in both never set `unit_name` at
  all — the join key `_resolve_los_by_unit_name` needs. Both must be fixed together or the fix is a
  no-op (no unit_name -> never resolves regardless of what the fake LOS feed returns).
- **`live_los_clear is None` already collapses four distinct causes uniformly** by design, one
  level below where fail-closed reads it: feed absent (`get_line_of_sight_latest() is None`), skew
  too stale (`> LOS_MAX_AGE_S`, 3.0 s), the unit's name missing from the Hook's `verdicts` dict
  (outside its own queried wedge, or malformed), and non-unique `unit_name` among this poll's
  objects (`naked_eye_source._resolve_los_by_unit_name`, mirroring `_resolve_velocity_by_object_id`'s
  precedent from `plans/movement-detection/plan.md` Decision 1). The gaze/bubble gates run *before*
  gate 4, so a candidate rejected there never reaches the LOS check at all — the coverage counter's
  denominator should only count candidates that reach gate 4, which excludes those for free via
  control flow, no special-casing needed.
- **`check_visibility` already has an optional-collector idiom** (`trace: DetectionTraceCollector |
  None = None`) — the coverage counter deliberately does *not* reuse that pattern, because
  `DetectionTraceCollector`'s whole design intent is "opt-in, true no-op when `None`," and the
  coverage counter must be always-on (visible without `--detection-trace`) to do its job. Two
  separate mechanisms with a similar shape, kept separate on purpose.
- `body-layer/ROADMAP.md` Stage 4 (search "REWRITTEN 2026-10-06") already carries the authorising
  history in full — the 76%-admitted-had-no-verdict baseline, the statics-enumeration fix that
  closed it, and the 2026-10-08 sortie's 145/145-evaluated/85/85-admitted result. Read it before
  re-deriving any of those numbers.
