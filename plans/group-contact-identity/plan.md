### Goal

Make **group** identity the thing that persists across losing sight — a remembered `Group` matched
against a freshly observed cluster on kind, composition, movement state and plausible displacement —
so contact-level churn stops reaching the pilot as new-group-every-poll, and resolve contact-level
ambiguity *within* a group toward the remembered contact instead of founding a duplicate.

Decisions honoured, not relitigated: **D3, D4, D5, D6, D7, D8, D9, D10** of
`plans/post-review-fixes/explore-notes.md` ("Decisions this conversation produced"). §2, §3, §5 are
this plan's; §4 (D10) is the seam with `BL-8`.

---

# Amendment — 2026-10-11

**Status: the plan below is not re-planned and its decisions are not re-decided.** This section
brings it current against five days of merges and measurements, per `docs/PROCESS.md`
("Superseding a decision") — the superseded passages stay in place with a pointer to their
replacement here. Everything in the body that this section does not name still stands.

Written against `feature/bl12-group-contact-identity` at `6daeec6` (= `main`, 2026-10-11).
**Nothing here is an implementation change; Stage 1 has not been started.**

**Everything measured below was run, not reasoned.** Two probes against the real tree, through
`body-layer/.venv`'s interpreter: a reproduction of `BL-B48`'s cohesion arithmetic with a candidate
fix beside it, and an enumeration of the air-defence resolution paths. The commands and their
output are in this amendment where the number decides something.

---

## A1 — Both stated prerequisites have landed. Confirmed, with one number corrected.

The body's "Interaction with already-merged and in-flight work" says *"Land `BL-11` Stage 2 first,
or accept a measurable regression"* and that Stage 3 *"governs whether Stage 5 is affordable at
all"*. **Both conditions are now satisfied.** Verified on this tip:

| claimed prerequisite | state |
|---|---|
| `group_salient_ids` hoist | **landed** — `body-layer/src/perception/group_salience.py` exists |
| `@cache` on `profile_for` | **landed** — `perception/object_model.py:557`, `functools.cache` imported at `:68` |
| `describe_position` memo | **landed** — `WorldEnrichmentCache`, `belief/enrichment.py:668`, keyed on `contact_id` plus a 50 m cell |

So the dependency is discharged: Stage 1's per-reconcile `composition` pass rides the `profile_for`
cache, and the regression the body warned about cannot occur.

**One number in the body's reasoning is weaker than written, and it does not change the
conclusion.** The hoist measured **5.1×, not the predicted 8.1×** (`plans/bl11-tick-cost/
performance-review.md` — that review's one required change was a docstring correcting exactly this
claim). The remaining 1.6× is located and **declined**: `BL-B40` records it as 1.1 ms in situ, so
1.6× would save ~0.4 ms of a 12.6 ms poll against a 1,000 ms budget, and the ratio **saturates at
5.1× from ~2,500 pairs upward** — a bigger mission does not make it grow back. Nothing in this plan
needs the declined remainder.

**One number is stronger than written.** The body's Stage 5 hard constraint cites
`describe_position` at **51.6 ms median**; the `BL-11` pass measures **84.6 ms per call in situ**
and 57.4 ms standalone, and found every call shape costs the same (same position ×20, 1 m apart,
within one 50 m cell — no internal memo, so a cache hit saves the full unit cost). The argument
against a per-group-per-tick road query is therefore **stronger**, not weaker.

Current poll cost for sizing anything in this plan: **12.6 ms median work, 1.000 s realised period,
2.0 % of polls overrunning 1.0 s** — and every one of those overruns is a single
`describe_position` spike, which is a `query.describe` question and not body-layer's.

---

## A2 — `BL-B48`: BL-12 does not dissolve the infantry bridge. It amplifies it, and the fix belongs before Stage 1.

**This is the pass's main finding and the body does not cover it.** The body's Risks section names
`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` (20.0) and `GROUP_PROXIMITY_GAP_RATIO` (3.0) as
uncalibrated assumptions *"upstream of everything here"* and says *"not this plan's to fix"*.
`BL-B48` is a third and sharper instance, and that disposal no longer holds for it.

### The mechanism, reproduced

`_cluster_contacts` (`belief/groups.py:375`) is single-link union-find with
`pair_threshold = min(relative_threshold, pair_backstop)`, where `relative_threshold = gap_ratio ×
median(nearest-neighbour gap)` and `_pair_backstop_m` (`:336`) returns `math.inf` when **either**
member's `op_class` is `EAGER` (today only `OP_INFANTRY`).

Reproduced exactly, real profiles, real constants (`GAP_RATIO=3.0`, `UNIT_WIDTHS=20.0`,
`MIN_MEMBERS=2`; sizes `T-72B` 7.0 m, `Ural-375` 6.0 m, `Infantry AK` 1.8 m):

| scene | relative threshold | current (`any`-EAGER) |
|---|---|---|
| armor@1 km + truck@3 km | 6,000 m | 0 groups (pair backstop 130 m beats the 2,000 m gap) |
| armor@1 km + infantry@7 km | 18,000 m | **one group, extent 6,000 m** |
| armor@1 km + truck@3 km + infantry@7 km | 6,000 m | **one group of three, extent 6,000 m** |

**Two independent faults compound**, and only naming both explains the numbers:

1. **The eagerness is applied to the pair, not to the infantry** — `BL-B48`'s own reading, and
   `_pair_backstop_m`'s `in (backstop_i, backstop_j)` is literally where it happens.
2. **With the absolute backstop gone, the relative test cannot reject anything at n = 2.** With two
   contacts, both nearest-neighbour gaps equal the pair's own distance, so
   `relative_threshold = 3 × d ≥ d` *always*. Measured as the 18,000 m row above. This is why
   `armor@1km + infantry@7km` merges at any separation whatsoever, and it is not noted anywhere in
   the repo.

### Does BL-12's model dissolve it? No — three ways it makes it worse

Stage 1 reconciles *remembered groups against observed clusters*. **It does not produce the
clusters**, so every new field it remembers is an aggregate over whatever `_cluster_contacts`
handed it.

1. **Stage 1's displacement test (test 5) is the plan's only geometric gate, and a 6 km cluster
   breaks it — measured.** `centroid_uncertainty_m` is specified as *RMS of members'
   `position.radius_m()`*, which captures each member's own position uncertainty and says **nothing
   about the cluster's 6 km extent**. Dropping the bridging infantry for one tick moves the
   remembered centroid **1,667 m** (measured on the three-member scene above). Against Stage 2b's
   fastest row — truck at 15 m/s — and a 1.0 s poll, test 5's bound is ~15 m plus slack. So **every
   membership flip in a bridged group fails the displacement test and founds a new group.** Stage
   1's central promise — group identity survives — fails precisely on the groups `BL-B48` produces,
   and it fails *silently*, as a founding rather than an error.
2. **Stage 4's heading would be fabricated.** `heading_deg` is specified as derived from centroid
   displacement between successive reconciles of the same group id, smoothed over N = 5. On a
   bridged group the input signal is membership flipping, not motion — kilometre-scale steps with no
   relation to where anything is going. Stage 4 exists to avoid exactly this: the body rejects
   `enrichment.motion_when_seen` because *"a single noisy percept can flip the reported
   direction"*, then proposes a source whose noise is two orders of magnitude larger.
3. **Decision 7 is unspeakable at that extent.** `BL-B48` states it directly and it is the pilot-
   facing form of the whole problem: *"a group 6 km across has no single believable bearing, range
   or disclosure line."* D7's line — *"that column, now 2 o'clock, three kilometres, still moving
   north on the road"* — is a claim about a thing in one place. Three of its four facts are false
   for a 6 km group, and Stage 1 is what makes Petrovich say them with the confidence of continuity.

