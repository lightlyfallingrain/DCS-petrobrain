### Goal

A contact the pilot has told Petrovich to watch reports itself — on movement change, on crossing a
whole-kilometre mark inside 5 km, and on entering or leaving its believed weapon envelope — and
"follow" becomes both a synonym for "watch" and a new way to *name* which contact to watch
(`follow 1 o'clock [3 km]`).

---

### What was measured before designing, not assumed

Load-bearing for every decision below. Each was read on `feature/binocular-optic` merged into this
worktree, not inferred.

- **`callouts._TEMPLATED_KINDS` is the speech allowlist, and it is
  `{CONTACT_DETECTED, CONTACT_REACQUIRED, CONTACT_CLASSIFICATION_CHANGED}`.** Every other kind is
  filtered out of `CalloutScheduler.tick` before anything else happens. So:
  - **Reacquisition already speaks, for every contact, watched or not.** The user's second bullet is
    *already built*. This milestone must not touch it.
  - **`CONTACT_MOTION_CHANGED` fires and is never spoken.** `movement-detection` built the event and
    stopped at the event. This is the single cheapest thing in the milestone.
  - `CONTACT_CARDINALITY_CHANGED` is deliberately silent (`speech._render_lifecycle_text`'s own
    docstring: *"the event is real, logged, and visible to `poll_events`; it simply never renders to
    speech"*). That is the precedent for gating at the speech layer rather than at emission.
- **Attention today changes ordering, not eligibility.** `callout_priority` is
  `(threat_band, -attention_rank, range_m, -event.t_sim)` and `_DEFAULT_THREAT_BAND` is a hard-coded
  `0` for every contact. A watched contact is said *first*; nothing is said *only* because it is
  watched. This milestone introduces the first watched-only speech.
- **`ContactStore.tick(now_sim)` takes no ownship and no enrichment**, and `enrichment.py` imports
  `contacts.py` — so passing `EnrichmentContext` into `tick` would be an import cycle. It is not
  needed: range-to-ownship is pure geometry, and `contacts.py` already imports `GeoPosition` from
  `perception.geometry`. `logger.run_once` constructs exactly that `GeoPosition` two lines above its
  `self.store.tick(ownship.t_sim)` call, for `reproject_relative_areas`.
- **`tick` has a five-block shape** (lifecycle → classification → cardinality → motion → attention),
  every block identical: compute current → compare against `last_emitted_*` → `if kind is not None
  and self._cooldown_elapsed(...)` → append `Event` + stamp `last_event_emitted_sim[kind]` → update
  `last_emitted_*` **outside** the guard. New kinds follow this shape exactly and inherit
  `EVENT_COOLDOWN_S = 15.0` per contact per kind for free.
- **Decay constants checked before designing temporal state** (this is where a range trigger goes
  wrong): `POSITION_HALF_LIFE_S` 30, `LOST_THRESHOLD_S` 120, `OBSERVED_WINDOW_S` 16,
  `MOTION_HALF_LIFE_S` 60, `MOTION_STOP_CONFIRM_S` 5, `IDENTITY_HALF_LIFE_S` 600,
  `EVENT_COOLDOWN_S` 15, `CALLOUT_MAX_AGE_S` 10. The stop side of motion is **already debounced** by
  `MOTION_STOP_CONFIRM_S`; do not add a second debounce.
- **Watch is a standing mode with three representations**: `Contact.attention` (the direct mark),
  a `PendingIntent` of kind `"watch_contact"` with `contact_id` set and `deadline_sim=math.inf`
  (what makes it cancellable), and the *derived* `effective_attention(contact.attention,
  contact.last_position, store.areas) in ("watch", "priority")`. There is **no watched-id set**
  anywhere. All watched-ness tests in this plan use the derived form, because an `AttentionArea` can
  make a contact watched with an unmarked direct attention.
- **`_bearing_verb_token` in `command_matcher.py` says in its own docstring that "no `watch`-verb
  bearing slot exists"** — i.e. the slot mechanism is keyed by verb and extending it to a new verb is
  the documented path, not an invention.
- **`VERB_ANCHOR_WORDS` is derived from `PHRASES` at import time**, so adding `"follow …"` phrasings
  makes `follow` an anchor word automatically. No matcher change for the synonym half.
- **`crew_console._AIR_DEFENCE_OP_CLASSES` is `{OP_SPAAG, OP_ZU23, OP_SRSAM, OP_MRSAM}` — `OP_LRSAM`
  is absent.** So "watch nearest air defence" will not select an S-300. Possibly deliberate,
  possibly a defect; **flagged, not fixed here** (see Risks).

---

### Affected Modules / Files

**body-layer**

- `body-layer/src/belief/events.py` — two new `EventKind`s (`CONTACT_RANGE_CROSSED`,
  `CONTACT_ENGAGEMENT_CHANGED`), their `Final` constants, two new `Event` snapshot field pairs, and
  two pure comparison functions in the established `*_event_kind` shape.
- `body-layer/src/belief/contacts.py` — `tick` gains `ownship_position: GeoPosition | None = None`
  and `los_clear: Callable[[GeoPosition, GeoPosition], bool] | None = None` (4f); two new blocks in
  the five-block loop; new `Contact` fields (`last_announced_range_km`, `last_emitted_engagement`,
  and the watched-seed bookkeeping below).
- `body-layer/src/belief/threat.py` — **new module.** The ingested table (range band, altitude band,
  radar range, acquire time), the per-`op_class` worst-case rollup, and the believed-classification
  lookup. The only new module in the plan. Two of its four fields have no consumer yet, deliberately
  (4f).
- `body-layer/src/belief/callouts.py` — `_WATCHED_ONLY_KINDS`; the watched test in `tick`'s filter;
  a per-contact `_last_spoken_sim` gap for the watched-only family.
- `body-layer/src/belief/speech.py` — `_contact_report_text` gains two optional affixes
  (`lead`, `event_clause`); `_render_lifecycle_text` gains the two new kinds; `render_no_contact`.
  **No second rendering path.**
- `body-layer/src/belief/crew_console.py` — `_handle_follow`; `_FOLLOW_CLOCK_TOKENS`; dispatch
  entries; `range_km` threaded through `handle_command`/`handle_transcript`/`_act_on_voice_decision`;
  `DISPATCHED_COMMAND_TOKENS` updated; `_describe_token_for_confirm` says the range.
- `body-layer/src/belief/voice_commands.py` — `PendingConfirmation` gains `range_km`.
- `body-layer/src/logger.py` — pass the already-built `GeoPosition` into `store.tick`, plus the
  `los_clear` closure over the existing `world_model_conn`/`theatre`; read `range_km` off the
  transcript event; `!voice` harness gains the optional range argument.
- Tests: `test_events.py`, `test_contacts.py`, `test_threat.py` (new), `test_callouts.py`,
  `test_speech.py`, `test_crew_console.py`, `test_logger.py`.

**audio-adapter**

- `audio-adapter/src/vocabulary.py` — `follow` phrasings on `watch_nearest`/
  `watch_nearest_air_defence`/`cancel_watch`; nine new `follow_clock_<p>` tokens; `parse_range_km`.
- `audio-adapter/src/command_matcher.py` — `_RANGE_TOKEN_VERBS` sibling of `_BEARING_TOKEN_VERBS`;
  `MatchResult.range_km`.
- `audio-adapter/src/transcript_queue.py`, `server.py` — a ninth `TranscriptEvent` field, exactly as
  Stage 3 of `plans/voice-command-completeness/plan.md` added the eighth.
- Tests: `test_vocabulary.py`, `test_command_matcher.py`, `test_transcript_queue.py`, `test_server.py`.

**Prose**

- `docs/concept/STATE_TRANSITIONS.md` — the "Watching" block's *"engagement envelope … is a concept
  nothing in the codebase has"* note becomes a pointer to `belief/threat.py`.
- `body-layer/ROADMAP.md`, root `ROADMAP.md`, `todo/todo.md`.

**Unchanged, deliberately**

- `callouts._DEFAULT_THREAT_BAND` and `callout_priority`. Filling the threat band is a **separate,
  deferred roadmap item marked "Do not start without the user's instruction."** This milestone builds
  the envelope data that item names as its main missing input, and stops there.
- `perception/*`. No perception module is edited. `perception` must not import `belief`, and nothing
  here inverts that; `belief/threat.py` reads `perception.object_model`, which is the legal direction.

---

### Decision 1 — what actually changes for a watched contact, and what does not

The user said "watched contact(s)". Three of the four triggers already have machinery and two of
them **already speak for every contact**. Being precise here is the difference between the
implementer duplicating existing behaviour and silently changing it for everything.

| trigger | today, unwatched | today, watched | after this plan |
|---|---|---|---|
| reacquired | **spoken** | spoken | **unchanged, both** |
| classification changed | **spoken** | spoken | **unchanged, both** |
| detected | **spoken** | spoken | **unchanged, both** |
| lost / cardinality | silent | silent | **unchanged, both** |
| started/stopped moving | event only, silent | event only, silent | unwatched **unchanged (silent)**; watched **speaks** |
| crossed a km mark ≤5 km | nothing | nothing | unwatched **nothing**; watched **speaks** |
| entered/left weapon envelope | nothing | nothing | unwatched **nothing**; watched **speaks** |

So the milestone adds exactly three watched-only report kinds and touches nothing else.

**Two different gate placements, and the asymmetry is deliberate:**

- **Motion is gated at the speech layer.** The event already exists and fires universally; a watched
  contact is a *speech* decision about an event the log should keep either way. `callouts.tick`'s
  filter gains: a kind in `_WATCHED_ONLY_KINDS` is skipped unless
  `effective_attention(contact.attention, contact.last_position, store.areas)[0] in ("watch",
  "priority")`. This mirrors `CONTACT_CARDINALITY_CHANGED`'s existing "real event, never spoken"
  precedent, and it means attention changing *after* the event still does the right thing.
- **Range-crossing and engagement are gated at emission.** Both need per-contact bookkeeping
  (`last_announced_range_km`, `last_emitted_engagement`) that is only meaningful for a watched
  contact, and emitting them for every contact in the theatre would flood `store.events` with
  thousands of entries nobody will ever read. They are watched-only by construction.

**The seeding conventions are opposite, and both matter:**

- **Range crossing seeds silently.** On the first tick a contact is watched, set
  `last_announced_range_km` to the current floor'd kilometre and emit nothing. Otherwise
  `follow 2 o'clock` would immediately blurt "armor, two o'clock, three kilometres" one second after
  the readback already said exactly that. Clear the field back to `None` when the contact stops being
  watched, so a re-watched contact re-seeds rather than comparing against a stale mark.
- **Engagement seeds as "outside".** The first evaluation that finds the contact inside its envelope
  *does* fire. This is the whole point of Decision 4's late-warning behaviour: recognising a SAM you
  are already inside the envelope of is exactly when you need to be told.

---

### Decision 2 — `follow` is two separate changes, and only one of them is a synonym

**(a) The synonym is free.** `follow nearest` / `follow nearest air defence` become extra phrasings
on the existing `watch_nearest` / `watch_nearest_air_defence` tokens; `stop following` / `cancel
follow` join `cancel_watch`. `VERB_ANCHOR_WORDS` picks up `follow` automatically. **Zero body-layer
change.** This is a `vocabulary.py` edit and nothing else.

**(b) `follow <clock> [<n> km]` is a new referring expression** — the first command in this project
that selects a contact by *where it is* rather than by "whichever is nearest". This is the
`o'clock-and-distance location form` that `body-layer/ROADMAP.md` records as *rejected for the F10
menu and owned by voice* (user, 2026-09-16). It combines the two mechanisms that already exist,
rather than inventing a third:

- **The clock is enumerated**, exactly like `report_clock_*` and `scan_clock_*`: nine
  `follow_clock_<p>` tokens over `FORWARD_CLOCK_POSITIONS`, one phrasing each
  (`"follow one o'clock"`), plus a `_FOLLOW_CLOCK_TOKENS: dict[str, int]` in `crew_console.py`
  alongside the two identical dicts already there.
- **The range is a slot**, threaded exactly as `bearing_degrees` was in Stage 3 of
  `plans/voice-command-completeness/plan.md`: `vocabulary.parse_range_km` → `MatchResult.range_km` →
  `TranscriptEvent.range_km` (a ninth field) → `logger._poll_transcripts` →
  `handle_transcript(range_km=…)` → `handle_command(range_km=…)` → `PendingConfirmation.range_km`.
  **Missing the `PendingConfirmation` field is the specific way this breaks**: a `follow` command
  that lands in the confirm band would lose its range on "affirm" and act on a bare clock.

Enumerating the product instead — 9 clocks × range values — would be ~60 tokens for one command.
The clock is closed and the range is not; that is precisely the closed-grammar / slot split
`vocabulary.py`'s own "Slots, not enumerated phrases" section already draws.

**The range checksum is weaker than the bearing one, and that must be said.** `parse_bearing`'s 5°
constraint rejects roughly four in five mishearings. Whole kilometres 1–20 have no such redundancy:
"three" misheard as "two" is a legal value and is undetectable. Consequence: constrain to integer
kilometres 1–20, and rely on the readback (which names the range) to expose a mishearing. Do **not**
copy the "resolution is a checksum" comment across — it would be false here.

**Resolution.** `_handle_follow(now_sim, *, clock: int, range_km: int | None)` reads the same source
`_handle_report` does — `tools.get_contacts(store, now_sim, enrichment=self.enrichment)`, drop
`facts["certainty"] == "lost"`, drop contacts with no `relative_now`, and answer the existing
"no world-model connection configured" line when `self.enrichment is None`. Then:

- filter `relative_now["clock_position"] == clock` — **exact hour match, reusing `_handle_report`'s
  rule verbatim**. `_clock_position` already quantises 30° buckets; layering a second tolerance on a
  quantisation produces overlap the speaker did not ask for. (`_handle_report`'s own note.)
- if `range_km is not None`, additionally require
  `abs(relative_now["range_m"] / 1000.0 - range_km) <= FOLLOW_RANGE_TOLERANCE_KM` (proposed `0.75`,
  uncalibrated, isolated constant).
- **no matches** → `speech.render_no_contact(label)` → `"Nothing at two o'clock."` The rear-hemisphere
  "can't see there" carve-out from the report family does **not** apply: `FORWARD_CLOCK_POSITIONS` is
  8–4, all inside the Mi-24P mask's `rear_cutoff_deg` by construction.
- **exactly one** → `watch_contact_task(...)`, readback via the existing
  `render_watch_nearest_readback`.
- **several** → **watch all of them** (see the open decision below).

---

### Decision 3 — the report wording, and the one rendering path

The user's format is `<unit> <where> <what>` with the example `"armor, 2 o'clock, 3 km"`.
`speech._contact_report_text` already produces exactly
`"<unit type>, <clock> o'clock, <range>[ <semantic>][, moving]."` — so the example is *already* what
it renders. No new renderer. Instead give it two optional affixes:

```python
def _contact_report_text(facts, *, lead: str | None = None,
                         event_clause: str | None = None) -> str
```

`lead` prefixes (for `"Danger, "`); `event_clause` is inserted before the terminating period. When
`event_clause` is supplied, the existing automatic `", moving"` clause is **suppressed** — otherwise
a motion callout reads *"armor, two o'clock, three kilometres, moving, moving."*

| kind | rendered |
|---|---|
| `CONTACT_RANGE_CROSSED` | no affixes at all — `"Armor, two o'clock, three kilometres."` The range *is* the news, and it is already in the body. This is the user's example verbatim. |
| `CONTACT_MOTION_CHANGED` | `event_clause="moving"` / `"stopped"` |
| `CONTACT_ENGAGEMENT_CHANGED`, entering | `lead="Danger"` → `"Danger, SAM, one o'clock, four kilometres."` |
| `CONTACT_ENGAGEMENT_CHANGED`, leaving | `lead="Safe from"` → `"Safe from SAM, four o'clock, eleven kilometres."` |

The two engagement wordings are `STATE_TRANSITIONS.md`'s own `"danger <unit> <where>"` /
`"safe from <unit> <where>"` — taken from the spec rather than invented.

**What stops it becoming noise.** Four mechanisms already exist and three of them suffice:

1. `EVENT_COOLDOWN_S = 15.0`, per contact **per kind**, applied by `tick`'s guard — inherited free by
   both new kinds.
2. `CalloutScheduler.busy_until_sim` — at most one line in flight; `tick` returns at most one line
   per call regardless of how many candidates scored.
3. `CALLOUT_MAX_AGE_S = 10.0` — a candidate that loses the priority sort **expires and is dropped**
   rather than queuing. `plans/callout-scheduling/` fixed the stale-backlog defect precisely this
   way, and a burst of simultaneous triggers therefore already degrades to "say the most important
   one, forget the rest" rather than to a queue.
4. `note_reply` — a spoken answer to `report`/a readback *extends* `busy_until_sim` rather than
   resetting it, so a watched-contact callout waits behind an answer to the pilot. Correct ordering:
   an answer beats an unsolicited update.

**The one gap they leave** is a single watched contact alternating kinds: six eligible kinds each on
their own 15 s cooldown is, worst case, one line every ~2.5 s about one object. So add the fifth
mechanism, and it belongs in the scheduler because it is about *talking too much about one thing*,
not about *logging a transition twice*:

```python
_last_spoken_sim: dict[str, float]          # contact_id -> sim time, on CalloutScheduler
WATCH_REPORT_MIN_GAP_S: Final[float] = 8.0  # uncalibrated
```

applied **only to `_WATCHED_ONLY_KINDS`**, so no existing callout timing changes. It is a third
"seconds of suppression" constant living near two others and the distinction must be written into its
docstring, because this codebase has already been bitten by conflating two of them
(`events.py`'s note on `EVENT_COOLDOWN_S` vs `CLASSIFICATION_CONTRADICTION_LOCKOUT_S`):

- `CLASSIFICATION_CONTRADICTION_LOCKOUT_S` suppresses a **belief promotion**;
- `EVENT_COOLDOWN_S` suppresses **one kind's emission** for one contact;
- `WATCH_REPORT_MIN_GAP_S` suppresses **all watched-only speech** about one contact, across kinds.

**The cost, stated plainly:** a suppressed callout is *lost*, not deferred. `tick` adds an expired
candidate to `_consumed` and leaves it **unacknowledged**, and `contact.last_emitted_motion` is
updated outside the cooldown guard — so a "stopped" that loses the sort is never spoken and the next
comparison is against "stopped". Petrovich will occasionally miss a state change under load. That is
the deliberate trade the callout-scheduling milestone already made for every other kind, and this
plan extends it rather than re-litigating it.

---

### Decision 4 — engagement envelopes: ingest the Hoggit table, key the lookup on belief

**Source:** `https://wiki.hoggitworld.com/view/Threat_Database`. Per-type engagement range band (NMI),
altitude band (feet), radar range (NMI) and acquire time (seconds), by threat category. **Every range
column is a min/max band written as one cell** (`0 - 6500`) — see 4f, which is where two successive
misreadings of that fact were caught.

#### 4a — provenance

This is a **community wiki**, not DCS ground truth and not ED documentation. It is the same evidence
class as the pydcs-derived projections in `world-model` and takes the same treatment recorded in this
project's provenance memory: **provisional until confirmed**, never silently promoted to fact.

- Every row carries `source="hoggit-threat-database"`, `confidence="provisional"`, and the
  **retrieval date**, in the module docstring of `belief/threat.py` — it is a dated snapshot of a
  page that can change under us, and saying so is the whole point.
- **A missing or `TBC` value degrades to "no warning", never to a default.** There is no fallback
  envelope, no `DEFAULT_ENGAGEMENT_RANGE_M`. A contact whose class resolves to no row simply never
  produces a danger call. Inventing a number here would be worse than silence: it would be an
  authoritative-sounding warning derived from nothing, and it would be invisible, because the output
  would merely look like slightly odd prioritisation.
- **Conversion happens once, at transcription.** The table is committed in **metres** (ranges *and*
  altitudes) and **seconds**, with the source's NMI/feet figures in a trailing comment per row. This
  project works in metres throughout; a runtime conversion is a unit bug waiting for the one caller
  that forgets it — and with two different source units on one row, that caller will exist.

#### 4b — why hand-transcription, rather than a scraper or the DCS install

*(How the rows physically reach the repo, which is a gate on Stage 4, is 4g.)*

**Recommended: hand-transcribe.** There is no JSON/Lua/CSV export — only HTML tables. The set that
matters is small (the air-defence categories, ~40 rows; ground armour and trucks have no relevant
envelope against a helicopter beyond gun range). A scraper for a page with no stable schema, run
once, is more code than the data it produces and rots the moment the wiki's markup changes.

**What the alternative would buy.** An investigator pass against the DCS install's own unit
definitions would be strictly higher provenance — DCS ground truth rather than a community
transcription. It is **not recommended now**, for a reason already established in this repo rather
than guessed: `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md` records that
*stock unit definitions live in the encrypted `Scripts/Database.edce`* and a grep for `BMP-2` across
all of `CoreMods` returns nothing. The live route (`Unit.getDesc()` through the mission-scripting
bridge, which **does** ship — `2026-09-22-mission-bridge-already-shipping.md`) returns attributes and
a bounding box, not weapon envelopes. So the DCS-native route is a milestone of its own with an
uncertain payoff, and — decisively — **it would not change this design**, because 4c forces the
lookup to be keyed on *believed* class regardless of how good the underlying numbers are. The table
is not a stopgap for the DCS route; it is the correct shape either way.

*No investigator pass was run for this plan, and that is deliberate:* the one DCS-internals claim it
could resolve (whether envelopes are extractable) cannot change the recommendation.

#### 4c — the class-level question: worst case within the class, **derived, not hand-written**

Contacts classify to `op_class` far more often than to a type. Agreed with the coordinator's
reading: when he knows only *"that is a SAM"*, use the **longest max range among that class's
members**. It is how a crewman actually thinks, it is conservative in the safe direction, and the
warning **tightens as recognition improves** — which falls out of the data rather than needing a
rule.

One refinement, and it is the part that stops this drifting: **do not hand-write a per-class number.**
Compute the rollup at import time by joining the transcribed per-type rows through
`perception.object_model`'s *existing* keyword table:

```
for each (keyword, envelope) in _ENGAGEMENT_ROWS:
    op_class = object_model.profile_for(keyword).op_class
    class_max[op_class] = max(class_max[op_class], envelope.range_max_m)
```

Same "computed once at import from a static table" precedent as `VERB_ANCHOR_WORDS`. Class membership
then has exactly one definition — the keyword table that already decides it — and adding a new SAM to
`object_model.py` updates the class worst case automatically. A new type with no threat row
contributes nothing and the class degrades gracefully.

**A finding that falls out of doing this, worth recording rather than fixing:** our `OP_SRSAM` bucket
holds SA-3 (~18 km), SA-8 (~14 km), SA-9, SA-13 (~5 km) and SA-15. The worst case for "short-range
SAM" is therefore ~18 km — nearly 4× the SA-13 a pilot most often means. The class-level warning will
be very early and often badly wrong in magnitude, tightening only at type level. That is not a bug in
this design; it is our `op_class` buckets grouping things with a 4× range spread, and it should be
recorded against the buckets, not patched here with a hand-tuned class number.

**Where the lookup lives, and the invariant it guards.** New module `belief/threat.py`, and its public
function takes a **`ClassificationBelief`** (value + level), never an `Observation` or a raw DCS type
string:

```python
def envelope_for(classification: ClassificationBelief) -> EngagementEnvelope | None
```

- `level == UNKNOWN` or `PRESENCE` → `None`. **A dot has no envelope.** There is nothing to look one
  up for, and this is the no-omniscience boundary in one line.
- `level == CLASS` → the derived class worst case.
- `level == TYPE` → the per-type row, by the same specific-before-general substring match
  `object_model` uses.

The signature *is* the guard: `belief/threat.py` cannot be handed ground truth because it does not
accept the type that carries it. **Add a test asserting the module imports nothing from
`perception.source`.** The roadmap's own warning is that computing this from ground truth would be
*"an omniscience backdoor wearing a prioritisation label — and an invisible one."*

#### 4d — the no-omniscience consequence: the warning arrives with recognition, not before

**This is the honest statement of what the pilot will experience, and it is not a detail.**

Because the envelope is keyed on believed classification, Petrovich cannot warn about a contact he
has not yet classified. `perception/visibility.py`'s recalibrated tiers put class recognition for a
7 m vehicle at ~2 km and presence at up to ~9.3 km. An SA-8's envelope is ~14 km. **So by the time he
can say "that's a SAM", you have been inside its envelope for twelve kilometres.**

**That is a feature, and it is the single most valuable thing this trigger produces** — not despite
being late, but because being late is *true*. A real operator cannot warn you about a launcher he
has not recognised, and flying into an unidentified SAM is the actual danger. A system that warned
earlier would be warning from data Petrovich does not have.

Two consequences the implementer must not get wrong:

1. **"Entering the envelope" is not only an outside→inside geometric crossing.** It is far more often
   a *recognition* event while already deep inside. Hence Decision 1's "seed as outside" convention:
   the first evaluation that resolves a class and finds itself inside fires. One wording covers both —
   the pilot needs the same fact and can take the same action either way, and a second wording for a
   distinction he cannot act on is noise.
2. **Reliability tracks recognisability, not threat.** An S-300 radar is `distinctiveness=2.6` and
   recognisable a long way out, so its danger call will be genuinely early. A Strela-10 in a treeline
   will be recognised at knife-fight range or not at all, and its call will be useless. Say this in
   the sortie card, because a pilot who gets one good warning and one absent one will otherwise read
   the absent one as a bug.

#### 4e — the 1.5 factor is hysteresis, and that is why it exists

`STATE_TRANSITIONS.md` specifies *"until well outside its engagement envelope (1.5 factor for now)"*.
Enter at `1.0 ×` max range, leave at `1.5 ×`. This is a Schmitt trigger: without the gap, a contact
sitting near the boundary flaps between "danger" and "safe from" every few seconds and burns the
`EVENT_COOLDOWN_S` budget doing it. Implement it as hysteresis and say so, so nobody later
"simplifies" it to a single threshold.

#### 4f — four fields, four different questions, and only two of them are consumed now

The source table's real columns, per the user's own reading of the page (a summarising fetch
flattened the band into a maximum twice; the literal cells say otherwise):

```
Threat | NATO Designation | RWR Symbology | HARM Code | Range (NMI) min/max |
Altitude (Feet) min/max | Acquire Time (Seconds) | Guidance Type | Ammunition
```

Worked example, ZSU-23-4 Shilka: engagement range **0–2 NM**, **radar range 12 NM**, acquire time
**8 s**, altitude **0–6,500 ft**.

`EngagementEnvelope` therefore carries four distinct facts. They are easy to collapse into one
"threat range" and the collapse would be wrong in a different way each time, so the module docstring
must name what each one answers:

| field | answers | consumed by this milestone |
|---|---|---|
| `range_min_m` / `range_max_m` | *Can it shoot me from here?* | **yes** — the user's "nearing their engagement range of us" |
| `alt_min_m` / `alt_max_m` | *Can it shoot me at this height?* | **yes** — see the floor rule below |
| `radar_range_m` | *Can it see me?* — separate from and **longer** than weapon range | **no** |
| `acquire_time_s` | *Does it get a shot off before I'm past?* | **no** |

**The min end of the range band is real, not a rounding artefact.** Too close to engage is a genuine
state and a helicopter closing on a SAM actually reaches it. The envelope is an annulus, not a disc.

**The altitude floor is the tactical fact, and it only binds when non-zero.** I was wrong in the
previous revision of this section, twice over: the column is a band, and even the ceiling binds —
the Shilka's 6,500 ft is ~2,000 m, squarely inside a Mi-24P's operating range, not the unreachable
150,000 ft an S-300 ceiling suggested. More importantly the floor is where the tactics live:

- Shilka, `0–6,500 ft`: **no floor**, so flying low buys nothing against it. You are inside its
  altitude band on the deck.
- A system with a genuine minimum engagement altitude is **defeated by flying under it**.

That distinction is the whole point, and it falls straight out of the data with no special-casing:
the test is `alt_min_m <= h <= alt_max_m`, and `alt_min_m == 0` makes the lower bound vacuous on its
own. Do not write an `if floor == 0` branch — the arithmetic already does it.

`h` is ownship's height **above the threat's own position**, not MSL and not AGL:
`ownship_position.alt_m - contact.last_position.alt_m`. Both are already in hand inside `tick`. A SAM
on a 1,500 m plateau and one in a valley have the same band relative to themselves, and comparing
either against an MSL figure would be wrong by the terrain.

**Terrain LOS composes with both bands; it does not replace either.** The previous revision presented
LOS as a substitute for altitude, which was the wrong framing — they answer different questions. All
three are ANDed:

```
threatened = range_min_m <= range <= range_max_m          # can it shoot this far
             and alt_min_m <= height_above_threat <= alt_max_m   # can it shoot this high/low
             and los_clear(threat_position, ownship_position)    # is there a ridge in the way
```

with `range_max_m` scaled by `1.5` on the leaving side (4e). A helicopter hiding behind a ridge is
defeated by none of range or altitude — only by terrain — which is exactly why the third term is
needed and why it is not interchangeable with the second.

Two properties of the LOS term worth protecting from a later "simplification":

- **It is symmetric with perception.** He cannot see through terrain; neither can the SAM.
  `perception/visibility.py` already gates every sighting on `geometry.line_of_sight_clear`, and the
  same primitive answers both directions. The model needs no separate notion of "can it see me".
- **It subsumes the stale-contact cry-wolf case.** A contact decayed to `estimated` because you slid
  behind a ridge now fails LOS on its remembered position and goes "safe from", rather than warning
  off a position he cannot confirm.

**Cost.** `line_of_sight_clear` is a sampled elevation-grid walk against world-model's SQLite store —
the same call the naked-eye channel already makes per candidate per poll. Bounded here by *watched
contacts that resolved an envelope*, not by contact count: `envelope_for` returns `None` for
unknown/presence-level contacts and for classes with no row, and that check is free and runs first.
Order the three terms range → altitude → LOS so the cheap arithmetic rejects before the grid walk.

**Wiring, and the import cycle it avoids.** `contacts.py` cannot import `belief.enrichment` (cycle),
and `line_of_sight_clear` needs `conn` and `theatre`. Rather than widening `tick` with two
world-model arguments, inject the check:

```python
def tick(self, now_sim: float, ownship_position: GeoPosition | None = None,
         los_clear: Callable[[GeoPosition, GeoPosition], bool] | None = None) -> None
```

`logger.run_once` supplies a closure over its existing `world_model_conn`/`theatre`. `contacts.py`
stays free of both world-model and enrichment imports, the engagement block keeps its place in the
five-block loop (and its free `EVENT_COOLDOWN_S`), and a fixture tests the hysteresis with a two-line
lambda instead of a terrain database. `los_clear=None` skips the term — correct degradation for the
no-world-model path the console already handles elsewhere.

**`radar_range_m` and `acquire_time_s` are ingested and nothing reads them.** Say so explicitly in
the module docstring, because an unused field invites either deletion or invention:

- **Radar range is the natural home of a future "he's looking at us" warning**, and it is a
  *different* claim from "he can shoot us" — being tracked at 12 NM by a Shilka whose gun reaches
  2 NM is information, not a threat. The roadmap already records that "tracking us" is *observable*
  (a slewed dish is a visible fact) rather than an omniscience problem, so the perception half is
  legitimate; the knowledge half is this column. Transcribing it now costs one more cell per row and
  saves re-transcribing the whole table later.
- **Acquire time is what would eventually decide whether a fast crossing pass actually gets engaged**
  — the difference between overflying a Shilka and loitering in front of one. Nothing models
  time-in-envelope today.

Neither is speculative scope: they are cells in a row already being typed. **They must not acquire a
consumer in this milestone.**

#### 4g — getting the data into the repo, which is a real gate

The wiki page is HTML-only with no JSON/Lua/CSV export, and **the fetching tool available to the
planning session declines to reproduce the tables in full**, so the ingest cannot be automated from
here. This is a genuine blocker on Stage 4, not a formality — name it rather than discovering it
mid-implementation.

Two honest routes, and the first is better:

1. **The user pastes the tables.** They already have the page open — the Shilka row above came from
   them. Air-defence categories only (AAA, MANPADS, SAM, and the radar rows); ground armour and
   trucks have no envelope worth modelling against a helicopter beyond gun range. That is roughly 40
   rows, one paste, and it puts the literal cells in front of whoever transcribes them — which is
   exactly what would have prevented the two errors in this section's own history.
2. **An investigator pass with different tooling**, if the paste is inconvenient. Slower, and it
   reintroduces the summarisation risk that caused the problem.

**Do not begin Stage 4 before the data is in hand.** Transcribing from memory or from a summary is
how a wrong max range becomes a confident wrong danger call.

Whichever route: the result is a **transcribed snapshot of a community wiki**, carrying
`source="hoggit-threat-database"`, `confidence="provisional"` and the retrieval date per 4a, with a
missing or `TBC` cell degrading to **no warning** — never to an invented default.

---

### Decision 5 — the kilometre trigger, and the decay trap in it

Straightforward, with one non-obvious correctness rule.

- New `Contact.last_announced_range_km: int | None`.
- In `tick`, for a watched contact with `ownship_position` supplied:
  `current_km = floor(range_m(ownship_position, contact.last_position) / 1000)`.
- Fire `CONTACT_RANGE_CROSSED` when `current_km != last_announced_range_km` **and**
  `current_km <= WATCH_RANGE_REPORT_MAX_KM` (`5`, the user's own cap) **and** the contact is not in
  the silent-seed state.
- Fires on opening as well as closing. The user said "passes a whole kilometre mark", not "closes
  through one", and knowing something you are following is drawing away is the same kind of news.

**The trap: a decayed position will manufacture crossings nobody observed.** `relative_now` and
`Contact.last_position` are *believed* position, and `POSITION_HALF_LIFE_S` is 30 s against
`LOST_THRESHOLD_S` 120 s — a contact can sit in memory for two minutes while ownship flies past it,
and the *relative* range changes the whole time from ownship's motion alone. Without a gate,
Petrovich calls kilometre marks for a contact he last saw ninety seconds ago, with total confidence
and no basis.

**So: gate emission on `certainty_of(contact, now_sim) in ("observed", "tracked")`.** `"estimated"`
does not announce. This is the one rule in the milestone that is invisible in testing (a fixture with
a stationary ownship will never expose it) and wrong in flight, so it needs its own named test with
ownship moving past a stale contact.

Note this is a *different* question from whether to report at all — an `"estimated"` contact remains
watched, keeps its `last_announced_range_km`, and resumes announcing on reacquisition. Only the
*claim* is withheld, exactly as `render_no_view` withholds an absence claim rather than the belief.

---

### Implementation Plan

**Stage 1 — watched contacts report their movement. This is the stage the user notices first.**
`_WATCHED_ONLY_KINDS` and the watched test in `callouts.tick`'s filter; `_last_spoken_sim` +
`WATCH_REPORT_MIN_GAP_S`; `_contact_report_text`'s two affixes; `CONTACT_MOTION_CHANGED` in
`_render_lifecycle_text`. **No new event, no new data, no wire change** — the event has been firing
since `movement-detection` and has never been spoken. Smallest diff in the plan and the first time a
watched contact says anything unprompted. Flyable alone, body-layer only.

**Stage 2 — kilometre crossings.** `CONTACT_RANGE_CROSSED` in `events.py`;
`Contact.last_announced_range_km`; `tick` gains `ownship_position`; the sixth block in the loop;
`logger.run_once` passes the `GeoPosition` it already builds. The freshness gate and its named test.
Flyable alone; body-layer only.

**Stage 3 — `follow`.** Split in two, and 3a is worth shipping on its own:
- **3a — the synonym.** `vocabulary.py` phrasings only. Needs an audio-adapter redeploy (Mac-side),
  nothing else.
- **3b — the selector.** Nine `follow_clock_*` tokens, `parse_range_km`, the range slot through all
  five layers, `_handle_follow`, `render_no_contact`. The body-layer half is exercisable from the
  `!voice` harness and the typed console **before** any redeploy, which is how to test the selector
  logic without burning a sortie on recognition.

**Stage 4 — engagement envelopes. Gated on the table being in hand (4g) — do not start without it.**
`belief/threat.py` (transcription + rollup + `envelope_for`); `CONTACT_ENGAGEMENT_CHANGED`; the
seventh block in `tick` with the range annulus ANDed with the altitude band and the injected
`los_clear` term, the 1.5× hysteresis on the leaving side, and the seed-as-outside convention; the
two wordings. `radar_range_m`/`acquire_time_s` are transcribed and left unconsumed. Largest and least
certain — last, so the sortie after Stage 3 informs it.

**Stage 5 — prose and roadmap.** `STATE_TRANSITIONS.md`'s "Watching" block, both `ROADMAP.md`s,
`todo/todo.md` for the deferrals named below.

Verification after every stage that touches a subproject: `ruff format` + `ruff check` +
`mypy --strict` + `pytest`, in **each** touched subproject — both `body-layer` and `audio-adapter`
for Stage 3.

---

### Risks & Unknowns

- **Every new token is unbenched.** `follow nearest`, `follow nearest air defence`, `stop following`,
  `cancel follow`, nine `follow_clock_*`, and every `parse_range_km` phrasing have **no recordings in
  this corpus**. Their recognition accuracy on this user's voice is unmeasured — the same cost that
  kept `cancel_scan`/`cancel_watch` off voice until 2026-09-23. They should go into the next corpus
  recording. Until then, Stage 3's behaviour is verified only through the typed harness.
- **`follow` and `full` are one edit apart** (`scan_full` is an existing token) and both anchor at the
  start of an utterance. `VERB_ANCHOR_WORDS` is derived, so nothing will warn about this; the
  ambiguity band exists and will ask, but this collision deserves an explicit matcher test.
- **The range slot has no checksum.** "Follow two o'clock three kilometres" misheard as "two
  kilometres" is a legal, undetectable value. Only the readback protects against it.
- **`WATCH_REPORT_MIN_GAP_S = 8.0` and `FOLLOW_RANGE_TOLERANCE_KM = 0.75` are guesses**, uncalibrated
  like `SPEECH_RATE_WPS` and `MIN_UTTERANCE_S` next door. Both are isolated single constants.
- **Suppressed callouts are lost, not deferred** (Decision 3). Under load Petrovich will miss a
  "stopped" and never say it, because `last_emitted_motion` advances outside the cooldown guard.
  Pre-existing behaviour for every other kind; now applies to three more.
- **Hoggit data is a dated community snapshot** and some cells read `TBC`. A wrong max range produces
  a confidently wrong danger call. Missing values degrade to silence by design; wrong ones do not
  announce themselves.
- **Stage 4 is blocked until the table is physically in the repo** (4g), and the page cannot be
  fetched in full by the tooling available to planning. This is the only hard external dependency in
  the milestone; Stages 1–3 are unaffected.
- **The altitude column was misread twice before this plan settled** — a summarising fetch flattened
  `0 - 6500` into "6500 max", which inverted the conclusion (from "the floor is the tactical fact"
  to "drop the column"). Transcribe from the literal cells, never from a summary, and treat any
  single-number altitude as suspect.
- **Two ingested fields have no consumer** (`radar_range_m`, `acquire_time_s`). They will read as
  dead code to a reviewer. The module docstring must say what each is for and that neither is wired,
  or one will be deleted as unused and the other pressed into service as a threat range — being
  *tracked* is not being *shootable*.
- **The LOS term makes the danger state flap over broken ground.** Terrain masking is binary and
  changes fast at 150 kt through valleys, so danger/safe could alternate at the poll rate. The 1.5×
  hysteresis only damps the *range* boundary, not the LOS one. `EVENT_COOLDOWN_S` (15 s) and
  `WATCH_REPORT_MIN_GAP_S` (8 s) bound how often that reaches speech, but the underlying state will
  chatter in the event log, and if it proves audible the fix is a dwell on the LOS term — **not** a
  fourth suppression constant applied to speech.
- **`line_of_sight_clear` costs a sampled elevation walk per watched threat per poll.** Bounded by
  watched contacts with a resolved envelope (4f), not by contact count, but it is the first time this
  project calls the primitive outside the perception gate. If a watched-heavy sortie shows poll-time
  growth, this is the first thing to measure.
- **The `OP_SRSAM` bucket has a ~4× internal range spread** (Decision 4c), so the class-level warning
  will often be wrong in magnitude until type-level recognition lands. Recorded against the buckets,
  not fixed here.
- **`_AIR_DEFENCE_OP_CLASSES` omits `OP_LRSAM`** — "watch nearest air defence" will not select an
  S-300. Pre-existing, not touched by this plan, and the implementer should not fix it silently: it
  may be deliberate (an S-300 is rarely the nearest thing that matters). **Raise it, do not patch
  it.**
- **`store.tick`'s signature widens twice** (`ownship_position`, `los_clear`). Every existing caller —
  tests especially — passes only `now_sim`. Both default to `None` and the new blocks no-op without
  them, so nothing breaks; but a fixture that forgets to pass them will silently test nothing, and
  an `los_clear=None` in production would make every envelope fire without the terrain term. Assert
  the wiring at the `logger` level, not only in unit tests.
- **Out of scope and deliberately untouched:** the threat-band fill (`_DEFAULT_THREAT_BAND`), which is
  a deferred roadmap item marked *"Do not start without the user's instruction"*; `"tracking us"` /
  `"engaging us"` (no behaviour-change channel exists, and the roadmap has an open investigator
  question about whether turret azimuth is exportable at all); auto-watch-on-engaged; the
  group-as-single-threat "highest-capability member sets the reporting" rule; and *"frequently come
  back to watched targets"*, which is a scan-loop modifier belonging to `perception/gaze.py`, not to
  belief.

---

### Second-order effect

This **unblocks the deferred threat-band milestone**, which names unit engagement envelopes as its
principal missing input alongside terrain control and a behaviour-change channel. After Stage 4 the
envelope data exists behind a belief-keyed lookup, so `callouts._DEFAULT_THREAT_BAND` can be replaced
with a real band without any new data — and, importantly, without the omniscience hazard that item
warns about, because `envelope_for` structurally cannot see ground truth. It also **narrows** the
DCS-native unit-database investigation from "needed" to "a provenance upgrade", since the
belief-keyed lookup shape would not change if better numbers arrived.

---

### Decisions Requiring User Input

1. **`follow <clock>` when several contacts sit in that hour — watch all, or the nearest?**
   **Recommendation: all of them.** The pilot's own phrasing is *"follow **group** 1 o'clock"*, and
   a clustering model already means one contact ≈ one group of units at one bearing; several contacts
   in one hour are, from the cockpit, one patch of marks in one direction. Picking the nearest
   silently drops most of what he pointed at, and asking "which one?" is unanswerable by voice —
   contact ids are deliberately never spoken. The readback would name the count
   (*"Following four contacts, one o'clock."*). The cost is that `cancel_watch` must clear a set, and
   that one careless `follow` can mark a dozen contacts watched, multiplying Stage 1's reports.
2. **Does `follow` mean "watch that hour" or "watch those contacts"?** This plan assumes the latter —
   a per-contact mark that stays attached as the contact moves out of the hour. The alternative is
   cheaper and already built: a `relative_clock_hour` `AttentionArea`, which `reproject_relative_areas`
   already tracks through turns, so any contact entering the hour becomes watched and any leaving
   stops. But "follow" connotes following *the thing*, and the optional range slot has no meaning for
   an area. **Recommendation: contacts, as planned** — but this is a genuine fork and cheap to reverse
   only before Stage 3b is built.
3. **Is the late danger warning (Decision 4d) acceptable?** He cannot warn about a SAM he has not
   recognised, so in practice the first "Danger, SAM" often arrives when you are already well inside
   the envelope. I argue that is correct and valuable. If the expectation was an *early* warning, this
   trigger will disappoint, and that is better known before Stage 4 is built than after.
