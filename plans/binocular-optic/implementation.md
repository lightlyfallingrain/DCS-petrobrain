### Implementation Summary

Stage 3b (`plans/binocular-optic/stage3b.md`): a binocular identification look now sweeps the
believed bearing's own angular uncertainty instead of staring at its centre. Built exactly to the
plan's four settled decisions (D1-D4); no re-litigation.

### Files Changed
- `body-layer/src/belief/association_over_time.py` — `_CLOCK_BUCKET_DEG` -> `CLOCK_BUCKET_DEG`
  (public), value and behaviour unchanged. `perception/naked_eye_source.py` keeps its own private
  copy of the same literal (it cannot import `belief`); left untouched, out of this stage's scope.
- `body-layer/src/belief/optic_policy.py`:
  - `_step_centres_deg` extracted from `search_pattern`'s step-arithmetic; `search_pattern` now
    calls it (pure refactor, no behaviour change — full suite green at that commit-equivalent
    point before any GLASSING change landed).
  - New `look_sweep(centre_azimuth_deg, centre_elevation_deg, bearing_uncertainty_deg,
    fov_full_width_deg)` — a sibling of `search_pattern`, not a reuse (D2). Elevation constant,
    steps ordered centre-outward (`sorted(..., key=lambda a: (abs(a), a))`), `N == 1` reproduces a
    stare exactly.
  - `LookTarget.bearing_uncertainty_deg` default -> `CLOCK_BUCKET_DEG / 2.0` (numerically
    identical to the prior literal `15.0`, now a real derivation rather than a coincidence, per D1).
  - `OpticState` gains `look_envelope_azimuth_deg` / `look_envelope_half_width_deg` — the sweep's
    *fixed* centre and half-width for the whole `GLASSING` phase, separate from
    `look_azimuth_deg`/`look_elevation_deg`, which now move to the current step every poll (D3).
    Elevation stays constant across a sweep by construction, so no separate envelope-elevation
    field was needed — `state.look_elevation_deg` always equals it.
  - `look_is_finished` / `_target_in_current_look` widened from the binocular field of view to the
    sweep's envelope (D4); falls back to the FOV when no envelope is recorded (a search phase, or
    a hand-built `OpticState` in a test), reproducing the pre-sweep behaviour exactly.
  - `decide`'s `GLASSING` branch is step-indexed the way `SEARCHING` already was:
    `step_s = MAX_LOOK_S / len(search_pattern_steps)`, no new constant (D3). `N = 1` gives
    `step_s == MAX_LOOK_S`, identical to today.
  - The SCANNING -> GLASSING transition now builds the sweep via `look_sweep`, stores it in
    `search_pattern_steps` + the new envelope fields, and starts on the sweep's first (centre-most)
    step. The attempted-range marking widens from the FOV to `chosen.bearing_uncertainty_deg` for
    the same reason `look_is_finished` did (D4) — a contact the sweep only reaches on a later step
    must still be marked, or it re-triggers a look immediately.
- `body-layer/tests/test_optic_policy.py` — `TestLookSweep` (pure geometry: N=1 vs N=4, constant
  elevation, centre-outward order, offsets bounded by the uncertainty), `TestSweepStepsWithTime`
  (the sweep advances through `decide` on the derived `step_s`, and running out of steps coincides
  with `MAX_LOOK_S`), `TestSweepEnvelope` (a target outside step 0's own FOV but inside the
  envelope does not end the look early — the defect the fix targets), and
  `TestSweepFindsAnOffsetContact` — the real Stage 3b tripwire the plan's step 5 asked for: a
  class-level contact whose believed azimuth is offset from truth by 12° (outside the 4.25°
  binocular half-angle, inside the 15° envelope). Verified by hand (not just by writing it) that
  this test goes red if `look_sweep`'s width is forced to 0 (i.e. reverted to a stare) — confirmed
  via a scratch-copy edit-and-restore, not by touching the tracked file.

### Test-impact check (plan step 1b)
- `test_mock_flight_chain_single_threaded_reaches_expected_contact_state`'s `xfail` marker named
  in the plan's "tripwire is mislabelled" section **did not exist** at merge time — it had already
  been corrected (marker removed, comment rewritten to name the search phase and the 650 m AGL
  geometry) by a prior commit on this branch (`75fc4a7`, "Correct the tripwire..."), before this
  implementation pass started. No change needed there; verified the assertion still reads `== 32`
  and the comment's own reasoning is undisturbed by this stage's changes.
- Grepped the full suite for consumers of every changed symbol (`look_is_finished`,
  `_target_in_current_look`, `search_pattern`, `GLASSING`, `bearing_uncertainty_deg`, `MAX_LOOK_S`)
  outside `test_optic_policy.py`: only `test_logger.py`'s
  `test_a_player_command_lowers_the_binoculars` touches `OpticState`/`OpticPhase.GLASSING`
  directly, and it never calls `decide()` for that phase, so it was unaffected. No file needed
  changes beyond the three staged.

### Tests Added
- `TestLookSweep` (5 tests) — `look_sweep`'s own geometry in isolation.
- `TestSweepStepsWithTime` (2 tests) — step progression through `decide`, and the
  cap/exhaustion coincidence.
- `TestSweepEnvelope` (1 test) — the widened `look_is_finished` does not end a sweep on step 0.
- `TestSweepFindsAnOffsetContact` (1 test) — the real tripwire: sweep finds what a stare would
  miss.

### Checks
(body-layer/ only — the sole subproject touched)
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`PYTHONPATH=src:../world-model/src mypy src`, run from `body-layer/`): pass
- pytest -q: pass — 1016 passed, 4 xfailed (was 1007 passed, 4 xfailed before this stage; +9 new
  tests, 0 regressions)

### Notable Discoveries
- No `.venv` existed in this worktree (worktrees don't carry gitignored dirs) — created one ad hoc
  with `pyproj`, `mypy`, `pytest`, `ruff` matching the main checkout's `body-layer/.venv` versions.
- A live-patch-and-revert sanity check (proving the new tripwire actually fails on a reverted
  implementation) must never use `git checkout -- <tracked file>` when that file carries unstaged
  work — it silently discards everything back to `HEAD`, which is exactly what happened once during
  this session (all of `optic_policy.py`'s edits were lost and had to be redone from memory of the
  diff). Use a scratch copy (`cp file /tmp/backup`, patch, test, `cp /tmp/backup file`) for this
  class of check instead.
