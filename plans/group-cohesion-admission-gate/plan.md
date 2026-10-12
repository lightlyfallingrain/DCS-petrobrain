# BL-B58 — the cohesion admission gate

**BL-12 Stage 3.5**, on `feature/bl12-group-contact-identity` (written against `dcf38b4`).
Resolves `body-layer/ROADMAP/BL-B58.md`. The user chose **option 3 — fix at source in clustering**,
over option 1 (speech-time suppression) and option 2 (bound the fold's position displacement).
Their stated reason, which this plan holds itself to:

> group membership is what the rest of BL-12 and BL-14 build on — a wrong member poisons heading,
> composition and attack-run alignment, not just one spoken line.

**Why its own document rather than an amendment to `plans/group-contact-identity/plan.md`.** It
spans two modules (`contacts.py` *and* `groups.py`), carries its own staging, its own acceptance
tests and three open decisions, and would roughly double that plan's amendment section. A pointer
amendment (**A9**) goes into the BL-12 plan instead, updating A6's stage table — the existing
supersede-in-place convention, per `docs/PROCESS.md` "Superseding a decision".

---

### Goal

Stop `_cluster_contacts` from admitting a contact into a group on the strength of a gap that closed
because *another member's* fused position was moved by a Stage 3 ambiguity fold rather than by
anything either contact was observed to do.

---

## 1. The measurement that changes the design — BL-B58's own sketch is a no-op

`BL-B58` sketches the fix as *"excluding a newly-added member whose own gap to the pre-existing
cluster fails the same pair backstop `_cluster_contacts` already applies pairwise."*

**Measured: that check cannot fire, because the absorbing edge already passes that backstop.**
Replaying the 2C fixture and dumping every pair's gap, backstop and verdict at the absorption tick
(probe 1, `scratchpad/probe_b58_geometry.py`, run with
`body-layer/.venv/bin/python` and cwd `body-layer`):

```
=== t=8, before the fold   n=5  median_nn=147.8  relative_threshold=443.5
CONTACT_1-CONTACT_4       293.1 gap     88.0 backstop     88.0 thresh   .
  positions: CONTACT_1 (1500, 0)   CONTACT_4 (1242, 140)

=== t=12, after the fold   n=5  median_nn=124.6  relative_threshold=373.8
CONTACT_1-CONTACT_4        81.9 gap     88.0 backstop     88.0 thresh   LINK
  positions: CONTACT_1 (1324, 131)  CONTACT_4 (1242, 140)
  cluster ['CONTACT_1','CONTACT_2','CONTACT_3','CONTACT_4'] extent=329.9
```

Three facts follow, and each one kills a candidate design:

1. **The absorbing edge clears the existing pair backstop legitimately — 81.9 m against 88.0 m.**
   `_pair_backstop_m` is *already* applied to that edge. Re-applying it changes nothing. Any fix
   that re-runs the existing geometric test on the existing positions is a no-op by construction.
2. **The cause is a 219 m single-tick displacement of `CONTACT_1`** (1500,0 → 1324,131), with
   `CONTACT_4` stationary. The gap did not close because anything moved; it closed because the fold
   rewrote one belief.
3. **A cluster-extent bound cannot separate right from wrong here.** The four-member (wrong) cluster
   and the three-member (correct) cluster have **identical extent — 329.9 m**, because the widest
   pair is `CONTACT_2`–`CONTACT_3`, both infantry, both legitimately in the group. So the
   cluster-extent rule that `tests/test_groups.py::test_the_eager_cap_still_chains_a_long_infantry_line`
   anticipates (*"the fix is a cluster-extent rule, not a smaller cap"*) is the right instinct for
   *width*, and the wrong instrument for *this*.

**And the corrupted position persists.** t=15 shows `CONTACT_1` still at (1324,131). So **no
tick-local rule can fix this**: any test comparing this tick against the last one (displacement
plausibility, previous-position gap, per-tick movement bounds) merely delays the absorption by one
tick, after which the corrupted position *is* the previous position. Verified against t=15's dump:
the geometry is byte-identical to t=12's.

**Consequence for the plan.** The only durable gate at the clustering seam is one that carries
**provenance** — how much of a contact's current fused position is attributable to folds rather than
to its own observations. That is one new field, not new persistent store state, but it is written in
`contacts.py`, which `BL-B58`'s option-3 framing did not anticipate.

### Effort/value correction owed to the user

They chose on `BL-B58`'s cost line (*"most architecturally correct … and the most expensive —
touches the clustering mechanism this whole milestone's Stage 0 already revised once, and needs its
own review pass"*). Corrected:

| | quoted | measured |
|---|---|---|
| modules touched | `groups.py` | `groups.py` **and** `contacts.py` (the fold site, for provenance) |
| new calibration constant | implied none | **none** — the gate reuses the existing thresholds |
| new persistent store state | implied none | **none** — one float field on `Contact` |
| the sketched check | the fix | **a measured no-op** (§1.1) |

**Net: not materially more expensive — differently shaped.** One more file, one more field, and no
new number for the user to own. The honest correction is not the cost but the *description*: they
approved a re-check that does not work, and the fix that does work is a provenance mechanism
spanning two modules. Flagged here; the choice of seam stands and is not re-litigated.

---

## 2. The two open sub-questions — both answered by reproduction, neither deferred

### 2a. A second, independent incident — reproduced cleanly

`BL-B58` records that the Reviewer's attempt hit a different pre-existing continuity-merge path by
accident. A clean one, different geometry, different class mix, no 2C fixture
(probe 2, `scratchpad/probe_b58_second_incident.py`): three infantry in a ~95 m knot at 1,000 m,
a ZSU-23-4 195 m away and **continuously observed** for 20 s while the infantry are not re-observed;
then two fresh infantry percepts arrive 260 m to the flank and fold onto the group (Stage 3 branch 2).

```
=== t=20, before the fold   relative_threshold=195.6
  CONTACT_1-CONTACT_4       195.0 gap      78.0 backstop   .
  GROUP GROUP_1 members=['CONTACT_1','CONTACT_2','CONTACT_3'] air_defence=[]

=== t=20, after the fold    relative_threshold=169.0
  CONTACT_1-CONTACT_2       194.6 gap     169.0 thresh     .        <-- EVICTED
  CONTACT_1-CONTACT_4        63.8 gap      78.0 backstop   LINK     <-- ABSORBED
  GROUP GROUP_1 members=['CONTACT_1','CONTACT_3','CONTACT_4'] air_defence=[('OP_SPAAG', 1)]

=== t=30, persistence check -- byte-identical to t=20
```

So the mechanism is **not** an artifact of the 2C fixture's undeclared-uncertainty fallback path or
of its continuity merges. `CONTACT_1` moved 132 m, `CONTACT_3` 146 m.

### 2b. An actual air-defence contact as the absorbed member — reproduced, and worse than predicted

The same run answers it: `GROUP_1.air_defence_composition` goes `[]` → `[('OP_SPAAG', 1)]`. The
group now **asserts air defence it does not contain**, persistently.

**And the same single tick corrupts membership in the other direction too.** `CONTACT_2` — a real,
correctly-identified infantry member — was **evicted**, because the fold shifted the median
nearest-neighbour gap and the relative threshold dropped 195.6 → 169.0 while the
`CONTACT_1`–`CONTACT_2` gap grew to 194.6 m. `BL-B58` speculated *"in either direction"*; both
directions now fire in one incident.

This is the suppression case in miniature: had `CONTACT_2` been the air-defence member, the group
would have **stopped** reporting air defence. That is the direction `D6`'s carve-out exists to
prevent, and `D6` does not sit on this path (it gates the *fold's* candidate set; `CONTACT_2` is not
a candidate for anything).

**The eviction half is deliberately not fixed by this plan** — see §6 and the new backlog item
`BL-B59`, because fixing it means retention hysteresis against the *relative* test, which is a
second mechanism with its own calibration and reopens `BL-B50`. Bundling them would make the
mechanism/calibration split in §5 impossible to keep clean.

---

## 3. Where the check goes — `_cluster_contacts`, and why `reconcile` phase 1 is wrong

This is the central design judgement, so both sides are stated.

**`reconcile` phase 1 is the wrong seam, for three reasons, the third decisive:**

1. **Phase 1 does not form membership.** By the time it runs, `_cluster_contacts` has already
   returned `frozenset({CONTACT_1..4})`. Phase 1 only decides which remembered `Group` id that
   cluster inherits. The corruption is upstream of it; phase 1 is merely where it becomes *invisible*
   (the id is inherited, so nothing re-discloses and no gate fires).
2. **Excluding a member there means mutating a cluster the union-find produced.** `cluster_props` is
   a dict keyed on the `frozenset`, so a mutation invalidates the key; and removing a member can
   split the remainder into pieces, which would require re-clustering inside `reconcile`. That is
   either an inconsistent intermediate state or a second clustering pass.
3. **A phase-1 check misses the founding case entirely.** The same drift can make two
   previously-separate contacts cohere where *no* remembered group exists — that cluster resolves
   through **phase 3 (found)**, which a phase-1 gate never sees. Measured: in §2a, delete `GROUP_1`
   from the scenario and the identical drift founds a group containing the ZSU-23-4. A fix that
   closes only the inheritance path leaves the founding path open.

**`_cluster_contacts` is the right seam** because it is the single place where membership is
*decided*; it already owns the pair predicate (`_pair_backstop_m`), so the veto composes as one more
term in an existing comparison; and the union-find is exactly where a *per-edge* veto behaves
correctly — single-link still finds a clean path through an un-tainted member if one exists (proved
as Row F below), so one tainted member does not freeze a group's legitimate growth.

**What `_cluster_contacts` lacks is the prior rosters**, and they are supplied as an **explicit
parameter**, keeping it a pure function of its inputs. `GroupStore.reconcile` has them: at the point
it calls `_cluster_contacts`, `self._groups` still holds the *previous* reconcile's rosters, because
`reconcile` has not yet reassigned `self._groups`. Ordering confirmed by reading `ContactStore.tick`
— `ingest` (where the fold happens) runs before `tick` (where `reconcile` runs), so the provenance
written by a fold is visible to the very next clustering pass, which is the tick the absorption
occurs on.

---

## 4. What the check is

### The rule

`_cluster_contacts` gains one parameter, `prior_rosters: Sequence[frozenset[str]]`, and reads one new
`Contact` field, `fold_displacement_m`. For each candidate link `(i, j)`:

- **If `i` and `j` were co-members of one and the same prior roster** → the ordinary rule, byte-for-byte
  unchanged. *This is what makes the gate incapable of causing eviction churn.*
- **Otherwise** (an *admission*: at least one side is new to the other's group, or neither is grouped) →
  `effective_gap = gap + fold_displacement_m[i] + fold_displacement_m[j]`, compared against the same
  `min(relative_threshold, pair_backstop)` as today.

`fold_displacement_m` is **metres of fused-position displacement attributable to an ambiguity fold
since this contact was last recorded from an unambiguous percept.** It is written at the one call
site in `ContactStore.ingest` that folds (`fold_target is not None`) as
`hypot(position_after − position_before)`, and **reset to 0.0** on either unambiguous branch
(`continuity_by_observation_id` resolved it, or `len(passing) == 1`) — an independent look that
confirms the contact where we believe it to be is exactly the evidence that retires the doubt.

### The three sub-questions `BL-B58` left inside its own sketch

- **"What does *the pre-existing cluster* mean when membership is exactly what is in question?"**
  It is not a cluster. It is **the previous reconcile's group rosters** (`Group.member_contact_ids`)
  — the only membership statement that exists before this tick's clustering has run. The test is
  *pairwise co-membership in one roster*, never distance to an aggregate: a centroid test was
  measured and rejected (it breaks an incrementally-observed convoy tail, where each new member is
  one gap from its neighbour but many gaps from the centroid — the undermerging
  `plans/group-undermerging/` fixed).
- **"What happens to an excluded contact — own group, ungrouped, founded?"**
  **Nothing special, and that is the point.** The union-find simply does not take that edge; the
  contact lands wherever its remaining edges put it, and if it has none it is a singleton, dropped by
  `GROUP_REPORTING_MIN_MEMBERS` and reported individually. No new code path, no new group, no new
  state. Measured in Rows A and B below: `CONTACT_4` becomes ungrouped in both.
- **"Is the sketched pair-backstop re-check right?"** No — §1.1, measured.

### Why this currency and not position uncertainty

`Contact.position.radius_m()` was the obvious alternative and is wrong here. `plans/group-undermerging/debug.md`
already measured that budgeting uncertainty into this same pairwise test **over-merges** at close
range (one naked-eye look carries ~300 m RMS even at 500 m); and in these incidents uncertainty
argues the wrong way — at 213–300 m of RMS, `CONTACT_1` and `CONTACT_4` are not distinguishable in
position at all, which is an argument *for* merging. `fold_displacement_m` is narrower and
provenance-honest: it measures only the part of the position that no observation of *this* contact
supports.

### Measured: the candidate rule beside the current one, with invariant rows

Probe 3, `scratchpad/probe_b58_candidate.py` — reimplements only the predicate, calls the real
`_pair_backstop_m` / `_representative_size_m` / `profile_for` and reads the real `Final` constants.

| row | scene | current | candidate |
|---|---|---|---|
| **A** | 2C incident, t=12 | `[1,2,3,4]` | **`[1,2,3]`** — `CONTACT_1–CONTACT_4` eff. 301.6 vs 88.0, vetoed; `CONTACT_4` ungrouped |
| **B** | incident 2, t=20 | `[1,3,4]` | **`[1,3]`** — eff. 196.2 vs 78.0, vetoed; `air_defence_composition` back to `[]` |
| **C** | **invariant** — the pinned 1,200 m chained infantry line, first formation | `[I1,I2,I3,I4]` | `[I1,I2,I3,I4]` — **IDENTICAL** |
| **D** | **invariant** — three infantry at 30 m | `[I1,I2,I3]` | `[I1,I2,I3]` — **IDENTICAL** |
| **E** | **invariant** — an un-folded armour contact genuinely joins an armour pair | `[A1,A2,A3]` | `[A1,A2,A3]` — **IDENTICAL** |
| **F** | A1 carries a 130 m fold budget; A3 joins anyway via A2 | `[A1,A2,A3]` | `[A1,A2,A3]` — the A1–A3 edge is vetoed, single-link routes through A2 |

Row A's detail, which is the one a reviewer should check hardest — the two infantry edges that must
*not* change are the ones the gate exempts as prior co-members:

```
pair                         gap     eff   thresh  rule        cur -> new
CONTACT_1-CONTACT_2        127.7   127.7    372.9  ordinary    LINK -> LINK
CONTACT_1-CONTACT_3        219.5   219.5    372.9  ordinary    LINK -> LINK
CONTACT_2-CONTACT_3        329.5   329.5    372.9  ordinary    LINK -> LINK
CONTACT_1-CONTACT_4         82.2   301.6     88.0  admission   LINK -> .    <== CHANGED
```

Exactly one edge changes in Row A and exactly one in Row B. **Rows C–E are byte-identical**, which
is the whole of the argument in §4.1 below.

---

### 4.1 It does not reintroduce what Stage 0 fixed, nor undo what D5 bought — measured

- **Stage 0a (both-`EAGER`)**: untouched. The gate adds a term to the comparison; it never changes
  which backstop a pair selects. Row D is identical.
- **Stage 0b (the finite 500 m eager cap)**: untouched. Row C is the pinned chaining test's exact
  geometry, with no prior group and no fold budget anywhere, and comes out identical — so the one
  test that exists to protect eager chaining is not at risk.
- **D5's error preference** (*"new group beliefs popping up all the time"* is the worse error):
  the gate **only ever blocks an admission, never an eviction**, so it cannot increase churn among
  existing members (Row A keeps `{1,2,3}` intact at a 329.5 m internal gap). And because an excluded
  contact becomes *ungrouped* rather than founding a group, it cannot produce new group beliefs
  either. The gate moves error strictly toward "a contact is reported individually for a while",
  which is the direction D5 names as tolerable.
- **`BL-B50`** (membership flipping): mildly *helped* and not fixed. Blocking fold-driven admissions
  removes one source of consecutive-tick flipping; the eviction source measured in §2b remains and
  is `BL-B59`.

---

## 5. Staging — `body-layer/CLAUDE.md`, "Mechanism and calibration never share a commit"

**There is no calibration half.** The gate introduces **no new constant**: the inflation term is a
measured quantity and the threshold is the existing `min(relative_threshold, pair_backstop)`. So the
split is by module seam instead, which is what gives the no-behaviour-change half the task asks for.

> **Commit 1 — provenance, behaviour-neutral.** `Contact.fold_displacement_m: float = 0.0`, written
> in `ContactStore.ingest`'s fold branch, reset on both unambiguous branches. **Nothing reads it.**
> **Acceptance: the full suite is unchanged — 1676 passed / 4 xfailed**, plus one new test asserting
> the field's value after a fold (≈219 m on the 2C path) and 0.0 after an unambiguous re-observation.
> A behaviour change here is a defect, not a step.
>
> **Commit 2 — the admission gate.** `_cluster_contacts` takes `prior_rosters`;
> `GroupStore.reconcile` passes `[g.member_contact_ids for g in self._groups.values()]` before
> reassigning `self._groups`. **Acceptance: the six-row table in §4**, with C, D and E asserted
> identical, A and B asserted to the candidate column, and `test_the_eager_cap_still_chains_a_long_infantry_line`
> green unmodified.
>
> **Commit 3 — the fixture rewrite.** `tests/test_callouts.py`'s 2C fixture, and `BL-B58`'s own
> entry. Separate because it is a *recorded consequence*, not a mechanism change — this fixture's own
> convention (three prior rewrites) is that its new expectation is **read off a run, never
> predicted**.

**Flagged, because it changes spoken output and the test's own name:** with `CONTACT_4` no longer a
group member, the 2C fixture's fourth line — `"BTR-70, in 1 o'clock group."` — has no group to come
from, and `CONTACT_4`'s own `CONTACT_DETECTED` is already past `CALLOUT_MAX_AGE_S` before polling
starts (that fixture's own docstring). So the fixture most likely renders **three** lines, and
`test_2c_transcript_fixture_renders_four_lines_not_seven` needs renaming. Stated as a prediction and
explicitly *not* asserted here — the implementer reads it off a run and records the actual result.

**Performance.** `prior_rosters` is consulted inside the existing O(n²) edge loop, so it must be
flattened once into a `dict[str, frozenset[str]]` (contact id → its prior roster id) before the loop,
not scanned with `any(...)` per pair. One extra float add and one dict lookup per edge; nothing else
changes. `performance-reviewer`'s existing note on this function (`_cluster_contacts` reconciles over
every contact ever seen) is unaffected either way.

---

### Affected Modules / Files

- `body-layer/src/belief/contacts.py` — `Contact.fold_displacement_m` field; written/reset at
  `ingest`'s three resolution branches. Commit 1.
- `body-layer/src/belief/groups.py` — `_cluster_contacts` gains `prior_rosters` and the admission
  term; `GroupStore.reconcile` passes the prior rosters. Docstrings for both, citing §1's measurement
  so the no-op sketch is not rediscovered as the fix. Commit 2.
- `body-layer/tests/test_contacts.py` — the provenance field's write/reset. Commit 1.
- `body-layer/tests/test_groups.py` — the six-row table; `test_constants_are_the_stated_assumptions`
  needs **no** change (no new constant). Commit 2.
- `body-layer/tests/test_callouts.py` — the 2C fixture, read off a run. Commit 3.
- `body-layer/ROADMAP/BL-B58.md` — point at this plan, record the decision. `BL-B59.md` — new.
- `plans/group-contact-identity/plan.md` — amendment **A9**, the pointer and the A6 stage-table row.

---

### Implementation Plan

1. **Commit 1** — the provenance field, behaviour-neutral. Acceptance: 1676 passed / 4 xfailed,
   unchanged.
2. **Commit 2** — the admission gate. Acceptance: §4's six rows, C/D/E identical.
3. **Commit 3** — the 2C fixture, read off a run; rename the test if the line count changes.
4. **Re-run both probes** against the implementation and paste the new columns into
   `implementation.md`, so the plan's numbers and the shipped code are checked against each other
   rather than only against each other's descriptions.

---

### Where this sits in BL-12

- **It precedes Stage 4, and Stage 4's extent guard is still needed.** The heading input is exactly
  what §2 corrupts: one tick, no motion, a 132 m member displacement plus a simultaneous
  absorption *and* eviction. That is amendment A2.2's "membership noise, not motion" with a number
  on it. But the guard is **not** replaced: measured, the *correct* cluster in Row A is still 329.5 m
  wide and Row C's legitimate infantry line is 1,200 m — 2.4 of `_format_range_km`'s 500 m buckets —
  so a speech-time width bound is still required, exactly as A6's Stage 4 row already says.
- **Independent of Stage 5** (road corridor) and of `BL-B49`. It adds no `describe_position` caller.
- **Stage 6** unaffected.
- **New A6 row: Stage 3.5, blocking Stage 4.** Not folded into Stage 4, for Stage 0's own reason —
  it is upstream, independently testable, and worth flying on its own.

### The milestone-completion question (root `CLAUDE.md`)

**Yes, it changes something downstream.** It invalidates the 2C fixture's Stage-3 assertion, which is
currently a *pinned record of the defect* rather than of desired behaviour, and it probably reduces
that fixture's spoken line count — so the "four lines not seven" claim that names the test, and which
three earlier rewrites preserved, may no longer hold. Nothing else in BL-12 asserts over a corrupted
roster, so no other stage's assumption is invalidated. It also makes `BL-B50`'s lapse condition
newly evaluable in the honest direction: after this lands, consecutive-tick membership flipping that
still appears in a sortie trace is **eviction**, i.e. `BL-B59`, not absorption.

---

### Risks & Unknowns

- **`fold_displacement_m`'s reset rule is a mechanism, but it is a judgement.** Reset-on-unambiguous-record
  is calibration-free and self-clearing on the natural event. The failure mode if it is wrong: a
  contact that is never again seen unambiguously carries its budget indefinitely and can never admit
  a new member. Bounded — it never evicts, and `LOST_THRESHOLD_S` (120 s) eventually removes the
  contact from `reconcile`'s input via `BL-B23`'s filter — but it is the one place this design could
  latch. **Decision 1.**
- **Repeat folds accumulate or replace?** If a contact is folded onto twice before any unambiguous
  look, the second fold's displacement should *add* to the budget, not replace it. Stated as the
  intended semantics; unmeasured (neither incident folds twice onto one contact). **Stated assumption.**
- **Row F's property is load-bearing and only one scene wide.** "Single-link routes around a tainted
  member" is what stops the gate freezing legitimate growth, and it is measured on one synthetic
  armour triple. A real sortie could have no clean path.
- **The eviction half is live after this lands** (§2b, `BL-B59`). Anyone reading a post-fix trace
  should not take stable absorption as stable membership.
- **No DCS-internals dependency.** Everything here is inside body-layer's own belief code; nothing in
  this plan rests on a DCS file format, coordinate behaviour or scripting-API claim.

---

### Decisions Requiring User Input

1. **How does `fold_displacement_m` retire?** Recommendation: **reset to 0.0 on the next unambiguous
   record** — no new constant, self-clearing, and it is the honest provenance statement ("an
   independent look confirmed the position"). The alternative is a half-life, which would be a real
   calibration commit and a number they own; `POSITION_HALF_LIFE_S` (30 s) is the obvious reuse
   candidate rather than a fresh constant. Recommendation stands on Rows A/B persisting correctly
   under the reset rule in both incidents.
2. **Is the eviction half deliberately out of scope?** Recommendation: **yes** — file `BL-B59`, fix
   it separately. It needs retention hysteresis against the *relative* test, which is a second
   mechanism with its own calibration and reopens `BL-B50`; bundling it would destroy this plan's
   zero-calibration property. But it is the direction that can **suppress** an air-defence report,
   so it is the more dangerous of the two and should not sit in the backlog unprioritised.
3. **The 2C fixture's spoken line count may drop from four to three.** This is correct behaviour (the
   BTR-70 genuinely is not in that group), but the test's name encodes "four lines". Confirm that a
   quieter Petrovich here is the intended outcome rather than a regression to investigate.
