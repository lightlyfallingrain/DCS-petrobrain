### Debug Report

### Observed Issue

`--eyesight-view` and `--pov-view` disagreed on where Petrovich was looking, for the same poll,
same optic (`sight_wide`). Top view: `gaze: 3_oclock centre=+90 deg +/-15 deg`, sector drawn at
3 o'clock. POV view: `boresight az=+6 el=+1`, matching the watched contact `U`'s real bearing.
User direction (`docs/acceptance/2026-10-26-sortie-feedback.md`): *"both should show what
Petrovich is really looking at and with what optic. Scan plan is useless data unless he actually
looks there."*

### Hypothesis

`ConsolePerceptionRunner.scan_plan` (`body.py`) is the *commanded* scan plan `_active_gaze`
resolves early in `run_once`, before `_apply_active_gaze` runs. `_apply_active_gaze` may override
that plan with a fixed look (a binocular glass phase, or the 9K113 sight) — but it applies the
override only onto the naked-eye `PerceptionSource`'s own private `scan_plan` attribute
(`source.scan_plan = resolved_plan`), never back onto `runner.scan_plan`. `_render_eyesight_frame`
unconditionally read `gaze_at(runner.scan_plan)`, so while on a fixed look it kept showing
whatever sector was commanded *before* the look took over. `_render_pov_frame` already had a
per-optic boresight table (`plans/pov-view/plan.md`) that bypassed `scan_plan` for the sight tier
(reading `SightHead.world_az_true_deg/world_el_deg` directly) — which is why the POV view was
correct for the screenshot's sight case — but its non-sight ("else") branch still read
`gaze_at(runner.scan_plan)`, so a binocular glass phase would hit the identical defect there too,
just not the case the screenshot happened to show.

A second, narrower finding during design: simply writing the resolved plan back onto
`runner.scan_plan` after `_apply_active_gaze` would have fixed the binocular case but broken the
sight case — `_apply_active_gaze`'s sight-tier override uses `head_body_direction` (the sight
head's *body*-relative direction, pitch/bank included), which `plans/pov-view/plan.md`'s own
Design section explicitly rules out as the display frame for these two canvases (azimuth must be
heading-relative, elevation horizon-relative, so a ground target stays still on the canvas while
the airframe pitches/rolls).

### Evidence

- `grep -n "self\.scan_plan\s*="` in `body.py` shows exactly one assignment site (`_active_gaze`'s
  result, before `_apply_active_gaze` runs) — it is never reassigned afterward in `run_once`.
- `_apply_active_gaze`'s own body (`body.py`) shows `resolved_plan` is a local variable, applied
  only via `source.scan_plan = resolved_plan` for `NakedEyePerceptionSource` instances in
  `sources`, never returned or written onto the caller's own `scan_plan` field.
- `_render_eyesight_frame` (pre-fix) called `gaze_at(runner.last_t_sim, runner.scan_plan)`
  unconditionally, with no per-optic branch at all — confirmed by reading the function.
- `_render_pov_frame` (pre-fix) already branched on `optic in (SIGHT_WIDE_OPTIC,
  SIGHT_NARROW_OPTIC)`, reading `sight_head.world_az_true_deg/world_el_deg` via
  `relative_bearing_deg` for that case — but fell back to `gaze_at(runner.scan_plan)` for every
  other optic, including `BINOCULAR_OPTIC` with an active fixed look.
- `tests/test_body.py`'s pre-existing `test_render_pov_frame_binocular_optic_uses_fixed_look_
  boresight` masked this: it sets `runner.scan_plan` directly to the fixed-look plan by hand,
  never exercising `run_once`'s actual (broken) wiring from `OpticState.actual_aim_*` through to
  `scan_plan`. There was no test for `_render_eyesight_frame` at all before this fix.
- `OpticState.actual_aim_azimuth_deg`/`actual_aim_elevation_deg` (`belief/optic_policy.py`) is set
  by `_apply_active_gaze` to the identical resolved value for a binocular fixed look (confirmed by
  reading the elif branch at `body.py`), and is the correct heading-/horizon-relative frame for
  display — unlike the sight tier's own `actual_aim_*`, which carries the body-relative value for
  the naked-eye source's internal gating and is not meant for this canvas.

### Fix Applied

Added `_resolve_active_gaze(runner) -> Gaze` in `body-layer/src/body.py`: the single resolved
value both views now read.

- Sight tier (`SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`): `SightHead.world_az_true_deg`/
  `world_el_deg`, azimuth converted to heading-relative via `relative_bearing_deg` — the logic
  `_render_pov_frame` already had, now shared.
- A fixed look on any other optic (binoculars): `OpticState.actual_aim_azimuth_deg`/
  `actual_aim_elevation_deg`, read directly rather than through `runner.scan_plan`, which never
  carried it.
- Otherwise (genuinely free-scanning, `actual_aim_*` both `None`): `gaze_at(runner.last_t_sim,
  runner.scan_plan)`, unchanged — this was already correct.

`gaze.label` is the optic's own name (`"sight_wide"`, `"binocular"`) on a fixed look, not a stale
scan-plan o'clock label, so a view's header never claims a scanning direction that is not what is
happening.

`_render_eyesight_frame` and `_render_pov_frame` both now call `_resolve_active_gaze` instead of
each deriving (or, in `_render_eyesight_frame`'s case, failing to derive at all) their own notion
of "where he's looking." `_render_pov_frame`'s per-optic table was deleted in favour of the shared
function; no other behaviour of either view changed (ground-truth/believed marker handling,
radius, max-lines budget, the ground-truth ASCII exemption — all untouched).

No change to `_apply_active_gaze`, `run_once`'s scan-plan wiring, or the speech-log sink
(`_speech_log_sink`, which has the same latent defect reading `runner.scan_plan` — out of this
fix's stated scope, left as-is).

### Verification

- New tests in `body-layer/tests/test_body.py`:
  - `test_resolve_active_gaze_binocular_fixed_look_uses_actual_aim_not_stale_scan_plan`
  - `test_resolve_active_gaze_sight_tier_uses_sight_head_not_scan_plan`
  - `test_resolve_active_gaze_free_scan_still_reads_scan_plan`
  - `test_render_eyesight_frame_sight_tier_shows_sight_head_direction_not_scan_plan_label`
  - `test_render_eyesight_frame_binocular_fixed_look_uses_actual_aim_not_stale_scan_plan`
  - `test_eyesight_and_pov_frames_agree_on_the_sight_boresight`

  Each constructs a runner with `scan_plan` deliberately left at an unrelated, stale commanded
  sector (reproducing the production wiring gap) and asserts the rendered frame reflects the
  resolved look instead. All fail against the pre-fix code (confirmed by running them before the
  fix was applied — `_render_eyesight_frame` was not even imported/tested in this file before this
  change) and pass after.
- Full suite: `body-layer/tests -q` → 2692 passed, 4 xfailed (unrelated pre-existing xfails).
- `ruff format --check src tests`, `ruff check src tests`: clean (one test file needed
  `ruff format`, applied).
- `cd body-layer && .venv/bin/mypy src`: `Success: no issues found in 77 source files`.
- No debug instrumentation left in the diff; only the shared resolver function, its docstring, and
  tests.
