# BL-B59 — retention against the relative cohesion test

> **SUPERSEDED at §5, 2026-10-13 — the user chose [[BL-B58]] option 2 instead.** Replacement:
> `plans/bounded-fold-displacement/plan.md`. §2's measurements remain the base for it; see the
> note at §5 for exactly what stands and what does not.

> **Status: plan only, not implemented.** Written 2026-10-13 by the Architect pass on
> [[BL-B59]], on `fix/bl-b59-retention-hysteresis` (branched from `main` at `1884775`, so
> BL-12 Stage 3.5 is present). Prioritised by the user as the next piece of work after
> BL-12 merged.
>
> **Read §2 before §5.** The measurements reverse this entry's own framing of the defect
> and rule out the instrument it names, so the plan does not implement what the backlog
> entry proposed. §3 is the effort/value correction the user is owed before deciding.

### Goal

Stop a Stage 3 within-group ambiguity fold from evicting a real, correctly-identified member
from the group it already belongs to — the eviction half of the fold-drift defect whose
absorption half BL-12 Stage 3.5 fixed, and the dangerous half, because for an air-defence
member it **suppresses** a report rather than fabricating one.

---

## 1. Reproduction — confirmed, not taken on trust

`plans/group-cohesion-admission-gate/scratchpad/probe_b58_second_incident.py`, run against
`1884775`:

```
=== t=20, before the fold   relative_threshold=195.6
  CONTACT_1-CONTACT_2        72.1 gap     500.0 backstop     195.6 thresh  LINK
  GROUP_1 members=['CONTACT_1', 'CONTACT_2', 'CONTACT_3'] air_defence=[]

=== t=20, after the fold    relative_threshold=169.0
  CONTACT_1-CONTACT_2       194.6 gap     500.0 backstop     169.0 thresh  .
  GROUP_1 members=['CONTACT_1', 'CONTACT_3'] air_defence=[]
```

Byte-identical at t=30. The defect is live and persistent, exactly as [[BL-B59]] records.

---

## 2. The measurements that reverse the entry's framing

### 2a. The threshold tightening is the *minor* cause. The fold's own displacement is the major one.

[[BL-B59]] states the mechanism as *"position drift shifts the median nearest-neighbour gap,
which tightens `_cluster_contacts`'s relative threshold, which can drop a real member."*
Decomposing the two terms across the fold tick:

| term | before | after | change |
|---|---|---|---|
| `relative_threshold` | 195.6 m | 169.0 m | **−13.6 %** |
| `CONTACT_1–CONTACT_2` gap | 72.1 m | 194.6 m | **+170 %** |

The gap moved an order of magnitude more than the threshold. Measured cause, from
`Contact.fold_displacement_m` at the fold tick
(`scratchpad/probe_b59_mechanism.py`):

```
fold_displacement_m: {'CONTACT_1': 132.7, 'CONTACT_3': 143.3, 'CONTACT_2': 0.0, 'CONTACT_4': 0.0}
pos before: C1=(1000, 0)  C2=(1060, 40)  C3=(1030, -50)
pos after : C1=( 868,10)  C2=(1060, 40)  C3=( 888, -35)
```

`CONTACT_1` and `CONTACT_3` were each dragged ~133/143 m toward the new percepts.
`CONTACT_2` did not move at all. The group genuinely *split in two* in position space —
`{C1,C3}` near x≈878 and `{C2}` at x=1060 — and clustering reported that split correctly.
**The clustering is not misbehaving. It is reading a position that the fold corrupted.**

So this is not a second, independent defect with its own instrument. It is **the same
provenance defect as [[BL-B58]], read on the other side of the comparison** — and
`fold_displacement_m`, the field Stage 3.5 added, already measures it exactly.

### 2b. The backstop never evicts. The relative term is the only binding constraint.

Measured above: the `CONTACT_1–CONTACT_2` backstop is **500.0 m** (Stage 0b's
`GROUP_REPORTING_EAGER_COHESION_CAP_M`, both sides infantry) against a 194.6 m gap. The
binding threshold is the relative term at 169.0 m, by `min(relative, backstop)`.

**Consequence for the design: a retention term must touch the relative term only.** Loosening
`_pair_backstop_m` would reopen the n≥3 over-merge the module docstring's own history
records, and buys nothing here.

### 2c. `watch-reporting` §4e's 1.5× factor does not transfer. Measured, not argued.

