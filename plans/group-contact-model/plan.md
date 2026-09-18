### Goal

Give `belief.contacts.Contact` a *cardinality* belief and a *composition* belief — both refinable,
both contradictable — and move the honest resolution boundary into the perception channel's own
clustering, so twelve vehicles at 9 km become one contact that says "a group of about ten" rather
than one contact that permanently says "a truck".

---

### The reframing this plan rests on

The observed defect and the requested feature have one root cause, and it is not in `belief/`:

> **The pipeline emits one `Observation` per DCS `object_id`, then asks `belief/` to guess which
> observations are the same object. At 9 km that guess is unanswerable, and `ContactStore.ingest`'s
> structure forces a binary answer (merge / new) with no way back.**

Both historical fixes tried to make the guess better — BL-2.6 widened the gate, the reverted
presence-tier veto narrowed it. Neither can succeed, because the question itself is ill-posed at
that range. `plans/contact-merge-undercount/debug.md`'s cascade finding is the proof: once one
false merge happens, the "2+ candidates → found a new contact" safety net can never fire again for
that cluster.

The answer is to stop asking. `NakedEyePerceptionSource` already quantises every object to a clock
bucket (30°) and an `OP_D*` range bucket, and `association_over_time._naked_eye_uncertainty_m`
already computes, honestly and from those bucket widths, the radius inside which this channel
*cannot* distinguish two positions (~2.5 km at 9 km). That radius is the honest resolution limit.
Objects inside it are not separately resolvable — so they should not leave the perception layer as
separate reports.

**A `Contact` therefore becomes a belief about the occupants of one resolution cluster, not about
one object.** Cardinality is how many occupants; composition is what kinds. Both are beliefs
because both are perceived through the same degrading channel as class already is.

#### This is not a new idea in this codebase — three existing artefacts point at it

1. `perception/naked_eye_source.py`'s module docstring, **Scope limit (plan Decision #5)**:
   Finding 2's count/formation buckets `OP_1UNIT`…`OP_MORETHAN15UNITS` / `OP_SINGLE`/`OP_GROUP`
   "describe an *aggregate* callout across a cluster of objects, which this channel's per-object-id
   emission model doesn't produce without first building object clustering — out of scope for v1."
   This plan is v2 of exactly that deferral.
2. `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` line 442
   and 448: **ED's own Petrovich already reports a bucketed count per clock direction.** The user's
   observed live callout `9 CONTACTS, 1 O'CLOCK` decomposes to `OP_8TO10UNITS` + `OP_A1H`. The
   cardinality ladder does not need inventing; it is already the vocabulary this channel models,
   and ED's designers already decided a bucketed count is what a crew member can honestly perceive.
3. `belief/speech.py`'s module docstring already names the gap: *"**No contact clustering.**
   `render_contact_report` reports one contact at a time. §3.6's multi-contact `contact_group`
   worked example (composition counts) needs data this codebase does not track yet."*

#### Where the honest boundary sits (requirement 6), stated as an invariant

> **Belief never holds a position for anything finer than a cluster, and never holds a per-member
> position at all.** Composition answers "what kinds, and how many"; it never answers "where is
> each one". The cluster radius is the channel's own `uncertainty_radius_m` — the same number the
> spatial gate already budgets — so the model's resolution and the channel's resolution are the
> same number by construction, not by a tuned constant that can drift apart from it.

At 9 km that yields exactly one position, one coarse count bucket, no member positions. At 500 m
the same mechanism yields several clusters with small exact counts. The progression the user
described falls out of the channel closing range, which is what should drive it.

---

### Affected Modules / Files

**New**

