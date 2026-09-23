### Goal

A contact the pilot has told Petrovich to watch reports itself — on movement change, on crossing a
whole-kilometre mark inside 5 km, and on entering or leaving its believed weapon envelope — and
"follow" becomes both a synonym for "watch" and a new way to *name* which contact to watch
(`follow [armor] [2 o'clock] [3 km]`, resolved by best match).

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
  needed: `contacts.py` already imports `GeoPosition` from `perception.geometry` **and `Observation`
  from `perception.source`**, so passing the whole `OwnshipState` (position, `alt_agl_m`, heading)
  adds no import and no cycle. `logger.run_once` already has it in hand at the
  `self.store.tick(ownship.t_sim)` call site.
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
- `body-layer/src/belief/contacts.py` — `tick` gains `ownship: OwnshipState | None = None` (position
  *and* `alt_agl_m`, 4f) and `los_clear: Callable[[GeoPosition, GeoPosition], bool] | None = None`;
  two new blocks in the five-block loop; new `Contact` fields (`last_announced_range_km`,
  `last_emitted_engagement`, and the watched-seed bookkeeping below).
- `body-layer/src/belief/threat.py` — **new module.** Loads `data/threat_envelopes.json`, derives the
  per-`op_class` worst-case rollup, and exposes the believed-classification lookup. The only new
  module in the plan. Carries the per-field null rules (4f-i) and the match from a threat row to
  `object_model`'s keyword table.
- `body-layer/data/threat_envelopes.json` + the saved source page under `docs/concept/` —
  **extracted, untracked, must be committed before Stage 4** (4g). The `_files/` asset directory
  beside the HTML is 1.8 MB of page chrome and must be gitignored, not committed.
- `body-layer/src/belief/callouts.py` — `_WATCHED_ONLY_KINDS`; the watched test in `tick`'s filter;
  a per-contact `_last_spoken_sim` gap for the watched-only family.
- `body-layer/src/belief/speech.py` — `_contact_report_text` gains two optional affixes
  (`lead`, `event_clause`); `_render_lifecycle_text` gains the two new kinds; `render_no_contact`.
  **No second rendering path.**
- `body-layer/src/belief/crew_console.py` — `_handle_follow` and `_resolve_follow_target` (the
  scoring resolver, Decision 2b-iii) with its weights/thresholds; `slots` threaded through
  `handle_command`/`handle_transcript`/`_act_on_voice_decision` **replacing** `bearing_degrees`;
  `DISPATCHED_COMMAND_TOKENS` updated; `_describe_token_for_confirm` renders the slot set.
- `body-layer/src/belief/voice_commands.py` — `PendingConfirmation.slots` replaces
  `PendingConfirmation.bearing_degrees`.
- `body-layer/src/logger.py` — pass the `OwnshipState` it already holds into `store.tick`, plus the
  `los_clear` closure over the existing `world_model_conn`/`theatre`; read `slots` off the
  transcript event; `!voice` harness takes the slot set.
- Tests: `test_events.py`, `test_contacts.py`, `test_threat.py` (new), `test_callouts.py`,
  `test_speech.py`, `test_crew_console.py`, `test_logger.py`.

**audio-adapter**

- `audio-adapter/src/vocabulary.py` — `follow` phrasings on `watch_nearest`/
  `watch_nearest_air_defence`/`cancel_watch`; a single `follow` token (no `follow_clock_*` family —
  the clock is a slot, Decision 2b-i); `parse_clock`/`parse_range_km`/`parse_descriptor`; the closed
  descriptor set mirroring `speech._OP_CLASS_DISPLAY`.
- `audio-adapter/src/command_matcher.py` — slot parsing for the `follow` verb alongside the existing
  bearing slot; `MatchResult.slots: dict[str, int | str] | None` **replacing** `bearing_degrees`.
- `audio-adapter/src/transcript_queue.py`, `server.py` — `TranscriptEvent.slots` replaces
  `TranscriptEvent.bearing_degrees` and its `to_dict` key. **A breaking wire change**, cheap because
  both ends are Mac-local processes restarted together (Decision 2b-i).
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

### Decision 2 — `follow` is two changes: a free synonym, and a descriptor-match resolver

**(a) The synonym is free.** `follow nearest` / `follow nearest air defence` become extra phrasings
on the existing `watch_nearest` / `watch_nearest_air_defence` tokens; `stop following` / `cancel
follow` join `cancel_watch`. `VERB_ANCHOR_WORDS` picks up `follow` automatically. **Zero body-layer
change.** This is a `vocabulary.py` edit and nothing else.

**(b) `follow [<descriptor>] [<clock> o'clock] [<n> km]` — a best-match referring expression.**
User direction, 2026-09-24:

> *this really needs the brain so I can freetext tell which contact to follow. Let's approximate it
> by "follow/watch [group/class/type] &lt;where o'clock&gt; &lt;distance&gt;" then find the closest
> match to it and watch that.*