§4e applies a 1.5× factor to engagement-envelope *exit* and argues for naming it hysteresis.
Implemented as the literal analogue — prior co-members compared against
`min(relative_threshold * 1.5, backstop)` — against the real pipeline
(`scratchpad/probe_b59_lifetime.py`):

| candidate | fold tick t=20 | next 60 ticks |
|---|---|---|
| baseline | `GROUP_1:[1,3]` — evicted | 12 transitions |
| **§4e's 1.5× on the relative term** | `GROUP_1:[1,2,3]` — retained | **loses `CONTACT_2` again at t=25**, 12 transitions |
| fold-budget discount, unbounded | `GROUP_1:[1,2,3]` — retained | **0 transitions**, holds all 60 ticks |

**What transfers and what does not:**

- **The shape transfers**: an already-formed pair is tested differently from a first
  formation, and it must be *named* retention so nobody later reads it as a fudge. §4e's own
  closing argument, and it stands.
- **The factor does not.** 1.5× fixes the fold tick and loses the member five ticks later.
- **The justification does not, and this is the load-bearing difference.** §4e is a Schmitt
  trigger against a *continuous* quantity flapping at the poll rate — boundary noise, where
  widening the band is the whole of the fix. BL-B59's perturbation is **discrete, one-sided,
  attributable and already measured to the metre**. When you know the artifact's size, you
  subtract it; you do not widen a band and hope it covers it. Measured: the artifact is
  132.7 m against a 169.0 m threshold, i.e. 79 % of the threshold — no plausible band
  multiplier dominates it reliably.
- `plans/watch-reporting/fix-review.md`'s note that the altitude side has *no* hysteresis
  counterpart unlike range is the right precedent for the **asymmetry** here: retention
  applies to the relative term and deliberately not to the backstop (§2b), and that asymmetry
  must be stated in the docstring as a decision.

### 2d. Every bounded form of the discount fails within five ticks. Only the unbounded one works.

The natural mechanism is the dual-sign reuse of Stage 3.5's own field: for a prior co-member
pair, `effective_gap = max(0.0, gap − fold_displacement_m[i] − fold_displacement_m[j])`.
Perfectly symmetric to the admission gate (which *adds* the same two terms), and
algebraically identical to the shipped rule wherever no fold has occurred.

It needs a bound, or a repeatedly-folded pair becomes unevictable. Sweeping the bound as a
fraction `f` of the pair's own threshold, `discount = min(folds[i] + folds[j], f × threshold)`
(`scratchpad/probe_b59_trace.py`, real pipeline, `CONTACT_1`'s group traced for 60 ticks after
the fold):

| bound | fold tick t=20 | `CONTACT_2` present | holds until |
|---|---|---|---|
| baseline (no retention) | evicted | 0 / 60 ticks | — |
| `f = 0.1` | **evicted** | 0 / 60 | — |
| `f = 0.25` (ceiling 1.25× threshold) | retained | 4 / 60 | t=25 |
| `f = 0.5` (ceiling 1.5× threshold) | retained | 4 / 60 | t=25 |
| `f = 1.0` (ceiling 2.0× threshold) | retained | 4 / 60 | t=25 |
| **unbounded** | retained | **60 / 60** | holds |

Per-pair trace at the fold tick, showing why the bound stops mattering and then starts
failing:

```
f=0.25  C1-C2 gap=194.6 th=169.0 folds=132.7+0.0 cap= 42.2 disc= 42.2 eff=152.3 LINK
f=0.5   C1-C2 gap=194.6 th=169.0 folds=132.7+0.0 cap= 84.5 disc= 84.5 eff=110.1 LINK
f=1.0   C1-C2 gap=194.6 th=169.0 folds=132.7+0.0 cap=169.0 disc=132.7 eff= 61.9 LINK
```

All three clear the fold tick. All three lose the member at t=25, because the infantry are
re-observed, **fold again**, and the budget grows past the bound.

**This sweep is not a calibration curve with a good value in it.** There is no `f` that both
bounds the term and fixes the defect. That is the finding, and it rules out the whole family.

### 2e. Why: the fold budget never retires in the regime where the defect lives.

`Contact.fold_displacement_m` resets to `0.0` on either unambiguous resolution
(`contacts.py:1071` object-permanence continuity, `contacts.py:1086` a single passing gate
candidate) and accumulates with `+=` otherwise. Measured over 60 ticks of continued
re-observation in this geometry (`scratchpad/probe_b59_lifetime.py`):

