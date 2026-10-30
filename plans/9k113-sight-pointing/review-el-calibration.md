### Review Summary

Branch `fix/9k113-el-calibration` (47b56c64, one commit on `main`). Flight-fitted elevation
calibration for the ASP-17 mark (boresight 0.83 → 0.8333, scale 1/0.037 → 1/0.0277), replacing the
2026-10-28 gimbal-derived guess that put the ATGM cross ~25% short. Fitted against DCS AI
Petrovich tracking a real unit (BMD-1), truth from body-layer's detection trace, 107 samples,
rms 0.006°, flat/linear across the full -1.7..-14.5° span and a 7.1→2.6 km range closure — the
flat residual across a changing attitude is itself evidence the heading/pitch/bank rotation used
to get truth into the airframe frame is correct; a wrong rotation order would show up as a
systematic residual trend, not noise this small. No fitting script is checked in (consistent with
how this project's other ad-hoc flight calibrations are recorded — numbers and method in the
research note, not pipeline code).

Checked and consistent:
- Every consumer of `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL` in `Export.lua` (derived
  `ASP17_FIELD_EL_UP_DEG`/`DOWN_DEG`, `sight_mark_is_clipped`, `push_slew_trace`, the
  homing/closed paths at the bottom of `run_sight_servo`) reads the two updated constants; nothing
  hardcodes the old 0.83/0.037 elsewhere in the file. Up-side inset (≈+5.5°) still sits inside the
  new +6.0° raw clip.
- Grepped `body-layer/src` and `body-layer/config` for the old field (+4.6/-14.9), the new one
  (+6.0/-20.1), and the raw constants (0.83, 0.037, 0.0277, 0.8333) — no hits. The only elevation
  envelope body-layer carries is the 9K113's physical gimbal field-of-regard (`perception/optics.py`
  `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`: `regard_elevation_up_deg=20.0`,
  `regard_elevation_down_deg=-15.0`), sourced independently from `Devices_specs/9K113.lua`, not
  from this mark calibration — a different fact (mechanical travel vs. the ASP-17 reticle mark's
  own readable range), and the -15° it states agrees with the research note's "past the -15° gimbal"
  framing. Nothing in body-layer disagrees with this change because nothing there encoded the old
  mark-field numbers in the first place.
- Test harness constants in `test_sight_servo_lua.py` (the Lua preamble literal and the new
  `_EL_BORESIGHT`/`_EL_SCALE` module constants) were updated in lockstep with every call site.
  `test_elevation_field_target_clips_at_the_down_inset_edge` → renamed
  `test_elevation_down_field_bound_is_past_the_gimbal` and rewritten to assert the setpoint parks
  at the -15° gimbal stop rather than at a field inset, matching the new derived bound (~-20.1°,
  past the gimbal) — the replacement still guards something real (that the field clip never
  engages on a side it no longer reaches) and isn't a weaker test than before.
- Comment pruning: the removed "pending a pitch-change check" line is superseded by this flight
  fit actually doing that check (truth rotated through heading/pitch/bank across a maneuvering
  approach). The dropped pilot quote ("about boresight") is not lost — it still lives verbatim in
  `2026-10-28-9k113-asp17-elevation-mark-calibration.md`, which gets a supersession note at the top
  rather than being deleted, per `docs/PROCESS.md`.

One loose end, not a blocker: `_mark_raw`'s docstring in `test_sight_servo_lua.py` still says
"elevation callers pass `boresight=_EL_BORESIGHT, scale=_EL_SCALE` to match the harness's
**(measured 2026-10-28)**" — that date is now wrong; the values it's describing are the 2026-10-30
flight fit. Cosmetic (the code is correct, the cross-reference is not), but worth a one-line fix
next time this file is touched.

### Required Fixes

None.

### Optional Refinements

- Update the stale "(measured 2026-10-28)" date in `_mark_raw`'s docstring
  (`aircraft-layer/tests/test_sight_servo_lua.py`) to 2026-10-30, since that's the flight the
  numbers it documents actually came from (optional — doesn't affect test correctness).

### Verdict

APPROVED

### Review Confidence

Full read — diff is small (one Lua constant block, one research note, test edits), all consumers
of the changed constants were grepped and traced by hand, and body-layer was checked for any
duplicated/disagreeing encoding of the elevation field. Mechanical checks run from inside
`aircraft-layer/` with the `body-layer/.venv` tools: `ruff format --check` clean, `ruff check`
clean, `mypy --strict src` clean (26 files), `luac5.1 -p Export.lua` clean, `pytest -q` — 649
passed, 2 failed (`test_collector_server_accept_errors.py`, "Address already in use" — the known
pre-existing environment issue named in the review brief, unrelated to this change).
