### Definition of Done: precise-position-belief

Scope: `311d3d3` (Stages 1-2) through `a9f76c9` (review-fix merge) on `feature/binocular-optic`.
The binocular-optic and voice-command-completeness milestones on the same branch already passed
DoD (`plans/binocular-optic/dod-check.md`) and are not re-gated here.

#### Code Quality

Touched subproject: `body-layer/` only (confirmed by diff — `git diff --name-only 311d3d3~1 a9f76c9`
touches only `body-layer/`, `plans/precise-position-belief/`, `docs/`, `.claude/agent-memory/`).
`audio-adapter/` and `aircraft-layer/` show zero diff for this milestone's commit range
(`git diff --stat 311d3d3~1 a9f76c9 -- audio-adapter aircraft-layer` is empty) — confirmed
untouched, not re-run.

Ran from a fresh venv built in this worktree (`cd body-layer && python3 -m venv .venv`, matched
tool versions to the main checkout's venv: ruff 0.16.6, mypy 2.3.1, pytest 9.1.1):

- `ruff format --check src tests` — **101 files already formatted**
- `ruff check src tests` — **All checks passed**
- `PYTHONPATH=src:../world-model/src mypy src` — **Success: no issues found in 47 source files**
- `PYTHONPATH=src:../world-model/src python -m pytest tests -q` — **1104 passed, 4 xfailed** (matches
  the expected number given; the 4 xfails are pre-existing `detection-cones-slice2` calibration
  regressions, unrelated to this milestone)

No `print(`/`pdb`/debug output or bare `except:` introduced by this milestone (checked the diff
range directly). No new TODO comments in the diff.

#### The one thing that got disproportionate attention: is there a third omniscience path?

The review found `perception/hybrid_source.py` handed belief truth-exact `bearing_deg`/`range_m`
from `association.associate()`'s ground-truth geometry, behind a cosmetic `PositionUncertainty(300,
300)` — Stage 1's declaration had landed, Stage 2's actual perturbation never had. Verified the fix
directly, and checked for a third path with the same shape:

1. **Read `hybrid_source.py`'s observation-construction site** (lines ~190-270). Confirmed
   `perturbed_bearing_range` is now called with `true_bearing_deg=result.bearing_deg,
   true_range_m=result.range_m` (the ground-truth geometry `associate()` computed) and its output
   (`estimated_bearing_deg`, `estimated_range_m`) is what's written onto `Observation.bearing_deg`/
   `range_m`. `derived_world_position` still carries `result.candidate.x/z` unperturbed — by design,
   per its own docstring, trace/debug only.

2. **Reproduced the regression the fix closes.** Extracted the pre-fix `hybrid_source.py` from
   `b248c5e~1`, swapped it in, and ran the new regression test
   (`test_repeated_scope_observations_of_a_stationary_object_do_not_converge_on_truth`) plus the two
   updated ones. All three fail against pre-fix code — the key assertion:
   `assert abs(mean_range_m - true_range_m) > 20.0` fails with `0.0 > 20.0` (converges on *exact*
   ground truth over 60 looks). Restored the fixed file; all 19 tests in `test_hybrid_source.py`
   pass again; `git status --porcelain` on the file came back clean before and after.

3. **Checked `belief/percept.py`'s boundary structurally, not just by inspection of one call site.**
   `Percept` (the only type `belief/contacts.py` and `belief/association_over_time.py` ever see) has
   no field that can carry a ground-truth position or DCS object id — `derived_world_position` and
   `Observation.id`-as-truth-key are structurally absent from the dataclass, not merely unused.
   `Percept(...)` is constructed in exactly one production location (`percept.py`'s own
   `percept_of`); the only other constructions are in `test_association_over_time.py`. Every
   `Observation` entering `ContactStore.ingest` passes through `percept_of` before touching fusion
   logic (`contacts.py:681`, `:692`) — `self._observations` (the raw `Observation` log) is kept only
   for provenance/history, and every read of it (`_recent_percepts` in `enrichment.py`) re-converts
   through `percept_of` before use.

4. **Checked `enrichment.py::_terrain_aware_world_position`, the other place a "world position" gets
   computed downstream of belief.** It reprojects `contact.last_position` — the fused *believed*
   mean — not `derived_world_position` or any raw candidate coordinate. The observer for the
   fixed-point terrain solve comes from the most recent `Percept.ownship_at_observation` (perceived
   bookkeeping, not truth); the *target* fed in is always `contact.last_position`.

5. **Traced `Contact.record`/`Contact.from_percept`** (`belief/contacts.py`): both call
   `implied_position(percept)` and `fold_position(...)`, whose only inputs are
   `percept.bearing_deg`/`range_m` (the perturbed, perceived numbers — `Percept` has no other
   position-shaped field) and `percept.ownship_at_observation`. There is no code path from a
   `Contact`'s fused position back to any ground-truth field.

**Conclusion: no third path found.** The only place ground truth (`derived_world_position`,
`WorldObjectCandidate` coordinates) exists in this codebase is inside `perception/`, and the
`Percept` boundary in `belief/percept.py` is a structural cut, not a convention — a future belief
function cannot reach a truth field by accident, only by bypassing `percept_of` entirely and
importing `perception.source.Observation` directly into `belief/`, which no current code does.

#### A genuine, pre-existing gap confirmed, not fixed

A prior agent flagged that `test_naked_eye_source.py` has a comment (lines ~833-839) naming two
tests — `test_emitted_bearing_range_are_perturbed_not_quantised` and
`test_position_uncertainty_is_declared_on_every_observation` — that might not exist. Confirmed:
**neither test exists under those names anywhere in the suite** (`grep -rn "def test_.*perturb\|def
test_.*uncertaint"` across all test files), and no test in `test_naked_eye_source.py` directly
asserts that an emitted `Observation` from `_build_observation` has perturbed bearing/range or a
declared `position_uncertainty` — that behaviour is covered only *indirectly*, via
`test_estimation.py`'s direct unit coverage of `perturbed_bearing_range` itself (which
`naked_eye_source.py`'s `_build_observation` is confirmed, by reading the source, to call
correctly). This is a real, pre-existing documentation/coverage gap — not a regression, not this
milestone's introduction, and the mechanism itself is verified correct by source reading + the
hybrid-channel regression test above (which does directly assert perturbation for that channel).
Not blocking; noted as the same class of gap the Reviewer's Optional Refinements already flagged
for `Covariance2D.inverse()`.

