---
name: worldmodel-mypy-path-requires-cwd
description: world-model/pyproject.toml's mypy_path is relative -- strict type-checking tools/ or tests/ imports (raster, coordinates, control_points) only resolves when cwd is world-model/
metadata:
  type: project
---

`world-model/pyproject.toml` sets `mypy_path = "src:tests"` (relative). The
documented command in `world-model/CLAUDE.md` (`mypy world-model/src`, run
from repo root) sidesteps this because `src/` is self-contained. But running
`mypy`/`ruff` against `world-model/tools/*.py` or `world-model/tests/*.py`
from the **repo root** fails with spurious `import-not-found` errors for
local packages (`raster`, `coordinates`, `control_points`) that resolve fine
in `pytest` (which uses `pythonpath` in the same `pyproject.toml`, working
regardless of cwd).

**How to apply:** to strict-type-check a `tools/` or `tests/` file that
imports local packages, `cd world-model` first, then run
`.venv/bin/python -m mypy src tools tests` (or similar) from there. Don't
conclude a tool script has a real import bug just because repo-root mypy/ruff
invocation reports one -- verify from `world-model/` before flagging it.
