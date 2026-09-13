### Implementation Summary

Implemented BL-7 as locked in `plans/bl7-mission-phase-relevance/plan.md` (commit `e45cbc9`) on
`feature/bl7-mission-phase-relevance`. No new `TOOL_SET` entry -- mission phase folds into
`get_situation`'s facts payload, exactly per the plan's "Stale-flag resolution" decision.
`mission_phase.py` hand-parses MI-6's `--emit-compact` JSON as a plain file read/JSON parse
(verified the real `dataclasses.asdict()` shape by round-tripping a constructed
`RuntimeMissionUnderstanding` through mission-interpreter's own venv before writing the fixture and
parser, rather than guessing the envelope shape from the plan's prose alone).

### Files Changed
- `body-layer/src/belief/mission_phase.py` (new) -- `CompactRoutePoint`/`MissionPhaseInfo` (local
  Tagged-envelope mirrors, carrying `epistemic_status`/`basis`), `MissionUnderstandingData`
  (phases sorted ascending, defensively), `load_mission_understanding` (raises `ValueError` on any
  missing/malformed field; empty `phases`/`route` lists are valid), `MissionPhaseTracker`
  (`update`/`current_phase`), `mission_phase_relevance`, `WAYPOINT_CAPTURE_RADIUS_M` (placeholder,
  3000.0m). Distance math reuses `perception.geometry.range_m` (never reimplemented inline) --
  route points carry no altitude, so the target is placed at the observer's own altitude for the
  distance check, collapsing the vertical component.
- `body-layer/src/belief/tools.py` -- `_select_from_tier` (new): within an already-chosen attention
  tier, mission-phase relevance (ascending) breaks ties before `last_seen_sim`, but only when a
  relevance value is available for every candidate in that tier; otherwise falls back to the
  original `last_seen_sim`-only rule unchanged. `_highest_attention_contact` gained an optional
  `mission_phase_tracker` parameter, threaded to `_select_from_tier` for each tier. `get_situation`
  gained an optional `mission_phase_tracker` parameter: `facts["mission_phase"]` is **absent**
  entirely when no tracker is supplied, present-but-`None` when a tracker is loaded but no phase is
  active yet, and the phase name string once one is active -- the same absent-not-empty convention
  this module already uses for `enrichment`-gated facts. Summary line gets a `"Phase: <name>."`
  fragment only when a phase is active.
- `body-layer/src/belief/console.py` -- `Console.mission_phase_tracker: MissionPhaseTracker | None
  = None` field, threaded through `_dispatch`/`_handle_situation` into `tools.get_situation`. Not
  explicitly named in the plan's "Affected Modules" file list, but required by its own wiring
  instruction ("threaded through to wherever `EnrichmentContext` is already threaded... the
  `--console` poll loop and the REPL") -- `get_situation` has no other caller, so this file had to
  change for the feature to be reachable at all.
- `body-layer/src/logger.py` -- new `--mission-understanding PATH` CLI flag (optional, default
  `None`). `main()` loads it once via `load_mission_understanding` and builds one
  `MissionPhaseTracker` **on the main thread, before either poll thread starts** -- unlike
  `sources`/`world_model_conn`, this is a plain JSON file load with no sqlite connection, so there
  is no thread-affinity reason to defer construction to the poll thread. The same tracker instance
  is passed into `ConsolePerceptionRunner` (both `--console` and `--crew-text` branches) and into
  `Console` for `--console`. `ConsolePerceptionRunner.run_once` calls `.update()` on it every poll
  (the only mutation site, poll thread); `Console`'s `situation` command only ever calls
  `.current_phase()` (REPL thread, read-only) -- the same write-thread/read-thread split
  `EnrichmentContext.ownship`/`last_t_sim` already use, deliberately followed rather than
  reinventing synchronization, per the plan's explicit callout of this codebase's recurring sqlite
  thread-affinity defect class (BL-2 Stage 6, BL-5). Because the tracker is built once up front (not
  lazily per-poll like `EnrichmentContext`), `Console` only needs the reference set once at
  construction -- no per-command resync was needed, unlike `enrichment`'s lazy-rebuild dance.
- `body-layer/src/belief/tool_api.py` -- one sentence added to the module docstring recording the
  "no new tool, folded into `get_situation`" decision. `TOOL_SET` itself unchanged.
- `body-layer/tests/test_mission_phase.py` (new), `body-layer/tests/fixtures/
  mission_understanding_sample.json` (new) -- see Tests Added.
- `body-layer/tests/test_tools.py` -- extended for `get_situation`'s three `mission_phase` states
  (absent/null/active) and `_highest_attention_contact`'s tie-break (with/without an active phase).
- `body-layer/tests/test_logger.py` -- extended for `ConsolePerceptionRunner.run_once` calling
  `mission_phase_tracker.update()` on every poll, and no-op behavior when the tracker is `None`.
- `body-layer/tests/test_console.py` -- extended for `Console`'s `situation` command surfacing an
  active phase's name in the summary.

### Tests Added
- `test_mission_phase.py` (15 tests) -- fixture parsing (valid, sorts-if-unsorted, empty
  phases/route degrade to `current_phase() is None`, raises `ValueError` on missing/malformed
  fields); `MissionPhaseTracker.update` walking a route (advance, monotonic non-decrement, advances
  past a skipped intermediate waypoint in one poll, does not advance outside the capture radius);
  `mission_phase_relevance` (no active phase -> `None`, distance to active phase's waypoint,
  waypoint not in route -> `None`); `MissionUnderstandingData` frozen-dataclass check.
- `test_tools.py` -- `get_situation`: fact absent without a tracker, present-but-`None` before the
  first waypoint, phase name once active (plus matching summary fragments).
  `_highest_attention_contact`: falls back to recency without a tracker; breaks ties by mission-phase
  proximity over recency when both candidates have a relevance value; falls back to recency when no
  phase is active (relevance unavailable for either candidate).
- `test_logger.py` -- `ConsolePerceptionRunner.run_once` advances a configured tracker's
  `last_reached_waypoint_index` using ownship's telemetry position; a `None` tracker is untouched
  (stays `None`, no exception).
- `test_console.py` -- `situation` command's summary includes `"Phase: <name>."` when
  `Console.mission_phase_tracker` reports an active phase.

### Checks
`body-layer/`:
- ruff format --check: pass
- ruff check: pass (7 `TRY004` findings in `mission_phase.py` suppressed with `# noqa: TRY004` --
  the isinstance checks there validate untrusted external JSON content, not Python call-site type
  contracts, so `ValueError` is the semantically correct exception per the plan's explicit
  "raises a plain `ValueError`" instruction; no existing `# noqa` precedent existed in this
  codebase, so this is a new but narrowly-scoped suppression, not a config-wide rule change)
- mypy src (strict): pass
- pytest tests -q: pass (475 passed, up from 466 before this milestone)
- `test_mock_flight_chain.py` re-verified passing unchanged, per the plan's Stage 4 instruction

### Notable Discoveries
- Confirmed the exact `dataclasses.asdict()` JSON shape of `RuntimeMissionUnderstanding` by
  constructing one in mission-interpreter's own venv and dumping it, rather than trusting the
  plan's prose description of the `Tagged` envelope alone -- worth doing for any future
  cross-subproject JSON-artifact consumer, since a hand-guessed envelope shape is exactly the kind
  of thing that would silently diverge from the real producer.
- `get_situation` has exactly one caller (`console.py`'s `situation` command) -- `CrewConsole`
  never calls it, so BL-7's user-facing surface is deliberately narrower than "every console" would
  suggest; `--crew-text`'s poll loop still advances the shared `MissionPhaseTracker` (harmless,
  keeps future BL-8/PB-9 consumers correctly synced) even though nothing reads it on that path yet.
- `MissionPhaseTracker`'s "read-only from the REPL thread" requirement turned out to need no new
  synchronization primitive at all: because the tracker is built once (not lazily re-built per poll
  the way `EnrichmentContext` is), the same Python object reference threaded to `Console` at
  startup stays valid and current for the whole session -- mutation is visible across threads
  without any explicit hand-off step, unlike `enrichment`'s lazy first-build dance.
