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

---

## Addendum 2 (2026-09-11): terser crew-text vocabulary; drop ids/coalition; two lifecycle formats

**Trigger.** Live-flown a third time. The routing mechanism and the detected/reacquired content
fix (Addendum 1) both hold, but the user now wants the crew-text *wording itself* pared down --
verbatim before/after examples:

```
CONTACT_5: UNKNOWN ground contact, 1 o'clock, 5.0 km near a road (439m).
  -> GROUND, 1 o'clock, 5 km, near road (~400m)
CONTACT_4 lost.
  -> <do not report contact lost>
CONTACT_26 identified as OP_INFANTRY.
  -> unit at <o'clock> <distance> is infantry
```

Stated principle: "The pilot needs terse and informative messages, no contact id's (can't keep
track of them). iff (not yet implemented though, so skip now), unit type (or group of if can tell
that yet), *where it is*."

### Scope confirmation: `belief.console.Console` is untouched

Re-read `belief.console.Console`/`format_event_for_overlay` (`body-layer/src/belief/console.py`)
against this feedback. `format_event_for_overlay` builds its line from `tools.describe_contact`'s
`summary` field and does **not** call `speech._unit_type_display`, `speech._contact_report_text`,
or any other symbol this addendum touches -- it is a fully separate rendering path, consumed only
by `logger.py`'s `--overlay` mirror when running with `--console` (not `--crew-text`). The user's
own framing confirms this split is intentional: "Console without --crew-text can print all the
data, but with --crew-text [it should be terser]." **This addendum's entire diff is scoped to
`belief/speech.py` (plus its tests and the `CLAUDE.md` Structure entry) -- `console.py` is not
touched and its debug output is unaffected.**

### What already exists (read before designing, per this role's step 3a)

- `_unit_type_display` (speech.py) is already private to this module -- `console.py`/
  `format_event_for_overlay` never import or call it, confirmed above. Its presence/unknown-level
  return strings can be reworded directly with zero effect on the debug console.
- `_contact_report_text` (added in Addendum 1) is already the single shared formatter behind both
  `render_contact_report` (player-initiated `status`/`where is <id>`, already id-less) and the two
  lifecycle branches that prepend an id. No second formatter exists yet for a "terser" variant --
  see the architecture-fork resolution below for whether one is needed.
- `SemanticFact` (`enrichment.py`) has no raw `distance_m` field -- only a pre-formatted `text`
  string (e.g. `"near a road (439m)"`, `"inside Anapa"`, built by `semantic_facts_for`). Rounding
  the embedded distance for crew-text without also rounding it in the (unaffected, per above)
  console/debug path means this addendum cannot change `enrichment.py`'s `text` construction --
  that field is shared state read by both `speech.py` and `console.py`.

### Design

**1. Drop the contact id from every spoken lifecycle/contact-report line.**
Addendum 1's `f"{contact_id}: "` prefix on `CONTACT_DETECTED`/`CONTACT_REACQUIRED` is removed --
that addendum's own reasoning ("the crew still needs a way to refer back to this specific
contact... when the player has not yet named it themselves") is explicitly overridden by this
feedback: the pilot cannot track `CONTACT_<n>` ids by ear, so speaking one is net noise, not help.
`_render_lifecycle_text`'s detected/reacquired branches call `_contact_report_text` directly, with
no prefix -- the same shape `render_contact_report` already uses. (The id still exists internally
and in the typed/console surfaces -- `watch <id>`, `status <id>`, the debug console -- this only
changes what is *spoken*. How a player refers back to an unnamed just-detected contact by voice
alone is a real BL-5-adjacent usability gap this addendum does not solve; noted under Risks, not
blocking.)