#### Scope & Correctness

- Implementation matches `plans/precise-position-belief/plan.md`'s five stages plus the required
  review fix (`implementation.md`'s "Review fix — Decision 2 answered" section, `b248c5e`).
  Decision 2 ("does the scope/hybrid channel get Stage 2's treatment?") is now recorded answered
  "yes" in `implementation.md`, and confirmed in code per the verification above.
- No unplanned scope added beyond the review-required fix and its roadmap entry.
- `git status --porcelain` clean after merge (checked below).
- Invariants: `Percept`'s structural exclusion of DCS-truth fields, `derived_world_position` staying
  trace-only, and DCS-authoritative geometry all hold — verified directly above, not assumed from
  the review's own verdict.

#### Testing

- Core logic (covariance fusion, the 2D gate, perturbation, terrain-aware reprojection) covered by
  `test_position_belief.py`, `test_estimation.py`, `test_association_over_time.py`'s directional
  gate test, `test_contacts.py`'s re-derived fixture, `test_enrichment.py`'s terrain-aware
  regression test, and `test_hybrid_source.py`'s new regression test — all hand-verified not merely
  present (see above).
- Tests are meaningful: the hybrid-channel regression test was proven to fail against the actual
  pre-fix code, not just asserted to exist.
- No existing tests broken: full suite at 1104 passed / 4 xfailed matches the pre-merge expectation
  exactly.

#### Documentation

- Reviewer's two required fixes (hybrid-channel perturbation, missing ROADMAP entry) both addressed
  and verified directly, not taken on the commit message's word.
- `body-layer/ROADMAP.md` gained an accurate, detailed entry (`grep -n "Precise position belief"`)
  covering the model, the fusion change, the review fix, and outstanding calibration/live-sortie
  debt. Checked against the actual commits and code rather than trusted as merely present.
- Root `ROADMAP.md`'s Body Layer status row and `audio-adapter/ROADMAP.md` — **still stale**,
  already flagged by the prior binocular-optic DoD pass and not caused by this milestone (this
  milestone touches only `body-layer/`, confirmed above). The staleness here is paragraph-class, not
  one-line-class (the Body Layer row is one long running paragraph that would need a real rewrite to
  cover binocular-optic/precise-position-belief/voice-command-completeness), so left flagged rather
  than half-fixed. Re-flagging rather than re-fixing, per the prior DoD's own finding.

#### Security

Per `CLAUDE.md` "Agents": security plan review and deep analysis are currently exempted project-wide
(offline single-user local pipeline, no hot path, no untrusted-input surface) and were not invoked
for this milestone, consistent with every other milestone on this branch.

#### Milestone-completion question (CLAUDE.md "Milestone Completion")

**Does this milestone's completion change what the next milestone should be, or invalidate an
assumption downstream milestones rely on? Yes — `plans/watch-reporting/plan.md` needs a second
look before it is implemented, not before it is read.**

That plan's Decision 5 (the kilometre-crossing trigger) computes
`current_km = floor(range_m(ownship_position, contact.last_position) / 1000)` and fires
`CONTACT_RANGE_CROSSED` on any change, gated only on staleness (`certainty_of(...) in ("observed",
"tracked")`). It was designed against the *old* believed position: quantised reporting buckets that
only changed when a contact's true range crossed a whole reporting-bucket boundary — infrequent,
one-directional, effectively noise-free jumps. `Contact.last_position` is now a continuously-updated
2x2-covariance fused mean that moves on every fold, including per-look noise (`perturbed_bearing_
range`'s per-observation draw) on top of the never-redrawn systematic bias. Two concrete risks this
plan's Decision 5 does not currently account for:

- **Boundary jitter.** A contact sitting near a whole-kilometre line can now have its fused position
  cross back and forth over that line from look-to-look noise alone, especially early in a contact's
  life when the covariance (and therefore the per-look update magnitude) is still wide — firing
  `CONTACT_RANGE_CROSSED` repeatedly for a contact that, in truth, never moved. The staleness gate
  in Decision 5 does not address this; it guards against *reporting on a contact you haven't looked
  at recently*, not against *a fresh look nudging the estimate across a line by noise*.
- **`line_of_sight_clear`, called per watched threat per poll** (plan section on cost), takes
  `contact.last_position` as an input to a ridge-based visibility test. The same per-look jitter
  could flip a borderline geometry's visibility verdict poll-to-poll near a terrain edge, in a way
  the old quantised position (stable between bucket boundaries) would not have.

This is not a defect in precise-position-belief — the milestone did exactly what it set out to do
(replace a biased quantisation with a real error model) — but `watch-reporting`'s plan reasoned
about the position source that predates this milestone, and neither risk above is mentioned in its
Decision 5 or its cost section. Recommend the Architect revisit Decision 5 before `watch-reporting`
implementation starts: likely fix is a small hysteresis band or a minimum-dwell debounce on the
kilometre-crossing trigger (the same shape of fix already applied elsewhere on this branch for
repetitive-report aggregation), not a redesign.

#### Acceptance testing — deferred, recorded as debt, not blocking

Per this task's explicit instruction: **this milestone's acceptance is deferred.** The user flies
`docs/acceptance/2026-09-23-eyes-and-voice-sortie.md` next, covering the already-accepted
binocular-optic and voice-command-completeness milestones. precise-position-belief has not had its
own live acceptance and needs one — Stage 3's 2D association gate carries real regression risk the
plan's own text says needs a live sortie before trust, and `BEARING_SIGMA_DEG`/`RANGE_FRACTIONAL_
SIGMA`/`SYSTEMATIC_BIAS_FRACTION`/`SCOPE_UNCERTAINTY_M` are all uncalibrated judgement constants
pending flight. This is recorded as **debt**, not waived — `body-layer/ROADMAP.md`'s entry already
states "Unflown as of this entry" for Stage 3. No acceptance card is published here; the user is not
asked to run anything from this DoD pass. The next sortie that can clear it should be batched with
whatever else is outstanding at that time (per the "batch what a single flight can clear"
convention).

#### Verdict: PASS

Nothing here blocks a merge to `main`. Outstanding, and already tracked as live-acceptance debt
rather than a blocker:

- Stage 3's association gate — needs a live sortie (plan's own instruction).
- `BEARING_SIGMA_DEG`, `RANGE_FRACTIONAL_SIGMA`, `SYSTEMATIC_BIAS_FRACTION`, `SCOPE_UNCERTAINTY_M` —
  uncalibrated, pending flight.
- Two commits on this branch that belong on `main` (already noted by the task brief, pre-existing,
  not this milestone's to fix).
- The `test_naked_eye_source.py` stale-comment coverage gap above — worth a follow-up test, not a
  blocker.
- `watch-reporting`'s Decision 5 needs revisiting before that plan is implemented (see above) — a
  planning-stage note, not a code defect in this milestone.
- Root `ROADMAP.md` / `audio-adapter/ROADMAP.md` staleness — pre-existing, not this milestone's
  cause, re-flagged rather than fixed (paragraph-class, not one-line-class).

#### Recurring-fix pattern check (against `.claude/agent-memory/dod/MEMORY.md`)

This is the first DoD pass to check ROADMAP-prose-claims against the actual grep/commit for this
specific project phase's memory ("Verify ROADMAP prose claims") — applied above (Decision 2's
"recorded answered" claim, and the ROADMAP entry's accuracy, were both grep/source-verified rather
than trusted). No new recurring-category pattern to add: this milestone's required fixes (an
incomplete channel rollout, a missing roadmap entry) don't yet match any prior category 2+ times in
this project's history at the granularity worth a new memory entry.
