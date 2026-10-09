# BL-W32 — Precise position belief — Stages 1 through 5

- [x] **Precise position belief — Stages 1 through 5. DONE** #status/done, merged on `feature/binocular-optic`
  alongside the two milestones below it (plan/review: `plans/precise-position-belief/`). Replaces
  the reporting-vocabulary quantisation that used to stand in for a believed position with a real
  perception-side error model, closing a bug that was worse than "coarse": `naked_eye_source.py`'s
  old `_quantise_range_m` snapped every range onto its bucket's *upper bound*, not its midpoint, so
  belief was systematically biased **long** by up to a full bucket width (500 m at 3 km) — not a
  conservative approximation, a one-directional error nobody had named. The old clock-bucket
  bearing/range-bucket split was also inverted: it claimed range was known tighter than bearing,
  when a human points at something far better than he judges its distance to it.

  **The model**: each look's error ellipse is elongated along its own line of sight —
  `sigma_down_m = RANGE_FRACTIONAL_SIGMA(0.17) * true_range_m` (derived from ED's own `OP_D*`
  range-bucket ladder, which coarsens with range — the signature of a fractional error), `sigma_
  cross_m = radians(BEARING_SIGMA_DEG(3.0)) * true_range_m` (a declared, unmeasurable judgement
  constant — nothing in DCS reports a crewman's own pointing precision). **Every reported bearing/
  range is perturbed**, not just budgeted with a disclaimer (`perception/estimation.py`,
  `perturbed_bearing_range`): a per-look draw hashed off the observation id (reproducible, averages
  down across looks) plus a per-object systematic bias hashed off the object id and never re-drawn
  (`SYSTEMATIC_BIAS_FRACTION = 0.4` of one look's sigma). The property this defends: a
  heavily-observed contact must converge to a position that is confidently and precisely **wrong**,
  not to exact ground truth behind a cosmetic uncertainty figure — stating an uncertainty on an
  exact number would make `belief/percept.py`'s no-omniscience boundary a comment rather than a
  mechanism. `derived_world_position` stays ground truth, unperturbed and never crew-facing (trace/
  debug tooling only).

  **Fusion is 2x2 covariance, not a running mean** (`belief/position_belief.py`'s `PositionEstimate`
  — mean x/z + covariance + `as_of_sim` — now what `Contact.position` holds and `record()` folds
  into via the standard information-form update; `last_position`/`last_position_uncertainty_m` stay
  as derived properties so existing readers compile unchanged). This is real triangulation: two
  looks from different lines of sight cross and narrow both axes, which a scalar radius cannot
  express. `association_over_time.py`'s spatial gate was promoted to match — a 2D Mahalanobis-style
  test on summed covariances instead of a scalar-radius comparison — **and this is the one piece
  carrying real regression risk pending a live sortie**: a gate that is too tight reproduces the
  2026-09-09 duplicate-contact runaway, this time from a genuinely different mechanism (covariance
  fusion, not shared-formula acuity) than the one Stage 3b-i's own revert was about, so the two
  should not be read as the same risk recurring.

  **Spent downstream**: `belief/optic_policy.py`'s binocular sweep now passes the contact's real,
  measured `bearing_uncertainty_deg` instead of a hardcoded half-clock-bucket default — a
  well-observed contact's sweep collapses toward a single stare instead of always stepping the full
  width Stage 3b assumed.

  **Required review fix, applied post-merge**: Stage 1's `PositionUncertainty` declaration landed
  on `perception/hybrid_source.py` (the scope/HelperAI channel) but Stage 2's actual perturbation
  never did — the plan's own Decision 2 ("does the scope channel get the same treatment?") was never
  recorded as answered by either implementer, so a heavily-observed scope contact was converging on
  *exact* ground truth behind the declared 300 m band, on the channel the pilot actually flies with
  today. Fixed by applying `perturbed_bearing_range` there too, isotropic on both axes at
  `SCOPE_UNCERTAINTY_M` (no reporting bucket on this channel to derive an anisotropic figure from);
  a regression test now pins that repeated scope-channel looks at a stationary object do not
  converge on truth. Decision 2 is recorded answered ("yes") in `plans/precise-position-belief/
  implementation.md`.

  **Uncalibrated, pending a sortie** — same debt class as every perception constant before its
  first flight: `RANGE_FRACTIONAL_SIGMA`, `BEARING_SIGMA_DEG` (the one number only the user's own
  cockpit judgement can move, if callouts point at the wrong place), `SYSTEMATIC_BIAS_FRACTION`,
  and `SCOPE_UNCERTAINTY_M` (still the original placeholder, never revisited). **Unflown as of this
  entry** — Stage 3's gate in particular needs a live sortie before it can be trusted, per the
  plan's own "do not merge Stage 3 without a live sortie" instruction.


**Closed by [[BL-W7]]'s sortie, 2026-09-25** — this entry's own "Unflown as of this entry" sentence above predates that closure and is left unedited (see [[BL-W7]] for why), but live acceptance is no longer outstanding.
