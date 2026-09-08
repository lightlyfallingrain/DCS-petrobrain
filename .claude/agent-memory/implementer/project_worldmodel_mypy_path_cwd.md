---
name: worldmodel-mypy-path-requires-cwd
description: mypy only auto-discovers pyproject.toml in its CWD, never by walking up from the target path -- any subproject whose mypy_path points outside its own self-contained src/ (world-model tools/tests, body-layer importing world-model/src) silently loses strict mode and mypy_path from repo root
metadata:
  type: project
---

Root cause (generalizes beyond world-model): mypy's config-file discovery looks for
`pyproject.toml`/`mypy.ini`/etc. **only in the current working directory**, not by ascending from
the file/directory arguments given on the command line, and not from the target package's own
location. `mypy <subproject>/src` invoked from the **repo root** therefore uses mypy's hardcoded
defaults (non-strict, no `mypy_path`) whenever no `pyproject.toml` sits at the repo root -- silent,
no warning, and it can still print "Success: no issues found" because non-strict mode simply
checks less, not because the code passed strict mode. Verify with
`mypy <path> --verbose 2>&1 | grep "Config File"` -- "Default" means the subproject's config was
never read.

Two situations where this actually bites:
1. `world-model/pyproject.toml` sets `mypy_path = "src:tests"`. The documented command in
   `world-model/CLAUDE.md` (`mypy world-model/src`, from repo root) happens to still pass because
   `src/` is fully self-contained -- no cross-package import needs `mypy_path` to resolve. But
   `world-model/tools/*.py` or `world-model/tests/*.py` (which import `raster`/`coordinates`/
   `control_points` from `src/`) fail with spurious `import-not-found` from repo root, while
   resolving fine under `pytest` (whose `pythonpath` setting works regardless of invocation cwd --
   this asymmetry between mypy and pytest config resolution is itself worth remembering).
2. **`body-layer/pyproject.toml`'s `mypy_path` includes `../world-model/src`** (the in-process
   world-model seam, `perception.geometry`'s `from query.describe import ...`). Unlike case 1,
   this breaks the *documented top-level command* itself (`mypy body-layer/src`), not just an
   auxiliary tools/tests path -- confirmed 2026-09-07 building `plans/pb1-perception-logger/
   plan.md` stage 2: from repo root, `query.describe`/`store.reader` report `import-not-found`;
   from `cwd=body-layer/`, the same command is a clean strict pass, 6 files.

**How to apply:** whenever a subproject's `mypy_path`/`pythonpath` reaches outside its own `src/`
(cross-subproject in-process seams, or a `tools/`/`tests/` importing sideways), `cd` into that
subproject first before running `mypy`, regardless of what the CLAUDE.md "Commands" block's
example invocation literally shows. Don't conclude a real import bug exists just because a
repo-root mypy invocation reports one -- verify from inside the subproject before flagging it.
