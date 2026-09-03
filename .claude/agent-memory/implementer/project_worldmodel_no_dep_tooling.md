---
name: project-worldmodel-no-dep-tooling
description: world-model/ had no venv/lockfile tooling before M1 added pyproj — first real dependency
metadata:
  type: project
---

As of M1 (coordinate transform, 2026-09-03), `world-model/` had no `.venv`, `uv.lock`,
`poetry.lock`, or CI config anywhere — `pyproject.toml` had `dependencies = []` until M1 added
`pyproj`. No `uv`/`poetry` installed on the dev Mac either (plain `python3`/`pip3`, Homebrew
Python 3.14).

**Why:** M0 was pure recon/scaffolding with no runtime deps; M1 is the first milestone that
actually needs a third-party library.

**How to apply:** If a task needs to install/run against a dependency, there's no existing
venv to reuse — create `world-model/.venv` (already covered by `world-model/.gitignore`'s
`.venv/` entry, do not add a new ignore rule) and `pip install` into it. Don't assume `uv` or
`poetry` are available; check first. If dependency count keeps growing, worth flagging to the
user/architect that a lockfile tool decision is now overdue rather than each session ad-hoc
creating a venv.

Also: `pytest`'s `pythonpath` ini option (`[tool.pytest.ini_options] pythonpath = ["src"]`,
pytest 7+) was used to make `tests/` import from `src/` without installing the project as a
package — simplest option given no packaging setup exists yet. `tests/control_points.py` is a
plain data+helper module (not itself a test file) imported by both `tests/test_coordinates.py`
and `tools/report_control_point_errors.py`; the latter reaches it via a manual `sys.path.insert`
since tools/ scripts run standalone, not under pytest.
