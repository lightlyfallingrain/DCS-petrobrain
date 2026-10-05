### Goal

Make **group** identity the thing that persists across losing sight — a remembered `Group` matched
against a freshly observed cluster on kind, composition, movement state and plausible displacement —
so contact-level churn stops reaching the pilot as new-group-every-poll, and resolve contact-level
ambiguity *within* a group toward the remembered contact instead of founding a duplicate.

Decisions honoured, not relitigated: **D3, D4, D5, D6, D7, D8, D9, D10** of
`plans/post-review-fixes/explore-notes.md` ("Decisions this conversation produced"). §2, §3, §5 are
this plan's; §4 (D10) is the seam with `BL-8`.

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
| 3 | air-defence confirmation (hard) | if either side's `air_defence_composition` is non-empty, require **equality** of both sides' `air_defence_composition` | **user direction**, D6. This is the one gate where ambiguity does *not* resolve toward the remembered group: positive confirmation is required, because `threat.envelope_for` keys the danger call on believed classification, so a wrongly-continued SAM **suppresses the warning** rather than mislabelling a contact. |
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

**Hard constraint if this stage is built**: `describe_position` is measured at **51.6 ms median on
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
  the pilot noticing a wrong "that column".
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
- **Knowledge-graph query returned "No graph yet. Build it with /graphify, then query."** from this
  worktree, so the graph step produced nothing. The prior work was found by reading
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
