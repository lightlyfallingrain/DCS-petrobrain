### Implementation Summary

Stages 0-5 (branch, Stage 1 `belief/attention.py` relative-sector geometry, Stage 2
`belief/contacts.py` `add_area`/`reproject_relative_areas`, Stage 3 `logger.py` tick wiring, Stage 4
`belief/tools.py` `scan_area`/`watch_area` `relative_sector` params, Stage 5 Hook Lua + `ALLOWED_COMMANDS`)
were already done and committed before this session (`e023a6a` + plan commit). This session
implemented **Stage 6** (`belief/crew_console.py` dispatch) and **Stage 7** (docs), plus the test
coverage Stages 1-5 had not added.

### Files Changed
- `body-layer/src/belief/speech.py` — new `render_scan_readback(sector_label)`, a fixed-phrasing
  `"Scanning {label}."` template mirroring `render_readback`'s "fast and identical every time"
  posture (a scan has no contact to describe the way `render_watch_nearest_readback` does).
- `body-layer/src/belief/crew_console.py` — replaced `_handle_scan_forward` with `_handle_scan`,
  implementing D5's register-then-trigger contract: calls `belief.tools.scan_area` first (mirrors
  `console.py`'s `_handle_scan_area` handler almost exactly, just with `center`/`radius_m`/`reason`
  all fixed since an F10 button supplies no geometry), then `aircraft_client.
  trigger_petrovich_search("forward")` wrapped in its own `try`/`except AircraftLayerError` so a
  failed trigger never un-registers the task. `handle_f10_command` dispatches the 14-token
  vocabulary via two lookup tables (`_RELATIVE_SCAN_TOKENS: dict[str, RelativeSector]`,
  `_BEARING_SCAN_TOKENS: dict[str, Sector]`) rather than a 14-branch if/elif, matching
  `belief.utterance`'s existing ordered-table idiom for a closed vocabulary. New module constant
  `F10_SCAN_RADIUS_M = 3000.0`, documented as an uncalibrated placeholder (same debt class as
  `DEFAULT_SCAN_DEADLINE_S`). Updated the `tasks`/`aircraft_client` field docstrings and
  `_handle_cancel_task`'s docstring, which previously described the token as always dead.
- `body-layer/tests/test_crew_console.py` — replaced the 4 `scan_forward`-token tests (which failed
  outright once the token was removed) with scan-token tests covering: enrichment-unset and
  tasks-unset graceful degradation, a successful relative-sector scan (readback + live trigger +
  task registered pending, `area.relative_sector`), an absolute-bearing scan (`area.sector`), D5's
  "task still registers when the live trigger raises" path, and "scan then cancel_task actually
  cancels it." Updated the overlay-push funnel test to use `scan_ahead` with enrichment/tasks wired.
- `body-layer/tests/test_attention.py` — added the `RelativeSector` wedge-bounds-vs-plan-table test,
  `project_relative_area` rotation/wraparound/fixed-area-unchanged (identity check) tests, and
  `area_wedge_deg` precedence tests (explicit wedge > sector > none, plus the unprojected-relative
  full-circle case). Extended the `_area` test helper with `relative_sector`/`wedge_deg` params.
- `body-layer/tests/test_contacts.py` — added `add_area` sector+relative_sector `ValueError` test
  and a `reproject_relative_areas` test confirming only the relative area's `center`/`wedge_deg`
  change (fixed area's identity/values untouched) and the returned count.
- `body-layer/tests/test_logger.py` — added a test confirming `ConsolePerceptionRunner.run_once`
  re-projects a relative area onto that tick's telemetry (heading/position) before returning,
  exercising D2's tick-wiring end to end rather than only at the `contacts.py` unit level.
- `aircraft-layer/WORKFLOW.md` — updated the "Deploy the F10 commands Hook script" section's menu
  description (three flat items -> the 14-token Scan/Bearing/Watch/Cancel tree) and the no-DCS
  manual UDP-send check's example token (`scan_forward` -> `scan_ahead`, with a pointer to
  `ALLOWED_COMMANDS` for the rest).
- `aircraft-layer/CLAUDE.md` — updated the `petrobrain-f10-commands-hook.lua` Structure bullet's
  stale "three fixed items" description to the 14-token tree (outside the plan's named doc list,
  but the same file class as `WORKFLOW.md` and directly, genuinely wrong after Stage 5 — see
  "Notable Discoveries").
