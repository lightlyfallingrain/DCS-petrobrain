---
name: bl-b110-expected-area-check-sector-and-location-gain-cost
description: Measured per-poll cost of BL-B110 Stage 1's new per-sector scan resolution and per-contact location_gain_for -- all negligible, two MONITOR notes (precomputable SCAN_PLAN partition, inherited choose_look O(n^2))
metadata:
  type: project
---

Performance review of `BL-B110` Stages 0a/0/1 (`plans/expected-area-check/plan.md`,
`feature/expected-area-check` @ `20de6ab1`). Full report:
`plans/expected-area-check/performance-review.md`.

## New per-contact cost: `location_gain_for` / `look_target_for`

`look_target_for` (called once per live contact from `body._look_targets`, unchanged O(n) call
site) now also computes `location_gain_for` -- `profile_for` (already `@cache`d, confirmed
present), `apparent_extent_m`, `distinctiveness_of`, `tier_ranges`, one
`PositionEstimate.range_uncertainty_m`, one `look_sigma_m`. **Measured directly**
(`body-layer/.venv`, real production functions): `location_gain_for` alone **1.92 µs/call**;
whole `look_target_for` build **5.75 µs/call** (up from [[project_9k113_search_and_choose_look_scaling]]'s
pre-batch ~4.1 µs/contact -- this batch adds ~1.6 µs/contact). At 55 contacts (largest recorded
sortie) that's 0.32 ms/poll; at 200, 1.15 ms/poll. Three orders of magnitude under the 1.0 Hz
budget. **Non-issue, MONITOR only** -- consistent with every other per-contact cost finding in
this subsystem.

## `choose_glass_look` inherits `choose_look`'s O(n^2), fed a *narrower* candidate set

`_within_sector` filters `targets` down to the swept sector's own wedge (plus half a binocular
field margin) **before** `choose_glass_look`/`choose_look` run -- so this batch's `k` is bounded
by one sector's worth-looking contacts, strictly narrower than the pre-Stage-1 unsectored
candidate set. `choose_look`'s own O(k²) cost is unchanged and not re-measured here; see
[[project_9k113_search_and_choose_look_scaling]] for its existing figures (18.75 µs @ k=5 up to
27.66 ms @ k=200). This batch does not add exposure to that pre-existing MONITOR item -- if
anything it narrows it.

## `sector_runs_for_legs(SCAN_PLAN)` recomputed every poll, unconditionally, in the free-scan path

`body._resolve_sector_scan` calls `perception.geometry.sector_runs_for_legs(SCAN_PLAN)` on every
poll while free-scan is active, even though `SCAN_PLAN` is a module-level constant that never
changes at runtime -- classic "precompute instead of per-request" case. **Measured: 1.07 µs/call**
against the real `SCAN_PLAN` (8 legs) -- 0.0001% of the 1.0 Hz budget, genuinely negligible at
this project's table sizes. Flagged as MONITOR, not NOW, because the mechanical fix (hoist to a
module-level constant, same pattern `SCAN_CYCLE_PERIOD_S` already uses) is trivial and the cost is
real but immaterial -- revisit only if `SCAN_PLAN`-scale tables grow by orders of magnitude, which
this project's o'clock-hour structure makes implausible.

See [[project_body_layer_poll_loop_diagnosis]] for the 1.0 Hz budget this is measured against.
