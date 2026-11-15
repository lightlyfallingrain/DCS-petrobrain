### Review Summary

Reviewed `BL-B110` Stages 0a, 0 and 1 (`feature/expected-area-check`, tip `d081674e`) against
`plans/expected-area-check/plan.md` (fifth architect pass) and root/body-layer `CLAUDE.md`. Stage 2
onward is correctly out of scope for this merge and not built. Nine implementation commits plus
agent-memory/implementation-log commits, all present on the branch; the branch was merged into this
worktree by fast-forward before review (clean tree, no conflicts).

Read in full: `plan.md` (all 1427 lines, incl. every Decision 1–11 and the Stage 0 measured
results), `implementation.md`, the full diff of every file named in "Files Changed"
(`optic_policy.py`, `position_belief.py`, `body.py`, `gaze.py`, `geometry.py`,
`naked_eye_source.py`, `decay.py`, `tuning.py`), `defaults.toml`'s rendered entries for the three
new/changed tunables, and the three flagged "existing tests changed beyond plan" diffs
(`test_mock_flight_chain.py`, `test_bl_b104_scenario_mock_flights.py`,
`test_optic_policy.py`'s stall-cooldown-window test). Ran `/invariant-check`'s checks directly
(no new finding), `ruff format --check`, `ruff check`, `cd body-layer && mypy src`, and the full
`pytest body-layer/tests -q` (3044 passed, 4 xfailed, matching the implementer's own report).

**Verdict: APPROVED.**

### Findings on the six look-hard items

1. **Deviation 2 (interrupt-while-`GLASSING` does not advance the sector) — acceptable, not a
   required fix, with one wording nit.** Code (`_decide_without_guidance`'s `GLASSING` branch,
   `not steady` path) confirmed: `_back_to_home` resets `phase_started_sim` to `now_sim` but leaves
   `scan_sector_index`/`glass_recent_steps_s` untouched — the interrupted sector's sweep restarts
   rather than advancing, and the interrupted look's elapsed time is dropped from the rolling
   window entirely (neither counted nor rolled). This genuinely differs from the plan's Co-moving
   Fields row ("as the 'step ends' row — the time spent counts; pending marks dropped").
   Consequences checked, not assumed:
   - `is_steady`'s threshold (`STEADY_RATE_LIMIT_DEG_S` = 12°/s) is far above the body-rotation
     rates the plan's own approach-profile analysis uses (0.5–3°/s for circling/sidestepping at
     ~28 m/s). So the "not steady" branch of this gap fires only on genuine abrupt manoeuvring —
     combat turns, not the user's stated cruise/orbit profile — making it rarer than the
     implementation note's "pilot-driven and rare" framing implies for that one trigger (the
     `lower_binoculars` command trigger genuinely *is* pilot-driven; "not steady" is airframe-
     dynamics-driven, not command-driven). Worth a one-line wording fix in the code comment, not a
     behaviour fix.
   - The failure mode this creates — a sustained abrupt manoeuvre could keep re-starting the same
     sector's sweep and never let the other three sectors take their turn — is real but bounded by
     the same rate threshold: at 12°/s+ sustained, the aircraft is already past any steady orbit,
     and the sector resumes its normal rotation the moment a poll reads steady again. It does not
     silently violate the static `I2` coupling invariant (which is checked against the nominal
     12 s/4-sector model at import time, not runtime), and it does not strand binoculars up
     indefinitely — the interrupt always returns to `SCANNING`/eye.
   - Net: this is a local, reversible, stated simplification exactly as the implementer framed it,
     and its blast radius is smaller than "every interrupt" because the two triggers have very
     different real-world frequency. No required fix.