```
t=25  C1=132.7 → 172.5    t=50  C1=222.3    t=70  C1=235.0
t=30  C1=192.3            t=60  C1=229.6    t=80  C1=239.0   (C3 = 259.8)
```

**It never resets. Not once in 60 ticks.** The reason is structural: in a scene dense enough
for the relative term to bind, every re-observation has ≥2 passing gate candidates, so every
re-observation is *itself* ambiguous and folds again. The unambiguous resolution that would
retire the budget never arrives.

Covariance supplies no retiring bound either — `Contact.position.radius_m()` floors at
**120.0 m** and never goes below it (`scratchpad/probe_b59_bounded.py`), which is why the
`min(fold, radius_m())` variant also fails (evicts at t=30, 11 transitions).

**This is a measured finding about already-merged Stage 3.5 code, not only about BL-B59.**
[[BL-B58]]'s own Risks section recorded accumulate-not-replace as *"a stated assumption, not
measured against a real repeat-fold incident."* It is now measured: the *admission* penalty
grows monotonically and without retirement too, so Stage 3.5 becomes progressively more
exclusionary for a repeatedly-folded contact — 132.7 m of penalty at the first fold, 239.0 m
by t=80. No live symptom is attached to that yet; it needs a recheck note on [[BL-B58]]
either way (§7, Stage 0).

### 2f. Oscillation: not reachable by the retention term. Reachable by its absence.

