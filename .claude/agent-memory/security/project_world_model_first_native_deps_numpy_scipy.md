---
name: world_model_first_native_deps_numpy_scipy
description: world-model's first non-pyproj/pillow/osmium deps (numpy<2.5, scipy>=1.11), scoped to terrain.curvature only; assessed clean 2026-10-01
metadata:
  type: project
---

terrain-feature-probing (watershed basins) added `numpy>=1.26,<2.5` and `scipy>=1.11` to
world-model/pyproject.toml -- the first additions beyond the long-standing pyproj/pillow/osmium
trio. Scoped narrowly: only `terrain/curvature.py`'s `smooth_grid`/`find_basin_seeds` call
`scipy.ndimage.uniform_filter`/`minimum_filter`; basin growth (`terrain/features.py`'s
`grow_basins`, hand-written heapq priority flood) and axis extraction stay stdlib.

Checked 2026-10-01 (deep analysis, feature branch `feature/terrain-landform-features`,
tip 7329ec3): no CVEs found for numpy 1.26-2.4.x or scipy >=1.11 that touch this usage pattern
(no pickle/deserialization, no network, no untrusted file formats reaching numpy/scipy directly --
`.hgt` parsing stays in stdlib `elevation/dem.py`, untouched by this feature). The `<2.5` ceiling
is a mypy-stub-compatibility pin (numpy 2.5's bundled stubs use PEP 695 syntax mypy rejects under
`python_version = "3.11"`), not a security pin -- worth re-checking whenever that ceiling is
revisited, since it is the kind of pin that *could* someday block a patched release, but there is
no live advisory today that it blocks.

**Why this is low-risk here:** the grid processed is bounded by theatre extent (~2.5M cells max,
same bound the old discrete-Laplacian classifier already worked over), not by any externally
supplied/malicious size. No new resource-exhaustion surface vs. the pre-existing pipeline.

See [[store_writer_fail_closed_geometry_guard]] for the one new invariant-enforcement point this
feature also added.
