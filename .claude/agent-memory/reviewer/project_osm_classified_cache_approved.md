---
name: project-osm-classified-cache-approved
description: Third M8-pattern persistent store (osm_cache) reviewed and approved — atomicity, invalidation, and source_id-drop deviation all verified sound.
metadata:
  type: project
---

Reviewed `feature/osm-classified-cache` (commit 8fbf9a8) against
`plans/osm-classified-cache/plan.md` (ff68282). Approved, no required fixes.

Key verification points that mattered for this one, useful pattern for the next
M8-shaped persistent-cache feature:
- The "except BaseException guarantees no canonical file" claim was true for a subtle
  reason: the except block does no cleanup of the canonical path itself — it doesn't need
  to, because `finalize_cache` (the sole writer of the canonical path via `os.replace`) is
  simply never reached. Read the except block expecting active cleanup and initially wanted
  to double check it wasn't a hollow guarantee; it wasn't, but this is worth verifying
  directly every time this atomicity shape (`.tmp` + os.replace + broad except) reappears.
- The mid-stream-failure test actually flushed one real batch (`on_ways(...)` called) before
  raising, so it's a genuine partial-population repro, not just "raise and check nothing
  exists" (which would have passed for a wrong reason too).
- The `source_id`-dropped-from-cache-schema deviation was sound: verified against
  `store/schema.py`'s actual `feature.source_id -> source(id)` FK relationship, and confirmed
  every cache-read batch is retagged with the current build's `source_id` before
  `insert_features` (both in `pipeline.py`'s real branch and the perf tool's mirrored loop).

See [[project_mi5_reviewed_approved]] and [[project_osm_streaming_ingest_approved]] for other
approved reviews in this area's lineage (M8 probe-store precedent, streaming-ingest fix this
cache piggybacks on).
