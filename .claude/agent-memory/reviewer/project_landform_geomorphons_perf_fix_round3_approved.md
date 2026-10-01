---
name: landform-geomorphons-perf-fix-round3-approved
description: Round 3 review of the performance change request (b4d38cf) on feature/landform-geomorphons — APPROVED clean; how a subset-of-candidates safety argument can be verified without needing "exactness"
metadata:
  type: project
---

Round 3 of `feature/landform-geomorphons` (`plans/landform-geomorphons/review.md`) reviewed the
Performance Reviewer's change request (`b4d38cf`): bounding `ingest_terrain`'s per-theatre memory
accumulation via a per-tile `on_tile_features` callback, and turning the Chaikin-smoothing deviation
check from O(N²) to O(N) via a per-point "support window" into the original polyline. APPROVED, no
required fixes.

**The reusable technique: a "checking a subset can only report ≥ the true minimum" safety argument
does not require the subset to be exact — only that it really is a subset.** The implementer's
docstring called the support window "construction-exact," which invited scrutiny of whether the
window was precisely minimal. It doesn't need to be: `distance_point_polyline` takes a `min()` over
candidate segments, and removing candidates from a `min()` can only raise or preserve the result,
never lower it. So the safety property holds for *any* subset of the original points, as long as the
indices never exceed `[0, len(points)-1]` (checked here: `lo`/`hi` are always derived from
`(i, i)`-seeded indices via repeated `min`/`max` merges, so they can't escape that range). This
separates "is the optimization correct" (yes, trivially, given subset-ness) from "is the window tight
enough to be fast" (a performance question, not a correctness one) — worth reaching for whenever a
plan or docstring frames a window/subset optimization's safety as resting on the window's precision,
when it may actually rest on the much weaker and easier-to-verify subset property.

**Re-derive empirical "zero mismatches" claims on different inputs than the implementer used, not
the same ones.** The implementer's own old-vs-new comparison covered 588 + 11,104 real lines
including the tile named in `performance.md`. This review wrote an independent script tracing real
lines from three *different* Syria SRTM tiles (deliberately excluding the named one) through the
actual pipeline functions, getting 45,578 lines / 422,511 points with zero divergence — a larger,
genuinely independent sample rather than a re-run of the same numbers. See
[[feedback_regression_test_empirical_check]] for the general pattern this extends (empirically
breaking/verifying rather than reading).

**Memory re-measurement must correct for the macOS `ru_maxrss` unit pitfall before trusting any
number**, including your own. This project already has
[[reference_macos_ru_maxrss_unit_bytes]] (an implementer agent-memory file) documenting that
`ru_maxrss` is bytes on macOS, KB on Linux. This review's first-draft measurement script divided by
1024 once (the Linux convention) and printed "peak RSS 787,344 MB" before catching it — the same
mistake the memory file warns about, caught only because the file existed and was checked. Always
divide by `1024 * 1024` for MB on macOS, or compute in bytes and label the column explicitly.

Full review: `plans/landform-geomorphons/review.md`, "Round 3" section.