2. **Deviation 1 (`decide` keeps `scan_cycle_period_s` naming, new params default to pre-Stage-1
   behaviour) — verified safe.** `body.py:752-840` calls `_resolve_sector_scan` every poll and
   passes the *real* `sector_wedge_deg`/`n_sectors`/`glass_budget_per_cycle_s=GLASS_BUDGET_PER_CYCLE_S`
   into `decide_optic` — not the backward-compatible defaults. The only caller relying on the
   defaults is the ~130 pre-existing `test_optic_policy.py` call sites, which is exactly what the
   deviation claims. This is not the plan's own wiring-defect pattern repeating (that defect was
   `body.py` passing a *constant* regardless of what was commanded, discovered and fixed by this
   same merge) — here the production caller genuinely threads the new mechanism through. Confirmed
   by reading the call site directly, not by trusting the implementer's note.

3. **Stage 0a `_apply_floor` cap — matches Decision 7(a) exactly.** `floor_trace = min(floor_trace,
   prior_inflated_covariance.trace())`, with `prior_inflated_covariance` passed as `None` for a
   founding look (`fold_position`'s `prior is None` branch) and as the *same* `prior_covariance`
   value the fuse itself already computed via `_inflated_since_last_fuse` for a real fuse — one
   `min`, one parameter, no second anchor, exactly as specified. `test_position_belief.py`'s four
   new Stage-0a tests split the growth-0/armour-growth cases as the plan's own "What it does not
   do" note requires (fixed component never rises above the post-fix value; a moving class's floor
   still grows back toward naked grade over ~6–7 fuses). BL-B108's own fences
   (`test_relative_distance_sweep.py`/`test_relative_distance_scenarios.py`/`test_position_belief.py`,
   116 tests per the implementation log) were run before and after per the plan's own gate, and the
   full suite run confirms nothing moved (3044 passed). `clamp_to_detection_envelope`'s separate
   hold path (a different function, pre-existing, untouched by this diff) correctly does not
   interact with this cap — it was never in scope.

4. **Co-moving Fields — every new field carried through both fresh-construction sites, every
   external transition handled.** Grepped `OpticState(` directly (not trusted from the plan's own
   count): two fresh-construction sites in `optic_policy.py` (`GLASSING` entry ~2980, `SEARCHING`
   entry ~3402) both explicitly carry `scan_sector_index`/`glass_recent_steps_s` forward (the
   `GLASSING` site also carries `glass_step_started_sim`, correctly left at its `None` default on
   the `SEARCHING` site, which never has an active glass step to preserve). `body.py`'s three
   external transitions (scan command change, OBSERV-off, OBSERV-on) match the Co-moving Fields
   table's rows exactly: scan-command-change and OBSERV-off both reset `scan_sector_index=0` with a
   cleared window; OBSERV-on leaves sector/window state untouched. The interrupt-while-`GLASSING`
   row's deviation is covered under item 1 above.

5. **Budget/stall/priority mechanics verified directly in code, not from the docstrings.**
   `_glass_budget_admits_look` gates look *starts* only (`spent_s + MAX_LOOK_S <=
   glass_budget_per_cycle_s`, no cutoff of a running look) — matches the plan's Decision 5 (b)
   exactly. `_rolled_glass_window` keeps the last `n_sectors - 1` entries (rolling, not a per-cycle
   reset) — matches the plan's correction to alternative (b) as written. `GLASS_STALL_COOLDOWN_S`
   is floored through `_EFFECTIVE_GLASS_STALL_COOLDOWN_S` at `OPTIC_RETRY_INTERVAL_S`, the same
   pattern `SIGHT_STALL_COOLDOWN_S` already uses, and is passed into `GLASSING`'s own
   `is_worth_a_look` call as `stall_cooldown_s`. `choose_glass_look`'s three buckets (`0`/`1` via
   the shared `_classification_bucket` helper, `2` for exact-location-only) resolve exactly as
   Decision 8 REVERSED specifies: type-identification and classification before exact location,
   watched still wins inside each bucket via the unchanged `choose_look`. The rough-location fence
   (`test_estimation.py`) asserts `0.2 · R` down-range with **no 250 m floor**, matching the
   re-check-3 answer, over the full stated range/altitude grid. `_within_sector` filters on this
   poll's believed azimuth with the half-binocular-field margin applied by the caller (`body.py`),
   matching the "sector margin" item.

