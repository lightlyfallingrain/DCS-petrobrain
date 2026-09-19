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

**Stage 3 is split into 3a and 3b** (user direction, 2026-09-18), because as originally written it
bundled a structural fix that needs no flight with calibration that cannot happen without one — and
running them in that order would have produced misleading data. **Stage 4 also splits**, because
cardinality is currently invisible: it is absent from `tools.py`'s facts payload and from
`console._SHOW_FACT_KEYS`, so a calibration sortie could observe how many *contacts* exist but not
the count *bucket* on each — which is precisely what 3b calibrates.

Running order: **3a → 3b-i → 4a → sortie → 3b-ii → 4b**. (3b itself split again on 2026-09-18 —
see Stage 3b below: its resolution rework turned out to be derivable without flying, and flying
before it lands would repeat the exact mistake the 3a/3b split was made to avoid.)

**Stage 3a — close the gate-vs-cluster radius mismatch. No sortie needed; must land before one.**
The structural finding from Stage 2's review, described in full below. Clustering splits on
`max(radius_a, radius_b)` (single-sided) while the belief gate re-tests a split child against its
parent on `uncertainty_a + uncertainty_b + growth` (both sides summed), and `sum ≥ max` means a
split whose children sit near the cluster's resolution boundary is re-merged. **This must land
before the sortie**, not after: flying while clustering is still being silently undone downstream
would calibrate a system in which the thing being calibrated is partly defeated, and the numbers
brought back would be wrong in a way that is hard to detect.

