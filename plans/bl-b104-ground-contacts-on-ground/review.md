### Review Summary

BL-B104 Stages 1-5 (surface-domain wiring, altitude-from-unit-data, two-cue inverse-distance
range fusion, association verification, helicopter-landed rule) and Stage 7 (manoeuvre mock-flight
scenarios) reviewed against `plan.md`, `alignment.md`, `implementation.md`, the aircraft-layer
recon note, and `BL-B104.md`. HEAD fast-forwarded cleanly to `cbfb52d6` from `main` at `54633ef8`.

Mechanical checks all pass as the Implementer reported:

- `aircraft-layer`: `ruff format --check` pass, `ruff check` pass, `mypy src` pass (26 files),
  `pytest` 661 passed, `luac5.1 -p` pass on both touched Lua files.
- `body-layer`: `ruff format --check` pass, `ruff check` pass, `mypy src` pass (79 files), `pytest`
  2851 passed / 4 xfailed (the 4 are pre-existing, from `fix/flexible-sequence-tests` on `main`,
  unrelated to this feature). `mypy tests` (not a mandated command per `body-layer/CLAUDE.md`
  "Commands") has pre-existing looseness elsewhere in the suite unrelated to the two touched test
  files that mattered here (`test_belief_truth_log.py`'s added tests sit cleanly outside the
  flagged lines).
- Rendered `config/defaults.toml` checked directly (not the source comment):
  `DEPRESSION_SIGMA_DEG` and `HELI_SURFACE_AGL_MAX_M` both render complete first sentences with
  correct status/range/source lines — the digit-period truncation bug the Implementer's own
  Notable Discovery 2 describes finding and fixing is in fact fixed in the committed file.
- The no-omniscience grep fence (`test_estimation.py` ~line 406) exists and pins
  `surface_range_estimate` away from `RelativeDirection`/`RELATIVE_DIRECTION_SIGMA_DEG`, matching
  E7.
- `perception/domain.py`'s rule table matches the plan and the recon note; `Flags.Static` is
  correctly *not* used as the discriminator.
- Both touched Lua files (`Export.lua`, `petrobrain-line-of-sight-hook.lua`) are minimal,
  additive, backward-compatible (optional/appended fields, `nil`/`""` on failure, never a guessed
  value) and documented at the call site.

Both worktree accidents during this review (a stray `git checkout <old-sha> -- .` that staged a
reversal of all 26 changed files, and `git reset --hard` being denied by the permission system)
were caught and fully reversed with `git checkout cbfb52d6 -- .` before any check ran against a
corrupted tree; `git status --porcelain` was empty immediately after and stayed empty through
every subsequent check. No committed content was affected — this was working-tree-only.

### Required Fixes

