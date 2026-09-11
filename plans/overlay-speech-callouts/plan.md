### Goal
Route `CrewConsole`'s spoken crew text (readbacks, contact reports, lifecycle-event lines, urgent
calls -- everything `belief.speech.OutgoingSpeech` produces) to the in-cockpit text overlay via
the existing `POST /text/push` channel, so the overlay reads as a radio callout feed (SRS
stand-in), verbatim what a crew member would actually say -- not the separate lifecycle-event
debug mirror that channel currently carries.

### Affected Modules / Files
- `body-layer/src/belief/crew_console.py` -- new `overlay_client: AircraftLayerClient | None =
  None` field on `CrewConsole` (mirrors `logger.ConsolePerceptionRunner.overlay_client`'s
  None-means-no-op pattern; deliberately **not** reusing the existing `aircraft_client` field,
  which BL-6 reserved for a different purpose -- live search-trigger commands -- per that field's
  own docstring). `_print` (called from both `handle_line` and `drain_events`, i.e. every path
  that produces spoken text) gains a second sink: after printing each line to `output`, push it to
  `overlay_client.push_text_line` if set, wrapped in its own `try/except AircraftLayerError`
  (log-and-continue), same degrade-on-failure shape as `ConsolePerceptionRunner.run_once`'s
  existing BL-2.5 push loop. This makes `_print` the single, already-tested point where "what to
  push and when" is decided -- it is exactly "every line `CrewConsole` already returns/prints,"
  no new selection logic to write or test.