- `body-layer/src/belief/cardinality.py` — `CountBucket` ladder (ED's `OP_*UNITS` vocabulary),
  `CardinalityBelief`, `fold_cardinality`, `CARDINALITY_CONTRADICTION_LOCKOUT_S`. Deliberately a
  sibling of `classification.py`, mirroring its structure line for line.
- `body-layer/src/belief/composition.py` — `MemberClaim`, `CompositionBelief`,
  `fold_composition`. Contains *no* new fusion logic: it matches claims and delegates to
  `classification.fold_classification` and `cardinality.fold_cardinality`.
- `body-layer/src/perception/clustering.py` — groups visible candidates into resolution clusters
  and derives each cluster's count bucket and composition multiset. Pure, testable, no I/O.

**Changed**

- `perception/naked_eye_source.py` — emits one `Observation` per cluster instead of one per
  object; derives cluster-level `continues_observation_id` by majority object overlap;
  `NAKED_EYE_MAX_NEW_PER_POLL` re-reads as a per-cluster cap.
- `perception/source.py` — `Observation` gains `count_bucket: str | None` and
  `composition: tuple[tuple[str, int, int], ...]` (raw, level, n), both perceived metadata with
  the same justification `classification_level` already carries.
- `belief/percept.py` — carries both fields through `percept_of` unchanged; the boundary argument
  in that module's docstring applies verbatim and needs restating, not reinventing.
- `belief/contacts.py` — `Contact` gains `cardinality: CardinalityBelief`,
  `cardinality_lockout_until_sim`, `composition: CompositionBelief`,
  `last_emitted_cardinality`; `record` folds both; `from_percept` seeds both.
- `belief/classification.py` — **unchanged.** The fold rule generalises as-is (see below).
- `belief/association_over_time.py` — the presence-tier veto added by the interim fix is
  **removed** here (Stage 2); the gate itself is otherwise untouched.
- `belief/decay.py` — one new pure function `cardinality_confidence_at`, reusing
  `IDENTITY_HALF_LIFE_S`. **No new constant** (see "Existing mechanisms checked" below).
- `belief/events.py` — one new `EventKind`, `CONTACT_CARDINALITY_CHANGED`; existing
  `EVENT_COOLDOWN_S` machinery reused unchanged.
- `belief/tools.py` — `facts["cardinality"]` and `facts["composition"]`, absent-when-unknown;
  `get_situation`'s `contact_counts` gains an `estimated_units` figure.
- `belief/speech.py` — count clause; `_OP_CLASS_DISPLAY["OP_GROUPSOMETHING"]` collision resolved.
- `belief/console.py` — `_SHOW_FACT_KEYS` gains the two new keys.
- `belief/crew_console.py`, `belief/escalation.py`, `belief/mission_phase.py` — small; see stages.
- `body-layer/tests/test_calibration_cluster_merge_undercount.py` — its assertions are the
  characterisation of the *defect*; they get replaced, per its own docstring's instruction.
- `body-layer/tests/test_mock_flight_chain.py::test_two_real_objects_stay_two_contacts` — the
  strict xfail becomes a real assertion.
- `body-layer/ROADMAP.md`, `plans/body-layer/plan.md` §3.6 (see Decisions).

---

### Existing mechanisms checked before designing new ones

Per the Architect process step 3a, I read the modules this plan edits for constants and logic
already governing cardinality, decay, and contradiction, rather than trusting the framing:

- `decay.py`'s **full constant inventory** — `IDENTITY_HALF_LIFE_S` 600, `POSITION_HALF_LIFE_S` 30,
  `MOTION_HALF_LIFE_S` 60 (declared, unconsumed), `GENERAL_AREA_HALF_LIFE_S` 180 (declared,
  unconsumed), `OBSERVED_WINDOW_S` 5, `LOST_THRESHOLD_S` 120, `OBJECT_ID_MEMORY_S` = 600.
  **Cardinality confidence reuses `IDENTITY_HALF_LIFE_S`** — how many things are there is an
  identity claim, and that module's docstring already insists on one table. The count *interval*
  never decays, exactly as `ClassificationBelief.level` never decays.
- `classification.py`'s `CLASSIFICATION_CONTRADICTION_LOCKOUT_S` = 30 — the re-promotion lockout.
  Cardinality gets its own `CARDINALITY_CONTRADICTION_LOCKOUT_S`, **defaulting to the same value
  but declared separately**, following the documented precedent `OBJECT_ID_MEMORY_S` set for
  "conceptually distinct claims that happen to share a value for now, not permanently coupled".
- `events.py`'s `EVENT_COOLDOWN_S` = 15, per-contact-per-kind via `Contact.last_event_emitted_sim`.
  The new event kind uses it unchanged; no second suppression mechanism.
- `association_over_time.py`'s `SCOPE_UNCERTAINTY_M` 300 / `GATE_GROWTH_RATE_MPS` 20 and
  `_naked_eye_uncertainty_m` — the cluster radius **is** `_naked_eye_uncertainty_m`, reused, not a
  new tunable.

Net: **one new constant** in the whole design (`CARDINALITY_CONTRADICTION_LOCKOUT_S`), plus the
Stage 3 calibration table.

---

### Design

#### 1. Cardinality as a belief (requirement 1)

`CountBucket` is a named closed interval over ED's own vocabulary:

```
OP_1UNIT (1,1)  OP_2UNITS (2,2)  OP_3UNITS (3,3)  OP_TO5UNITS (4,5)
OP_5TO7UNITS (5,7)  OP_8TO10UNITS (8,10)  OP_ABOUT15UNITS (11,15)  OP_MORETHAN15UNITS (16,inf)
```

plus two coarse rungs that are not counts but shapes: `UNKNOWN` (0, inf) and `OP_GROUP` (2, inf) —
"several somethings". `CardinalityBelief(lo, hi, confidence, established_sim)` mirrors
`ClassificationBelief` field for field.

`fold_cardinality(held, incoming, now_sim, lockout_until_sim)` is the direct analogue of
`fold_classification`, with interval containment standing in for lattice depth:

| case | outcome |
|---|---|
| incoming strictly narrower, intervals intersect | **refine** → adopt the intersection |
| identical interval | **reinforce** → confidence step toward the ceiling |
| incoming wider, intervals intersect | **hold** → the held claim survives untouched |
| intervals disjoint ("three, now five") | **contradict** → collapse to the interval *hull*, confidence floored to the lower of the two, lockout armed |

The hull is the cardinality lattice's "deepest common ancestor": the smallest thing still true of
both readings. `UNKNOWN` is its root, reachable only when the hull spans everything. The lockout
prevents the same contradict → collapse → refine → contradict spam `classification.py` documents.

**The one honest asymmetry, stated rather than papered over:** counts legitimately *change* — a
vehicle drives off, one is destroyed. This model cannot tell a perception error from a world
change, and it should not pretend to. Both are handled identically (widen, then re-narrow after
lockout onto whatever the world now is), which converges correctly in both cases and costs only a
lockout's worth of hedged reporting. Modelling arrivals and departures explicitly is the expensive
thing this deliberately does not do.

#### 2. Composition as counts-per-claim, not identified members (requirement 2)

**Decision: members have no stable identity. A member is a `(ClassificationBelief, CardinalityBelief)`
pair, and two member claims are "the same member" iff their classification values are equal or one
is the other's lattice ancestor (`parent_class_of`).**

This is the load-bearing simplification, and it is the honest one: at any range where a group
exists as a group, you cannot tell which of three identical infantrymen is which. Claiming stable
member identity would be precisely the omniscience the project exists to prevent, *and* it would
require solving a within-cluster association problem — the same problem that just failed at the
cluster level, now harder and with less evidence.

`fold_composition(held, incoming, now_sim)`:

1. Match each incoming claim to a held claim by lattice ancestry, deepest match first (an incoming
   `TYPE` claim `T-72` matches a held `CLASS` claim `OP_ARMORED`, since `parent_class_of("T-72")`
   is `OP_ARMORED`).
2. For each match: `fold_classification` on the claim, `fold_cardinality` on the count.
   **The debugger's hypothesis holds — this is where it pays off.** No new fusion logic exists in
   this module; per-member contradiction and retraction (requirement 3) is `fold_classification`
   applied per member, with the lockout deadline stored on the `MemberClaim` rather than on the
   contact.
3. Unmatched incoming claims are appended.
4. Unmatched held claims **hold** — the same "lower specificity holds" posture the lattice already
   takes. They are never silently deleted.
5. **The remainder is derived, never stored:**
   `remainder_lo = max(0, cardinality.lo - sum(member.count.lo))`. "Three tanks and something else"
   falls out for free from a group of five with one `OP_ARMORED×3` claim. That it costs nothing is
   the strongest evidence the shape is right.

**Over-subscription is the retraction rule.** "Not IFVs, but Shilka and two MLRS" arrives as
`{SPAAG×1, MLRS×2}` against a held `{IFV×3}` with no ancestry match, which rule 3 alone would turn
into six members in a group of three. So: after folding, if `sum(member.count.lo) > cardinality.hi`,
collapse held claims — lowest `classification_confidence_at` first — to the presence root (they
become unresolved remainder) until the totals are consistent, and arm the composition lockout. This
encodes "when the totals cannot both be true, the newer and more confident reading wins", which is
what the user's example describes.

#### 3. Splitting — the largest blast radius, argued explicitly (requirement 4)

**Recommendation: there is no structural split. `Contact` ids are never deleted, never re-keyed,
and never made children of anything. Clusters re-home onto existing contacts by majority object
overlap, and the id follows the majority.**

Mechanism: when a cluster divides, the child carrying most of the parent cluster's objects gets a
`continues_observation_id` pointing at the parent's last report, so
`ContactStore._resolve_continuity` folds it onto the existing contact — whose cardinality then
*narrows* (a legitimate refine, or a contradiction if disjoint). The minority child arrives with
`continues_observation_id=None` and founds a new contact through the existing gate. Nothing is
deleted. `CONTACT_CARDINALITY_CHANGED` fires on the parent; `CONTACT_DETECTED` fires on the child.

Answering the sub-questions directly: **the group's id survives on the majority child. History,
attention mark, and any `PendingIntent` referencing it stay valid and keep pointing at a live
contact.** The new child starts at `attention="normal"` and an empty event-cooldown dict.

The two alternatives, and why not:

- **(B) A group container with `member_ids` and child `Contact`s** — this is what
  `plans/body-layer/plan.md` §3.6's `contact_group` sketch describes, so it deserves a real answer
  rather than a dismissal. It introduces a second contact kind that all thirteen consumers must
  handle, a parallel shape on the tool surface, and — decisively — it presupposes the members were
  *separately resolved into `C31`/`C32`/`C33` first*. That presupposition is true at 500 m and
  false at 9 km, which is exactly the case this work exists to fix. §3.6 is a *presentation and
  association* layer over already-resolved contacts; this plan is a *perception-limit* aggregate.
  They are compatible, and §3.6 remains buildable later as a view over contacts (BL-8/brain), but
  building it now would answer the wrong question at permanent structural cost.
- **(A) Delete the parent and respawn two children** — `contacts.py` states outright that the
  correlation index is "never pruned or re-keyed". The survey found five surfaces that would dangle:
  `ContactStore._events[].contact_id` (append-only, unprunable — unacknowledged events for a dead
  contact would re-surface through `poll_events` forever),
  `_observation_id_to_contact_id`, `PendingIntent.result_contact_ids` (terminal, never revisited),
  `WorldEnrichmentCache._cache` (a leak), and `PartialParse.referenced_contact_id`. Deleting would
  also break the event log's replay determinism. Not worth it for a distinction the channel cannot
  maintain anyway.

Option (C)'s honest cost, to be documented on the fields rather than hidden: the surviving
contact's identity is arbitrary among the children (majority, ties broken by lowest object id — so
deterministic, but physically meaningless), and its `first_seen_sim`/`sighting_spans` describe the
*group's* history, not the survivor's.

