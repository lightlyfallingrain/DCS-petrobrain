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

---

## Follow-up review, 2026-10-30 — Stage 8 + Stage 7 amendment

Branch `feature/bl-b104-ground-contacts-on-ground`, fast-forwarded cleanly from `54633ef8` to
`0831944e` (HEAD was a strict ancestor; tree was clean before and after). Reviewed `plan.md`'s new
Stage 8 and amended Stage 7, `explore-notes.md`'s "E5 fold on a closing run" decision,
`implementation.md`'s Stage 8 / Stage 7 amendment sections, against the prior `review.md` Findings
1/2 above.

No venv existed in this worktree; built one (`body-layer/.venv312`, Python 3.12, matching
`pyproject.toml`'s `>=3.11`) and ran the mandated commands directly — all pass, matching the
Implementer's own report exactly:

- `ruff format --check src tests`: pass (190 files).
- `ruff check src tests`: pass.
- `cd body-layer && mypy src`: pass (79 source files).
- `pytest`: 2855 passed, 4 xfailed (same 4 pre-existing xfails `main`'s `fix/flexible-sequence-tests`
  carries, unrelated to this feature).

**Mechanism review (dispatch point 1).** `contact_growth_rate_mps` (`association_over_time.py`
lines 368-416) matches the plan exactly: installation components return `0.0` unconditionally,
checked first; `not contact.on_surface` (air contacts) take the unconditional class-rate branch
regardless of `Contact.motion`, confirmed bit-identical by a dedicated test
(`test_contact_growth_rate_mps_air_contact_stays_bit_identical`, all three `motion` states);
surface contacts with `motion is None` or `motion.state == "stopped"` get
`UNOBSERVED_MOTION_GROWTH_RATE_MPS`; `motion.state == "moving"` gets the class rate. The tunable is
declared via `tuning.real` with `lo=0.0, hi=1.0, status="judgement"`, and the rendered
`config/defaults.toml` entry (checked directly, not the source comment) carries the correct first
sentence, status, range, and source line — the generator's own first-sentence-only truncation did
not bite here. Both consumers (`Contact.record` and `attack_run._tier2_alignment`) call this one
function, confirmed by grep — the "one table" rule holds.

### Required Fixes

- **Finding 5 (dispatch point 2 — control experiment): the restored closing-run scenario's "no
  fold" result is not evidence that Stage 8 fixes the E5 fold, because the scenario does not fold
  even with Stage 8's fix reverted.** Patched `contact_growth_rate_mps` locally (not committed) to
  return `plausible_speed_mps(profile.op_class)` unconditionally for every contact — the exact
  pre-Stage-8 behaviour — and re-ran `test_two_groups_one_bearing_stay_two_contacts`: it still
  passes, with the identical contact-count trace `implementation.md`'s own Measurement section
  records (`CONTACT_1` founds at t=85, `CONTACT_2` founds at t=135, count never drops). Instrumented
  further to find why: `CONTACT_1`'s `last_observable_sim` stops advancing at t=105 and does not
  resume until `CONTACT_2` founds at t=135 — a **30 s** masked gap, not the geometry's forward-mask
  "closest approach ~508 m, inside 743 m" claim alone. The plan's own Stage 8 worked-numbers section
  computed that closing the ~500 m covariance gap by growth alone needs `growth_rate_mps *
  elapsed_s ≈ 340 m`, which at the **pre-Stage-8** rate (8 m/s, confirmed as `OP_GROUPSOMETHING`'s
  resolved default — `_DEFAULT_PLAUSIBLE_SPEED_MPS`) needs **≈42 s** unseen. The scenario's actual
  masked gap is 30 s — short of that threshold even under the old, uncapped growth rate. So this
  scenario was never going to fold, with or without Stage 8: it does not exercise the mechanism
  Stage 8 changed, and "No fold, so Finding 1 is resolved" (`implementation.md`'s own conclusion) is
  not supported by this run. This reopens the prior review's Finding 1 in substance even though its
  particular form (fully-stationary redesign) is gone — **the E5 closing-run case still has no
  genuine empirical verification against the real pipeline**, for a different reason than before
  (insufficient mask duration rather than no motion at all).
  - This is not a reason to distrust Stage 8's mechanism itself — the function-level unit tests
    (`test_contact_growth_rate_mps_*`) correctly verify the gate in isolation, and the arithmetic in
    the plan's own worked-numbers section is sound as an order-of-magnitude argument. What is
    missing is a scenario (or a more direct test) that actually brackets the ~42 s threshold: one
    where the masked gap is long enough that the **old** rate would fold and the **new** rate does
    not, run both ways and shown to differ.
  - **Required**: either (a) widen scenario 3's masked window past ~45-50 s (slower closing speed
    on the final leg, or a longer stand-off before the turn, re-derived by the same throwaway-script
    integration practice already used for this scenario's geometry) and re-run the same before/after
    control experiment done here to confirm it actually discriminates, or (b) add a narrower,
    cheaper differential test directly against `Contact.record`/`fold_position`/
    `clamp_to_detection_envelope` with a contrived elapsed time that straddles the ~42 s threshold
    for a surface contact (this also closes Finding 6 below). Either way, the claim "Stage 8 fixes
    the fold" needs a test that is shown, by the same kind of control experiment used here, to fail
    without Stage 8 and pass with it.

- **Finding 6 (dispatch point 3): no test exercises the fold-displacement bound path
  (`Contact.record` → `fold_position`/`clamp_to_detection_envelope`) for a surface contact under
  Stage 8's new rule.** Confirmed the Implementer's own Discovery 1 is correct — `test_contacts.py`'s
  `_observation` helper defaults `surface_alt_m=None`, never overridden by either fold-displacement
  test, so `contact_d`/the class-swapped copy are `on_surface=False` throughout and correctly
  untouched by this stage. But that leaves the actual integration path — a surface contact,
  `motion=None`/`"stopped"`, folding after a long gap, with the tiny rate feeding the displacement
  clamp exactly as `Contact.record` line 647 calls it — tested nowhere. The four new
  `test_association_over_time.py` tests all call `contact_growth_rate_mps` directly on a constructed
  `Contact`, never through `Contact.record`; `test_bl_b104_association_scenarios.py`'s surface-domain
  scenarios never leave a contact unseen (every poll re-observes, 2 s cadence) so elapsed-time growth
  is never exercised there either. **Required**: add a `test_contacts.py` case with a surface
  contact (`surface_alt_m` set), a motion state of `None` or `"stopped"`, and a controlled elapsed
  gap, asserting the fold-displacement bound uses `UNOBSERVED_MOTION_GROWTH_RATE_MPS` (not the class
  rate) through the real `Contact.record` call — the same shape as the existing
  `test_fold_displacement_m_is_bounded_by_the_contacts_own_plausible_speed` test but with
  `on_surface=True` and no `motion` override. This single test can also serve as Finding 5's
  narrower differential test (recommendation (b) above) if given an elapsed time that straddles the
  ~42 s threshold.

### Dispatch points checked, no fix needed

- **Point 4 (sight-tracking assertion).** Confirmed by re-reading `sight_head.advance_sight_head`:
  `mode` only leaves `"off"` once `observ_observed` is true, which in production is driven by the
  898/886 lamp readback through the effector-engine wiring this scenario harness deliberately does
  not build (same gating the implementer already found for `weapon="missiles"`). There is no cheap
  alternative assertion available in this harness that would not be tautological (`aim_source`
  cannot be anything but `"belief"` while `mode` is permanently `"off"`) — forcing `observ_observed`
  directly would mean calling `advance_sight_head` out-of-band from the scenario's own pipeline,
  which duplicates `test_sight_head.py`/`test_optic_policy.py`'s existing unit coverage rather than
  adding anything from this scenario's own belief data. Documenting this in the test's docstring
  rather than asserting it, as done, is the right call — accepted as-is, matching the original
  review's framing of this as an Optional Refinement, not a blocker.
- **Point 5 (non-Level leg per scenario).** All five scenario tests now contain at least one
  non-Level leg: `test_run1_overflight_...` (Turn + Descend), `test_run2_shallow_approach_...`
  (Turn), `test_two_groups_one_bearing_stay_two_contacts` (Turn), `test_cockpit_mask_forward_
  boundary_...` (Turn), and `test_cockpit_mask_pitch_down_recovers_masked_forward_target` (Descend,
  pre-existing, not touched by this amendment — its own pitch-down leg already satisfied "some
  aircraft manoeuvre" before Stage 7 amendment was needed). The `Turn` dataclass itself is sound:
  heading is interpolated per step (`fraction = step / n_steps`, reaching `end_heading_deg` exactly
  at the last step), `dx`/`dz` are recomputed from the per-step heading (unlike `Level`/`Descend`,
  which compute once per leg, correctly since their heading is constant), `bank_deg` is held for the
  leg's duration and reset to `0.0` immediately after, and the exit heading carries forward correctly
  as the entry heading for whatever leg follows.

### Optional Refinements (carried over / new)

- The plan's own "worth a small backlog item" note (widening `belief.groups.group_matches`'s
  displacement bound to both sides, now unblocked by `Group.movement_state`) was not minted —
  `.claude/scripts/mint-id.sh BL-B` was not run and no `BL-B*.md` file for it exists. Low severity
  (explicitly "worth," not "required," in the plan itself) but worth doing before this is forgotten
  a second time, per the plan's own framing.
- Everything from the first review round's Optional Refinements (comment accuracy, the
  cross-thread `CrewConsole` footgun, the `DEPRESSION_SIGMA_DEG`/`_SIGHT_*_SCALE` coupling) stands
  unchanged and is not re-verified in this round beyond what Stage 8/7-amendment touched.

### Verdict

NEEDS REVISION

Stages 1-5 and the mechanism half of Stage 8 (the gate logic itself, the tunable, the bit-identical
air-contact guarantee, the "one table" consumer check) are sound and APPROVED as implemented. The
two Required Fixes above are both about **verification, not mechanism**: Finding 5 shows the
scenario built to empirically confirm the E5 fix does not actually discriminate between "fixed" and
"not fixed," and Finding 6 shows the fold-displacement bound's own integration path for a surface
contact has no test at all. Recommend resolving both together via a single new `test_contacts.py`
case that directly exercises `Contact.record`'s fold-displacement bound for a surface,
unobserved-motion contact across an elapsed gap straddling the ~42 s threshold the plan's own
arithmetic names, run once with the real code (expect no fold / bounded displacement) and once with
Stage 8's gate reverted locally (expect the old, wider bound) — the same before/after check performed
in this review, made a permanent, committed test rather than a one-off reviewer probe. Widening
scenario 3's masked window is a reasonable alternative or complement, but the direct test is cheaper
and does not depend on getting integration-harness timing exactly right.

### Review Confidence (this round)

Full read of the new Stage 8 code (`association_over_time.py`), its four new tests, the Stage 7
amendment's `Turn` dataclass and `build_scenario_frames` changes, and all five scenario tests' legs
and docstrings. The control experiment (Finding 5) was run directly against the real pipeline, not
inferred from the plan's arithmetic — both with the shipped code and with a local, uncommitted
revert of Stage 8's gate, restored and confirmed clean (`git status --porcelain` empty,
`git diff src/belief/association_over_time.py` empty) before the final test run. Not independently
re-verified this round: Stages 1-5's own mechanism (unchanged since the prior full read), the
Lua wiring (unchanged), and the Optional Refinements carried over from the first review round.