6. **The three flagged test changes are data updates with premise intact, not premise rewrites.**
   - `test_mock_flight_chain.py`: contact count changes from 1 to 2 and observation count from 23
     to 24, because the commanded-scan wiring-defect fix genuinely changes the fixture's binocular
     cadence (3-leg "ahead" scan: 6 s real period vs. the old bare 16 s). The assertion's *premise*
     — "the pipeline reaches this exact, fully-enumerated contact state" — is unchanged; only the
     state it reaches changed, because a previously-undetectable fixture object becomes genuinely
     reachable once the wiring defect is fixed. The new numbers are backed by actually running the
     pipeline and reading `Counter(...)`/full contact facts, not recomputed by hand.
   - `test_bl_b104_scenario_mock_flights.py`: the crude round-number range-error bound rises from
     700 m to 800 m because the per-sector scan's cadence changes shift which look geometries
     contribute to this scenario's fixed, hash-derived field realisation. Confirmed every poll
     still clears the far more rigorous, model-honest 3-sigma-per-poll budget checked immediately
     below it in the same test — the loosened round-number bound is not covering up a real
     regression, it is tracking a benign shift in which draws land where.
   - `test_optic_policy.py`'s stall-cooldown-window-widening test: the premise ("a naturally
     completed look on a stalled contact eventually becomes re-eligible") is explicitly preserved
     in the updated docstring; only the loop window widens (144 s → 240 s) because
     `GLASS_STALL_COOLDOWN_S` (180 s) now governs this exact scenario instead of the shorter
     `OPTIC_RETRY_INTERVAL_S` (64 s) — the longer cooldown is a correctly-anticipated consequence of
     Stage 1's own selectivity gap fix, named in the plan itself ("Selectivity", the retry gap).

   None of these three needed escalation under `AGENTS.md`'s "existing tests rewritten, not
   extended" rule — in each case the assertion still tests the same claim, with updated numbers
   traced to a named, intended mechanism change, not a silently loosened or reinterpreted check.

### Required Fixes

None.

### Optional Refinements

- **`optic_policy.py`'s look-follow code comment (lines ~3168–3177 and ~3185–3194) is duplicated
  verbatim** across the `glassing_state = state` binding and the block that follows it. Harmless
  (a comment, not logic) but worth collapsing into one block next time this function is touched —
  not worth a commit on its own.
- **The "pilot-driven and rare" framing for Deviation 2** (implementation.md and the inline code
  comment) slightly overstates how pilot-driven the `not steady` half of the interrupt is — see
  finding 1 above. A one-line wording clarification (not a behaviour change) would make
  the next reader's risk assessment faster; optional, since the underlying 12°/s threshold already
  bounds the real exposure correctly.
- **`BL-B110.md`'s roadmap entry** should carry the Stage 0 STOP finding (long-gap stationary
  false-trigger rate 7–27%, exceeding the 10% gate) forward loudly for whoever picks up Stage 2 —
  the implementer's log says this is already recorded in three places including the roadmap entry;
  confirmed present. No action needed, noted here only so DoD's harvest step does not need to
  re-derive it.

### Verdict

**APPROVED.**

### Review Confidence

**Full read.** Every file named in "Files Changed" was diffed and read in context, not sampled;
all six "look hard" items were checked against the actual code paths (not the implementer's prose
alone); `ruff format --check`, `ruff check`, `mypy --strict` and the full `pytest` suite
(3044 passed, 4 xfailed) were all re-run directly from this worktree, not taken on the
implementer's report. The one thing this review did not re-derive from scratch is the Stage 0
probe-harness's own statistical measurements (the residual-fold/false-trigger percentage tables) —
those are read and sanity-checked against the stated gate (~10%) and the STOP finding is confirmed
present and consistent across `plan.md`, `implementation.md`, and the test module's own docstring,
but the underlying Monte Carlo runs were not independently re-executed.