**2. `CONTACT_LOST` gets no template at all.**
`_render_lifecycle_text` returns `None` for `CONTACT_LOST`, exactly the existing
`CONTACT_ATTENTION_CHANGED` pattern the module docstring already documents ("returns `None`, not
acknowledged"). `route_event`'s structure already handles this correctly with no change needed:
`text = _render_lifecycle_text(...); if text is None: return None` runs *before*
`acknowledge_event` is called, so an unspoken `CONTACT_LOST` is also left unacknowledged --
consistent with "body only acknowledges what it actually spoke," not a special case.

**3. `CONTACT_CLASSIFICATION_CHANGED` gains a position, drops the raw enum.**
New format: `"unit at {clock} o'clock, {range} km is {unit type}."` (range clause omitted, same
absent-not-null convention, when `facts["relative_now"]` is absent -> `"unit is {unit type}."`).
Built from `facts["classification"]` via the *same* `_unit_type_display` helper
`_contact_report_text` already uses, replacing today's raw `event.classification` enum string
(`OP_INFANTRY` -> `infantry`, matching the user's own example). No semantic-fragment clause on
this line -- the user's example has none, and a classification update is about identity, not a
fresh scan of the surroundings; `_contact_report_text` (detected/reacquired, contact reports)
keeps the semantic fragment, this new classification-changed line does not.

**4. Drop the `"UNKNOWN"` coalition placeholder from `_contact_report_text` entirely.**
`_COALITION_PLACEHOLDER` is removed from the format string (`text = f"{_COALITION_PLACEHOLDER}
{unit_type}"` -> `text = unit_type`) -- no leading space, no orphaned punctuation, since
`unit_type` is simply the new first token. The constant itself is deleted (dead code once
unused) rather than kept around unused; when coalition inference is eventually built (existing
backlog item, module docstring's "Coalition is always UNKNOWN" note, unaffected by this addendum
otherwise), that work reintroduces a coalition token at that point, conditioned on actually having
one to say.

**5. Range and enrichment-distance rounding -- concrete rules (a local, reversible call per
AGENTS.md, not escalated).**
- **Range** (`facts["relative_now"]["range_m"]`, used by `_contact_report_text` and the new
  classification-changed line): round to the nearest 0.5 km, format without a trailing `.0`
  (`5.0 -> "5"`, `1.5 -> "1.5"`, matching the user's own `5.0 km -> 5 km` example while keeping
  useful precision at close range, where 500 m matters tactically and 1 km does not). New helper
  `_format_range_km(range_m: float) -> str`.
- **Enrichment distance** (the trailing `"(NNNm)"` inside a `SemanticFact.text`, e.g. `"near a
  road (439m)"`): round to the nearest 100 m, prefix with `~` (`439 -> "~400m"`, matching the
  user's example exactly). Since `SemanticFact.text` is pre-formatted and shared with the
  unaffected console path (see "What already exists" above), this is done by a small regex-based
  post-process in `speech.py` itself -- `_round_enrichment_fragment(text: str) -> str` matches a
  trailing `r"\((\d+)m\)$"`, rounds the captured number, and rewrites just that parenthetical (a
  `"near {name}"` fact with no trailing distance, e.g. `"inside Anapa"`, does not match and passes
  through unchanged). This keeps `enrichment.py`/`SemanticFact` completely untouched -- the
  regex is scoped to `speech.py`'s own consumption of an already-built string, not a new shared
  field. Documented as a real tradeoff under Risks: a future change to `semantic_facts_for`'s
  phrasing that alters the trailing-distance format would silently stop matching rather than error.

**6. Unit-type wording: normalize to lowercase, not the user's literal `"GROUND"` capitalization.**
Resolved directly (flagged here rather than left silent, since it is a visible cosmetic choice):
the user's own third example keeps `"infantry"` lowercase, and `_OP_CLASS_DISPLAY`'s existing
vocabulary (`"armor"`, `"truck"`, `"SAM"`... wait, `"SAM"`/`"AAA"` are already uppercase
initialisms) is mixed-case by necessity for acronyms but lowercase for words. Treating the user's
`"GROUND"` as emphasis in their own typed note rather than a deliberate spec, `_unit_type_display`'s
presence-level word becomes `"ground"` (was `"ground contact"`) and the level-unknown fallback
becomes `"contact"` (was `"unidentified contact"`) -- both lowercase, consistent with
`infantry`/`truck`/`armor` and with the initialism entries staying as-is (`SAM`/`AAA` are acronyms,
not a casing style choice). If the user actually wants presence-level contacts shouted in caps for
salience, that is a one-line revert, flagged here for confirmation rather than blocking.

**7. "Group of" / composition counts stay out of scope.**
Matches the module's existing, already-documented "No contact clustering" cut
(`docs/concept/PETROBRAIN_RUNTIME.md` line 336) -- the user's own phrasing ("if can tell that yet")
anticipates this is not yet buildable. No change needed to reconfirm this; noted so a future reader
sees it was checked again, not missed.

**8. Where the new terse formatting lives -- resolved: change the shared `_contact_report_text`
itself, not a second formatter.**
This is the addendum's one real architectural fork. Two options: (a) a second, lifecycle-only
"terse" builder, leaving `render_contact_report` (the player-typed `status <id>`/`where is <id>`
response) exactly as it was -- `"UNKNOWN ground contact, 1 o'clock, 5.0 km near a road (439m)."`;
or (b) apply items 1/4/5/6 to `_contact_report_text` itself, so every caller (both lifecycle kinds
*and* `render_contact_report`) gets the terser wording.

Chosen: **(b)**. Reasoning:
- The user's stated principle ("the pilot needs terse and informative messages") is general, not
  qualified to proactive narration only -- all three of their examples happen to be lifecycle
  lines, but nothing in the feedback singles out player-command responses as a case that should
  stay verbose, and a pilot who types `status CONTACT_5` mid-flight wants the terse answer just as
  much as one who hears it announced.
- Addendum 1 deliberately extracted `_contact_report_text` specifically to stop `render_
  contact_report` and the lifecycle branches from carrying two hand-synced phrasings of the same
  thing. Forking a second "terse" formatter now would reopen exactly that duplication one addendum
  later, for a distinction (proactive vs. player-queried) the user's feedback never draws.
- Item 1 (drop the id) already only affects the lifecycle branches structurally, since
  `render_contact_report` never spoke an id to begin with -- so choosing (b) does not make the two
  call sites *more* different in the id department, only more *alike* in wording (coalition,
  casing, rounding), which is a consistency improvement either way.

Flagged rather than silently assumed, per this role's step 8 instruction, since it does change the
previously-approved `render_contact_report` format for a case (`status <id>`) not covered by the
user's live examples -- easy to split back into two formatters later if the user finds the
player-queried response should stay more verbose.

### Affected Modules / Files (in addition to the two lists above)
- `body-layer/src/belief/speech.py` -- remove `_COALITION_PLACEHOLDER` and its use in
  `_contact_report_text`; reword `_unit_type_display`'s presence/fallback strings; add
  `_format_range_km` and `_round_enrichment_fragment`, and call both from `_contact_report_text`;
  remove the `f"{contact_id}: "` prefix from `_render_lifecycle_text`'s detected/reacquired
  branches; change `CONTACT_LOST`'s branch to `return None`; rewrite `CONTACT_CLASSIFICATION_
  CHANGED`'s branch to build the new `"unit at ... is ..."` line via `_unit_type_display` instead
  of `event.classification`. Update the module docstring's "Contact report format," "Which
  lifecycle kinds get a template," and "Coalition is always UNKNOWN" notes to describe the new
  id-less/coalition-less/rounded format and the `CONTACT_LOST`-has-no-template change.
- `body-layer/tests/test_speech.py` -- update every existing assertion that currently expects an
  id prefix, the `"UNKNOWN"` token, `"ground contact"`/`"unidentified contact"`, or an unrounded
  `X.0 km`/`(NNNm)` fragment; add a `CONTACT_LOST` case asserting `route_event` returns `None` and
  does **not** call `acknowledge_event` (mirroring however the existing `CONTACT_ATTENTION_CHANGED`
  test already asserts this, if one exists); replace the `CONTACT_CLASSIFICATION_CHANGED` test with
  one asserting the new `"unit at {clock} o'clock, {range} km is {type}."` shape, plus a no-
  `relative_now` case asserting the range clause is omitted; add rounding-boundary cases for
  `_format_range_km` (e.g. an exact `.25`/`.75` km input) and `_round_enrichment_fragment` (a
  distance-free fact text passes through unchanged).
- `body-layer/CLAUDE.md` -- update `speech.py`'s Structure entry: replace the coalition/`_unit_
  type_display` description with the id-less, coalition-less, rounded format; note `CONTACT_LOST`
  now has no template (joins `CONTACT_ATTENTION_CHANGED`); note `CONTACT_CLASSIFICATION_CHANGED`'s
  new position-bearing format; note that `render_contact_report`'s player-command-response format
  changed identically (Design point 8's resolved fork), not just the lifecycle lines.

### Implementation Plan (addendum 2)
1. Remove `_COALITION_PLACEHOLDER` and its use; reword `_unit_type_display`'s two generic-word
   returns.
2. Add `_format_range_km` and `_round_enrichment_fragment`; wire both into `_contact_report_text`
   (range formatting call site, and the semantic-fragment append call site).
3. Strip the id prefix from `_render_lifecycle_text`'s detected/reacquired branches; change
   `CONTACT_LOST` to `return None`; rewrite `CONTACT_CLASSIFICATION_CHANGED` to the new
   position-bearing line via `_unit_type_display`.
4. Update `test_speech.py` per the Affected Modules note above.
5. Update `speech.py`'s module docstring and `body-layer/CLAUDE.md`'s `speech.py` Structure entry.
6. Run body-layer's format/lint/type/test commands (`ruff format`, `ruff check`,
   `cd body-layer && mypy src`, `pytest body-layer/tests -q`).
7. Live acceptance (user): trigger a detection, a loss, and a classification change in one session;
   confirm no id/coalition is spoken, ranges/distances read as rounded, the lost event produces no
   line at all, and the classification line reads as `"unit at <clock> o'clock, <range> km is
   <type>."`.

### Risks & Unknowns (addendum 2)
- **How a player refers back to a just-announced, now-unnamed contact by voice** is a real gap
  this addendum opens (item 1) and does not close -- typed/console reference by id still works,
  spoken natural reference (`"watch that"`) depends on `utterance.py`'s existing filler-stripping +
  `find_contact` resolution already covering "the thing just mentioned," which has not been
  verified against this exact new no-id-spoken scenario. Flag for live testing, not a blocker for
  this addendum's own scope.
- **`_round_enrichment_fragment`'s regex is coupled to `semantic_facts_for`'s current trailing-
  distance phrasing** (`"(NNNm)"`) -- a future rewording of that text (still allowed, since
  `enrichment.py` itself is untouched by this addendum) would silently stop matching rather than
  raise, degrading to the unrounded original text. Acceptable now; worth a shared-field revisit
  (`SemanticFact.distance_m`) if `enrichment.py` phrasing churns later.
- **`render_contact_report`'s format change (Design point 8)** affects the player-typed
  `status`/`where is` response the same way it affects lifecycle lines -- flagged as a resolved-
  but-overridable call, not silently assumed; easy to revert to a two-formatter split if the user
  wants the player-queried response to stay more verbose than proactive narration.
- **Casing convention (Design point 6)** is a resolved-but-flagged cosmetic call (lowercase
  `"ground"`/`"contact"`, not the user's literal `"GROUND"`) -- one-line revert if wrong.

### Decisions Requiring User Input (addendum 2, resolved-but-flagged, not blocking)
- Item 6: lowercase `"ground"`/`"contact"` vocabulary vs. the user's literal `"GROUND"` caps --
  resolved toward lowercase for cross-vocabulary consistency; flagged for override.
- Item 8: applying the terser format to `render_contact_report` (player `status`/`where is`
  responses) as well as lifecycle lines, not just the three lifecycle examples given -- resolved
  toward applying it everywhere `_contact_report_text` is used; flagged since the live examples
  did not cover this call site.

### Second-Order Effects (addendum 2)
Removing the id from spoken lifecycle lines widens the gap between "what body can say" and "what a
player can say back" -- BL-5's natural-reference resolution (pronoun/last-mentioned-contact
handling in `utterance.py`) goes from a nice-to-have to something the crew-text loop actually
depends on for a normal conversational flow ("what's that... watch it"), which the current
`find_contact`-after-filler-stripping mechanism was not explicitly designed against this scenario.
