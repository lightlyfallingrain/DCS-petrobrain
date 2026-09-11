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

---

## Addendum implementation (2026-09-11): fix CONTACT_DETECTED/REACQUIRED lifecycle-event content

### Implementation Summary
Extracted `_contact_report_text(facts)` in `belief/speech.py` -- an id-less helper building
`"<COALITION> <unit type>[, <clock> o'clock, <range> km][ <best semantic fact text>]."` from a
`describe_contact` result's `facts` dict. `render_contact_report` is now a thin wrapper over it
(unchanged output for existing callers/tests, verified). `_render_lifecycle_text`'s
`CONTACT_DETECTED`/`CONTACT_REACQUIRED` branches now call the same helper and prepend
`f"{contact_id}: "`, replacing the old raw-enum-value template
(`f"{contact_id} {classification.get('value')}."`). `CONTACT_LOST`/`CONTACT_CLASSIFICATION_CHANGED`
branches are untouched, per the addendum's explicit design.

The semantic-fragment selection (`max(semantic, key=lambda fact: fact["confidence"])`) mirrors
`belief.console.format_event_for_overlay`'s existing logic exactly, reading `facts["semantic"]`
(a `list[dict]` from `asdict(SemanticFact)`, same shape `tools.py`/`console.py` already consume).

### Files Changed
- `body-layer/src/belief/speech.py` -- added `_contact_report_text`; `render_contact_report`
  delegates to it; `_render_lifecycle_text`'s `CONTACT_DETECTED`/`CONTACT_REACQUIRED` branches
  build `f"{contact_id}: {_contact_report_text(result['facts'])}"` instead of their own ad hoc
  string. Updated the module docstring's "Which lifecycle kinds get a template" and "Contact
  report format" notes to describe the shared helper, the semantic fragment, and the new
  detected/reacquired format.
- `body-layer/tests/test_speech.py` -- added a local `_enrichment_context` fixture (mirroring
  `test_console.py`'s own fake `describe_position`/`project_terrain_aware` monkeypatches and fake
  dataclasses, since this module had none of its own and per-test-file fixtures are this project's
  convention). Updated `test_route_event_contact_detected_renders_id_and_classification` and
  `test_route_event_contact_lost_and_reacquired`'s reacquired assertion to the new
  `"{id}: UNKNOWN {type}."` format. Added
  `test_route_event_contact_detected_includes_clock_range_when_enriched` and
  `test_render_contact_report_includes_semantic_fragment_when_enriched` covering the new
  enrichment-fragment append on both call sites.