#### 4. Merging into an existing group (requirement 5)

Falls out of the same mechanism with **zero new code**, which is the strongest argument for (C):
two clusters becoming one produce a single report whose majority overlap resolves onto one of the
two contacts; its cardinality *widens* (a contradiction → hull, correctly hedged). The other
contact is not deleted — it stops being observed and decays `tracked → estimated → lost` on the
existing ladder. That is exactly right epistemically: the crew did not watch it vanish, they
stopped seeing it separately.

#### 5. The `OP_GROUPSOMETHING` collision, resolved as a side effect

`speech._OP_CLASS_DISPLAY` maps `OP_GROUPSOMETHING` → `"group"`, but that token is
`classification.PRESENCE_CLASS` — "something is there", not a count. Today that is a latent
mis-statement. With cardinality present, presence level speaks **"something"** when the count is
`OP_1UNIT` or `UNKNOWN` and **"a group"** / **"several"** when the count bucket is plural. The
count belief is what disambiguates the one token ED gave us for both meanings.

---

### Effort / Value check

This is a large change to the core of the belief layer driven by one sortie, so the check applies.
Verdict: **build stages 1–4, build stage 5, do not ever build member identity.**

- **Stages 1–3 (cardinality + clustering + calibration) are roughly a third of the total cost and
  deliver most of the value.** They fix the observed defect at its actual cause, produce "a group
  of about six, 11 o'clock, 2 kilometres", and stop the honest coarse claim from hardening. If the
  user wants to stop anywhere, stop here.
