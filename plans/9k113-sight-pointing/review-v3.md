# Review: BL-B80 v3, Stage 6 — the real sight never leaves the ASP-17 field (edge park)

Branch `feature/9k113-sight-edge-park`, diff base `9dfc3d2f` (plan-only tip) .. `80714a98`
(implementation tip). Worktree fast-forwarded to the corrected tip `0ec20d59` (main merged in,
docs/config only — no code in that merge).

## Review Summary

Implements exactly what `plan.md`'s v3 section specifies: the root-cause fix (mark-validity gate
checks the mark's own raw reading against the ASP-17's ~4.3° field, not the setpoint against the
60° gimbal envelope), the always-closed loop on `field_target` (the setpoint radially projected
onto the inset field, recomputed every frame — continuous tracking, not a one-shot park), part
3's feed-forward switch to `field_target`'s own finite difference while sliding, the merged
`closed`/`homing` mode (open loop removed entirely, not kept as fallback), and the shared stall
detector. Both named mutations in the plan's own "Tests" section were manually reproduced against
the real `Export.lua` and confirmed red (see "Mutation verification" below) — this is a real fix,
not a plausible-looking one.

Scope matches the plan's own stated boundary: aircraft-layer only, no body-layer change, which
the plan's "Implementation Plan" section states explicitly ("Does not touch body-layer"). The
implementer's `implementation.md` flags this narrowing explicitly rather than silently deviating
from the "Affected Files" table drafted for v3 as a whole (which had listed
`sight_trace_writer.py`). The elevation-measurement decision ("measure in flight") is satisfied
without that body-layer wiring: `push_slew_trace`'s per-frame log now carries raw `mark_az_raw`/
`mark_el_raw`/`mark_clipped`, which is what the plan's own ANSWERED note says the flight needs to
read 555's clip edges off.

## Required Fixes

None.

## Optional Refinements

