### Goal

Redesign `belief.groups`' cohesion test so size-relative spacing and installation kind-coherence
both decide whether contacts form one `Group`, release the infantry over-merge constraint the
2026-10-01 debug pass found a pinned test enforcing, and change group re-disclosure from
re-speaking the whole roster to speaking only what changed.

---

### Controlling documents, read in full before this plan

- `plans/group-undermerging/explore-notes.md` (2026-10-01, user's own words) — controlling over any
  earlier assumption below.
- `plans/group-undermerging/debug.md` — the re-trigger fix just merged, and the reverted
  uncertainty-budget cohesion experiment.
- `plans/group-reporting/explore-notes.md` (2026-09-28) and `plans/group-reporting/plan.md` — the
  model this plan modifies: `Group`/`GroupStore`, the disclosure ladder, the four cues (proximity,
  common fate, figure-ground/local-density, similarity), the "no spoken split/merge event" decision
  this plan revises (see Decision 8 below).
- `plans/group-detectability/plan.md` — the perception-layer sibling (`group_salience.py`,
  `GROUP_COHESION_GAP_UNIT_WIDTHS` = 10.0, angular currency). Different layer, different question,
  deliberately separate constants — do not conflate with this plan's belief-layer backstop.
- `body-layer/src/belief/groups.py` — current mechanism, read in full; its own docstring already
  records most of the history above and the exact reasoning this plan builds on.

---

### What's already built and reusable — size-relative spacing exists today

The explore notes ask "where does characteristic unit size come from" as if it were open. It is
not: `belief/groups.py`'s `_cluster_contacts` already runs **two** thresholds per pair and takes the
tighter —

1. a **relative** test: `GROUP_PROXIMITY_GAP_RATIO (3.0) × local median nearest-neighbour gap`
   (figure-ground, scene-density-scaled, no absolute constant), and
2. an **absolute backstop**, in **unit widths**: `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS (20.0) ×
   mean(pair's own believed physical size)`, where size comes from `perception.object_model.
   profile_for(contact.last_class_raw).size_m` (`_representative_size_m`), falling back to
   `GROUP_REPORTING_UNKNOWN_SIZE_M (7.0)` when the believed classification resolves to no real type.

This is a real answer to the trucks-vs-ships framing in the explore notes: a 1 km gap between 6 m
trucks fails the 140 m backstop and stays split; the same gap between larger objects whose believed
size is bigger passes. **No new size source and no new architecture is needed for this axis** —
it's built, it's perceptual (`last_class_raw` is Petrovich's own believed classification, never a
DCS object id), and it is already the module's own stated-assumption constant pending sortie
evidence. This plan's job on this axis is narrower than the explore notes assumed: not "build
size-relative spacing" but "make its one constant vary by class" (Decision/Stage 1 below) and "stop
asking it to do a job it structurally cannot do" (kind-coherence, Stage 2).

---

### 1. Kind-coherence — the central design question, answered without DCS group membership

**The honest source is perceptual, exactly as the dispatch suspected, and it already exists in this
codebase: ED's own `op_class` bucket** (`perception.object_model.ObjectTypeProfile.op_class` —
`OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM`/`OP_SPAAG`/`OP_ZU23`/`OP_ARMORED`/`OP_TRUCK`/`OP_INFANTRY`/...).
This is derived from Petrovich's own recognized-type classification (`contact.last_class_raw` run
through `profile_for`), the same no-omniscience boundary `_representative_size_m` already crosses
for the size axis — **never** a DCS `object_type` string and **never** group/country metadata. A
crew member who recognises "that's a radar" and "those are launcher-shaped vehicles" near it is
exactly this: pattern-matching recognized *kinds*, not reading a mission file. No new perceptual
mechanism is needed; a new **grouping policy** over the kind vocabulary that already exists is.

**Why a purely geometric rule (any multiple, however well scaled) cannot be made to work**, confirmed
against the debug pass's own real ground truth: the 2026-10-01 S-300 battery's components
(`tr`/`sr`/`54K6 cp`/`64H6E sr`) sit 236–838 m apart. Two of those four components (`40b6m tr`,
`64h6e sr`) do have real `object_model` entries (13.2–24 m, radar masts) and the other two match no
keyword and fall back to the 7 m default. Even fixing every missing keyword with realistic vehicle
sizes caps out in the tens of metres — no vehicle's physical size legitimately justifies an
800+ m unit-width backstop, because **the spread is a property of the installation's doctrine
(deliberately dispersed against a single hit), not of any one component's size.** This is exactly
the user's own point, confirmed by the data rather than assumed from his wording alone.