- **Stage 5 (composition) is worth its cost specifically because the fold machinery already exists.**
  The marginal build is the ancestry matching rule and the over-subscription retraction — perhaps a
  fifth of what it would cost if `fold_classification` were not already there. Were it not, I would
  recommend deferring it.
- **Stable per-member identity, per-member positions, and members migrating between groups are
  disproportionately expensive and should never be built.** They require a within-cluster
  association problem the channel cannot support, they multiply the blast radius across every
  consumer, and — checked against the user's own progression — *every step of it is expressible as
  counts-per-claim*. "3 T-72, 1 BMP-2, 2 GRAD" is a multiset. Nothing in the target behaviour asks
  which T-72 is which.
- **Should any of it wait for a brain layer? No.** `speech.py` and `crew_console.py` consume this
  today and Petrovich already talks; the brain (`plans/brain-layer/plan.md`) is a plan, not code.
  There is a live consumer, so the feedback loop that would validate the calibration exists now.
  Deferring would mean flying more sorties against a model known to be wrong.

---

### The interim fix: stepping stone or throwaway?

**Throwaway at the mechanism level; load-bearing at the knowledge level. It will be reverted by
Stage 2, and the plan is built assuming that.** Not re-litigating the decision to land it — this is
how the two fit together.

Under Stage 2 the naked-eye channel emits one presence-tier report *per cluster*, and that report
must be allowed to fold onto the cluster's existing contact. A blanket "a `PRESENCE`-level percept
never passes the gate" veto would then found a fresh contact every poll for any cluster whose
continuity misses — strictly worse than today. So the veto's two lines in
`association_over_time.passes_gate` come out in Stage 2. What survives the redesign is the
*observation* the veto encodes — a report carrying zero class evidence must not make a confident
1:1 identity claim — which Stage 2 honours by not making a 1:1 claim at all.