- **Flight B's test card does not yet exist with the edge-park case the plan's own "Risks &
  Unknowns" section requires** ("hold the target well outside the ASP-17 field and watch the real
  cross hair park and slide at the edge rather than drift or peg"). The plan itself says Flight
  B's card "has not been flown or had its card written yet" independent of this stage, so this is
  not a Stage 6 scope gap — but it is a loose end someone (DoD, or whoever runs `/test-card` before
  the next sortie) needs to close before this can be acceptance-tested. Flagging so it isn't lost
  between Reviewer and DoD. (Optional only because it is explicitly out of this stage's own file
  list, not because it doesn't matter — the user cannot verify this fix without it.)
- **`ASP17_FIELD_EL_HALF_DEG`/`ASP17_FIELD_MARGIN_DEG` are both guesses**, as the plan itself
  states repeatedly and ships deliberately. No action needed before merge; carried here only so
  the open-guess status is visible in one place alongside the review verdict.

## Checks (aircraft-layer; body-layer untouched — confirmed, no body-layer source in the diff)

- `ruff format --check` — pass (72 files already formatted)
- `ruff check` — pass
- `mypy --strict` on `src` — pass (25 source files); on the two touched test files directly — pass
- `pytest tests -q` — 607 passed (matches implementer's claim)
- `luac5.1 -p Export.lua` — pass
- `GETGLOBAL`-vs-own-helpers check on `Export.lua` — clean (every global is stdlib or a genuine
  DCS API; no own-helper read-before-declaration)
- `test_dcs_export_lua_local_order.py` / `test_dcs_export_lua_syntax.py` — 122 passed

(No `.venv` existed in this worktree; one was created fresh with `ruff`/`mypy`/`pytest` installed
to run these — not committed, per the subproject's own gitignore posture.)

## Mutation verification (not just reading the diff)

Per this role's own standing "verify by mutation" practice, both of the plan's own named
mutations were applied directly to the real `Export.lua` (not a reproduction) and reverted after:

1. **Reverting `field_target` to the raw setpoint** (`local field_target_az, field_target_el,
   field_clipped = sight_setpoint_body_az_deg, sight_setpoint_body_el_deg, false`) —
   `TestRunSightServoFieldPark` went from 7/7 passed to **3 failed**
   (`test_far_off_boresight_setpoint_converges_...`,
   `test_feed_forward_uses_field_target_rate_...`,
   `test_continuous_tracking_never_sticks_...`), exactly reproducing the sortie's own symptom per
   the plan's own prediction.
2. **Feeding the raw goal rate into `ff` unconditionally** (deleting the `if field_clipped ...`
   finite-difference block) — exactly one test failed,
   `test_feed_forward_uses_field_target_rate_not_raw_goal_rate_while_sliding`, with the obtained
   value (`1.5`, the write-clamp ceiling) matching the plan's own stated reversion arithmetic
   (`KP*0.8 + FF_GAIN*50 = 152.4°`, clamped). All 6 other tests in the class stayed green, as the
   plan's own test-impact note predicted.

File restored to the merged state after each check (`git status --porcelain` clean throughout and
at the end).

## Other checks performed

- **Co-moving fields**: every reset site (`LuaExportStop`, OBSERV off/on, caged, hold/stale) was
  checked for the five new/renamed state fields (`sight_field_target_body_az/el_deg`,
  `sight_mark_clipped`, `sight_prev_field_target_body_az/el_deg`) alongside the removed
  `sight_estimate_body_*_deg` — all five reset sites carry all five fields; none left stale.
- **Schema required-field posture**: `mark_clipped: bool` is required, mirroring `stalled`'s
  posture per the plan's own instruction; `field_target_azimuth_deg`/`field_target_elevation_deg`
  are optional (`None` when `hold`/`caged`/`off`), matching `mark_azimuth_deg`'s existing
  optionality pattern. `from_dict`/`to_api_dict` both carry all three; the five-test ripple in
  `test_sight_servo_api.py` (beyond the plan's one-line note) was itself flagged by the
  implementer, verified against the diff, and is correctly exhaustive — no sixth construction
  site was missed.
- **Comment pruning**: `push_slew_trace`'s dated 2026-10-21 "local read as global" note was
  preserved verbatim at its new location (moved, not deleted or rewritten) — no durable line lost.
  `FIELD_MARGIN_DEG`'s old comment was replaced with ASP17-specific prose since the constant
  itself is gone (confirmed by grep — no remaining use outside one explanatory comment).
- **Tuning convention**: the four new constants are correctly left as bare Lua locals with the
  "no tuning mechanism outside body-layer" posture stated explicitly in `implementation.md`,
  matching root `CLAUDE.md`'s instruction for this exact case (declare normally, note it, don't
  improvise a second loader).
- **Vocabulary/STT**: not applicable — no new spoken command, phrasing, or slot word in this
  stage.
- **Knowledge graph / memory**: queried before concluding anything; no prior documentation
  contradicted what's built here. New architect/implementer memory entries added this stage
  (`feedback_two_fields_different_scales_name_both`,
  `feedback_export_lua_new_helper_can_make_an_earlier_function_stale`,
  `feedback_required_field_mirroring_existing_one_ripples_fixtures`,
  `project_sight_clip_to_field_body_deg_margin_reduced_call_shape`) read and are substantive, not
  derivable-from-repo filler.

## Verdict

APPROVED

## Review Confidence

Full read — plan v3 section, implementation.md Stage 6 section, sortie feedback §2 verbatim, full
`Export.lua` diff read line-by-line, schema diff, both test file diffs, all new/changed test names
in `test_sight_servo_lua.py`, `notes/` and `body-layer/CLAUDE.md` edits. Both of the plan's own
named mutations reproduced directly against the real source and confirmed red, then reverted. All
subproject checks (format/lint/type/test/Lua syntax/local-order) re-run fresh in this worktree,
not taken on the implementer's word.