**Design: kind-coherence relaxes the backstop for a recognised installation family; it does not
replace the relative/density test, and it does not become a second unconditional merge rule.**

- New, hand-authored constant `AIR_DEFENSE_INSTALLATION_CLASSES: frozenset[str]` in `groups.py` —
  `{OP_SRSAM, OP_MRSAM, OP_LRSAM, OP_SPAAG, OP_ZU23}` to start. Same posture as every other
  hand-authored vocabulary in this codebase (`object_model._KEYWORD_PROFILES`,
  `_OP_CLASS_DISTINCTIVENESS`): a stated, revisable guess, not a validated doctrine table.
- A pair whose **both** members' `op_class` falls in that set gets a **flat-metre** backstop,
  `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M`, instead of the per-size unit-widths backstop.
  **Flat metres, not unit widths, deliberately** — unit widths is the right currency when spacing
  scales with the thing's own size (a convoy's vehicle-to-vehicle gap, a formation's hull-to-hull
  gap); it is the *wrong* currency here, because an installation's footprint has no relationship to
  its radar's mast height. Proposed **1000 m**, picked by looking at the one real dataset point
  (838 m, plus margin) exactly as the existing constants' own "pick something, refine with sortie
  evidence" posture — **not a measurement**, flagged below as a decision.
- Composition with the relative/density test: `min(relative_threshold, kind_backstop)` for a
  recognised-pair, same `min()` shape `_cluster_contacts` already uses for the general case — the
  relative test still governs everything (two SA-6 batteries states apart in a cluttered scene still
  need to be each other's nearest neighbours by density before the flat cap can even become the
  binding term), so this does not become an unconditional "any two SAM parts anywhere merge" rule.
- A **mixed** pair (one member in the installation set, one not — e.g. a radar and a nearby but
  unrelated truck) gets the **ordinary** size-relative backstop, not the relaxed one. Kind-coherence
  only loosens a pair where *both* sides are recognised as parts of one kind of installation.

---

### 2. Asymmetric error tolerance — a per-class cohesion policy, not a hard-coded list

**Settled form: a small per-`op_class` policy, defaulting to today's behaviour, with one named
exception.**

```python
class CohesionBackstop(Enum):
    STRICT = "strict"   # today's unit-widths backstop (default for every class)
    EAGER = "eager"      # no backstop at all -- relative/density test is the only gate
```

`_OP_CLASS_COHESION_BACKSTOP: dict[str, CohesionBackstop] = {"OP_INFANTRY": CohesionBackstop.EAGER}`,
default `STRICT` for everything not named — the identical default-plus-exception shape
`object_model._OP_CLASS_DISTINCTIVENESS` already uses, for the same reason: naming one exception is
honest about what's actually decided, and inventing a policy for every class would fabricate 140+
judgments with no evidence behind them.

This is a direct, narrow translation of the user's own words — *"ok to merge infantry too eagerly...
least detectable and also least important"* — not a general "classes close in importance get looser
rules" mechanism. **Scope held to `OP_INFANTRY` only** (Decision 2 below asks whether this should
extend further; recommend not, yet).

`EAGER` drops the absolute backstop entirely for a pair where **either** member resolves to
`OP_INFANTRY` (not requiring both — an infantry contact standing next to a technical/truck should
still be free to cohere eagerly with it, since the asymmetry is about infantry specifically being
cheap to over-merge, not about infantry-only pairs). The relative/density test alone decides —
no floor, same honest "this class costs little to get wrong" framing the user gave.

---

### 3. How the three things compose, per pair, concretely

For a pair `(i, j)`:

1. Compute `relative_threshold = GROUP_PROXIMITY_GAP_RATIO × local_median_nn_gap` (unchanged).
2. If **both** `op_class`es are in `AIR_DEFENSE_INSTALLATION_CLASSES`: `backstop =
   GROUP_REPORTING_INSTALLATION_COHESION_CAP_M` (flat).