**So: fix it first.** Not because `BL-B48` is urgent on its own — it is live today and has been
tolerated — but because Stage 1 converts it from an over-wide group into a *persistent, spoken,
geometrically-asserted* over-wide group, and Stage 4 then attaches a direction to it.

### The smallest correct fix, and it is one word

**Require *both* members to be `EAGER`**, i.e. `_pair_backstop_m`'s
`if CohesionBackstop.EAGER in (backstop_i, backstop_j)` becomes an `and` over the two. A mixed
infantry/non-infantry pair then falls through to the ordinary unit-widths backstop.

**It is precedented in the function it edits**, by the same plan that introduced `EAGER`. Rule 1 of
`_pair_backstop_m`'s own docstring already says: *"A **mixed** pair (one installation component, one
not) falls through to the ordinary rule below — an installation cap is only meaningful when both
members are plausibly parts of the same site."* The identical argument applies here, which is why
this is a correction rather than a new policy: an eager cap is only meaningful when both members are
the kind of thing eagerness was granted for.

**Measured, same probe, candidate rule beside the current one:**

| scene | current | both-EAGER |
|---|---|---|
| armor@1 km + truck@3 km | 0 groups | 0 groups (unchanged) |
| armor@1 km + infantry@7 km | one group, 6,000 m | **0 groups** (mixed pair → backstop 88 m) |
| armor + truck + infantry | one group of three, 6,000 m | **0 groups** (all three pairs rejected) |
| three infantry at 30 m spacing | one group, extent 60 m | **one group, extent 60 m — byte-identical thresholds and unions** |

All three `BL-B48` cases resolve; infantry-to-infantry eager merging is untouched, which is what
*"ok to merge infantry too eagerly"* actually granted. It is a **mechanism** change with no
calibration, so it is one commit under `body-layer/CLAUDE.md`'s "Mechanism and calibration never
share a commit".

### What this fix does *not* close, and why it is the user's call

Fault 2 above survives: **two infantry contacts form a group at any separation**, because an
infantry-infantry pair still has `backstop = inf` and the relative test is vacuous at n = 2. After
the fix, an infantry-only group of two spanning kilometres is still reachable — and infantry is
often the only class held at range, so this is not a corner. A finite eager cap would close it, but
the number is a calibration the user owns, so it is **Q-A below**, not a decision taken here.

### New Stage 0, blocking

> **Stage 0 — bound a group's extent before anything remembers one.** Two commits, in order:
> **0a (mechanism)** `_pair_backstop_m` requires both members `EAGER`; acceptance is the four-row
> table above, with the three-infantry row asserted bit-identical. **0b (calibration, gated on
> Q-A)** a finite eager cap replacing `math.inf`.
> Belongs **before Stage 1**, for the three reasons above. `tests/test_groups.py`'s
> `test_constants_are_the_stated_assumptions` gains any new constant from 0b.

---

## A3 — Test 3 and Stage 3 branch 1 reintroduce the defect `BL-B47` fixed yesterday. Measured.

**Found in this pass; nobody flagged it.** This is the plan's one gate where the body says ambiguity
must *not* resolve toward memory, because a wrongly-continued SAM **suppresses** a threat warning.

The body specifies both air-defence checks as resolving through `_profile_for_contact`
(`groups.py:304`) → `object_model.profile_for(contact.last_class_raw)`:

- Stage 1's `air_defence_composition` — *"the subset of `composition` whose `op_class` is in
  `AIR_DEFENSE_OP_CLASSES`"*, and `composition` is built via `_profile_for_contact`.
- Stage 3 branch 1 — *"any passing candidate's `last_class_raw` resolves to an `op_class` in
  `AIR_DEFENSE_OP_CLASSES`"*.

`profile_for` keyword-matches DCS **type** designations. A classification held at **class** level
carries the `OP_*` string itself and matches nothing. That is precisely `BL-B47`, merged
2026-10-10 as `1063f2a`. Enumerated against the real tables on this tip:

```
last_class_raw         profile_for().op_class  in ADOC?  _op_class_of()  in ADOC?
SA-6 Kub LN            OP_MRSAM               True      OP_MRSAM        True
OP_SRSAM               OP_GROUPSOMETHING      False     OP_SRSAM        True
OP_MRSAM               OP_GROUPSOMETHING      False     OP_MRSAM        True
OP_LRSAM               OP_GROUPSOMETHING      False     OP_LRSAM        True
OP_SPAAG               OP_GROUPSOMETHING      False     OP_SPAAG        True
OP_ZU23                OP_ZU23                True      OP_ZU23         True
```

**Four of the five air-defence classes fail the plan's carve-out at class level.** `OP_ZU23` passes
*by accident* — the literal string matches that table's own `"zu23"` keyword, which `BL-B47`'s
implementation log documents as a coincidence. And a class-level belief is what a contact holds
*before* it is identified to type, which at range is most of the time.

**Correction to the plan**: both air-defence resolutions read
`belief.classification._op_class_of` / `parent_class_of`, not `object_model.profile_for` — the
lattice side, which is where a *believed classification* belongs. This is `BL-B47`'s own boundary
decision applied to the two new consumers this plan adds, and it is a strict widening (that fix
enumerated 1,060 candidate values: 0 verdicts lost, 4 gained).

`composition` itself still goes through `_profile_for_contact`, which is correct — it needs
`installation_component` and `size_m`, which only a profile carries. Only the **air-defence
membership test** moves.

**Fold `BL-B51` into Stage 0 or Stage 1 rather than leaving it separate.** `BL-B51` records three
copies of the air-defence set with one `<=` drift guard between them, and says explicitly: *"Worth
doing before or alongside anything that widens the air-defence treatment further."* This plan adds
the fourth and fifth consumers of that set, both inside the gate whose failure suppresses a warning.
`groups.AIR_DEFENSE_OP_CLASSES` is the guard-less copy the plan keys on today.

