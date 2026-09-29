### Goal

Give `belief/` a persisted **`Group`** — an associative belief that a set of already-individuated
`Contact`s (a convoy, an outpost) belongs together perceptually — with identity across split/merge,
and change what Petrovich says about a group's members from one line per member to one line per
group, escalating detail with range/threat and speaking only on refinement.

---

### Why this is not the group-contact-model / group-detectability work, restated so it isn't re-derived

Two mechanisms already exist that look like "grouping" and are not this:

- **`perception/group_salience.py`** (`plans/group-detectability/plan.md`) decides whether a distant
  *candidate* is even admitted into perception at all, using group membership only to relax the
  presence threshold. It runs before resolution and never produces a group the belief layer can see.
- **`plans/group-contact-model/plan.md`** (cardinality + the angular-separability clustering rework)
  makes one `Contact` represent one *resolution cluster* — objects the channel genuinely cannot
  resolve apart. Its deferred Stage 5 (`composition`) would add per-class counts *inside* one such
  cluster, and is deliberately built on **member claims with no stable identity**, because inside one
  unresolvable cluster there is no way to tell which infantryman is which.

**`plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md` shows the 2026-09-28 sortie's
noise is neither of these.** 52 contacts against 62 real objects is ~1:1 — the clustering/cardinality
machinery is working, correctly concluding that vehicles tens of metres apart at 2 km *are*
individually resolvable. So each one founds its own `Contact`, each with a real, stable id. The user's
own refutation of a gaze-wedge/sector model (*"a convoy... I could fly through the middle of it and
it would be on both sides of ownship, but be single group"*) confirms this is a **different axis**:
not "can the eye tell these apart" (resolution, already handled) but "do these already-resolved,
already-identified things belong together" (association). Because the members are real Contacts with
real ids, **the member-identity problem Stage 5 exists to avoid does not apply here** — this plan
groups things that already have stable identity, which is a strictly easier problem than Stage 5's.

---

### Existing mechanisms checked before designing new ones

- **`Contact.position`** (`belief/position_belief.py`, `plans/precise-position-belief/plan.md`) is a
  continuously fused (x, z) mean with its own covariance — not the old quantised bucket position.
  Group cohesion is computed on this, not on bearing/range buckets, which is what makes a group able
  to span 180° (the convoy-through-ownship case).
- **`Contact.motion`** (`belief/motion.py`) is a two-state `"moving"`/`"stopped"`/`None` flag only.
  **The velocity vector never leaves `perception/`** (`plans/movement-detection/plan.md` — deliberate
  module-boundary decision, not an oversight). So a true shared-heading "common fate" test is not
  available at the belief layer today; only the boolean state is. `belief/enrichment.py`'s
  `motion_when_seen` already derives a rough implied heading from **one contact's own** two most
  recent fused positions — legitimate there because it is one real object's history, unlike the
  cluster case its own docstring flags as fabrication-prone (mixing different vehicles' positions).
  That precedent is reusable per-contact here.
- **`belief/threat.py`** (`envelope_for`, `plans/watch-reporting/plan.md` Stage 4) already gives a
  believed engagement envelope per classification. This is enough to decide which member of a group
  "leads" the disclosure line by capability — `docs/concept/threat-levels.md` / `BL-B11` (deferred,
  backlog) is a broader *whole-scan* report-prioritisation scheme and is not needed for
  within-group member ordering.
- **`belief/events.py`**'s `EventKind`s and `EVENT_COOLDOWN_S`, and `belief/callouts.py`'s
  `CalloutScheduler`/`group_candidates`/`render_group_report` — read in full; see "What happens to
  `callouts.group_candidates`" below.
- **`ContactStore.tick`'s ordering** (lifecycle → classification → cardinality → motion → attention →
  range-crossing) is strictly per-contact. Group computation is cross-contact and does not fit inside
  that loop; it needs its own pass over the whole contact set, once per `tick()` call.
- **object_model has no air/ground domain field.** Nothing here currently distinguishes an airborne
  contact from a ground one structurally — see "Ground units only" below for what that means for
  scope, rather than inventing a filter that doesn't exist yet.

---

### Effort/value: does progressive disclosure alone (no new entity) already fix most of the noise?

**No, and the sortie's own numbers say why.** Run 0: 52 contacts, 131 reports — about 2.5 reports per
contact, not the extreme per-contact repetition that a "don't repeat myself" gate would mostly fix.
What actually produces "the same sentence up to seven times" is that **4310 of 5996 belief rows sit
at `PRESENCE`/`OP_GROUPSOMETHING`**, so many *different* contacts render to the literal same string
(`"ground, 5 o'clock, 2 kilometres."`) — the repetition is cross-contact, not within one contact's
history. A per-contact refinement gate cannot merge those, because from any one contact's point of
view nothing repeated; the pilot hears the fifty-second slightly-different instance of the same idea.
**The dominant driver of tonight's noise is contact *count*, not contact *chattiness* — which is
exactly what an associative Group model fixes and a disclosure-only fix cannot.**

That said, per-contact disclosure gating is real, cheap, and worth doing regardless — it is Stage 1
below, ships alone, and is the right long-term rule even once grouping exists (a group's own line
must obey it too). It is a complement, not an alternative.

---

### The model

**`Group`**: `group_id`, `member_contact_ids: frozenset[str]`, `established_sim`,
`last_reconciled_sim`, and a disclosure snapshot (`last_spoken_signature: str | None`,
`last_spoken_sim: float | None`) — the group-level analogue of `Contact.last_emitted_certainty`.
Persisted in a new `belief/groups.py`, `GroupStore`, structurally parallel to `ContactStore` but far
smaller: no observation log, no per-member position, no per-member identity — membership is a set of
*existing* `Contact` ids, which already have identity. This is the whole reason the model is cheap
compared to Stage 5.

**Membership is recomputed every `tick()` from the current `Contact` set, then reconciled against
persisted `Group`s by majority-member-overlap** — the same split/merge pattern
`plans/group-contact-model/plan.md` Stage 3 already argued through in full for clusters (no deletion,
ever; the majority child keeps the id; the minority child founds a new group through the same gate;
merging is zero new code because two partitions resolving to one group just widens its membership).
Reused as a *pattern*, not as code — that plan's design is for object-id clusters with no stable
member identity; this one is for Contacts that already have it, so there is no over-subscription
retraction to build, no ancestry matching, no `MemberClaim`.

**Cohesion test — relative, not a tuned radius.** Single-link union-find over `Contact.position`
(fused, so world-space and range/bearing-independent — a group can span 180°). Two contacts cohere
when their fused-position gap is within `GROUP_PROXIMITY_GAP_RATIO` (stated assumption, proposed
**3.0**, one dataset's worth of confidence exactly like `GROUP_MIN_MEMBERS`) times the **local median
nearest-neighbour gap** among all currently tracked contacts within some outer horizon. This is the
belief-layer answer to the user's figure–ground cue (*"a wide line of objects... stands out from
nothingness [in a desert]... in a cluttered area, a group is much more tightly together"*) — the
boundary scales with how densely populated the scene already is, with no absolute constant, the same
honesty `group_salience.py`'s unit-widths trick already established at the perception layer for a
different yardstick (angular size there; local density here, because belief-level contacts have real
world positions and perception-level candidates are compared by how big they look). `GROUP_MIN_MEMBERS`
mirrors `group_salience.py`'s constant of the same name and value (3) for the same reason: a pair is
a pair, not a formation, and there's no data suggesting otherwise yet.

**Similarity and common fate are not gates in this pass — see Decisions.** Adding either now would
be exactly the "regularity term fitted to n=1" mistake `group_salience.py`'s own docstring warns
against, with even less data behind it (zero flown examples of a convoy transiting a checkpoint).
Proximity + local density is what ships; the convoy/checkpoint discriminator is a named, deferred
follow-up gated on a sortie, matching the precedent `plans/group-contact-model/plan.md` set for its
own Stage 5.

**Ground units only, honestly scoped rather than filtered.** There is no air/ground domain field
today (checked above), so nothing here excludes an airborne contact structurally. In practice the
naked-eye/hybrid channels are exercised against ground targets, and this plan's tests and fixtures are
ground-only by construction — no aircraft-formation fixture is written, and no claim is made about
correctness there. A real domain filter, if one is ever wanted, is future work this plan does not
build.

---

### Affected Modules / Files

**New**

- `body-layer/src/belief/groups.py` — `Group`, `GroupStore` (`reconcile(contacts, now_sim)`,
  analogous shape to `ContactStore.tick`'s reconciliation, called once per `tick()`), the cohesion
  union-find (local-density-relative gap over `Contact.position`), and the majority-overlap
  split/merge re-homing.

**Changed**

- `belief/contacts.py` — `ContactStore.tick` gains a group-reconciliation pass. Cross-contact, so it
  runs once per `tick()` call, not inside the per-contact loop — placement relative to the existing
  six blocks needs to be after attention (a group needs each member's *current* attention/threat to
  render, same reasoning `tick`'s docstring already gives for why range-crossing sits last).
- `belief/speech.py` — new `render_group_report(group, member_facts, ...) -> str`, the disclosure
  ladder (see below). Reuses `_cardinality_phrase`/`_unit_type_display`/`_plural_unit_type_display`
  and `_format_range_km` untouched — no new word-choice path, same posture `callouts.py`'s existing
  `group_candidates` already committed to.
- `belief/threat.py` — no signature change; `envelope_for` is called per-member to pick the leading
  member (widest/nearest engagement envelope wins), read-only use.
- `belief/callouts.py` — `CalloutScheduler`'s candidate pool gains group-level candidates alongside
  contact-level `Event`s; see "What happens to `group_candidates`" below for the specific decision
  needed on `Event`'s shape.
- `belief/tools.py` — `facts` gains a `"group"` key (absent when the contact belongs to no group),
  same absent-not-null convention as `"cardinality"`/`"composition"` would have used.
- `belief/console.py` — `_SHOW_FACT_KEYS` gains `"group"`.
- `body-layer/ROADMAP.md` — milestone entry.
- Tests: `test_groups.py` (new), plus edits to `test_callouts.py`, `test_speech.py`,
  `test_contacts.py` (the new tick pass), `test_tools.py`.

**Not touched**

- `perception/group_salience.py`, `perception/clustering.py` — different layer, different question,
  argued above.
- `belief/cardinality.py`, `belief/classification.py` — unchanged; each member's own beliefs are read,
  never re-derived.
- `belief/composition.py` — still not built; still Stage 5 of the other plan, still deferred, still
  not needed here because members here have identity.

---

### What happens to `belief.callouts.group_candidates`

**Retire it, in the stage that lands the belief-level `Group`.** It groups *at speech time* by
matching a report's own rendered `(unit type word, range word)` pair plus adjacent clock, which the
log analysis shows degenerates for the `report` command into concatenated near-duplicate sentences
("ground, 5 o'clock, 3km. ground, 5 o'clock, 4km. ... And more.") — more noise than one line, not
less — and almost never fires for scheduled callouts because two members are rarely pending at the
same instant. A belief-level `Group` answers the actual question ("do these things belong together in
the world") once, persistently, instead of re-guessing it from word choice on every render. Once it
exists, `render_report`'s bundling should read `GroupStore` directly instead of re-deriving grouping
from rendered text. Keeping both mechanisms live would mean two independent, sometimes-disagreeing
answers to "is this a group" reaching the pilot — worse than either alone.

The one thing `group_candidates`'s docstring got right and this plan keeps: **`CONTACT_CLASSIFICATION_CHANGED`
is never grouped.** A member's individual identification jump (a Shilka revealed inside a group)
still fires and speaks on its own — see the disclosure ladder's step 3 below, which is exactly that
case given a name.

---

### The disclosure ladder — worked example

Three ground units, `PRESENCE`-level at 5 km, closing to 1 km, one later refined to a Shilka:

| range | what's held | what's said |
|---|---|---|
| 5 km | all `PRESENCE` | *"Group, eleven o'clock, five kilometres."* |
| 3 km | all refined to `CLASS`: two `OP_ARMORED`, one `OP_TRUCK` | *"Tanks and trucks, eleven o'clock, three kilometres."* |
| 1 km | one refined to `TYPE` = Shilka (threat-capable, `threat.envelope_for` non-empty); the rest still `CLASS` | *"Danger, Shilka. Also two tanks and a truck, eleven o'clock, one kilometre."* |
| 1 km, watched | same, but `attention == "watch"` and the count intervals happen to be exact | *"Danger, Shilka. Also two T-72s and a truck, eleven o'clock, one kilometre, watched."* |

Each row differs from the one above it — that difference **is** the trigger to speak; an identical
render at the next tick stays silent (`last_spoken_signature` unchanged). The per-member breakdown at
row 3–4 costs no new fusion logic: each member is already a real `Contact` with its own folded
`classification`/`cardinality`, so "how many members share this class" is a display-time `groupby`
over already-resolved beliefs, not new belief machinery — this is what makes the group case cheaper
than Stage 5's composition, which had to invent that fold for members with no identity. The mixed
exact/vague register (*"1 Shilka, 2 tanks, several trucks"*) and the threat-leads-the-line rule both
fall out for free: leading member picked by `threat.envelope_for`, each clause's own
precision-vs-specificity pairing enforced by `_cardinality_phrase` exactly as it already is for a
single contact.

**Progressive-disclosure trigger, concretely:** speak the group's line when (a) the group is new
(no prior `last_spoken_signature`), (b) the leading member's threat status changes (a member becomes
engagement-capable, or stops being so), (c) the rendered line's own text differs from
`last_spoken_signature` — which already captures a classification-specificity crossing (row 2), a
membership change from split/merge, or a range-band crossing coarse enough to change which ladder rung
applies. Do **not** speak on a bare cardinality wobble (a count moving from "several" to "a handful")
alone — same posture `plans/group-contact-model/plan.md`'s "settled: how a group is spoken" already
decided for individual contacts, extended here to groups.

---

### Implementation Plan

**Stage 1 — per-contact disclosure gating, no new entity (flyable alone, immediate partial relief).**
Add a rendered-signature check before a scheduled contact-report callout is spoken: compute the
signature `render_contact_report` would produce, compare to the contact's own last-spoken signature,
suppress if unchanged (a hold on a lockout-armed classification counts as "unchanged" for this
purpose). Small, mechanism-only, testable without the rest of this plan. Per the effort/value section
above: **ships real value, but is not expected to close most of tonight's noise on its own** — that
expectation should not be set with the user.

**Stage 2 — `Group`/`GroupStore`, membership only, no speech yet.** `groups.py`'s reconciliation
(union-find + majority-overlap re-homing), wired into `ContactStore.tick`. Testable entirely against
synthetic `Contact` fixtures (fused positions, no live DCS needed). No callout behaviour changes in
this stage — verify membership computation and split/merge identity in isolation before speech
depends on it, exactly the "stage something flyable, not five stages of invisible work" instruction.
Flyable in the sense of inspectable via `belief/console.py`'s new `"group"` fact, not yet audible.

**Stage 3 — the disclosure ladder and `render_group_report`.** `speech.py`'s new renderer, the
progressive-disclosure trigger, `tools.py`'s `"group"` fact. This is the first stage that changes what
the pilot hears.

**Stage 4 — `CalloutScheduler` integration and retiring `group_candidates`.** Group candidates enter
the same priority/`busy_until_sim` competition as individual contact events — needs the `Event`
shape decision below. Remove `group_candidates`/the old `render_group_report`'s callers, point
`render_report`'s bundling at `GroupStore`.

**Stage 5 (deferred, gated on a sortie — same posture as the other plan's Stage 5) — common fate.**
Add motion-state compatibility (and, if warranted by what's actually observed, the per-contact implied
heading `motion_when_seen` already knows how to derive) as a second cohesion gate, so a moving convoy
does not silently absorb a stopped checkpoint it passes through. **Do not build this on reasoning
alone** — proximity + local density may already separate most real cases (a checkpoint is usually not
literally coincident with the convoy's fused positions at the same instant), and there is zero flown
evidence yet that it doesn't. Fly Stages 1–4, look at what actually happens at a checkpoint, then
decide.

---

### Risks & Unknowns

- **`GROUP_PROXIMITY_GAP_RATIO` and `GROUP_MIN_MEMBERS` are both stated assumptions**, the first with
  zero data behind it (unlike `group_salience.py`'s cohesion constant, which had one flown dataset).
  Both are one-line changes; flag explicitly to the user that the first sortie under this model is
  the first real evidence either way.
- **Majority-overlap re-homing inherits the same "arbitrary survivor" caveat** `plans/
  group-contact-model/plan.md` documented for clusters: after a split, the surviving group's
  `established_sim`/history describes the *group's* history, not any particular member's. Same
  honest cost, same decision (accept it, document it on the fields).
- **The `Event`/`CalloutScheduler` integration in Stage 4 needs a real design decision** (does `Event`
  grow a `group_id` field alongside `contact_id`, mutually exclusive, or does a group produce its own
  parallel event stream?) — sketched above but not fully specified; do this as its own short design
  pass at Stage 4, not assumed now, because getting it wrong risks a group callout starving or
  preempting an urgent individual danger call.
- **No true common-fate signal exists at the belief layer** (motion is a boolean, not a heading) —
  Stage 5 is weaker than the user's own convoy/checkpoint mental model until/unless a real heading
  channel is built, which is out of scope here.
- **O(n²) cohesion pass per tick**, same cost shape `clustering.py`/`group_salience.py` already pay at
  the perception layer — fine at today's contact counts, worth watching if a sortie produces
  materially more simultaneous contacts.
- **Retiring `group_candidates` (Stage 4) removes the `report` command's only existing bundling** —
  if Stage 4 slips relative to Stage 3, there's a window where scheduled callouts group but the
  player-requested `report` command does not; acceptable as an interim state but worth naming so it
  isn't mistaken for a regression.

---

### Second-Order Effect

This **narrows `BL-B11`** (threat-based report prioritisation): once group membership exists, "which
member leads a group's line" is answered here with `threat.envelope_for` alone, so BL-B11's remaining
scope shrinks to ordering *between* groups/lone contacts competing for the same callout slot, not
within one. It also **unblocks** a future domain-aware extension (aircraft formations) cheaply, since
`GroupStore`'s reconciliation is domain-agnostic by construction even though untested for it.

---

### Decisions Requiring User Input

- **`GROUP_PROXIMITY_GAP_RATIO` (proposed 3.0) and `GROUP_MIN_MEMBERS` (proposed 3, matching
  `group_salience.py`)** — no data behind either; fine to ship as stated assumptions and correct after
  the next sortie.
- **Whether group split/merge gets its own spoken event now** (*"the convoy has split"*) or is
  deferred, matching `plans/group-contact-model/plan.md`'s "no `CONTACT_SPLIT` event kind, inferred"
  precedent. Recommend deferring — Stage 4's ladder already surfaces a membership change as a
  changed rendered line; a dedicated event is a wording nicety, not core noise reduction.
- **Whether to fly Stages 1–4 before deciding on Stage 5 (common fate)**, exactly as the sibling plan
  did for its own Stage 5. Recommend yes — no convoy/checkpoint evidence exists yet, and it may not be
  needed.
- **The `Event` shape question for Stage 4** (`group_id` field vs. a parallel stream) — flagged above
  as needing its own short pass at that stage rather than being decided now.

---

### Stage 4 design — wiring the disclosure into `CalloutScheduler` (2026-09-28)

Stages 1-3 are merged (`feature/group-reporting`, `84a0577`) and fully inert: `render_group_
disclosure` is built and tested but nothing calls it from a live poll loop. This closes the `Event`
shape question left open above and specifies exactly what changes in `callouts.py`/`groups.py`.

#### 0. The headline question, answered: neither named option — no `Event` at all

The plan's two candidates were "`Event` grows a `group_id` field" or "a parallel event stream."
Both assume a group's speak-trigger is a discrete transition an `Event` could snapshot, the way
`lifecycle_event_kind`/`classification_event`/etc. each compare one attribute's before/after. A
group's trigger is not that shape: Stage 3 already built it as "does a *fresh render* differ from
`Group.last_spoken_signature`" (the plan's own "progressive-disclosure trigger, concretely" section)
— a whole-line text diff, not a single field's before/after. Minting an `Event` for it would mean
either (a) deriving the same text diff a second time inside `events.py` just to decide whether to
mint the event, which duplicates the comparison Stage 3 already owns on `Group` itself, or (b)
minting an `Event` on every reconciliation regardless of whether the render actually changed, then
letting the scheduler re-derive the diff anyway — either way the `Event` is a redundant middle layer
around a comparison that already has a perfectly good home: `Group.last_spoken_signature` itself,
exactly the mechanism Stage 1 already proved out for individual contacts (`_last_spoken_signature`
in `CalloutScheduler`, promoted here to live on the belief object instead of the scheduler).

**So: `CalloutScheduler.tick` reads `store.groups` directly, once per tick, alongside
`store.unacknowledged_events` — two candidate sources feeding one shared priority sort, no new
`Event` kind, no parallel stream.** This is the simplest option and it is obviously right once the
trigger's actual shape is named; the rest of this design is the acknowledgement and priority rules
the dispatch asked for.

A consequence worth stating plainly: **groups need no expiry and no `_consumed` bookkeeping.**
`store.unacknowledged_events` is a real queue an entry can go stale in (`CALLOUT_MAX_AGE_S`); `store.
groups` is not a queue at all — it is read fresh every tick, and a group that loses this tick's
priority contest is simply re-evaluated next tick against the same `last_spoken_signature`, with no
staleness concept and nothing to mark "lost." This is a genuine simplification over the event path,
not a gap.

#### 1. Grouped detections are spoken for by the group, never individually

**Rule:** in `tick`'s event-collection loop, a `CONTACT_DETECTED`/`CONTACT_REACQUIRED` event whose
contact currently belongs to a group (`store.group_for_contact(event.contact_id) is not None`) is
skipped before it ever reaches the candidate pool — not consumed, not acknowledged, just excluded
from this tick's contest (the same "skip without consuming" treatment `_WATCHED_ONLY_KINDS` already
gets for a not-yet-watched contact, a few lines above it in the same loop).

**Why this has to happen before scoring, not after:** if a grouped contact's own detection stayed in
the candidate pool, it would compete against its own group's disclosure candidate for the same
tick's one speaking slot. Whichever won, the pilot would eventually hear both — the individual line
this tick, the group's line (or vice versa) a later tick — which is the exact "fifty near-identical
lines" failure this whole feature exists to remove, just shrunk to two. Filtering before scoring
makes that pairing structurally impossible: a grouped contact's detection is never a candidate on
its own, full stop.

**Why this doesn't strand new members silently:** a new member joining an existing group changes
that group's own composition (`_group_composition_clause`'s per-class counts), which changes the
rendered line, which the signature check already treats as a live trigger — rule (c) of the
plan's own "progressive-disclosure trigger" above ("a membership change from split/merge"). So a new
member's detection is never silently lost; it surfaces as *the group's own line changing*, which is
exactly the sentence the plan's worked-example table already wants said.

**What is deliberately untouched by group membership:** `CONTACT_CLASSIFICATION_CHANGED` and every
`_WATCHED_ONLY_KINDS` kind (`CONTACT_MOTION_CHANGED`/`CONTACT_RANGE_CROSSED`/`CONTACT_ENGAGEMENT_
CHANGED`) compete and speak exactly as they do today, grouped contact or not — this is the plan's
own already-settled decision ("`CONTACT_CLASSIFICATION_CHANGED` is never grouped... still fires and
speaks on its own"), restated here because the filter above must not be written broad enough to
catch it by accident. Concretely: only `event.kind in (CONTACT_DETECTED, CONTACT_REACQUIRED)` is
gated on group membership; nothing else in `_TEMPLATED_KINDS` is.

#### 2. Acknowledgement: filter early, reconcile at speak-time

Filtering a grouped detection out of the candidate pool (step 1) leaves it sitting in `store.
unacknowledged_events` indefinitely if nothing else ever touches it — a real cost, but not a new
kind of one: it is the same "lost, not deferred" posture `CALLOUT_MAX_AGE_S` expiry and Stage 1's
duplicate-suppression already accept elsewhere in this module, where a suppressed candidate stays
visible to a future brain's `poll_events` rather than vanishing. Left alone, though, it would sit
unacknowledged *forever* even after the group's line does eventually speak about it, which the old
multi-event `_render_group` branch never did — it always acknowledged every member event once its
group line actually spoke.

**Rule: when a group's disclosure line is actually chosen and spoken this tick** (not merely
scored — see step 3), sweep `store.unacknowledged_events` for `CONTACT_DETECTED`/`CONTACT_
REACQUIRED` events whose `contact_id` is in that group's current `member_contact_ids`, and
`acknowledge_event` each one. This exactly mirrors the multi-event branch of today's `_render_group`
(which already does this for `render_group_report`'s event list) — nothing new, just retargeted
at group membership instead of at report-space bucketing.

Net effect: a grouped contact's detection sits unacknowledged for however many ticks pass before its
group wins a priority slot (bounded only by the group's own composition changing again and
re-triggering sooner), then is acknowledged the moment the group is actually heard. No event is ever
double-spoken and none is silently dropped from the persisted log without ever being accounted for.

#### 3. Priority: one shared tuple shape, group candidates included

`callout_priority`'s tuple, `(threat_band, -attention_rank, range_m, -event.t_sim)`, needs a
group-level twin so both candidate kinds sort in one list. Add:

```python
def group_priority(
    member_facts: Sequence[dict[str, object]], now_sim: float
) -> tuple[int, int, float, float]:
    """`callout_priority`'s group-level analogue. `-attention_rank` uses the
    *highest* rank among members -- any one watched/prioritised member
    elevates the whole group's line, matching `render_group_disclosure`'s
    own trailing ", watched" clause, which fires on the same "any member"
    test. `range_m` is the nearest member's, the same convention `render_
    group_disclosure`/`render_group_report` both already use. `-now_sim`
    stands in for `-event.t_sim`: a group candidate has no event and no
    age -- it is read fresh from `Group.last_spoken_signature` every tick
    (see design doc, "groups need no expiry") -- so "now" is the only
    honest recency value, and every group candidate this tick ties on it,
    which is fine: ties only matter for stable ordering, not for staleness."""
```

Both `range_m` and `attention_rank` need the group's member facts, which `render_group_disclosure`
already gathers internally but does not return. Rather than gather them twice (once here for
priority, once inside `render_group_disclosure` for the text), **extract the gathering loop
(`describe_contact` per member + the `len(member_facts) < 2` guard) out of `render_group_disclosure`
into a small shared helper**, e.g. `belief.speech._group_member_facts(store, group, now_sim,
enrichment) -> list[dict[str, object]] | None`, returning `None` under the same "fewer than two
members still resolve" condition `render_group_disclosure` already checks. `render_group_disclosure`
calls it first and keeps its existing behaviour; `callouts.py` calls it once at scoring time to
build the priority tuple, and once more at speak-time via `render_group_disclosure` itself (see
step 4 on why the second call is deliberate, not an oversight). This is a real, small duplication
removed, not a new abstraction invented for its own sake.

`threat_band` stays `_DEFAULT_THREAT_BAND` — same disposable placeholder every other candidate uses;
a group's "danger, leads with the threat member" framing is already expressed in the rendered text
via `envelope_for`, not in this tuple, and widening the tuple's meaning here would be a second,
disagreeing threat model living next to the one `callout_priority` already doesn't have.

#### 4. `tick`'s shape, end to end

1. Build `live_events` exactly as today, plus the new group-membership filter from step 1.
2. Build `live_groups`: for every `belief_group in store.groups`, call `_group_member_facts` (and,
   if non-`None`, the rendered text via the existing composition/threat logic already in `render_
   group_disclosure` — in practice this means calling `render_group_disclosure` itself, since it is
   already the one function that turns member facts into the final string); skip a group whose
   fresh text equals its own `last_spoken_signature` (silent — nothing changed) or whose member
   facts come back `None` (fewer than two members currently resolve; self-corrects on the next
   `GroupStore.reconcile`, needs no bookkeeping here).
3. Score every event candidate via `callout_priority`, every group candidate via `group_priority`,
   into one `scored` list, sorted ascending exactly as today.
4. Walk `scored` in order. For an event candidate, behaviour is unchanged from today (render fresh,
   speak, or consume-and-continue on `None`). For a group candidate, **re-render fresh at the
   instant of speaking** (`render_group_disclosure` again, not the scoring-time text) — this is the
   same "nothing exists ahead of being spoken" invariant the module docstring already states for
   every other candidate, restated here so a group's line is never spoken from belief that is one
   tick stale relative to the moment it is actually chosen. If the fresh render still differs from
   `last_spoken_signature` (it should, almost always — nothing plausible changes belief between
   scoring and speaking within one `tick()` call, but the check costs nothing and matches the
   event path's own re-render-before-speaking discipline), call `store.mark_group_spoken(group.id,
   text, now_sim)`, run step 2's acknowledgement sweep, update `busy_until_sim`, and return.
   Otherwise (rare/defensive), fall through to the next candidate exactly as a vanished event
   candidate does today.

#### 5. `group_candidates` (the function) is retired, and so is half of `_render_group`

With grouped detections filtered out before scoring (step 1) and the residual singleton events
never re-bucketed at speech time, nothing ever calls `group_candidates` from `CalloutScheduler.tick`
again — **delete it**. Its multi-Event bucketing existed to catch reports that would sound alike at
speech time; the belief-level `Group` now answers that question once, upstream, exactly as the
plan's own "What happens to `group_candidates`" section already decided. `group_facts`/
`_chain_by_clock`/`render_group_report` are **not** deleted — they are still the residual path for
report-space bucketing below `GROUP_MIN_MEMBERS` (see Decision 2 below) and, per §6, for `_handle_
report`'s own remaining ungrouped case.

`_render_group`'s multi-member branch (the `len(group) > 1` case, which called `describe_contact` +
`render_group_report` + acknowledged every member) becomes dead code once nothing constructs a
multi-`Event` list anymore — delete that branch too, and simplify the function to take one `Event`
rather than `list[Event]`. **Rename it while doing so** — `_render_group`'s parameter is today named
`group` for a *list of Events*, which now sits in the same module as `belief.groups.Group`; keeping
the name risks exactly the kind of collision the Stage 3 implementer already flagged once for
`render_group_report`/`render_group_disclosure`. Suggested name: `_render_event`.

**What replaces `group_candidates`'s behaviour for contacts not in any group:** nothing does, by
design — see Decision 2 below for why that residual is small and acceptable rather than something
to build a replacement for.

#### 6. The `report` command (`_handle_report`) — same question, smaller scope, still worth deciding now

`crew_console.CrewConsole._handle_report` is a second, independent caller of the same report-space
machinery (`group_facts`/`render_group_report`), reached only on-demand (the pilot says or selects
"report"), not through `CalloutScheduler`. The plan's own Stage 4 description ("point `render_
report`'s bundling at `GroupStore`") names this as in scope. **Recommend switching it too**: for
each candidate contact already in the report's scope (direction/sector filtering is `_handle_
report`'s own, untouched), resolve `store.group_for_contact`; render each distinct `Group` found
that way via `render_group_disclosure` once (a report is pull-based, so it always speaks fresh —
skip the `last_spoken_signature` gate entirely here, it exists only to throttle the push path);
route every contact with no group through the existing `group_facts`/`render_group_report` residual
bucketing exactly as today. See Decision 3 below — this is one extra call site, not a new
mechanism, but it is scope beyond the dispatch's headline "CalloutScheduler" framing, so it is
listed separately for confirmation rather than assumed.

#### Tests this design needs, beyond what Stages 1-3 already pin

- A fresh 3-member cluster's first tick speaks one group line, not three detections; all three
  members' `CONTACT_DETECTED` events end up acknowledged afterward.
- A grouped contact's `CONTACT_CLASSIFICATION_CHANGED` still fires and speaks on its own tick even
  while grouped (pins §1's "deliberately untouched" carve-out).
- A grouped, watched contact's `CONTACT_MOTION_CHANGED`/`CONTACT_RANGE_CROSSED`/`CONTACT_ENGAGEMENT_
  CHANGED` still speaks independently of the group's own line (same carve-out, the watched-only
  kinds).
- Priority competition both directions: an urgent watched individual event beats a pending group
  candidate; a watched group beats a normal-attention individual event.
- Progressive disclosure: after a group's line is spoken once, an unchanged tick stays silent; a
  membership or composition change re-triggers it.
- Two groups changed in the same tick: exactly one speaks; the other is still a live candidate next
  tick (not lost, no expiry).
- A below-floor pair (2 contacts, `GROUP_MIN_MEMBERS` not met) still speaks as two individual
  singleton lines with no cross-suppression — pins Decision 2's accepted residual.
- Regression: ungrouped-contact singular output is byte-identical to today's (Stage 1's own
  suppression path, untouched by any of the above).

#### Decisions Requiring User Input

- **Group priority's attention rule** (§3: highest attention rank among members elevates the whole
  group). Worked example: a 3-truck group, one truck under `watch <id>` — the group's line now
  outranks a normal-attention lone contact's detection competing for the same tick, exactly as it
  would if that one truck were reported alone. Recommend as stated; flag in case "the group as a
  whole" reading is preferred to "any one watched member speaks for the group."
- **Accepting the below-`GROUP_MIN_MEMBERS` residual** (§5/§2 of tests): a 2-contact pair close
  together no longer gets any cross-contact dedup at all once `group_candidates` is deleted — each
  speaks its own singleton line, back to back if both are live the same tick. Worked example: two
  BMPs 80 m apart -- "BMP-2, 5 o'clock, 3 kilometres." twice, not merged. Recommended: accept it.
  `group_candidates` already barely fired on the push-callout path (its own docstring says so), and
  lowering `GROUP_MIN_MEMBERS` to close this gap is `groups.py`'s own calibration constant, not a
  mechanism change — it waits for a sortie's evidence like `GROUP_PROXIMITY_GAP_RATIO` already does.
- **Whether `_handle_report` (§6) also switches to real-`Group`/`render_group_disclosure`, or keeps
  the old report-space bucketing everywhere for now.** Recommend yes, switch it — otherwise the
  pilot hears two different descriptions of the same group depending on whether he asked or waited:
  a pushed callout says *"Group, eleven o'clock, four kilometres."*; without this, saying "report" a
  moment later would answer *"Three trucks, eleven o'clock, four kilometres."* (the old cardinality-
  hedged report-space phrasing) for the identical group. This is one extra call site reusing the
  same renderer, not a second mechanism, but it is beyond the dispatch's named scope, so it is
  listed here rather than assumed.
- **The acknowledgement lag (§2)**: a grouped contact's own `CONTACT_DETECTED` sits unacknowledged
  for as many ticks as its group takes to win a priority slot, with no explicit upper bound (unlike
  `CALLOUT_MAX_AGE_S`'s bound for a lone event). Flagging since it is a new instance of an already-
  accepted cost class (see §2's own reasoning), not because it looks wrong — confirm the "no explicit
  bound" is acceptable rather than wanting a group-level max-age analogue added now.