- `body-layer/src/logger.py` -- relax the mutual-exclusivity check from `args.crew_text and
  (args.console or args.overlay)` to `args.crew_text and args.console` (only the two console UIs
  stay mutually exclusive; `--overlay` becomes valid with either). In the `--crew-text` branch of
  `main()`, wire `crew_console.overlay_client = aircraft_client if args.overlay else None` --
  exact mirror of the existing `--console` branch's `overlay_client=aircraft_client if
  args.overlay else None` wiring. Update `--overlay`'s and `--crew-text`'s `argparse` help text to
  describe the new combination instead of describing it as console-only/mutually exclusive.
- `body-layer/tests/test_crew_console.py` -- add a `FakeOverlayClient` test double (`pushed: list[str]`,
  optional `fail_on` set, mirroring `tests/test_logger.py`'s existing `FakeOverlayClient` almost
  exactly -- reuse that shape rather than inventing a new one) and tests asserting: a readback, a
  contact report, and a drained lifecycle/urgent-call event each push their exact `OutgoingSpeech.text`
  when `overlay_client` is set; nothing is pushed when it is `None` (existing tests, unchanged,
  already cover the no-op default); a failing push degrades to "no overlay line," does not raise,
  and does not stop the remaining lines in the same batch from being pushed/printed.
- `body-layer/CLAUDE.md` -- update the `crew_console.py` Structure entry and the "Running the live
  logger" `--overlay` note to describe the new `--crew-text --overlay` combination and what it
  pushes (spoken text, not the lifecycle mirror).
- No change to `body-layer/src/belief/speech.py`, `belief/console.py`'s `format_event_for_overlay`,
  or the `--console --overlay` path -- both existing mechanisms are left exactly as they are (see
  Decision below).

### Implementation Plan
1. Add `overlay_client` to `CrewConsole` and the push-on-`_print` logic; extend `_print`'s
   docstring to explain the new sink and why it lives here (single funnel point for all spoken
   text, not duplicated per call site).
2. Add `FakeOverlayClient` (or import/share the one in `test_logger.py` if it can be moved
   somewhere both test modules import from -- prefer a small local copy over a new shared test
   helper module, to match this project's existing per-test-file fixture convention) and the three
   test cases above.
3. Relax `logger.py`'s mutual-exclusivity check and wire `overlay_client` in the `--crew-text`
   branch of `main()`; update the two `argparse` help strings.
4. Update `body-layer/CLAUDE.md`'s `crew_console.py` Structure entry and `--overlay` running note.
5. Run body-layer's format/lint/type/test commands (`ruff format`, `ruff check`, `cd body-layer &&
   mypy src`, `pytest body-layer/tests -q`).
6. Live acceptance (user): run `--crew-text --overlay` against a live session (or at minimum
   confirm `--overlay`'s combination with `--console` is still unaffected), watch the overlay
   during a contact detection + a typed `watch`/`status` command + an `!inject-urgent` call, and
   confirm each shows the exact spoken text.

### Risks & Unknowns
- **Burst/last-wins is inherited, not solved here.** `TextOverlaySender`'s single-message mode
  (`clear()` + `addText()` per push) already meant BL-2.5's lifecycle mirror could push several
  events in one poll and leave only the last one visible; this feature inherits that exact
  characteristic for `CrewConsole`'s own bursts (e.g. two contact reports fired back-to-back by
  `drain_events`). Not a regression this plan introduces and not something in scope to fix (would
  need a queued/scrollback overlay, an aircraft-layer-side change) -- noted so it isn't mistaken
  for a new bug during live acceptance.
- **`!inject-urgent`'s pushed text is still the manual test-harness string**, not a real
  detector-driven call -- the overlay will show exactly what the operator typed after
  `!inject-urgent <id>`, same caveat `speech.py`'s own module docstring already carries.
- Live-acceptance-only: the actual overlay push call itself (`AircraftLayerClient.push_text_line`
  hitting a real DCS `POST /text/push`) is not unit-testable per this project's own testability
  convention; only the decision of what/when to push is.

### Decisions Requiring User Input
- **Urgent-call visual prominence -- resolved (user decision, 2026-09-11): add a text prefix
  marker.** `TextOverlaySender` has no color/bold mechanism, so the distinction is a plain text
  prefix -- e.g. `"!! "` -- prepended to the pushed line only when the source `OutgoingSpeech`
  carries `bypass_gate=True` (i.e. only the `UrgentCall` path, never a routine contact report or
  readback). Implementer: apply this at the `_print`-sink push call, not by mutating
  `OutgoingSpeech.text` itself (the non-overlay print path -- stdout/REPL -- stays unprefixed,
  since this is an overlay-display concern, not a change to what was spoken/printed generally).
- **Whether `format_event_for_overlay`'s `--console --overlay` mirror should eventually be
  retired in favor of a speech-based overlay everywhere**, once/if `belief.console.Console` (the
  developer debug REPL) ever grows its own speech-template path. Out of scope for this plan (the
  two consoles stay mutually exclusive with each other, so there is no live conflict today) --
  flagged only so a future architect session doesn't have to rediscover that two overlay-text
  conventions coexist deliberately, not by oversight.

### Second-Order Effects
Prepares BL-10 (SRS transport wiring, `ROADMAP.md`): once `CrewConsole`'s outbound text has a
single funnel point (`_print`) that already fans out to a second sink, swapping/adding a real SRS
TTS sink at BL-10 is a third sink on the same funnel rather than a new routing design -- this
milestone is effectively BL-10's dry run for "where does spoken text go" without committing to
voice synthesis yet.

### Invariant Check
- DCS stays authoritative / read-only: no DCS install or world-model data is touched; the overlay
  push is the same existing outbound `POST /text/push` write path aircraft-layer already exposes
  and BL-2.5 already proved live.
- Code owns facts, models interpret: unaffected -- this plan pushes text `belief.speech`'s
  body-written templates already produced; no model/brain involvement, no new interpretation
  layer.
- No provenance/uncertainty work needed here: `OutgoingSpeech` carries no provenance/timestamp
  fields to begin with (it is final rendered text, not a fact record), consistent with `speech.py`'s
  existing design.

---

## Addendum (2026-09-11): fix detection/reacquisition callout content

**Trigger.** Live acceptance of the routing mechanism above passed, but the user then found the
*content* wrong: `CONTACT_DETECTED`/`CONTACT_REACQUIRED` lines show as `"CONTACT_1
OP_GROUPSOMETHING."` -- `_render_lifecycle_text`'s own minimal template, which reads
`classification.get("value")` raw with no `_unit_type_display` mapping, no clock/range, no
enrichment. Same feature (what `CrewConsole` speaks), scope grows from "route existing speech" to
"also fix what two of those templates say." No new plan file per this project's convention for a
same-day follow-on to an in-flight feature.

**User's explicit format requirement (verbatim):** `"<unit type as far as is known>, <clock
direction>, <distance> [<world enrichment data>]"` -- e.g. `"truck, 2 o'clock, 1.5 km near road."`