Three things to do so the interim change costs as little as possible when it is removed:

1. Keep it to the two lines in `passes_gate`. No new module, no new constant.
2. **Do not add tests asserting "presence percepts never merge" as desired behaviour**, beyond
   flipping `test_two_real_objects_stay_two_contacts`. Any such test becomes a wrong pin in Stage 2.
3. Put a one-line comment naming this plan's Stage 2 as its removal point.

And the honest warning the user should have going in: **it trades under-count for over-count.** At
9 km twelve objects will found twelve contacts at twelve distinct positions, which is the
omniscience failure in the other direction. It is the better error to have temporarily — visible,
self-correcting as range closes, and not permanent — but it is an error. It also does **nothing**
for same-class clusters: three AK infantry within 50 m all resolve to `OP_INFANTRY` and still pass
each other's gate, confirmed by the debugger against the reproduction's `INFANTRY_1..3`.

---

### Implementation Plan

Every stage is independently mergeable and leaves the suite green. Mechanism and calibration are
deliberately in separate commits, per this project's own history.

**Stage 0 — presence-tier merge veto (already decided, lands first, separate branch).**
Not part of this plan's scope; constrained as above.

**Stage 1 — `belief/cardinality.py`, mechanism only. No behaviour change.**
The ladder, `CardinalityBelief`, `fold_cardinality`, the lockout constant, and
`decay.cardinality_confidence_at`. `Contact` gains `cardinality` and `cardinality_lockout_until_sim`,
seeded to `OP_1UNIT` at founding so every existing test observes identical behaviour. Unit tests
for all four fold outcomes plus the lockout. **Merge criterion: the full suite passes untouched.**

