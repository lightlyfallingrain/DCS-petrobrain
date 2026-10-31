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