### What already exists (read before designing, per this role's step 3a)

- `render_contact_report` already builds almost exactly this format (`"<COALITION> <unit type>,
  <clock> o'clock, <range>."`, via `_unit_type_display`/`_OP_CLASS_DISPLAY`) -- but it is a
  separate function from `_render_lifecycle_text`, which `route_event` calls for lifecycle kinds
  instead, and which never used it.
- `render_contact_report` does **not** currently append the `facts["semantic"]` enrichment
  fragment at all, even though it already accepts and threads an `EnrichmentContext` through to
  `describe_contact` -- the "near road" half of the user's requested format is missing from *both*
  the broken lifecycle template and the already-correct contact-report renderer. This is a real
  gap in the already-approved format, not something this addendum is introducing new scope by
  fixing.
- `belief.console.format_event_for_overlay` (the older lifecycle-mirror path, `belief/console.py`)
  already does exactly this pick: `max(semantic, key=lambda fact: fact["confidence"])`, appended as
  `" -- {best['text']}"`. Working precedent for *how* to pick the fragment; this addendum does not
  reuse its `" -- "` punctuation (see format below), since the user's own example has no dash.
- `render_contact_report` is already called from `crew_console._act` for the player-initiated
  `describe_contact` intent (`"status <id>"`/`"where is <id>"`) with **no id spoken** -- the player
  already named/resolved the contact in their own utterance, so speaking the id back would be
  redundant. This is the existing, working precedent that answers the "does the id need to be
  spoken" question below without needing to ask the user.

### Design

**1. Extract a shared, id-less formatting helper; both call sites reuse it.**
Add `_contact_report_text(facts: dict[str, object]) -> str` in `speech.py`, built from today's
`render_contact_report` body plus the missing enrichment fragment:
```
<COALITION> <unit type>[, <clock> o'clock, <range> km][ <best semantic fact text>].
```
(clock/range omitted when `relative_now` is absent, semantic fragment omitted when `facts["semantic"]`
is absent/empty -- both already this module's "absent, not null" convention.) `render_contact_report`
becomes a thin wrapper: call `describe_contact`, return `None` if not found, else
`OutgoingSpeech(text=_contact_report_text(result["facts"]), template="contact_report")` -- no
format-string duplication between the two call sites, per this role's reuse-over-duplication
default.

**2. Which lifecycle kinds get the full format.**
- **`CONTACT_DETECTED` and `CONTACT_REACQUIRED` -> full format**, prefixed with the contact id
  (see point 3): a contact newly visible or reappearing is exactly the moment a crew gives a full
  positional callout, and this is the user's own original example ("tank, 12 o'clock, 3 km").
- **`CONTACT_LOST` stays minimal** (`"{id} lost."`, unchanged): there is no current position to
  report -- a positional callout for a contact that just went out of view would be reporting stale
  data as if it were current, which is worse than the terse form.
- **`CONTACT_CLASSIFICATION_CHANGED` stays minimal** (`"{id} identified as {classification}."`,
  unchanged): it is an identification update on an already-known contact, not a new sighting: a
  full positional restatement every time confidence firms up (which can happen more than once per
  contact) would be spammy relative to what changed, and the player already has the contact's
  position from its original detection callout or a `status`/`where is` query.

**3. Contact id: spoken as a prefix, only for the two lifecycle kinds that gain the full format.**
`_contact_report_text`'s output itself never contains an id (matches `render_contact_report`'s
existing, already-live behaviour for player-initiated reports -- point above). For
`CONTACT_DETECTED`/`CONTACT_REACQUIRED`, `_render_lifecycle_text` prepends `f"{contact_id}: "`
before calling the shared helper, becoming e.g. `"CONTACT_1: UNKNOWN truck, 2 o'clock, 1.5 km near
a road (120m)."` -- the crew/brain still needs a way to refer back to this specific contact
(`watch CONTACT_1`, a later `status CONTACT_1`) the moment it is first announced, when the player
has not yet named it themselves. This is not left as an open decision: it follows directly from
the existing player-initiated-report precedent (id redundant when the player already named the
contact) plus the readback templates' own precedent of speaking ids (`"Watching {id}."`) when the
player has not already supplied one in the sentence being confirmed.

