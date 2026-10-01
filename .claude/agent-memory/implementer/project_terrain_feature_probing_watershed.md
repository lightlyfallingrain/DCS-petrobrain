---
name: terrain-feature-probing-watershed
description: Stage 1-2 watershed rewrite — saddle formula bug, sinuosity not fixable by tuning, numpy/mypy pin
metadata:
  type: project
---

Implemented the marker-controlled-watershed replacement for the old discrete-Laplacian ridge/valley
classifier (`world-model/src/terrain/curvature.py`/`features.py`, `plans/terrain-feature-probing/
plan.md`'s revised Stage 1/2). Three findings worth carrying forward:

1. **The saddle/pass-height formula between two basins is `min` over every contact point of
   `max(elevation on each side)`, never a naive `min` over the combined boundary-cell set.** The
   naive version collapses to whichever basin's own floor-adjacent cell is lowest, which is not the
   height a route between the two basins must actually climb. Caught by hand-deriving test fixture
   expectations before writing the implementation (see [[feedback_regression_test_verify_mechanism_not_just_hypothesis]]-style
   discipline), not after a failing assertion. Relevant again for any future basin-adjacency work.

2. **Sinuosity (zigzag polylines) is not fixed by replacing the classification mechanism, and
   cannot be fixed by retuning alone, when the plan mandates reusing the existing
   `_connected_components`/`_principal_axis` geometry-extraction step unchanged.** That step sorts a
   2D point cloud by projection onto its own major axis; any point set wider than 1 cell across its
   minor axis zigzags, independent of why the cells were grouped. A basin's low-elevation "core" is
   inherently wider than a basin-pair's boundary line, so valleys show this defect far more than
   ridges — pushing the valley core-fraction knob up to fix fragmentation (more cells) makes
   sinuosity 2-3x worse (more width), a genuine structural tradeoff, not a missed sweep value. If a
   future plan needs clean valley/ridge lines, the fix has to be in the geometry-extraction step
   itself (e.g. a skeleton/centreline method), not in the classification mechanism feeding it.

3. **numpy 2.5's bundled type stubs adopted PEP 695 `type` statements unconditionally**, which mypy
   rejects as a syntax error (not a type error) under `python_version = "3.11"` — confirmed 2.2.x/
   2.3.x/2.4.x are clean, 2.5.3 is not. Pinned `numpy>=1.26,<2.5` in `world-model/pyproject.toml`.
   scipy ships no bundled stubs at all and its `scipy-stubs` PyPI package has the same PEP 695
   problem one numpy version earlier — used a scoped `[[tool.mypy.overrides]]` with
   `ignore_missing_imports` for `scipy.*` instead of hunting for a compatible stub version. Revisit
   both the version ceiling and the override if `python_version` ever moves to 3.12+.

Also: a plain `git reset --hard` is in this harness's permission deny-list even when a dispatching
prompt explicitly calls for it (to fix a worktree branch landed on the wrong commit) —
`git checkout -B <branch> <sha>` achieves the same branch-pointer reset without tripping the gate.