**Frame this as the stopgap it is, in the code and not only here.** The user named it an
approximation of a brain-layer capability. When free text arrives, `_resolve_follow_target` should be
**deleted, not extended**, and its weights are not a model of anything — they are a scoring hack
standing in for comprehension. Say that in the function's own docstring, or someone will tune it as
if it were a perception model.

#### 2b-i — the vocabulary shape, which is the crux of the stage

`follow armor 2 o'clock 3 km` **cannot be a token.** Descriptors × nine hours × ranges is a
cross-product in the hundreds, and `vocabulary.py`'s closed grammar has to list what it admits. This
needs parsed slots, and there is exactly one precedent: `bearing_degrees`, threaded matcher → wire →
console in Stage 3 of `plans/voice-command-completeness/plan.md`.

**Three slots at once is where the flat-field shape stops being right.** `TranscriptEvent` carries 8
fields today, 9 with `bearing_degrees`. Adding `descriptor`/`clock`/`range_km` makes 12, of which 4
are mutually-exclusive per-token payloads — the wire would be describing a transcript in terms of
whichever command it happened to be. So:

**Replace `bearing_degrees` with one structured field, in the same change:**

```python
slots: dict[str, int | str] | None = None     # on MatchResult and TranscriptEvent
```

`handle_command(token, *, slots=None)`; `PendingConfirmation.slots`. `bearing_degrees` becomes
`slots["bearing_degrees"]`.

**Why migrate rather than add a second mechanism:** doing it now, with exactly one existing slot, is
strictly cheaper than doing it later with four, and the alternative is precisely the "second
mechanism" this project keeps warning against. **The wire is ours end to end** — audio-adapter and
body-layer are both Mac-local processes restarted together — so a breaking change costs a coordinated
restart, not a migration. (The Windows collector is a different endpoint and is untouched.) It also
collapses Stage 3's six-item plumbing list into one generic path, so the three follow slots need
*zero* new wire work.

**Missing `PendingConfirmation.slots` is the specific way this breaks**: a `follow` that lands in the
confirm band would lose all three qualifiers on "affirm" and act on a bare verb. Stage 3 hit the same
trap with `bearing_degrees`.

**Three parsers in `vocabulary.py`**, siblings of `parse_bearing`:

- `parse_clock` — reuses `_CLOCK_WORDS` and the existing `o’clock`/`o clock`/`oclock` normalisation
  that `report_clock_*` already needed.
- `parse_range_km` — anchored on `km` / `kilometre(s)` / `klick(s)`.
- `parse_descriptor` — matched against the closed descriptor set below.

**The range slot has no checksum, and that must be said.** `parse_bearing`'s 5° constraint rejects
roughly four in five mishearings. Whole kilometres have no such redundancy — "three" heard as "two"
is a legal, undetectable value. Constrain to integers 1–20 and rely on the readback. Do **not** copy
the "resolution is a checksum" comment across; it would be false here.

#### 2b-ii — the descriptor vocabulary is closed, and admits two of the user's three kinds

The descriptor set is **exactly the words Petrovich himself speaks** — `speech._OP_CLASS_DISPLAY`'s
vocabulary ("armor", "truck", "SAM", "AAA", "infantry", "ship"), plus `group`. If he calls it armor,
the pilot must be able to say "follow armor"; any other vocabulary is one the pilot cannot learn
without reading the source.

