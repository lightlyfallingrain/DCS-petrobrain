---
name: cockpit-visibility-mask
description: cockpit-visibility plan's body-relative occlusion mask replacing the flat FOV cone -- geometry sign conventions and test-robustness trick
metadata:
  type: project
---

`plans/cockpit-visibility/plan.md` replaced `perception/visibility.py`'s `NAKED_EYE_FOV_HALF_WIDTH_DEG`
flat azimuth cone with a body-relative depression-per-azimuth mask (`perception/cockpit_mask.py` +
`geometry.body_relative_direction`), landed as 2 commits (244d436 mechanism, f0945c2 calibration) per
D3.

- `OwnshipState.pitch_deg`/`bank_deg` sign convention is **assumed, not verified**: standard aviation
  (positive pitch = nose up, positive bank = right wing down). No aircraft-layer research note pins
  `LoGetADIPitchBankYaw`'s real sign. If a live sample shows it inverted, fix is a single negation
  where the field is read off the wire (`OwnshipState.from_telemetry_dict`), not a geometry rewrite.
- Integration-test trick for a D3-style mechanism/calibration split: write `check_visibility`-level
  tests using depression/azimuth values *well clear* of any plausible table's boundary numbers (e.g.
  10° depression at the nose = trivially visible under any reasonable table, 40° abeam = trivially
  rejected under any reasonable table) so the same tests pass unmodified before and after the
  calibration commit swaps in real numbers -- verified directly by running pytest against both
  tables with zero test edits. Pure mechanism tests (interpolation, rear cutoff, symmetry) still
  belong in their own file against a synthetic mask, never the shipped `COCKPIT_MASKS`.
- Upward visibility falls out for free: `is_visible` only checks `depression <= max_depression`, and
  above-boresight depression is negative, trivially under any positive table value -- no special case
  needed, worth remembering as a pattern for "we deliberately don't model X" requirements.
- Angle derivation from screenshots is real but thin: only 2 of 4 reference screenshots gave usable
  pixel-to-degree anchors (forward ~45°, abeam ~15°); the other two (left, wide) used different
  camera FOV/zoom and were only usable qualitatively. Don't assume "4 screenshots" means "4
  independent numeric measurements" if asked to extend/verify this table later.