- `body-layer/CLAUDE.md` — updated the `--f10-commands` paragraph and the `crew_console.py`
  Structure bullet to describe the 14-token vocabulary, `_handle_scan`'s register-then-trigger
  behavior, and the two lookup-table dispatch shape (was: three tokens, `scan_forward` hollow).
- `body-layer/ROADMAP.md` — replaced the `[>]` deferred "F10 command refinement and specification"
  backlog entry with an `[x]` done entry for this milestone, stating what was and was not addressed
  (command vocabulary/geometry/D5 fix done; `Observ`/`Track` still blocked on the unidentified 9K113
  OBSERV OFF control; the spec's autonomous-behaviour half deliberately out of scope).

### Tests Added
- `test_relative_sector_wedge_bounds_match_the_plan_table` — the plan's o'clock table (ahead/left/
  right/full) against `project_relative_area`'s output at heading 0.
- `test_project_relative_area_rotates_by_heading`, `test_project_relative_area_wraps_across_360`,
  `test_project_relative_area_returns_fixed_areas_unchanged` — rotation correctness, 360-wrap, and
  the "fixed areas come back as the same object" identity guarantee.
- `test_area_wedge_deg_explicit_wedge_wins_over_sector`, `..._falls_back_to_sector_literal`,
  `..._is_none_with_no_angular_filter`, `..._unprojected_relative_area_matches_full_circle` — D3's
  precedence order end to end, including the permissive-until-first-tick case.
- `test_add_area_rejects_sector_and_relative_sector_together` — the mutual-exclusion `ValueError`.
- `test_reproject_relative_areas_updates_only_relative_areas` — a fixed + a relative area registered
  together; only the relative one's `center`/`wedge_deg` change, count returned is 1.
- `test_console_runner_reprojects_relative_areas_before_ingest` — `logger.py`'s tick wiring, real
  `ConsolePerceptionRunner.run_once` call.
- `test_scan_ahead_without_enrichment_reports_not_configured`,
  `test_scan_ahead_without_tasks_reports_not_configured` — graceful degradation.
- `test_scan_ahead_registers_a_task_and_triggers_a_live_search` — the happy path: readback text,
  live trigger call, and the registered `PendingIntent`'s `area.relative_sector`.
- `test_scan_bearing_n_registers_a_task_with_the_absolute_sector` — the compass-absolute half of the
  vocabulary, `area.sector` set and `area.relative_sector` `None`.
- `test_scan_registers_task_even_when_the_live_trigger_fails` — D5's core claim: a raising
  `trigger_petrovich_search` still leaves the task `pending`.
- `test_scan_then_cancel_task_actually_cancels_it` — the end-to-end fix for `cancel_task`'s
  previously-dead path.

### Checks
**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy src --strict (run from `body-layer/`): pass
- pytest -q: pass (520 passed, +14 from the 506 baseline)

**aircraft-layer/** (docs-only touch, verified unaffected)
- ruff format --check: pass
- ruff check: pass
- mypy src --strict: pass
- pytest -q: pass (109 passed, unchanged from baseline)

### Notable Discoveries
- Stages 1-5's committed state matched the plan exactly on inspection (`RelativeSector`/
  `wedge_deg`/`project_relative_area`/`reproject_relative_areas`/`scan_area`'s new params/the Hook
  script's 14-token tree/`ALLOWED_COMMANDS`) — no rework needed there, only Stage 6/7 and tests.
- `console.py`'s existing `_handle_scan_area` (BL-6) already implements D5's exact register-then-
  trigger shape for the typed `scan-area` command — `_handle_scan` mirrors it directly rather than
  inventing a new pattern, per the "verify mission-probe pattern claims" memory: I read that
  function in full before claiming the mirror, not just its docstring. `_handle_scan`'s `center`
  is ownship's own position at the source (`GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.
  alt_m)`), unlike a typed `scan-area <bearing> <range> <radius>`'s player-projected point — an F10
  button has no bearing/range input, so "scan around where we are" is the only geometry available;
  the plan's Stage 6 instructions confirm this ("Centre is ownship position").
- Removing the `scan_forward` token broke 4 pre-existing tests outright (the token no longer
  dispatches at all, per D4's "not aliased" decision) — rewrote them to the new vocabulary rather
  than leaving them red, since the plan's D4 explicitly mandates removing the token, not keeping a
  compatibility path.
- Found and fixed one doc beyond the plan's named Stage 7 list: `aircraft-layer/CLAUDE.md`'s
  Structure section for `petrobrain-f10-commands-hook.lua` still said "three fixed items: Watch
  Nearest/Scan Forward/Cancel Task" — directly, genuinely wrong after Stage 5's Hook-script commit,
  same class of staleness as `WORKFLOW.md`'s deploy section the plan did name.

## Review fixes (2026-09-16, addressing plans/f10-command-vocabulary/review.md)

### Files Changed
- `body-layer/src/belief/contacts.py` — added `ContactStore.get_area(area_id)`, a plain live
  lookup into `self._areas`. This is the mechanism the fix below resolves a task's area through,
  instead of trusting `PendingIntent.area`'s captured reference.
- `body-layer/src/belief/tasks.py` — **Required fix 1.** `TaskStore.tick` now resolves each
  pending task's area via `store.get_area(task.area.id) or task.area` before calling
  `area_contains`, instead of reading `task.area` directly. `task.area` (captured once at
  `tools.scan_area`/`ContactStore.add_area` time) goes stale for a relative-sector area the moment
  `ContactStore.reproject_relative_areas` first replaces the store's entry via `dataclasses.
  replace` (a new frozen object, `task.area` still points at the old one) — this was silently
  turning every `scan_ahead`/`scan_left`/`scan_right`/`scan_full` task's sector filter into "no
  angular filter at all," per the review's repro. Chose id-based resolution against the live
  `ContactStore` (already passed into `tick`) over threading a callback or giving `belief/
  contacts.py` a `belief/tasks.py` import — the latter was explicitly ruled out by the fix's own
  constraints as a worse layering inversion. The `or task.area` fallback only matters if a
  still-`pending` task's area id is ever missing from the store, which should not happen —
  `tools.cancel_task` always cancels the task before removing its area — so it is a documented
  safety net for an invariant violation, not a path the design relies on.
  Also updated `PendingIntent.area`'s docstring to say plainly that only `.id` is safe to read
  directly off a captured reference; anything else (`.center`/`.wedge_deg`) needs live resolution.
- `body-layer/src/belief/tasks.py` — **Required fix 2.** Extended the module docstring with an
  "Ownship-anchored areas are a moving patch of view, not ground" section: states that a relative-
  sector scan's completion predicate means "seen in the sector at *some* tick since the task was
  created," a genuinely different predicate from the fixed-ground-area case, and explains why (the
  captured-vs-live-object staleness above) and how `tick` now resolves it.
- `body-layer/tests/test_tasks.py` — two new tests (below) plus a new `_observation_at` helper
  (configurable `bearing_deg`, mirroring the existing `_observation`'s bearing=0-only shape) needed
  to place a contact off-axis for the sector test.
- `plans/f10-command-vocabulary/plan.md` — **Optional fix 3.** Redrew the "Menu tree (D4)" diagram
  to include the `Bearing` submenu's 8 compass items (matching the shipped Hook script/
  `ALLOWED_COMMANDS`/every other doc) and added a "14 leaves total" line under it reconciling the
  diagram with D4a's "14-token vocabulary below" prose. Added a one-line note under the "Sector
  bounds" table clarifying it only covers the 4 new relative sectors — the 8 `Bearing` items reuse
  the pre-existing absolute `Sector` literal and need no new bounds definition.

### Tests Added
- `test_tick_resolves_relative_scan_area_against_its_live_projection` — the fix's core regression:
  registers a `relative_sector="left"` area, creates a task over it, reprojects onto heading 0
  (projecting to absolute bearings [270, 330)), then asserts a contact dead ahead (bearing 0 —
  inside the old permissive/unprojected circle, outside the projected wedge) does NOT complete the
  task, while a contact at bearing 300 (inside the projected wedge) does. Would have failed before
  the fix (the task would have completed on the bearing-0 contact, since `task.area.wedge_deg` was
  still `None` at tick time).
- `test_tick_falls_back_to_captured_area_when_the_live_area_is_gone` — exercises the `or task.area`
  fallback branch directly: removes a still-pending task's area from the store via `remove_area`
  (bypassing `cancel_task`, which never leaves this state reachable in practice) and confirms
  `tick` still runs the containment check against the stale reference rather than raising or
  silently treating the task as unmatched.

### Checks
**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy src --strict (run from `body-layer/`): pass
- pytest -q: pass (522 passed, +2 from the 520 baseline)

**aircraft-layer/** (untouched by this fix pass; re-verified per CONSTRAINTS)
- ruff format --check: pass
- ruff check: pass
- mypy src --strict: pass
- pytest -q: pass (109 passed, unchanged)

### Notable Discoveries
- None beyond the review's own finding — `store.get_area` did not exist yet (only `.areas` and
  `.remove_area`), so it needed adding rather than reusing something already there.