3. Elif **either** member's `op_class` has an `EAGER` cohesion policy: `backstop = math.inf`
   (no absolute cap).
4. Else: `backstop = GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS × mean(pair's sizes)` (today's rule).
5. `pair_threshold = min(relative_threshold, backstop)`; cohere iff the pair's gap clears it.

Kind-coherence and the eager policy never both apply productively to the same pair in practice
(infantry is never in the installation set), so there's no precedence conflict to resolve between
them — only one of (2)/(3)/(4) ever fires per pair, and the `min()` against the relative test is the
one place all three paths meet.

---

### 4. The delta re-report

**Scope check against what already exists, so this doesn't rebuild a mechanism that's already
there:** `belief/events.py`'s `CONTACT_CLASSIFICATION_CHANGED` already fires and speaks **per
member, individually, regardless of group membership** (`belief/callouts.py`'s module docstring —
only `CONTACT_DETECTED`/`CONTACT_REACQUIRED` are filtered for a grouped contact). So a member's own
refinement is already told to the pilot once, outside the group's line. The actual redundancy the
explore notes are pointing at is narrower than "repeat the whole roster on any change": it's that
`render_group_disclosure`'s current trigger is a **whole-rendered-text diff**
(`belief/callouts.py` lines ~661/685, comparing fresh `content_signature` against
`Group.last_spoken_signature`), so *any* member's classification change — even a non-leading one
already announced individually — also changes the group's composition string and re-speaks the
**entire** group line a second time, in full.

**Redesign: replace the whole-text-diff trigger with a three-tier taxonomy, computed inside
`render_group_disclosure` itself (it already returns `OutgoingSpeech | None`; it gains more ways to
return `None`).**

`Group` gains three new fields, all carried over unchanged on a reconciliation that keeps a group's
id (same convention `last_spoken_signature`/`last_spoken_sim` already follow), reset to their
"never spoken" default only for a freshly founded group:

- `last_spoken_member_contact_ids: frozenset[str] | None` (`None` until first spoken)
- `last_spoken_leading_contact_id: str | None`
- `last_spoken_differentiated: bool` (was any member above `presence`/`unknown` level, last time
  this group spoke)

On each attempt to render:

| condition | what's said |
|---|---|
| never spoken (`last_spoken_member_contact_ids is None`) | **full** disclosure, as today |
| leading member changed (new leader, leader gained, or leader lost) | **full** disclosure — the threat framing reorders the whole line; a partial delta would misstate who leads |
| first time any member crosses from undifferentiated to differentiated (`not last_spoken_differentiated and` now true) | **full** disclosure, once — this is new information about the group's *shape*, not any one member's own event |
| membership changed (new members joined), same leader, already differentiated | **delta only**: compose just the *new* members via the existing `_group_composition_clause`, phrased as an addition (e.g. `"Also now: {composition}."`) |
| members only departed (no new arrivals), same leader | **silent** — matches the module's existing "no spoken split event" cost; the next real trigger computes against the current roster, not the stale one, because nothing updates `last_spoken_*` until something is actually spoken |
| nothing in the above (e.g. a non-leading member's own classification refined, already differentiated, same membership) | **silent** at group level — already told via that member's own `CONTACT_CLASSIFICATION_CHANGED` |

`GroupStore.mark_spoken` grows the two extra fields (member ids, leading id, differentiated flag) so
whichever branch actually speaks updates the full baseline, not just the text — `content_signature`
stays what `belief/console.py` reads for the group's own "what did I just say" display, now holding
either the full line or the delta line depending on which branch fired.

`belief/callouts.py`'s two existing `content_signature == belief_group.last_spoken_signature` checks
(scoring-time and speak-time) become redundant once `render_group_disclosure` itself returns `None`
for the silent branch — leave them in place as a cheap defensive fallback rather than deleting them;
the implementer may simplify if it reads better, but correctness doesn't depend on removing them.

---

### Affected Modules / Files

- `body-layer/src/belief/groups.py` — `CohesionBackstop` enum, `_OP_CLASS_COHESION_BACKSTOP`,
  `AIR_DEFENSE_INSTALLATION_CLASSES`, `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M`;
  `_cluster_contacts`'s per-pair backstop computation (§3); `Group` gains the three new
  `last_spoken_*` fields; `GroupStore.mark_spoken` signature change; `reconcile`'s carry-over of the
  new fields alongside the existing two.
- `body-layer/src/belief/speech.py` — `render_group_disclosure`'s trigger logic rewritten per the
  taxonomy in §4; a new small helper for composing a delta line over a member-id subset (reusing
  `_group_composition_clause`, not duplicating it).
- `body-layer/src/belief/callouts.py` — the two `mark_group_spoken`/`mark_spoken` call sites pass the
  new fields; no change to `group_priority`'s tuple shape.
- Tests: `test_groups.py` (new cohesion-policy and kind-coherence cases), `test_speech.py` (new
  taxonomy cases), `test_callouts.py` (integration: delta vs. full vs. silent across a tick
  sequence), **`test_callouts.py::test_2c_transcript_fixture_renders_four_lines_not_seven` rewritten**
  (see Decision 4 — this is an explicit AGENTS.md escalation: an existing pinned test's expected
  output changes, not just its implementation).
- `body-layer/ROADMAP.md` — milestone entry.
- `plans/group-reporting/plan.md` — **Decision 8 below amends, in place, its "no spoken split/merge
  event" framing** (see that section).

**Not touched:** `perception/group_salience.py`, `perception/clustering.py` (different layer,
confirmed still a different question — re-checked, not re-assumed, while reading this codebase for
this plan); `belief/cardinality.py`, `belief/classification.py` (read-only, as today); naval/ship
profiles (see Effort/Value below).

---

### Implementation Plan

**Stage 1 — per-class cohesion policy (the infantry release).** `CohesionBackstop` enum,
`_OP_CLASS_COHESION_BACKSTOP`, wire `EAGER` into `_cluster_contacts`. Mergeable alone; no kind-
coherence or delta work depends on it.
*Acceptance, no sortie needed:* rewrite `test_2c_transcript_fixture_renders_four_lines_not_seven`'s
expected line count for the now-eager infantry pair/triple; add a new pinned test proving a
non-infantry pair at the identical 260 m/500 m geometry still does **not** merge (so `STRICT`
classes are provably unaffected by this stage).

**Stage 2 — kind-coherence for air-defence installations.** `AIR_DEFENSE_INSTALLATION_CLASSES`,
`GROUP_REPORTING_INSTALLATION_COHESION_CAP_M`, the backstop-selection order in §3.
*Acceptance:* a synthetic fixture pinned to the real 236–838 m S-300 spacing (so CI doesn't depend on
replaying the full trace), **plus** one offline replay of the 2026-10-01 trace's S-300 segment
(`CONTACT_3/8/15/16`, `/Users/sg/dcs-detection-trace.jsonl` + `/Users/sg/dcs-belief-truth.jsonl`) —
the same method `debug.md` already used and proved works — confirmed to form one four-member group
at its true spacing, where the unmodified mechanism would not.

**Stage 3 — the delta taxonomy.** `Group`'s three new fields, `mark_spoken`'s signature,
`render_group_disclosure`'s rewritten trigger.
*Acceptance, no sortie needed:* one synthetic test per taxonomy row in §4 — new group, leader
change, first-differentiation, membership-delta, departure-silence, non-leading-refinement-silence.
Then one full replay of the 2026-10-01 trace end to end (reusing `debug.md`'s replay harness) as the
overall regression check: confirm no group re-speaks its full roster for a reason already covered
by an individual event, and that the delta line fires exactly where a new member joins mid-flight.

**Stage 4 — docs and ROADMAP.** Module docstring updates recording these decisions (matching this
module's existing documentation discipline), `plans/group-reporting/plan.md` Decision 8 amendment,
`body-layer/ROADMAP.md` entry.

---

### Risks & Unknowns

- **Both new constants (`EAGER`'s no-backstop, the 1000 m installation cap) are stated assumptions
  with at most one dataset point each** — same posture as `GROUP_PROXIMITY_GAP_RATIO`/
  `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` already carry; expect both to move after the next sortie
  exercises either path live.
- **Kind-coherence is not a full fix for over-splitting every installation** — it is still bounded by
  the relative/density test, which this plan does not change. Two genuinely distinct SAM batteries of
  the same class, close enough together in a dense scene that the local median gap is inflated by
  other nearby contacts, could in principle still bridge via single-link chaining. Same honest
  residual risk `groups.py`'s own docstring already names for the relative-only rule generally — this
  plan narrows it (a 1000 m finite cap, not an unlimited kind-only merge) but does not eliminate it.
- **The delta taxonomy's "silent" branches rely on `CONTACT_CLASSIFICATION_CHANGED` genuinely firing
  per grouped member**, as the module docstrings claim but this plan did not independently
  instrument-verify (unlike the debug pass's own "confirmed by print-instrumenting, not guessed"
  standard for the cohesion mechanism). Flagged as a thing Stage 3's implementation should verify
  directly before relying on it, not re-derive blind from a docstring.
- `AIR_DEFENSE_INSTALLATION_CLASSES` is exactly the kind of hand-authored, unvalidated vocabulary
  `object_model`'s own keyword table has needed repeated correction against real DCS data — expect
  it to need extension (early-warning radar, air-defence command posts, if those ever get their own
  `op_class`) once more real traces are flown.

---

### Effort/Value

**Naval formations are out of scope here, correctly.** The user raised ships only to illustrate the
size-relative principle in the abstract (*"relative to that the spacing is normal"*); the Mi-24P over
Syria is not a maritime mission profile today. No ship-specific cohesion path, test, or constant is
added — the general size-relative backstop already handles a ship pair correctly if one is ever
flown (its believed size, 100 m per `object_model`, scales the backstop the same way any class
does), so nothing is actually missing for that case; it's just untested and unclaimed, which is the
honest state to leave it in rather than building and validating a path with zero flown evidence.

---

### Second-Order Effect

This **unblocks `BL-B11`** (threat-based report prioritisation, deferred backlog): once a group's
cohesion correctly reflects installation structure, "which group's line should win a contested
callout slot" has a correctly-bounded group to prioritise, rather than one that might still be
artificially split. It **complicates** `plans/group-reporting/plan.md`'s deferred Stage 5 (common
fate): that stage will need to compose with *three* cohesion inputs (relative/density, size-relative
backstop, kind-coherence) instead of two, and should be designed against this plan's `min()`
composition shape rather than bolted on independently.

---

### Decisions Requiring User Input

1. **`EAGER` cohesion policy for `OP_INFANTRY`: no backstop at all, vs. a generous-but-finite
   multiplier.** Recommend no backstop — simplest, matches "least important" framing exactly, and the
   relative/density test alone still bounds it (infantry scattered across an empty desert does not
   merge just because it's infantry). Flag because "no floor at all" is a bigger release than a large
   finite number would be.
2. **Should any other class get `EAGER` now, or strictly `OP_INFANTRY` as the user stated?** Recommend
   strictly infantry — extending further is this plan inventing a judgment the user didn't make.
3. **`AIR_DEFENSE_INSTALLATION_CLASSES`'s membership and `GROUP_REPORTING_INSTALLATION_COHESION_
   CAP_M`'s value (proposed 1000 m).** Both are one-dataset-point guesses; confirm or adjust before
   or shortly after the first sortie that exercises this path.
4. **Rewriting `test_2c_transcript_fixture_renders_four_lines_not_seven`'s expected output** (Stage
   1) — named explicitly per AGENTS.md's "existing tests must be rewritten rather than extended"
   escalation rule, not silently changed.
5. **The delta taxonomy's two "always full" exceptions** (leader change; first differentiation) and
   its two "always silent" branches (departure-only; non-leading refinement) — confirm this is the
   right line between "the group's own voice should say this" and "an individual event already did."
6. **Decision 8 — amending `plans/group-reporting/plan.md`'s "no spoken split/merge event" framing.**
   That plan decided a membership change needs no dedicated spoken event because "a changed rendered
   line" already surfaces it — true at the time, when the rendered line was the *whole* roster. This
   plan's delta taxonomy changes what that changed line actually contains (a delta, not the roster),
   which is the refinement that decision was waiting for, not a reversal of it. Recorded here as the
   pointer; `plans/group-reporting/plan.md` itself should get a one-line "Decision REVISED, see
   `plans/group-cohesion-redesign/plan.md` §4" note at merge time, per this role's own standing
   instruction to amend open decisions a newly merged plan invalidates.
