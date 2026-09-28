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
