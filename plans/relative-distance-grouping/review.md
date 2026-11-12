### Review Summary

Reviewed `feature/relative-distance-grouping` (BL-B108) at merged tip `49107102` (fast-forwarded
from `a03b8f54`, origin/main ancestor, clean tree). Full read of `plan.md`, `explore-notes.md`,
`alignment.md`, `implementation.md`, `BL-B108.md`/`BL-B109.md`, and the diff vs merge-base
`4c50996e` across `estimation.py`, `position_belief.py`, `association_over_time.py`,
`group_salience.py`, `admission.py`, `contacts.py`, `source.py`, `naked_eye_source.py`,
`hybrid_source.py`, `defaults.toml`, and the test files.

The mechanism is careful, well-documented, and traces cleanly to the plan and the user's own
words: the three-part correlated down-range model, the shared `correlated_innovation` helper
used identically by gate and fold, the `LookAnchor`/co-moving-fields discipline (all 9
`PositionEstimate(` construction sites checked individually against the plan's own table — all
correct, including the two `clamp_fold_displacement` returns and the floor), the
`group_salience` along-line check (no new tunable, correctly derived from
`RANGE_RELATIVE_SHARE`), and the mission-memory admission change (drops only `nameable`, keeps
`GROUP_ENTRY_CONFIDENCE_FLOOR`, with the three tests the dispatch asked for). The renumber
BL-B106/107 → BL-B108/109 is complete; no stale reference to this feature under the old numbers
remains (the `BL-B106` hits that remain are the *other*, unrelated async-speech item on `main`).
The 2.0-vs-2.5-km case is never hard-coded; E6 is tested as a flip, not a verdict.

All checks pass: `ruff format --check`, `ruff check`, `mypy --strict` (79 files), and the full
suite — 2882 passed / 4 xfailed (fast suite, 39s) plus 4 passed / 1 xfailed in
`test_bl_b104_scenario_mock_flights.py` (117s) — reproduced independently, matching
`implementation.md`'s own numbers exactly.

One required fix (the `xfail`) and one required fix (a rendered-config truncation), both below.

### Required Fixes

- **The cross-optic `xfail` reopens E1 under Petrovich's own default behaviour, not an edge
  case — the correlation model needs a real fix, or the user needs to accept this gap explicitly
  before merge.**

  `stable_range_correlation` returns `(0.0, 0.0)` whenever the anchor's optic and the new look's
  optic differ (`estimation.py`'s `_field_value`: `optic_class` is folded into the field seed, by
  design, "so belief cannot infer the field's value exactly from two fully-correlated optics").
  When `correlated_innovation`'s `ρ_view = 0`, `S` collapses to the plain independent sum — the
  exact pre-`BL-B108` gate width this whole plan exists to narrow. `test_two_groups_one_bearing_
  stay_two_contacts` demonstrates the consequence directly: the near contact's anchor is
  `unaided`, the far group's reacquisition look is `binocular`, and the two groups fold.

  This is not reached only through a contrived scenario. `belief/optic_policy.py`'s own module
  docstring describes the mechanism as Petrovich's **ordinary, autonomous cycle**: "First
  complete the current sector naked eye scan... then raise binoculars to take a closer look" —
  entered automatically "only at a phase boundary, and only when there is something worth looking
  at." Raising binoculars on something he is watching is not a rare player action; it is what he
  does by default once a scan finds a target. Any two groups on one bearing, one of which gets
  glassed between the near and far group's own first looks, hits exactly this path.

  Weighed against the user's own words: *"an observer can fairly easily tell relative distance"*
  and, on optics specifically, *"With binoculars you see better and so can judge unit apparent
  size better. That'd give a better range estimate... though not exact."* The user is describing
  **partial** correlation improving with a better optic, not independence. The plan's own
  argument for zero cross-optic correlation ("fusing two fully correlated estimates of unequal σ
  extrapolates past both, which is omniscience by arithmetic") is an argument against `ρ = 1`,
  not against any `ρ > 0` — the two are conflated in the shipped model. A real observer glassing
  the same scene seconds later is still looking at the same terrain, same depression cue, same
  general picture; only the measurement's own precision changed, not the whole basis for the
  estimate.

  This is a model decision (which field/seed structure a "different optic, same moment" look
  should correlate through), not a one-line implementer patch, so I am not prescribing the fix —
  candidates worth weighing: a partial cross-optic ρ (bounded well short of 1, so no arithmetic
  omniscience), or deriving the cross-optic correlation from the *tighter* optic's own σ_down
  rather than zeroing it outright, or a `Z_near`-only (not `Z_view`) cross-optic share, since
  `Z_near` is the "same place, same moment" shared cue and `Z_view` is the one the plan already
  treats as the optic-specific "new information" term. Whichever direction, it needs the same
  gate/fold symmetry the rest of Stage 2 already has.

  Given this reopens the plan's own headline goal (E1) through routine behaviour rather than
  through the already-accepted "large old absolute error... after a big geometry change" risk in
  the plan's "Risks & Unknowns" (which is about ownship having closed far enough that `ρ ≈ 0` from
  genuine decorrelation, not an optic switch at unchanged geometry), I am marking this required
  rather than recommended. If the user decides the scope and cost of a correct fix outweighs
  shipping with this known gap now (`xfail(strict=False)` already means it will not block CI
  either way), that is a legitimate call — but it should be made knowingly, not merged past
  silently. Flag it to the user before merge; if they accept the gap as-is, downgrade this to
  optional and record that decision in `BL-B108.md`'s own entry (which currently reads as if E1
  is unconditionally delivered).

