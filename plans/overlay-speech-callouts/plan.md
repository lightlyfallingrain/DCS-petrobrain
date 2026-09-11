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
- **Urgent-call visual prominence.** `route_event` already marks an `UrgentCall`'s
  `OutgoingSpeech` with `urgency="critical"`/`bypass_gate=True`, but `TextOverlaySender`'s API
  (`clear()`/`addText()`, per `aircraft-layer/CLAUDE.md`) has no documented mechanism for visual
  distinction (color, bold, separate box) -- pushing it is a plain `push_text_line` call identical
  to a routine contact report. Should this milestone leave urgent calls visually identical to
  routine callouts (simplest, matches "the push mechanism today only supports one line of plain
  text"), or is a cheap text-only distinguishing marker (e.g. a `"!! "` prefix) worth adding now
  rather than waiting for a real prominence mechanism? Not answered here -- flagging per this
  role's instruction not to invent an answer not grounded in what's documented.
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
