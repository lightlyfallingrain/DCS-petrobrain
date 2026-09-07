---
name: project_aircraft_layer_stage1_2
description: aircraft-layer/ scaffold + stage 1-2 (one-way kinematic push) implementation facts
metadata:
  type: project
---

Built 2026-09-06 on branch `feature/aircraft-layer-telemetry`, per `plans/aircraft-layer/plan.md`.

- `aircraft-layer/` is a fully independent sibling subproject to `world-model/` — own `pyproject.toml`, no shared config, no dependency on world-model's Python packages. Layout mirrors world-model exactly: `src/<package>/`, `tests/`, mypy strict via `mypy_path = "src:tests"`, pytest `pythonpath=["src"]`.
- No global ruff/mypy/pytest install on this machine — reused `world-model/.venv/bin/{ruff,mypy,pytest}` for aircraft-layer since those tools are standalone and aircraft-layer has zero third-party deps. Safe reuse, not a real coupling.
- Unlike world-model, aircraft-layer's mypy run was NOT cwd-sensitive in this session (worked identically from repo root and from `aircraft-layer/`). Don't assume this holds forever — recheck once more inter-package imports exist. See [[project_worldmodel_mypy_path_cwd]] for the world-model version of this issue.
- Schema (`src/schema/`): `TelemetrySample` frozen dataclass, both `dcs_model_time_s` (DCS sim clock) and `received_wall_clock_s` (Python `time.time()` at collector receipt) on every sample — this is a hard project invariant (provenance/timestamps), not just this plan's choice.
- Validation gotcha: `bool` is an `int` subclass in Python — `isinstance(x, int | float)` alone lets `True`/`False` through as valid numeric fields. Must explicitly check `isinstance(x, bool)` first and reject. Caught by a dedicated test (`test_from_json_line_rejects_boolean_for_numeric_field`).
- Collector (`src/collector/`): `TelemetryCache` (pure in-memory ring buffer, `push`/`latest`/`since`) is deliberately decoupled from `CollectorServer` (the live TCP accept loop) — only the cache is unit-tested; the server's correctness depends on a real Export.lua and is validated by the still-pending stage 3 live DCS mission test, not by this session's tests.
- `LoGetSelfData()`'s exact sub-field shape (nested `Position.p.x/.y/.z` vs flat `Position.x/.y/.z`, whether `Heading` is top-level) is documented (Hoggit wiki) but NOT independently verified against the installed DCS version — Export.lua accesses it defensively (`pcall`, fallback shape, skip-sample-on-mismatch) rather than assuming. Confirm/correct in stage 3.
- Stage 3 (live DCS mission test) and stage 4 (Mac-facing HTTP API) are explicitly NOT built yet — deferred per the task boundary, not an oversight. `aircraft-layer/CLAUDE.md` and `WORKFLOW.md` also not written yet (stage 6).
