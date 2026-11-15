### Performance Review

Branch `fix/same-optic-gate-indefinite` vs `main`, batch = Stages for this fix (single-batch bug
fix, pre-DoD). Target: body-layer's own phase budget per root `CLAUDE.md` -- **no hard real-time
budget yet** (that starts once Petrobrain Runtime work begins); the applicable discipline is "no
per-request allocations on hot paths" and "prefer batching/precomputation" against body-layer's own
measured poll budget (default poll interval **1.0 s**, not the stale "5 Hz" docstring figure --
`.claude/agent-memory/performance-reviewer/project_body_layer_poll_loop_diagnosis.md`).

Scope: `correlated_innovation`'s new `_max_c_down_for_psd` (closed-form quadratic + one `sqrt`),
now run unconditionally for both callers -- `passes_gate` and `contacts_plausibly_same`
(`belief/association_over_time.py`) -- where before the gate path (`for_fusion` defaulting `False`)
applied no cap at all, and the fold path (`for_fusion=True`) applied only the cheaper per-axis cap.

### Measurement

Can-this-fail probe run first in both scripts (asserts `_max_c_down_for_psd` returns a positive cap
on a well-conditioned input and does not raise on a degenerate `K`, and that `correlated_innovation`
end-to-end returns a sane `S.xx` on a known-good input) -- both passed before any timing was taken.

Micro-benchmark, `body-layer/.venv/bin/python -I`, `PYTHONPATH=src:../world-model/src`, 100k-200k
calls, uniform-random realistic inputs, `main` imported by file path alongside the branch's own
module so both run in the same process:

| path | before (main) | after (this branch) | delta |
|---|---|---|---|
| gate caller (`for_fusion=False` on `main` -- no cap at all) | 4.58 us/call | 5.78 us/call | **+1.20 us (+26%)** |
| fold caller (`for_fusion=True` on `main` -- per-axis cap only) | 5.14 us/call | 5.78 us/call | **+0.64 us (+12.5%)** |
| `_max_c_down_for_psd` alone vs. the old per-axis-only cap alone | 0.64 us/call | 1.67 us/call | +1.03 us |

Projected per-tick cost (1 Hz poll) at contact-store sizes this project has actually measured
(`.claude/agent-memory/performance-reviewer/project_group_reporting_cohesion_scale.md`,
`project_contact_store_pruning_live_count_axis.md`: 2026-09-28 sortie peak 16 concurrent / up to
554 total-ever-seen, the unpruned axis `BL-B23` left open):

| candidates x percepts/tick | old | new | delta |
|---|---|---|---|
| 16 x 5 (typical sortie peak) | 0.37 ms | 0.46 ms | +0.10 ms |
| 142 x 10 (2026-10-05 sortie's 142 live contacts) | 6.51 ms | 8.21 ms | +1.70 ms |
| 554 x 10 (worst observed total-ever-seen) | 25.4 ms | 32.0 ms | +6.6 ms |

Test-suite runtime: the three directly touched files (`test_position_belief.py`,
`test_relative_distance_sweep.py`, `test_expected_area_trigger.py`) run in 45.3s, 120 passed; the
slowest items (2.64s, 1.89s, 1.46s) are the ensemble/sweep harnesses' own statistical trial counts
(unchanged by this diff), not the per-call cost under review.

### Findings

#### `_max_c_down_for_psd` added to every gate evaluation
- **Location:** `belief/position_belief.py::correlated_innovation`, called from
  `belief/association_over_time.py::passes_gate` (per unclaimed candidate contact, per percept not
  resolved by continuity -- `belief/contacts.py:1267`) and `::contacts_plausibly_same` (per
  `CONTACT_DETECTED`-suppression pair check, `belief/callouts.py:836`).
- **Risk:** at the worst total-ever-seen contact count this project has actually observed (554,
  `BL-B23`'s known-open unpruned-store axis) and a generous 10 unresolved percepts in one poll, the
  added cost is ~6.6 ms against a 1.0 s poll period -- well under 1%. At the sortie peaks actually
  seen (16 concurrent, 142 live), it is sub-millisecond. No credible scenario at this project's
  actual scale pushes this into a budget-relevant figure; the dominant poll-loop cost by two orders
  of magnitude remains `group_salience.group_salient_ids` (~300 ms/poll, already on record).
- **Action:** MONITOR. Re-measure only if the unpruned-store axis (`BL-B23` lineage,
  `.claude/agent-memory/performance-reviewer/project_contact_store_pruning_live_count_axis.md`) is
  ever allowed to grow materially past the 554 already observed, or if a future milestone raises
  live simultaneous contact counts into the low hundreds (the threshold the group-clustering MONITOR
  already names).
- **Mitigation (not needed now):** none required; if it ever is, `_max_c_down_for_psd`'s closed-form
  solve has no obvious cheaper reformulation without losing the exactness the fix depends on
  (it is a one-time quadratic per pair, already closed-form rather than iterative).

#### No new per-request allocation
- **Location:** same function.
- **Risk:** none found. `sum_covariance = prior_covariance + look_covariance` is now a named
  intermediate reused by both the PSD cap and the final `S` computation, where `main` recomputed
  the equivalent sum inline once -- this is a *de-duplication*, not an addition, and the count of
  heap-allocated `Covariance2D`/`_Matrix2D` instances per call is unchanged from `main`. No lists,
  dicts, or per-call containers are built inside the new code.
- **Action:** none.

#### `for_fusion` parameter removed, not just defaulted
- **Location:** `correlated_innovation` signature; both call sites in `position_belief.py` and
  `association_over_time.py` updated accordingly (confirmed by diff and by the passing test suite).
- **Risk:** none from a performance angle -- flagged only because it closes off a previous asymmetry
  (gate uncapped, fold capped) that this fix's whole point is to remove. No stale caller left calling
  with the old keyword (would be a `TypeError`, not a silent miss) -- verified via `grep` across
  `src/` and `tests/` for `for_fusion=`.
- **Action:** none (correctness/scope, not performance; noted for completeness).

### Verdict
APPROVED
