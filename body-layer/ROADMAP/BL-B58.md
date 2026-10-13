# BL-B58 — A within-group fold's position drift can widen a cluster enough to absorb an unrelated contact

> **Option 2 chosen by the user, 2026-10-13 — the option declined for the absorption half is now
> the fix for both halves.** *"Bound how far a single fold-driven `Contact.record` call may move a
> fused position"*, the option listed below and passed over in favour of option 3 (Stage 3.5's
> admission gate). Plan: **`plans/bounded-fold-displacement/plan.md`**, which closes [[BL-B59]]
> at the same time.
>
> **Three measurements that bear on this stage's own shipped code**
> (`plans/bounded-fold-displacement/scratchpad/`):
>
> 1. **At a bound of `plausible_speed_mps × elapsed`, Stage 3.5's gate becomes a no-op in
>    incident 2** — the absorbing `CONTACT_1`–`CONTACT_4` edge goes **63.8 → 155.0 m** against its
>    78.0 m backstop, so the ordinary rule already refuses it and the roster is the same with the
>    admission term neutralised. At a 3× looser bound the edge returns to 75.5 m and the gate is
>    **load-bearing again**. **The gate and `fold_displacement_m` therefore stay**: they are the
>    safety net for a bound derived from `_PLAUSIBLE_SPEED_MPS`, which is stated assumptions.
> 2. **The accumulator recheck below is only half-discharged.** Under the bound
>    `fold_displacement_m` still **never resets** — 40.0 m at t=20 → 160.0 m by t=80 — it merely
>    grows at a physically plausible rate instead of an arbitrary one. The `+=` → `max()` question
>    survives as that plan's Stage 3, with its own commit and its own re-measurement, exactly as
>    this note already required.
> 3. **This stage's six-row table re-measured**: rows C–F are identical *by construction* (they
>    feed `_cluster_contacts` synthetic positions and hand-set budgets, which a change confined to
>    `contacts.py`'s fold branch cannot reach); row B is the no-op above; row A's 2C fixture test
>    passes unchanged. Mechanical backing: the whole suite under the bound is **1696 passed / 1
>    failed**, the one failure being this stage's provenance test, whose fold is entirely at
>    `t_sim=0.0` (elapsed 0 ⇒ bound 0).