**Stage 2 — perception clustering, count emission, veto removal. The stage that fixes the defect.**
`perception/clustering.py`; `Observation`/`Percept` gain `count_bucket`; `naked_eye_source` emits
per cluster with majority-overlap continuity; `Contact.record` folds cardinality; the Stage 0 veto
is removed. Replace `test_calibration_cluster_merge_undercount.py`'s assertions (twelve objects at
9 km → **one** contact with a plural count bucket; at 500 m → several contacts with small counts).
Turn `test_two_real_objects_stay_two_contacts` into a real assertion. Uses provisional constants;
does not tune them.

**Stage 3 — calibration, separate commit.** The tier → count-coarseness table (`lowres` clamps to
`OP_GROUP`; `medres` gives the real bucket; `hires` gives an exact one), the cluster-radius policy
and its chaining cap, and `NAKED_EYE_MAX_NEW_PER_POLL` re-read as a per-cluster cap. Needs a live
sortie to confirm; expect to land after one.

**Stage 4 — surface cardinality.** `facts["cardinality"]` (absent-when-unknown, per `tools.py`'s
documented convention); `console._SHOW_FACT_KEYS`; `speech.py`'s count clause and the
`OP_GROUPSOMETHING` fix — **singular output must stay byte-identical**, which is the regression
guard for every existing speech test; `CONTACT_CARDINALITY_CHANGED`; and fixing the count
arithmetic the survey flagged (`get_situation`'s `contact_counts`, `get_stats`, and
`escalation._situational_header`'s bare `len(store.contacts)`) to distinguish contact records from
estimated units.

**Stage 5 — composition.** `belief/composition.py`, `Observation.composition`, per-member folding,
the over-subscription retraction, `facts["composition"]`, and speech's "three of them tanks … and
something else". Also amend `enrichment.motion_when_seen`, which derives a direction from a
contact's two most recent implied positions — for a cluster those can come from different vehicles
and fabricate a heading. Suppress it when cardinality is plural.

**Stage 6 — split/merge hardening and docs.** Tests that pin majority-overlap re-homing (split and
merge), the arbitrary-survivor caveat documented on the fields, `WorldEnrichmentCache` invalidation,
`PendingIntent.result_contact_ids` resolved by id at read time rather than trusted as captured, and
the ROADMAP/§3.6 amendments. Small; may fold into Stage 2 if it stays trivial.

---

### Risks & Unknowns

- **Cluster churn at boundaries.** An object oscillating near a cluster edge flips membership
  poll-to-poll, making cardinality jitter and spamming `CONTACT_CARDINALITY_CHANGED`. Mitigations:
  sticky assignment (prefer the previous poll's cluster within a margin), the existing
  `EVENT_COOLDOWN_S`, and the fold's hold-on-wider rule. Real risk, calibration-shaped, Stage 3.
- **Single-link chaining.** A 2.5 km radius at 9 km will chain across a battlefield if clustering is
  naive — twelve vehicles and a distant convoy become one "group of 20". Needs a maximum cluster
  angular/linear extent. This is the single most likely thing to need a second calibration pass.
- **Cluster-level continuity is weaker than object-level continuity.** Majority overlap is a
  heuristic where `object_id` matching was exact. A cluster that splits evenly has no majority (tie
  broken deterministically but arbitrarily). Accepted; the contact still exists and still decays
  honestly.
- **`derived_world_position` becomes a centroid.** It is truth-side bookkeeping never read by
  `belief/`, but its meaning changes and every reader of it (logger output, future fusion work)
  must be told.
- **`contributing_observation_ids` changes meaning** — one entry now covers N objects. Affects
  `enrichment._recent_percepts`.
- **Cross-channel duplication gets harder, not easier.** The parked backlog item (per-channel
  continuity maps, a bus tracked as two contacts) now has to reconcile a cluster-level report from
  one channel with per-object reports from the scope channel. This plan does not make it worse in
  practice — the scope channel simply reports `count_bucket=None` → `UNKNOWN` → hold — but it does
  make the eventual shared-map fix a harder design.
- **Unverified DCS-internals dependency: none.** Every fact this plan depends on (the `OP_*UNITS`
  ladder, `OP_SINGLE`/`OP_GROUP`, `OP_GROUPSOMETHING`'s catch-all semantics, the `9 CONTACTS,
  1 O'CLOCK` decomposition) is already recorded in
  `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`. No
  investigator pass needed. One item in that file is marked inferred rather than confirmed —
  `OP_GROUPSOMETHING`'s "generic catch-all regardless of the `OP_SINGLE`/`OP_GROUP` modifier" — and
  this design does not depend on it either way, since we compose our own callouts rather than
  replaying ED's.
- **Stage 2 is the only stage with a real regression surface.** It changes how many contacts exist
  for the same world, so every downstream count, every speech line, and both console renderings
  shift at once. It must land with the mock-flight chain test green and a live sortie behind it.

---

### Second-order effects

Unblocks **BL-8 (memory layer)**: "the group we saw at the crossroads" is a far better memory unit
than twelve anonymous contact records, and BL-8 was deliberately left last precisely so the shape
of what is worth remembering could be learned first — this is that learning.
Narrows the deferred **coalition/IFF** item: a group carries one IFF claim over a composition,
which is both cheaper and more realistic than per-vehicle inference.
Complicates the parked **cross-channel duplication** item, as noted above.
Makes `plans/body-layer/plan.md` §3.6's `contact_group` a *later, optional presentation layer*
rather than a data-model requirement — a simplification of that milestone, not a contradiction of it.

---

### Settled Decisions (user, 2026-09-18)

All five resolved, each matching this plan's own recommendation.

1. **Scope: implement Stages 1-4, then decide on Stage 5 with sorties behind it.** Cardinality
   first; composition is a separate commitment made later, on evidence. Note Stage 3 needs a live
   flight, so the run is 1 → 2 → sortie → 3 → 4.
2. **Attention does not survive a split.** Only the majority child keeps the parent's mark: a watch
   is on a thing the crew deliberately picked, and a newly-separated thing was never picked.
3. **No `CONTACT_SPLIT` event kind.** A split stays observable as a cardinality narrowing on the
   parent plus a `CONTACT_DETECTED` on the child. Revisit only if Petrovich should actually *say*
   "they're separating" — that would want its own kind rather than inference by a consumer.
4. **Over-subscription retracts lowest-confidence claims first**, matching the lattice's existing
   "floor to the lower confidence" posture and the user's own example, where the newer reading
   ("not ifvs, but shilka") wins.
5. **`plans/body-layer/plan.md` §3.6 may be amended with a dated note**, not rewritten — its
   `contact_group` sketch is reinterpreted here (container with `member_ids` → perception-limit
   aggregate with counts) and the original reasoning is worth preserving alongside the change.

