---
name: junctions-streaming-fix-minor-fix
description: junctions-streaming-fix reviewed, minor fix — tracemalloc call present but unasserted in the memory-bound test.
metadata:
  type: project
---

Reviewed `feature/junctions-streaming-fix` (2026-09-13). The `feature_layer_bbox` plan
deviation (deriving chunk-walk coverage from a real MIN/MAX R*Tree aggregate instead of the
region's nominal bbox, because `ingest_roadnet.py` stores a route's full unclipped geometry
if *any* point falls in-region) was genuinely reasoned and genuinely implemented — verified by
reading `store/reader.py`'s `feature_layer_bbox` body directly (no reference to `region`) and
by confirming `ingest_junctions_streaming` actually calls it, plus rerunning the real-store
`latakia-20km` test that caught it.

**Pattern worth watching for again**: `test_ingest_junctions_streaming_bounded_peak_roads_per_chunk`
called `tracemalloc.start()`/`get_traced_memory()`, unpacked the peak into a leading-underscore
`_peak_bytes`, and never asserted on it — the test's real assertions were against a
monkeypatched call-count proxy instead. This project's own precedent
(`test_osm_pbf.py::test_peak_buffered_memory_is_bounded_by_batch_size_not_file_size`) does
assert on the traced value. A test that imports/calls `tracemalloc` but discards the result is
an overclaim ("tracemalloc-based test" in the implementation report) worth flagging even when
the proxy metric it actually asserts on is reasonable — check whether traced values feeding a
`_`-prefixed variable are ever read before trusting a "memory-bound" test's docstring claim.

See [[feedback_verify_pipeline_wiring_not_just_module]] — same discipline applies here: don't
trust a docstring's description of what a test proves; read the actual assert statements.
