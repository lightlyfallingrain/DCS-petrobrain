---
name: project_landform_geomorphons_review
description: WM-B6 geomorphons review outcome — set-of-int-tuple determinism technique, stale-doc-pointer gap, misleading test name for an unexercised mechanism
metadata:
  type: project
---

`feature/landform-geomorphons` (WM-B6, Stages A-F) reviewed APPROVED WITH MINOR FIXES
(`plans/landform-geomorphons/review.md`). All checks pass (508/3), reproduction numbers and render
are byte-identical to the implementer's claim when independently re-run.

**Why:** three findings worth remembering as techniques, not just outcomes.

1. **Determinism of Python-set-keyed algorithms over int/tuple-of-int data is actually checkable,
   not just arguable.** `terrain/skeleton.py`'s junction-walk tracer uses a `set`/`dict` keyed by
   `tuple[int, int]` whose iteration order visibly affects output (which walk "wins" a junction).
   CPython does **not** salt int (or int-tuple) hashes — only `str`/`bytes` get randomized-hash
   treatment — so iteration order over such collections is stable across processes for a fixed
   input array. Verified by running the same synthetic skeleton through `trace()` in four separate
   `.venv/bin/python` invocations (two with `PYTHONHASHSEED` pinned differently, two unset/random)
   and diffing output: byte-identical every time. This is the right empirical check whenever a
   "cache premise depends on determinism" claim involves set/dict iteration over int-keyed data —
   don't just reason about it, run it across process boundaries with varied `PYTHONHASHSEED`.

2. **A capability's removal can be perfectly recorded in a plan's implementation.md, a ROADMAP
   entry, and two docstrings, and still be wrong in the one doc a reader is pointed to by name.**
   `world-model/docs/M8_PROBE_STORE.md` is root `CLAUDE.md`'s named pointer for "an M8 reader," and
   it still claimed the probe store held ridge/valley chunk-scoped extraction after this branch
   removed it — even though `ROADMAP.md`, `build/pipeline.py`'s docstring, and `probe_store/
   reader.py`'s docstring all describe the removal correctly. **When a plan removes a capability
   that a named canonical doc describes, check that specific doc by name — "is it documented
   somewhere" is not the same question as "is the doc CLAUDE.md points readers to still correct."**
   See [[m8-probe-store-read-path-drift-gap]] for a related M8-doc-drift finding.

3. **A test can be named for the exact risk a plan calls out, and not test it — and the gap is only
   found by running the real mechanism by hand.** `test_ingest_terrain_resumes_a_partially_completed_
   cache` sounds like it tests Stage E's resumability acceptance check (kill mid-build, resume,
   verify skipped-vs-reprocessed). It actually tests "different tile set → full invalidation, same
   tile set → full cache hit" — two behaviours already covered elsewhere in the same file. Caught by
   reading the test body against what it claims to assert (not just the name), then independently
   hand-constructing the actual untested scenario (write one tile's completion row under a matching
   `TerrainCacheMeta`, call the real `ingest_terrain`, assert `cache_hit=1, processed=1`) — which
   confirmed the mechanism itself is correct, so this was a coverage gap, not a live defect. General
   lesson: a well-named test for a stated risk is not evidence the risk is covered; read what it
   actually constructs.

**How to apply:** on any future terrain/geomorphons/cache follow-up (Stage 5 callout, region-bbox
clip fix), re-check these three before assuming them settled. The region-bbox clipping gap (a region
build stores a whole tile's output, not clipped to the region bbox) is real and *not yet fixed* —
only documented as a required-fix-to-record, not a required-fix-to-code, because the only imminent
real build is full-theatre (no clipping needed there). Don't assume it's been quietly fixed by a
later commit without checking `ingest_terrain`'s own docstring again.
