---
name: project_bl7_mission_phase
description: BL-7 mission-phase tracking implementation facts (compact-artifact shape, tie-break wiring, thread split)
metadata:
  type: project
---

BL-7 (`plans/bl7-mission-phase-relevance/plan.md`) implemented on
`feature/bl7-mission-phase-relevance`, 2026-09-13.

- No new `TOOL_SET` entry -- `get_situation` gained `facts["mission_phase"]` instead (absent when
  no tracker, `None` before first waypoint, phase name once active -- absent-not-empty convention).
- `mission_phase.py` hand-parses MI-6's `--emit-compact` JSON (file read only, never a Python
  import of mission-interpreter). Verified the real `dataclasses.asdict()` envelope shape by
  constructing a `RuntimeMissionUnderstanding` in mission-interpreter's own venv and dumping it,
  rather than trusting the plan's prose description alone -- do this for any future
  cross-subproject JSON-artifact consumer.
- `get_situation` has exactly one caller: `console.py`'s `situation` command. `CrewConsole` never
  calls it -- BL-7's tracker is still advanced on the `--crew-text` poll path (harmless, keeps
  future BL-8/PB-9 consumers synced) but nothing reads it there yet.
- `Console.mission_phase_tracker`/`ConsolePerceptionRunner.mission_phase_tracker` needed no new
  cross-thread synchronization: unlike `EnrichmentContext` (lazily rebuilt per poll, thread-affine
  sqlite connection), `MissionPhaseTracker` is a plain object built once in `main()` before either
  poll thread starts and shared by reference -- poll thread only calls `.update()`, REPL thread
  only calls `.current_phase()`. This is the same write/read split as `last_t_sim`, not the
  "rebuild per-thread" pattern Stage 6/BL-5 needed for sqlite connections.
- `get_situation`/`Console` needed edits even though the plan's "Affected Modules" file list didn't
  name `console.py` explicitly -- its own wiring instruction ("threaded through to wherever
  EnrichmentContext is already threaded... the REPL") required it, since `get_situation` has no
  other caller.
- Tie-break (`_select_from_tier` in `tools.py`): mission-phase relevance ascending wins over
  `last_seen_sim`, but only when a relevance value is available for every candidate in the tier
  (uses a `for/else` over the candidate list to detect "any candidate has no relevance" and fall
  back cleanly).
- Ruff's `TRY004` (prefers `TypeError` for `isinstance` failures) fired 7x in the JSON-validation
  parser -- suppressed with `# noqa: TRY004` per site, since these validate untrusted external
  JSON content (correctly `ValueError` per the plan's explicit instruction), not Python call-site
  type contracts. No prior `# noqa` existed anywhere in body-layer; this is a narrow, justified
  first use, not a precedent for reaching for noqa generally.
