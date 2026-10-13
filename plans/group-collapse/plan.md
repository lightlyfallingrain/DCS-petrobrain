# `collapse(group, depth)` — the group tree, derived at read time

### Goal

Add one derivation that collapses a `Group`'s members to a requested depth on the user's own
group → class → sub-class → type → contact ladder, storing nothing new, and put it behind at least
one real consumer so it is not dead code.

---

### User direction this plan is built on

From `docs/acceptance/2026-10-13-group-model-and-attention-tiers.md` Part 4:

> *"collapse(group, depth) would be a good approach.*
>
> *Note that usually we are interested in one group at a time, so once its members are collected,
> no need to iterate through the other groups."*

And Part 2, his concept of the tree — explicitly *"Not final word, but concept"* — group → class →
sub-class → type → individual unit, with `iff` named and **deferred but needed later** (*"Do not
build it; do not design it out either"*).

**Mid-pass direction, 2026-10-13, on cost:**

> *"As with other detection logic, we can ignore units outside the perception FOV cone or masked by
> cockpit. If Petrovich could not see it, we don't need to calculate it any further."*

**And his settling of the ambiguity in that sentence, same day:** *"Yes, I mean 1, not 2"* —
reading 1 (cost pruning: the FOV/mask test decides **whether** the expensive work runs) and
**not** reading 2 (content filtering: unseen members omitted from the derived tree). See
Decision 6, which records both readings because the literal reading of the first sentence is the
one a later pass would otherwise re-derive.

---

### What this gives the pilot

Today three separate projections of a group's roster exist, and **none of them can answer *"what
armor is there"***:

| projection | source field | resolver | serves |
|---|---|---|---|
| `Group.composition` | `last_class_raw` | `object_model.profile_for` | the matcher, only |
| `Group.air_defence_composition` | `last_class_raw` | the lattice | the matcher, only |
| `speech._group_composition_clause` | `Contact.classification` via facts | `(value, level)` groupby | one spoken line |

One structure at a requested depth serves both the noise-reducing group callout the pilot wants at
range (*"Group, 5 o'clock"* — shallow) and the precise per-unit question he wants on an attack run
(*"where's that Shilka"* — deep). That is the whole product argument, and it is his: *"A group can
be treated as a group but also as it's indivudual members."*

**Said plainly: Stage 1 and 2 change nothing the pilot can hear.** They are a seam plus an
inspection fact. Stage 3 is where a spoken line starts coming from the new structure. If the user
would rather not build a seam ahead of its consumers, Decision 1 is where to say so.

---

### Affected Modules / Files

- **`body-layer/src/belief/group_view.py`** — *new.* `CollapseDepth`, `CollapseNode`, `collapse()`
  and `collapse_members()`. Owns the reporting projection and nothing else.
- **`body-layer/src/belief/classification.py`** — add `CLASS_GROUP_OF`, the level-1 ("class")
  vocabulary. One entry today: every member of `AIR_DEFENSE_OP_CLASSES` maps to `"air defense"`.
  Everything else is its own class. No behaviour change on its own.
- **`body-layer/src/belief/tools.py`** — `_group_facts` gains a `tree` key (Stage 2), the first
  consumer. Absent-not-null per that module's convention.
- **`body-layer/src/belief/speech.py`** — Stage 3 only: `_group_composition_clause` re-expressed as
  a renderer over a depth-3 collapse. Behaviour-preserving; the existing speech tests are the oracle.
- **`body-layer/src/belief/groups.py`** — **Stage 4 only, and optional**: `group_matches` test 4's
  inline `- AIR_DEFENSE_OP_CLASSES` carve-out reads `CLASS_GROUP_OF` instead. Pure
  de-duplication, no behaviour change (probe 2 §3 proved the partition is identical).
- **`body-layer/tests/test_group_view.py`** — *new.*
- **`body-layer/docs/STRUCTURE.md`** — register the new module.
- **`body-layer/ROADMAP/BL-B61.md`** — *new backlog item*, filed not fixed (see Risks).

Not touched: `belief/groups.py`'s cohesion, reconcile, or any stored field. **Nothing new is
stored.**

---

### Measured answers to the three open questions

Probes under `plans/group-collapse/scratchpad/`, all runnable.

**1. `collapse`'s per-call cost — a non-issue, and the real risk is elsewhere.**
`probe_collapse_cost.py`, linear in members, ~0.05–2 µs per member:

| members | depth 0 (group) | depth 2 (sub-class) | depth 4 (contact) |
|---|---|---|---|
| 2 | 0.24 µs | 2.4 µs | 3.3 µs |
| 6 | 0.45 µs | 5.2 µs | 7.8 µs |
| 52 | 2.6 µs | 22.7 µs | 43.9 µs |

The push path (`callouts.py:1140`, every group every poll) at a realistic 10 groups × 6 members is
~~**~5 µs/tick shallow, ~78 µs/tick at full depth** — against `BL-11`'s 12.6 ms poll, 0.04% and
0.6%.~~

> **CORRECTED 2026-10-13 by the performance review** (`performance-review.md`). **The arithmetic
> above was wrong, by 5–47×.** The "shallow" figure multiplied 10 × **0.45 µs**, which is the
> *group*-depth column, while Stage 2's actual caller requests **sub-class** depth (5.2 µs at 6
> members). Re-measured against a realistic mixed roster:
>
> | depth requested | per tick, 10 groups × 6 members | share of the 12.6 ms poll |
> |---|---|---|
> | `SUBCLASS` (Stage 2's caller) | **~235 µs** | **1.86%** |
> | `CONTACT` (full depth) | **~415 µs** | **3.3%** |
>
> Still trivial in absolute terms, and the conclusion — depth is affordable on the push path —
> **stands unchanged**. But the understated 0.04%/0.6% figures would have been cited later as
> headroom that does not exist, so they are struck rather than silently replaced.
>
> **Linearity was separately confirmed 77× past this table's own ceiling**: an adversarial probe
> (`scratchpad/perf_review_adversarial_scaling.py`) drove `collapse_members` to **4,000 members**
> at the worst-case shape — many `TYPE` values across all five air-defence sub-classes, forcing the
> deepest dict-build branch — and per-member cost *fell*, 6.24 µs at n=52 to 2.45 µs at n=4,000.
> That is single-pass bucketing, not a quadratic re-filter.

**The cost story the capture expected is inverted.** The push path *already* calls
`describe_contact` per member via `_group_member_facts`, and `BL-B49` measured that path's
enrichment term at **63.25 ms per contact** cold / 6.77 ms warm (never-cached
`terrain_divide_qualifier`) against the real 738 MB `syria-full.sqlite`. A full-depth collapse over
52 members is **~150× cheaper than one `describe_contact` enrichment term.** So depth is not what
costs anything here; **routing `collapse` through `describe_contact` would be**, and Decision 3
forbids it.

`probe_collapse_scaling.py`: a nested re-filter per sub-class costs 2.6–4.3× a single pass and stays
linear (sub-class count caps at 5). Both trivial; Stage 1 specifies the single pass anyway, so a
future cohesion change that makes one group large cannot degrade it.

**2. The matcher keeps working off the flat tuple — confirmed three ways.**
`probe_matcher_independence.py`:

- **By AST**, `group_matches` reads exactly `{air_defence_composition, centroid_uncertainty_m,
  centroid_x, centroid_z, composition, installation, stopped}`. **No roster- or tree-shaped
  attribute at all.** It cannot want a tree.
- **By round trip**, a depth≤2 tree partitions rosters identically to the flat multiset — it groups
  and nests, it never adds a distinction. Only depth ≥3 adds information, and no test reads it.
- **And the probe's own first-draft bug is the evidence for keeping the key flat**: a nested dict
  built by insertion order split `["OP_SPAAG","OP_LRSAM"]` from `["OP_LRSAM","OP_SPAAG"]` — the same
  multiset. A derived tree is not canonical unless every level is sorted deliberately. That is the
  capture's *"a nested structure would need its own comparison semantics"*, demonstrated.

**3. `air_defence_composition` CANNOT be retired.** `probe_ad_composition_retirement.py` drives the
real `GroupStore`: a group forms from two class-level `OP_LRSAM` contacts, then every member leaves
the `ContactStore`. The group is **retained** for `GROUP_REIDENTIFY_WINDOW_S` = 60 s with
`air_defence_composition = (("OP_LRSAM", 2),)` still held, and **0 of 2 members resolvable** — so a
derivation would return an empty tree exactly when `group_matches` test 3 needs the value. Probe
confirms test 3 then does real work off the remembered field: a fresh LRSAM cluster re-matches
(`True`), a fresh truck cluster does not (`False`).

The capture called the field *"a symptom of the tree being flattened"*. **It is not.** It is a
*memory of a derivation*, held for a window in which that derivation's inputs no longer exist. The
two answer different questions — `collapse`: what is this group *now*, from live members;
the field: what *was* this group, for re-identification. Retiring it would silently weaken D6's gate
to nothing.

---

### Two findings that change the design

**A. `Group.composition` cannot be the tree's source — it is blind to most class-level beliefs.**
`probe_matcher_independence.py` §2b: `_composition_of` resolves through `object_model.profile_for`,
which keyword-matches DCS *type* names. Measured over the real vocabulary, **`OP_ARMORED`,
`OP_SPAAG`, `OP_LRSAM`, `OP_SRSAM`, `OP_MRSAM` all bucket to `OP_GROUPSOMETHING`** — 5 of 10 real
classes, and class level is the common case at range. Probe 3 shows it live: a group of two LRSAM
sites has `composition = (("OP_GROUPSOMETHING", 2),)`.

This is the **5th occurrence** of the `BL-B47` family (`BL-B47`, `BL-B51`, `BL-B56`, `BL-B57`), and
the `dod` role's own memory says to raise it *at Architect, not Reviewer/DoD, rather than filing a
fifth backlog item*. So, raised: **test 4 is far weaker than it reads** — at class level it cannot
tell a tank company from a SAM site, and test 3 carries that load alone. It is *self-consistent*
(both sides resolve the same way) and so not a live defect, which is why this plan does not fix it —
see `BL-B61` and Decision 5.

**B. `collapse` must read `Contact.classification`, not `last_class_raw`.**
`probe_source_field.py`: a contact identified to `"ZSU-23-4 Shilka"` (TYPE) re-observed as
`"OP_SPAAG"` (CLASS) *holds* the type claim — the lattice's `hold` rule, the oscillation fix — while
`last_class_raw` becomes the coarser `"OP_SPAAG"`. Reading `last_class_raw` would make a reported
tree lose a type identification the moment a coarser percept arrived, and would contradict
`_group_composition_clause`, which already reads the folded claim.

So `collapse` differs from `Group.composition` in **both** the field and the resolver. Two
independent reasons it is a new derivation and not a reshaping of that field.

**Decay, checked before finalising** (`belief/decay.py`): `classification.value`/`.level` never
decay by design; only `confidence` does, over `IDENTITY_HALF_LIFE_S` = 600 s. So the collapse's
*grouping* is decay-free and matches the facts path exactly — but any node exposing confidence must
route through `belief.decay.classification_confidence_at`, never read `ClassificationBelief.
confidence` raw.

---

### Decisions

**Decision 1 — home: a new module, `belief/group_view.py`.** Not `groups.py`. That module owns
identity, cohesion and matching, reads `last_class_raw` through `profile_for`, and deliberately
takes `Sequence[Contact]` rather than knowing about `ContactStore`. The collapse reads the *other*
field through the *other* resolver and needs id→contact resolution. Putting them together invites
exactly the cross-contamination the `BL-B47` family is made of, in the module where that family
already bit twice. `groups.py` is also 1545 lines.

**Decision 2 — signature, in two layers.** His signature is the public one:

```python
def collapse(store: ContactStore, group: Group, depth: CollapseDepth, now_sim: float) -> CollapseNode
def collapse_members(members: Sequence[Contact], depth: CollapseDepth, now_sim: float) -> CollapseNode
```

`collapse` resolves `group.member_contact_ids` against the store and delegates. The pure form keeps
`groups.py`'s store-agnostic posture available to tests and to any future caller that already holds
members. **His access-pattern note is satisfied structurally**: the signature takes one group, so
there is no loop over others to skip.

**Decision 3 — it reads `Contact` directly and never `describe_contact`.** Finding A/B plus the cost
table. `describe_contact` carries the `BL-B49` enrichment cost and `collapse` needs none of what it
adds (semantic position, terrain qualifier). This is the single most important constraint in the
plan: the derivation is cheap *because* it stays off that path.

**Decision 4 — `depth` is an `IntEnum`, and the return type is one recursive dataclass.**

```python
class CollapseDepth(IntEnum):
    GROUP = 0; CLASS = 1; SUBCLASS = 2; TYPE = 3; CONTACT = 4
```

An enum because the user's ladder has named rungs; `IntEnum` because ordering comparisons
(`depth >= CollapseDepth.TYPE`) are how it will be used, exactly as `SpecificityLevel` already does
in this codebase. **One frozen `CollapseNode` type at every depth**, not a depth-dependent union —
stable and predictable beats clever (heuristic 1), and a `mypy --strict` consumer needs no
depth-keyed narrowing. A shallower call simply returns `children = ()`.

Each node carries `label`, `level`, `contacts: int`, `units_lo: int`, `units_hi: float`,
`children: tuple[CollapseNode, ...]`, and at `CONTACT` depth a `contact_id` with position and
`radius_m`. Sorted at every level (finding 2's canonicality point), so two nodes are comparable.

**Decision 5 — `air_defence_composition` and `Group.composition` both stay, untouched.** Measured,
open question 3. Stage 4's optional change shares the level-1 *table* with test 4; it does not touch
either field or any matching behaviour.

**Decision 6 — the FOV/mask test gates *whether* `collapse` is called, never *what it returns*.**
User direction, *"Yes, I mean 1, not 2"*. `collapse` stays a pure projection of belief state; a
remembered member stays in the tree, and belief's own ladder (`OBSERVED_WINDOW_S` 16 →
`POSITION_HALF_LIFE_S` 30 → `LOST_THRESHOLD_S` 120) remains the only thing that retires a contact.

Reading 2 was considered and **rejected by him**. Recorded because the literal reading of his first
sentence is the one a later pass would re-derive. What it would have cost, measured in
`probe_fov_pruning.py`: the co-pilot mask has `rear_cutoff_deg = 130`, so body azimuths 150–330 are
unviewable. Under a current-mask content filter *"what armor is there"* answers differently as the
airframe yaws with the world unchanged, and a group looked at two seconds ago reports fewer members
than it holds. Worse — the member set is also the matcher's input, so a filter upstream of clustering
would make a yaw look like a split/merge and churn the very group identity `BL-12` exists to
stabilise.

**Consequences, both good:** `collapse` needs **no FOV/mask state at all**, so **no
perception→belief seam is crossed** — module independence and the `belief/percept.py`
no-omniscience boundary are untouched. And the gating already exists: `callouts.py:1140` tests
`store.callout_observable(member, now_sim)` with **`any` member observable, not `all`** (its own
comment: *"a group straddling the cutoff is a group Petrovich can genuinely see"*). Stage 2 and 3
callers reuse that predicate; nothing new is written.

**Decision 6a — the caller-side test is the *remembered* one, not the current mask.** Answering the
coordinator's remaining question. `ContactStore.callout_observable` is already
`now_sim - last_observable_sim < CALLOUT_OBSERVABILITY_GRACE_S` (10 s) — a remembered test with a
grace window, and its own docstring says the window *must* be measured from the last confirmed
sighting rather than the first failed check. The raw current-mask test would churn on every yaw.
The bookkeeping is stamped once per `ContactStore.tick(ownship=...)`, so the mask geometry is
evaluated once per tick rather than once per collapse — `callout_observable` is explicitly *"a read
of bookkeeping, not a second mask computation"*. Use it; do not add a second one.

**Decision 7 — level 1 is one table with one entry, and nothing is invented.** The user's sketch
names `"armor"`, `"truck"`, `"infantry"`, `"air defense"` as classes — but in code `OP_ARMORED`
*is* the class, and the only super-class grouping that exists is `AIR_DEFENSE_OP_CLASSES`.
So `CLASS_GROUP_OF` maps the five air-defence classes to `"air defense"` and leaves every other
`OP_*` as its own class. Probe 2 §3 showed this is not invention: test 4 *already* partitions
op_classes into {air defence} / {everything else} and treats the two differently, i.e. the user's
level-1 step with one branch named. Adding more super-classes is a vocabulary question for the
attention-tier milestone, not this plan.

---

### Implementation Plan

**Stage 1 — the derivation, with nothing consuming it yet.**
`classification.CLASS_GROUP_OF`; `belief/group_view.py` with `CollapseDepth`, `CollapseNode`,
`collapse_members`, `collapse`. **Single pass** over members building `(class, sub-class)` buckets,
one `parent_class_of` call per member (probe 1b). Sorted at every level. Reads
`Contact.classification` (Decision 3/finding B). `units_lo`/`units_hi` summed from
`Contact.cardinality`, **never `len(members)`** — see Risks. `tests/test_group_view.py`: depth
ladder, the air-defence branch, a class-level-only roster (the case `Group.composition` cannot see),
a mixed class/type roster, canonical ordering, empty and single-member groups, and a group whose
members have all left the store.

**Stage 2 — first consumer: `tools._group_facts` gains `tree`.** A shallow collapse
(`CollapseDepth.SUBCLASS`), absent-not-null, inspectable through `console.py`'s `show <id>` — the
existing inspection seam `BL-W36` Stage 2 established. Caller-side observability gating per
Decision 6/6a. **Nothing spoken changes.** This is the stage that stops the derivation being dead
code.

**Stage 3 — migrate the duplication.** Re-express `speech._group_composition_clause` as a renderer
over `collapse_members(..., CollapseDepth.TYPE)`. Behaviour-preserving: the existing speech tests
are the oracle, and the baseline is **1726 passed / 4 xfailed**. Keep the clause's own vocabulary
(`_unit_type_display`, `_SPOKEN_NUMBERS`, `_undifferentiated_phrase`) exactly where it is — the
collapse supplies *structure*, speech supplies *words*. This is the named duplication the new
abstraction removes, and the reason it earns its place.

**Stage 4 — optional, behaviour-preserving.** `group_matches` test 4 reads `CLASS_GROUP_OF` instead
of its inline `- AIR_DEFENSE_OP_CLASSES`. Separate commit, per
*"mechanism and calibration never share a commit"* — this is mechanism touching the matcher and
should be reviewable alone. Skip it if Stage 3 runs long.

**Stage 5 — file `BL-B61`.** Finding A as a backlog item, not a fix.

Per-subproject checks after every stage, from **inside** `body-layer/`:
`.venv/bin/ruff format src tests && .venv/bin/ruff check src tests && .venv/bin/mypy src && .venv/bin/pytest`.

---

### Scope — what is excluded, and where it belongs

| excluded | why / where |
|---|---|
| `iff` | user-deferred (*"Do not build it; do not design it out either"*). `CollapseNode` is a frozen dataclass with defaulted fields, so adding `iff` later is additive. Not designed out. |
| Attention tiers (low/medium/high) | capture Part 3. They are *context* for why depth is a parameter; the tier→depth mapping is the attention milestone's. |
| Attention-driven per-unit resolution | the larger piece Part 3 identifies. Its own milestone question — `BL-14` vs a predecessor — and the user's to sequence. |
| Who chooses `depth` | follows from the tiers. Stage 2/3 callers pass a fixed depth. |
| 9K113 channel | unbuilt, user-deferred with the spec. |
| Retiring `air_defence_composition` | **measured impossible** (probe 3). |
| Fixing test 4's resolver | `BL-B61`. Self-consistent today; fixing it changes matching behaviour and deserves its own pass. |
| Stage-3-style flag flips | not applicable. |
| Any new stored field | nothing is stored. |

---

### Risks & Unknowns

- **A contact is not a unit, so depth 4 cannot honestly be called "individual units".** `Contact`
  carries a `CardinalityBelief` interval — `OP_TO5UNITS` is 4–5 units in *one* contact (the user's
  own *"ten trucks in one glance is one perceptual event"*). The user's ladder bottoms at
  *individual unit*; the deepest level this derivation can reach is **contact**. Hence
  `units_lo`/`units_hi` as an interval rather than a count, and hence `CollapseDepth.CONTACT`
  rather than `UNIT`. **This is the plan's sharpest honest limit** and it is Decision 8 territory —
  see below.
- **A derived view with no consumer is dead code; a big-bang migration is riskier.** Mitigated by
  the Stage 2 / Stage 3 split, but Stage 3 touches a live speech path with 1726 tests behind it. If
  the oracle disagrees anywhere, stop and report rather than adjusting the expected line.
- **Finding A means `BL-14` may inherit a weaker matcher than its spec assumes.** `step left`
  *"staying inside the unit group"* depends on group identity, and test 4 cannot distinguish kinds
  at class level. Filed as `BL-B61`, flagged here because `BL-14`'s plan should not be written
  against an assumed-strong test 4.
- **Canonical ordering is load-bearing and easy to lose.** Probe 2's own first draft lost it. Any
  future field added to `CollapseNode` must preserve sorted-at-every-level or node comparison
  silently stops working.
- **`CLASS_GROUP_OF` will want to grow**, and the pressure will come from speech wanting
  *"armor"* as a super-class. Growing it changes the collapse *and* (after Stage 4) test 4's
  partition. Keep it a one-entry table until the attention milestone decides the vocabulary.
- **Not an unknown, stated for completeness:** nothing here touches DCS internals, file formats,
  coordinate systems or the scripting API, so no `investigator` pass is owed.

---

### Second-order effect

**Unblocks** the attention tiers cleanly: the tier's job becomes *choose a depth*, which is now a
parameter rather than a redesign, and the push/pull cost split the capture worried about turns out
not to constrain the choice at all (measured: **1.9–3.3%** of a poll — corrected from an earlier
0.04–0.6%, see the correction note in §1). **Narrows** `BL-14`: the
measured contact-vs-unit gap means a deep collapse delivers *per-contact* selection, not per-unit,
so `BL-14`'s *"selection, step and guidance are all per unit"* still needs the attention-driven
resolution mechanism — this plan does not supply it and must not be read as having done so.
**Complicates** nothing, because nothing is stored and no existing field changes meaning.

---

### Decisions Requiring User Input

1. **Build the seam now, or fold it into the attention-tier milestone?** The derivation's motivating
   consumers (*"describe group"*, *"what armor is there"*, *"where's that Shilka"*) **do not exist** —
   they are Part 3's high tier. Stages 1–3 are cheap and remove a real measured 3-way duplication,
   but Stage 1–2 give the pilot nothing audible and Stage 3's gain is internal. *Recommendation:*
   build Stages 1–3 now. The shape is tightly constrained by his own Part 2 sketch, so the risk of
   guessing wrong is low, and having the structure in place makes the attention-tier plan a
   depth-selection question instead of a data-model question. But it is a seam ahead of its
   consumers, and that is his call.
2. **Is `CollapseDepth.CONTACT` an acceptable name for the deepest rung, given it is not his
   "individual unit"?** The honest answer is that per-unit does not exist and cannot be derived
   (`BL-12` measured 16 m real spacing against a gate inflating to 600 m). Naming it `CONTACT`
   keeps the limit visible in every call site; naming it `UNIT` would read as a promise the belief
   layer cannot keep. *Recommendation:* `CONTACT`, and let the attention-tier milestone add a real
   `UNIT` rung if and when per-unit resolution lands.
3. **Stage 4 — share the level-1 table with `group_matches` test 4, or leave the matcher alone
   entirely this pass?** Behaviour-identical by measurement, but it is a change to `BL-12` code
   merged two days ago. *Recommendation:* include it, as its own commit, so there is one definition
   of the air-defence partition rather than two.

---

### Supersedes

Per `docs/PROCESS.md`'s superseding rule, `BL-12`'s flat `composition` **was not wrong, it was
narrower** — and this plan does not replace it. Both fields stay exactly as they are (Decision 5,
measured in probe 3). What this plan adds is a *second, independent* projection for reporting, with
a different source field and a different resolver. `plans/group-contact-identity/plan.md`'s
`Group.composition` / `air_defence_composition` decisions stand unamended; this is an addition
beside them, not a revision of them.

### Probes

All under `plans/group-collapse/scratchpad/`, all runnable with
`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python3` from this worktree's root:

- `probe_collapse_cost.py` — per-call cost by depth and member count; the `describe_contact` contrast.
- `probe_collapse_scaling.py` — nested re-filter vs single pass.
- `probe_matcher_independence.py` — AST read-set, round trip, the resolver split (§2b), partition identity.
- `probe_ad_composition_retirement.py` — the retirement question, against the real `GroupStore`.
- `probe_fov_pruning.py` — what observability state belief already holds; the head-turn artefact.
- `probe_source_field.py` — `last_class_raw` vs `classification.value`.
