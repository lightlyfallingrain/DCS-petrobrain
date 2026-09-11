### Implementation Summary

Wired `CrewConsole`'s spoken crew text (readbacks, contact reports, drained lifecycle events,
injected urgent calls) to the in-cockpit text overlay via the existing `POST /text/push` channel,
as a second sink alongside the existing `output` print sink -- both funneled through `_print`, the
one place every line `CrewConsole` produces already passes through. Urgent (`bypass_gate=True`)
lines get a `"!! "` prefix on the pushed overlay copy only, per the plan's resolved decision;
`output`'s printed copy is untouched. `logger.py`'s `--crew-text`/`--console` mutual-exclusivity
check was relaxed so `--overlay` combines with either.

### Files Changed
- `body-layer/src/belief/crew_console.py` -- added `overlay_client: AircraftLayerClient | None =
  None` field (deliberately separate from the existing `aircraft_client` field, which BL-6
  reserved for live search-trigger commands). `_print` now takes a `bypass_gate: bool = False`
  parameter and, when `overlay_client` is set, pushes each line via `push_text_line` in its own
  `try/except AircraftLayerError` (log-and-continue), prefixing `"!! "` only on the pushed copy
  when `bypass_gate` is True. `handle_line` and `drain_events` pass `bypass_gate` through to
  `_print`. `_handle_inject_urgent`'s return type changed from `list[str]` to
  `tuple[list[str], bool]` so the caller learns whether the produced line actually carried
  `bypass_gate=True` (read straight off `route_event`'s `OutgoingSpeech.bypass_gate` rather than
  re-deriving it) -- this is a private method, not called directly by any existing test, so the
  signature change is safe. `drain_events` always passes `bypass_gate=False` since a lifecycle
  `Event` (unlike an injected `UrgentCall`) never sets that flag.
- `body-layer/src/logger.py` -- relaxed the mutual-exclusivity check from
  `args.crew_text and (args.console or args.overlay)` to `args.crew_text and args.console`. Wired
  `overlay_client=aircraft_client if args.overlay else None` into the `--crew-text` branch's
  `CrewConsole(...)` construction, mirroring the existing `--console` branch's identical
  `ConsolePerceptionRunner(overlay_client=...)` wiring. Updated the `--overlay` and `--crew-text`
  argparse help strings and the module docstring's `--overlay`/`--crew-text` sections to describe
  the new combination.
- `body-layer/tests/test_crew_console.py` -- added a local `FakeOverlayClient` test double (a
  small copy of `test_logger.py`'s own, per this project's per-test-file fixture convention, not a
  new shared helper module) and eight new tests covering: no-op when `overlay_client` is unset
  (explicit assertion of the existing default); a readback pushes; a contact report pushes; a
  drained lifecycle event pushes; an urgent call pushes with the `"!! "` prefix while the printed
  copy stays unprefixed; the inject-urgent usage-error message (not itself urgent) is pushed
  without the prefix; and a failing push degrades without raising and does not block a later,
  unrelated push in a subsequent call.
- `body-layer/CLAUDE.md` -- updated the "Running the live logger" `--overlay` note and the
  `crew_console.py` Structure entry to describe the new `--crew-text --overlay` combination
  (pushes spoken text verbatim, not the lifecycle-event mirror `--console --overlay` uses) and the
  `overlay_client` field/`_print` push logic.

### Tests Added
- `test_no_overlay_push_when_overlay_client_is_unset` -- explicit no-op assertion for the default.
- `test_readback_pushes_to_overlay` -- a `watch <id>` readback's exact text is pushed.
- `test_contact_report_pushes_to_overlay` -- a `status <id>` contact report's exact text is pushed.
- `test_drained_lifecycle_event_pushes_to_overlay` -- a `drain_events`-produced lifecycle line is
  pushed.
- `test_urgent_call_pushes_to_overlay_with_prefix_but_prints_unprefixed` -- `!inject-urgent`'s
  urgent call is pushed with `"!! "` prepended while `output`'s printed copy stays unprefixed.
- `test_inject_urgent_usage_message_is_not_prefixed_when_pushed` -- the usage-error message (not
  a real urgent call, `bypass_gate=False`) is pushed without the prefix.
- `test_failed_overlay_push_degrades_without_raising_and_does_not_block_remaining_lines` -- a push
  that raises `AircraftLayerError` degrades silently (nothing recorded, no exception propagates)
  and does not disable the sink for a later push in a subsequent call.

### Checks
(body-layer/)
- ruff format --check: pass
- ruff check: pass
- mypy src (via `cd body-layer && mypy src`): pass, no issues in 29 source files
- pytest -q: pass, 444 passed

### Notable Discoveries
- `_handle_inject_urgent`'s original `list[str]` return already collapsed away the
  `OutgoingSpeech.bypass_gate` flag `route_event` produces -- the only way to know a pushed line
  was actually an urgent call (versus the harness's own usage-error string) was to widen this
  private method's return type to carry the flag through, rather than re-deriving "was this
  urgent" from string content at the `_print` call site.
- `route_event` always returns a non-`None` `OutgoingSpeech` for an `UrgentCall` input (only the
  `Event` branch can return `None`, for an unknown contact) -- confirmed by reading `speech.py`
  directly rather than assuming, since `_handle_inject_urgent` needed to handle a hypothetical
  `None` case correctly regardless.
- No new files were created this milestone (only edits to `crew_console.py`, `logger.py`,
  `test_crew_console.py`, `CLAUDE.md`), so there was nothing beyond the ordinary staged edits.
- Live acceptance (the actual `POST /text/push` call against a running aircraft-layer/DCS session)
  is out of this milestone's automated-test scope per the plan and is left to the user, per this
  project's execution-boundary convention for live/full DCS runs.