### Affected Modules / Files (in addition to the routing-mechanism list above)
- `body-layer/src/belief/speech.py` -- add `_contact_report_text`; `render_contact_report` becomes
  a thin wrapper over it; `_render_lifecycle_text`'s `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
  branches call the same helper with an id prefix instead of their own ad hoc string; `CONTACT_LOST`/
  `CONTACT_CLASSIFICATION_CHANGED` branches unchanged. Update the module docstring's "Contact
  report format" and "Which lifecycle kinds get a template" notes to describe the shared helper and
  the new detected/reacquired format instead of the old per-kind minimal lines.
- `body-layer/tests/test_speech.py` -- update the two `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
  assertions (currently asserting the old `"CONTACT_1 OP_GROUPSOMETHING."`-shaped text) to the new
  format; add a case covering the semantic-fragment append on both `render_contact_report` and the
  lifecycle path (reuse whatever fixture/fake `EnrichmentContext` the existing BL-3-enrichment
  speech tests already use, if any exist in this file -- otherwise a minimal fake matching
  `enrichment.py`'s `SemanticFact` shape). `CONTACT_LOST`/`CONTACT_CLASSIFICATION_CHANGED` tests
  unchanged.
- `body-layer/CLAUDE.md` -- update `speech.py`'s Structure entry: replace the "the runtime doc's
  literal 'C17 BMP'/'C17 lost'/'C17 reacquired' lines" description with the new split (full
  contact-report format + id prefix for detected/reacquired; minimal lines unchanged for
  lost/classification-changed), and note `render_contact_report`/`_render_lifecycle_text` now share
  `_contact_report_text`.

### Implementation Plan (addendum)
1. Add `_contact_report_text` (id-less, coalition + unit type + optional clock/range + optional
   semantic fragment + trailing period); have `render_contact_report` call it.
2. Update `_render_lifecycle_text`'s `CONTACT_DETECTED`/`CONTACT_REACQUIRED` branches to build
   `f"{contact_id}: {_contact_report_text(result['facts'])}"`; leave `CONTACT_LOST`/
   `CONTACT_CLASSIFICATION_CHANGED` branches untouched.
3. Update `test_speech.py`'s existing detected/reacquired assertions and add an enrichment-fragment
   case; update `render_contact_report`'s existing format tests only if `_contact_report_text`'s
   extraction changed anything observable for them (it should not -- same output, same call site).
4. Update `speech.py`'s module docstring and `body-layer/CLAUDE.md`'s `speech.py` Structure entry.
5. Run body-layer's format/lint/type/test commands (`ruff format`, `ruff check`,
   `cd body-layer && mypy src`, `pytest body-layer/tests -q`).
6. Live acceptance (user): trigger a `CONTACT_DETECTED` and a `CONTACT_REACQUIRED` in a live
   session (or replay) and confirm the spoken/overlay line reads as a proper radio callout with
   unit type, clock, range, and (when near a mapped feature) the enrichment fragment -- not the raw
   enum value.

### Risks & Unknowns (addendum)
- **Enrichment-fragment wording is a first-guess placeholder, same status `enrichment.py`'s own
  module docstring already carries** (`_FEATURE_CONFIDENCE_NUMERIC`, `_combined_confidence`) --
  this addendum consumes `SemanticFact.text` verbatim (e.g. `"near a road (120m)"`), it does not
  redesign that text's own phrasing.
- **No `EnrichmentContext` -> no fragment, silently.** A `CONTACT_DETECTED` fired before
  `logger.py`'s poll loop has built an `EnrichmentContext` (or with `--crew-text` run without
  `--world-model-db`-backed enrichment wired) still renders correctly, just without the enrichment
  clause -- same absent-not-null convention as the rest of this module, noted so it isn't mistaken
  for a bug during live acceptance if the very first detection in a session shows no enrichment
  fragment.
- **Coalition stays `"UNKNOWN"`** (module docstring's existing, separately-tracked backlog item) --
  unaffected by and out of scope for this addendum.

### Second-Order Effects (addendum)
Closes the gap between `render_contact_report`'s already-approved format and what lifecycle events
actually spoke, which was the last place `belief.speech` had two divergent phrasings for
"describe this contact's position." Any future BL-10 SRS/TTS work, or a brain-authored speech
class, now has exactly one place (`_contact_report_text`) that defines what a positional contact
callout sounds like, rather than needing to keep two templates in sync by hand.
