---
name: project_unbounded_sector_scan
description: F10 scan radius removal (fix/unbounded-sector-scan) -- what changed and how the blast radius stayed small
metadata:
  type: project
---

`AttentionArea.radius_m` is now `float | None` (`body-layer/src/belief/attention.py`), `None`
meaning unbounded (range test skipped in `area_contains`, wedge still applies).
`F10_SCAN_RADIUS_M` constant deleted from `crew_console.py`; F10-originated `scan_area` calls now
pass `None`. Typed `scan-area`/`watch-area` console commands are untouched -- their radius stays
a required `float` at the console-parsing layer, only the shared `tools.watch_area`/`tools.
scan_area`/`ContactStore.add_area`/`AttentionArea` types widened to `float | None` to let the F10
path through.

**Blast radius was smaller than the cones-slice-1 precedent this task warned about**: only two
direct `.radius_m` reads exist in the whole subproject outside tests --
`attention.area_contains`'s range comparison and `console.py::_format_area_line`'s display
string (needed a `"unbounded"` fallback for the `:.0f` format). `belief/tasks.py` never touches
`radius_m` directly, only `area_contains` via the area object, so it needed zero changes.
`grep -n "\.radius_m\b"` across `src tests` is the fast way to re-verify this if the field ever
changes shape again.
