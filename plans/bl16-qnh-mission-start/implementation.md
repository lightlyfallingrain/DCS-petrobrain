### Implementation Summary

BL-B118 built per `plans/bl16-qnh-mission-start/plan.md`'s four stages (Stage 4, the live card,
is explicitly the pilot's own two sorties -- not built here). Test-impact check done against the
plan's own list before starting: every test it named (`test_mission_start_schema.py`,
`test_altimeter_qnh_sync.py` (new), `test_mission_start_reset.py`, `test_crew_console.py`) exists
or was created as planned; one test the plan did not name also needed a change --
`aircraft-layer/tests/test_mission_start_api.py::test_pushed_event_is_returned` asserts the full
wire dict `MissionStartEvent.to_dict()` produces over a real `TelemetryAPIServer`, so adding
`qnh`/`atmosphere_type` broke its exact-equality assertion the same way it broke the schema's own
`test_to_dict_round_trips`. Both updated to include the two new keys.

### Files Changed
- `aircraft-layer/src/schema/mission_start.py` -- `qnh: float | None`/`atmosphere_type: int | None`
  added to `MissionStartEvent`, parsed/emitted the same best-effort, null-on-failure way `theatre`
  already is (bool-excluded numeric/int validation, same shape as `sequence`'s own check).
- `aircraft-layer/dcs-export/petrobrain-mission-start-hook.lua` -- `resolveQnh()`/
  `resolveAtmosphereType()` mirroring `resolveTheatre()` exactly; both included in the UDP payload.
  **Caught by the existing `test_no_nested_long_bracket_in_block_comment` test**: an Obsidian
  `[[BL-B118]]` wiki-link reference inside the file (even outside the `--[[ ]]` header block) is
  banned file-wide in this project's Lua files (2026-10-17 incident, see that test's own assertion
  message) -- written as plain `` `BL-B118` `` instead throughout the Hook script.
- `aircraft-layer/src/aircraft_client.py`, `aircraft-layer/src/collector/mission_start_receiver.py`
  -- two docstring-only fixes (wire-shape examples that enumerated the old 3-key dict), done
  opportunistically since both describe the exact shape Stage 1 changed; no code change.
- `aircraft-layer/CLAUDE.md` -- one clause added to the mission-start-signal sentence.
- `body-layer/src/belief/altimeter_qnh_sync.py` **(new)** -- `AltimeterQnhSyncState` (frozen,
  `replace()`-only, single construction site `start_altimeter_qnh_sync`) and
  `advance_altimeter_qnh_sync`, the self-calibrating secant loop over device 42/cmd 3001/arg 834.
  Eight new `tuning.real`/`tuning.whole` constants, exactly as listed in the plan's table.
- `body-layer/config/defaults.toml` -- regenerated; staleness test passes. Read the rendered first
  sentence of each of the eight new entries against the plan's own comments before regenerating --
  no drift found.
- `body-layer/src/belief/crew_console.py` -- `ALTIMETER_QNH_NO_RESPONSE_LINE`/
  `ALTIMETER_QNH_TIMEOUT_LINE` constants, `altimeter_qnh_failed_pending` field (not preserved across
  a mission reset, unlike `config_error_pending`), `drain_altimeter_qnh_failed` (mirrors
  `drain_config_error`'s shape, takes the run's `phase` as a caller-supplied argument since this
  class holds no reference to the run itself).
