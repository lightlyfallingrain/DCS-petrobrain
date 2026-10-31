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
