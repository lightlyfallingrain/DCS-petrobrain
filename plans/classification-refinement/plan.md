# BL-2.6 — Classification refinement

Branch: `feature/classification-refinement` (from local `main`, `a7733f5`).

### Goal

Grade Petrovich's classification of a contact by how well he could actually have observed it —
`something` → coarse class → specific type — so that identity refines monotonically as an
observation improves (closure, or a scope look), and fire `CONTACT_CLASSIFICATION_CHANGED` when
it does.

---

### Milestone label — confirmed: **BL-2.6**

`todo/todo.md` asks the Architect to confirm the label. Keeping `BL-2.6`:

- It is scheduled in the **BL** sequence (between BL-2.5 and BL-3, user decision 2026-09-09), and
  per the naming precedent set at BL-2.5, a milestone takes the family of the roadmap it is
  actually scheduled into.
- Its mechanism is **contact-memory work**: it modifies `belief/contacts.py`, `belief/events.py`,
  `belief/decay.py`, and it *absorbs* an open BL-2 backlog item (last-writer-wins
  certainty/classification fusion). The BL-2 family fits.
- The decimal follows BL-2.5's precedent for an interim milestone inserted by user decision.
- It is **not** a new perception tier, which is what earned PB-1.5 a PB- label — no new channel,
  no new source, no new cognition capability. It regrades the output of an existing channel.
- Precedent for a BL-numbered milestone that lands code outside `belief/`: BL-2 Stage -1 (a pure
  aircraft-layer change tracked under a BL-numbered plan because BL-2 was the consumer). BL-2.6
  lands real work in `perception/visibility.py` and `perception/naked_eye_source.py` for the same
  reason.

One bookkeeping consequence to record when this lands: BL-2.6 **supersedes part of PB-1.5's
calibration** (its `medres`-gate defaults and its worked range table). `plans/body-layer/plan.md`
§6 must say so, or a future reader will treat PB-1.5's numbers as current.

---

### Design in brief

**1. The specificity lattice — a total order over four *levels*; a tree over *values*.**

```
level 0  unknown    no identity claim at all                     value: None
level 1  presence   "something is there"                         value: PRESENCE_CLASS (see below)
level 2  class      ED coarse class                              value: one of the 8 OP_* buckets
level 3  type       specific type / ED reporting name            value: "T-72", "SA-3 launcher", …
```

The **levels** are a total order (0 < 1 < 2 < 3) — that is what makes "better" well-defined.
The **values** form a shallow tree: a level-3 value's parent is its level-2 class, resolved by the
function `belief/association_over_time.py` already has (`_op_class_of`, which routes free text
through `object_model.profile_for`). Two claims are comparable only when the deeper one's parent
chain is consistent with the shallower one. Depth is uniform per branch — deliberately *not* a
per-branch variable depth, because we have exactly two producing vocabularies and neither offers a
fifth rung. `iff` (friend/foe) would be a level 4; it stays out of scope, as PB-1.5 already
documented.

**Vocabulary bridge.** `reporting_names.py` + `object_model.profile_for` is the existing bridge and
it suffices, with one honest limitation already accepted at BL-2: some scope free text
(`"Slava cruiser"`) does not resolve to a class at all. Rule: **an unresolvable parent yields
`unknown` comparability — it permits refinement but never asserts contradiction.** That is the same
three-valued posture `class_compatibility` already takes, reused rather than re-invented.

`PRESENCE_CLASS = object_model.DEFAULT_OP_CLASS` (`OP_GROUPSOMETHING`) — the investigator pass below
confirmed ED has no singular "something" fragment, so its only catch-all is the right value. It
composes correctly for free: `_op_class_of` already maps that string to `None` ("no class claim"),
which is exactly what level 1 means, so the existing association gate treats a presence-level
percept as class-`unknown` and neither blocks nor confirms a merge on it. No change needed there.