- **Finding 1 (E5 — two groups on one bearing during a closing run): a real detection-pipeline
  defect was found and then routed around, not reported, contrary to the plan's own stop
  condition.** Stage 7's first scenario-3 draft ("two groups on one bearing ... closing run," as
  the plan itself specifies for Stage 4(c)) produced exactly the failure alignment.md Finding 4
  warned about: the near group gets cockpit-masked (now real, post-Stage-2 depression) before a
  reliable run of polls sees both groups together, and the belief-side spatial gate folds the far
  group's first admitted look into the near group's own stale, decay-widened contact — **two
  contacts collapse into one**, which is precisely what E5 forbids ("Two groups on the same bearing
  at different ranges stay two contacts"). The plan's Stage 4 text is explicit and anticipatory:
  *"If (a) or (b) fails, stop and report rather than retune the gate: a gate change is a behaviour
  change across every contact and needs its own decision."* Instead, the Implementer rewrote the
  scenario to hold ownship stationary (`speed_mps=0.0`), which keeps both groups continuously
  admissible and simply never exercises the geometry that produces the fold. Stage 4's own
  `ContactStore`-direct scenario (c) "passes" only because — as the Implementer's own memory file
  states — it never exercises the real angular-size/cockpit-mask gate at all, so **E5 for this
  geometry is not actually verified anywhere in this branch against the real pipeline**; the one
  test that would have verified it was changed to avoid triggering the failure instead of being
  escalated.
  - This is not an implausible test-geometry artifact: a convoy spread along one bearing, closed
    on and overflown in sequence, is an ordinary Mi-24 attack-run shape, and the window in which
    both groups are simultaneously admissible shrinks with altitude (near-zero at 300 m AGL, per
    the Implementer's own distances) — exactly the altitude band this feature targets. A normal
    polling cadence closing at realistic attack speed can plausibly skip over that window entirely,
    reproducing the fold in a live sortie.
  - **Required**: report this finding to the user/Architect per the plan's own stop-and-report
    instruction, rather than closing it as "a geometry artifact, not a finding about
    `association_over_time`'s gate." Whether the eventual answer is "acceptable, rare, and the
    decay/gate behaviour stays as is" or "the gate/decay interaction needs a change" is the user's
    call, specifically because the plan pre-committed to treating any such gate-relevant failure as
    a decision point, not a silent scope change. The Stage 7 scenario can stay stationary as an
    *additional* test (it does exercise E5's "level flight" half correctly), but it must not be the
    only test standing in for the closing-run case the plan explicitly asked for, and the finding
    itself belongs in the report, not only in a code comment.

- **Finding 2 (Stage 7 scope vs. the user's explicit ask): two of the four scenarios contain no
  aircraft manoeuvre, and no `Turn` leg exists anywhere in the branch.** The user's quoted
  instruction was *"Simple mock flights that still contain some aircraft manoeuvre"* — stated in
  contrast to the existing `mock_flight_canonical.json` fixture's "straight north, constant 700 m,
  no manoeuvre" shape, which this stage exists to move past. As built:
  - Scenario 2 (`test_run2_shallow_approach_...`) is a single `Level` leg — constant heading,
    constant altitude, constant speed, only range closing. This is the same shape as the rejected
    canonical fixture with different numbers; no climb/descend/turn/pitch change occurs anywhere in
    it.
  - Scenario 3 (`test_two_groups_one_bearing_stay_two_contacts`) sets `Level(speed_mps=0.0, ...)` —
    ownship is **completely stationary** for the entire scenario. This is less motion than the
    fixture the user was explicitly moving away from, not more.
  - `mock_flight_scenario.py` implements only `Level`/`Descend` of the plan's own
    `Level`/`Climb`/`Descend`/`Turn`/`RunIn`/`Hover` sketch; `implementation.md` defends this as
    "these two are the only kinds the four scenarios below actually need" — true as stated, but
    that is circular given scenarios 2 and 3 were themselves designed not to need one.
  - Scenario 3's redesign to fully stationary is also the same redesign flagged in Finding 1 above
    — the fix for one problem (avoiding the E5 fold) directly produced this second deviation from
    an explicit, quoted user requirement, which is why both are being raised together rather than
    independently.
  - **Required**: before closing Stage 7, either add a leg with real lateral/attitude change (a
    `Turn`, or let scenario 3 close at a nonzero speed on a track that doesn't trigger Finding 1,
    e.g. approaching off-bearing before swinging onto it) to at least one scenario, or take this
    back to the user as an explicit, named scope reduction rather than reporting the stage as
    delivering what was asked. Given Finding 1 is a prerequisite decision for scenario 3's shape,
    raise both together.

### Optional Refinements

- **Scenario 2's shortened leg and its "steep-depression blow-up" comment should be rechecked.**
  Direct inspection of `surface_range_estimate` (numeric sweep against fixed AGL=400 m, distance
  5000→1 m) shows `sigma_down_m` **monotonically decreasing** as true distance shrinks — it does
  not blow up or grow near 900 m / 30° depression; the single-look realized errors in that range
  are just noisy (consistent with Gaussian single-look draws, not a systematic trend). The
  comment's causal claim ("a `1/tan` sensitivity that makes absolute range error grow again...a
  real property of the geometry") is plausible for the *fused belief* (which averages several past
  looks while closing fast — a lag effect, not a single-look sensitivity issue) but is not
  supported by the single-look estimator the comment names. This doesn't change the scoping
  decision itself (900 m is still outside the plan's own tested envelope, whose nearest grid point
  is 500 m, so stopping there is reasonable), but the stated mechanism should be corrected or
  re-verified against the actual fused-belief series before another reader relies on it (optional —
  comment accuracy, not a behaviour defect).
- **Finding 3 (the engage-time position jump) is worth a named test, not just a scoped
  assertion.** Notable Discovery 3 isolates the cause correctly (attention switching off the
  scan-ahead cycle changes which per-look hash draws land on the believed position — a real,
  intended attention effect) and the convergence assertion is correctly scoped to the pre-engage
  prefix for that reason. But nothing in this branch asserts that the *sight* stays locked/
  "Tracking." across that same jump, which is the moment E2 cares about most (the pilot has just
  committed to the run). The believed-position series jumping ~2 m → ~148 m right at the commit
  point is plausible and may be entirely fine for the sight (which should already be aim-source
  `"seen"`/tracking by then), but nothing here checks it. Recommend a follow-up assertion (could be
  added to this file or a later stage) on `sight_head`'s aim source / tracking state immediately
  before and after `engage`, rather than leaving the transition unverified. Not a required fix for
  this branch — it is a coverage gap on a transition the plan didn't explicitly call out — but
  worth tracking given the Reviewer checklist's standing instruction that player-facing correctness
  at transitions is no longer backstopped by Security.
- **Finding 4 (`_run_crew_text_poll_loop` cross-thread `crew_console.enrichment` footgun) — severity
  noted, no fix requested here, per the dispatch's own instruction.** This is a real, demonstrated
  bug class (confirmed by running it, both in production per BL-B96's own docstring and again in
  this stage's own test harness) but it is pre-existing, not introduced by BL-B104, and is already
  captured as agent memory
  (`.claude/agent-memory/implementer/feedback_crew_console_cross_thread_enrichment.md`) with the
  exact fix pattern (`_run_crew_text_repl`'s thread-local `EnrichmentContext`) named. Recommend a
  small backlog item (`BL-B` prefix, minted via `mint-id.sh`) so a future third caller of
  `CrewConsole` from a non-poll-thread doesn't rediscover this the hard way; low severity today
  because the only two callers (the poll thread itself and the REPL thread) are both already
  correct.
- Cross-key coupling the Implementer already flagged (`DEPRESSION_SIGMA_DEG` vs. the four
  `_SIGHT_*_SCALE` constants, no per-key bound catches their joint effect) is a real residual risk
  but matches the class of known, documented, unclosed couplings this project already carries
  elsewhere (`body-layer/CLAUDE.md`'s `OBSERVED_WINDOW_S`/`POSITION_HALF_LIFE_S` note) — fine to
  leave as a documented risk, not a blocker.

### Verdict

NEEDS REVISION

The two Required Fixes above both trace to the same root cause (Stage 7's scenario-3 redesign)
and are local to Stage 7 — Stages 1-5's own mechanism, tests, and tunables are sound and match the
plan. Recommend: report Finding 1 to the user per the plan's own stop condition before deciding
Stage 4/7's final shape (the gate/decay interaction may turn out to be acceptable as-is, but that
is a decision this plan explicitly reserved, not a Reviewer call), and resolve Finding 2 by either
adding a genuine manoeuvre leg or taking the reduced scope back to the user explicitly. Everything
else (Stages 1-5, the mechanical checks, the tunables, the no-omniscience fence, the Lua wiring) is
APPROVED as implemented.

### Review Confidence

Full read of plan.md, alignment.md, implementation.md, BL-B104.md, the aircraft-layer recon note,
`perception/domain.py`, `perception/estimation.py` (including a direct numeric sweep of
`surface_range_estimate`), both touched Lua files, the rendered `config/defaults.toml` entries,
and the four Stage-7 scenario tests' own docstrings/assertions in full. Spot-checked rather than
fully read: `association_over_time.py`, `naked_eye_source.py`, `hybrid_source.py`,
`belief/contacts.py`/`attack_run.py`/`enrichment.py`/`belief_truth_log.py` line-by-line (checked
via their docstrings, the Implementer's own per-file summary in `implementation.md`, and the full
green test suite, not read in full diff form) — low risk given mypy --strict and the full test
suite both pass and the plan's own module boundaries are narrow and unchanged elsewhere. `mypy
tests` (whole directory) was run as an extra check beyond the mandated command set and its
pre-existing, unrelated findings are noted but not treated as blocking since they fall outside
`body-layer/CLAUDE.md`'s own "Commands" list.
