---
name: bl16-lv-estimator-ring-buffers-confirmed-fixed
description: flight_control.lua's LV-0/LV-1 estimator ring buffers (est_ring_*) implement both NOW items perf-plan-review.md requested -- fixed-size preallocated arrays with incremental least-squares sums, and the unselected velocity source gated behind FLIGHT_TRACE_ENABLED -- verified in code, not just planned
metadata:
  type: project
---

`plans/flight-lift-vector/perf-plan-review.md` (plan-time review, before any code) flagged two NOW
items for the BL-16 lift-vector estimator: (1) the unselected velocity source (`"position"` vs.
`"vector"`) must not keep computing forever past LV-0, and (2) the least-squares windows must be
fixed-size preallocated ring buffers with incremental running sums, never an O(window) per-frame
refit or a growing table. The first code-level review (`plans/flight-lift-vector/performance.md`,
tip `bbddd80b`) confirmed both landed exactly as requested:

- `flight_control.lua`'s `est_ring_new`/`est_ring_push`/`est_ring_slope`/`est_ring_mean`
  (L1967-2117 at that tip) use `EST_RING_CAPACITY`-sized arrays allocated once, with
  `sum_t`/`sum_t2`/`sum_v`/`sum_tv` updated O(1) amortized per push (add newest, evict oldest) —
  never refit from stored samples except in `est_ring_rebase`, the one deliberate exception for
  the periodic timestamp-rebase that bounds cancellation error over a long session.
- `read_estimator_raw`'s unselected-source reads and ring pushes are gated behind
  `FLIGHT_TRACE_ENABLED` (not the always-on `velocity_source == "vector"` check alone) — the common
  case (flag off) computes one velocity source per frame, not two.

**Reusable lesson**: when a plan-time performance review asks for a specific code shape (not just
"be careful"), the follow-up code review should grep for the exact mechanism requested and confirm
it, rather than re-deriving a fresh risk assessment from scratch — `test_flight_control_estimator.
py`'s own 3-simulated-hour-at-30 Hz test is the kind of evidence that settles "fixed, not just
claimed fixed" for a ring-buffer/incremental-sum design.

See also `project_bl16_m1_m2_redundant_envelope_measured_reads`,
`project_bl16_mode1_rotor_rpm_seam_dormant_arg_proxy` — this file's prior per-frame findings, both
also confirmed still fixed/unchanged by this same review pass.