Driven for 60 ticks with repeat folds (§2d's probe): the unbounded discount gives **0
membership transitions**. Every bounded variant and the baseline give **12**, all of which
trace to contact-id churn *downstream of the eviction* (new contacts founded once the group
breaks), not to the retained pair alternating. No configuration produced a retention term and
the admission gate alternating against each other.

Mechanically that is expected and worth stating as the reason rather than the observation: the
discount only ever **shrinks** a gap, and only for a pair that was **already** co-member, so it
can add an edge but never remove one and never found a group. The admission gate only ever
**grows** a gap. They push on disjoint pair sets within one pass — a pair is either a prior
co-member or it is not — so neither can undo the other inside a tick.

---

## 3. Effort/value — the correction the user is owed

[[BL-B59]] frames the fix as *"retention hysteresis against the relative test … a second
mechanism with its own calibration,"* which reads as one predicate branch plus one constant —
roughly Stage 3.5's shape and cost.

**Measured, that is not available.** The honest options are:

| | [[BL-B59]]'s framing | measured |
|---|---|---|
| instrument | a hysteresis factor on the relative term | **ruled out** — 1.5× fails at t=25 (§2c); *no* bounded factor works (§2d) |
| new constants | one, calibrated | **zero if unbounded, and then the term has no ceiling**; or one that does not work |
| the sufficient fix | — | **unbounded** fold-budget discount — correct in every probe, with a latent over-retention runaway (§2e) |
| scope | `groups.py` | `groups.py`, plus a decision about `contacts.py`'s accumulation semantics that **also affects merged Stage 3.5 behaviour** |

**And the value is smaller than the framing implies**, for a reason Security's BL-12 pass
already established and which this plan has no measurement that contradicts: the exposure is
**visible** in `--group-trace` (a shrinking roster under one `group_id`) and **partially
bounded** — `CONTACT_CLASSIFICATION_CHANGED` and watched-contact engagement warnings key on
the *individual* contact, so an evicted member that has already spoken for itself still gets
its warning. The genuinely unreported case is narrow: a contact absorbed and evicted again
before its own disclosure ever fired, never watched, where the group line was its only
channel.

**What I recommend, and it is not what the entry proposes.** The measurements point at
[[BL-B58]]'s **option 2** — *bound how far a single fold-driven `Contact.record` call may move
a fused position* — which the user declined for the absorption half. One mechanism, at the
source, fixes **both** halves: if the fold cannot move `CONTACT_1` by 132.7 m, the absorbing
edge never closes *and* the evicting gap never opens. It also removes the need for a retention
term entirely, rather than adding a second mechanism that pushes against the first and needs a
ceiling nobody can calibrate.

That is a larger piece of work than BL-B59, and it touches the fuse rather than the clustering,
so it is the user's call — not mine to substitute silently. §5 therefore plans the retention
term as asked, and §8 puts the option-2 alternative as decision 1.

**Cheaper narrowing available today, if the exposure above is judged acceptable:** Stage 1
alone (the mechanism, behaviour-neutral, §5) plus the `--group-trace` roster-shrink line makes
the defect *observable in a sortie* without changing behaviour — which is also what
[[BL-B50]]'s recheck condition asks for. That is a one-commit outcome and a real option.

---

## 4. Affected Modules / Files

- `body-layer/src/belief/groups.py` — `_cluster_contacts`: the prior-co-member branch (which
  Stage 3.5 already created and which today reads `effective_gap = gap  # prior co-members:
  ordinary rule, unchanged`) gains the retention discount. Docstring gains the measured
  asymmetry from §2b (relative term only, never the backstop) and the §2e lifetime caveat.
- `body-layer/src/belief/contacts.py` — **only if decision 2 goes to `max()`**:
  `fold_displacement_m`'s accumulation and its field docstring. Behaviour-affecting for
  merged Stage 3.5 admission as well, so its own commit and its own measurement.
- `body-layer/tests/test_groups.py` — new retention cases. **`test_the_eager_cap_still_chains_a_long_infantry_line`
  is Stage 0b's pinned evidence and is not modified.**
- `body-layer/ROADMAP/BL-B59.md` — pointer to this plan, the user's prioritisation, and the
  §2 reversal of its own framing.
- `body-layer/ROADMAP/BL-B58.md` — recheck note for §2e (the `+=` assumption, now measured).
- `body-layer/ROADMAP/BL-B50.md` — its recheck condition is dischargeable once this lands
  (§6).
- `body-layer/docs/STRUCTURE.md` — the `belief/groups.py` entry, per that file's remit.

---

## 5. Implementation Plan

> **Decision 1 REVISED — 2026-10-13. §5 is SUPERSEDED and was not implemented.** The user chose
> **[[BL-B58]] option 2** (bound the fold's displacement at source) over the retention term, which
> is what §3 above recommended and what §8 decision 1 put to him. The replacement is
> **`plans/bounded-fold-displacement/plan.md`**.
>
> **§1–§4 and §6–§10 stand and are the measurement base that justifies the replacement** — in
> particular §2a (the fold's displacement is the dominant term), §2b (the backstop never binds),
> §2d (*no* bounded retention factor works) and §2e (`fold_displacement_m` never retires). The
> option-2 plan re-measures §2e under the bound and finds the accumulator still never retires,
> only at a bounded rate.
>
> **§5 below is left in place deliberately, per `docs/PROCESS.md` "Superseding a decision"** — it
> is the design that was *rejected on the user's decision*, not a design that was wrong, and the
> ruled-out family in §2c/§2d is only legible beside it. Do not implement it.

Per `body-layer/CLAUDE.md`, *"Mechanism and calibration never share a commit."* Here the
mechanism and the **bound** are the two separable halves, because §2d showed the bound is
where all the behaviour lives.

**Stage 0 — record the §2e finding. No code.**
Recheck note on [[BL-B58]] that `+=` is now measured to never retire in a dense scene, with
the 132.7 → 239.0 m trace. *Acceptance:* the note exists and cites the probe. This is first
because it is a finding about merged code and must not be lost if the rest is deferred.

**Stage 1 — the mechanism, provably behaviour-neutral.**
Replace `_cluster_contacts`'s prior-co-member branch with
`effective_gap = max(0.0, gap - discount_i - discount_j)`, where `discount_*` is *wired to
`0.0`* in this stage. No threshold changes, no new constant.

*Acceptance test for this no-behaviour-change half, and it is a proof rather than a sample:*
`max(0.0, gap - 0.0 - 0.0) == gap` for every non-negative `gap`, so this stage is
algebraically the shipped predicate. The mechanical check is the **full suite unchanged** —
1697 passed / 4 xfailed at `1884775`, with `tests/test_groups.py` + `tests/test_callouts.py`
at 129 passed (both confirmed against this branch). Any single failure means the wiring is
wrong, not that a threshold moved.

**Stage 2 — the calibration: switch the discount on.**
`discount_* = contact.fold_displacement_m`, bounded per decision 2. One commit, one
attributable behaviour shift, and the acceptance table in §6 is its evidence.

**Stage 3 — tests and observability.**
The §6 table as `tests/test_groups.py` cases, plus a `--group-trace` field recording the
discount actually applied, so a sortie can distinguish "retained by the discount" from
"retained by the ordinary rule" without re-deriving it. Stage 3.5 set this precedent with
`fold_displacement_m` as provenance; a retention term that is invisible in the trace cannot
be audited against a real flight.

**Deliberately not staged here:** any re-tune of `GROUP_PROXIMITY_GAP_RATIO` or
`GROUP_REPORTING_EAGER_COHESION_CAP_M`. Both are stated assumptions awaiting a sortie
(`groups.py` module docstring), and moving one inside this fix would make two causes for one
behaviour shift.

---

## 6. Acceptance table — in Stage 3.5's style, invariants included

Rows **C–F** must be **byte-identical** to current behaviour. By §5 Stage 1's identity they are
identical by construction wherever no contact carries a fold budget, which is every row except
A and B.

| row | scene | current | required |
|---|---|---|---|
| **A** | incident 2, fold tick t=20 | `GROUP_1=[1,3]`, `CONTACT_2` evicted | **`GROUP_1=[1,2,3]`** |
| **B** | incident 2, t=30 persistence | `GROUP_1=[1,3]` | **`GROUP_1=[1,2,3]`**, and stable for ≥60 further ticks (§2d's 60/60) |
| **C** | **invariant** — Stage 0b's pinned 1,200 m chained infantry line (`test_the_eager_cap_still_chains_a_long_infantry_line`, unmodified) | chains | **IDENTICAL** |
| **D** | **invariant** — Stage 0a's three infantry at 30 m, eager cohesion | `[I1,I2,I3]` | **IDENTICAL** |
| **E** | **invariant** — Stage 3.5 row E: an un-folded armour contact genuinely joins an armour pair | `[A1,A2,A3]` | **IDENTICAL** (admission path, untouched) |
| **F** | **invariant** — Stage 3.5 row A/B: the absorption vetoes | `CONTACT_4` excluded, `air_defence=[]` | **IDENTICAL** — retention must not reopen absorption |
| **G** | a genuine departure: a continuously re-observed member drives away | evicts | **still evicts**, with the discount bounded by §8 decision 2 — this is the row the bound exists for |
| **H** | 60-tick repeat-fold run, membership transitions | 12 (eviction + downstream churn) | **0** (§2f) |
| **I** | [[BL-B50]]'s 2C fixture, `test_2c_transcript_fixture_renders_three_lines_not_seven` | three lines | **three lines, and stable across consecutive ticks** — discharges that entry's recheck condition |

Row **G** is the one with no measurement behind it yet, because this fixture harness cannot
produce a clean unambiguous re-observation in a scene dense enough for the relative term to
bind (§2e's structural reason; established by `scratchpad/probe_b59_axes.py`, which also found
that `_observation`'s docstring claim that `dwp_x`/`dwp_z` drive `last_position` is **stale** —
`ownship_x` drives the fused position, `dwp` drives gate matching only). **Stated assumption,
not a derived result**, and the first thing the Implementer should try to measure.

---

## 7. Invariant conflicts — checked, not assumed

- **DCS authoritative / no omniscience** — untouched. The discount reads
  `Contact.fold_displacement_m`, belief-derived provenance written by `ingest`, and no
  `derived_world_position` or DCS object id.
- **[[BL-B50]] (membership flipping on consecutive ticks)** — measured, and it pushes the
  **right** way: 0 transitions versus the baseline's 12 (§2d, §2f). This fix reduces flipping
  rather than adding a source of it, and §6 row I discharges that entry's explicit recheck
  condition.
- **`D5` continuity preference** — the discount *favours* continuity, which is `D5`'s own
  direction. The risk is the opposite one (over-retention), which is what decision 2 bounds.
- **`D6`'s air-defence carve-out** — not on this path, confirmed by reading rather than
  assumed: `D6` gates the fold's *candidate set* and `reconcile` phase 2; an evicted member is
  not a candidate for anything, and `Group.air_defence_composition` is recomputed fresh from
  actual current members every `reconcile()`.
- **Stage 3.5's admission gate** — untouched. §2f's disjoint-pair-sets argument is why.
- **`_pair_backstop_m` / the n≥3 over-merge floor** — untouched by design (§2b).
- **Mechanism/calibration commit split** — §5 Stages 1 and 2.

---

## 8. Decisions Requiring User Input

1. **Fix the symptom or the source?** §3's recommendation is [[BL-B58]] **option 2** — bound a
   single fold's position displacement — because it fixes *both* halves with one mechanism at
   the source and removes the need for a retention term at all. It is bigger, it touches the
   fuse rather than the clustering, and you declined it for the absorption half. **If you
   still prefer the retention term, §5 builds it and the plan stands as written.** My read:
   option 2 is the better engineering and the worse fit for the next-piece-of-work slot.
2. **The bound on the discount — and there is no good answer, which is the point.** §2d:
   every bound expressed as a fraction of the pair threshold fails within five ticks; only the
   unbounded discount works, and unbounded means a repeatedly-folded pair's combined discount
   reaches 498.8 m by t=80, above the 500 m eager cap. Three ways out, none free:
   - **(a) Unbounded.** Correct in every probe, 0 transitions. Accepts a latent
     over-retention runaway with no measured symptom. Zero new constants.
   - **(b) `max()` instead of `+=`** on `fold_displacement_m` — "the worst single unretired
     fold" rather than the sum. Bounds the budget at one fold's displacement (132.7 m here,
     since later folds are smaller) with no new constant. **But it changes merged Stage 3.5
     admission behaviour too**, so it needs its own commit and its own re-measurement of
     Stage 3.5's six-row table. My preference of the three.
   - **(c) A fraction of the pair threshold.** Measured insufficient (§2d). Listed only so the
     rejection is on the record.
3. **Is §3's narrowing enough for now?** Stage 0 + Stage 1 alone (the finding recorded, the
   mechanism wired behaviour-neutral, the trace line) makes the defect observable in a sortie
   and discharges [[BL-B50]]'s recheck condition, without changing behaviour or minting a
   constant. Given the exposure is visible and partially bounded, flying it before calibrating
   it is a defensible order — and it is the order this project's own constants
   (`GROUP_PROXIMITY_GAP_RATIO`, the eager cap) are already waiting on.

---

## 9. Risks & Unknowns

- **Row G is unmeasured** (§6). The genuine-departure case is the one the bound exists for and
  the harness could not produce it. If it turns out the unbounded discount *does* retain a
  departing member, decision 2(a) is off the table and 2(b) becomes necessary rather than
  preferred.
- **§2e's finding is about merged code.** Stage 3.5's admission penalty grows monotonically
  with no retirement. No symptom is attached to it yet; it may surface as a genuine joiner
  being refused admission to a group it belongs in, which would read as under-merging and be
  attributed to the wrong mechanism.
- **Every number here comes from one geometry** — probe 2's three-infantry-plus-ZSU scene, at
  the fixture's `_FALLBACK_UNCERTAINTY_RADIUS_M` (300 m) uncertainty path that
  `association_over_time.py`'s own comment says "should not happen in production."
  [[BL-B58]]'s entry already argues at length that the *mechanism* is not confined to that
  artifact while the fixture's amplification at these close ranges is. The same caveat applies
  to this plan's magnitudes: the ~133 m fold displacement is fixture-amplified; the shape is
  not.
- **No sortie has exercised this path.** Both cohesion constants the retention term interacts
  with are stated assumptions awaiting flown data.
- **O(n²) cost unchanged** — one `min`, one subtraction and one `max` per prior-co-member edge,
  inside a loop that already computes a distance and a backstop per edge. No new allocation,
  no new pass. Stage 3.5's own performance note covers the shape.

---

## 10. The milestone-completion question (root `CLAUDE.md`)

**Does this change what comes next, or invalidate a downstream assumption?**

Yes, in one direction that matters. **`BL-14` (attack run) and `BL-8` both build on group
membership**, and §2a establishes that membership can be wrong *because the member positions
are wrong*, not because clustering mis-reads them. A retention term makes the roster stable
without making the positions right — so `BL-14`'s alignment geometry would be computed from
`CONTACT_1` at x=868 when the unit is at x=1000, a 132 m error that no amount of membership
stability removes. **If `BL-14` consumes member positions rather than only the roster, decision
1's option 2 (bound the fold at source) stops being the more expensive alternative and becomes
the prerequisite.** That is worth settling before `BL-14` is planned, not during.

Narrower, and settled: [[BL-B50]]'s recheck condition becomes dischargeable (§6 row I), and
[[BL-B57]] is unaffected — it widens a growth-rate lookup, a different `profile_for` consumer
from the cohesion path.