- `group` → matches on `cardinality.lo > 1` (the user's own example word).
- a class word → matches `classification.value`'s `OP_*` bucket through the same display map.
- **Type names are deliberately not admitted**, narrowing the user's "group/class/type" to two.
  Reasons: a type set is open and cannot be enumerated into a closed grammar (`vocabulary.py`'s own
  rule for why "report the tanks" was excluded), and a type-level descriptor only helps once he has
  *type*-classified the contact — which needs ~250 m unaided (2b-iv). It would be vocabulary that
  almost never fires. **This is a stated scope cut, not an oversight.**

#### 2b-iii — the scoring: minimise a distance-to-request, with a floor

All three qualifiers are optional; **at least one must be present.** A missing qualifier contributes
nothing and does not penalise. Candidate set is the same one `_handle_report` builds —
`tools.get_contacts(...)`, drop `certainty == "lost"`, drop contacts with no `relative_now`, and
answer the existing "no world-model connection configured" line when `self.enrichment is None`.

| qualifier | contribution to the score (lower is better) |
|---|---|
| descriptor | `0` exact class/group match · `W_DESC_UNKNOWN` if the contact is presence-level or unclassified · `W_DESC_WRONG` (large) if it is a *different* known class |
| clock | `abs(wrapped hour delta) × W_CLOCK` |
| range | `abs(range_km − actual_km) × W_RANGE` |

**The unclassified case is the one that earns the soft descriptor.** If the pilot says "follow armor"
and the only thing at two o'clock is an unresolved dot, he is pointing at a thing he *believes* is
armour — matching it is right. Matching a known *truck* when he said armor is wrong. A hard filter
gets the first case wrong; the three-way soft score gets both right.

**Clock is a soft match here, unlike `report_clock_*`, and the divergence is deliberate.** `report
three o'clock` asks about a *region* and an exact 30°-bucket match is correct — layering a tolerance
on a quantisation would overlap regions the speaker did not name. `follow` names *a thing*, and a
pilot's eyeball estimate of which hour it sits in is routinely an hour out. Same word, different
question. Write the reason next to the weight or someone will "unify" the two rules.

- **Match floor.** If the best score exceeds `FOLLOW_MATCH_FLOOR`, watch **nothing** and say so —
  `"Nothing like that."`, or `"Nothing at two o'clock."` when the clock was the only qualifier given.
  Direct precedent: `command_matcher.MATCH_FLOOR` refusing a phrase rather than taking the least-bad
  one. Watching the least-bad contact is worse than admitting no match, because the pilot then gets
  confident reports about the wrong object.
- **Ties: prefer the nearer, and let the readback expose it.** When the best two scores fall within
  `FOLLOW_SEPARATION`, take the closer contact rather than asking. A confirm round-trip costs seconds
  while the pilot is pointing at something *now*; `render_watch_nearest_readback` already names unit,
  clock and range, so a wrong pick is audible immediately and `cancel watch` + re-issue is one
  utterance. This is a deliberate divergence from the matcher's `ambiguous` → ask behaviour, which
  can afford the round-trip because it has no target decaying in front of it.
- **Winner** → `watch_contact_task(...)`, readback via the existing `render_watch_nearest_readback`.
  **Exactly one contact, never a set** — confirmed by the user's *"find the closest match to it and
  watch that"*.

**Every weight and both thresholds are guesses**, uncalibrated in the same way `SPEECH_RATE_WPS` is.
They are isolated module constants in `crew_console.py` and are meant to be thrown away with the
resolver.

The rear-hemisphere "can't see there" carve-out does **not** apply: `FORWARD_CLOCK_POSITIONS` is 8–4,
all inside the Mi-24P mask's `rear_cutoff_deg` by construction.

#### 2b-iv — "follow" attaches to the contact, not to the hour — **confirmed**

The alternative was a `relative_clock_hour` `AttentionArea`, which `reproject_relative_areas` already
tracks through turns: any contact entering the hour becomes watched, any leaving stops. **The user
confirmed the per-contact reading.** It is also the only one consistent with the resolver above — a
best-match score picks a *thing*, and the descriptor and range qualifiers have no meaning for a
region. Recorded as decided, not assumed.

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

**Source:** `https://wiki.hoggitworld.com/view/Threat_Database`, **already extracted** to
`body-layer/data/threat_envelopes.json` (28 entries) with the saved page committed beside it as
provenance. Per-type engagement range band and altitude band, by threat category. **Every range
column is a min/max band written as one cell** (`0 - 6500`) — see 4f, which is where two successive
misreadings of that fact were caught and where the data now settles the question empirically.

#### 4a — provenance

This is a **community wiki**, not DCS ground truth and not ED documentation. It is the same evidence
class as the pydcs-derived projections in `world-model` and takes the same treatment recorded in this
project's provenance memory: **provisional until confirmed**, never silently promoted to fact.

- **The payload carries its own provenance and `threat.py` must read it, not restate it** — the
  JSON header already holds `source`, `source_file`, `retrieved: 2026-09-24`, `provenance` and
  `units`. Two copies of a retrieval date drift; one does not.
- **No fallback envelope, ever.** There is no `DEFAULT_ENGAGEMENT_RANGE_M`. A contact whose class
  resolves to no row simply never produces a danger call. Inventing a number would be worse than
  silence: an authoritative-sounding warning derived from nothing, and an invisible one, because the
  output would merely look like slightly odd prioritisation. **Which nulls mean silence and which
  mean "no protection" is not uniform — see 4f-i**, where applying one blanket rule would have been
  backwards for three fields out of four.
- **Conversion already happened, once, at extraction.** The file is metres throughout; the source's
  NMI and feet never reach the code. No caller converts.

#### 4b — why a transcribed snapshot, rather than the DCS install

*(The rows are extracted; what remains before Stage 4 can start is committing them — 4g.)*

Extraction was one-off, from a saved copy of the page, into a committed JSON payload. There is no
JSON/Lua/CSV export upstream and the set that matters is small (air-defence categories only — ground
armour and trucks have no envelope worth modelling against a helicopter beyond gun range). A live
scraper against a page with no stable schema would be more code than the data it produces and would
rot the moment the wiki's markup changed; the saved HTML beside the payload is the reproducible
artifact instead.

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

#### 4d — the warning arrives with recognition — **accepted by the user, and it is gated on the 9K113**

**Accepted, 2026-09-24**, with a qualification that changes what this milestone is worth:

> *useful for SHORAD, longer range SAM's can't be identified that far. Even for SHORAD, the 9K113
> view is needed for identification at safe range.*

Because the envelope is keyed on believed classification, Petrovich cannot warn about a contact he
has not yet classified. **For long-range SAMs that is not a defect of this feature** — you cannot
identify an S-300 at 40 km by eye, with or without this milestone, and no design choice here changes
that. The feature's real target is **SHORAD**, where recognition range and weapon range are the same
order of magnitude and the warning can actually precede the shot.

**But for SHORAD the margin is currently negative, and the arithmetic says so.** Class recognition —
the tier that matters, since `envelope_for` resolves at class level via the rollup — is
`recognition_extent_m / MEDRES_ANGULAR_RADIUS_RAD × optic.class_range_mult`. For a 7 m vehicle
(`0.014 rad`), against a ZSU-23-4's own 2 NM (3,704 m) envelope:

| optic | `class_range_mult` | class recognition | vs. a Shilka's 3,704 m envelope |
|---|---|---|---|
| unaided | 1.00 | **500 m** | recognised at 13% of the way in — useless |
| binocular | 3.50 | **1,750 m** | recognised at 47% in — already engaged |
| **9K113 (wide), deferred** | **7.00** | **3,500 m** | **recognised at the envelope edge** |

So with the two optics that exist, **the danger call fires from inside the envelope of nearly every
threat it can recognise.** With the 9K113 it fires as you arrive at the edge — which is the
difference between a warning and a statement of fact.

**That does not make the milestone wrong.** The data and the trigger are correct, the class tier
reaches considerably further than type, and the warning is still worth having late. But record the
dependency plainly: **the practical value of the engagement trigger is gated on an optic that does
not exist yet** — *"Model the 9K113 Raduga-Sh as a selectable optic"*, deferred 2026-09-20 in
`todo/todo.md`.

**This is the strongest argument yet for un-deferring the 9K113, and it is a different argument than
the one that was deferred.** The 9K113 was shelved as *more detail* — a third optic when two already
worked. The case now is *identify the thing before it can shoot you*: it is the only optic in the
table whose class range reaches a SHORAD envelope's edge, and its multipliers (wide 3.55/7.00/6.50)
are **already measured and already written down** in `perception/optics.py`'s module docstring,
waiting for a slice that wires them. Add this to the todo entry as the reason the deferral should be
revisited — do not un-defer it inside this milestone.

Two consequences the implementer must not get wrong:

1. **"Entering the envelope" is not only an outside→inside geometric crossing.** Per the table above
   it is far more often a *recognition* event while already deep inside. Hence Decision 1's "seed as
   outside" convention: the first evaluation that resolves a class and finds itself inside fires. One
   wording covers both — the pilot needs the same fact and can take the same action either way, and a
   second wording for a distinction he cannot act on is noise.
2. **Reliability tracks recognisability, not threat.** An S-300 radar carries `distinctiveness=2.6`
   and is recognisable a long way out, so its danger call will be comparatively early — while the
   launcher beside it is not. A Strela-10 in a treeline will be recognised at knife-fight range or
   not at all. Say this in the sortie card, because a pilot who gets one good
   warning and one absent one will otherwise read the absent one as a bug.

#### 4e — the 1.5 factor is hysteresis, and that is why it exists

`STATE_TRANSITIONS.md` specifies *"until well outside its engagement envelope (1.5 factor for now)"*.
Enter at `1.0 ×` max range, leave at `1.5 ×`. This is a Schmitt trigger: without the gap, a contact
sitting near the boundary flaps between "danger" and "safe from" every few seconds and burns the
`EVENT_COOLDOWN_S` budget doing it. Implement it as hysteresis and say so, so nobody later
"simplifies" it to a single threshold.

#### 4f — three independent ways to be safe, settled by the data rather than by argument

The table is extracted: **`body-layer/data/threat_envelopes.json`, 28 entries** (19 SAM, 6 AAA,
3 MANPADS), with the saved source page committed beside it at
`docs/concept/Threat Database - DCS World Wiki - Hoggitworld.com.html` as its provenance. Fields:
`threat`, `nato`, `category`, `range_min_m`, `range_max_m`, `alt_min_m`, `alt_max_m` — **metres,
converted once at extraction** from NMI and feet, so no caller ever converts.

**The altitude question is now measured, and my earlier "drop the column" was wrong.** The column is
a band, and 12 of 28 entries carry a non-zero floor. The split is **by category, not by reach** —
which is the more useful rule and the physically sensible one (radar-guided SAMs suffer ground
clutter; optically- and IR-aimed weapons do not):

| category | entries with a non-zero floor |
|---|---|
| SAM | **12 of 19** |
| AAA | **0 of 6** |
| MANPADS | **0 of 3** |

| system | floor | reach |
|---|---|---|
| S-125 / SA-3 | 213 m | 25.0 km |
| MIM-23 Hawk | 137 m | 47.4 km |
| MIM-104 Patriot | 61 m | 159.3 km |
| MIM-72G Chaparral | 46 m | 5.6 km |
| 2K12 / SA-6 | 30 m | 35.6 km |
| 9K31 / SA-9 | 30 m | 4.6 km |
| **9K35 / SA-13** | **23 m** | **5.2 km** |
| 9K331 / SA-15, 9K37 / SA-11 | 18 m | 12.0 / 35.6 km |
| 9K33 / SA-8, S-300PS / SA-10 | 15 m | 13.9 / 74.1 km |
| MIM-115 Roland | 9 m | 6.3 km |

**Correcting the summary this section was first written from: the floor is not confined to
long-reach systems.** SA-13 (23 m / 5.2 km), SA-9 (30 m / 4.6 km), Roland (9 m / 6.3 km) and
Chaparral (46 m / 5.6 km) are SHORAD, and their floors sit at exactly the NOE altitudes a Mi-24P
actually flies. So the floor is tactically live **in the same SHORAD band where 4d says this feature
is worth having at all** — better news than "it only matters under a Hawk". Meanwhile every gun and
every MANPADS will engage on the deck, and the data says so uniformly rather than by assumption.

**The test ANDs three independent conditions**, and each answers a different question:

```
threatened = range_min_m <= range <= range_max_m          # can it shoot this far
             and (alt_min_m is None or ownship_agl >= alt_min_m)   # am I under its floor
             and los_clear(threat_position, ownship_position)      # is there a ridge in the way
```

with `range_max_m` scaled by `1.5` on the leaving side (4e), and the terms ordered **range →
altitude → LOS** so the cheap arithmetic rejects before the elevation-grid walk.

Three different ways to be safe: **out of range, under the floor, behind a ridge.** The terrain
reasoning below survives intact — it was only ever wrong as a *replacement* for altitude.

**`alt_max_m` is carried and never tested against.** The lowest ceiling in the table is 1,372 m,
which a Mi-24P can technically reach but essentially never occupies on a combat profile. Keep the
field (it is already extracted, and a future high-altitude or fixed-wing consumer would want it) and
say in the docstring that nothing reads it, so its absence from the test reads as a decision rather
than an omission.

**Which altitude: `alt_agl_m`, and this is settled, not inferred** (user, 2026-09-24). The floor is
a *minimum engagement altitude* — physically a ground-clutter and radar-horizon limit — so height
above the terrain is the meaningful quantity, and it is also the number the pilot actually flies to
("stay under 200 feet"). MSL would be nonsense over a 1,500 m plateau. `OwnshipState.alt_agl_m` was
added by the binocular milestone and is already populated from the wire's `altitude_agl_m`; nothing
new is needed to read it.

**This changes what `tick` receives.** An earlier revision passed a bare `GeoPosition`; AGL is not on
it. Pass the whole `OwnshipState` instead — `contacts.py` already imports from `perception.source`
(it uses `Observation`), so this adds no import and no cycle, and it supplies position, AGL and
heading in one argument:

```python
def tick(self, now_sim: float, ownship: OwnshipState | None = None,
         los_clear: Callable[[GeoPosition, GeoPosition], bool] | None = None) -> None
```

#### 4f-i — nulls do **not** all degrade the same way, and the payload's own rule is inverted for three of four fields

`threat_envelopes.json` states: *"a null MUST degrade to no warning, never to a default."* **That is
correct for `range_max_m` and dangerously backwards for the other three.** Read literally, a missing
`alt_min_m` would *suppress* a warning — i.e. a system whose floor we do not know would be treated as
though flying low defeated it. The conservative direction is the opposite: unknown protection is no
protection.

| field | null count | degrades to | why |
|---|---|---|---|
| `range_max_m` | 1 (SA-5) | **no envelope at all — silence** | with no reach there is nothing to test; this is the payload's rule, and it is right here |
| `range_min_m` | 5 (SA-2, SA-5, SA-11, Rapier, NASAMS) | **0 — no inner hole** | assume it can shoot you close in |
| `alt_min_m` | 6 | **no floor — altitude never protects** | assume flying low does not help |
| `alt_max_m` | 2 | unused anyway | — |

**The SA-2 case is why this matters and why the blanket rule had to be split.** S-75 / SA-2 has a
null `range_min_m` and a null `alt_min_m` but a perfectly good **51.9 km** `range_max_m`. Applying
"any null ⇒ silence" entry-wide would throw away a 51 km envelope over two missing inner bounds — for
one of the most recognisable threats on the map. **Only SA-5 (S-200) is genuinely unusable**, with
every numeric field null.

Write this per-field table into `threat.py`'s docstring. A single "nulls mean silence" line is the
kind of rule that reads as safe and is not.

#### 4f-ii — LOS is a *precondition for tracking*, not a terrain nicety

Reframed by the user, 2026-09-24: *"LOS is required for radar tracking."* This is stronger than "a
ridge happens to be in the way", and it changes what the term means. **A radar-guided system cannot
track what it cannot see**, so line of sight is not a modifier on an otherwise-live threat — it is
part of what makes the threat live at all. Three behavioural consequences follow, and they are
behaviours rather than restatements:

1. **Losing LOS *ends* the threat state; it does not merely fail to start it.** A system that had you
   and then lost you when you dropped behind a ridge stops being a threat, and a standing danger
   warning should **clear** — `CONTACT_ENGAGEMENT_CHANGED` fires in the "safe from" direction on an
   LOS loss exactly as it does on a range exit. This is the duck-behind-terrain behaviour the pilot
   will actually fly, and it will be immediately obvious in the air as working or not — which makes
   it the best acceptance test in the milestone.
2. **It is symmetric with perception.** He cannot see through terrain; neither can the SAM.
   `perception/visibility.py` already gates every sighting on `geometry.line_of_sight_clear` (a thin
   wrapper on world-model's `query.line_of_sight`), and the same primitive answers both directions.
   The model needs no separate notion of "can it see me".
3. **It is why `acquire_time` will eventually earn its column** (4f-iii). A brief exposure crossing a
   gap may not last long enough for the system to acquire. LOS-as-precondition *plus* acquire time is
   what separates "it saw me for a second" from "it has me". Nothing consumes it here, but the reason
   to extract it later is now concrete rather than speculative.

#### 4f-ii-a — the LOS test inherits belief uncertainty, and that is the part most likely to bite

**Ownship's end of the sightline is exact; the threat's end is a belief.** `Contact.last_position` is
reconstructed from a percept, and `Contact.last_position_uncertainty_m` is its error budget — a
conservative scalar radius in **metres** (`association_over_time.uncertainty_radius_m`). *Use it as
metres of position error, which is what it is; do not convert it into a bearing error* — that
misreading already cost a pass on `plans/binocular-optic/stage3b.md`. The terrain profile between the
**believed** position and ownship can be nothing like the profile to the real one.

**Resolution: sweep the uncertainty rather than pretend it is not there** — the same answer the
binocular search arrived at for the same class of problem.

- **Sample LOS at three points, not one:** the believed position and two lateral offsets at
  `±last_position_uncertainty_m` perpendicular to the ownship→threat bearing. **If any sample is
  clear, treat the threat as having LOS.** Lateral is the axis that matters — whether a ridge
  intervenes turns on *which side of it* the threat is, far more than on how far along the bearing.
- **Fail open, deliberately, because the costs are asymmetric.** A false danger call costs the pilot
  a glance; a missed one costs the aircraft. So LOS may only *suppress* a warning when the whole
  uncertainty disc is masked.
- **Do not shrink the effective range to account for uncertainty.** That would smear a positional
  error into a capability figure and quietly make the envelope table wrong. Keep the table honest and
  put the uncertainty where it belongs — in the geometry query.

**Consistency check, and it comes out right:** fail-open plus three samples still delivers the
duck-behind-a-ridge behaviour, because a ridge is hundreds of metres to kilometres across while a
freshly-observed contact's uncertainty is tens to low hundreds of metres — the ridge masks the whole
disc and the warning clears. For a *stale* contact the disc is large and the warning persists longer.
That is honest rather than a defect: he does not know you are safe, he knows he has lost sight of the
thing. Note the tension with consequence 1 above and resolve it that way in the implementation, not
by tightening the samples.

**Cost.** Three elevation-grid walks instead of one, per watched contact that resolved an envelope
per poll — the same primitive the naked-eye channel already runs per candidate per poll. Bounded by
*watched contacts with an envelope*, not by contact count: `envelope_for` returns `None` for
unknown/presence-level contacts and for classes with no row, and that check is free and runs first.
`LOS_UNCERTAINTY_SAMPLES = 3` is an isolated constant.

**Wiring, and the import cycle it avoids.** `contacts.py` cannot import `belief.enrichment` (cycle),
and `line_of_sight_clear` needs `conn` and `theatre`. Rather than widening `tick` with two
world-model arguments, inject the check as the `los_clear` callable above; `logger.run_once` supplies
a closure over its existing `world_model_conn`/`theatre`. `contacts.py` stays free of world-model and
enrichment imports, the engagement block keeps its place in the five-block loop (and its free
`EVENT_COOLDOWN_S`), and a fixture tests the hysteresis with a two-line lambda instead of a terrain
database. `los_clear=None` skips the term — correct degradation for the no-world-model path.

#### 4f-iii — what was *not* extracted, and whether it is worth a pass

The SAM table carries separate **`Track RADAR` and `Search RADAR` columns with HARM codes**, and an
acquire-time column; none is in the extracted payload. An earlier revision of this plan speculatively
designed `radar_range_m`/`acquire_time_s` fields — **drop them from the schema**: the extracted file
is the schema, and inventing fields it does not contain is how a table and its reader drift.

They are worth a **later** pass, not this one:

- **Search/track radar is detection range, which is a different and longer claim than weapon range** —
  being tracked at 12 NM by a gun that reaches 2 NM is information, not a threat. That is the natural
  home of a future *"he's looking at us"* warning, which the roadmap already records as legitimate
  (a slewed dish is *observable*, not an omniscience problem). It needs a behaviour-change channel
  that does not exist, so the data would sit unused.
- **Acquire time** would decide whether a fast crossing pass actually gets engaged — it needs a
  time-in-envelope model that nothing has.

Record both in `todo/todo.md` as a follow-on extraction against the same saved HTML, so the next pass
does not re-fetch a page that may have changed.

#### 4g — the data is extracted but **not yet committed**

`body-layer/data/threat_envelopes.json` and the saved HTML exist in the main checkout as **untracked
files**, on no branch. Stage 4 cannot start until they are committed. Three things to settle when
they are:

1. **Neither path is gitignored** — `.gitignore` covers `graphify-*`, `win-mac-sync` and the `.miz`
   samples, not `body-layer/data/`. So `git add` will work; the file is not at risk of being silently
   swallowed the way `world-model/data/` would be.
2. **The saved page brings a 1.8 MB `..._files/` asset directory** (CSS, images, scripts) beside the
   160 KB HTML. Commit the **HTML only**; the assets are page chrome and carry no evidence.
   `.gitignore` the `_files/` directory, or the repo gains 1.8 MB of wiki styling as permanent
   history.
3. **Provenance travels with the payload, and already does** — the JSON's own header carries
   `source`, `source_file`, `retrieved: 2026-09-24`, `provenance: community wiki, transcribed
   snapshot -- not DCS ground truth`, and `units`. `threat.py` must not restate those as literals;
   read them from the file so the two cannot disagree.

**Community wiki, not DCS ground truth, and not ED documentation.** Same evidence class as the
pydcs-derived projections in `world-model`, and the same treatment: provisional until confirmed. A
wrong `range_max_m` produces a confidently wrong danger call and does not announce itself.

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
- **3b — the slot migration.** `slots` replaces `bearing_degrees` end to end (matcher → wire →
  console → `PendingConfirmation`). **No behaviour change**, and worth its own commit for exactly
  that reason: it is the one step that touches already-flown paths, so a regression here is
  attributable rather than tangled up with the new command.
- **3c — the resolver.** The `follow` token, three slot parsers, the descriptor set,
  `_resolve_follow_target` with its weights, floor and tie rule, `render_no_contact`. The body-layer
  half is exercisable from the `!voice` harness and the typed console **before** any redeploy — which
  is how to tune the weights without burning a sortie on recognition, and the only part of this
  milestone whose behaviour is a judgement call rather than a threshold.

**Stage 4 — engagement envelopes. Gated on the payload being committed (4g) — do not start without it.**
`belief/threat.py` (transcription + rollup + `envelope_for`); `CONTACT_ENGAGEMENT_CHANGED`; the
seventh block in `tick` ANDing the range annulus, the AGL floor and the three-sample `los_clear`
term, the 1.5× hysteresis on the leaving side, and the seed-as-outside convention; the two wordings.
Largest and least certain — last, so the sortie after Stage 3 informs it. **Its acceptance test is
the duck-behind-a-ridge behaviour** (4f-ii): fly under a ridge from a recognised SAM and hear the
danger call clear.

**Stage 5 — prose and roadmap.** `STATE_TRANSITIONS.md`'s "Watching" block, both `ROADMAP.md`s,
`todo/todo.md` for the deferrals named below.

Verification after every stage that touches a subproject: `ruff format` + `ruff check` +
`mypy --strict` + `pytest`, in **each** touched subproject — both `body-layer` and `audio-adapter`
for Stage 3.

---

### Risks & Unknowns

- **Every new token and every slot phrasing is unbenched.** `follow nearest`, `follow nearest air
  defence`, `stop following`, `cancel follow`, the `follow` verb, and every descriptor / clock /
  range phrasing have **no recordings in this corpus**. Their recognition accuracy on this user's voice is unmeasured — the same cost that
  kept `cancel_scan`/`cancel_watch` off voice until 2026-09-23. They should go into the next corpus
  recording. Until then, Stage 3's behaviour is verified only through the typed harness.
- **`follow` and `full` are one edit apart** (`scan_full` is an existing token) and both anchor at the
  start of an utterance. `VERB_ANCHOR_WORDS` is derived, so nothing will warn about this; the
  ambiguity band exists and will ask, but this collision deserves an explicit matcher test.
- **The range slot has no checksum.** "Follow two o'clock three kilometres" misheard as "two
  kilometres" is a legal, undetectable value. Only the readback protects against it.
- **The resolver's weights, `FOLLOW_MATCH_FLOOR`, `FOLLOW_SEPARATION` and `WATCH_REPORT_MIN_GAP_S`
  are all guesses**, uncalibrated like `SPEECH_RATE_WPS` next door. They are isolated constants and
  are meant to be deleted with the resolver when free text arrives — **do not tune them as if they
  modelled something.**
- **The descriptor resolver is a stopgap for a brain-layer capability** (user's own framing). The
  risk is that it works *well enough* to become load-bearing, and then nobody replaces it. Its
  docstring must say it is temporary.
- **Suppressed callouts are lost, not deferred** (Decision 3). Under load Petrovich will miss a
  "stopped" and never say it, because `last_emitted_motion` advances outside the cooldown guard.
  Pre-existing behaviour for every other kind; now applies to three more.
- **Hoggit data is a dated community snapshot** (retrieved 2026-09-24). A wrong `range_max_m`
  produces a confidently wrong danger call and does not announce itself.
- **Nulls are not rare and not uniform** (4f-i). SA-5 is fully unusable and will never produce a
  warning; SA-2 keeps a 51.9 km reach but has no inner bound; six entries have no floor. "Degrades
  to silence" is the behaviour for a real, recognisable threat, not an edge case — say so in the
  sortie card, or its silence reads as a bug.
- **Stage 4 is blocked until the payload is committed** (4g). It exists but is untracked, on no
  branch. Only hard dependency in the milestone; Stages 1–3 are unaffected.
- **The altitude column was misread twice before the data settled it** — a summarising fetch
  flattened `0 - 6500` into "6500 max", which inverted the conclusion twice over (first "gate on the
  ceiling", then "drop the column"; the answer was "gate on the floor"). Read literal cells, never a
  summary, and treat any single-number range as suspect.
- **The LOS term makes the danger state flap over broken ground, and it now drives a real
  transition.** Since losing LOS *clears* a warning (4f-ii), terrain masking that changes fast at
  150 kt through valleys will alternate danger/safe at the poll rate. The 1.5× hysteresis damps only
  the *range* boundary, not the LOS one. `EVENT_COOLDOWN_S` (15 s) and
  `WATCH_REPORT_MIN_GAP_S` (8 s) bound how often that reaches speech, but the underlying state will
  chatter in the event log, and if it proves audible the fix is a dwell on the LOS term — **not** a
  fourth suppression constant applied to speech.
- **`line_of_sight_clear` now costs three sampled elevation walks per watched threat per poll**
  (4f-ii-a's uncertainty sweep). Bounded by watched contacts with a resolved envelope, not by contact
  count, but it is the first time this project calls the primitive outside the perception gate. If a
  watched-heavy sortie shows poll-time growth, this is the first thing to measure.
- **Fail-open LOS and prompt duck-behind-ridge clearing are in tension** (4f-ii-a). A stale contact's
  uncertainty disc is wide enough that some sample stays clear, so the warning persists after you
  are actually masked. That is honest — he has lost sight of it and does not know you are safe — but
  a pilot may read it as the feature not working. Resolve it by letting uncertainty shrink with fresh
  observation, **not** by tightening the sample set.
- **The `OP_SRSAM` bucket has a ~4× internal range spread** (Decision 4c), so the class-level warning
  will often be wrong in magnitude until type-level recognition lands. Recorded against the buckets,
  not fixed here.
- **`_AIR_DEFENCE_OP_CLASSES` omits `OP_LRSAM`** — "watch nearest air defence" will not select an
  S-300. Pre-existing, not touched by this plan, and the implementer should not fix it silently: it
  may be deliberate (an S-300 is rarely the nearest thing that matters). **Raise it, do not patch
  it.**
- **`store.tick`'s signature widens twice** (`ownship`, `los_clear`). Every existing caller —
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
with a real band without any new data — and without the omniscience hazard that item warns about,
because `envelope_for` structurally cannot see ground truth. It also **narrows** the DCS-native
unit-database investigation from "needed" to "a provenance upgrade", since the belief-keyed lookup
shape would not change if better numbers arrived.

Two further effects, both new in this revision:

- **It makes the case for un-deferring the 9K113 concrete** (4d). The optic was shelved as *more
  detail*; the argument now is *identify the thing before it can shoot you*, and it is arithmetic
  rather than preference — only the 9K113's class multiplier reaches a SHORAD envelope's edge. Its
  multipliers are already measured and sitting in `perception/optics.py`'s docstring.
- **The `slots` migration (2b-i) pays forward.** Every future command that takes a parameter — and
  free-text targeting will take several — threads through one field instead of adding a wire column
  per command family. It is the last cheap moment to do it, with one slot in flight rather than four.

---

### Decisions — all three resolved by the user, 2026-09-24

Recorded rather than open, so a later reader does not reopen them.

1. **How `follow` picks a contact: neither "all" nor "nearest" — a best-match over optional
   qualifiers.** *"this really needs the brain so I can freetext tell which contact to follow. Let's
   approximate it by 'follow/watch [group/class/type] &lt;where o'clock&gt; &lt;distance&gt;' then
   find the closest match to it and watch that."* Designed in Decision 2b: parsed slots, a scored
   resolver, a match floor, and exactly one contact watched. **Explicitly a stopgap for the brain
   layer** — delete it when free text arrives, do not extend it. Type-level descriptors are dropped
   from the user's "group/class/type" as unenumerable in a closed grammar and almost never
   satisfiable at realistic recognition range (2b-ii).
2. **`follow` attaches to the contacts, not to the hour — confirmed** (2b-iv). The per-contact mark
   was the assumption and it is now the decision; it is also the only reading consistent with a
   best-match resolver, since descriptor and range qualifiers have no meaning for a region.
3. **The late danger warning is accepted, with a qualification that matters** (4d). *"useful for
   SHORAD, longer range SAM's can't be identified that far. Even for SHORAD, the 9K113 view is
   needed for identification at safe range."* So the feature targets SHORAD, the lateness against
   long-range SAMs is a fact about recognition rather than a defect here — and its practical value
   is **gated on the deferred 9K113 optic**, which is now recorded as the strongest argument for
   revisiting that deferral.

Also settled in passing: **the altitude floor compares against `OwnshipState.alt_agl_m`** (4f), and
**LOS is a precondition for radar tracking**, not a terrain nicety — which is what makes losing LOS
*clear* a standing warning (4f-ii).