> **Recheck note added 2026-10-13 ([[BL-B59]]'s Architect pass): the `+=` accumulation this
> stage shipped is now measured, and it never retires.** This entry's own Risks line recorded
> accumulate-not-replace as *"a stated assumption, not measured against a real repeat-fold
> incident."* Measured over 60 ticks of continued re-observation in probe 2's geometry
> (`plans/group-retention-hysteresis/scratchpad/probe_b59_lifetime.py`):
> `CONTACT_1.fold_displacement_m` goes **132.7 → 172.5 → 192.3 → … → 239.0 m** (`CONTACT_3`
> reaches 259.8 m) and **resets zero times**. The reason is structural rather than incidental:
> in a scene dense enough for `_cluster_contacts`'s relative term to bind, every
> re-observation has ≥2 passing gate candidates, so every re-observation is *itself* ambiguous
> and folds again — the unambiguous resolution at `contacts.py:1071`/`:1086` that would retire
> the budget never arrives. `Contact.position.radius_m()` floors at 120.0 m, so covariance
> supplies no retiring bound either.
>
> **Consequence for this stage's own gate, not just for [[BL-B59]]:** the *admission* penalty
> grows monotonically too, so Stage 3.5 becomes progressively more exclusionary for a
> repeatedly-folded contact. **No live symptom is attached to this yet** — it would surface as
> a genuine joiner refused admission to a group it belongs in, which reads as under-merging
> and would plausibly be attributed to the wrong mechanism. Replacing `+=` with `max()` ("the
> worst single unretired fold") is decision 2(b) of
> `plans/group-retention-hysteresis/plan.md`; it would change this stage's behaviour, so it
> needs its own commit and a re-measurement of this stage's six-row table.

> **Implemented, Reviewer-APPROVED (round 7) and DoD-PASSED, 2026-10-12, on
> `feature/bl12-group-contact-identity` (BL-12 Stage 3.5).** Three commits: `Contact.fold_displacement_m` (provenance,
> behaviour-neutral), the admission gate itself (`_cluster_contacts` gains `prior_rosters`), and the
> 2C fixture rewrite. Re-run against the real pipeline, not just the isolated predicate: probe 2
> (`plans/group-cohesion-admission-gate/scratchpad/probe_b58_second_incident.py`) now shows
> `GROUP_1 members=['CONTACT_1', 'CONTACT_3']`, `air_defence=[]` after the fold -- the ZSU-23-4
> (`CONTACT_4`) is no longer absorbed. Full numbers: `plans/group-cohesion-admission-gate/
> implementation.md`. The eviction half this plan's own point 3 names (`CONTACT_2` dropping out in
> the same probe run) is **[[BL-B59]]**, filed separately and deliberately not fixed here.

> **Decided and planned, 2026-10-12.** The user chose **option 3 — fix at source in clustering** over
> options 1 and 2, because *"group membership is what the rest of BL-12 and BL-14 build on — a wrong
> member poisons heading, composition and attack-run alignment, not just one spoken line."* The plan
> is **`plans/group-cohesion-admission-gate/plan.md`** (BL-12 Stage 3.5, blocking Stage 4; pointer
> amendment **A9** in `plans/group-contact-identity/plan.md`).
>
> **Three things that Architect pass measured, which correct this entry below rather than confirm it:**
>
> 1. **This entry's own option-3 sketch is a no-op.** The absorbing edge *already clears*
>    `_pair_backstop_m` — 81.9 m against 88.0 m. The cause is a **219 m single-tick fold
>    displacement** of the folded-onto contact, and it **persists**, so re-checking the existing
>    pairwise test (or any tick-local displacement test) cannot close the gap. The gate in the plan
>    carries **provenance** (`Contact.fold_displacement_m`) instead, and introduces **no new
>    constant**.
> 2. **Both open sub-questions are now closed by reproduction, not deferred.** A clean second
>    independent incident (different geometry and class mix, no 2C fixture) and the same absorption
>    **with a ZSU-23-4 as the absorbed member** — `air_defence_composition` goes `[]` →
>    `[('OP_SPAAG', 1)]`, persistently.
> 3. **A sibling defect was found in the same run: the drift also *evicts* a real member**, by
>    shifting the median nearest-neighbour gap and tightening the relative threshold. That is the
>    direction that can **suppress** an air-defence report, and it is **[[BL-B59]]** — deliberately
>    out of Stage 3.5's scope.
>
> The cost line below ("the most expensive") is corrected in that plan's effort/value section: the
> fix is **not materially more expensive, but differently shaped** — one more module (`contacts.py`,
> for the provenance field), no new calibration constant, no new persistent store state.

- [x] **BL-B58 — [[BL-12]] Stage 3's within-group ambiguity fold (D5 at contact grain) moves a
  contact's fused position toward the folded percept (`fold_position` is a real weighted fuse, not
  a no-op); the next `tick()`'s position-only cluster can widen enough to absorb a previously
  separate, correctly-identified contact into the same `Group` — not itself an ambiguous candidate
  for anything, and not individually failing any gate. FIXED by the Stage 3.5 admission gate.**
  #status/done Found by the Implementer
  during Stage 3 (2026-10-12), via a plan-unlisted test (`test_callouts.py`'s 2C fixture), confirmed
  and characterised by the Reviewer the same stage round.

  **Reproduced independently, not just read off the implementer's log.** Running the fixture
  directly: at t=12 a 2-o'clock infantry pair folds onto `GROUP_1`'s two nearest members
  (`CONTACT_1`/`CONTACT_2`, 12/1-o'clock infantry inflated 12s unseen) instead of founding
  `CONTACT_6`/`CONTACT_7` — accepted failure mode 2 (undercount), per the plan's own Q5. The fold's
  position drift then pulls `CONTACT_4` (a correctly-identified BTR-70, never itself a candidate)
  into the same cluster on the very next `reconcile()`, via `_cluster_contacts`'s ordinary
  single-link union-find over fused positions — not via Stage 1's displacement test or D6's
  identity-matching gate, neither of which this path goes through (the absorbed cluster already
  overlaps 3/4 members with the existing `Group`, so it resolves via phase 1's plain
  highest-overlap match, which carries no class/air-defence/displacement check at all).

  **Bounded within one incident, not an unbounded single-tick runaway — measured, not argued.**
  Continuing the fixture for ten further polls with fresh, nearby infantry percepts: each one folds
  onto the existing group (repeating the undercount) and nudges the folded-onto contact's position,
  but `centroid_uncertainty_m` stabilises (258 m -> 242 m) and group membership does not keep
  growing past the four members the first incident produced — re-observation shrinks covariance
  faster than drift widens it, once the group *is* being seen. The risk is **repeat-incident**, not
  single-tick exponential: each time a group's members go unobserved long enough for covariance to
  inflate (ordinary, e.g. masked by terrain or out of the FOV wedge) *and* an ambiguous percept
  happens to land nearby when visibility returns, one more absorption of this shape can occur,
  independently, on its own schedule.

  **Significantly amplified by this fixture's own fallback, not a pure artifact either.** The
  fixture's observations declare no `position_uncertainty`, so both sides of the gate fall back to
  the isotropic `_FALLBACK_UNCERTAINTY_RADIUS_M` (300 m) — a path `association_over_time.py`'s own
  comment says "should not happen in production," since both real sources (naked-eye, scope/hybrid)
  declare their own. At the fixture's short ranges (280-500 m), real declared naked-eye uncertainty
  (`naked_eye_sigma_m`, `BEARING_SIGMA_DEG=3.0`, `RANGE_FRACTIONAL_SIGMA=0.17`) is far tighter
  (~50-90 m one-sided) than the 300 m fallback, so this fixture's absorption at 500-900 m would not
  reproduce at these ranges with a real declared uncertainty. **But at the ranges this project's own
  measurements already cite as typical naked-eye operating range** (`plans/
  contact-duplication-ambiguity-runaway/debug.md`: ~590 m one-sided gate at 1200 m range; `[[BL-12]]`
  roadmap entry: 600 m gate after 30 s unseen), declared uncertainty alone is already comparable to
  or wider than this fixture's fallback — so the mechanism (fold -> drift -> wider cluster -> absorbs
  an unrelated, previously-separate contact) is not confined to the fixture's artifact; it would
  recur at realistic mid-range engagement distances with entirely real, declared uncertainty, just
  without the fixture's own extra ~3x amplification at *these particular* close ranges.

  **D6's own gate is unaffected — checked directly, not assumed.** The absorption happens through
  `reconcile`'s phase 1 (overlap match) and `_cluster_contacts` (position-only single-link), neither
  of which is a resolution path D6 or amendment A3 touch; D6's hard air-defence-confirmation test
  (Stage 1 test 3) only gates phase 2 (property match — re-identifying a cluster with *zero* member
  overlap against a remembered group), which this path never reaches, and
  `Group.air_defence_composition` is recomputed fresh from the matched cluster's actual current
  members every `reconcile()` call regardless of phase (`groups.py` phase 1/3 construction, read
  directly) — so it is never stale or carried over. The practical risk is therefore not a stale or
  bypassed air-defence flag; it is that **cluster *membership itself* can be corrupted by this
  drift**, in either direction — an air-defence-classified contact could be swept into (or a
  previously-included one swept out of) a group via spurious position drift unrelated to either
  unit's real movement, which would then correctly but misleadingly update that group's reported
  `air_defence_composition` to match the corrupted membership. Not reproduced with an actual
  air-defence contact in this round (time-boxed); flagged here as the concrete next check before
  this is closed.

  **None of the plan's three named Stage 3 failure modes individually describes this.** Failure mode
  1 ("within-group record swapping... the group-level answer stays correct") is the one that comes
  closest and explicitly does not cover it: here the group-level answer becomes wrong — a correctly
  individually-identified unit gets reported as part of a group it does not belong in.

  **Options, costs, or-mark for the user (orchestrator: put this to them, no recommendation forced
  here beyond the relative cost read):**

  1. **Accept as-is for Stage 3; widen [[BL-12]] Stage 4's planned speech-time extent guard** (plan
     amendment A6: "do not speak a heading or a single bearing for a group wider than one believable
     bearing") **to also suppress composition-based disclosure lines** (not just heading/bearing)
     once a group's extent exceeds the same bound. Cheapest — Stage 4 is not built yet, so this is a
     scope addition to unbuilt work, not a new mechanism on a merged stage. Does not fix the
     underlying membership corruption, only stops it from being *spoken* past a width bound; the
     wrongly-grouped contact's own individual disclosure (if it has one) is unaffected.
  2. **Bound how far a single fold-driven `Contact.record` call may move a fused position**,
     independent of the covariance-driven fuse. New mechanism, new calibration question (what bound,
     relative to what), delays nothing already merged but is real design work the plan did not
     scope and the implementer correctly declined to add unprompted.
  3. **Require cohesion to be re-checked before a cluster absorbs a member via plain overlap-match**,
     e.g. excluding a newly-added member whose own gap to the pre-existing cluster fails the same
     pair backstop `_cluster_contacts` already applies pairwise within one cluster-formation pass.
     Most architecturally correct (closes the gap at its source, `_cluster_contacts`/`reconcile`
     rather than downstream at speech time) and the most expensive — touches the clustering
     mechanism this whole milestone's Stage 0 already revised once, and needs its own review pass.

  Related: [[BL-12]] Stage 3 (where this was found), [[BL-B50]] (membership flipping on consecutive
  ticks — a sibling instability in the same reconcile machinery), amendment A6 in `plans/
  group-contact-identity/plan.md` (the Stage 4 extent guard option 1 would widen).