**2. What drives specificity: the same quantity that already gates detection.**

Angular radius, `size_m / range_m`, against ED's own `min_angular_radius` tiers
(`lowres 0.0043 / medres 0.008 / hires 0.02 / iff 0.025` rad — `HelperAI.lua`, recorded in
`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` Finding 3),
scaled by the existing `BINOCULAR_RANGE_MULTIPLIER = 4.0`.

Why the same quantity rather than an independent one: it is already computed in `visibility.py`,
it is already grounded in ED's constants rather than invented, and a second independent quantity
would create a second calibration surface that can disagree with the first — producing a contact
that is detected but incoherently classified. One curve, one place to tune.

**Decision 1 resolved by the user (2026-09-09): naked-eye reaches level 3 (type) at close range,
not just level 2.** This departs from the architect's recommendation (cap at class), which rested
on the investigator's Q2 finding that ED's own ambient-callout fragment bank has no per-model
vocabulary at all. The user's call is explicit: closure alone should be able to complete
`something → tank → T-72`, not only `something → tank`. Consequence: the `hires` tier promotes to
level 3 using `reporting_name_for(object_type)` for its value — ground truth, exactly as the scope
channel already does, so the existing "Petrovich can never mis-identify, only fail to identify"
caveat (Risks) applies here too, not only to the scope channel. This narrows what actually
differentiates the two channels (both can now reach type on their own), but the scope channel is
still the only path that reaches type *without* closing to `hires` range, which stays a genuine
distinction — the user's framing was about *what's reachable*, not about making channels identical.

So the three tiers map to **three levels plus a confidence gradient**, for a target of
characteristic size `S` at range `R` (`M` = 4.0):

