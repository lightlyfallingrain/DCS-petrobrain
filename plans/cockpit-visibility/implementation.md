### Implementation Summary

Replaced `perception/visibility.py`'s flat, elevation-blind
`NAKED_EYE_FOV_HALF_WIDTH_DEG` azimuth cone with a body-relative cockpit
occlusion mask, per `plans/cockpit-visibility/plan.md` D1-D7. Landed as two
commits, exactly matching D3's mechanism/calibration split:

1. `244d436` — mechanism: `OwnshipState.pitch_deg`/`bank_deg`,
   `geometry.body_relative_direction` (pure yaw/pitch/bank rotation),
   `perception/cockpit_mask.py` (`OcclusionMask`, `is_visible`,
   per-station `COCKPIT_MASKS`), wired into `check_visibility` in place of
   `_within_fov`. Placeholder table numbers, clearly marked.
2. `f0945c2` — calibration: replaced the placeholder table with a
   first-pass table read off the four reference screenshots
   (`win-mac-sync/from-windows/Screen_260917_0000{55,59,105,125}.jpg`),
   corrected for the assumed 5° nose-down attitude those were captured at.
   No other line changed.

A third, small bookkeeping commit (`7f0a5bb`) narrowed `todo/todo.md`'s
"Scan commands should drive naked-eye perception, and the naked-eye FOV is
a 9K113 number" entry to only the still-open scan-steering half, since this
plan resolved the "wrong instrument" half. Not a mechanism/calibration
commit itself — kept separate anyway, since it is bookkeeping, not code.

### Files Changed
- `body-layer/src/perception/source.py` — `OwnshipState` gains
  `pitch_deg`/`bank_deg: float = 0.0` (degrees, defaulted so every existing
  fixture/call site is unaffected); `from_telemetry_dict` reads the wire's
  existing `pitch_rad`/`bank_rad` and converts to degrees, same unit rule
  as `heading_true_deg`. Deliberately *not* wrapped to `[0, 360)` — pitch
  and bank are small signed angles, wrapping would corrupt the sign.
