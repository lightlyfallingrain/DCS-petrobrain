---
name: project_osm_streaming_ingest_approved
description: OSM streaming-ingest memory fix (feature/osm-streaming-ingest) reviewed and approved 2026-09-12.
metadata:
  type: project
---

Reviewed `feature/osm-streaming-ingest` (worktree fix for the M9 `syria-full` OSM `.osm.pbf`
ingest memory blowup that stalled the user's Windows rebuild at ~77M elements/~8.6M ways kept).
Verdict: APPROVED, no required fixes.

Confirmed real (not superficial): `osm/pbf.py`'s `_FeatureCollector` flushes kept nodes/ways to
caller callbacks every `batch_size` (50,000) elements instead of accumulating for the whole
`apply_file` pass; `load_features` is a genuine thin wrapper (`stream_features` with
`batch_size=sys.maxsize`). Most importantly, `build/pipeline.py`'s `osm_pbf_path` branch actually
calls `stream_features_from_pbf`, not the old `load_features` — verified by reading the branch
directly, since a fix that's correct in `pbf.py` but never wired into the pipeline would do
nothing for the real bug. Tests prove streaming output is byte-identical to bulk output on the
same fixture (not just "doesn't crash"), plus a `tracemalloc`-based test proving the memory bound
directly.

One real gap found, classified optional/non-blocking: `docs/M9_OSM_RUN_INSTRUCTIONS.md` was not
updated per the plan's own Step 6, despite being explicitly listed as an affected file — the
operator-facing warning ("steady-but-slow batched commits are now expected, not a hang") only
exists in code comments. Recommended doing promptly given the user was about to re-run the exact
build this targets, but did not block merge.

**Why relevant to future reviews**: this is a good template for "does the fix actually get used by
its caller" verification on wiring-heavy fixes — see [[feedback_verify_pipeline_wiring_not_just_module]].
