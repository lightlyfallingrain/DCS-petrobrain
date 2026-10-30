# BL-B58 option 2 — bound how far one ambiguity fold may move a fused position

> **Status: plan only, not implemented.** Written 2026-10-13 on
> `fix/bl-b59-retention-hysteresis` (from `a024fea`, so BL-12 Stage 3.5 and the BL-B59
> measurement pass are both present).
>
> **The user chose option 2 over the retention term**, 2026-10-13, after
> `plans/group-retention-hysteresis/plan.md` §3 recommended it. That plan's §5 (the retention
> discount) is **superseded, not deleted** — its §2 measurements are what justify this plan, and
> its retention design stands on the record as *rejected on the user's decision*. See its own
> superseding note.
>
> **Two further user directions arrived mid-pass and are answered here, not deferred:**
> position accuracy is a first-class acceptance criterion (§3), and position uncertainty must key
> on observed movement rather than class (§6).

### Goal

Stop a Stage 3 within-group ambiguity fold from moving a contact's fused position further than
that contact could plausibly have travelled — fixing the absorption half (`BL-B58`) and the
eviction half (`BL-B59`) with one mechanism at the source, instead of two compensating
mechanisms in the clusterer.

---

## 1. The seam, and why the other two are wrong

The fold path is `ContactStore.ingest`'s fold branch → `Contact.record` → `position_belief.
fold_position`.

| seam | verdict |
|---|---|
| `position_belief.fold_position` | **Wrong.** It is the real weighted covariance fuse every `record` calls, folds and unambiguous looks alike. Bounding there needs an `is_fold` flag, which makes the fuse know about *association ambiguity* — the boundary that module's own docstring draws twice (the detection envelope is "a caller concern, not something `fold_position` itself should need to know"; `PositionEstimate` "does not know its own classification and should not"). |
| `ingest`'s fold branch | **Wrong, though it is where my probes clamped.** It would assign `contact.position` directly, and `Contact.position`/`last_position`'s field docstrings state the invariant that `record`/`from_percept` are its **only** writers, always via `position_belief`. A probe may break that; merged code may not. |
| **`Contact.record`, via a new keyword** | **Correct.** `record` already resolves `contact_growth_rate_mps(self)` from the contact's *own pre-update* class, and already applies a **caller-invoked post-fusion clamp** immediately after the fuse — `clamp_to_detection_envelope`. This bound is the same shape as that one, and there is precedent in the same five lines. |

**How the fold case is distinguished at that seam:** one keyword-only boolean.

```python
# ingest, the one call site that folds:
contact.record(percept, ambiguous_fold=True)
```

`record` then computes the bound from state it already has and hands `position_belief` a plain
number of metres:

```python
max_displacement_m = (
    growth_rate_mps * max(0.0, percept.t_sim - prior_position.fused_at_sim)
    if ambiguous_fold else None
)
self.position = clamp_fold_displacement(
    clamp_to_detection_envelope(...), prior_position, max_displacement_m
)
```

`clamp_fold_displacement` is a new pure function in `position_belief`, structurally parallel to
`clamp_to_detection_envelope`: scales the fused mean back along the line to the prior so the
displacement equals the bound, leaves the covariance alone, and is an identity when
`max_displacement_m is None`. It knows nothing about ambiguity — it receives metres.

**Applied after the envelope clamp**, so the bound is measured against the position actually
adopted. When the envelope clamp has already held the prior mean, the displacement is 0 and this
clamp is a no-op by construction.

---

## 2. The bound: `plausible_speed_mps(class) × elapsed`, zero new constants

### 2a. Every candidate, measured against the incident

`scratchpad/probe_o2_bound.py`, real pipeline, probe 2's geometry. Residual error is against
truth (the three infantry never move: C1 at x=1000, C3 at x=1030).

| bound | fold tick t=20 | residual @t=20 | residual @t=80 | transitions / 60 ticks |
|---|---|---|---|---|
| none (merged) | **evicted** `[1,3]` | 132.7 / 143.3 m | 132.7 / 143.3 | 12 |
| **B1′ `speed × elapsed`, accept fused covariance** | retained `[1,2,3]` | **40.0 / 40.0 m** | 160.0 / 40.0 | **0** |
| B1 same, but *hold* prior covariance | retained | 40.0 / 40.0 | 208.2 / 40.0 | 10 |
| B2 `speed × elapsed` + `group_matches` test-5 slack | **evicted** — bound 552.1 m | 132.7 | 132.7 | 12 |
| B3a `1.0 × prior.radius_m()` | **evicted** — bound 300.0 m | 132.7 | — | 12 |
| B3b `0.5 × prior.radius_m()` | **evicted** — bound 150.0 m | 132.7 | — | 12 |
| B4a absolute 50 m | retained | 50.0 | 255.9 | 0 |
| B4b absolute 25 m | retained | 25.0 | 200.0 | 6 |
| B5 bound 0 (a fold never moves a position) | retained | **0.0** | **0.0** | 0 |

Four findings decide the design, and three of them are negatives:

- **The `group_matches` test-5 slack analogue is a no-op (B2).** The obvious in-repo precedent
  for this exact bound shape — `displacement_m <= speed_bound_mps * elapsed_s + slack_m`,
  `groups.py:1165` — evaluates to **552.1 m** against a 132.7 m fold. Reusing it verbatim would
  have shipped a mechanism that never fires. It is the right shape for comparing two *centroids
  with independent uncertainty*; it is the wrong shape for bounding a single mean's movement.
- **The whole `radius_m()` family is a no-op (B3).** Not because of the 120 m floor the previous
  pass measured — at the fold tick the prior radius is **300.0 m**, inflated by 20 s unseen — so
  even `0.5 ×` does not bind. Rules out every `k ≳ 0.45`.
- **`B5`'s perfect 0.0 m residual is an artifact of a scene where nothing moves** (§2b).
- **The clamped remainder's covariance is settled by measurement, with a mechanism behind it**
  (§2c).

### 2b. Why not bound 0, which scored perfectly above

`scratchpad/probe_o2_motion.py` — two infantry 200 m apart, **genuinely translating**, every look
ambiguous (the regime in which a zero bound freezes belief). Error against truth:

| variant | t=5 | t=10 | t=20 | t=40 | contacts at t=40 |
|---|---|---|---|---|---|
| truth speed **2.0 m/s** = the class bound | | | | | |
| baseline (unbounded) | 5.0 | 8.9 | 11.7 | 12.5 m | 2 |
| **B1′ `speed × elapsed`** | 5.0 | 8.9 | 11.7 | **12.5 m — byte-identical to baseline** | 2 |
| B5 bound 0 | 10.0 | 20.0 | 40.0 | **80.0 m and growing** | 2 |
| B6 found instead of fold | 0.0 | 0.0 | 0.0 | 0.0 | **82** |
| truth speed **8.0 m/s** = 4× the class bound (a misclassified unit) | | | | | |
| baseline | 20.0 | 35.6 | 46.7 | 49.8 m | 2 |
| B1′ | 30.0 | 60.0 | 120.0 | **104.2 m — worse than baseline** | 2 |

- **B1′ is exactly neutral on a correctly-associated, plausibly-moving contact.** Identical to
  baseline at every sample. That is the property that makes it safe to apply to every fold rather
  than only to suspicious ones: when the association is right and the class rate is right, the
  bound never binds.
- **B5 freezes.** 80 m of lag by t=40, and its covariance tightens to the 120 m floor around a
  stale mean — confidently wrong, the no-omniscience failure in its usual form. Its 0.0 m residual
  in §2a was the scene's truth, not the mechanism's merit.
- **The honest cost of B1′ is the misclassified fast unit**: 104.2 m versus baseline's 49.8 m, a
  direct consequence of `_PLAUSIBLE_SPEED_MPS` being a table of **stated assumptions, none
  measured** (its own docstring). This is the bound's one measured regression and it is a **stated
  risk, not a resolved one** (§8).

### 2c. The clamped remainder: clamp the mean, accept the fuse's covariance

The percept and the belief do disagree after a clamp, and there are three things that could happen
to the difference. Measured (§2a rows B1 vs B1′):

- **Clamp the mean and keep the fuse's covariance** — 0 transitions, 160 m residual at t=80.
- **Clamp the mean and hold the prior's covariance** (`clamp_to_detection_envelope`'s own "hold"
  shape) — **10 transitions, 208 m residual.** Worse, and the mechanism is the reason, not noise:
  holding leaves `fused_at_sim` at the old value, so `elapsed` keeps growing, so the *next* fold's
  bound is larger. The hold is self-defeating.
- **Refuse the fold outright** — not measured as a position variant because it is not a position
  decision: it would discard the percept's classification, cardinality and motion evidence too,
  and force `ingest` to found or drop. Out of scope; D5 chose the fold deliberately.

**So: the fold still happens, with a clamped positional delta.** The percept's class, count,
motion, `last_seen_sim` and observation id all land as they do today; only the *distance the mean
travels* is capped. `fold_displacement_m` records the clamped value actually applied, which keeps
it an honest measure of movement-no-look-supports.

**The zero-elapsed case is real and is a decision, not an oversight.** A same-tick fold has
`elapsed == 0`, hence a bound of 0, hence no positional movement at all. This is physically
correct (no time, no travel) but it forbids same-tick *triangulation* refinement on an ambiguous
pair, which is this module's own premise elsewhere. It is what breaks the one failing test (§5),
whose fold is entirely at `t_sim=0.0`. Recommendation: accept it — a fold is a guess about *which*
contact a percept belongs to, and declining to move the mean on zero elapsed time is the
conservative reading; the next unambiguous look both refines the position and zeroes the budget.
Decision 2 in §8 if the user wants otherwise.

### 2d. Multiplier: `k = 1`

`scratchpad/probe_o2_stage35.py`, incident 2, the absorbing `CONTACT_1`–`CONTACT_4` edge against
Stage 3.5's own measured 78.0 m backstop for that pair:

| bound | C1 position | gap to the ZSU | roster | Stage 3.5's gate |
|---|---|---|---|---|
| none | (868, 10) | **63.8 m** — inside 78.0, absorbs | `[1,3]` | **load-bearing** (without it: `[1,3,4]`, `air_defence=[('OP_SPAAG',1)]`) |
| **k = 1** | (960, 3) | **155.0 m** | **`[1,2,3]`** | **no-op** — same roster with the gate neutralised |
| k = 2 | (920, 6) | 115.2 m | `[1,2,3]` | no-op |
| k = 3 | (880, 9) | 75.5 m — inside 78.0 again | `[1,2,3]` | **load-bearing again** |

`k = 1` is the only value that needs no justification of its own, and it is sufficient. `k = 3`
is measurably too loose. **No new constant: the bound is `plausible_speed_mps` read through
`association_over_time.contact_growth_rate_mps`, the same single resolution `record` already
performs** — one table, per `BL-B51`'s lesson, never a second copy.

---

## 3. Position accuracy, as the acceptance criterion

User direction, 2026-10-13: *"Attack run does need individual unit positions. That is the whole
premise of attack run."* `scratchpad/probe_o2_accuracy.py` scores the incident against **all six
real units**, not only the four with contacts.

| real unit | truth | baseline error | **k=1 error** | bearing error at that range |
|---|---|---|---|---|
| U1 infantry | (1000, 0) | 72.1 m | **40.0 m** | 4.12° → **2.29°** |
| U2 infantry | (1060, 40) | 0.0 m | 0.0 m | — |
| U3 infantry | (1030, −50) | 94.9 m | **40.0 m** | 5.26° → **2.22°** |
| U4 ZSU-23-4 | (805, 0) | 0.0 m | 0.0 m | — |
| U5 infantry (arrives t=20) | (740, 20) | **no record** | **no record** | — |
| U6 infantry (arrives t=20) | (750, −20) | **no record** | **no record** | — |
| distinct contacts serving 6 units | | **2** | **4** | |

**Verdict, in two halves, and only one of them is good.**

- **For a unit Petrovich holds a record for, the bound clears the bar.** 40 m at 1,000 m is
  **2.29° of bearing error, below the naked-eye channel's own `BEARING_SIGMA_DEG = 3.0`** — the
  fold-induced error drops from 1.4–2.5σ (the dominant error term) to under 1σ (no longer the
  limiting one). The pilot cannot be aimed more precisely than the look that produced the belief,
  and after the bound he is not being aimed *less* precisely than that either. The baseline's
  72–95 m / 4.1–5.3° is above the noise floor and is a real aiming error.
- **For completeness of the target set, the bound changes nothing.** Two real infantry have **no
  contact at all**, before and after — their percepts were folded into C1 and C3. An attack run
  cannot be aimed at a unit Petrovich does not believe exists, and no displacement bound creates
  it. That is BL-12 Stage 3's accepted undercount, and §4 is about it.

**Drift is bounded but not removed.** Under repeat folds the k=1 residual grows 40.0 m (t=20) →
46.8 m (t=80) in the incident, and up to 160 m in the §2a single-contact trace where every fold
pulls the same way. The bound converts an instantaneous non-physical jump into drift at no more
than the class's plausible speed — which is, by construction, **indistinguishable from the unit
having actually walked there.** That is the most a mechanism can do without knowing the
association was wrong, and it is the honest ceiling on this plan's accuracy claim.

---

## 4. The fold itself versus its magnitude — the BL-14 finding

Asked for by the user, assessed rather than assumed, and **not** redesigned here.

BL-12 Stage 3's fold deliberately merges two contacts' records inside a group; its accepted
failure modes say `contributing_observation_ids` and `sighting_spans` become unreliable at
within-group grain and an undercount replaces an overcount — accepted on the explicit reasoning
that **the group-level answer stays correct**. BL-14 changes the product that reasoning was about.

Measured (`probe_o2_accuracy.py`, `probe_o2_motion.py`):

| | per-unit position error | contacts for the real units |
|---|---|---|
| fold, unbounded (today) | 72–95 m, 2 units invisible | 4 → 16 for 6 |
| **fold, bounded at k=1** | **40 m, 2 units invisible** | **4 for 6, stable** |
| **no fold at all** (`_fold_target_…` → `None`, which reverses `D5` at contact grain) | **0.0 m, every unit visible** | **18 for 6**; and 82 for 2 in the moving-pair scene |

**The finding: bounding the displacement is sufficient for the *accuracy* of a per-unit position
and insufficient for its *existence*.** The fold's magnitude is what makes a held position wrong;
the fold's existence is what makes a unit absent. Those are different defects with different
fixes, and only the first is in this plan.

**So if BL-14 consumes individual member positions, it needs something this plan does not
deliver, and reversing D5 is not it** — 82 contacts for 2 real units is the overcount runaway D5
was chosen to prevent, and it would be worse for the pilot than an undercount. What BL-14 would
need is a third option neither D5 nor this plan contains: resolving a within-group ambiguity by
**splitting** (founding the member *and* keeping the group's cardinality honest) rather than by
folding or founding freely. **Decision 1 in §8.** It is better settled before BL-14 is planned
than during it, which is why it is here rather than in a later pass.

---

## 5. What the existing suite says — mechanical, not argued

The proposed bound installed into the real fold branch for a whole suite run
(`scratchpad/clamp_plugin.py`, a pytest plugin, so `src/` is untouched):

```
cd body-layer
PB_CLAMP_K=off PYTHONPATH=../plans/bounded-fold-displacement/scratchpad \
  .venv/bin/python -m pytest -p clamp_plugin -q tests/   # 1697 passed, 4 xfailed  (control)