**Stage 4a — make cardinality observable. No sortie needed; must land before one.**
`facts["cardinality"]` (absent-when-unknown, per `tools.py`'s documented convention) and
`console._SHOW_FACT_KEYS`. This is the minimum that lets a sortie see what 3b is tuning. Speech is
deliberately *not* here — hearing counts is 4b, and is not needed to calibrate.

**Stage 3b — the resolution model. Split into 3b-i (no sortie) and 3b-ii (needs the sortie),**
for the same reason Stage 3 split: flying before the resolution model is right would measure a
system whose behaviour is still wrong, and the numbers brought back would be wrong in a way that is
hard to detect afterwards.

**Stage 3b is not a constant-tuning exercise. The cluster radius is built on the wrong quantity**
(user, 2026-09-18, and confirmed against the code):

```python
cross_range_m = range_m * math.sin(_HALF_CLOCK_BUCKET_RAD)   # half of a 30 deg clock bucket
down_range_m  = _range_bucket_width_m(range_m)               # an OP_D* bucket's width
return math.hypot(cross_range_m, down_range_m)
```

Both terms are **reporting** quantisations — the clock vocabulary and the `OP_D*` vocabulary — not
**resolving** power, and the two are different things. Petrovich can plainly see two dots 2 degrees
apart while still *reporting* both as "eleven o'clock", and can plainly see one vehicle is nearer
than another while reporting both as "8-9 km". Separation should be triggered by what the channel
can **resolve**, and for the cross-range axis that is **apparent angular separation against visual
acuity**.

#### The finding that reorders this whole stage: the term being fixed is not the term that binds

Correcting the angle alone is a **no-op**, because `math.hypot` lets the down-range term set the
radius at every range in the ladder:

| Range | cross-range, acuity-derived | down-range (`_range_bucket_width_m`) | `hypot` |
|---|---|---|---|
| 503 m | 0.4 m | 100 m | 100 m |
| 2.99 km | 2.2 m | 500 m | 500 m |
| 8.89 km | 6.7 m | 1000 m | 1000 m |

The two axes differ by a factor of ~150 at 9 km. Folding them into one scalar with `hypot` throws
the anisotropy away and the larger term wins everywhere. **So the real content of 3b-i is not
"replace a constant" — it is "stop pretending this uncertainty is isotropic."** The uncertainty of
a bearing-and-range observation is an ellipse elongated along the line of sight; it has always been
one, and the scalar radius was hiding that as much as the wrong angle was.

This also revises what Stage 3a's dead zone was about. The plan previously attributed its width to
the 15-degree angle alone; the down-range term was the larger half of it.

#### Where the acuity constant comes from — and the honest limit of the evidence

**Checked first, before inventing anything** (and this is the answer to "should it simply *be*
`LOWRES_ANGULAR_RADIUS_RAD`?"):

`perception/visibility.py`'s `LOWRES_ANGULAR_RADIUS_RAD = 0.003` is compared against
`size_m / range_m * BINOCULAR_RANGE_MULTIPLIER` — i.e. it is a threshold on **apparent angular
extent**, already including magnification. 0.003 rad = **10.3 arcmin**. More important than the
number is the *model* that module and `research/2026-09-17-vision-range-calibration-pass2.md`
established and validated: read as apparent angle, the naked-eye and binocular columns collapse
onto **one** threshold set (class: 0.0139 vs 0.0141 rad, agreeing to 2%), with the optic supplying
only the magnification. That is a measured cross-optic result, not an assumption.

**Decision: derive the acuity constant from it rather than introducing an independent number.**
`perception/clustering.py` importing `perception/visibility.py` is legal — both live in
`perception/`, unlike the `belief/` direction that forced the `_RANGE_BUCKETS_M` duplication. One
line, one name:

```python
NAKED_EYE_ACUITY_RAD: Final[float] = LOWRES_ANGULAR_RADIUS_RAD
```

The justification is *not* "human two-point resolution equals human minimum detectable size" — for
a real eye those differ by an order of magnitude in the opposite direction (a high-contrast dot is
detectable far below the 1-arcmin two-point limit). It is that **neither constant is modelling a
retina.** 0.003 rad is ten times real foveal acuity precisely because what was graded was a
*rendered frame*: the binding limit is how much detail DCS puts on screen per unit apparent angle.
Minimum-detectable-extent and minimum-resolvable-separation are two expressions of that same
render-side scale, which is why "two blobs one blob-width apart" is the natural criterion here. One
number, one instrument, one derivation.

**The honest limit, stated plainly rather than dressed up as a derivation.** The versioned evidence
does **not** pin this value:

- `tests/fixtures/vision_calibration.json` records a per-complex *recognition tier*
  (`nothing` / `marginal_speck` / `speck_no_class` / `class_recognizable` / `type_recognizable`).
  It records **no countability or separation grade at all**. The "~6-7 distinct specks" reading is
  an interpretation of the images, which are gitignored — it is not in the fixture or the research
  doc, and cannot be re-checked from the repo.
- The "not countable at 8.89 km, naked eye" datapoint is **confounded and bounds nothing.** At that
  range a 7 m vehicle subtends 2.7 arcmin unaided, far below the 8-10 arcmin *detection* threshold,
  while the 18 m spacing subtends 7.0 arcmin. The units are not individually countable there
  because they are not individually *detectable* — a detection failure, not a resolution failure.
  It is consistent with any acuity value, including much finer ones.
- The "6-7 specks from 12 units" binocular reading is confounded the other way: Complex C contains
  natural pairs (SA-3 launcher + its TR radar, ZU-23 *on* a Ural, 3x AK infantry), so 6-7 blobs is
  equally explained by real spatial clumping as by resolution merging. The fixture stores no
  per-object positions, so the two cannot be separated from the repo.
- The one genuine constraint is an **upper bound**: naked eye at 2.99 km, 18 m spacing = 20.7
  arcmin apparent, and the row reads as distinct. So acuity ≤ ~20.7 arcmin. There is **no lower
  bound in the evidence at all.**

10.3 arcmin sits comfortably under that bound and costs no new number, so it is a defensible
**provisional** value. **The mechanism is settled in 3b-i; the magnitude is not, and 3b-ii owns
it.** Saying otherwise would move the guesswork somewhere less visible, which is the one outcome
worse than an open question.

#### Is acuity per-optic? No — and the multiplier must be applied

`visibility.py` models the **binocular** observer, explicitly and by user decision, and its
docstring forbids re-deriving its constants from an unaided assumption. **Clustering must model the
same observer**, or Petrovich detects with one instrument and separates with another — he would
merge things he could plainly see apart at the moment he saw them. The pass-2 result says the
threshold is a property of the eye and the optic only multiplies the angle, so:

    two candidates are unresolvable when  separation_m / range_m * M  <  acuity
    cross_range_radius_m = range_m * NAKED_EYE_ACUITY_RAD / BINOCULAR_RANGE_MULTIPLIER

Note the symmetry that is itself an argument the two constants belong together: `visibility.py`
*multiplies* its range threshold by `M` (see 4x further); clustering *divides* its radius by `M`
(resolve 4x finer). Both are the same statement that the optic scales apparent angle. No per-optic
acuity dimension is introduced here, for the same reason the pass-2 calibration did not need one;
the per-optic split stays with the deferred "attention direction and detection cones" milestone.

#### The down-range term — examined, kept, re-justified

It stays, but **its stated reason was wrong and must change, and it must stop being `hypot`'d.**
`_range_bucket_width_m` is a reporting quantisation, exactly the conflation being fixed on the
cross-range axis. The reason it survives is different: **depth discrimination really is terrible at
range.** Stereopsis is useless past ~100 m and monocular depth cues on flat desert are weak, so a
genuinely large down-range uncertainty is physically right — the bucket width is approximately the
right *magnitude* reached for the wrong *reason*. Keep it as an explicit stand-in for
depth-discrimination uncertainty, documented as provisional magnitude, and let 3b-ii confirm it.

#### Counting versus resolving — the anisotropy gives this for free

The two thresholds separate cleanly once the axes are separate, with **no new constant and no
invented tier table**:

- **Counting** is pure two-point resolution: how many angularly distinct blobs. It needs the
  **cross-range axis only.** Six specks in a row are countable without any of them being placeable
  in depth.
- **Forming a contact** needs resolution *and* a usable position, so it needs the **full ellipse**,
  down-range term included.

So: **the count bucket is computed by sub-clustering a cluster's members on the cross-range axis
alone; cluster membership uses the full ellipse.** Same acuity constant, two projections of it.
This is what lets one contact honestly say "several of them" — the group-contact model's entire
point — and it now falls out of geometry instead of a tier→coarseness table. The tier table
degrades from the primary mechanism to a **cap** on top of the geometric count (a `lowres` cluster
should not claim an exact number however the geometry counts), which is a much smaller thing for
3b-ii to calibrate.

#### Blast radius — what each affected assertion becomes

Every one of these encodes behaviour produced by the *current* radius. Re-derive, do not assume.

- **`test_calibration_cluster_merge_undercount.py` inverts.** Its Stage 2 assertion (twelve objects
  at 9 km → **one** contact with a plural count bucket) is **false** under the corrected model when
  the complex lies across the line of sight: 18 m spacing vs a 6.7 m cross-range radius resolves
  all twelve, and all twelve clear detection (7 m vehicle reaches 9333 m). It becomes: a 206 m row
  **perpendicular** to LOS at 9 km → twelve contacts; the same 206 m line **along** LOS at 9 km →
  one contact with a plural count bucket. **Geometry, not range, decides** — which is the real
  lesson and a better test than the one it replaces.
- **`test_two_real_objects_stay_two_contacts` (strict `xfail`) — outcome is geometry-dependent, so
  do not predict it.** The two objects are 400 m apart, first seen ~2 km. Cross-range radius at 2 km
  is 1.5 m, so if that separation is across the LOS it resolves trivially and the `xfail` flips to
  pass. If it is *along* the LOS, the down-range radius there is 500 m > 400 m and it still merges.
  Work out the actual approach geometry before touching the marker.
- **Stage 3a's same-source/same-poll rule becomes *more* load-bearing, not less.** A far finer
  cross-range radius means clustering splits far more, so there is far more for the belief gate to
  wrongly re-merge. The rule should still hold, but its cases were chosen near the *old* boundary
  and must be re-derived at the new one.
- **The by-construction identity is what makes this consequential.** `belief.association_over_time.
  uncertainty_radius_m` calls `naked_eye_cluster_radius_m` directly (line 171) — the plan's central
  claim that the cluster radius and the gate's per-percept uncertainty are *the same number*. If
  clustering goes anisotropic and the gate stays scalar, that identity breaks and re-opens exactly
  the dead zone Stage 3a was written to close. **Mitigating fact found while checking:** `Percept`
  already carries `ownship_at_observation`, and `ownship_state` is already in scope at
  `naked_eye_source.py`'s `cluster_candidates` call site — so both sides can take the LOS frame
  **without a data-plumbing change**, only signature changes. That makes moving both together
  substantially cheaper than it looks, but it does mean 3b-i touches the gate fixed twice already
  (BL-2.6 widened it; `plans/contact-duplication-ambiguity-runaway/` made it the exception path).
  **See Decisions Requiring User Input.**
- **`NAKED_EYE_MAX_NEW_PER_POLL = 3`** — twelve resolved clusters at 9 km take four polls to
  acquire. `naked_eye_source.py` documents the cap as throttling *objects*, not clusters; re-read it
  as a per-cluster cap here. Whether four polls reads as natural or as a stutter is a
  perception-feel question → 3b-ii.
- **Single-link chaining drops in severity.** It was alarming at a 2.3 km radius; at 6.7 m
  cross-range it is minor. The down-range axis can still chain a convoy into one cluster, which is
  arguably *correct*. The chaining cap therefore demotes from "needed" to "confirm whether it is
  needed at all" → 3b-ii.

#### Stage 3b-i — the resolution rework. No sortie. Derivable now.

1. `NAKED_EYE_ACUITY_RAD` in `perception/clustering.py`, imported from `perception/visibility.py`'s
   `LOWRES_ANGULAR_RADIUS_RAD`, with the derivation and its one-sided evidence bound written on it.
2. Replace the scalar `naked_eye_cluster_radius_m` with an anisotropic cross-range / down-range
   pair; cross-range from acuity and `BINOCULAR_RANGE_MULTIPLIER`, down-range from
   `_range_bucket_width_m` under its new justification.
3. Ellipse membership test in `cluster_candidates`, taking the observer position to define the LOS
   frame (available at the call site already).
4. Count bucket from cross-range-only sub-clustering.
5. Re-derive the affected tests above from the new geometry.

**Merge criterion: the suite is green and every re-derived assertion has its geometry written out
in the test, not just its expected number** — these are the assertions that were previously right
for the wrong reason.

#### Stage 3b-ii — what genuinely needs the sortie

1. **The acuity magnitude.** The evidence gives an upper bound and no lower bound; only live
   observation closes that. This is the honest reason to fly.
2. **The tier → count-coarseness cap** on top of the geometric count.
3. **The chaining cap** — whether one is needed at all, now that the radius is ~300x finer.
4. **`NAKED_EYE_MAX_NEW_PER_POLL` as a per-cluster cap**, and whether staged acquisition of a
   resolved group reads as natural.
5. **Confirmation that the acuity constant behaves in motion**, against real terrain and clutter
   rather than a flat-desert still — the condition under which none of the existing evidence was
   gathered.

Running order is unchanged except that 3b-i joins the pre-sortie group: **3a → 3b-i → 4a → sortie →
3b-ii → 4b**.

**Stage 4b — speech and events. No sortie needed.** (4a already surfaced the facts key and the
console.) `speech.py`'s count clause and the `OP_GROUPSOMETHING` fix — **singular output must stay
byte-identical**, which is the regression guard for every existing speech test;
`CONTACT_CARDINALITY_CHANGED`; and fixing the count arithmetic the survey flagged
(`get_situation`'s `contact_counts`, `get_stats`, and `escalation._situational_header`'s bare
`len(store.contacts)`) to distinguish contact records from estimated units. **Full design: "Stage
4b design — speech and events" below.**

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

### Stage 3a design — closing the gate-vs-cluster radius mismatch

Decided 2026-09-18, in response to `plans/group-contact-model/review.md`'s required fix. This is
the one stage that edits a gate already fixed twice in opposite directions (BL-2.6 widened it,
`plans/contact-duplication-ambiguity-runaway/` made it the exception path), so the reasoning is
written out rather than compressed.

#### The mismatch, restated with its numbers

`perception.clustering.cluster_candidates` splits two candidates when their real separation exceeds
`max(radius_a, radius_b)` — **single-sided**, ≈205 m at 690 m range (`hypot(690·sin 15°, 100)`).
`belief.association_over_time.spatial_gate_radius_m` then re-tests the split child against the
parent's contact on `uncertainty_a + uncertainty_b + GATE_GROWTH_RATE_MPS·elapsed_s` — **both sides
summed**, ≈410 m before growth. Since `a + b + growth ≥ max(a, b)` for any positive radii, a split
whose children sit near the cluster's own resolution boundary is re-absorbed. That boundary is
exactly where a split first becomes possible, so this is the common case, not an edge one.

The same arithmetic produces a second, worse symptom that the review's worked example did not
name: **two clusters from the same poll that were never one contact**. Two same-class clusters
300 m apart at 690 m are separate clusters (300 > 205) but the second passes the gate against the
first's brand-new contact (300 < 410) and folds into it — one contact, cardinality reinforced to
`OP_1UNIT`, a *confident* false merge rather than an honestly hedged one. Any fix aimed only at
split children leaves this open; it is the same-class hole the plan's "interim fix" section already
warned about, now reachable through clustering instead of around it.

Both symptoms are one violation of this plan's own invariant: *the model's resolution is the
channel's resolution by construction*. The channel has already decided these are separate reports;
belief then decides they might be one thing.

#### Decision

**Two `Observation`s from the same source in the same poll may never resolve to the same contact.
Enforce that as a candidate exclusion in `belief.contacts.ContactStore.ingest`, not as a change to
the gate's radius.**

The gate stays exactly what it is — a per-percept geometry-and-class predicate, with BL-2.6's
symmetric budgeting untouched, byte for byte. What is added is an *association bookkeeping* rule,
which is the same category as `_resolve_continuity` and belongs beside it.

The rule rests on a property both current sources actually have, and it must be documented as a
precondition rather than assumed forever: post-Stage-2 naked-eye emits one `Observation` per
resolution cluster, and two clusters are separable by construction; the scope/hybrid channel emits
one `Observation` per `object_id`, and two object ids are two real objects. **Neither source can
emit two reports of the same thing in one poll.** A future source that could would violate this
rule's premise and must be excluded from it explicitly.

#### Mechanism — exactly what changes

`ContactStore.ingest` only. Roughly fifteen lines plus docstrings.

1. **A read-only pre-scan over the batch, before the existing loop.** For each observation, evaluate
   `_resolve_continuity` once and memoize the result; record, for every observation that resolves,
   `claimed[(observation.source, observation.t_sim)].add(contact.id)`. The pre-scan mutates nothing.
   Its purpose is order-independence: the majority child of a split claims the parent contact before
   any minority child reaches the gate, regardless of the order clustering happened to emit them in
   (`cluster_candidates` does not define cluster order, and `naked_eye_source._build_observations`
   does not sort).
2. **The existing single-pass loop is otherwise unchanged**, including the order in which
   `contact.record` runs — so no fold ordering shifts as a side effect of this stage. It consumes
   the memoized continuity result instead of calling `_resolve_continuity` a second time (using the
   pre-scan as authority also keeps a contact refreshed mid-batch from changing its own continuity
   verdict mid-batch).
3. **The gate branch filters candidates** by `candidate.id not in claimed[(source, t_sim)]` before
   applying the existing one/zero/two-or-more decision rule. Exclusion happens *before* counting, so
   a percept whose only candidates are all claimed this poll sees zero and founds — the same
   outcome the ambiguity rule already produces, through the same code path.
4. **Whatever contact the observation ends up on — merged or founded — is added to
   `claimed[(source, t_sim)]`.** Without this, three clusters against one old contact would collapse
   to two: the third would be excluded from the old contact and merge into the second's brand-new
   one.

Keying on `(source, t_sim)` rather than on the batch is what preserves cross-channel fusion: the
whole point of `test_cross_channel_fusion.py`'s same-batch scope + naked-eye cases is that two
reports from *different* channels in one batch fold into one contact, and they must keep doing so.
`logger.PerceptionRunner` builds one combined batch per poll across all sources, so source-keying is
load-bearing, not defensive. `t_sim`-keying costs nothing and keeps the rule correct for any
multi-poll batch a test or a future replay path might hand in.

No new constant. No new tunable. Nothing for Stage 3b's sortie to calibrate here — which is the
point of landing it before the sortie.

#### Does the percept need to carry a cluster identity? No.

The perception layer does know more than it currently says — `_build_observations` computes, for a
minority split child, that another cluster in this same poll claimed its parent's observation id,
and then throws that away by setting `continues_observation_id=None`, which is indistinguishable
from "never seen before". Carrying it as a new `Observation.separated_from_observation_id` field was
the obvious design and is **rejected**: the store can already derive everything the rule needs from
`source`, `t_sim`, and the observation ids it is holding anyway, and a field would buy only the
split case while leaving the same-poll false merge above untouched. Given that `Observation` and
`Percept` just gained `count_bucket` in Stage 2, not adding a second field for a strictly weaker
rule is the right trade. **`Observation`, `Percept`, `percept_of`, and `naked_eye_source` are all
unchanged by this stage.**

#### Why the two alternatives from the review are worse

- **"Exempt a freshly-split child from the gate."** Needs a definition of "freshly" (the store has
  no natural one), needs the new field above to know a child is split at all, and exempting a
  percept from the *whole* gate also stops it merging onto some genuinely different existing
  contact it should merge onto — an older, still-estimated contact the child is the reacquisition
  of. It is a special case bolted onto a general rule, and it covers strictly less than the chosen
  rule does.
- **"Make the gate single-sided when the percept carries a distinct cluster identity."** After
  Stage 2 *every* naked-eye percept carries a distinct cluster identity, so the condition collapses
  to "naked-eye percepts get a single-sided gate" — which is BL-2.6 reverted for the channel BL-2.6
  was fixed for. Narrowing the condition to split children only does not rescue it either: halving
  the radius still re-merges any split at a separation between the cluster radius and the halved
  gate radius (a 210 m split at 690 m still sits inside ≈205 m + growth), so it closes part of the
  gap at the cost of touching the one formula that must not be touched. The chosen rule closes all
  of it and leaves the formula alone.

#### How both prior fixes stay fixed — the argument by inspection

- **BL-2.6 (`plans/classification-refinement/`, symmetric budgeting) is preserved because the
  radius formula is not edited at all**, and because the new rule is provably a **no-op for any
  `(source, t_sim)` group of size one**. BL-2.6's live-observed failure was a single slow-moving
  object whose bucket-quantised implied position shifted between polls, missing an under-sized gate
  and spawning a duplicate that then poisoned the ambiguity rule. That object produces exactly one
  observation per poll per source, so its exclusion set is empty on every poll and it sees the full,
  symmetric, both-sides-summed gate it has today. The failure mode BL-2.6 fixed is *across* polls;
  this rule constrains only *within* one poll. The two cannot collide.
- **Object-permanence correlation (`plans/contact-duplication-ambiguity-runaway/`) is untouched
  because the continuity path is never vetoed.** The pre-scan reads it and records what it claims;
  it never blocks it. Every percept that resolves by continuity folds exactly as it does today. The
  gate remains the exception path, and this stage only changes which candidates it may choose from
  when it is reached.
- The duplication *runaway* itself needed the gate to be re-entered poll after poll. A contact this
  rule causes to be founded carries its own continuity from the very next poll (its members' entries
  in `naked_eye_source._object_id_to_last_observation_id` now point at its own observation), so it
  never returns to the gate and cannot become a permanent second candidate.

#### What the affected tests assert afterwards

- **`test_calibration_cluster_merge_undercount.py` — unchanged, both tests, and that is the guard.**
  The 9 km case is one cluster, so the rule cannot apply. The close-range case is six same-poll
  clusters that already found six contacts because their classes are mutually incompatible; the
  exclusion is redundant there, not decisive. If either test's assertions move, the rule has been
  implemented more broadly than designed.
- **`test_mock_flight_chain.py::test_mock_flight_chain_single_threaded_reaches_expected_contact_state`
  — this is the test that changes, and the long derivation comment in it must be rewritten, not
  merely re-numbered.**
  - Observation count stays **42**: clustering is untouched, the poll-by-poll 14 + 4 + 4 derivation
    still holds.
  - Contacts become **2**, not 1. At poll 14 the truck singleton is the majority-overlap
    continuation and folds onto the existing contact; the infantry singleton reaches the gate, finds
    that contact already claimed by a same-source, same-poll observation, and founds its own.
  - Events become **two** `CONTACT_DETECTED` (the founding one, plus the infantry contact at poll
    14). The implementer must confirm nothing else appears — re-derive poll by poll and run it, per
    this test file's own stated convention, rather than pasting these figures in.
  - The truck contact keeps `classification == "Ural truck"` at `type` level, `certainty ==
    "observed"` (the hybrid channel keeps reporting object 101 every poll even after the cockpit
    mask drops it from naked-eye), and both sources. The new contact is naked-eye only at the
    presence root.
  - Cardinality: the truck contact held `OP_2UNITS` (2,2) through polls 0–13; the poll-14 singleton
    report is (1,1), which is **disjoint**, so `fold_cardinality` contradicts to the hull **(1,2)**
    and arms `CARDINALITY_CONTRADICTION_LOCKOUT_S`. Expect it to still read (1,2) at the fixture's
    end, since the fixture is shorter than the 30 s lockout — verify rather than assume, as the
    figure depends on the fixture's poll cadence. The new contact is (1,1).
- **Should the two 400 m-apart objects separate at 690 m? Yes, and the channel's own numbers say so
  twice over.** In this fixture the separation is *down-range* (x=1400 vs x=1800 on roughly the same
  line of sight): at that range the `OP_D*` buckets are 100 m wide, so the two objects quantise into
  four buckets' worth of separation — the channel reports them at plainly different ranges and is
  not guessing. The transverse case argues the same way: 400 m at 690 m subtends ≈32°, just past the
  30° clock-bucket width, so they would land in different clock positions. Claiming "these might be
  one object" when the channel's own output places them in different buckets on the axis that
  separates them is the model claiming *less* resolution than the channel has — the same
  no-omniscience invariant this plan is enforcing, violated in the opposite direction. Two contacts
  is the honest answer.
- **New unit test in `test_contacts.py`**: two same-source, same-`t_sim` observations, spatially
  close enough and class-compatible enough to pass the gate against each other, found two contacts;
  the same two observations with *different* sources still merge into one. That pair pins both
  halves of the rule, including the source-scoping that keeps cross-channel fusion alive.

#### Deliberate non-goals of this stage

- **A split still registers as a cardinality *contradiction*, not as a known structural event.**
  Narrowing (2,2) to (1,1) is disjoint, so the parent hedges to (1,2) and locks out for 30 s even
  though nothing actually contradicted — the group simply became resolvable. Treating a split as a
  privileged narrowing is a separate decision about `fold_cardinality` that needs evidence, and the
  hull is honest in the meantime, only hedged. If 3b's sortie shows counts stuck wide after splits,
  this is the first thing to revisit.
- **A contact that already holds two continuity chains keeps holding them.** This rule blocks new
  same-poll co-folds through the gate; it cannot unpick a false merge that happened before it landed
  or that was assembled one poll at a time. Detecting it (a contact whose folded reports imply more
  occupants than its cardinality admits) belongs with Stage 3b's sortie and Stage 5's composition
  work. A flag-gated debug line in `ingest` when two same-source, same-poll observations resolve by
  continuity to the same contact would surface it cheaply and is worth adding here.

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

### Decisions Requiring User Input (raised 2026-09-18 by the Stage 3b rework)

1. **Does Stage 3b-i take the belief gate anisotropic at the same time as clustering, or only
   clustering?** Recommended: **both together.** The plan's load-bearing claim is that the cluster
   radius and `association_over_time.uncertainty_radius_m` are the same quantity *by construction*;
   splitting them re-opens precisely the dead zone Stage 3a exists to close. The cost is that 3b-i
   then edits a gate already fixed twice in opposite directions. The mitigating find is that
   `Percept.ownship_at_observation` already carries the observer position, so no data plumbing is
   needed on either side — only signatures. Escalated rather than decided because it is
   consequential and not cheaply reversible.

2. **Is "twelve resolved contacts at 9 km" the behaviour you want?** Under the corrected model a
   206 m row across the line of sight resolves into twelve individual contacts at 9 km, because the
   modelled observer is the *binocular* one (`visibility.py`'s standing decision) and 18 m at 9 km
   through 4x is nearly half a degree. That is defensible, but it inverts this plan's own
   motivating example, and it means **part of the observed defect was the broken radius rather than
   a missing group model.** Cardinality is still needed — for along-LOS columns, tight formations,
   and small/infantry targets — but the headline case shrinks. Worth confirming before 3b-i rewrites
   the regression test around it.

---

### Second-order effects

The 3b rework **narrows** Stage 5 (composition) and the deferred per-optic "attention direction and
detection cones" milestone at once: once resolution is modelled as an apparent-angle threshold
projected onto two axes, adding a second optic is supplying a different magnification rather than a
new model, and composition inherits a geometric member count instead of needing its own.

Unblocks **BL-8 (memory layer)**: "the group we saw at the crossroads" is a far better memory unit
than twelve anonymous contact records, and BL-8 was deliberately left last precisely so the shape
of what is worth remembering could be learned first — this is that learning.
Narrows the deferred **coalition/IFF** item: a group carries one IFF claim over a composition,
which is both cheaper and more realistic than per-vehicle inference.
Complicates the parked **cross-channel duplication** item, as noted above.
Makes `plans/body-layer/plan.md` §3.6's `contact_group` a *later, optional presentation layer*
rather than a data-model requirement — a simplification of that milestone, not a contradiction of it.

---

### Correction (user, 2026-09-18): separability is angular, full stop

This supersedes the world-space ellipse Stage 3b-i implemented. Recorded before Stage 3b-ii so the
ellipse is not calibrated into permanence.

**The framing.** Whether two units are one contact or two is a question about the **angle between
them as seen from Petrovich**, compared against the angular size of the targets themselves. The
user's non-DCS analogue: two apples 20 cm apart at 50 cm are obviously two when side by side, and
may be one when one sits behind the other — same objects, same separation, different geometry. A
line of units at 12 o'clock likewise depends only on the angle between them; far enough away, any
number of units is a single dot.

**The ellipse was an approximation of this, and an unnecessary one.** Computing the true angular
separation from ownship — in 3D, including ownship's altitude — reproduces the anisotropy for free,
because **Petrovich is airborne** and a down-range pair separates by *depression angle*. For two
objects 400 m apart with ownship at 200 m AGL:

| Range | Along the line of sight | Side by side |
|---|---|---|
| 9 km | **3.2 arcmin** (one dot) | 153 arcmin |
| 5 km | 10.2 arcmin (just splits) | 274 arcmin |
| 2 km | 56.8 arcmin | 679 arcmin |
| 1 km | 191 arcmin | 1308 arcmin |
| 500 m | 556 arcmin | 2320 arcmin |

A factor of ~48 at 9 km, collapsing as ownship closes — the same shape the ellipse imposed with two
hand-chosen radii, but *derived* rather than tuned, and automatically correct for an observer who
is 200 m up rather than on the ground. It also explains the along-LOS column resolving as the
aircraft descends or closes, which the ellipse could only reproduce by coincidence.

**What this changes:**

- **Replace the ellipse with a true angular separation test.** `EllipseRadii`,
  `naked_eye_cross_range_radius_m` / `naked_eye_down_range_radius_m`, `los_components_m` and
  `within_ellipse` collapse into one angular predicate. The down-range radius stops needing a
  justification at all, which is a good sign — it was the term whose rationale had already been
  replaced once.
- **Angular *size* of the targets belongs in the test too**, not just their separation. Two
  units whose angular separation is smaller than their own angular size are not resolvable as two.
  `object_model.size_m` already supplies the size, and `visibility.py` already works in apparent
  angle.
- **This likely dissolves the jitter regression.** The 38-contacts failure came from the
  cross-range budget shrinking ~100x in *world space* while bearing-bucket requantisation jitter
  stayed constant in world space. In angular space the jitter is a fixed angular quantity (the
  clock bucket), so the comparison is like-for-like and the mismatch may simply not arise. **Check
  this before designing a separate jitter budget** — the cheaper fix may already be in hand.

**Counting has its own angular law, and ED's ladder already encodes it.** The user: telling 1 from
10, or 5 from 30, is easy; 1 from 2, or 20 from 23, is not — and it degrades with distance. That is
Weber's law over a subitizing floor, and **ED's own count vocabulary already has exactly that
shape**: exact at the bottom (`OP_1UNIT`, `OP_2UNITS`), widening upward (`OP_TO5UNITS`,
`OP_5TO7UNITS`, `OP_8TO10UNITS`, `OP_ABOUT15UNITS`, `OP_MORETHAN15UNITS`). So count *precision*
should fall as both count magnitude and angular crowding rise, and the ladder is the right output
alphabet for it rather than something to be replaced. This is also the honest answer to "twelve
along the line of sight reports `OP_1UNIT`": at 9 km that is *correct* — he sees one dot — and the
model should say so confidently rather than hedging.

**Deferred by the user, recorded so they are not silently assumed away:** occlusion (a near object
hiding a far one on the same line of sight — the apple and the orange), and shape, colour and
movement as separability cues. Movement in particular is a strong real-world cue and this model
currently ignores it entirely.

### Stage 3b-i rev.2 — the angular separability design (2026-09-18)

**This section supersedes the Stage 3b-i step list above and the ellipse it produced
(`c625299`).** The step list's items 1-4 are void; item 5 ("re-derive the affected tests") stands,
against the geometry below. Read the "Correction (user, 2026-09-18)" section first — this is its
implementation design.

#### 1. The predicate

Everything happens in one frame: the **3D angle subtended at ownship**. No world-space radii, no
LOS decomposition, no ellipse.

For two candidates `a`, `b` seen from ownship `O` (all three with real `alt_m`; ownship's altitude
is the term that makes this work at all):

    theta_sep      = angle between (a - O) and (b - O)          [true radians]
    theta_size(i)  = size_m(i) / slant_range_m(i)               [true radians]

**Two candidates are separable when**

    theta_sep  >=  0.5 * (theta_size(a) + theta_size(b))        ... (S)

and, as a floor,

    theta_sep * BINOCULAR_RANGE_MULTIPLIER  >=  LOWRES_ANGULAR_RADIUS_RAD     ... (A)

They merge into one cluster when either fails.

**(S) is the two-apples criterion, derived not tuned.** Two discs of angular diameter `d_a`, `d_b`
visually overlap when their centre separation is less than `(d_a + d_b)/2`. That is literally (S).
The only inputs are `object_model.profile_for(...).size_m` — already looked up at the call site in
`naked_eye_source._cluster_candidate` — and the slant range `visibility.py` already computed.
**No new constant, and no magnification term: `M` cancels out of (S) entirely**, because both
sides of the inequality are angles scaled by the same optic. The "clustering divides by `M` where
visibility multiplies by it" argument that Stage 3b-i needed disappears with the ellipse.

**(A) is provably non-binding for anything the channel actually detected, and that is the point.**
`visibility.py` admits a candidate when `range_m <= size_m / LOWRES_ANGULAR_RADIUS_RAD * M`, i.e.
exactly when `theta_size * M >= LOWRES_ANGULAR_RADIUS_RAD`. Combined with (S):
`theta_sep * M >= 0.5*(theta_size_a + theta_size_b)*M >= LOWRES_ANGULAR_RADIUS_RAD`. So (A) can
never be the binding constraint for a detected pair. Keep it anyway — one line, as a named floor
with that proof on it, and as a self-consistency assertion in the tests — but **the consequence is
large: the acuity magnitude stops being load-bearing for clustering.** Stage 3b-ii's item 1 ("the
acuity magnitude — the honest reason to fly") shrinks to "confirm the *detection* threshold", which
is already the calibrated quantity from `research/2026-09-17-vision-range-calibration-pass2.md`.
The one genuinely uncalibrated number in Stage 3b-i is gone rather than deferred.

**The anisotropy falls out, as the correction predicted.** Nothing in (S) mentions cross-range or
down-range. A down-range pair separates only by *depression angle*, which is small and shrinks with
range; a cross-range pair separates by the full bearing angle. Checked against the correction's own
table (400 m pair, ownship 200 m AGL, 9 km): along-LOS `atan(200/8800) - atan(200/9200) = 3.4
arcmin` (the table says 3.2 — same figure, different rounding of the midpoint), side-by-side
`400/9000 = 153 arcmin`. The factor of ~45 is produced by geometry alone.

#### 2. What collapses

Deleted outright from `perception/clustering.py`:

- `EllipseRadii`
- `naked_eye_cross_range_radius_m`, `naked_eye_down_range_radius_m`, `naked_eye_ellipse_radii_m`
- `los_components_m`, `within_ellipse`
- `_count_cross_range_subclusters` (the grid-binning count — see §5)
- `_RANGE_BUCKETS_M`, `_build_bucket_widths_m`, `_RANGE_BUCKET_WIDTHS_M`, `_range_bucket_width_m`
  — **moved back to `belief/association_over_time.py`**, their pre-Stage-2 home, because after this
  rework clustering has no use for a reporting quantisation and the gate is their only consumer
  (§3). Moved, still not duplicated.

Added, both pure and tiny:

- `angular_separation_rad(observer, a, b)` — unit vectors from ownship, `atan2(|cross|, dot)` for
  numerical stability near zero. 3D.
- `angular_size_rad(size_m, slant_range_m)` — `size_m / slant_range_m`.

Changed:

- `ClusterCandidate` gains `alt_m: float` and `size_m: float`. Both are already in hand at
  `naked_eye_source._cluster_candidate` (`candidate.alt_m`, `profile.size_m`); `range_m` there is
  already `geometry.range_m`'s slant range. **No new plumbing.**
- `cluster_candidates(candidates, observer)` takes an `OwnshipState` (or a `GeoPosition`) instead
  of `observer_x, observer_z` — it needs `alt_m`. `naked_eye_source` already has `ownship_state` at
  the call site.
- `_build_cluster` takes the observer for §5's count; its classification-aggregation half is
  **untouched**.

**Net: the module loses one dataclass, six functions and a 24-entry table, and gains two
one-line functions.** It shrinks, as required.

Kept unchanged, deliberately — the ellipse work was not wasted here: `cluster_candidates`' union-find
skeleton and its "cluster order is not defined" contract, `_build_cluster`'s aggregate-label
degradation, `count_bucket_for` and `_COUNT_BUCKET_SELECTION`, and all of
`naked_eye_source._build_observations`' two-pass global majority-overlap continuity resolution
(the implementation log's hardest-won finding, and orthogonal to this change).

#### 3. The belief gate — it does not become angular, and it stops sharing numbers with clustering

**Decision 7 is retired.** Its premise — "leaving the gate isotropic would re-open exactly the
Stage 3a dead zone" — does not hold, and Stage 3a's own Decision section says why in its first
line: *"Enforce that as a candidate exclusion in `ContactStore.ingest`, **not as a change to the
gate's radius**. The gate stays exactly what it is."* The dead zone is closed by the
same-source/same-poll exclusion, which is **radius-independent**: two `Observation`s from one
source in one poll can never resolve to the same contact, whatever the gate's width. Both symptoms
the Stage 3a section worked through (a split child re-absorbed by its parent; two never-merged
same-poll clusters folding together) are same-poll symptoms and are structurally impossible under
that rule. Decision 7 attached the gate to the cluster radius for a reason that was already
handled.

**So: revert `belief/association_over_time.py` to its pre-`c625299` form.** `uncertainty_radius_m`
(scalar, `naked_eye_cluster_radius_m(percept.range_m)`), `spatial_gate_radius_m`, and `passes_gate`
return byte-identical to `c625299^`; `uncertainty_radii_m` and the ellipse-based `passes_gate` are
deleted. The naked-eye uncertainty function comes back as a **private** `_naked_eye_uncertainty_m`
in that module (its original name and home), `hypot(range_m * sin(_CLOCK_BUCKET_DEG/2),
_range_bucket_width_m(range_m))`, alongside the bucket table moved back in §2.

The justification is not "restore what was there" — it is that **the gate and the cluster predicate
answer different questions about different things, and it was the sharing that was wrong**:

| | cluster predicate | spatial gate |
|---|---|---|
| Question | can he tell these two *live* candidates apart? | is this quantised *report* about that remembered thing? |
| Inputs | two objects, one instant, one observer | one report and one stored position, from two ownship positions at two times |
| Dominant error | optical resolving power | the channel's reporting vocabulary (30 deg clock bucket, `OP_D*` range bucket) + elapsed motion |
| Correct magnitude | ~one target width | ~one bucket width |

A contact stores a position, not a pair of live candidates, and that position was *quantised on the
way in*. Budgeting a quantised report against an acuity figure is a category error — it was the
real defect in Stage 3b-i, and §4 measures it.

Everything Stage 3b-i's docstrings assert about the gate being "the same ellipse by construction"
comes out with it. What stays untouched, again: BL-2.6's symmetric both-sides budgeting,
`GATE_GROWTH_RATE_MPS`, `SCOPE_UNCERTAINTY_M`, the class-compatibility gate, and Stage 3a's
exclusion rule in `ContactStore.ingest`.

#### 4. The jitter regression — refuted, then dissolved by §3 instead

**The correction's hypothesis is wrong, and the arithmetic says so in one line.** The ratio of
jitter to budget is a ratio of two *angles*, and a ratio of angles is invariant under the change of
representation the hypothesis was hoping would help:

- bearing-bucket requantisation jitter: up to one full `_CLOCK_BUCKET_DEG` = **30 deg = 1800
  arcmin**, by construction, at any range;
- Stage 3b-i's cross-range budget: `LOWRES_ANGULAR_RADIUS_RAD / M` = `0.003/4` = 0.00075 rad =
  **2.58 arcmin**, at any range;
- ratio **~700:1**, at *every* range.

In world space at the regression test's own geometry (target 1200 m out): jitter
`1200 * 2*sin(15 deg)` = 621 m against a cross-range budget of `1200 * 0.00075` = 0.9 m — the same
700:1. The implementation log measured ~700 m of real jump against ~1-7 m of budget and reached the
same number empirically. **Both quantities were already angular; expressing them in radians instead
of metres changes nothing.** They are different physical quantities (vocabulary granularity vs
optical resolving power) that a shared formula made look comparable, and no representation makes
them the same.

**The regression is nevertheless fixed in this stage — by §3, not by the angular model.** Once the
gate stops being acuity-derived and goes back to the quantisation-derived figure it had before
`c625299`, it budgets the thing that is actually jittering, which is what BL-2.6 established.

**So: delete the `xfail(strict=True)` marker on
`test_contacts.py::test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` in this
stage and restore its plain assertion of one contact.** Rewrite the paragraph its docstring gained
in `c625299` to record what was learned rather than deleting it: that an acuity-derived gate is a
category error, and why. **No separate jitter budget is designed, and none is needed** — the
quantisation figure *is* the jitter budget, correctly derived, and always was.

#### 5. Counting — angular extent over unit width

Grid-binning goes. The implementer's finding that single-link cross-range sub-clustering was
provably dead was correct and remains correct; the grid-binning replacement escaped that trap but
carried a free parameter (the bin width) and a documented boundary artefact (three members reading
`OP_2UNITS`). **The angular model removes both, and makes the count a one-line derivation with no
free parameter:**

    extent_rad = max over member pairs of angular_separation_rad(observer, i, j)   # angular diameter
    unit_rad   = mean over members of angular_size_rad(member)
    n          = floor(extent_rad / unit_rad) + 1                                  # floor at 1

That is literally "how many unit-widths long is this blob, plus one" — the same disc geometry as
the merge predicate (S), read as an extent instead of a pairwise test, reusing the same two
functions. `count_bucket_for(n)` is unchanged.

Worked, at the plan's own headline geometry (twelve 7 m vehicles, 18.7 m spacing, 206 m row,
9 km range):

| geometry | adjacent pair sep | `unit_rad` | outcome |
|---|---|---|---|
| perpendicular to LOS | 7.1 arcmin | 2.67 arcmin | separable -> **12 contacts**, each `OP_1UNIT` |
| along LOS, ownship 200 m AGL | 0.16 arcmin | 2.67 arcmin | merges -> **1 contact**; extent 1.75 arcmin, ratio 0.66 -> **`OP_1UNIT`** |
| along LOS, ownship 1000 m AGL | 0.78 arcmin | 2.67 arcmin | merges -> **1 contact**; extent 8.61 arcmin, ratio 3.22 -> **`OP_TO5UNITS`** |

Three things worth naming in that table:

- **`OP_1UNIT` for the 200 m AGL column is the correct answer, reported confidently, and this
  design says so rather than engineering around it** (requirement 6). Twelve vehicles nose-to-tail
  at 9 km subtend two thirds of one vehicle's width — they *are* one dot. The model states one
  unit at full confidence; it is not hedging and has nothing to apologise for. The honest boundary
  invariant this plan opened with is being *honoured* here, not worked around.
- **The last row is the argument for including ownship altitude**, and the test that proves it:
  identical world geometry, different ownship altitude, different honest count — because from
  higher up the column genuinely does spread out across the depression axis. No world-space ellipse
  can produce that.
- The user's two degradation laws are both present. **Magnitude**: `count_bucket_for`'s ladder
  widens upward, so the same fractional error in `n` lands in a coarser bucket the larger `n` is —
  Weber over a subitizing floor, already ED's shape. **Crowding**: tighter packing means a smaller
  `extent/unit` ratio for the same true count, so a dense group undercounts. Range degradation
  enters at the *merge* boundary (more units merge into one blob as range grows), which is the
  honest place for it, rather than as a second decay applied to the count.

`floor`, not `round`, deliberately: it is the conservative reduction ("at least this many unit
widths fit"), it makes the 200 m AGL row come out at `OP_1UNIT` robustly rather than by a rounding
coincidence at 0.66, and it preserves the implementer's finding 2 (a two-member cluster reports
`OP_1UNIT`) as a *theorem* of the merge criterion rather than an artefact — two candidates merge
only when their separation is under one mean unit width, so `floor(<1) + 1 = 1` always.

#### 6. Where the deferred cues would attach

One line each, then dropped: **occlusion** is an additional merge reason inside the same predicate
(a near candidate's angular disc containing a far one), not a new mechanism; **movement** is a
separability *override* on the same predicate (differing angular rates split a blob that geometry
merged), needing per-member velocity on `ClusterCandidate`; **shape and colour** attach to
`_build_cluster`'s aggregate-label path, never to the merge predicate.

#### 7. Implementation order

1. `perception/clustering.py`: add `angular_separation_rad` / `angular_size_rad`, replace the merge
   test with (S)+(A), replace `_count_cross_range_subclusters` with §5's extent/unit count, delete
   everything in §2's deletion list, move the bucket table out.
2. `perception/naked_eye_source.py`: `ClusterCandidate` gains `alt_m`/`size_m` at
   `_cluster_candidate`; pass `ownship_state` to `cluster_candidates`.
3. `belief/association_over_time.py`: revert to `c625299^` for `_naked_eye_uncertainty_m`,
   `uncertainty_radius_m`, `spatial_gate_radius_m`, `passes_gate`; take in the bucket table.
   `git show c625299^:...` is the reference, but re-read the module docstring afterwards — it
   describes a gate that no longer exists.
4. Tests, per §8. **Every re-derived assertion writes its geometry out in the test** — angular
   separation and mean unit width in arcmin, not just the expected number. Same merge criterion as
   3b-i, and for the same reason: these are the assertions that were previously right for the
   wrong reason.

#### 8. What the affected tests assert afterwards

- **`test_calibration_cluster_merge_undercount.py` — the three-row table in §5 becomes three
  tests**, replacing the two split out in `c625299`. The perpendicular case (twelve contacts) and
  the along-LOS case (one contact, `OP_1UNIT`) stay; the **new third test is the same along-LOS row
  at 1000 m AGL reading a plural count**, which is the one that pins the altitude term. The
  close-range six-group test keeps its shape but its fixture must be re-derived: the
  `_GROUP_CROSS_STEP_M = 0.3 m` chaining spacing was built for the acuity radius (~0.375 m at
  500 m) and is now measured against unit width (~7 m at 500 m), so those groups will merge
  differently. Re-run, do not re-predict.
- **The twelve-object test's along-LOS `OP_1UNIT` result is an assertion of correct behaviour, not
  a tolerated limitation, and the test's docstring must say that.** It is requirement 6's pin.
- **`test_mock_flight_chain.py` — expect this to change more than `c625299` did, and re-derive it
  by running the fixture.** The fixture's own numbers say why: ownship sits at 700 m MSL with both
  objects at 500 m, i.e. **exactly the correction's worked case** (a 400 m pair, 200 m up), and
  objects 101/102 are along-LOS at `z=0`. Under (S) the pair's depression separation is ~107 arcmin
  at 2 km against a mean unit width of ~5.8 arcmin (`Ural-375` 5.0 m, `Infantry AK` 1.8 m), and
  ~3.2 arcmin against ~1.3 arcmin even at 9 km — **separable at every range in this fixture**. So
  the merged-cluster phase across polls 0-13 disappears, observation count rises above 42, and
  `CONTACT_1`'s cardinality holds `OP_1UNIT` throughout instead of contradicting to the hull `(1,2)`
  at poll 14. Contact count should stay **2** (Stage 3a's exclusion founds both at the first poll
  both are detected; from the next poll each carries its own continuity and never reaches the
  gate) — but confirm by running, per this test file's own convention. The long derivation comment
  is rewritten around angular separation, not bucket steps.
- **`test_two_real_objects_stay_two_contacts` (strict `xfail`) is expected to flip to passing**, for
  the reason above — this is the geometry the plan's blast-radius section refused to predict, and
  the fixture's altitudes now settle it. Verify, then remove the marker; if it does not flip, that
  is a finding, not a number to tune.
- **`test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts`** — `xfail` marker
  deleted, plain `len(store.contacts) == 1` restored (§4).
- **`test_association_over_time.py`** —
  `test_naked_eye_ellipse_derived_from_acuity_and_quantisation_bucket` reverts to the pre-`c625299`
  `test_naked_eye_uncertainty_derived_from_quantisation_buckets`, asserting the single scalar.
- **`test_clustering.py`** — the geometry tests were re-derived onto a down-range-only axis in
  `c625299` specifically to avoid the anisotropy; they can go back to plain separations now, since
  there is only one predicate. Delete
  `test_chained_cluster_with_real_cross_range_extent_reports_a_plural_count` and replace it with a
  direct extent/unit count test (a chain whose angular diameter spans several unit widths). Add the
  **self-consistency test for (A)**: for a candidate at its own detection-range limit, (A) is
  satisfied whenever (S) is — the floor is provably slack.
- **`test_contacts.py`'s two Stage 3a tests and `test_cross_channel_fusion.py` must pass
  untouched** — that is this stage's narrowness guard for the dead zone and for cross-channel
  fusion, and if either moves the gate revert was implemented more broadly than designed.

#### 9. How the two closed bugs stay closed

- **BL-2.6's duplicate-contact bug**: its fix was symmetric both-sides budgeting in
  `spatial_gate_radius_m`, and §3 restores that function byte-identically to its pre-`c625299`
  form, which is the form that carried the fix. Its own regression test comes off `xfail` and
  passes again as the direct check.
- **The Stage 3a dead zone**: closed by the same-source/same-poll candidate exclusion in
  `ContactStore.ingest`, which this stage does not touch, and which does not depend on any radius
  (§3). Its two unit tests pass untouched.

#### 10. Risks this stage carries forward

- **`size_m` is now load-bearing for clustering, and `object_model.DEFAULT_SIZE_M` (5.0 m) is the
  fallback for every unmatched `object_type`.** Previously size only set detection range; it now
  also sets the merge boundary, so a mis-sized profile merges or splits groups. Cheap to check and
  worth one line in the sortie notes, not a redesign.
- **`size_m` is a *characteristic* size, not a silhouette width**, and (S) treats it as a disc
  diameter. A 7 m tank seen end-on is narrower than seen broadside. That is exactly the deferred
  shape cue; the isotropic-disc reading is the honest approximation until it lands.
- **A wide gate over finely-resolved neighbours is a new ambiguity exposure.** Twelve contacts
  18.7 m apart at 9 km all sit inside one another's restored gate radius (~2.3 km cross-range). It
  is not reachable while continuity holds (the gate is the exception path) and it is **bounded, not
  a runaway** — a contact founded through ambiguity carries its own continuity from the next poll.
  But on a long occlusion followed by reacquisition, a resolved group can double once. Watch for it
  on the sortie; **do not pre-engineer a fix.**
- **The 200 m AGL along-LOS column comes out at a ratio of 0.66, not 0.1** — one-and-a-half times
  from flipping to `OP_2UNITS`. The right answer sits near a boundary there, so the sortie should
  check the *column* case specifically rather than assuming the headline result is robust.
- **(S) has one reduction choice that is not derived**: sum-of-radii ("the discs touch") rather
  than max-of-radii ("one centre inside the other"). Sum is the more generous merge. If the sortie
  shows over-merging, this is the dial — a choice of reduction, not a new constant.

#### 11. Effort / value — what survives from the ellipse

Most of `c625299`'s *structure* survives (union-find, continuity resolution, cluster shape,
`count_bucket_for`) and all of its *geometry* goes. That is the right split: the ellipse's lasting
contribution was proving two things that this design depends on and would otherwise have had to
discover again — that re-testing the merge predicate over its own members is provably dead (which
is why §5 counts extent rather than re-partitioning), and that an acuity-derived gate produces a
700:1 mismatch against reporting jitter (which is why §3 unpicks Decision 7). The diff is a
deletion-heavy rework of two modules, smaller than `c625299` itself, and it removes the stage's
only uncalibrated constant rather than deferring it.

#### 12. Second-order effect

Stage 3b-ii loses its headline reason to fly — the acuity magnitude is no longer load-bearing (§1)
— and gains a sharper one: whether the *detection* threshold and `size_m` profiles produce merge
boundaries that match what the pilot sees. Stage 5 (composition) gets easier, because a cluster's
members are now merged on a criterion that is genuinely about visual overlap, so "some of them are
tanks" describes a real blob rather than an ellipse artefact.

### Addendum: what rev.2's implementation found that its design missed (2026-09-18)

Recorded so a future stage touching this test surface does not rediscover it.

- **`test_naked_eye_source.py` was absent from the design's test-impact list**, and needed five
  tests reworked. Cause: its fixtures place candidates at the same bearing and altitude, which
  under the angular predicate is a *degenerate always-merge* case — the separation is zero by
  construction. Those fixtures had been exercising the cap, debounce and continuity paths through
  incidental geometry that the ellipse tolerated and the angular model does not. Any future change
  to the separability predicate should expect this file to move with it.
- **`test_two_real_objects_stay_two_contacts` does not exist**, though the design named it as an
  xfail expected to flip. Review traced it through git history: it was folded into
  `test_mock_flight_chain_single_threaded_reaches_expected_contact_state` by commit `de5e7eb`,
  predating this whole ellipse/angular sequence. Not a silent deletion — but the design was written
  against a test list that was already stale, which is the more useful lesson.
- **One assertion was dropped without replacement** in
  `test_a_cluster_splitting_gives_the_majority_child_continuity`: the majority child's
  `count_bucket == "OP_2UNITS"` check. Under the angular model both the 3-member and 1-member
  children report `OP_1UNIT`, so the count no longer distinguishes them and the test identifies
  them by position instead. The test's actual purpose — continuity on split — is unaffected, but
  the count assertion is genuinely gone rather than relocated.

### Settled: how a group is spoken (user, 2026-09-19) — Stage 4b's vocabulary

Explored before implementation by putting three candidate phrasings of the same situation side by
side. The user chose the **hedged** register throughout, and added a constraint the options did not
anticipate.

**1. Vague by default. "Several", not "six".** A plural group is *"several contacts, eleven
o'clock, two kilometres"*. `OP_TO5UNITS` is *"a handful"*, `OP_MORETHAN15UNITS` is *"many"*. The
count leads the callout, because the number of things is what changes the pilot's decision — but it
leads as a vague quantity, not a figure.

**2. Precision only when it is both available and useful.** An exact number is spoken when the
model actually holds one *and* the count matters — the user's example is *"how many targets
remain"*, where the difference between two and one is the whole point. Precision is not the default
reward for close range; it is earned by the question being asked.

**3. Count precision must track classification specificity.** This is the constraint the options
missed, and it is load-bearing. The user's progression:

> *"tanks and IFVs"* → *"2 tanks, IFVs and trucks"* → *"2 T-72's, 2 BMP-2's, trucks"*

Exact counts appear **only** beside firm identification. "Trucks" stays uncounted while "2 T-72's"
is exact, *in the same sentence*. So the rule is: **never pair a precise count with a vague class,
or a vague count with a precise type.** A confident "six" attached to "contacts" claims a
resolution the channel did not have; a vague "several" attached to "T-72" throws away one it did.
The two ladders — `classification.SpecificityLevel` and the count buckets — must be spoken at
matching rungs.

Note this mostly *lands* in Stage 5 (composition), since per-member counts are what it describes.
But it constrains Stage 4b now: the count vocabulary must be designed so that its vague rungs pair
naturally with `presence`/`class`, and its exact rungs only become reachable at `type`.

**4. Cardinality-change announcements are a non-issue at this register.** With vague buckets, a
count moving from "several" to "a handful" is not worth interrupting for. The interesting
progression is *identification* refining, which is Stage 5's. `CONTACT_CARDINALITY_CHANGED` should
therefore exist as an event but be spoken sparingly, if at all, until composition lands.

**5. The contact-report wording fixes stay out of Stage 4b** (spelling out metres/kilometres,
acronym spacing, "very close" under 0.5 km). They are the immediate next step, deliberately
separate, to keep 4b's scope clean and preserve its regression guard that singular output stays
byte-identical.

### Settled: attention earns precision (user, 2026-09-19)

Two additions after hearing Stage 4b's output rendered.

**1. Two or three is "a couple of", not "several".** Carries its own connector
for the same reason `"a handful of"` does.

**2. A watched or tracked contact gets a detailed report, including an exact unit count.** The
user: *"a group of watched/tracked contacts is, for whatever reason, more important and should get
more detailed reports, including unit counts."*

This resolves something the Stage 4b design had recorded as unreachable. It cut exact counts on the
grounds that *precision-on-demand needs a caller holding a question, and none exists*. **One did,
under another name**: `Contact.attention`. A `watch` or `priority` mark is the crew deliberately
saying this one matters — which is exactly the "useful" half of the standing rule that precision is
spoken only when it is both *available* and *useful*. Attention is the usefulness signal; it was
already in the facts payload.

The honesty condition is unchanged, and this is the part to preserve if the rule is ever extended:
an exact number is spoken **only when the belief itself is exact** (`lo == hi`). A watched contact
whose interval is 4-5 still says *"a handful of"*. So **attention buys disclosure of precision
already held, never manufactured precision** — which keeps the no-omniscience invariant intact
while making Petrovich more useful about the things the crew asked him to watch.

One bound, from the same reasoning rather than a tuned constant: above twelve the hedge resumes
even when attended and exact, because a crew member who says *"seventeen"* about vehicles he is
looking at is claiming a count nobody makes by eye. Exactness in the model does not make a number
sayable if no human would say it.

### Settled Decisions (user, 2026-09-18) — Stage 3b escalations

6. **Geometry decides, not range.** Twelve units in a row perpendicular to the line of sight
   resolving as twelve contacts at 9 km is the wanted behaviour; along the line of sight they
   still merge into one contact carrying a plural count. Accepted with its consequence stated: it
   partly inverts this plan's motivating example, meaning much of the observed defect was the
   broken radius rather than a missing group model. **Cardinality still earns its place** — for
   along-LOS columns, tight formations, and infantry too small to detect individually — but the
   headline case shrinks, and Stage 5's value should be re-judged after flying rather than assumed.
7. **RETIRED 2026-09-18 by "Stage 3b-i rev.2" above, §3** — its premise (that an
   isotropic gate reopens the Stage 3a dead zone) does not hold: Stage 3a closed that dead zone
   with a radius-independent exclusion rule. Kept here for the record. ~~The anisotropy extends
   into the belief gate.~~ `association_over_time.uncertainty_radius_m`
   calls `naked_eye_cluster_radius_m` directly, so leaving the gate isotropic would re-open exactly
   the Stage 3a dead zone. This edits a gate now fixed three times, which is accepted deliberately;
   the mitigating find is that both call sites already carry the observer position, so it is a
   signature change with no new plumbing.

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


---

### Stage 4b design — speech and events (2026-09-19)

Expands the Implementation Plan's one-paragraph Stage 4b sketch into an implementable design,
against "Settled: how a group is spoken" above, which is binding and not re-litigated here.
Everything below reads `Contact.cardinality`/`Contact.classification` — the aggregate beliefs
Stages 1-4a already produce. No per-member breakdown exists yet (that is Stage 5's `composition`),
so this design can only ever say *one* count about *one* class — "several armor" — never "tanks
and IFVs." That is the correct shape for what 4b has data for, not a shortfall against Stage 5.

**Deliberate scope cut, stated up front so it is not rediscovered as a gap:** *this stage never
speaks an exact number.* Settled decision 2 ("precision only when available and useful") describes
a future capability — a caller that has an actual question in hand ("how many targets remain") and
therefore knows precision is wanted. No such caller exists yet; `render_contact_report` and the
lifecycle templates are passive callouts, not answers to a question. Building a "sometimes exact"
branch here with nothing to drive it would be inventing the trigger condition rather than
implementing one, and would risk exactly the vague/precise mismatch settled decision 3 forbids by
accident. **The vocabulary below is designed so every rung stays vague on purpose, and it is
structurally impossible for it to misfire into a precise count paired with a vague class — because
it never emits a precise count at all.** Precision is Stage 5's to add, once there is a per-member
count to be precise *about* and a caller that asked. This is the one place this stage's scope was
checked against growing past "make five stages of invisible work audible," per the plan's own
effort/value framing — it does not.

#### 1. The `CountBucket` → phrase ladder, and where it applies

`_cardinality_phrase(lo: int, hi: float) -> str | None`, in `belief/speech.py`:

| held interval | phrase |
|---|---|
| `(1, 1)` — `OP_1UNIT`, or any refinement that lands back on exactly one | `None` (no clause at all — see §2) |
| `lo >= 16` — `OP_MORETHAN15UNITS`, and any wider hull whose floor is that high | `"many"` |
| `lo == 4 and hi <= 5` — `OP_TO5UNITS` exactly, or a narrower refinement inside it | `"a handful"` |
| everything else plural — `OP_2UNITS`, `OP_3UNITS`, `OP_5TO7UNITS`, `OP_8TO10UNITS`, `OP_ABOUT15UNITS`, `OP_GROUP`, and any fold-derived interval (an intersection or a contradiction hull) that matches none of the rows above | `"several"` |

This is deliberately **not** a lookup table keyed on `CountBucket.name`. A folded interval need not
equal any one named bucket (`_cardinality_facts` already documents this for `lo`/`hi`, and
`fold_cardinality`'s intersection/hull cases are exactly what produces it) — so the function reads
off `lo`/`hi` magnitude directly, the same way `_cardinality_facts` itself does, rather than trying
to re-derive a bucket name from an interval that might not have one. The two named exceptions
(`"a handful"`, `"many"`) are picked out by the exact numeric ranges ED's own bucket boundaries
describe; everything else — including a not-quite-matching fold result — collapses to the safe
default `"several"`, which is never wrong to say about any plural count.

**Sayable at every specificity level, by construction.** Because the phrase is always a hedge and
never a number, it cannot overclaim regardless of whether `Contact.classification` sits at
`presence`, `class`, or `type` — settled decision 3's pairing rule ("never pair a precise count
with a vague class, or a vague count with a precise type") is satisfied trivially, since one side of
that pairing never happens here. A `type`-level contact with a plural cardinality is a real,
reachable case even before Stage 5 (a naked-eye cluster whose members are all individually
ground-truth-identified to the same type still clusters and still carries a real member count,
per `naked_eye_source.py`'s aggregate-label rule) — it speaks `"several T-72"`, not `"3 T-72's"`.
That grammatical roughness (no plural inflection on a raw DCS type string) is intentional: settled
decision 5 keeps wording fixes like this out of 4b, and inventing a pluralization rule for arbitrary
type strings is exactly that class of fix.

#### 2. The regression guard: singular output is a different code path, not a conditional inside one

`facts["cardinality"]` is **absent** (not present, not `None`) whenever `Contact.cardinality` is
still the lattice root `UNKNOWN` — `_cardinality_facts` already guarantees this. Every contact is
seeded with a real claim at founding (`OP_1UNIT` when its founding percept carries no count
evidence), so in practice this fact is present on every contact `_contact_report_text` ever sees.

`_contact_report_text` gains one guard at its top, and nothing else about its existing body changes:

```python
def _contact_report_text(facts: dict[str, object]) -> str:
    classification = facts["classification"]
    assert isinstance(classification, dict)
    cardinality = facts.get("cardinality")
    phrase = None
    if isinstance(cardinality, dict):
        phrase = _cardinality_phrase(cardinality["lo"], cardinality["hi"])
    if phrase is None:
        text = _unit_type_display(classification.get("value"), classification.get("level"))
    else:
        text = f"{phrase} {_plural_unit_type_display(classification.get('value'), classification.get('level'))}"
    # ... everything from here down (relative_now clause, semantic fragment, trailing ".") is
    # byte-identical to the current function -- unchanged.
```

`phrase is None` covers both routes back to the old text: no `"cardinality"` fact at all, and a
present fact whose interval is `(1, 1)`. **On that path the function calls the exact same
`_unit_type_display` it calls today, with the exact same arguments, and executes no new code.**
This is the "early return" the task asked for, phrased as a branch rather than a literal early
`return` only because the trailing clock/range/semantic logic is shared by both branches and must
not be duplicated — duplicating it would itself be a regression risk (two copies of the
range-rounding/semantic-fragment logic to keep in sync). The new `_plural_unit_type_display`
function is never called, and `_cardinality_phrase` is never called with anything that could change
its result, on the singular path — so every existing `test_speech.py` assertion is the guard, and
the implementer's job is to run the full existing suite unmodified first and confirm zero diffs
before writing a single new plural-case test.

`_plural_unit_type_display` is `_unit_type_display`'s plural sibling, used only when `phrase` is not
`None`:

```python
_OP_CLASS_DISPLAY_PLURAL: Final[dict[str, str]] = {
    "OP_ARMORED": "armor",      # already a mass noun -- singular form doubles as plural
    "OP_TRUCK": "trucks",
    "OP_INFANTRY": "infantry",  # mass noun
    "OP_SRSAM": "SAMs",
    "OP_MRSAM": "SAMs",
    "OP_SPAAG": "AAA",          # mass/acronym -- unchanged
    "OP_ZU23": "AAA",
    "OP_SHIP": "ships",
}

def _plural_unit_type_display(value: object, level: object) -> str:
    if level == "type" and isinstance(value, str) and value:
        return value  # unpluralized on purpose -- see Sec 1's "sayable at every level" note
    if level == "class" and isinstance(value, str) and value:
        return _OP_CLASS_DISPLAY_PLURAL.get(value, value)
    return "contacts"  # presence and unknown/fallback levels both collapse here
```

The `presence`/fallback branch returning `"contacts"` is what produces the user's own worked
example verbatim — `"several contacts, eleven o'clock, two kilometres."` — and is a deliberate
divergence from `_unit_type_display`'s singular-case `"ground"`/`"contact"` split: a bare "ground" or
"contact" doesn't pluralize sensibly, and "several ground" reads wrong where "several contacts"
reads right. This divergence is confined to the plural path only; the singular path's `"ground"`
wording is untouched, per §2's guard.

#### 3. Where the clause attaches

`_contact_report_text` is shared by:

- `render_contact_report` (player-initiated `describe_contact`) — gains the clause.
- `_render_lifecycle_text`'s `CONTACT_DETECTED`/`CONTACT_REACQUIRED` branches — gain the clause,
  automatically, since both call `_contact_report_text` directly.
- `render_watch_nearest_readback` — gains the clause for free, same reason (it calls
  `_contact_report_text(facts)` and prepends `"Watching "`).

**Does not gain the clause:** `_render_lifecycle_text`'s `CONTACT_CLASSIFICATION_CHANGED` branch.
It builds its own line (`"unit at {clock} o'clock, {range} km is {unit type}."`) directly from
`_unit_type_display`, not through `_contact_report_text` — so it is untouched by this stage by
construction, not by an added exclusion. Leaving it untouched is also the right call on its own
merits: settled decision 4 says a bare cardinality move is not worth interrupting for, and a
classification-change callout that also started speaking a count every time would be volunteering
exactly that kind of unrequested cardinality chatter on an event about something else entirely.
`render_readback`, `render_scan_readback`, `render_cancel_readback` never touch a contact's facts
at all and are unaffected.

#### 4. The `OP_GROUPSOMETHING` display-table entry: dead code, not a live collision

Checked against `_unit_type_display`'s actual branch order before writing a fix: `level == "class"`
is tested *before* `level == "presence"`, and `classification.py`'s `_op_class_of` explicitly
excludes `object_model.DEFAULT_OP_CLASS` (`"OP_GROUPSOMETHING"`, also `classification.
PRESENCE_CLASS` — the same string) from ever being returned as a class-level value
(`if profile.op_class == object_model.DEFAULT_OP_CLASS: return None`). So
`_OP_CLASS_DISPLAY["OP_GROUPSOMETHING"] = "group"` is **unreachable today**, at both levels: a
presence-level classification is caught by the `level == "presence"` branch before the dict is ever
consulted, and a class-level classification can never hold the value `"OP_GROUPSOMETHING"` in the
first place. The plan's original framing (`OP_GROUPSOMETHING` doubling as a class-level "group"
token) does not hold up against the actual code path — there is no live mis-statement to fix by
disambiguating a collision, only a dead table entry to delete.

**Fix: remove the `"OP_GROUPSOMETHING": "group"` line from `_OP_CLASS_DISPLAY`.** Disambiguation of
"something" vs. "a group of somethings" at presence level is now handled structurally, the way §2
already does it: a singular presence-level contact still says `"ground"` (unchanged), a plural one
says `"several contacts"` / `"a handful of contacts"` / `"many contacts"` via
`_plural_unit_type_display`'s presence/fallback branch. No dict entry does this work; the cardinality
belief does. `_OP_CLASS_DISPLAY_PLURAL` (§2) correspondingly has no `"OP_GROUPSOMETHING"` entry
either, for the identical reason.

#### 5. `CONTACT_CARDINALITY_CHANGED`

**Event kind, added to `belief/events.py`:** `CONTACT_CARDINALITY_CHANGED: Final[EventKind] =
"CONTACT_CARDINALITY_CHANGED"`, joining the closed `EventKind` literal. `Event` gains two more
optional fields, mirroring `previous_classification`/`classification`'s existing shape exactly (both
default `None`, populated only by this kind, every other kind's construction site untouched):
`previous_cardinality: tuple[int, float] | None = None`, `cardinality: tuple[int, float] | None =
None` (a `(lo, hi)` pair — no reason to invent a richer shape than the two numbers a console/debug
reader needs, and `CardinalityBelief` itself isn't reused directly since `Event`'s other belief
snapshots are already plain values, not the belief dataclasses).

**Emit condition, in `belief/contacts.py`'s `ContactStore.tick`:** a new `cardinality_event`
function in `events.py`, `classification_event`'s direct analogue:

```python
def cardinality_event(
    previous: tuple[int, float] | None, current: tuple[int, float]
) -> EventKind | None:
    if previous is None:
        return None  # first tick -- nothing to compare against yet, same posture as
                      # classification_event's own first-tick case
    if previous == current:
        return None
    return CONTACT_CARDINALITY_CHANGED
```

`Contact` gains `last_emitted_cardinality: tuple[int, float] | None = None`, `last_emitted_
classification`'s direct sibling. In `tick()`, insert a fourth block with the **same shape** as the
existing classification block, in this position: **lifecycle → classification → cardinality →
attention** (extending the tick docstring's already-documented ordering sentence by one entry,
inserted between classification and attention since both cardinality and classification are
identity-shaped beliefs about what/how-many, and attention's own event should still see the
contact's fully up-to-date facts first):

```python
current_cardinality = (contact.cardinality.lo, contact.cardinality.hi)
cardinality_kind = cardinality_event(contact.last_emitted_cardinality, current_cardinality)
if cardinality_kind is not None and self._cooldown_elapsed(
    contact, CONTACT_CARDINALITY_CHANGED, now_sim
):
    self._events.append(
        Event(
            id=self._new_event_id(),
            contact_id=contact.id,
            kind=CONTACT_CARDINALITY_CHANGED,
            t_sim=now_sim,
            certainty=current_certainty,
            previous_cardinality=contact.last_emitted_cardinality,
            cardinality=current_cardinality,
        )
    )
    contact.last_event_emitted_sim[CONTACT_CARDINALITY_CHANGED] = now_sim
contact.last_emitted_cardinality = current_cardinality
```

**Cooldown: the existing `EVENT_COOLDOWN_S` / `_cooldown_elapsed` machinery, unchanged, keyed on this
new kind like every other.** No second suppression mechanism, no new constant — this was already
the plan's own stated intent ("existing `EVENT_COOLDOWN_S` machinery reused unchanged") and nothing
in the design above needed a different one. Note `_cooldown_elapsed` only gates *emission*; the
`last_emitted_cardinality` snapshot updates every tick regardless (identical to every other kind's
snapshot), so a rapid string of narrow/widen/narrow transitions during one cooldown window is
correctly collapsed to "whatever it is now" once the cooldown lifts, not replayed.

**`route_event` gives it no template, joining `CONTACT_LOST`/`CONTACT_ATTENTION_CHANGED`'s existing
pattern.** `_render_lifecycle_text` gains one more `if event.kind == CONTACT_CARDINALITY_CHANGED:
return None` branch (or simply falls through to the function's existing final `return None`, since
no other branch matches it — either is fine, the explicit branch is slightly more legible about
intent and is what should be written). This is settled decision 4's own instruction ("should exist
as an event but be spoken sparingly, if at all, until composition lands") applied via the module's
existing no-template mechanism, not a new one: the event is real, logged, visible to `poll_events`/
the debug console/a future brain, and simply never renders to speech. Per the existing convention a
kind with no template is **never acknowledged** by `route_event` (it returns `None` before reaching
`acknowledge_event`) — so an unspoken cardinality change stays in `unacknowledged_events` for
whatever consumer eventually wants it (the debug console via `get_events`, or a future brain), the
same posture `CONTACT_LOST` and `CONTACT_ATTENTION_CHANGED` already have.

#### 6. The count-arithmetic fix

Three sites conflate "how many `Contact` records exist" with "how many units we believe exist,"
per the task's framing. One shared helper, added to `tools.py` next to `get_stats`:

```python
def estimated_units_lower_bound(store: ContactStore) -> int:
    """The honest floor on total unit count -- sum of every contact's own
    cardinality floor (`Contact.cardinality.lo`). Deliberately a lower bound,
    not a point estimate: summing `.hi` is not meaningful when any contact
    holds `OP_MORETHAN15UNITS` (`hi == math.inf`), and reporting a floor
    rather than a guessed midpoint matches this stage's hedged-register
    posture (Sec 1) -- "at least this many units," never a fabricated precise
    total."""
    return sum(contact.cardinality.lo for contact in store.contacts)
```

- **`get_stats`** (`tools.py`) gains one key: `{"observations": ..., "contacts": ..., "events": ...,
  "estimated_units": estimated_units_lower_bound(store)}`. `contacts` keeps its existing meaning
  (record count) unchanged — it is a real, useful number (how many distinct tracked things), just
  not the same number as unit count, and both are now available side by side rather than the
  ambiguous single figure standing in for both.
- **`get_situation`** (`tools.py`) gains `facts["estimated_units"]` as a **new top-level key**, not
  nested inside `facts["contact_counts"]`. Checked against the existing tests before choosing this
  shape (`test_get_situation_counts_and_position_summary_with_no_contacts` and others assert
  `facts["contact_counts"] == {"total": ..., "visible": ..., "watched": ...}` by full dict equality)
  — nesting the new figure inside that dict would force every one of those exact-equality
  assertions to change for a fact they are not testing. A sibling top-level key extends `facts`
  additively, the same absent-not-null-elsewhere convention this module already uses for
  `mission_phase`/`highest_attention_contact`, and leaves `contact_counts`'s existing shape and every
  test asserting it untouched. The human `summary` sentence is **not** touched — wording changes to
  the spoken/summary text are explicitly out of this stage's scope (settled decision 5), and this
  fix is about the underlying data being right, not about how it reads.
- **`escalation._situational_header`** gains `header["estimated_units"] = estimated_units_lower_
  bound(store)`, always present (unlike `our_position`, which is gated on `enrichment` being
  supplied — unit count needs no ownship data, so it is unconditional). `header["contact_counts"]`
  keeps its existing bare-int shape (`len(store.contacts)`) rather than being reshaped into a dict —
  same reasoning as `get_situation` above: `test_situational_header_omits_our_position_without_
  enrichment` asserts `header["contact_counts"] == 0` directly, and reshaping that key for a fix
  this task scoped as "add the missing figure," not "restructure the existing one," would be scope
  creep against its own stated purpose.

#### Test list

The implementer must verify every name below against the actual suite before relying on it (per
this task's own instruction) — names are given as precisely as this design can make them, but only
`test_speech.py`'s existing test names (confirmed already, by reading the file directly for this
design) and `test_tools.py`'s `test_get_stats_counts_observations_contacts_and_events`/
`test_get_situation_counts_and_position_summary_with_no_contacts`/`test_get_situation_reports_
priority_contact_over_watched_and_visible` (confirmed the same way) are certain to exist as named.
The rest are new tests this stage adds and their exact names are the implementer's to choose,
following each file's existing naming convention.

**Regression guard — must pass unmodified, zero diffs, before any new test is written:**

- The entire existing `test_speech.py` suite (21 tests, confirmed present by direct read for this
  design): `test_render_readback_for_each_attention_level`,
  `test_render_readback_template_is_readback`, `test_render_contact_report_returns_none_for_unknown_
  contact`, `test_render_contact_report_follows_unit_type_clock_range_format`, `test_render_contact_
  report_maps_op_class_to_display_word`, `test_render_contact_report_maps_default_op_class_to_
  display_word`, `test_route_event_urgent_call_bypasses_the_gate`, `test_route_event_contact_
  detected_renders_classification_with_no_id`, `test_route_event_contact_detected_includes_clock_
  range_when_enriched`, `test_render_contact_report_includes_semantic_fragment_when_enriched`,
  `test_route_event_auto_acknowledges_a_rendered_event`, `test_route_event_contact_lost_has_no_
  template_and_is_not_acknowledged`, `test_route_event_contact_reacquired_renders_classification_
  with_no_id`, `test_route_event_classification_changed_speaks_position_and_new_type`, `test_route_
  event_classification_changed_omits_range_when_not_enriched`, `test_format_range_km_rounds_to_
  nearest_half_km_no_trailing_zero`, `test_format_range_km_boundary_cases`, `test_round_enrichment_
  fragment_rounds_trailing_distance`, `test_round_enrichment_fragment_passes_through_text_without_
  distance`, `test_route_event_attention_changed_has_no_template_and_is_not_acknowledged`, `test_
  route_event_returns_none_for_a_vanished_contact`. (Every fixture contact in these tests is founded
  through the normal `record`/`from_percept` path and so already carries `cardinality == OP_1UNIT`
  post-Stage-2 — confirm this is actually true of each fixture rather than assuming it; if any
  fixture's cardinality is not `(1, 1)`, that test's expected text changes and is not a clean
  regression-guard case.)

**New, `test_speech.py` (Sec 1-4):**

- A plural-cardinality contact report test per phrase row in Sec 1's table: default `"several"`
  (e.g. cardinality `(2, 2)` or `(3, 3)`), `"a handful"` (`(4, 5)`), `"many"` (`lo >= 16`), and one
  fold-derived non-named interval (e.g. an intersection like `(4, 7)`) asserting it falls back to
  `"several"`.
- One test per `_plural_unit_type_display` branch: presence level → `"contacts"`, a `class`-level
  value present in `_OP_CLASS_DISPLAY_PLURAL` (e.g. `OP_TRUCK` → `"trucks"`), a `class`-level value
  absent from the table (fallback to the raw value unchanged), and `type` level (raw string
  unpluralized).
- A test that `facts["cardinality"]` absent (root `UNKNOWN`) produces the old singular text —
  the second half of §2's guard, alongside the `(1, 1)` case already covered by the unmodified
  regression suite.
- A `CONTACT_DETECTED`/`CONTACT_REACQUIRED` test with a plural-cardinality fixture, confirming the
  clause reaches `route_event`'s lifecycle path, not just `render_contact_report` directly.
- A `render_watch_nearest_readback` test with a plural-cardinality fixture, confirming §3's "for
  free" claim.
- A `CONTACT_CLASSIFICATION_CHANGED` test with a plural-cardinality fixture confirming its rendered
  text is **unchanged** by this stage (still no count clause) — the negative case for §3's "does not
  gain the clause."
- `test_render_contact_report_maps_op_class_to_display_word`/`..._maps_default_op_class_to_display_
  word` (both in the existing/regression list above) should be re-read once `_OP_CLASS_DISPLAY`'s
  `"OP_GROUPSOMETHING"` entry is removed (§4) to confirm neither test actually exercised that entry
  (i.e. neither test's fixture uses a class-level `"OP_GROUPSOMETHING"` value, which by §4's own
  argument should be impossible to construct) — if one does, that is a finding about an existing
  test building an unreachable state, not a reason to keep the dead entry.

**New, `test_events.py` (§5):**

- `test_first_tick_with_no_previous_cardinality_emits_nothing` — mirrors `test_first_tick_with_no_
  previous_classification_emits_nothing`.
- `test_cardinality_interval_change_is_contact_cardinality_changed` — a narrowing (refine) and a
  widening (contradiction-hull) case, both firing the event; confirm `previous_cardinality`/
  `cardinality` on the resulting `Event` match.
- `test_unchanged_cardinality_emits_nothing` — mirrors `test_same_level_same_value_emits_nothing`.
- Cooldown suppression for this kind is **not** a required new test — `test_contacts.py`'s existing
  `test_event_cooldown_suppresses_rapid_reemission_but_not_after_it_elapses` already exercises
  `_cooldown_elapsed` generically (confirmed present); `cardinality_event` reuses that same gate with
  no kind-specific branching, so a second instance of the same test shape adds confirmation, not
  coverage. Optional, implementer's call.

**New, `test_speech.py`, for `route_event`'s no-template branch:**

- `test_route_event_cardinality_changed_has_no_template_and_is_not_acknowledged` — mirrors
  `test_route_event_contact_lost_has_no_template_and_is_not_acknowledged`/`test_route_event_
  attention_changed_has_no_template_and_is_not_acknowledged`, both confirmed present.

**Changed (breaks on purpose, per §6 — not a regression, the fix this stage makes):**

- `test_get_stats_counts_observations_contacts_and_events` (confirmed present, `test_tools.py`) —
  its `stats == {"observations": 1, "contacts": 1, "events": 1}` full-dict-equality assertion must
  gain `"estimated_units": 1`.
- `test_get_situation_counts_and_position_summary_with_no_contacts` (confirmed present) — add
  `assert facts["estimated_units"] == 0` alongside the existing `contact_counts` assertion (which
  stays unchanged, per §6).
- `test_get_situation_reports_priority_contact_over_watched_and_visible` (confirmed present) — add
  the equivalent `estimated_units` assertion for its two-contact fixture (value depends on each
  fixture contact's actual founding cardinality — derive it from the fixture, don't guess).
- `test_situational_header_omits_our_position_without_enrichment`/`test_situational_header_includes_
  our_position_with_enrichment` (both confirmed present, `test_escalation.py`) — each gains an
  `assert header["estimated_units"] == ...` assertion; `header["contact_counts"]`'s existing
  assertions are unchanged.