- `body-layer/src/perception/geometry.py` — new `BodyRelativeDirection`
  dataclass and `body_relative_direction()`: rotates an observer→target
  vector out of world coordinates into the observer airframe's own frame
  (yaw, then pitch, then bank removal, each step documented in the
  docstring with the intermediate frame it produces). Pure, no I/O, no
  `OwnshipState`/mask dependency — kept independently testable per plan
  point 2 ("keep the geometry pure and separately testable from the
  gate").
- `body-layer/src/perception/cockpit_mask.py` (new) — `OcclusionMask`
  (breakpoint table + linear interpolation + hard rear cutoff),
  `is_visible` (symmetric mirroring via `abs(azimuth_deg)`, D5), and
  `COCKPIT_MASKS` keyed by crew station (D6, only `STATION_CO_PILOT`
  populated). Upward visibility is not separately bounded — falls out for
  free since an above-boresight target's depression is negative, trivially
  under any positive `max_depression_deg` (documented explicitly so a
  future reader doesn't "fix" this as a missing case).
- `body-layer/src/perception/visibility.py` — `check_visibility` now
  computes `body_relative_direction` and gates on
  `cockpit_mask.is_visible(COCKPIT_MASKS[STATION_CO_PILOT], ...)` instead
  of `_within_fov`; `_within_fov` and `NAKED_EYE_FOV_HALF_WIDTH_DEG` are
  gone. Module docstring's gate-1 description rewritten to describe the
  mask and explicitly call out what it replaces and why (no elevation
  term, wrong-instrument constant).
- `body-layer/src/belief/crew_console.py` — one docstring reference to the
  now-removed `NAKED_EYE_FOV_HALF_WIDTH_DEG` updated to name
  `perception.cockpit_mask` instead; no behavior change (this file was
  already documenting, not depending on, the old constant).
- `todo/todo.md` — narrowed the "Scan commands should drive naked-eye
  perception, and the naked-eye FOV is a 9K113 number" entry: the
  wrong-instrument half is resolved by this plan, only the scan-steering
  half remains open.

### Tests Added
- `body-layer/tests/test_geometry.py` — `body_relative_direction`: level/
  unbanked reduces to plain bearing/elevation; heading removal; a target
  exactly along a pitched nose resolves to `elevation=0` (the derivation
  walkthrough's own worked case); below-horizon gives negative elevation;
  bank rotates a straight-down target's elevation into azimuth (the
  concrete case that justifies reading bank at all); rear-hemisphere
  azimuth wraps to ±180.
- `body-layer/tests/test_cockpit_mask.py` (new) — `OcclusionMask`/
  `is_visible` against a small hand-authored synthetic mask, never against
  `COCKPIT_MASKS`'s shipped values: exact-breakpoint lookup, linear
  interpolation, `None` at/beyond rear cutoff, nose-depression pass/reject,
  the same depression rejected abeam that a nose look allows, rear
  hemisphere blocked even when the target is above boresight, above-
  boresight always passes the depression check, left/right symmetry, and
  flat-hold past the last breakpoint before cutoff.
- `body-layer/tests/test_visibility.py` — replaced the old FOV-cone tests
  (`test_candidate_outside_fov_is_not_visible` etc., which encoded the
  removed 60° cone's exact edge behavior) with cockpit-mask integration
  tests against the real shipped `COCKPIT_MASKS`: forward-and-below at a
  mild depression is visible; the same depression abeam is rejected; a
  rear-hemisphere azimuth is blocked regardless of elevation; a contact
  rejected level becomes visible once banked toward it. Each is written
  with depression/azimuth values well clear of either the placeholder or
  the derived table's boundary numbers, specifically so they hold
  unmodified across the D3 commit split — verified directly: `pytest`
  passed against both the placeholder table (commit 1) and the derived one
  (commit 2) with zero test edits.
- `body-layer/tests/test_logger.py` — two pre-existing telemetry-dict
  fixtures (`_telemetry_dict`, `_console_telemetry_dict`) gained
  `pitch_rad`/`bank_rad` keys; `OwnshipState.from_telemetry_dict` now reads
  both unconditionally (mirroring how it already reads every other
  required field), so any fixture missing them raises `KeyError` --- this
  is exactly `test_from_telemetry_dict_raises_on_missing_field`'s existing
  contract extended to two more fields, not a new failure mode.

### Checks
(body-layer/ only touched)
- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src --strict` (run from `body-layer/`, per that subproject's CWD
  requirement): pass, 31 source files
- `pytest tests -q`: pass, **543 passed** (up from 527 before this
  branch — 16 net new tests: 6 geometry, 9 cockpit_mask, 4 new visibility
  integration tests minus 4 removed FOV-cone tests). Passed identically
  against both the placeholder table (commit 1) and the derived table
  (commit 2).

### Notable Discoveries
- **Sign convention for `pitch_deg`/`bank_deg` is assumed, not verified.**
  No `aircraft-layer/research/*.md` note pins `LoGetADIPitchBankYaw`'s sign
  convention — the closest evidence
  (`2026-09-11-petrovich-detection-readout.md`: "horizon-relative elevation
  ≈ arg 876 + aircraft pitch") is consistent with positive pitch = nose up,
  but nothing pins bank's sign at all. Documented explicitly in
  `OwnshipState`'s docstring as an assumption (standard aviation
  convention: positive pitch = nose up, positive bank = right wing down),
  with the fix path spelled out if it turns out inverted (a single
  negation at the point the field is read off the wire, not a geometry
  rewrite) — flagged rather than silently assumed, per this project's
  unverified-DCS-internals convention.
- **The two screenshot-derived anchor points (nose ~45°, abeam ~15°) came
  from rough pixel-position/assumed-vertical-FOV estimates on the forward
  (`...55`) and right (`...59`) screenshots** — the left screenshot
  (`...105`) is a materially different, more zoomed-in framing that does
  not support the same pixel-to-degree estimate, so it was used only
  qualitatively (confirms the left side is more obstructed than the
  right, consistent with D5's rationale for staying symmetric anyway) and
  the wide screenshot (`...125`) uses an unknown, clearly non-default FOV
  setting, so it was used only to confirm forward is both wide and steep,
  not for a second numeric anchor. The 20°/50°/80° breakpoints are
  interpolated between the two anchors on the plan's D2 band shape, not
  independently read from any screenshot — stated plainly in the
  `cockpit_mask.py` derivation comment so a future reader does not
  mistake five breakpoints for five independent measurements.
- **`aircraft-layer` needed no change**, confirming the plan's "feasibility
  — the enabling fact": `TelemetrySample.pitch_rad`/`bank_rad` were already
  on the wire and already present in `to_dict()`'s output, so
  `from_telemetry_dict` just had two more keys to read.