- **The rendered `defaults.toml` comment for `RANGE_DECORRELATION_BEARING_DEG` is truncated
  mid-sentence by a generator abbreviation bug, and reads as broken prose to anyone who opens the
  file.** The source comment (`estimation.py`, lines 294–302) reads "...a larger value means the
  estimate stays "the same look" longer, e.g. through a shallow orbit. Judgement default..." —
  but `tools/generate_defaults.py`'s `_SENTENCE_SPLIT` regex treats the period in "e.g." as a
  sentence end (it only special-cases decimal digits and quoted spans, not abbreviations), so the
  rendered file stops at:

  > `...a larger value means the estimate stays "the same look" longer, e.g.`

  dangling with no following clause. This is a pre-existing generator limitation (not introduced
  by this plan), but it is exactly the class of defect the project has now shipped three times
  before by reading the diff instead of the rendered file (root `CLAUDE.md`'s "Behaviour-affecting
  constants are tunable") — and it is this comment's own wording, written in this plan, that
  triggers it. Fix by rewording the comment to avoid "e.g." (the simplest fix — "for example" or
  restructuring the clause works fine, and nothing else here needs the generator itself touched),
  then regenerate `defaults.toml` and confirm the sentence reads whole.

### Optional Refinements

- **Deviation 2 (scenario suite built on direct `Observation`/`ContactStore` construction, not
  the threaded `mock_flight_scenario` pipeline) is honest for the mechanism it covers, but leaves
  the cross-optic interaction — which is exactly where the one real remaining bug lives —
  structurally untested by the new suite.** `test_relative_distance_scenarios.py`'s `_observation`
  helper is hard-wired to `UNAIDED_OPTIC` throughout; E1a/E1b never see an optic switch. This is
  not a defect in what was built (the direct-construction suite does exercise the real
  perception/belief math for the correlated-noise mechanism, which is the right call given the
  measured ~150ms/poll cost), but it means "E1 is proven" should be read as "E1 is proven for the
  single-optic case" until the required fix above is resolved — worth noting explicitly in
  `BL-B108.md` alongside the xfail, not just in `implementation.md`'s discoveries.
- **`_FIELD_FOURIER_K = 256`** is justified with a measured empirical finding (16–32 left
  realised variance 0.5×–1.5× of target; 256 holds every optic class within ±10%) and cached via
  `functools.cache` keyed on `(field_name, optic_class, length_scales)`, so the per-poll cost is
  bounded and amortised across calls at the same geometry inputs — nothing obviously expensive for
  the Performance Reviewer to chase, but worth that role's own look at cache-key cardinality over
  a long sortie (optic class changes are few, but `length_scales` as a tuple key means any caller
  passing slightly different float tuples would miss the cache; confirmed by reading the call
  sites that this does not currently happen, but it is an implicit invariant on every future
  caller of `_field_value`).

### Verdict

CHANGES REQUIRED

### Review Confidence

Full read. Every stage's diff was read against the plan and `implementation.md`'s own claims;
the fusion/gate/anchor math was traced by hand against the co-moving-fields table (all 9 call
sites); all four check commands were run and reproduced the implementer's reported numbers
independently (not re-trusted from the log); the rendered `defaults.toml` was read directly, not
inferred from the source comments, per this role's own standing instruction.

## Review round 2 (fix round, tip `161448d5`)

Verified the fast-forward first: `HEAD` (`a03b8f54`, `origin/main`) was a strict ancestor of the
named tip with a clean tree, so `git merge --ff-only 161448d5` was done as instructed rather than
re-reviewing from a cherry-pick. Read `implementation.md`'s "Review follow-up, 2026-10-31" section,
`explore-notes.md`'s Q3 and the plan-escalation answers, the full diff of `estimation.py`/
`position_belief.py` vs round 1's tip, `test_relative_distance_scenarios.py`'s new tests, and the
rendered `defaults.toml`.

**Fix 2 (the truncated comment) is correctly closed.** `RANGE_DECORRELATION_BEARING_DEG`'s
rendered comment now reads a complete sentence ("...longer, through a shallow orbit for
instance.") with no dangling `e.g.`, and `CROSS_OPTIC_RANGE_SHARE`'s own new comment renders as
one complete sentence with no bare `RANGE_RELATIVE_SHARE` identifier in it (reworded to "the
relative-share weight's own square..." prose, as `implementation.md` describes) — confirmed by
reading `config/defaults.toml` directly, not the source. The blank-`#:`-line paragraph-break
gotcha the implementer found and fixed is a real, separate defect from the `e.g.` one and is
recorded correctly in their own memory file.

**Fix 1 is not closed. The cross-optic correlation fix does not generalize past the one shipped
regression scenario, and fails the plan's own declared "clear case" guarantee — required fix,
not an acceptable-margin judgement call.**

I ran the real code (not inspection) against geometries beyond the single shipped test
(`test_two_groups_one_bearing_stay_two_contacts`, far 4.6 km / near 2.4 km, ~2.2 km separation),
using `test_relative_distance_scenarios.py`'s own `_observation`/`_ownship` helpers directly
against `ContactStore`:

- **The shipped geometry is robust**: 20 different bias-object-id draws at far=4.6 km/near=2.4 km,
  cross-optic (unaided founding look, binocular reacquisition), all stay two contacts. This part
  of the implementer's claim holds.
- **The plan's own declared "clear case" does not survive a cross-optic look.** `plan.md` line 66
  states, in its own worked-numbers table: *"clear case, 1.5 km apart at ~3 km ... always two
  (E1)"* — and the same-optic baseline (both looks unaided) confirms this: 10/10 bias draws at
  far=3.75 km/near=2.25 km (1.5 km apart, centred ~3 km) stay two contacts. **The identical
  geometry, with the near look through binoculars instead of unaided, folds to one contact in
  10/10 bias draws** at the shipped default (`CROSS_OPTIC_RANGE_SHARE = 0.6`), and **still folds
  in 5/5 bias draws at the tunable's own declared `hi = 0.75` bound** — there is no value within
  the declared range that preserves this case. (`effective_down_correlation` at this geometry: same
  optic ≈ 0.196, cross optic at the shipped default ≈ 0.118, at `hi` ≈ 0.147 — none close enough to
  the same-optic value to keep the gate narrow enough.)
- **A geometry sweep around the shipped point shows the boundary is close by, not a comfortable
  margin.** far=4.3 km/near=2.1-2.25 km (separation ≈ 2.05-2.2 km) still passes; far=4.3 km/
  near=2.4-2.7 km (separation ≈ 1.6-1.9 km) folds; far=4.5 km/near=2.7 km (separation 1.8 km) folds
  for some bias draws and not others. The shipped scenario's own ~2.2 km separation is close to
  where this starts failing, not comfortably inside a safe region — this is the "fitted to the one
  scenario" risk the dispatch named, confirmed by running the model rather than reading the
  comment.

**Why this is required rather than an accepted-risk note**: this is exactly round 1's finding
recurring at a different geometry. Round 1 flagged that the cross-optic `xfail` reopened E1 under
Petrovich's own ordinary autonomous behaviour (the scan-then-glass cycle), not a contrived case.
The fix closes that specific geometry but reopens the *same* failure mode — the plan's own
baseline same-optic separation guarantee collapsing the moment one look is cross-optic — at a
separation (1.5-1.9 km at ~3 km) that is, if anything, more representative of ordinary tactical
spacing than the shipped 2.2 km case. Scaling `Z_view`'s kernel by a flat fraction narrows the
fold window but does not close it, and the tunable's own declared ceiling cannot close it either,
so this is not something the user can dial around after merge.

**This is a model decision, same as round 1's finding, not a one-line patch** — I am not
prescribing the fix. Worth the user's explicit decision before merge: accept a documented, narrower
guarantee (e.g. "cross-optic separation reliably stays two only above ~2.2 km at this range band";
if so, `BL-B108.md`'s entry needs to say so, not read as the plan's original claim delivered
unconditionally), revisit the correlation model itself (the `Z_view`-only flat-share approach may
be structurally insufficient, same shape of problem Fix 1's own "tried and rejected" `Z_near`
analysis already demonstrated for a different slot), or decide the shipped scenario's coverage is
enough for now and carry the gap as a tracked, named risk rather than an implicit one.

**No-omniscience check: direction and bound confirmed, implementer's quoted figure is slightly
off but inside the test's own tolerance, not a defect.** Re-ran
`test_cross_optic_fuse_along_sigma_never_beats_the_tighter_optics_own_sigma`'s own scenario
directly: fused along-sigma comes out **2.1% below** the binocular-alone sigma for
unaided→binocular, and **2.5% below** for binocular→unaided — both within the test's declared 5%
tolerance band, both the same direction `implementation.md` describes (a small, bounded tightening
from genuine partial-correlation information gain, not an explosion toward zero), just measured
here at roughly 2-2.5% rather than the "~1.5%" quoted. Not required to fix — the test's tolerance
already covers the real value and the direction/boundedness claim holds — but worth a one-line
correction in `implementation.md` if that figure is ever cited again.

**Gate/fold symmetry**: confirmed by reading `correlated_innovation` — both `passes_gate`/
`contacts_plausibly_same` and `fold_position` call the same function; `stable_range_correlation`'s
`same_optic` comparison and the bearing/range-ratio kernel are symmetric in the two sides by
construction, and the only difference between gate and fold is which bearing/range the caller
supplies (hypothesis vs. the look's own), exactly as the module docstring states. No asymmetry
found.

**E3 across optics** (`test_e3_group_seen_unaided_then_through_binoculars_stays_one_contact`):
confirmed correct and not fragile the way E1 is — a *higher* correlation only ever helps E3 (it
wants the fold), so this sibling case is not at risk from the same mechanism that breaks E1's
clear case.

**Checks re-run independently** (fresh `body-layer/.venv`-equivalent, imports confirmed to resolve
to this worktree's own `src`): `ruff format --check src tests` (191 files, clean), `ruff check src
tests` (clean), `mypy src` (79 files, clean), `pytest -q` excluding the slow module (2886 passed,
4 xfailed, matching `implementation.md`'s own numbers exactly), `test_bl_b104_scenario_mock_
flights.py` (5 passed, ~117s, confirming the former `xfail` is now a plain pass). **The flaky test**
(`test_mission_start_reset.py::test_check_for_new_mission_keeps_the_traceback_for_a_non_
connection_failure`) passes cleanly in isolation and the file is untouched by this plan's diff
(last touched by unrelated ATGM-run commits) — consistent with the implementer's "pre-existing
test-order flakiness" claim, not something this change introduced.

### Required Fixes (round 2)

- **`CROSS_OPTIC_RANGE_SHARE` does not deliver the plan's own declared same-optic "clear case"
  guarantee (1.5 km apart at ~3 km stays two, `plan.md` line 66) once a look is cross-optic, and no
  value within the tunable's declared `0.0-0.75` range closes the gap** — demonstrated by direct
  execution, not inspection (see above). This reopens round 1's finding (E1 defeated by Petrovich's
  own ordinary autonomous optic-switching) at a geometry more representative of ordinary spacing
  than the one scenario the fix was built and tested against. Needs the user's explicit decision
  before merge: accept a narrower, documented guarantee; revisit the correlation model; or scope
  this as a tracked, named gap rather than letting `BL-B108.md` read as E1 unconditionally
  delivered across optics.

### Optional Refinements (round 2)

- **`implementation.md`'s "~1.5%" no-omniscience figure measured independently at ~2.1-2.5%** —
  same direction, same order of magnitude, within the test's own 5% tolerance, not a defect worth
  blocking on, but worth a one-line correction if the figure is cited again.
- **The geometry sweep that found the fold boundary (far 4.3-5.0 km / near 2.0-2.8 km, 20+ bias
  draws) is not currently captured as a test.** If the user's decision above is "accept a narrower
  guarantee," a parametrized sweep test recording where the boundary actually sits would turn this
  from something only a reviewer's one-off probe currently shows into a regression fence against
  the boundary moving silently in a future change to `RANGE_DECORRELATION_RANGE_RATIO`/
  `CROSS_OPTIC_RANGE_SHARE`/the gate threshold.

### Verdict (round 2)

CHANGES REQUIRED

### Review Confidence (round 2)

Full read, plus direct execution of the real code against geometries beyond the plan's own
dispatch-named scenario (not inspection of the comment/docstring) for the central question (default
fittedness/robustness). Checks re-run independently and matched the implementer's reported numbers.

## Review round 3 (amendment, tip `8b045631`)

Verified the fast-forward first: `HEAD` (`d299dd52`, `origin/main` ancestor) was a strict ancestor
of the tip named at dispatch (`8b045631`, after the orchestrator corrected the expected tip mid-task
— `origin/main` had advanced with an unrelated aircraft-layer probe merge, so `feature/
relative-distance-grouping` merged `origin/main` in first; `d0960df9`, the amendment's real tip, is
that merge's first parent). Clean tree, `git merge --ff-only` done as instructed.

Read the amendment section of `plan.md` ("Amendment 2026-10-31: cross-optic error model"),
`explore-notes.md`'s "Cross-optic amendment decision" (user, verbatim "1"), `implementation.md`'s
"Amendment implementation" section, and the full diff of `estimation.py`/`position_belief.py`/
`association_over_time.py`/`naked_eye_source.py` plus both new/rewritten test files
(`test_relative_distance_sweep.py`, the `test_relative_distance_scenarios.py`/`test_estimation.py`/
`test_hybrid_source.py` rewrites) against the review-round-2 tip (`161448d5`).

**1. Noise/belief correlation agreement — verified empirically, not by reading.** Ran the real
`_tiered_field` realisations (400-realisation ensembles, salted via `_FIELD_REALISATION_SALT`)
against `optic_range_correlation`/`view_range_correlation`'s declared values for five pairs
(unaided/binocular same geometry, unaided/unaided and binocular/binocular at a 1.5 range ratio,
sight_narrow/unaided, scope/unaided). Realised ρ matched declared `k · κ` within sampling noise in
every case (e.g. unaided/binocular: realised +0.670 vs declared +0.700; scope/unaided: realised
−0.037 vs declared 0.000). No belief-side ρ exceeds what the noise realises — confirmed by
measurement, and also follows structurally from `optic_range_correlation` being the single function
both `_tiered_field` and `stable_range_correlation` read (same code, not merely the same claim).

**2. Implementer's four stated deviations — each checked, not taken on their word.**

- **(a) Stages A-C as one commit, including the calibration change.** Verified the implementer's
  own justification by reverting `RANGE_DECORRELATION_RANGE_RATIO` to the plan's original `1.5` in
  this worktree (mechanism/belief changes otherwise untouched) and running
  `test_e1a_far_group_first_then_near_group_stays_two_contacts`: it fails (the near contact's
  `CONTACT_DETECTED` would be merge-echo-suppressed) — confirming the mechanism genuinely cannot
  pass the plan's own E1a scenario without the calibration change, which is the stated reason for
  not splitting the commit. Reverted immediately after; worktree confirmed clean. This is a
  reasoned, verified departure from the `CLAUDE.md` "mechanism and calibration never share a
  commit" invariant, not an unexamined convenience — accept it, but note the invariant's purpose
  (attributable bisection) is still slightly weakened here; nothing about this diff makes that
  unattributable in practice since both changes are the *same* amendment and both are explained in
  one commit message.
- **(b) Same-optic sweep ceiling 10%, not the plan's own 3%.** Confirmed by reading
  `test_relative_distance_sweep.py`'s own comment and reasoning: 24 cells at a true ~1-2% rate with
  `n=100` each makes at least one cell exceed 3% by binomial sampling noise alone reasonably often
  (one run measured 6% on an otherwise-clean suite). 10% still catches an order-of-magnitude
  regression; this is a sound, disclosed tradeoff, not a weakened guarantee in practice — accept.
- **(c) E3 binocular-then-unaided fenced ≥90%, not 100%.** Independently re-measured at N=300 with
  fresh salts (not the shipped test's own): 98% fold rate, consistent with the implementer's claimed
  97-99% and comfortably inside the 90% floor. This is a real, explainable, measured property (a
  tighter-then-looser optic order occasionally sits just past the gate's 3σ edge), not a defect
  papered over by a loose fence — accept.
- **(d) `STRUCTURE.md` gaps (`association_over_time.py`, `group_salience.py`) pre-existing.**
  Confirmed by diffing `STRUCTURE.md` against the merge-base (`f95a5fa1`): neither file had a
  dedicated entry there either, before this amendment touched anything. `estimation.py`'s own new
  entry (claimed added) is present and not present at the merge-base. Accept as stated.

**3. Memory-only cross-optic fold rate — the user's approved "5-67%" materially understates the
shipped code's own honest limit, and this is worth surfacing even though nothing here is a merge
blocker.**

The user's decision (`explore-notes.md`, verbatim "1") was made against the figures in `plan.md`'s
"Decision Requiring User Input" section — architect-prototype numbers, "5-67% across the clear-case
grid." Running the actual shipped code's own `_e1_fold_rate` helper (independent salts, N=300 per
cell, all 6 geometry pairs × 2 cross-optic orderings × 2 temporal orders = 24 cells) measures
**0%-86.3%**, not 5-67%:

| far/near km | u_b far-first | u_b near-first | b_u far-first | b_u near-first |
|---|---|---|---|---|
| 3.0/1.5 | 20% | 8% | 4% | 0% |
| 3.75/2.25 | 49% | 23% | 28% | 2% |
| 4.5/3.0 | 64% | 41% | **72%** | 14% |
| 5.0/3.5 | 78% | 53% | **86%** | 26% |
| 4.0/2.0 | 27% | 8% | 2% | 0% |
| 4.6/2.4 | 26% | 9% | 4% | 0% |

(u_b = far group unaided, near group binocular; b_u = far group binocular, near group unaided.)

The worst cells (**4.5/3.0 and 5.0/3.5 km, far group founded through binoculars, near group then
seen unaided, far-first** — "b_u far-first") sit at 72% and 86%, not the plan's quoted maximum of
67%. This is not a reviewer artifact of a different probe: re-running with the shipped test file's
*own* `salt_prefix` convention at its own `N=60` reproduces the same figures (e.g. 66.67%/88.33% at
those two cells) — the fence table in `test_relative_distance_sweep.py` itself was built from, and
correctly covers, these higher numbers (ceilings 0.85/0.95 at those cells), so **the test suite is
honest about this** — but `plan.md`'s Decision section and `BL-B108.md`'s roadmap entry, which is
what the user's "1" was actually answering, still say "5-67%."

**Root of the gap, traced, not guessed:** the architect's own prototype table (`plan.md`, "Measured
on the prototype") shows the *opposite* ordering — "far unaided, near binocular" always higher than
"far binocular, near unaided" at every geometry (e.g. 62% vs 40% at 4.5/3.0). The shipped code
inverts this at the two largest/most-separated geometries. Traced via an instrumented
`correlated_innovation` call: `passes_gate`'s hypothesis-scaling (`BL-B108` amendment, "Belief
side") multiplies the *second-observed* look's own declared sigma by `hypothesis_range_m /
percept.range_m`. When the second-observed look is already the *looser* optic (unaided) and that
ratio is `>1` (far-first order, hypothesis range is the larger, earlier-founded far range), an
already-loose sigma is scaled further up, which widens `S` and makes the gate's Mahalanobis test
*more* permissive — the opposite of what narrowing the gate around a *tighter* look does. This is
an emergent, explainable consequence of the hypothesis-scaling design (confirmed consistent across
all four order/label combinations' direction of effect), not an obvious coding defect — but it is
also not a case the architect's simpler prototype measurement surfaced, which is exactly why the
number the user approved is stale for the shipped mechanism.

**This is a required finding, not an optional one, but it does not block merge on its own**: the
fence correctly catches and bounds the real behaviour (all 71 sweep tests pass, including these
cells), and CLAUDE.md's "Direction before speed"/"Talking to the user" sections ask that a finding
which changes the user's own prior understanding be surfaced before it is silently carried forward
as settled. Concretely: **`plan.md`'s amendment and `BL-B108.md`'s roadmap entry both need their
"5-67%" language corrected to reflect the shipped code's own measured range (0-86%, worst case
binocular-anchor/unaided-reacquisition at 4.5-5.0 km, far-first)**, and the user should be told the
real worst case before this is treated as a closed decision — not because the model is wrong (it
is the honest limit the user already agreed to accept), but because "about two-thirds of the time"
and "folds almost every time" are different things to sign off on, and the user signed off on the
former.

**4. Surface-bearing fix — confirmed.** `surface_range_estimate` now takes a required
`true_bearing_deg`, used in both cue A (`field_domain="range"`) and cue B (`field_domain=
"depression"`)'s `_stable_fraction` calls. `naked_eye_source.py`'s one call site threads the
observer-to-centroid bearing it already computes (`bearing_deg(observer, centroid)`), not a new
calculation. A ground unit's stable error now genuinely decorrelates with line-of-sight rotation,
closing the gap round-1/round-2 never saw because every prior probe used the air-shape helper.

**5. Tunables — rendered `defaults.toml` read directly, correct; retired key fully gone.**
`BINOCULAR_RANGE_SIGMA_SCALE`, `RANGE_DECORRELATION_BEARING_DEG`, and `RANGE_DECORRELATION_
RANGE_RATIO`'s rendered first sentences are complete, no `e.g.`-truncation, no stray identifier.
`grep -rn CROSS_OPTIC_RANGE_SHARE` across the repo finds it only in docstrings/historical plan and
review text and `defaults.toml` has no entry for it at all — confirmed retired everywhere a live
reference could matter.

**6. `BL-B108.md` claims E1 for same-optic and in-view only — confirmed, modulo finding 3.** The
entry correctly scopes the guarantee ("E1 is delivered same-optic and whenever both groups are in
view") and correctly states the memory-only case is fenced, not solved. Its one inaccuracy is the
quoted rate itself (see finding 3) — the framing is right, the number needs updating.

**Checks re-run independently, full body-layer suite**: `ruff format --check src tests` (192 files,
clean), `ruff check src tests` (clean), `cd body-layer && .venv/bin/mypy src` (79 files, clean),
`pytest tests -q --ignore=tests/test_bl_b104_scenario_mock_flights.py` (2962 passed, 4 xfailed,
matching `implementation.md`'s own numbers exactly — all 4 xfails confirmed pre-existing and
unrelated: `test_visibility.py`/`test_vision_calibration.py`'s slice-2A binocular-presence
regressions), `test_bl_b104_scenario_mock_flights.py` (5 passed, ~117s). No stale `xfail` remains
anywhere in the touched test files — round 1/2's cross-optic `xfail` is fully replaced by the
fence.

### Required Fixes (round 3)

- **Correct the "5-67%" memory-only cross-optic fold-rate figure in `plan.md`'s amendment
  ("Decision Requiring User Input") and `BL-B108.md`'s roadmap entry to the shipped code's own
  measured range, and resurface the real worst case to the user** — see finding 3 above. The
  model and the test fence are both honest and correct; the *documentation the user's "1" decision
  was actually made against* is not. This is cheap to fix (a sentence in each file) and does not
  require touching any code, test, or the fence table itself.

### Optional Refinements (round 3)

- **The crossover where "far group founded via binoculars, near group reacquired unaided" becomes
  the worst cross-optic ordering at 4.5+ km (round 3's finding 3) is not documented anywhere in
  `estimation.py`/`position_belief.py`'s own docstrings**, even though the mechanism (hypothesis-
  scaling amplifying an already-loose look's sigma when the ratio is `>1`) is traceable and
  explainable. A one- or two-line docstring note on `passes_gate`'s hypothesis-scaling paragraph
  would save the next person who measures this from re-deriving it (optional — the fence already
  guards the behaviour; this is purely for the next reader's time).
- **Mechanism-and-calibration-in-one-commit (deviation (a))** is a reasoned, verified exception,
  but if a future amendment needs the same shape (a mechanism change whose own regression test only
  passes once a coupled calibration constant also moves), consider recording the *pattern* — not
  just this one instance — as a named, bounded exception to the `CLAUDE.md` invariant, the same way
  the Security/Performance-Reviewer cadence exemption carries its own stated condition for ending.

### Verdict (round 3)

APPROVED WITH MINOR FIXES

The amendment's mechanism is sound, verified by direct execution rather than inspection on every
substantive claim (correlation agreement, each stated deviation, the surface fix, the rendered
tuning file, the retired key). All checks pass and reproduce the implementer's own numbers exactly.
The one required fix is documentation-only — the "5-67%" figure the user's decision rests on needs
correcting to the shipped code's real range before this is carried forward as a settled number, but
nothing here needs re-implementation, and the fence that actually governs CI is already correct.

### Review Confidence (round 3)

Full read, plus direct execution for every point the dispatch named: an empirical correlation
sweep (noise vs. declared ρ), a revert-and-rerun to verify deviation (a)'s own justification, an
independent re-measurement of deviation (c)'s fold rate, a `git diff`-against-merge-base check for
deviation (d), a 24-cell independent ensemble sweep (N=300) for the memory-only fold-rate question
plus an instrumented trace of `correlated_innovation`'s actual call-site values to find the root of
the architect-prototype/shipped-code divergence, a grep for the retired tunable, and a direct read
of the rendered `defaults.toml`. Checks re-run independently and matched exactly.
