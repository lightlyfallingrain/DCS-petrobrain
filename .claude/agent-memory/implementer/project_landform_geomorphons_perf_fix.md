---
name: project-landform-geomorphons-perf-fix
description: WM-B6 performance fix (ff747c3->b4d38cf) -- streaming terrain inserts, O(N) Chaikin via per-point support windows
metadata:
  type: project
---

Fixed `plans/landform-geomorphons/performance.md`'s two findings on `feature/landform-geomorphons`
ahead of the user's planned full-theatre Syria build (commits `b4d38cf`, `75df2c0`).

**Blocking memory fix**: `ingest_terrain` no longer returns/accumulates a whole-theatre
`list[StoredFeature]` -- it takes an `on_tile_features` callback, called once per tile (cache hit or
processed), and the caller (`pipeline.py`) inserts immediately, mirroring the existing OSM
streaming-ingest `_flush_nodes`/`_flush_ways`/`_flush_areas` callback pattern already in that file.
The whole-build cache-hit fast path (previously its own `load_all_features`-based branch, same
unbounded shape on a warm rebuild) got folded into the *same* per-tile loop rather than kept as a
separate branch -- worth remembering as a general move: a "whole thing is already cached" fast path
is often just "every unit is individually cache-hit", and unifying the two loops removes a second
place the same memory bug can hide. Measured: 27 real tiles, peak RSS plateaus at 1.75GB (vs. the old
code's ~6-7GB predicted at the same cumulative-feature count) -- bounded by the largest single tile,
not cumulative count, confirmed by the plateau shape itself (RSS stops climbing once a bigger tile
than any seen so far has been processed, not when some total feature count is reached).

**O(N^2) deviation-check fix, reusable technique**: Chaikin corner-cutting repeatedly replaces an
edge `(c_i, c_{i+1})` with two points that are each convex combinations of `c_i` and `c_{i+1}` alone.
Tracking, for every output point, the `(lo, hi)` range of *original* point indices that fed into it
(a point's support can only grow by merging its two parents' ranges, one pass at a time) gives a
window that's provably bounded by iteration count, not line length. Checking a point's deviation only
against `points[lo:hi+1]` instead of the whole original polyline turns an O(line_length) per-point
check into O(1), and the whole deviation pass from O(line_length^2) to O(line_length) -- turned a
43.8s tile into 6.87s. **The safety argument that made this acceptable without an explicit formal
proof**: checking a subset of segments can only report a distance >= the true global minimum (fewer
candidates to minimize over), so the windowed check can only be *more* conservative than the full
scan, never less -- it can trigger the existing half-cell fallback in a case the full scan wouldn't,
but can never accept a smoothing the full scan would reject. Empirically verified zero-mismatch
against the full scan over every real traced line in two real datasets (588-line acceptance window +
11,104-line heaviest tile) rather than trusting the argument alone -- worth doing whenever a
"provably safe direction" optimization touches geometry that has a hard "must not change" bar
attached (here: the acceptance-window line counts were explicitly forbidden from moving).

**Branch-tip note**: dispatched tip was `ff747c3` ("Performance review ... NEEDS MITIGATION"), but
the checked-out branch tip was actually `c39ec08` (one commit ahead -- a security deep-analysis doc
commit, approved, that had landed on the branch after the performance review but before this fix).
`ff747c3` was confirmed a strict ancestor of `c39ec08` via `git merge-base --is-ancestor`, so this
was forward progress the task brief hadn't caught up with, not the AGENTS.md rule-4 "worktree landed
on the wrong code" trap (which is about the worktree tip *predating* or being *unrelated to* the
named commit) -- proceeded rather than stopping, and reported the mismatch rather than silently
ignoring it. Worth the one `git log`/`merge-base` check any time a dispatched sha doesn't match
`HEAD` exactly: ancestor-of vs. not-ancestor-of is the actual decision point, not sha equality.

See also [[reference-macos-ru-maxrss-unit-bytes]] for a measurement-script pitfall hit while
producing the before/after numbers for this fix.
