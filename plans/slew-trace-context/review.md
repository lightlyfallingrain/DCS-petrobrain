### Review Summary

Reviewed `feature/slew-trace-context` (commit `71fedbee`, worktree
`/mnt/e/DCS-petrobrain-slew-trace-context`) against its stated spec — the user's own words in the
commit message and `docs/acceptance/2026-10-28-sortie-feedback.md` §5 — since no `plan.md` exists
(none was expected for this scope: a small, additive extension to an existing diagnostic log, per
the Reviewer's own remit to fit the check to the size of the change).

Scope matches the ask exactly: `servo_<key>` columns for every `GET /sight_servo/latest` field,
ownship attitude/position, and `sight_fov` (sight-optic detection-trace rows past the FOV gate),
all added to the existing `--slew-trace` writer (`sight_trace_writer.py`) rather than a new log —
"add to existing trace" is honoured. No scope drift: no new CLI flag, no new log file, no behaviour
change to perception/belief, and the sortie-feedback doc correctly stops at "not explored, not
fixed" rather than jumping to a sight-pointing fix, consistent with the project's
capture-then-explore rule for flight feedback.

**The hard question — whether `_INSIDE_FOV_OUTCOMES` (`RANGE_OR_SIZE`, `TERRAIN_LOS`, `FOREST`,
`ADMITTED`) correctly captures "inside the sight's FOV," and whether `GAZE`/`COCKPIT_MASK` rows
could hide a genuinely in-FOV sight candidate — checked by reading the real gate order in
`perception/visibility.py` (lines 973–1072), not by trusting the comment:**

- Gate order there is exactly `GAZE -> COCKPIT_MASK -> OPTIC_FOV -> RANGE_OR_SIZE -> TERRAIN_LOS ->
  FOREST -> ADMITTED`, matching `GateOutcome`'s declaration order and the frozenset's claim. A
  candidate that reaches any of the four kept outcomes has, by construction, already cleared
  `OPTIC_FOV` — so the filter is sound on its own terms.
- Whether `GAZE`/`COCKPIT_MASK` could reject a candidate that *would* have cleared `OPTIC_FOV` for
  a sight optic: no, under the system's current wiring. When a sight optic is actually selected for
  perception (`body.py`'s `_apply_active_gaze`, the `is_sight_tier` branch), the gaze handed to
  `check_visibility` is always `ScanPlan.fixed_look_at(sight_head_body_az/el_deg)` — a 15°-half-width
  cone (`FOCUS_CONE_HALF_WIDTH_DEG`) centred on the *same* direction `within_optic_fov` uses as its
  boresight. Both `SIGHT_WIDE_OPTIC` (5.75°) and `SIGHT_NARROW_OPTIC` (3.0°) have a narrower
  half-angle than that 15° gaze cone, and `within_gaze` is azimuth-only while `within_optic_fov`
  checks both axes — so anything that clears the narrower `OPTIC_FOV` test was already inside the
  wider, same-centred `GAZE` cone, and the cockpit mask (full non-sight envelope) is wider still.
  `GAZE`/`COCKPIT_MASK` cannot presently mask an in-FOV sight candidate. (This rests on an
  invariant — gaze half-width ≥ sight optic FOV half-angle, same centre — that isn't asserted
  anywhere; see Optional Refinements.)
- Confirmed `self.optic` is reassigned every poll from `optic_decision.optic` (the single
  `NakedEyePerceptionSource` instance body.py mutates in place), so every trace row recorded in a
  given poll shares the one active optic that poll — `optic.startswith("sight")` genuinely scopes
  to "this poll's sight evaluation," not a stale tag from an earlier poll.

**`body.py` wiring, `poll_detection_records` lifetime:**

- `poll_detection_records = list(trace_collector.records) if trace_collector is not None else []`
  (body.py:3298) is set unconditionally, every poll, right after `runner.run_once()` returns and
  before anything clears `trace_collector.records` — whether via `trace_writer.write_poll` (which
  clears internally, confirmed in `detection_trace_writer.py`) or the explicit
  `trace_collector.records.clear()` else-branch a few lines later. The snapshot is a `list(...)`
  copy, so it's immune to that later clear regardless of which branch fires.
  `runner.last_ownship_state` is likewise this poll's own value (set inside `run_once()`, read
  after it returns). No `continue`/`return`/early exit sits between the snapshot (line 3298) and
  its use at the `slew_trace_writer.write_poll(...)` call (line 3864) — verified by scanning that
  span for control-flow breaks (none found; only local `try/except AircraftLayerError` blocks that
  don't escape the poll). So yes: always defined, and always the same poll's data.

**Enabling `DetectionTraceCollector` whenever `--slew-trace` is given:** traced every
`trace_sink is not None` branch in `naked_eye_source.py`/`visibility.py` — all are pure
recording/annotation side effects (`trace.record(...)`, `annotate_admission`, the player-bubble
pre-filter's own trace row) that never feed back into `result`, `visible`, or what gets emitted.
Matches the module's own stated contract ("`DetectionTraceCollector` is a true no-op when unused" —
the inverse holds too: using it changes nothing but memory/CPU). No behaviour change found.

**Column preservation:** `servo_mode`, `servo_error_azimuth_deg`, `servo_error_elevation_deg`,
`servo_stalled` are all still emitted, now via the `_SERVO_KEYS` tuple/dict-comprehension instead
of four explicit assignments — same keys, same values, confirmed by diff and by the untouched
pre-existing tests in `TestFieldSelection` still passing.

**Docs** (`body-layer/CLAUDE.md`, `.claude/skills/sortie-log-triage/SKILL.md`) accurately describe
the new columns and correctly note the collector is turned on in memory only (no detection-trace
file unless `--detection-trace` is also given).

**No omniscience leak:** `sight_fov` carries ground truth (true bearing/range/elevation), and the
docstring says so explicitly — "a debug log, never an input to Petrovich." It is never read by
belief or crew-text code, only written to the JSONL file.

**Mechanical checks, all from `/mnt/e/DCS-petrobrain/body-layer/.venv/bin/`:**
- `ruff format --check body-layer/src body-layer/tests` — clean (178 files).
- `ruff check body-layer/src body-layer/tests` — clean.
- `cd body-layer && .venv/bin/mypy src` — clean, strict.
- `pytest body-layer/tests -q` — 2695 passed, 4 xfailed, 5 failed. All 5 failures
  (`test_load_effector_config_round_trips_the_real_committed_files`,
  `test_round_trip_against_the_committed_registry`,
  `test_load_registries_by_aircraft_discovers_the_real_mi24p_directory`,
  `test_every_shipped_sequence_file_round_trips`,
  `test_switch_reference_matches_the_generator`) are in files this commit never touches
  (confirmed via `git diff --stat` against the merge-base on the relevant test/config files —
  no overlap) and match the pre-existing, out-of-scope failures named in the review brief.
  `tests/test_sight_trace_writer.py` alone: 17/17 passed.
- `invariant-check` skill (run against this worktree): all greppable invariants PASS; the two WARN
  rows (`type: ignore`, swallowed exceptions) are pre-existing project-wide counts, none introduced
  by this diff.
- New tests (`TestOwnship`, `TestSightFov` in `test_sight_trace_writer.py`) are meaningful, not
  decorative: they exercise every `GateOutcome` value (including `OPTIC_FOV`, `GAZE`,
  `COCKPIT_MASK`, `PLAYER_BUBBLE` as negative cases) against the filter in one table-style test,
  check nearest-first ordering with real geometry, and check the null-ownship default path.
- `git status` clean in the feature worktree; nothing extra staged; no raw/generated data touched.

### Required Fixes

None.

### Optional Refinements

- The correctness of excluding `GAZE`/`COCKPIT_MASK` from `sight_fov` rests on an invariant that
  lives in two unrelated modules and isn't asserted anywhere: `gaze.FOCUS_CONE_HALF_WIDTH_DEG`
  (15°) must stay ≥ both sight optics' `fov_half_angle_deg` (5.75°/3.0°), and
  `_apply_active_gaze`'s `is_sight_tier` branch must keep centring the fixed-look gaze on the same
  direction `within_optic_fov` uses as its boresight. True today, not enforced by a test or
  assertion anywhere. Worth a one-line note (or a cheap property test: "for every optic with a
  field of regard, its `fov_half_angle_deg` ≤ `FOCUS_CONE_HALF_WIDTH_DEG`") next time either module
  is touched — not a blocker for this diagnostic-only change, since nothing here changes that
  invariant, only reads its consequence. (optional)
- `_sight_fov`'s `record.optic.startswith("sight")` is a slightly looser test than "is one of
  `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`." Harmless today (no third "sight*"-named optic exists),
  and matching against the two names directly would be marginally more robust against a future
  optic named e.g. `"sight_camera"` that isn't the 9K113. (optional)

### Verdict
APPROVED

### Review Confidence
Full read — all six changed files read in full against the diff; the gate-order claim and the
poll-lifetime claim (the two riskiest parts of this change) were independently traced through
`perception/visibility.py`, `perception/naked_eye_source.py`, `perception/optics.py`,
`perception/gaze.py`, and the relevant spans of `body.py`, not taken from the commit message's own
description. Full mechanical suite run (format/lint/type/test) plus the invariant-check skill.