PB_CLAMP_K=1.0 ...                                       # 1 failed, 1696 passed, 4 xfailed
PB_CLAMP_K=2.0 ...                                       # 1 failed, 1696 passed, 4 xfailed
```

**Exactly one test moves, and it is the right one:**
`tests/test_contacts.py::test_fold_displacement_m_is_written_on_a_fold_and_reset_on_an_unambiguous_record`,
at `assert expected_displacement > 0.0` → `assert 0.0 > 0.0`. Its whole D/E/F geometry is at
`t_sim=0.0`, so elapsed is 0 and the bound is 0 — the §2c zero-elapsed case, not a defect in the
test. It is Stage 3.5's provenance test and must be rewritten to span a non-zero interval (and to
assert the clamp, which is new behaviour it should now pin).

**Both pinned invariants pass unchanged**, confirmed individually:
`tests/test_groups.py::test_the_eager_cap_still_chains_a_long_infantry_line` (Stage 0b's evidence,
**not to be modified**) and
`tests/test_callouts.py::test_2c_transcript_fixture_renders_three_lines_not_seven` (`BL-B50`'s
recheck fixture, whose own incident carries a 219 m fold).

### Stage 3.5's six-row table, re-measured

| row | input | under the bound |
|---|---|---|
| **A** 2C incident t=12 | real pipeline | **the 2C test passes unchanged** (§5). The gate's veto is no longer needed to reach the right answer; not separately traced per-edge. |
| **B** incident 2 t=20 | real pipeline | **gate becomes a no-op at k=1 and k=2** — same roster with the admission term neutralised. Load-bearing again at k=3 (§2d). |
| **C** pinned 1,200 m chained infantry line | synthetic positions, no fold budget anywhere | **IDENTICAL by construction** — the row feeds `_cluster_contacts` directly; a change confined to `contacts.py`'s fold branch cannot reach it. |
| **D** three infantry at 30 m | synthetic | **IDENTICAL by construction**, same reason |
| **E** un-folded armour joiner | synthetic | **IDENTICAL by construction**, same reason |
| **F** A1 carries a hand-set 130 m budget | synthetic, budget hand-set | **IDENTICAL by construction** — the budget is supplied by the row, not produced by a fold |

**Rows C–F are stated as identical by construction rather than re-run**, and the construction is
the argument: those rows are predicate-level inputs to `_cluster_contacts`, and this plan changes
only what `contacts.py` writes into `Contact.position` / `fold_displacement_m`. The suite run
above is the mechanical check that nothing else moved.

**So Stage 3.5's gate and `fold_displacement_m` both stay**, and the argument is not "keep merged
machinery by default":

- The gate is **measured load-bearing at k=3**, i.e. it is the safety net for exactly the failure
  mode this bound is most exposed to — a `_PLAUSIBLE_SPEED_MPS` row that turns out too generous
  (§2b's 8 m/s case). Removing it would make an uncalibrated table a single point of failure.
- The field's input is now physically bounded, so the never-retires defect (`BL-B58`'s recheck
  note) changes from unbounded to speed-bounded — **but it does not go away**: measured 40.0 m at
  t=20 → 160.0 m by t=80, still zero resets. **The accumulator fix is still owed**, and it is
  Stage 3 below rather than a consequence of this bound.

---

## 6. The motion-keyed uncertainty direction — does it invalidate this bound?

User direction, 2026-10-13 (`docs/acceptance/2026-10-13-position-uncertainty-direction.md`, on
`docs/tree-cover-direction`): *"Position uncertainty caused by movement must be based on whether
movement is observed or not."* Not designed here. Assessed for whether it breaks the bound.

> **Built by `BL-B104` Stage 8 (2026-10-30, `plans/bl-b104-ground-contacts-on-ground/plan.md`).**
> This section probed the narrower form of the rule (`0.0` only for `Contact.motion.state ==
> "stopped"`, class rate for `None`) and found it did not change this plan's own bound. BL-B104
> Stage 8 built the wider rule the user actually asked for (`None` **also** gets the tiny rate,
> not just `"stopped"` — "most typical case is units being stationary") as
> `UNOBSERVED_MOTION_GROWTH_RATE_MPS`, gated on `Contact.on_surface`, in
> `association_over_time.contact_growth_rate_mps` — the same single resolution function this
> section already reads. Treat this section as historical analysis of the narrower form, not as
> still-open direction: the direction is now built, differently and more completely than probed
> here.

`scratchpad/probe_o2_motion_keyed.py`, with the narrowest honest form of the rule — `0.0` when
`Contact.motion.state == "stopped"`, class rate when `None`:

| | `Contact.motion` | growth rate | passing gate candidates per fresh percept |
|---|---|---|---|
| as shipped | `None` ×4 | 2.0 / 8.0 | **3** |
| motion-keyed rate, motion still `None` | `None` ×4 | 2.0 / 8.0 | **3** — identical |
| percepts declare `apparent_motion=False` | `"stopped"` ×4 | **0.0** ×4 | **3** — still identical |

**It does not invalidate the bound; it improves it, and the coupling is deliberate rather than
accidental.** Because the bound reads `contact_growth_rate_mps` — the one shared resolution — a
motion-keyed table makes an observed-stationary contact's fold bound ≈ 0 automatically, which §2a
measured to be the *correct* answer for a unit that is genuinely not moving, and §2b measured to
be *wrong* only for a unit that is moving. The motion-keyed rule supplies exactly the
discrimination the bound was missing. **This is the argument for reading the bound through that
function and never copying the table.**

**The fragility is the horizon, and the bound inherits it.** If "observed stopped ⇒ 0" holds over
arbitrary elapsed time, this bound becomes "a fold may never move this contact's position, ever",
which is §2b's freeze with no escape. The user bounded his own claim at *"a couple of minutes"*;
whatever horizon that entry settles on, **this plan's acceptance table must be re-run by it** —
stated in Stage 4 and as a risk, not assumed away. `None` is **not** `"stopped"`: with `None`
falling back to the class rate, the bound behaves exactly as measured here, which is why every
number in this plan survives that change unaltered (the incident's motion state **is** `None`,
measured above).

**The two hypotheses that came with the direction are both false, measured:**

- **It does not reduce how often the fold fires.** Three passing candidates at 0.0 m/s, exactly as
  at 2.0 m/s. The gate's width here is dominated by the percept's own declared uncertainty — the
  fixture's 300 m `_FALLBACK_UNCERTAINTY_RADIUS_M` — on top of which elapsed-motion inflation at
  20 s × 2 m/s is 40 m, a rounding error. Removing a 40 m term from a 300 m gate cannot un-ambiguate
  anything.
- **It does not shrink `BL-B24`.** Two contacts 17 m apart, both observed stationary, reacquired
  after 120 s: a fresh percept at one still passes **both** gates at 0.0 m/s growth, same as at
  2.0 m/s. 17 m is far inside any declared look uncertainty, so the ambiguity is in the looks'
  precision, not in elapsed-motion inflation.

So the motion-keyed entry is right on its own terms (it fixes **staleness**) and should **not** be
sequenced as if it also fixed fold frequency or `BL-B24`.

---

## 7. Affected Modules / Files

- `body-layer/src/belief/position_belief.py` — new `clamp_fold_displacement(fused, prior,
  max_displacement_m)`, parallel to `clamp_to_detection_envelope`; identity when the bound is
  `None`. Module docstring gains it beside the existing caller-invoked-clamp note.
- `body-layer/src/belief/contacts.py` — `Contact.record` gains keyword-only `ambiguous_fold:
  bool = False`, computes the bound from the `growth_rate_mps` it already resolves, and applies the
  new clamp. `ingest`'s fold branch passes `ambiguous_fold=True`. `fold_displacement_m`'s docstring
  records that it now measures the **clamped** displacement.
- `body-layer/tests/test_contacts.py` — the one failing provenance test rewritten over a non-zero
  interval, plus the clamp's own cases. **`tests/test_groups.py::
  test_the_eager_cap_still_chains_a_long_infantry_line` is not modified.**
- `body-layer/tests/test_groups.py`, `tests/test_callouts.py` — new cases for §2a/§2d/§3; no
  existing assertions changed.
- `body-layer/ROADMAP/BL-B58.md` — option 2 chosen; this plan; the gate-goes-quiet measurement.
- `body-layer/ROADMAP/BL-B59.md` — fixed by this plan's source bound, not by a retention term.
- `plans/group-retention-hysteresis/plan.md` — §5 superseded in place with a pointer here.
- `body-layer/docs/STRUCTURE.md` — the `position_belief.py` / `contacts.py` entries.

---

## 8. Implementation Plan

Per `body-layer/CLAUDE.md`, mechanism and calibration never share a commit.

**Stage 0 — record what is already measured. No code.**
`BL-B58` (option 2 chosen, the gate-no-op finding), `BL-B59` (fixed at source), and the
superseding note on `plans/group-retention-hysteresis/plan.md` §5. *Acceptance:* the notes exist
and cite the probes. First, so none of it is lost if the rest is deferred.

**Stage 1 — the mechanism, provably behaviour-neutral.**
`clamp_fold_displacement` + the `ambiguous_fold` keyword, with **`ingest` not passing it**. Every
call site therefore has `max_displacement_m is None`, which is the identity branch.
*Acceptance, a proof rather than a sample:* the full suite unchanged at **1697 passed / 4
xfailed** (control run above, confirmed on this branch). A single failure means the wiring is
wrong, not that a bound bound.

**Stage 2 — the calibration: switch the bound on.**
`ingest`'s fold branch passes `ambiguous_fold=True`. One commit, one attributable behaviour shift.
*Acceptance:* §2a's B1′ row, §2d's k=1 row, §3's accuracy table, §5's suite result (1696 + the one
rewritten test), and both pinned invariants green.

**Stage 3 — the accumulator, which is owed either way.**
`fold_displacement_m` still never retires (40 → 160 m, zero resets). Its own commit and its own
re-measurement of §5's table, per `BL-B58`'s recheck note. `max()` instead of `+=` is the
candidate the previous pass preferred; it changes merged Stage 3.5 admission behaviour, so it is
not folded into Stage 2.

**Stage 4 — observability.** A `--group-trace` / detection-trace field recording the clamp
actually applied, so a sortie can tell "bounded" from "never needed bounding" without re-deriving
it. Stage 3.5 set this precedent with `fold_displacement_m`.

**Deliberately not staged here:** the motion-keyed rate (§6, its own entry), any re-tune of
`GROUP_PROXIMITY_GAP_RATIO` or `GROUP_REPORTING_EAGER_COHESION_CAP_M`, and any change to Stage 3's
fold-versus-split choice (§4, decision 1).

---

## 9. Invariant conflicts — checked, not assumed

- **No omniscience / DCS authoritative.** The bound is derived entirely from believed state:
  `Contact.last_class_raw` → `object_model.profile_for` → `plausible_speed_mps`, and
  `percept.t_sim − prior.fused_at_sim`. No `derived_world_position`, no DCS object id, no
  ground-truth position. The *probes* read truth to score residual error; the mechanism does not.
- **Stage 0a (both-`EAGER`) / Stage 0b (the 500 m eager cap).** Untouched — this plan changes no
  threshold and no backstop. Row C's pinned test passes unmodified (§5).
- **`D5`'s continuity preference.** Preserved exactly: the fold still happens and still prefers
  continuity over founding. Only the distance the mean moves is capped. Measured 0 membership
  transitions over 60 ticks versus the baseline's 12 — strictly *less* churn, `D5`'s own direction.
- **`D6`'s air-defence carve-out.** Not on this path. `D6` gates the fold's candidate set and
  `reconcile` phase 2; this clamp acts after the target is chosen and changes neither. Measured:
  `air_defence_composition` stays `[]` at k=1 (§2d) where the baseline produced
  `[('OP_SPAAG', 1)]` without Stage 3.5's gate.
- **`BL-B50`** (membership flipping): pushed the right way, 0 transitions vs 12, and its 2C
  fixture passes unchanged.
- **`Contact.position`'s single-writer invariant.** Honoured — §1's whole reason for rejecting the
  `ingest` seam.
- **`BL-B51`'s one-table rule.** Honoured — the bound reads `contact_growth_rate_mps`, never a
  copy of `_PLAUSIBLE_SPEED_MPS`. §6 is why that matters more than it looks.
- **Cost.** One `hypot`, one comparison and (rarely) one scale per fold — on the fold branch only,
  which is already the expensive path. Nothing added to any per-tick loop.

---

## 10. Risks & Unknowns

- **The bound is only as good as an uncalibrated table.** `_PLAUSIBLE_SPEED_MPS` is stated
  assumptions, none measured. §2b's 8 m/s case is the measured regression: a contact moving 4× its
  believed class rate is tracked **worse** than today (104.2 m vs 49.8 m). Mitigated, not removed,
  by Stage 3.5's gate remaining in place and by the classification fold itself correcting a
  misclassification over time. **Stated risk.**
- **Drift is bounded, not eliminated** (§3). 160 m of accumulated residual in the adversarial
  single-contact trace, at the plausible-speed rate. If BL-14 needs better than that, the fix is
  §4's split, not a tighter bound.
- **Two real units remain invisible** in the incident, before and after (§3). This plan does not
  claim to fix the undercount.
- **Zero-elapsed folds move nothing** (§2c) — a deliberate consequence, and the one existing test
  it breaks.
- **The motion-keyed horizon is unsettled** (§6) and this bound inherits it. This plan's acceptance
  table must be re-run when that entry lands.
- **Every number is from one geometry** — probe 2's three-infantry-plus-ZSU scene at the fixture's
  300 m `_FALLBACK_UNCERTAINTY_RADIUS_M`, a path `association_over_time.py`'s own comment says
  "should not happen in production". `BL-B58` argues at length that the *mechanism* is not confined
  to that artifact while the magnitudes are amplified by it. The same caveat applies here, with one
  addition: a slack term keyed on *declared* uncertainty (§2a B2) is a no-op in every current
  fixture and production-meaningful, so **the fixtures cannot calibrate that family at all** —
  stated as a limit of the measurement, not reasoned past.
- **No sortie has exercised this path.**

---

## 11. The milestone-completion question

**Does this change what comes next, or invalidate a downstream assumption?** Yes, twice.

1. **`BL-14` (attack run).** §4 is the finding: after this bound, a held member position is
   accurate to within the perception channel's own bearing noise, so *accuracy* stops being
   BL-14's blocker. *Completeness* becomes it — two real units with no record — and that is Stage
   3's fold-versus-split choice, which is **decision 1** and should be settled before BL-14 is
   planned. This plan narrows BL-14's problem rather than unblocking it.
2. **`BL-B59` is closed by this plan rather than by its own entry's instrument**, and
   `plans/group-retention-hysteresis/plan.md` §5 is superseded. **`BL-B50`'s recheck condition**
   becomes dischargeable (§5, the 2C fixture stable). **`BL-B58`'s recheck note survives**: the
   accumulator still never retires, now at a bounded rate (Stage 3).

---

## 12. Decisions Requiring User Input

1. **Does `BL-14` need a record per unit, or an accurate position for the records it has?** §4 is
   measured: the bound delivers the second (40 m, 2.29°, inside the channel's own 3.0° σ) and
   cannot deliver the first. Reversing `D5` delivers the first at 82 contacts for 2 real units,
   which is worse for the pilot. If per-unit records are genuinely required, Stage 3 needs a
   **split** path — a new mechanism, its own entry, and a revisit of `Q5`/`D5`. **My read: plan
   BL-14 against the group-level answer plus accurate member positions, and only build the split
   if flying it shows the undercount actually costs an attack run.** This is the one decision that
   should not wait.
2. **Accept that a same-tick ambiguous fold moves nothing?** (§2c) Recommended, zero constants,
   costs same-tick triangulation refinement on ambiguous pairs only, and rewrites one test. The
   alternative that keeps triangulation is a slack term keyed on declared uncertainty, which is a
   **no-op in every existing fixture** and therefore uncalibratable with what exists today.
3. **Stage 3's `+=` → `max()` now, or after a sortie?** It changes merged Stage 3.5 behaviour, and
   no live symptom is attached to it yet. Deferring is defensible; leaving it unrecorded is not,
   which is why Stage 0 exists.