- `body-layer/src/body.py` -- `altimeter_qnh_sync: AltimeterQnhSyncState | None` field on
  `ConsolePerceptionRunner` (not preserved across a reset); `_maybe_start_altimeter_qnh_sync`
  (arms/clears the run, called alongside `_maybe_switch_theatre` at both of
  `_check_for_new_mission`'s adoption sites); the poll loop advances the closed loop unconditionally
  once armed and detects a `running -> failed_*` transition to arm `crew_console.
  altimeter_qnh_failed_pending`; `drain_altimeter_qnh_failed` wired next to `drain_config_error`,
  sharing its `GET /spu8/state` fetch.
- `body-layer/CLAUDE.md` -- one paragraph beside the existing mission-start-trigger paragraph.
- Both dataclasses' `reset_for_new_mission` docstrings (`ConsolePerceptionRunner`'s and
  `CrewConsole`'s) -- the new field added to each method's own enumeration of what resets, for the
  mechanical per-field test (`test_console_perception_runner_reset_preserves_declared_fields_and_
  resets_rest`/`test_crew_console_reset_preserves_declared_fields_and_resets_rest`) to stay
  self-documenting; neither test required a code change since both fields are plain, undeclared-
  in-the-preserve-set fields that reset automatically.

### Tests Added
- `body-layer/tests/test_altimeter_qnh_sync.py` (new, 12 tests) -- every terminal phase against a
  fake `read_args`/`write_cockpit_switch` double with a configurable device-response function:
  worst-case 120 mmHg convergence, an inverted-gain-sign convergence (the secant self-correction),
  a fully non-responding knob (`failed_no_response`), one noisy non-response that must not trip it,
  an oscillating response that converges on neither error nor no-response (`failed_timeout` via the
  iteration bound), a `failed_timeout` reached purely by the wall-clock bound with iteration
  headroom left, transient read-failure and transient write-failure skip-and-retry, the settle gate,
  and both terminal phases' inertness. Every test asserts no write ever exceeds
  `ALTIMETER_QNH_MAX_STEP`. The settle-gate and inert-state tests are negative-space assertions
  (asserts a *second* read/write never happens); both were run against a deliberately broken
  version of the guard they test (settle gate removed; terminal short-circuit removed) to confirm
  each goes red for the stated reason, then the file was restored and its checksum verified against
  the pre-break version before re-running green.
- `aircraft-layer/tests/test_mission_start_schema.py` (6 new tests) -- `qnh`/`atmosphere_type`
  present/null/missing/non-numeric/bool cases, same shape as the existing `theatre`/`sequence`
  tests; `test_to_dict_round_trips` extended with the two new keys.
- `body-layer/tests/test_mission_start_reset.py` (4 new tests) -- QNH armed at the first-event-
  adopted site, armed at a genuine reset, cleared to `None` when `qnh` is missing, cleared to `None`
  when `qnh` is non-numeric.
- `body-layer/tests/test_crew_console.py` (`TestDrainAltimeterQnhFailed`, 7 new tests) -- both
  lines speak once the gate opens, silent when not pending, held while the gate is closed, held
  while silenced, silent (not a crash) when `phase` is `None`, and re-armable after a mission reset
  (the one behaviour that deliberately differs from `config_error_pending`).

### Checks
**aircraft-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (no issues, 27 source files)
- pytest tests -q: pass (772 passed)
- `luac5.1 -p` on every `dcs-export/*.lua` file: pass

**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (no issues, 84 source files) -- `mypy src tests` was tried once and surfaces ~285
  pre-existing errors across several test files unrelated to this change (loosely-typed test
  doubles, `Non-overlapping equality check` on test-only literal comparisons); the project's own
  prescribed command is `mypy src` only, which is clean.
- pytest tests -q: pass (3307 passed, 4 xfailed -- the 4 xfails are pre-existing and unrelated;
  3307 = the pre-change 3296 plus the 11 tests added in Stages 3)

### Notable Discoveries
- **The Lua wiki-link ban applies file-wide, not just inside the `--[[ ]]` header comment.**
  `test_no_nested_long_bracket_in_block_comment` scans the whole file for `[[ID]]`-shaped text, not
  only the region between `--[[` and the matching close -- two `--:` single-line comments using
  `[[BL-B118]]` outside the header block still failed it. Written up here since the test's own name
  suggests a narrower scope than it actually enforces.
- **`aircraft_client.get_mission_start_latest()` and `collector/mission_start_receiver.py` both
  carry a hand-written wire-shape example in their docstrings** that is not generated from the
  schema and does not get checked by any test -- both had already drifted (missing `qnh`/
  `atmosphere_type`) the moment Stage 1 landed, caught only by reading the files, not by a failing
  check. Worth a staleness test if this wire shape grows another field.
- **Coupling check not needed**: the plan's own tunables table states none of the eight new
  constants has a cross-key relationship with an existing one, and this was not re-derived here
  beyond trusting that stated check -- no `tuning._check_*_coupling` function was added.
- Comment pruning: none of the touched files' existing comment blocks were stale against the code
  they described before this change (checked `reset_for_new_mission`'s two docstrings, `_check_for_
  new_mission`'s, `_maybe_switch_theatre`'s), so nothing was cut -- only the two wire-shape docstring
  examples above needed a fix, and those were additions (the new fields), not prunes.

### Review fix round (Reviewer -> Implementer loop, `plans/bl16-qnh-mission-start/review.md`)

**Required fix applied.** `advance_altimeter_qnh_sync`'s `else` branch (the calibration-step probe
taken on iteration 0 and whenever the gain estimate is degenerate) now clamps its write to
`+-ALTIMETER_QNH_MAX_STEP`, the same way the gain-based branch already did --
`body-layer/src/belief/altimeter_qnh_sync.py:293-298`. This makes `ALTIMETER_QNH_MAX_STEP`'s own
docstring claim ("bounds any single write regardless of a bad gain estimate") true for every legal
pair of the two constants' declared bounds, not just their defaults. No `#:` comment changed (the
`MAX_STEP` docstring was already correct in wording, just not enforced for this branch), so
`config/defaults.toml` was regenerated and confirmed byte-identical -- no drift to read.

**Test added**: `test_calibration_step_is_clamped_to_max_step_even_when_configured_larger`
(`body-layer/tests/test_altimeter_qnh_sync.py`) -- `monkeypatch.setattr`s
`ALTIMETER_QNH_CALIBRATION_STEP`/`ALTIMETER_QNH_MAX_STEP` directly on the owning module (the
established in-process pattern for this shape of test, matching `test_groups.py`/
`test_relative_distance_scenarios.py`, not the heavier `PETROBRAIN_TUNING`-subprocess pattern
`test_tuning.py` uses for testing the loader itself) to `0.2`/`0.05` -- a legal pair per each
constant's own `lo`/`hi` bounds that inverts the defaults' ordering -- then drives one poll from a
fresh `start_altimeter_qnh_sync` state (guaranteed to take the `else` branch, since
`prev_delta_sent` is `None`) and asserts the write stays within `0.05`. Counterfactual run: reverted
the clamp, confirmed this test fails with the unclamped `0.2` write (`assert False` on
`abs(delta) <= 0.05`), restored the file, confirmed the restored file's checksum
(`d1affd34cf4c12623cdc771692f6894afa8f9840`) matches the pre-break version exactly.

**Optional fix also applied**: `body-layer/ROADMAP/BL-B118.md`'s stale closing line ("Not yet
implemented or flown") changed to "Implemented (Stages 1-3); not yet flown." with `#needs-flight`,
matching the review's own observation that Stages 1-3 are built. The `drain_altimeter_qnh_failed`
clarity suggestion was skipped, per the review's own "optional" framing and this task's explicit
instruction.

**Checks (this round, body-layer only -- aircraft-layer untouched)**:
- `ruff format --check src tests`: pass (206 files already formatted)
- `ruff check src tests`: pass (all checks passed -- the pre-existing unrelated `I001` finding the
  review noted in `test_bl_b104_association_scenarios.py` is gone; it was fixed on `main` by the
  `fix/ruff-import-order-slow-marker` merge this branch picked up via the required fast-forward)
- `mypy src`: pass (no issues, 84 source files)
- `.claude/scripts/fast-tests.sh body-layer`: pass (2414 passed, 4 xfailed)
- `tests/test_altimeter_qnh_sync.py` by name, verbose: all 13 pass, including the new test by its
  exact name