| condition | level | emitted value | confidence |
|---|---|---|---|
| `R > S/lowres * M` (or > range cap) | — | not detected; no observation at all | — |
| `S/medres * M < R ≤ S/lowres * M` | 1 presence | `PRESENCE_CLASS` | low |
| `S/hires * M < R ≤ S/medres * M` | 2 class | `profile_for(t).op_class` (today's behaviour) | medium |
| `R ≤ S/hires * M` | 3 type | `reporting_name_for(object_type)` | **high** |

The `hires` tier is not just a confidence bump anymore — it is the naked-eye channel's own path to
level 3. Every tier stays load-bearing without inventing a rung ED does not have.

Worked, with the current constants (`NAKED_EYE_RANGE_CAP_M = 5000`):

| object | size | type ≤ | class ≤ | presence ≤ | capped at |
|---|---|---|---|---|---|
| infantry | 1.8 m | 360 m | 900 m | 1674 m | — |
| Ural truck | 6 m | 1200 m | 3000 m | 5581 m | **5000 m** |
| T-72 | 7 m | 1400 m | 3500 m | 6512 m | **5000 m** |
| SA-3 launcher | 9 m | 1800 m | 4500 m | 8372 m | **5000 m** |

This is the visible behaviour change and it is the point: today a T-72 reads `OP_ARMORED` at 3.5 km
exactly as at 200 m; after this it is `T-72` inside 1.4 km, `OP_ARMORED` between 1.4 and 3.5 km, and
merely "something" beyond — out to a detection range roughly 1.9x today's.

**Channel is the other axis.** The scope/HelperAI channel emits Petrovich's own indication text
verbatim, which is type-specific by construction (real committed samples: `Ural truck`,
`SA-3 launcher`, `SA-3 Low Blow radar`, `Slava cruiser`, `Tarantul III corvette`, `Civilian bus`).
Scope observations are therefore **level 3 by channel**, not by parsing the string — no range gate
at all, since the scope always carries type text regardless of how far the target is. The naked-eye
channel now also reaches level 3, but only at `hires` range; beyond that it holds at class or
presence. So the user's `something → tank → T-72` sequence can complete two ways: entirely on the
naked-eye channel by closing to `hires` range, or via `something`/`tank` from closure followed by
`T-72` from the scope at any range. Both are genuine refinements, not vocabulary swaps, because the
level ordering is what the fusion rule keys on, not which channel produced the claim.

**Dwell and aspect are deliberately out of v1.** Dwell has no ED grounding and would be a second
independent input; aspect and contrast/fog have no available inputs at all (a gap PB-1.5 already
records). `ObservedSpecificity` is shaped so a dwell term later becomes an *additional input to the
same tier decision*, not a redesign — the same decoupling pattern PB-1.5 used for its filter.

**3. Fusion rule replacing last-writer-wins.**

New `Contact.classification: ClassificationBelief` = `{value, level, confidence, established_sim}`.
`Contact.record()` folds instead of overwriting:

| incoming vs held | outcome | event |
|---|---|---|
| higher level, parent-consistent (or parent unresolvable) | **refine** — adopt | yes, `refined` |
| same level, same value | **reinforce** — refresh `established_sim`, raise confidence toward a ceiling | no |
| **lower** level | **hold** — held claim survives untouched | no |
| same-or-higher level, resolvable and *incompatible* | **contradict** — collapse to the deepest common ancestor, start a lockout | yes, `contradicted` |

The "hold" row is the oscillation fix, and it is why a coarser observation is never a
contradiction: less information is not disagreement.

**Invariant: specificity is monotone non-decreasing over a contact's life, except on
contradiction. Confidence is free to fall.**

**Does classification decay?** Deliberate decision: **confidence decays, level does not.**
`decay.py` already declares `IDENTITY_HALF_LIFE_S = 600.0` for exactly this and has never consumed
it; `plans/body-layer/plan.md` §5 already specifies `classification: {value, confidence, decay:
slow}`. Reasoning: a crew member who identified a T-72 two minutes ago does not revert to
"something" — he becomes *less sure*, which is what confidence is for. Reverting the level would
also silently reintroduce the oscillation this milestone exists to remove, on a slower clock.
A contact reaching `certainty == "lost"` keeps its classification: lost means "I don't know where
he is," not "I forget what he was" — which is what `decay.py`'s own `IDENTITY_HALF_LIFE_S` comment
already argues.

**`last_class_raw` is kept, with its exact current meaning** (the most recent percept's raw string)
and stays the **association gate's** input. The gate asks "is this new percept compatible with what
I last saw"; feeding it the *held best* claim would make it monotonically stricter and could start
rejecting genuine re-observations of a contact whose type was refined once. Everything user-facing
(`tools.py`, `console.py`, events) reads `Contact.classification` instead. This dual field is a real
readability cost and must be called out in both docstrings.

**4. `CONTACT_CLASSIFICATION_CHANGED` semantics.**

`docs/concept/PETROBRAIN_RUNTIME.md`'s event model names the event and nothing more, so the payload
is open. Fires on **refinement and contradiction**, not on reinforcement, hold, or confidence decay.

- `EventKind` gains `"CONTACT_CLASSIFICATION_CHANGED"`.
- `Event` gains three fields, all defaulting to `None` so every existing construction site and test
  is untouched: `previous_classification: str | None`, `classification: str | None`,
  `direction: Literal["refined", "contradicted"] | None`.
  (Rejected alternative: a separate event type or a union — `store.events` is a `list[Event]`
  consumed by `format_event_for_overlay`, `get_contact_history` and the overlay push loop, and a
  union ripples through all three for no gain.)
- **Minted in `ContactStore.tick`, not in `ingest`**, against a new
  `Contact.last_emitted_classification` — mirroring `last_emitted_certainty` exactly. This keeps a
  single event-minting site, keeps the pure comparison (`events.classification_event`) separate
  from the bookkeeping, and preserves replay determinism and tick idempotence. Latency is zero in
  practice: `ConsolePerceptionRunner` calls `ingest` then `tick` in the same poll.
- **Ordering within one tick, per contact: lifecycle event first, then classification event** — a
  `CONTACT_DETECTED` must precede that same contact's first refinement.
- **Console/overlay.** `format_event_for_overlay` renders the transition for this kind only:
  `"C7: CONTACT_CLASSIFICATION_CHANGED, OP_ARMORED -> T-72, <summary>"`. Other event kinds are left
  byte-for-byte alone — BL-2.5's overlay restyle was flown and rejected once already; this
  discharges BL-2.5's DoD "enrich mirrored lines" recommendation for the new event only, and does
  not reopen the styling question.
- `tools._contact_facts` moves `"classification"` from `{"value": last_class_raw}` to
  `{"value", "level", "confidence"}` — a change *toward* `plans/body-layer/plan.md` §3.4's specified
  shape, made before BL-5 freezes the tool surface. `find_contact` searches the held value.

**5. Hysteresis.**

Threshold-edge spam as range oscillates is **structurally impossible under the monotone rule**: once
a contact reaches level 3 at 1399 m it stays level 3, so 1401/1399 m flapping fires one event ever.
No range-hysteresis constant is needed and none should be added.

The one residual spam path is two channels that *persistently disagree* on the same contact
(possible only through the gate's `unknown` compatibility path): contradict → collapse → refine →
contradict, at the poll rate. Guard: **after a contradiction, no promotion above the collapsed level
is accepted for `CLASSIFICATION_CONTRADICTION_LOCKOUT_S` (default 30 s)** — one named constant, one
timestamp field, bounded event rate, trivially testable, and epistemically sensible ("I got
conflicting looks; I'm not calling it until I get a better one"). Treated as a *tuning* constant:
separable commit, per the staging rule below.

---

### Investigator findings (2026-09-09, Session 6 addendum to `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`)

Run before finalizing this plan, against the live install (`$DCS_INSTALL_PATH`, v2.9.29.27278),
read-only. Four questions, and what each did to the design:

- **Q1 — do ED's four `min_angular_radius` tiers actually mean existence / class / class / IFF?
  Clean negative: unverifiable.** The table is defined once in `HelperAI.lua` and referenced
  *nowhere* else in the Mi-24P Lua tree; a `strings` sweep for the tier keys across `Mi24.dll`,
  `CockpitMi24.dll` and four core engine DLLs found zero matches. **Consequence: the tier →
  specificity mapping in this plan is this project's own modeling choice, not ED's** — the same
  posture PB-1.5 took with `BINOCULAR_RANGE_MULTIPLIER`. It must be documented that way in
  `visibility.py`, so a future reader does not "correct" it toward an ED semantics that was never
  established. This stays a **risk, not a silent assumption**.
- **Q2 — is there a singular "something" fragment, and does ED's ambient vocabulary reach specific
  types? Reproduced-locally, and it changed the design.** Complete ground-class fragment list:
  `OP_ARMORED`, `OP_TRUCK(S)`, `OP_INFANTRY`, `OP_SRSAM`, `OP_MRSAM`, `OP_LRSAM`, `OP_SPAAG`,
  `OP_ZU23`, `OP_GROUPSOMETHING`, `OP_SHIP(S)`. No singular "something" fragment exists —
  `OP_GROUPSOMETHING` is the only catch-all, so `PRESENCE_CLASS = object_model.DEFAULT_OP_CLASS`.
  **There is no per-model vocabulary anywhere in the bank** — ED's ambient callout is
  architecturally capped at coarse class, which is why this plan caps the naked-eye channel there
  too.
- **Q3 — does the scope indication text coarsen with range?** No coarsening found. Structural
  evidence is reproduced-locally and clean: zero range-conditional logic in the HelperAI page/
  indicator Lua, and `reporting_names` is a flat static dictionary with no distance parameter.
  Log evidence is consistent but was never a designed same-target-at-two-ranges test, so the
  strongest honest claim is "the scope channel *carries* specific type names" — which is all this
  design depends on. This plan makes no stronger claim.
- **Q4 — does recognition accumulate with dwell time? Clean negative.** No dwell or progressive-
  identification mechanism is visible; every `HelperAI.lua` timer constant is referenced only at
  its own definition, and the one confirmed detection model is purely geometric and instantaneous.
  Supports deferring dwell out of v1 rather than treating its absence as an oversight.

Side finding, **out of scope, log as backlog**: ED's real class vocabulary includes `OP_LRSAM` and
plural forms (`OP_TRUCKS`/`OP_SHIPS`) that `perception/object_model.py`'s eight-bucket table does
not carry. Not this milestone's work; do not widen the table here.

---

### Affected Modules / Files

**New**

- `body-layer/src/belief/classification.py` — the lattice. `SpecificityLevel`,
  `ClassificationBelief`, `PRESENCE_CLASS`, `level_of_percept`, `parent_class_of`,
  `fold_classification`, plus `_op_class_of`/`class_compatibility` **re-homed from
  `association_over_time.py`** (see below).
- `body-layer/tests/test_classification.py` — lattice + fusion unit tests.
- `body-layer/tests/fixtures/scope_indication_samples.json` — the six real committed
  indication-text strings, with provenance (see "Offline execution" below). Not invented.

**Modified**

- `body-layer/src/belief/association_over_time.py` — `_op_class_of` and `class_compatibility` move
  to `classification.py`; this module imports them. This is a **pure move that removes the exact
  duplication BL-2.6 would otherwise create** (a second class-resolution function in the lattice
  module), which is the only justification for the new module. Spatial gating is untouched.
- `body-layer/src/belief/contacts.py` — `Contact.classification`,
  `Contact.last_emitted_classification`; `record()` folds instead of overwrites; `tick()` mints the
  new event after the lifecycle event.
- `body-layer/src/belief/events.py` — `EventKind` + three optional `Event` fields +
  `classification_event()` pure comparison.
- `body-layer/src/belief/decay.py` — `IDENTITY_HALF_LIFE_S` finally consumed by a
  `classification_confidence_at(contact, now_sim)` helper. Extends the existing table; does not
  start a second one.
- `body-layer/src/belief/tools.py` — `facts.classification` shape; `_contact_summary`;
  `find_contact`.
- `body-layer/src/belief/console.py` — `format_event_for_overlay` transition rendering for the new
  kind only.
- `body-layer/src/perception/visibility.py` — `VisibilityResult.tier` becomes a **computed** achieved
  tier instead of the constant `"medres"` it is today; the gating tier constant moves to `lowres`
  (Stage 6, separate commit).
- `body-layer/src/perception/naked_eye_source.py` — `_build_observation` emits the tier-appropriate
  `classification_raw`; type-level values come from `reporting_names.reporting_name_for`.
- `body-layer/src/perception/source.py` — `Observation` gains `classification_level: int` (the
  producing channel states its own level; belief does not re-derive it by parsing). Defaults to the
  class level so no existing construction site breaks.
- `body-layer/src/belief/percept.py` — carry `classification_level` through the projection. It is
  perceived metadata, not a truth field; the `Percept` boundary is unchanged in kind.
- `body-layer/src/perception/hybrid_source.py` — sets `classification_level` to type.
- Tests: `test_contacts.py`, `test_events.py`, `test_tools.py`, `test_console.py`,
  `test_cross_channel_fusion.py`, `test_decay.py` extended; `test_visibility.py` and
  `test_naked_eye_source.py` **partly rewritten** at Stage 6 (their tier-threshold assertions become
  wrong when the gate moves) — flagged under Escalation, expected, not a surprise.
- Docs at Stage 9: `body-layer/CLAUDE.md` Structure section, `plans/body-layer/plan.md` §6 (BL-2.6
  entry + the PB-1.5-calibration-superseded note), `todo/todo.md`.

---

### Implementation Plan

Each stage is independently testable and independently committable. **Mechanism and calibration
never share a commit** — the BL-2.5 lesson (a bundled cosmetic change made the revert lossy).

1. **Re-home class resolution.** Create `belief/classification.py`; move `_op_class_of` /
   `class_compatibility` into it; `association_over_time.py` imports them. Zero behaviour change;
   existing tests pass with an import-path edit only. Trivially reviewable in isolation.
2. **Lattice + fusion, mechanism only.** `SpecificityLevel`, `ClassificationBelief`,
   `parent_class_of`, `fold_classification`, the contradiction lockout constant.
   `Observation`/`Percept` carry `classification_level`; `hybrid_source` declares type level,
   `naked_eye_source` declares class level (unchanged output). `Contact.classification` folds.
   **Result at this stage: the `OP_ARMORED → T-72` refinement works and the oscillation is gone,
   with no change to what is detected or emitted.** No new event yet.
3. **The event.** `EventKind` entry, `Event` optional fields, `events.classification_event()`,
   `Contact.last_emitted_classification`, minting in `tick()` after the lifecycle event.
4. **Surfacing.** `tools.facts.classification` shape, `_contact_summary`, `find_contact`,
   `console.format_event_for_overlay` transition line. Console `show <id>` picks the new shape up
   for free.
5. **LIVE ACCEPTANCE #1 — recommended, cheap, de-risks #2.** User flies with
   `--console --overlay`. Expect: a naked-eye contact appears as `OP_ARMORED`; on scope acquisition
   it refines to the reporting name; exactly one `CONTACT_CLASSIFICATION_CHANGED`; no ping-pong on
   subsequent naked-eye ticks. Behaviour so far is purely **additive** — nothing detected today
   stops being detected. This checkpoint separates "did the mechanism work" from "do I like the new
   calibration."
6. **Range-graded specificity in the naked-eye channel — mechanism.** `visibility.py` computes the
   *achieved* tier instead of returning the constant `"medres"`; `naked_eye_source.py` maps it to
   `(level, value, confidence)` — `hires` now emits `reporting_name_for(object_type)` at level 3,
   per Decision 1. **Gating tier stays `medres` in this commit**, so the only new behaviour is that
   close targets (already inside `medres`) now sometimes resolve to a specific type instead of a
   confidence bump. Still no presence tier — that is unreachable until the gate moves, which is
   deliberately the next, separately revertible commit.
7. **Calibration — move the gating tier `medres` → `lowres` (its own commit).** One constant, its
   documented consequences, and the retuned threshold tests. This is the anti-omniscience change:
   Petrovich now notices things further out and says less about them. Revertible in one line.
   *Requires the user's decision — see Decisions below.*
8. **LIVE ACCEPTANCE #2 — required.** User flies and judges the full `something → class → type`
   ladder, the new contact volume at the wider gate, and the overlay chatter rate. Expect concrete
   tuning feedback on the three tier ranges, `NAKED_EYE_RANGE_CAP_M`, and
   `NAKED_EYE_MAX_NEW_PER_POLL`.
9. **Tuning pass — constants only, one commit per concern.** Reserved in advance so Stage 8's
   feedback can never ride along with mechanism.
10. **Docs and backlog.** `body-layer/CLAUDE.md`, `plans/body-layer/plan.md` §6, `todo/todo.md`;
    close the absorbed BL-2 last-writer-wins backlog item explicitly.

Stages 1–4, 6, 7 and 10 are fully executable **offline** (no DCS install, no Saved Games, no live
session). Stages 5, 8 and 9 require a live DCS sortie — see below.

---

### Offline execution — what is available in-repo, and what is not

The next session may run on a machine with no `$DCS_INSTALL_PATH` and no Saved Games tree.
Everything the implementation needs is already committed, or is committed as part of this plan.

**Available offline (committed, with provenance):**

| Needed fact | Where it lives |
|---|---|
| `min_angular_radius` four tiers, `extra_eyesight_ratio`, `scan_rad_around_point` | `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` Finding 3; already transcribed as named constants in `perception/visibility.py` |
| ED ambient-callout `OP_*` vocabulary (class, clock, range, count fragments) | same doc, Finding 2; class/range/clock tables already transcribed into `perception/naked_eye_source.py` |
| Complete ground-class enum list + confirmation that no singular "something" fragment and no per-model vocabulary exist | **Session 6 addendum, appended to `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` by this plan's investigator pass.** This is the file that fixes `PRESENCE_CLASS = OP_GROUPSOMETHING` and justifies the naked-eye class ceiling |
| Confirmation that ED's tier semantics are *not* verifiable, and that no dwell mechanism exists | same addendum (Q1, Q4) — both clean negatives, both already searched so the next session need not re-search |
| DCS type → ED reporting name (the level-3 value source) | `body-layer/src/perception/data/dcs_type_to_reporting_name.tsv`, 595 rows, committed, provenance in `perception/reporting_names.py` |
| Per-type characteristic size (the angular-radius numerator) | `perception/object_model.py` |
| Real scope/HelperAI indication text carrying specific type names | **six real strings, already committed**: `Ural truck`, `Slava cruiser`, `Tarantul III corvette`, `SA-3 launcher`, `SA-3 Low Blow radar` (`…2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` Finding 6 table, from 3,652 device-6 samples) and `Civilian bus` (`aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md` line 54). Stage 2 lifts exactly these into `body-layer/tests/fixtures/scope_indication_samples.json`, each row carrying its source research file, the observing session's date (2026-09-08 / 2026-09-09) and DCS version `2.9.29.27278` — **do not invent additional representative samples** |
| Real `object_type` strings, world-object snapshots, telemetry frames for tests | `body-layer/tests/fixtures/{object_type_coverage_sample.json, world_objects_sample.json, telemetry_frames.json}` |

Note for the implementer: `win-mac-sync/from-windows/` (where the raw HelperAI Lua was fetched) is
**gitignored and will not exist** on an offline machine. Cite the committed research docs, never
that path.

**Genuinely requires a live DCS — cannot be resolved offline:**

- Stage 5 and Stage 8 live acceptance (the only way to judge whether the regraded ladder feels
  right in the cockpit, and whether the wider gate floods the contact store).
- Stage 9's tuning values, which are a function of Stage 8's observations.
- Any confirmation that the scope channel's indication text does *not* coarsen at long range beyond
  what the six committed samples show — the samples establish that it *carries* specific type
  names, which is all the design depends on; a stronger claim would need a live probe and the plan
  does not make one.
- Confirming that `CONTACT_CLASSIFICATION_CHANGED` renders legibly on the in-cockpit overlay.

---

### Risks & Unknowns

- **Contact-volume increase at the `lowres` gate.** Detection range grows ~1.86x, i.e. ~3.5x area.
  `NAKED_EYE_MAX_NEW_PER_POLL = 3` throttles the acquisition rate but not the steady-state store
  size or the overlay chatter. Watch it at Stage 8; the gate constant reverts in one line.
- **`NAKED_EYE_RANGE_CAP_M = 5000` binds the presence tier for everything truck-sized and up**
  (truck 5581 m, T-72 6512 m, SA-3 8372 m all clip to 5000 m), flattening the size curve at that
  tier — the exact defect the 2026-09-09 probe fixed at `medres`. Raising the cap is a live-tuning
  decision, listed below.
- **Petrovich can never mis-identify, only fail to identify.** Level-3 values come from ground truth
  via `reporting_name_for`, so there is no confusion matrix and no wrong guesses. This milestone
  narrows the omniscience gap (identity now costs observation quality) without closing it. Naming
  it here so it is not mistaken for solved.
- **The `last_class_raw` / `classification` dual field** is a genuine readability hazard. Mitigated
  by docstrings on both; still the most likely thing a future reader gets wrong.
- **`facts.classification` shape change** alters the brain-facing API surface ahead of BL-5's
  freeze. Intended (it moves toward §3.4's spec), but any hand-written console expectations must be
  updated with it.
- **The tier→specificity mapping is unverifiable and therefore ours (investigator Q1).** ED's
  `min_angular_radius` table has no readable consumer in Lua or in any DLL's string table, so the
  "existence / class / class / IFF" reading is inference from naming, and always was. The mapping
  stands as a modeling choice this project owns and documents in `visibility.py` — the same posture
  PB-1.5 took with `BINOCULAR_RANGE_MULTIPLIER`. It stays a risk on this list; it does not get
  quietly promoted to a fact. A hashed or non-literal comparison in native code would be invisible
  to the `strings` sweep that produced the negative, so the question is closed only to the depth of
  "not resolvable from local sources," not proven.
- **The scope channel's always-specific behaviour is consistent-but-untested (investigator Q3).**
  No same-target-at-two-ranges observation exists. If it turns out the scope text *does* coarsen at
  long range, level-3 claims would silently arrive less often — degraded output, not a wrong one,
  because the fusion rule holds rather than downgrades. Acceptable failure mode; note it in the
  Stage 8 acceptance script as something to watch for.
- **Stage 7 rewrites rather than extends** `test_visibility.py` / `test_naked_eye_source.py` tier
  assertions. Per the escalation rules this is surfaced rather than done quietly; it is unavoidable,
  since the constants those tests assert are the thing being changed.
- **Contradiction is rare by construction** (the association gate already blocks incompatible
  merges, so it can arise only via the `unknown` path), which means the lockout path will be
  thinly exercised live. Cover it in unit tests rather than expecting the sortie to find it.

---

### Second-Order Effect

**Unblocks BL-4**: the event model gains a second real event kind and a twice-proven
`last_emitted_*` comparison pattern, so BL-4's event-queue/cooldown work inherits a shape rather
than inventing one. **Unblocks BL-5**: `classification: {value, confidence}` moves from spec to
code, and §3.4's `certainty` derivation table — which is written as a function of
`classification.confidence` — becomes implementable for the first time. **Narrows BL-3**: the
overlay-enrichment follow-up BL-3 inherited from BL-2.5 now has a worked precedent for rendering a
transition, and should follow it rather than restyling. **Complicates nothing structurally, but it
stales PB-1.5's published calibration table** — future perception work must read BL-2.6's constants,
which is why Stage 10's doc edit is not optional.

---

### Decisions — resolved by the user, 2026-09-09

All four answered before implementation start; the design sections above already reflect them.
Recorded here for the record.

1. **Naked-eye caps at class, or reaches type at close range? → Reaches type.** Departs from the
   architect's cap recommendation. `hires` now promotes to level 3 via
   `reporting_name_for(object_type)` — see the design section above and Stage 6. Consequence
   carried through: "Petrovich can never mis-identify, only fail to identify" (Risks) now applies
   to the naked-eye channel's `hires` tier too, not only to the scope channel.
2. **Move the naked-eye gating tier `medres` → `lowres` (Stage 7)? → Yes**, per the architect's
   recommendation. Petrovich's detection envelope widens ~1.86x (~3.5x area) so the presence tier
   becomes reachable; watch contact volume at Stage 8 per the Risks section.
3. **`NAKED_EYE_RANGE_CAP_M = 5000`? → Accept, defer.** Left as-is; revisit after Stage 8's live
   tuning data if the flattened size curve at the cap proves to matter in practice.
4. **Should classification level decay, not just confidence? → No, level stays sticky**, per the
   plan of record and the architect's recommendation. Confidence decay via `IDENTITY_HALF_LIFE_S`
   is the only decay mechanism for classification.
