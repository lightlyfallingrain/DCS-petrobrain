---
name: correlated-innovation-psd-cap-cost
description: measured microsecond cost of correlated_innovation's always-applied PSD cap (BL-B108/same-optic-gate-indefinite fix) at realistic body-layer contact-store scale
metadata:
  type: project
---

`fix/same-optic-gate-indefinite` made `belief.position_belief.correlated_innovation` apply
`_max_c_down_for_psd` (closed-form quadratic + one `sqrt`) unconditionally for both callers
(`passes_gate`, `contacts_plausibly_same`), where before the gate path applied no cap at all and
the fold path applied only the cheaper per-axis cap.

Measured (`body-layer/.venv`, `python -I`, uniform-random realistic inputs, 100k-200k calls,
`main` vs. the fix imported side by side in one process):

- gate caller: 4.58 us/call -> 5.78 us/call (+26%)
- fold caller: 5.14 us/call -> 5.78 us/call (+12.5%)
- `_max_c_down_for_psd` alone vs. old per-axis-only cap alone: 0.64 -> 1.67 us/call

Projected per-tick cost (1 Hz poll) using this project's own already-measured contact-store sizes
([[group_reporting_cohesion_scale]], [[contact_store_pruning_live_count_axis]]: 16 concurrent
typical, 142 live / 554 total-ever-seen worst observed): +0.10 ms, +1.70 ms, +6.6 ms respectively
-- all well under 1% of the 1.0 s poll budget, and two orders of magnitude below the dominant
poll-loop cost (`group_salient_ids`, ~300 ms/poll, [[body_layer_poll_loop_diagnosis]]).

**Why this is worth keeping:** `correlated_innovation` is called per percept per unclaimed
candidate contact in `contacts.py`'s gate-scan loop, which inherits `BL-B23`'s known-open
unpruned-total-ever-seen axis -- any *future* change that adds cost inside `correlated_innovation`
or raises the candidate count should be checked against this same per-tick projection table rather
than re-deriving contact-store scale from scratch. Verdict at review time: APPROVED, no mitigation
needed -- re-measure only if the unpruned-store axis grows materially past 554, or live
simultaneous contacts move into the low hundreds (the same threshold
[[group_reporting_cohesion_scale]] already names for its own O(n^2) MONITOR).
