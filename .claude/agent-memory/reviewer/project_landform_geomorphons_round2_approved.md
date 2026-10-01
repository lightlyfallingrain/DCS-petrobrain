---
name: project_landform_geomorphons_round2_approved
description: landform-geomorphons round-2 fix review (5c9f683) APPROVED clean; how to verify a baseline-figure re-marking and a sentinel-feature test assertion aren't hedges
metadata:
  type: project
---

Round 2 of `feature/landform-geomorphons` (tip `5c9f683`, range `4ed1853..5c9f683`) reviewed all
three required fixes from round 1 plus two optional stale-comment fixes. All verified correct;
verdict APPROVED (no further fixes). See `plans/landform-geomorphons/review.md`'s "Round 2" section
for the full account.

Two verification techniques worth reusing:

1. **"Kept as a baseline, not re-measured" claims are checkable against git history, not just
   plausible-sounding.** The implementer re-marked a ~23 ms perf figure in `docs/M8_PROBE_STORE.md`
   as a "pre-`landform-geomorphons` baseline" rather than deleting or re-measuring it. Rather than
   trusting the framing, `git log --follow` found the commit that first recorded the number
   (`8e5ac81`), and reading that commit's own `build/pipeline.py` confirmed `add_probe_chunk` really
   did call the now-deleted `ingest_terrain_chunk`/`terrain.curvature` watershed path at the time —
   so the figure genuinely measured the now-removed work. A "this is a stale baseline, not current
   behaviour" comment is a place authors can quietly dodge re-measuring without being caught by
   reading alone; it has to be checked against the actual historical commit.

2. **A sentinel-feature assertion ("this exact geometry proves cache-hit, not recompute") needs a
   zero-recompute-output guarantee from elsewhere in the same test file, not just assertion by
   itself.** The resumability test's sentinel (`[(0.0, 0.0), (1.0, 1.0)]`) only proves "loaded from
   cache rather than recomputed" if the real pipeline provably cannot produce that geometry from the
   flat fixture tile. Found the proof not in the new test but in an adjacent existing one
   (`test_ingest_terrain_param_change_invalidates_the_whole_cache`, same flat-tile fixture, asserts
   `ridge_feature_count == 0`) — flat terrain has zero geomorphons ridge/valley classes, so recompute
   provably yields nothing, never the sentinel line. Check this cross-test guarantee before trusting
   a sentinel assertion's stated rationale.

Also reused [[feedback_regression_test_empirical_check]]'s pattern directly: patched
`already_complete = completed_tile_ids(conn)` to `already_complete = set()` in
`src/build/ingest_terrain.py`, confirmed the new resumability test fails (`0 == 1`) while the
renamed invalidation test still passes under the same break (proving the two tests exercise
genuinely different paths), restored byte-identical (`diff` against a pre-edit copy), reran full
suite (509/3 again).