*(Separate and pre-existing, noted so it is not rediscovered as this plan's doing:
`_representative_size_m` treats `op_class == DEFAULT_OP_CLASS` as "no real match" and substitutes
`GROUP_REPORTING_UNKNOWN_SIZE_M`, so a class-level SAM belief is sized as unknown. Correct as an
honest default; not this plan's to change.)*

---

## A4 — The group-identity trace line is part of Stage 1, not a suggestion

The body's Risks section says *"Consider a group-identity line in the sortie trace before flying
Stage 1, or the first evidence will be the pilot noticing a wrong 'that column'."* **Promote it to
Stage 1's first commit.** Four reasons, and the first is the decisive one:

1. **D5 is a rate claim, and the rate is currently unmeasurable.** The user accepted false
   continuity because *"it's the unusual occurence"*. That acceptance is conditional on rarity — if
   phase 2 fires often, the premise of his own decision has failed and he would want to know. There
   is no instrument that could tell him.
2. **The plan already concedes this argument once.** Test 6's ambiguity counter is *"part of the
   design and not an optional observable"* for exactly the same reason. The phase-2 match itself is
   the larger surface.
3. **`BL-B50`'s lapse condition is otherwise unevaluable.** Security attached *"blocking-priority if
   a sortie log shows membership flipping on consecutive ticks"* — no log records group rosters, so
   that condition cannot currently fire either way. One trace line serves both items.
4. **The alternative first evidence is a wrong spoken line in flight**, which is the failure class
   this project has repeatedly had to fix from sortie feedback rather than from tests.

Minimum fields, and note the third is the one `BL-B48` would have been caught by:
`group_id`, which phase resolved it (`overlap` / `property` / `found` / `expired`), the roster,
the centroid, **the cluster's extent**, and `composition`. Nothing logs extent today.

---

## A5 — Interaction rows added

These extend the body's "Interaction with already-merged and in-flight work".

| item | state | interaction |
|---|---|---|
| **`BL-13`** (crew query path) | **merged 2026-10-11, `6f04671`** | Its summary renderer aggregates over the **filtered contact set** and never walks a group roster, so it is immune to `BL-B48` by construction while the push path's `render_group_full_disclosure` is not. **This concentrates BL-12's value on the push path and should sharpen its scope, not widen it** — do not add group identity to the pull answer in this plan. Separately: D7's spoken line is a **push-path output**, so it does not need to fit BL-13's *input* slot schema; that schema is what the brain layer targets for questions, which is a different seam. `plans/crew-query-path/plan.md` "Not touched, deliberately" names `groups.py`, so there is no file conflict. |
| **`BL-B47`** (class-level SAM) | **merged 2026-10-11, `1063f2a`** | See **A3**. Changes this plan's air-defence resolution path from `profile_for` to the classification lattice. Not optional — as written, the plan reintroduces the fixed defect inside its own safety gate. |
| **`BL-B48`** (infantry cohesion bridge) | open, live on the push path | See **A2**. Becomes blocking **Stage 0**. BL-12 does not dissolve it. |
| **`BL-B49`** (narrow `report` priced as `report_all`) | open, Architect-owned | Independent of Stages 1–4 and 6 (its own entry says closing `BL-B48` will not change its cost either way). **It does gate Stage 5**: Stage 5 would add a fourth `describe_position` consumer at 84.6 ms in situ, while `BL-B49` is still choosing between three mitigations for the existing three. Two plans independently adding callers to that call is the thing to avoid — a further argument for A6's Stage 5 disposition. |
| **`BL-B50`** (group callout suppression ratchet) | open | **Stage 1 does not fix it, and the distinction matters: Stage 1 stabilises the group *id*, not the *roster*.** `reconcile` recomputes clusters every tick, so members are always the current cluster's members; phase 2 hands a cluster an existing id, it does not stabilise who is in it. The ratchet's only required ingredient is membership flipping on consecutive ticks, which is unchanged. What Stage 1 *does* change is that `last_spoken_*` now survives instead of being reset by re-founding, which reduces total group lines without closing the mechanism. **Stage 0 is what defuses it in practice** — `BL-B50`'s own text says *"`EAGER` infantry cohesion producing a group 6 km across is precisely the input that makes membership flip tick-to-tick"* and *"fix either and the other stops mattering much"*. So evaluate its lapse condition after **Stage 0 + Stage 3**, not after Stage 1. |
| **`BL-B51`** (three copies of the air-defence set) | open | See **A3**. This plan adds the 4th and 5th consumers of the set, inside the gate whose failure suppresses a warning. Fold the one-set-plus-`<=`-guard consolidation into Stage 0/1. |

---

## A6 — Stage order and boundaries, re-checked

**One stage is added, none is dropped, and the existing boundaries survive the re-check.**

| stage | change |
|---|---|
| **0 (new)** | Bound group extent — `_pair_backstop_m` both-EAGER (0a), finite eager cap if the user wants it (0b). **Blocking, before Stage 1.** |
| **1** | Unchanged in shape. Three corrections: the trace line becomes its **first commit** (A4); the air-defence test reads the classification lattice (A3); the prerequisite note is discharged (A1). |
| **2a / 2b** | Unchanged. The split is right and `body-layer/CLAUDE.md`'s rule requires it. |
| **3** | Unchanged in shape; branch 1's air-defence predicate corrected per A3. |
| **4** | Unchanged, **conditional on Stage 0**. Without a bounded extent its heading input is membership noise (A2.2). **The speech-time extent guard is unconditional, not a fallback** — do not speak a heading or a single bearing for a group wider than one believable bearing. (Corrected 2026-10-11, Stage 0 review observation 1. This read *"if Q-A declines 0b, Stage 4 needs an extent guard at speech time instead"*. Q-A/Q-B were **accepted** and 0b shipped, so the condition is settled — but 0b caps a *pair*, not a cluster, and single-link chaining still permits a 1.2 km span: `tests/test_groups.py::test_the_eager_cap_still_chains_a_long_infantry_line` pins four infantry at 400 m spacing, 3 gaps × 400 m = 1,200 m, as one group. Against `_format_range_km`'s 500 m bucket that is 2.4 buckets wide, so the guard is needed *with* 0b rather than instead of it. It is also the natural consumer of the `extent` field A4's trace line already requires.) |
| **5** | **Recommendation unchanged and now stronger.** The body's effort/value read used 51.6 ms; the real figure is 84.6 ms in situ, and `BL-B49` is unresolved on the same call. Keep the cheap anisotropic stand-in as a *proposal*, move the graph corridor to `BL-8`. Still Q1 for the user. |
| **6** | Unchanged, still last. Its stated precondition (Stages 1 and 3 in first) is unaffected. |

**Why Stage 0 is not simply folded into Stage 1.** It is upstream of it, it is independently
testable and mergeable, and it is the one change on this branch that is **worth flying on its own**
— it is live on the push path today and fixing it needs none of BL-12's new state.

---

## A7 — Corrections to specific claims in the body

| passage | correction |
|---|---|
| Interaction, `BL-11` Stage 2 bullet — *"Land `BL-11` Stage 2 first, or accept a measurable regression"* | **Discharged.** Landed; see A1. Also: the hoist is 5.1×, not the 8.1× the module docstring claimed before `BL-11`'s performance pass corrected it. |
| Interaction, `BL-11` Stage 3 bullet | **Discharged.** `WorldEnrichmentCache` landed, 89.7 % hit rate within a callout tick, from a measured 0 %. |
| Stage 5 hard constraint — *"51.6 ms median on `syria-full`"* | **84.6 ms per call in situ**, 57.4 ms standalone median; every call shape costs the same. The constraint is stronger. |
| Risks — *"Knowledge-graph query returned 'No graph yet'… so the graph step produced nothing"* | **No longer true.** `.claude/scripts/gq.sh` answered from the main checkout's graph (10,915 nodes, 565 reached). It surfaced the modules and functions this amendment cites — `GroupStore`, `render_group_disclosure`, `group_membership_state`, `group_callout_member_id`, `contacts_plausibly_same`, `WorldEnrichmentCache` — and **no prior plan document that was not already in hand**, so the body's "prior work found by reading plans directly" conclusion stands on its evidence. Today's merges are not in the semantic layer yet. |
| Risks — `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` / `GROUP_PROXIMITY_GAP_RATIO` *"not this plan's to fix"* | **Narrowed, not reversed.** Still true for the two constants' *calibration*. **False for `BL-B48`**, which is a composition defect in the same function and is now Stage 0. A second, unrecorded instance is named in A2: the relative test cannot reject any pair at n = 2 when the absolute backstop is infinite. |

---

## A8 — The user's decisions are intact, and what now cuts against them

**D3–D10 are untouched by this amendment.** D5's inversion and its stated error preference —
*"If a new group is mistakes as existing group, it's the unusual occurence and I can live with that
easier than new group beliefs popping up all the time"* — stand exactly as written, and nothing
here re-decides them.

**One piece of evidence cuts against a decision and is flagged rather than resolved.** The user's
*"ok to merge infantry too eagerly"* (which produced `_OP_CLASS_COHESION_BACKSTOP`) is being applied
to **pairs**, so it currently merges armour across 6 km. Whether that was meant is his call, not
this plan's — **Q-A**. The recommendation (both-EAGER) is the reading that keeps his sentence
literally true about infantry and nothing else, but it is a recommendation.

---

## Questions for the user — new in this amendment

These are in addition to the body's Q1–Q6, which all still stand.

- **Q-A (blocking Stage 1) — does *"ok to merge infantry too eagerly"* extend to merging armour
  across 6 km?** Measured: `armor@1km + truck@3km` is correctly two separate things; add
  `infantry@7km` and all three become one group 6 km wide. Recommendation: **no** — apply the
  eagerness to infantry pairs only (one word, precedented by the installation rule in the same
  function, infantry-to-infantry behaviour bit-identical). If he agrees, Stage 0a goes in before
  Stage 1.
- **Q-B — should a group have a maximum extent at all?** Even after Q-A, two infantry contacts form
  one group at *any* separation, because the relative test cannot reject a pair at n = 2 once the
  absolute backstop is infinite. A finite eager cap (in metres, or as a multiple of the ordinary
  unit-widths backstop) would close it. His number, his call — and the pilot-facing version of the
  question is: *at what width does "that group, two o'clock, three kilometres" stop being true?*
- **Q-C — is the group-identity sortie trace line accepted as part of Stage 1** rather than a
  suggestion? It is the only way the rarity his D5 preference rests on becomes checkable, and it
  also makes `BL-B50`'s lapse condition evaluable. Cost: one JSONL line per reconcile.

---

### What already exists, and what the churn mechanism actually is

Read before designing anything here, because three of the four mechanisms D4/D5 appear to ask for
are already in the tree and one of them is already the primary path.

1. **Cluster-level object permanence already exists and already uses DCS object ids.**
   `naked_eye_source` keeps a persistent `_object_id_to_last_observation_id: dict[int, str]` and
   resolves each cluster's `continues_observation_id` by **majority object overlap** across the
   whole batch (`src/perception/naked_eye_source.py:675-740`, module docstring point 6).
   `ContactStore._resolve_continuity` (`contacts.py:977`) is the consumer; the gate is already "the
   exception path, not the common case" (`association_over_time.py` docstring).
   **D3's relaxation therefore needs no new permission** — the object id is consumed inside
   `perception/` and only an `observation_id`-shaped reference crosses `percept.py`
   (`plans/contact-duplication-ambiguity-runaway/plan.md`, "Boundary reading"). What D3 *does*
   change is the **bound**: `OBJECT_ID_MEMORY_S = IDENTITY_HALF_LIFE_S = 600.0` (`decay.py:220`) is
   exactly the "oracle across occlusion and long gaps" D3 forbids. See Stage 6.

2. **Position-uncertainty growth is already parameterised.**
   `Covariance2D.inflated(elapsed_s, growth_rate_mps = GATE_GROWTH_RATE_MPS)`
   (`position_belief.py:256`) already takes the rate as an argument with a default. D8 is therefore
   a threading change at **three** call sites (`association_over_time.py:63` is a docstring,
   `:310`, and `position_belief.py:219`), not a new mechanism.
   **Coupling to check before touching the number**: `POSITION_HALF_LIFE_S = 30.0`'s own docstring
   derives 30 s *from* 20 m/s ("the time a ground vehicle needs to move roughly its own uncertainty
   radius at `GATE_GROWTH_RATE_MPS`"). Two `assert`s in `decay.py:174/188` bind
   `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S`. Leaving `POSITION_HALF_LIFE_S` alone keeps both
   asserts intact, but its docstring's derivation goes stale the moment the default rate moves —
   it must be corrected in the same commit as the calibration, or it reads as evidence for a number
   that no longer exists.

3. **`Group` exists, and group identity is reconciled by member-contact-id overlap only.**
   `GroupStore.reconcile` (`groups.py:553`) recomputes clusters every tick and matches them to
   persisted groups by **majority member-id overlap**, then *replaces the whole store*: "a persisted
   group with no matching cluster … is simply dropped."
   **This is the mechanism by which contact churn becomes group churn.** When `ingest` re-founds the
   same real vehicles under fresh contact ids (`BL-B24`: 554 contacts for 444 objects, 81 % of
   objects carrying 2+ contact ids), the next `reconcile` sees **zero** member overlap and founds a
   brand-new `Group` — losing `established_sim`, `last_spoken_signature` and the whole disclosure
   history. D7's "that column, still moving north" is unreachable through that path regardless of
   how the contact layer behaves.

4. **A group-level direction belief does not exist.** `MotionBelief` is `"moving"`/`"stopped"` with
   no direction (`belief/motion.py:48`). The only direction anywhere is
   `enrichment.motion_when_seen` (`enrichment.py:728`), derived from the **two most recent distinct
   raw implied percept positions** with "no smoothing/averaging — a single noisy percept can flip
   the reported direction" (its own docstring). That is unusable for D7's spoken direction and for
   D9's monotone test, and it also bypasses the fused `PositionEstimate` that
   `precise-position-belief` exists to produce. D7/D9 need a new, group-level, fused-centroid-derived
   direction.

**Consequence for the design: the cheapest place to honour D4/D5/D7 is `GroupStore.reconcile`, not
`ContactStore.ingest`.** Group identity must survive member-id *replacement*. The contact-level
ambiguity rule is then a second, smaller change (Stage 3) that stops the churn at source.

---

### Affected Modules / Files

- `body-layer/src/belief/groups.py` — the bulk of the work. `Group` gains a remembered property
  signature and a last-observed timestamp; `reconcile` goes from two phases (overlap-match, found)
  to four (overlap-match → **property-match** → found → **expire**); a new pure
  `group_matches(remembered, observed, elapsed_s)` predicate; a per-class plausible-speed table.
- `body-layer/src/belief/contacts.py` — `ingest`'s ambiguity branch (`:965-970`) gains the
  within-group tiebreak (Stage 3). `tick`'s eighth block (`:1422`) passes `now_sim` to a
  `reconcile` that now also expires — no signature change needed.
- `body-layer/src/belief/position_belief.py` — `GATE_GROWTH_RATE_MPS` becomes the *fallback* of a
  per-`op_class` table (Stage 2b); a `growth_rate_for(op_class)` lookup is added. `inflated`'s
  signature is already right.
- `body-layer/src/belief/association_over_time.py` — `_contact_covariance` (`:303`) threads the
  contact's own class-derived rate into `inflated`. No formula change.
- `body-layer/src/belief/decay.py` — `GROUP_REIDENTIFY_WINDOW_S` (new, D10-bounded) joins the one
  table, per that module's own "a future pass extends this table rather than starting a second one".
  `POSITION_HALF_LIFE_S`'s docstring corrected (see above). `OBJECT_ID_MEMORY_S` shortened (Stage 6).
- `body-layer/src/belief/speech.py` — `render_group_disclosure` gains the persistent-identity and
  direction wording (D7). Smallest possible diff; the taxonomy itself is untouched.
- `body-layer/src/perception/object_model.py` — **read-only**. `installation_component`, `op_class`
  and `AIR_DEFENSE_OP_CLASSES` (in `groups.py:234`) are the existing vocabulary this plan keys on;
  no new field.
- `body-layer/tests/test_groups.py`, `test_contacts.py`, `test_callouts.py` — see "Tests that must
  be rewritten".
- **Not touched**: `belief/percept.py` (no new boundary crossing anywhere in Stages 1–4),
  `perception/clustering.py`, `perception/group_salience.py`, `belief/threat.py`.

---

### Implementation Plan

> **Amended 2026-10-11 — a blocking Stage 0 precedes Stage 1.** See the amendment's **A2**: the
> clusters Stage 1 reconciles over can be 6 km wide (`BL-B48`), which breaks Stage 1's displacement
> test and Stage 4's heading. Stage 0 bounds group extent first.

Each stage is independently testable and mergeable. The no-omniscience check is stated per stage
because every stage in this plan reads believed classification (`Contact.last_class_raw` →
`object_model.profile_for`), which is the sanctioned path (`groups.py:304` `_profile_for_contact`),
never a DCS `object_type`.

#### Stage 1 — Group identity survives member-id replacement (minimal working version)

The one change that makes D4/D5/D7 reachable, with `ingest` untouched.

`Group` gains, all additive with defaults so every existing construction site compiles unchanged
(the same merge criterion `group-contact-model` Stage 1 used for `Contact.cardinality`):

| field | meaning |
|---|---|
| `last_observed_sim: float` | the last reconcile at which a cluster actually matched this group. Distinct from `last_reconciled_sim`, which currently means the same thing only because unmatched groups are dropped. |
| `centroid_x: float`, `centroid_z: float` | mean of the matched cluster's `Contact.position` (x, z). Needed because the members may be gone by the time a match is attempted. |
| `centroid_uncertainty_m: float` | RMS of members' `position.radius_m()`. The slack term in the displacement test. |
| `composition: tuple[tuple[str, int], ...]` | sorted `(op_class, count)` multiset over members, via `_profile_for_contact`. |
| `installation: bool` | every member's `profile.installation_component` is `True`. |
| `air_defence_composition: tuple[tuple[str, int], ...]` | the subset of `composition` whose `op_class` is in `AIR_DEFENSE_OP_CLASSES`. Separate field, not re-derived at match time, because D6 keys on it and it must be the remembered value, not a recomputation from members that may be gone. |

`reconcile` becomes four phases:

1. **Overlap match** — unchanged, exactly today's greedy-by-member-overlap pass. A group whose
   members survived keeps its id through the path it already does. This stays *first* so nothing
   about today's split/merge behaviour changes.
2. **Property match** — for each cluster still unmatched, against each persisted group still
   unclaimed, in descending order of `group_match_score` (see the predicate below): if
   `group_matches(...)` passes, the cluster claims that group's id, `established_sim` and the whole
   `last_spoken_*` snapshot — the same carry-over rule phase 1 already applies.
3. **Found** — unchanged, for clusters that matched nothing.
4. **Expire** — a persisted group that matched no cluster this reconcile is **kept**, with its
   properties frozen, until `now_sim - last_observed_sim > GROUP_REIDENTIFY_WINDOW_S`, then dropped.
   This is the change that makes phase 2 possible at all: today an unobserved group is gone before
   the cluster comes back.

`GroupStore.groups` must keep returning only *currently observed* groups, or every existing
consumer (`speech.render_group_disclosure`, `tools.py`, `callouts.py`) starts rendering remembered-
but-unseen groups. Add `GroupStore.remembered_groups` for phase 2's own use and leave `groups`
meaning what it means today. **This is the one place a careless implementation silently changes
pilot-facing output.**

**The matching predicate, concretely** — evaluated in this order, cheapest and hardest first. Every
threshold's provenance is labelled.

| # | test | threshold | provenance |
|---|---|---|---|
| 1 | elapsed window | `now_sim - group.last_observed_sim <= GROUP_REIDENTIFY_WINDOW_S` (**60.0 s**) | **derived** — 2 × `POSITION_HALF_LIFE_S` (30.0), and bounded by D10's "seconds to a minute". Past it, nothing here matches; that is `BL-8`'s horizon by decision, not by cost. |
| 2 | kind coherence (hard) | `group.installation == observed.installation` | **user direction**, D4: *"Different type of group, e.g. AAA installment (especially entrenced = not capable of movememnt) would be different than other units that are nearby."* Keyed on the existing `installation_component` field — no new vocabulary. |
| 3 | air-defence confirmation (hard) — **resolution path superseded, see amendment A3: read `classification._op_class_of`, not `profile_for`, or four of five air-defence classes fail this gate at class level (measured)** | if either side's `air_defence_composition` is non-empty, require **equality** of both sides' `air_defence_composition` | **user direction**, D6. This is the one gate where ambiguity does *not* resolve toward the remembered group: positive confirmation is required, because `threat.envelope_for` keys the danger call on believed classification, so a wrongly-continued SAM **suppresses the warning** rather than mislabelling a contact. |
| 4 | composition compatibility (hard) | the two sides' non-air-defence `op_class` **sets** must not be disjoint-in-both-directions: one must be a subset of the other | **user direction**, D4: a *different kind* appearing is evidence of a new group. **Count is deliberately not gated** — the user's own words cover both directions: more members than memory means *"some unit(s) have to be newly detected"* (new members of a continuing group), and *"I see more units from a different angle and maybe some are hidden by buildings"* means fewer is occlusion. A count test would be brittle in exactly the case the user described as normal. |
| 5 | displacement plausibility (hard) | `hypot(Δcentroid) <= speed_bound_mps * elapsed_s + slack_m`, where `slack_m = group.centroid_uncertainty_m + observed.centroid_uncertainty_m`, and `speed_bound_mps = 0.0` when **both** sides' movement state is `"stopped"`, else `max(plausible_speed_mps(op_class) for op_class in group.composition)` | **mixed** — the zero-when-both-stopped rule is **user direction**, D4: *"If I see no movement, then I especially expect that the units I remember have not moved."* The speed table is **stated assumption**, scaled by user direction (D8, *"20 m/s is fast for most units… Expect slower"*) — see the table below. `max` over classes, not `min`, because this is a plausibility *bound*, and bounding by the slowest member would reject a real match. |
| 6 | **ambiguity resolution (D5's inversion)** | more than one remembered group passing 1–5 → **nearest centroid wins**, then lowest group id | **user direction**, D5: *"If a new group is mistakes as existing group, it's the unusual occurence and I can live with that easier than new group beliefs popping up all the time."* Supported by the **measured** cluster separation (explore notes §2: median cluster-to-cluster nearest separation 236 m at 100 m link, 625 m at 250 m link) — two remembered groups both inside one displacement bound is rare, not typical. Count the occurrences in a store-level counter so the rarity stays **observable** rather than assumed. |

**`group_match_score`** (phase 2's ordering, not a gate): `-hypot(Δcentroid)`. Deliberately not a
composite score — a weighted score is the "best-match tiebreak" `pb2-contact-memory` Stage 1 refused
to build, and reintroducing one as a *gate* would be relitigating. Here it only orders candidates
that have already independently passed every hard test.

**No-omniscience check**: `reconcile` takes `Contact` objects, as it already does
(`groups.py:139`). Every property above is computed from `Contact.position` (fused belief) and
`Contact.last_class_raw` (believed classification). No `Observation`, no DCS object id, no
`derived_world_position`. Unchanged boundary.

#### Stage 2 — Per-classification uncertainty growth (D8), as two commits

**`body-layer/CLAUDE.md`'s "Mechanism and calibration never share a commit" applies directly here**,
so this is deliberately split:

- **2a, mechanism.** Add `position_belief.plausible_speed_mps(op_class) -> float`, returning
  `GATE_GROWTH_RATE_MPS` for every class. Thread the contact's own class-derived rate through
  `association_over_time._contact_covariance` and `position_belief._inflated_since_last_fuse`
  (which needs the rate passed in — `PositionEstimate` does not know its own classification, and
  should not; the caller in `Contact.record` does). **Provably no behaviour change**: the acceptance
  test is bit-identical gate outcomes against the current implementation, the same posture
  `BL-11` Stage 2 takes for the `group_salient_ids` hoist.
- **2b, calibration.** Populate the table. Every row is a **stated assumption**, scaled by user
  direction; none is measured.

| key | m/s | basis |
|---|---|---|
| `installation_component is True` | **0.0** | **user direction**, D8: "~0 for entrenched". Structural — keyed on the existing profile field, not an `op_class` list, for the same reason `group-cohesion-redesign` §1 rejected an `op_class`-keyed installation set. |
| `OP_INFANTRY` | 2.0 | stated assumption — dismounted pace. |
| `OP_ARMORED` | 8.0 | stated assumption, scaled from D8 (≈29 km/h sustained; the user says 20 m/s is near armour's *full* speed). |
| `OP_SPAAG`, `OP_ZU23`, `OP_SRSAM`, `OP_MRSAM`, `OP_LRSAM` (non-installation) | 8.0 | stated assumption — same band as armour. |
| `OP_TRUCK` | 15.0 | stated assumption — road truck, deliberately below the old flat 20. |
| `OP_SHIP` | 10.0 | stated assumption. |
| default, incl. `OP_GROUPSOMETHING` | 8.0 | stated assumption. **Deliberately not 20**: the old value modelled the worst case for everything, which is the behaviour D8 overturns. |

One table, consumed by both Stage 1's displacement bound and the gate's inflation, so the gate and
the group matcher can never disagree about how fast a class could have moved — the same
single-source reasoning `association_over_time.percept_position_uncertainty` already applies to
uncertainty.

**Also in 2b**: correct `POSITION_HALF_LIFE_S`'s docstring, which currently derives 30 s from
20 m/s. Leave the value alone (both `decay.py` asserts stay intact) and state plainly that the
derivation no longer holds and why, rather than leaving a stale derivation reading as evidence.

**No-omniscience check**: `plausible_speed_mps` takes an `op_class` string resolved from
`last_class_raw`. Unchanged boundary.

#### Stage 3 — Within-group ambiguity resolution (D5 at contact grain, D6 carve-out)

This is the stage that dissolves `BL-B24` and the 554-contacts-for-444-objects churn.

`ingest`'s ambiguity branch (`contacts.py:965`) becomes, when `len(passing) >= 2`:

1. If **any** passing candidate's `last_class_raw` resolves to an `op_class` in
   `AIR_DEFENSE_OP_CLASSES` → **found a new contact** (today's rule). D6: a visible duplicate is the
   safe direction for a threat; a wrong fold is not.
   > **Resolution path superseded 2026-10-11 — amendment A3.** "Resolves" here must mean
   > `classification._op_class_of`, not `object_model.profile_for`; via `profile_for` a class-level
   > SAM belief falls into the default bucket and this branch never fires. That is `BL-B47`,
   > merged 2026-10-11.
2. Else if **every** passing candidate is currently a member of one and the same `Group`
   (`self._groups.group_for_contact`) → **fold onto the nearest, then lowest id.**
3. Else → **found a new contact** (today's rule, unchanged).

**Why this does not reopen what the old invariant was protecting against.** The old rule's purpose
was to never collapse two things the pilot cares about separately into one record
(`association_over_time.py` docstring: "ambiguity must produce a visible duplicate, never a guessed
merge"). Branch 2 fires only when the candidates are *already believed to be one group* — i.e.
exactly when the pilot does **not** care separately, by this codebase's own cohesion rule. And the
measurement settles the alternative: at 16 m median nearest-neighbour spacing against a gate that
inflates to ±600 m in 30 s, there is no radius that both separates and tolerates
(`plans/contact-duplication-ambiguity-runaway/debug.md` escalated precisely this and said it needed
real spacing data; explore notes §2 supplies it). Founding a third contact does not preserve
information — it **destroys** the count, which is the thing the pilot actually hears.

Branch 3 keeps the invariant exactly where it still earns its place: two candidates in *different*
groups, or ungrouped, where the choice does carry information.

**New failure modes this accepts**, stated because the user accepted them explicitly:

1. **Within-group record swapping.** Two genuinely distinct units in one group can exchange contact
   records across a gap. `contributing_observation_ids` and `sighting_spans` become unreliable at
   *within-group* grain. `describe_contact`/`get_contact_history` are the readers; the group-level
   answer stays correct. (Related, pre-existing and now reached more often: the
   ambiguity-runaway plan's own note that `_extend_or_open_span` never splits a span on a time gap.)
2. **Undercount replaces overcount.** A genuinely new unit arriving inside an existing member's
   gate is folded rather than founded. Today's rule over-counts (554/444); this one can under-count.
   Bounded by D6's carve-out, and by the fact that primary cardinality evidence is naked-eye's own
   `count_bucket` per cluster, not the contact count (`cardinality.py`, `group-contact-model`
   Stage 2) — so an under-count in contact records does not by itself under-report the group.
3. **False group continuity** (Stage 1 phase 2): a different real group arriving where a remembered
   one left, within 60 s, with compatible composition, inherits its id, `established_sim` and
   disclosure history — so Petrovich may say "that column" of units he has not seen before. This is
   the error D5 names and accepts.

**No-omniscience check**: branch 2 reads `GroupStore.group_for_contact` and `Contact.position`.
Unchanged boundary.

#### Stage 4 — Group movement state and direction (D7's spoken identity)

`Group` gains:

- `movement_state: MotionState | None` — the majority of members' `Contact.motion.state`, `None`
  when no member has a motion belief (honestly `None`, the same posture `belief/motion.py`'s
  docstring argues for `Contact.motion`).
- `heading_deg: float | None` and `heading_confidence: float` — derived from **centroid
  displacement between successive reconciles of the same group id**, not from raw percepts. Held
  only while `movement_state == "moving"`; cleared on a confirmed stop. Smoothed over the last N
  reconciles (propose N = 5, ~5 s at the 1.0 s poll — **stated assumption**), explicitly because
  `enrichment.motion_when_seen`'s unsmoothed two-look derivation is documented as flippable by one
  noisy percept and must not be the source for spoken direction.

`speech.render_group_disclosure` then renders D7's line — *"that column, now 2 o'clock, three
kilometres, still moving north on the road"* — with the "still" available because the group id
survived (Stage 1) and the direction available here. Keep this diff minimal: the delta taxonomy
(`group-cohesion-redesign` §4) is not touched, only the wording a continuing group gets.

**Leave `enrichment.motion_when_seen` alone.** It answers a per-contact question for a different
consumer; replacing it is scope this plan does not need.

**No-omniscience check**: derived entirely from fused `Contact.position` means and folded
`Contact.motion`. Unchanged boundary.

#### Stage 5 — Road-following (D9) — see the effort/value read; recommended for `BL-8`

Recommendation is to build the **cheap half now** and move the graph half to `BL-8`:

- **Now (cheap):** make the displacement bound in Stage 1 test 5 **anisotropic** — elongated along
  a remembered road axis, tighter across it. The axis comes from
  `query.describe.describe_position(...).nearest_road.orientation_deg`, resolved **once per group,
  cached on the `Group`**, refreshed only when the centroid moves materially. No graph, no junction
  logic, no per-tick world-model query.
- **Deferred to `BL-8`:** the corridor that *branches at junctions* and is *monotone in direction*.
  Reasons in the effort/value read below.

**Hard constraint if this stage is built** (figure superseded 2026-10-11 — amendment A7: the real
cost is **84.6 ms per call in situ**, every call shape identical, and `BL-B49` is unresolved on the
same call; the constraint is *stronger*): `describe_position` is measured at **51.6 ms median on
`syria-full`** (`BL-11` Stage 3). A per-group-per-tick road query would be a larger term than the
one `BL-11` Stage 3 exists to remove. Cache per group, or do not build it.

#### Stage 6 — Shorten object-id continuity to the short horizon (D3's bound, D10's seam)

**Deliberately last, because it removes a mechanism.** `OBJECT_ID_MEMORY_S = IDENTITY_HALF_LIFE_S =
600.0` currently trusts an object-id continuity match across a ten-minute gap, which is exactly
D3's forbidden oracle. Shorten it to the belief layer's own horizon
(`GROUP_REIDENTIFY_WINDOW_S`, 60 s) so that beyond it, re-identification goes through Stage 1's
group-level predicate — a human-shaped judgement — and beyond *that*, through `BL-8`.

This must land only after Stages 1 and 3 are in, or it re-opens the churn it was introduced to fix
(`contact-duplication-ambiguity-runaway` is explicit that correlation is now the primary path for
"the overwhelming majority of a live session's percepts"). Expect a measurable contact-count change
on this stage specifically; re-measure against the same sortie logs.

---

### Interaction with already-merged and in-flight work

> **Amended 2026-10-11.** Both `BL-11` dependencies below have **landed** — amendment **A1**. Six
> further rows (`BL-13`, `BL-B47`, `BL-B48`, `BL-B49`, `BL-B50`, `BL-B51`) are in **A5**.

- **`BL-11` Stage 2 (`group_salient_ids` hoist, `@lru_cache` on `profile_for`)** — a **dependency**,
  not a conflict. Stage 1 computes a `composition` per cluster per reconcile via
  `_profile_for_contact`; without the `lru_cache` that is another `profile_for` pass over every
  contact every tick. Land `BL-11` Stage 2 first, or accept a measurable regression.
- **`BL-11` Stage 3 (`describe_position` memo)** — governs whether Stage 5 is affordable at all; see
  the hard constraint above.
- **`plans/contact-report-flood`'s merge-echo suppression** — keyed on
  `contacts_plausibly_same` + `CONTACT_DETECTED`. Stage 3 removes most of the re-foundings that
  suppression exists to silence, so the suppression becomes mostly inert rather than wrong. Its
  documented cost ("structurally unable to distinguish that merge-echo from a genuine split") is
  *reduced*, not changed in character. Needs a plan amendment, not a code change — see below.
- **`plans/redundant-group-disclosure`** — silences a group's opening line re-announcing already-
  reported members. Stage 1 makes group ids persist, so that suppression now has a *stable* key to
  work against, which is the condition it was written assuming. Verify, do not assume.
- **`CALLOUT_OBSERVABILITY_GRACE_S` / D11 (observability gate on every callout kind)** — D11 is not
  this plan's; but Stage 4's new spoken group line is a **new callout kind**, and it must go behind
  `_callout_may_speak` from the first commit rather than be retrofitted. That is exactly the gap
  D11 records (20 of 357 lines named masked hours).

---

### What `BL-8` will need from this design (D10's seam, stated explicitly)

The belief layer keeps **seconds to a minute**; `BL-8` takes the rest. Two things are exported for
it, and both should be built in the shape `BL-8` needs rather than retrofitted:

1. **`GroupMemory`** — a plain serialisable value (floats, strings, tuples; no live reference into
   `ContactStore`), the same posture `PositionEstimate` adopted for exactly this reason
   (`position_belief.py` docstring, "BL-8, and what not to foreclose"): group id, `established_sim`,
   `last_observed_sim`, centroid + uncertainty, `composition`, `air_defence_composition`,
   `installation`, `movement_state`, `heading_deg`, and the cached road axis if Stage 5 lands. A
   `Group` should be projectable to one without `BL-8` importing `belief.groups` internals.
2. **`group_matches(remembered, observed, elapsed_s, *, window_s, speed_table)`** — the predicate as
   a **pure function with its thresholds injected**, so `BL-8` reuses the same judgement at a
   ten-minute horizon with its own window and its own (road-graph-informed) displacement bound,
   rather than writing a second, diverging matcher. The thresholds being parameters is the whole
   point of the seam.

`BL-8` also inherits the **road-corridor** half of D9 and the **spatial-expectation** capability
(*"on the other side of the ridge there's a group of units, we better not go there"*), which the
explore notes already assign to it.

---

### Tests that must be rewritten, not extended (AGENTS.md escalation)

- `tests/test_contacts.py:132 test_two_ambiguous_candidates_create_a_new_contact_not_a_merge` —
  pins the exact behaviour Stage 3 branch 2 inverts. Rewritten: the same geometry must now
  demonstrate *both* branches (within-group → fold; cross-group → found), and keep the old
  assertion for branch 3.
- `tests/test_contacts.py:183` (reuses that geometry by name) — re-derive.
- `tests/test_callouts.py:489-554` — a merge-echo fixture built *on top of* that ambiguity
  behaviour, with the dependency written into its docstring. Its scenario stops occurring once
  Stage 3 lands; it needs a cross-group geometry to still exercise what it is testing.
- `tests/test_groups.py` — extended, not rewritten. The retention change (phase 4) means a group
  with no matching cluster is no longer dropped on the *same* reconcile; any test asserting
  immediate disappearance needs a `now_sim` past `GROUP_REIDENTIFY_WINDOW_S`.
  `test_constants_are_the_stated_assumptions` (`:355`) must gain the new constants.

---

### Risks & Unknowns

- **The 236 m/625 m cluster-separation figures come from one sortie**, deduplicated by `object_id`.
  Test 6's "two remembered groups both passing is rare" rests on them. If a denser mission makes it
  common, the counter added in test 6 is what will show it — which is why the counter is part of the
  design and not an optional observable.
- **Stage 1 phase 2's false-continuity rate is unmeasurable from existing logs** (no group-identity
  trace exists). The 60 s window and the composition test are the only things bounding it. Consider
  a group-identity line in the sortie trace before flying Stage 1, or the first evidence will be
  the pilot noticing a wrong "that column". **Promoted from a suggestion to Stage 1's first commit,
  2026-10-11 — amendment A4** (D5's acceptance is a rarity claim, and nothing can currently check
  it; `BL-B50`'s lapse condition is unevaluable without it too).
- **`GroupStore.groups` vs `remembered_groups`** is the sharpest silent-failure surface in this
  plan: a consumer that reads the wrong one starts speaking about groups nobody can see — the same
  class of defect as D11's masked-hour callouts.
- **D3's underlying probe is still unresolved and this plan does not depend on it.** Whether the
  Hook can supply an id that joins to `LoGetWorldObjects`'s key
  (`aircraft-layer/research/2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md`
  line 139) is queued for the user. **What improves if it lands**: the LOS join
  (`BL-11` Stage 4) stops dropping 76 % of objects, which makes `live_los_clear` meaningful for
  group members and lets Stage 1 distinguish "members occluded" from "members gone" — currently
  test 4's subset rule has to assume occlusion. Nothing in Stages 1–6 requires it.
- **`OBJECT_ID_MEMORY_S` shortening (Stage 6) is a behaviour regression risk by construction** —
  it removes the mechanism that the ambiguity-runaway fix made primary. Its own plan's Risks section
  flags object-id stability across multi-minute gaps as "a weaker desk-research claim", which argues
  *for* shortening; but the contact-count effect must be measured, not assumed.
- **Stage 4's heading smoothing window (N = 5) is an uncalibrated placeholder**, the same debt class
  as `MOTION_STOP_CONFIRM_S` and `GROUP_PROXIMITY_GAP_RATIO`: named, isolated, movable in one place.
- **`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` (20.0) and `GROUP_PROXIMITY_GAP_RATIO` (3.0) remain
  uncalibrated stated assumptions** feeding the clustering this whole plan reconciles over. A wrong
  cluster boundary makes the composition test compare the wrong things. Not this plan's to fix, but
  it is upstream of everything here.
  > **Narrowed 2026-10-11 — amendment A2/A7.** Still true of those two constants' calibration.
  > **False for `BL-B48`**, a composition defect in the same function, which is now blocking
  > **Stage 0**: BL-12 does not dissolve it, it amplifies it.
- **Knowledge-graph query returned "No graph yet. Build it with /graphify, then query."** from this
  worktree, so the graph step produced nothing. **Superseded 2026-10-11 — amendment A7**: the graph
  answered (10,915 nodes) and surfaced no prior plan document that was not already in hand, so this
  bullet's conclusion survives on different evidence. The prior work was found by reading
  `plans/contact-duplication-ambiguity-runaway/`, `plans/group-contact-model/`,
  `plans/group-reporting/` and the modules directly. Recording this because a miss means "not
  indexed", never "does not exist" — a rebuild before the next planning pass on this area would
  likely surface more.

---

### Effort/value read

**Stages 1–4 are worth building and the effort is proportionate.** Stage 1 is the single highest-
value change in the plan: it is the mechanism by which contact churn reaches the pilot, it is
contained in one small module, and it unblocks D7 — which is the pilot-facing payoff of the whole
conversation. Stage 3 is small and dissolves `BL-B24` directly. Stage 2 is a threading change
against an already-parameterised function.

**Stage 5 as D9 literally specifies it is where I would push back.**

1. **The challenge.** "A directional corridor along the road graph, branching at junctions" needs a
   *routable* road graph — junction adjacency, segment traversal, direction monotonicity. World-model
   exposes `nearest_road` and `nearest_junction` only as **point** facts inside `describe_position`
   (`world-model/src/query/describe.py:414/537`); there is no traversal API, and `describe_position`
   is 51.6 ms median on `syria-full`. So this is a world-model milestone — a new index and a new
   query on top of `M10`'s junction detection — plus a body-layer consumer, not a belief-layer change.
2. **Why the value is smaller than it looks at this horizon.** D10 caps the belief layer at
   seconds-to-a-minute. At the Stage 2b armour rate, 60 s of displacement is ~480 m. The **measured**
   median cluster-to-cluster separation is 236 m (100 m link) to 625 m (250 m link). So inside the
   belief layer's own window, an isotropic bound plus the composition and kind tests is already in
   the same discrimination band the corridor would buy — the corridor is narrowing a region that is
   not the thing failing. What *is* failing is that group identity does not survive at all (Stage 1),
   which the corridor does not address.
3. **Where it does pay for itself, and the cheap version now.** At `BL-8`'s ten-minute horizon the
   same rate gives ~4.8 km, where a disc is useless and a road is decisive — and `BL-8` is already
   where D10 puts the long horizon and the spatial-expectation capability. Recommendation: **move
   the graph corridor to `BL-8`**, and take the cheap anisotropic stand-in now (Stage 5's first
   bullet): elongate the existing displacement bound along a per-group cached
   `nearest_road.orientation_deg`. That captures "units follow roads" at roughly zero cost, with no
   graph, no junctions, and no per-tick query.

This is advice. If the full corridor is wanted in this feature, say so and it gets built properly —
but it should then be scoped as a world-model milestone first, not as a stage of this plan.

---

### Second-order effect

This gives `BL-8` its **first concrete interface** (`GroupMemory` + a threshold-injected
`group_matches`) rather than a prose requirement, and simultaneously **enlarges** `BL-8` by moving
D9's road corridor and the long-horizon window into it. It also makes `BL-B24`'s own numbers
(554 contacts / 444 objects, 81 % of objects with 2+ contact ids) the re-measurable acceptance
criterion for Stage 3, from logs that already exist.

---

### Plan amendments this design forces (per `docs/PROCESS.md`, "Superseding a decision")

To be written as numbered sub-decisions when this plan is accepted — the originals stay in place
with a pointer, never deleted or rewritten:

- **`plans/pb2-contact-memory/plan.md` Stage 1, "never a guessed merge"** — superseded *within a
  group* by D5/Stage 3. The invariant stands for the cross-group and ungrouped cases; the premise
  that failed was an unwritten density assumption the user has now contradicted (explore notes §2).
- **`plans/contact-duplication-ambiguity-runaway/plan.md`, Decision** — states "Still not gate
  re-tuning, still not relaxing the ambiguity policy". The ambiguity policy is now relaxed, in a
  bounded way. Also: its `OBJECT_ID_MEMORY_S = 600 s` reasoning is narrowed by D3/Stage 6.
- **`plans/group-reporting/plan.md` Stage 2** — `reconcile`'s "a persisted group with no matching
  cluster is simply dropped" is replaced by retention + property match.
- **`plans/contact-report-flood/plan.md` Stage 1** — its merge-echo suppression's premise (frequent
  re-founding) is substantially removed by Stage 3; the suppression's accepted cost shrinks.

---

### Questions for the user (queued, not blocking the read)

> **Amended 2026-10-11.** All six below still stand. **Three more were added, and the first of them
> blocks Stage 1** — see the amendment's "Questions for the user — new in this amendment" (Q-A
> infantry cohesion, Q-B maximum group extent, Q-C the trace line).

1. **D9 / Stage 5 — accept the recommendation?** Build the cheap anisotropic road-axis bound now and
   move the junction-branching corridor to `BL-8` (where D10 already puts the long horizon and where
   it needs a new world-model traversal query either way)? Or build the full corridor in this
   feature, scoped as a world-model milestone first?
2. **`GROUP_REIDENTIFY_WINDOW_S = 60 s** — D10 says "seconds to a minute". Is a minute the right
   edge, or should the belief layer hand off sooner (30 s, = `POSITION_HALF_LIFE_S`)?
3. **The Stage 2b speed table** — every row is a stated assumption scaled from *"expect slower"*.
   Are armour at 8 m/s and truck at 15 m/s roughly right from the cockpit, or still too fast?
4. **Three tests must be rewritten rather than extended** (`test_contacts.py:132`, `:183`, the
   `test_callouts.py` merge-echo fixture) — AGENTS.md escalation rule. Confirm.
5. **Stage 3 failure mode 2: under-count replaces over-count.** Today's rule over-counts badly
   (554/444). The new one can under-count when a genuinely new unit arrives inside an existing
   member's gate. Air defence is carved out (D6). Confirm that trade is the one you want.
6. **Stage 6 — is shortening `OBJECT_ID_MEMORY_S` from 600 s to 60 s the intended reading of D3?**
   D3 bounds object-id use to "what a human could have re-identified anyway — same place a second
   ago, small displacement", and 600 s of object-id trust is the oracle D3 forbids. But it is also
   the mechanism currently keeping the churn down, so shortening it depends on Stages 1 and 3
   working first.