- `body-layer/tests/test_crew_console.py` -- updated two pre-existing assertions
  (`test_scripted_crew_session_reproduces_the_first_useful_success_criterion`'s detected and
  reacquired lines, and `test_failed_overlay_push_degrades_without_raising_and_does_not_block_
  remaining_lines`'s `detected_line`) from the old `f"{contact_id} BMP-2."` to the new
  `f"{contact_id}: UNKNOWN BMP-2."` -- not in the addendum's own Affected Modules list, but their
  assertions encoded the exact broken output this addendum fixes, so they failed until updated
  (a genuine full-suite regression catch, not a rewrite of test intent).
- `body-layer/CLAUDE.md` -- updated `speech.py`'s Structure entry: replaced the old literal
  "C17 BMP"/"C17 lost"/"C17 reacquired" description with the new split (full callout format +
  id prefix for detected/reacquired via the shared helper; minimal, unextended lines for
  lost/classification-changed) and documented the semantic-fragment source.

### Tests Added
- `test_route_event_contact_detected_includes_clock_range_when_enriched` -- an enriched
  `CONTACT_DETECTED` includes clock/range and the semantic fragment ("Jableh").
- `test_render_contact_report_includes_semantic_fragment_when_enriched` -- `render_contact_report`
  itself also gains the semantic fragment when enriched (previously missing from both call sites,
  per the addendum's "What already exists" note).

### Checks
(body-layer/)
- ruff format --check: pass
- ruff check: pass
- mypy src (via `cd body-layer && mypy src`): pass, no issues in 29 source files
- pytest -q: pass, 446 passed

### Notable Discoveries
- The addendum's own Affected Modules list did not name `test_crew_console.py`, but running the
  full suite (not just the addendum's named test file) surfaced two pre-existing tests whose
  assertions were pinned to the exact broken `_render_lifecycle_text` output being fixed here --
  confirms this project's "verify full suite, not just new files" convention held real value on
  this task.
- `render_contact_report`'s pre-addendum tests (`test_render_contact_report_follows_coalition_
  unit_type_clock_range_format`, `test_render_contact_report_maps_op_class_to_display_word`) needed
  no changes -- confirms the `_contact_report_text` extraction is a pure refactor with identical
  output for the existing no-enrichment call path, as the addendum's design predicted.

---

## Addendum 2 implementation (2026-09-11): terser crew-text vocabulary

### Files Changed
- `body-layer/src/belief/speech.py` -- removed `_COALITION_PLACEHOLDER` and its use in
  `_contact_report_text` (unit type is now the first token, no leading placeholder/space);
  reworded `_unit_type_display`'s presence/unknown fallbacks from `"ground contact"`/
  `"unidentified contact"` to `"ground"`/`"contact"`; added `_format_range_km` (rounds to the
  nearest 0.5 km, no trailing `.0`, `f"{range_km:g}"` for the non-integer case) and
  `_round_enrichment_fragment` (regex `r"\((\d+)m\)$"` against a `SemanticFact.text` fragment,
  rounds the captured metres to the nearest 100 and rewrites the parenthetical with a `~` prefix;
  text with no trailing distance passes through unchanged); both are now called from
  `_contact_report_text`'s range and semantic-fragment append sites. `_render_lifecycle_text`'s
  `CONTACT_DETECTED`/`CONTACT_REACQUIRED` branches now call `_contact_report_text` directly with
  no `f"{contact_id}: "` prefix (removed per this addendum, explicitly overriding Addendum 1's own
  reasoning). `CONTACT_LOST`'s branch now returns `None` (joins `CONTACT_ATTENTION_CHANGED`'s
  no-template pattern -- `route_event`'s existing `if text is None: return None` ordering already
  handles leaving it unacknowledged, no structural change needed there). `CONTACT_CLASSIFICATION_
  CHANGED`'s branch was rewritten to build `"unit at {clock} o'clock, {range} km is {unit type}."`
  (or `"unit is {unit type}."` with no `relative_now`) from `result["facts"]["classification"]` via
  `_unit_type_display`, replacing the old raw-enum `event.classification` string. Module docstring's
  "Which lifecycle kinds get a template" and "Contact report format" sections rewritten to match;
  the "Coalition is always UNKNOWN" section replaced with a "No coalition token" section describing
  the removal and the still-deferred inference backlog item.
- `body-layer/tests/test_speech.py` -- updated every assertion that expected the id prefix, the
  `"UNKNOWN"` token, or the old `"ground contact"`/`"unidentified contact"` wording. Split the old
  `test_route_event_contact_lost_and_reacquired` into
  `test_route_event_contact_lost_has_no_template_and_is_not_acknowledged` (mirrors the existing
  `CONTACT_ATTENTION_CHANGED` no-template test's shape) and
  `test_route_event_contact_reacquired_renders_classification_with_no_id`. Added
  `test_route_event_classification_changed_speaks_position_and_new_type` (enriched) and
  `..._omits_range_when_not_enriched`, plus `_store_with_a_classification_change` (a small shared
  builder: ingest at `classification_level=2`, then a refining observation at `level=3`, mirroring
  `test_console.py`'s existing `test_format_event_for_overlay_renders_classification_transition`
  fixture shape). Added `test_format_range_km_rounds_to_nearest_half_km_no_trailing_zero`,
  `test_format_range_km_boundary_cases`, `test_round_enrichment_fragment_rounds_trailing_distance`,
  and `..._passes_through_text_without_distance` for the two new rounding helpers, importing them
  directly (`_format_range_km`, `_round_enrichment_fragment`) since they are private module
  functions with no public wrapper worth adding just for testability. Extended `_observation`'s
  fixture with an optional `classification_level` parameter (previously hardcoded to `2`) to build
  the classification-transition fixtures.
- `body-layer/tests/test_crew_console.py` -- updated the scripted-session acceptance test's
  detected/reacquired-line assertions (`"BMP-2."` instead of `f"{contact_id}: UNKNOWN BMP-2."`) and
  its lost-line assertion (now asserts `drain_events` returns `[]` for the lost tick, instead of
  checking for a `"{id} lost."` line); updated `test_failed_overlay_push_degrades_...`'s
  `detected_line` fixture the same way.
- `body-layer/CLAUDE.md` -- rewrote `speech.py`'s Structure entry to describe the id-less,
  coalition-less format, `CONTACT_LOST`'s new no-template status, `CONTACT_CLASSIFICATION_CHANGED`'s
  new position-bearing line, and the two rounding helpers.

### Tests Added
- `test_route_event_contact_lost_has_no_template_and_is_not_acknowledged` -- `CONTACT_LOST` speaks
  nothing and stays unacknowledged.
- `test_route_event_classification_changed_speaks_position_and_new_type` /
  `..._omits_range_when_not_enriched` -- the new position-bearing classification-changed line, with
  and without an `EnrichmentContext`.
- `test_format_range_km_rounds_to_nearest_half_km_no_trailing_zero` /
  `test_format_range_km_boundary_cases` -- `_format_range_km`'s rounding, including the two exact
  0.5 km tie-boundary inputs (`1250.0`, `1750.0`) pinned to Python's actual `round()` (ties-to-even)
  output (`"1"`, `"2"`) rather than a guessed convention.
- `test_round_enrichment_fragment_rounds_trailing_distance` /
  `..._passes_through_text_without_distance` -- `_round_enrichment_fragment`'s rounding (including
  the `450m` tie-boundary, pinned to `"~400m"`) and its no-op pass-through for distance-free text.

### Checks
(body-layer/)
- ruff format --check: pass
- ruff check: pass
- mypy src (via `cd body-layer && mypy src`): pass, no issues in 29 source files
- pytest -q: pass, 453 passed

### Notable Discoveries
- `_format_range_km`/`_round_enrichment_fragment`'s exact tie-boundary values (1250 m, 1750 m,
  450 m) all land on Python's `round()` ties-to-even behaviour rather than the more intuitive
  round-half-up; the plan's own risk note flagged this as unspecified, so the boundary tests assert
  the actual computed values (documented inline) rather than a guessed convention -- worth
  revisiting if a live-acceptance session finds the tie behaviour surprising in practice (e.g. a
  contact at exactly 1750 m reads "2 km" while one at exactly 1250 m reads "1 km", not obviously
  symmetric to a listener).
- `CONTACT_CLASSIFICATION_CHANGED`'s new line reads `result["facts"]["relative_now"]` for
  clock/range, which (per `tools.py`'s existing behaviour) is only present when an
  `EnrichmentContext` is supplied to `route_event` -- confirmed by writing both an enriched and an
  unenriched test rather than assuming the enriched case always applies live.
