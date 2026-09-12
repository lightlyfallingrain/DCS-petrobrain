### Review Summary

Reviewed on branch `feature/osm-streaming-ingest` (worktree `/tmp/dcs-petrobrain-osm-streaming`),
commit `03d4ce3`. This is the memory-bounded OSM streaming-ingest fix for the stalled `syria-full`
build. Verified by reading the full diff (`plans/osm-streaming-ingest/plan.md`,
`world-model/src/osm/pbf.py`, `world-model/src/build/ingest_osm.py`,
`world-model/src/build/pipeline.py`, `world-model/tests/test_osm_pbf.py`,
`world-model/ROADMAP.md`) and by running world-model's own format/lint/type/test commands myself
in the worktree.

**Core fix is real, not superficial.** `_FeatureCollector.node()`/`way()` flush their buffer to
`on_nodes`/`on_ways` the moment `len(buffer) >= batch_size` and clear it immediately — peak
resident kept-object count is bounded by `batch_size` (`_INGEST_BATCH_ELEMENTS = 50_000`), not by
file-total element count. `collector.flush()` after `apply_file` drains the tail. `load_features`
is a genuine thin wrapper — `stream_features(..., nodes.extend, ways.extend,
batch_size=sys.maxsize)` — so it still buffers everything, but only because it explicitly asks to
via an effectively-infinite batch size (documented, deliberate), not because streaming is fake.

**Pipeline wiring is real (this was the single highest-priority check).** `pipeline.py`'s
`osm_pbf_path` branch (lines ~307-371) now calls `stream_features_from_pbf(osm_pbf_path,
_flush_nodes, _flush_ways)` — the two closures call `ingest_osm_nodes_batch`/
`ingest_osm_ways_batch` and `insert_features(conn, ...)` per batch, immediately, against one
running `OsmIngestStats`. It does **not** call `load_features` anywhere in this branch. The
`osm_cache_path` (Overpass, M3) branch is untouched and still uses `load_features`/`ingest_osm`
as before — correctly, since Overpass responses are already small. A real `syria-full` rebuild via
`--osm-pbf` genuinely gets the fix.

**Correctness regression coverage is real, not cosmetic.**
`test_streaming_matches_load_features_on_the_same_file` asserts streamed node/way lists and
skip counts are byte-for-byte equal to `load_features`'s bulk output on the same synthetic
fixture — this is the actual "streaming == bulk" proof, not just "doesn't crash." A second,
`skipif`-gated test does the same comparison against the real gitignored Syria extract when
present. `TestStreamFeaturesMemoryBound` uses `tracemalloc` to assert peak traced memory scales
with `batch_size`, not fixture element count — the test that would have caught the original bug.
Chunking tests confirm no batch exceeds `batch_size` and the partial tail batch is not dropped.
`test_ingest_osm.py`-equivalent batch-splitting parity is handled at the `ingest_osm` level
(`ingest_osm` is now proven-identical to `ingest_osm_nodes_batch`+`ingest_osm_ways_batch` called
once each, by construction and by the pre-existing `test_ingest_osm.py` suite passing unchanged).

**Batch size**: `_INGEST_BATCH_ELEMENTS = 50_000`, matches the plan's chosen value and rationale
verbatim (module comment reproduces the plan's per-object memory reasoning and commit-count
estimate, and honestly flags it as unmeasured/needing re-tuning after a real run — consistent
with the plan's own "Risks & Unknowns").

**Relations/multipolygon handling unaffected**: `relation()` still only increments
`relations_skipped`, unchanged in shape or behavior; no multi-pass logic was introduced.

**Junctions audit spot-check (item 4, addendum)**: confirmed accurate against the actual code.
`roadnet/junctions.py`'s `extract_clusters` calls `all_features(conn, ["road"])`
(`store/reader.py:112-128`), a plain `SELECT ... FROM feature` materialized into one Python list
with no streaming/paging — the same "bulk-load into memory" shape the audit describes. The
`latakia-20km`-based extrapolation and "probably fine but unmeasured at syria-full+OSM scale"
characterization is a fair, non-overstated reading of the code; nothing there was mischaracterized.

**ROADMAP.md backlog entry**: present (`world-model/ROADMAP.md` lines ~103-111) and reads
accurately — correctly attributes the concern to this plan's addendum, correctly states it's
extrapolation not measurement, correctly frames it as "confirm on the next real syria-full build,"
matching the plan's own backlog note. Diff-scoped confirmation: `git diff main...HEAD -- world-model/ROADMAP.md`
shows only this 12-line addition, no unrelated roadmap edits smuggled in.

**Commands run in the worktree** (venv from the main checkout, per instructions):
- `ruff format --check src tests` — 94 files already formatted, clean.
- `ruff check src tests` — all checks passed.
- `mypy --strict src` — no issues in 55 source files.
- `pytest -q` — 305 passed, 2 skipped (the two real-data-gated tests, correctly skipped — no
  `data/raw/osm/syria-260911.osm.pbf` staged in this worktree).

No debug prints/TODO/FIXME left in the diff. Working tree is clean; the one commit is present and
contains everything reviewed (no unstaged new files).

### Required Fixes

None that block merging or block the user's urgent rebuild. See Optional Refinements for the one
real gap found.

### Optional Refinements

- **`docs/M9_OSM_RUN_INSTRUCTIONS.md` was not updated** — the plan's Step 6 and its own "Affected
  Modules/Files" list this file explicitly, with a specific purpose: warning a future operator
  watching a multi-hour `syria-full` OSM stage that steady-but-slow batched commits are the new
  expected shape, not a repeat of the killed hang. That operator-facing warning currently exists
  only in code comments (`pbf.py` module docstring, `pipeline.py` inline comment), which the user
  is unlikely to be looking at mid-rebuild. Given the user is about to re-run the exact build this
  fix targets, worth adding before or right after this run — but it is a documentation gap, not a
  correctness gap, and does not need to block the fix from being used now. (Optional, but
  time-sensitive enough to recommend doing promptly.)
- **No `implementation.md` decision log exists for this branch** — expected, per the reported
  cross-worktree coordination interruption that happened before that documentation step. Worth
  writing retroactively (batch-size rationale, the `ways_skipped_unresolved_nodes` field addition,
  the per-batch-commit-instead-of-per-stage-transaction decision) once the urgent rebuild is
  unblocked, purely for future readers — not a correctness or process blocker. (Optional.)

### Verdict
APPROVED

This is mergeable now. The core bug (unbounded in-memory accumulation across the whole
`apply_file` pass) is genuinely fixed, not superficially moved — verified by reading
`_FeatureCollector`'s buffer-and-flush logic directly, not by trusting the docstrings. The
pipeline wiring genuinely routes the real `--osm-pbf` build path through `stream_features`, not
`load_features` — this was the single highest-risk item (a fix that looks complete in `pbf.py`
but does nothing if the pipeline still calls the old bulk function), and it checks out. Tests
prove streaming produces identical output to the old bulk path, not just "doesn't crash," and
prove the memory bound directly via `tracemalloc`. All four of world-model's own format/lint/type/
test commands pass when run directly, not taken on faith from a prior report. The two items above
are worth doing but are documentation/process gaps, not code defects — nothing here should hold
back the user's rebuild.

### Review Confidence
Full read — `world-model/src/osm/pbf.py` read in full, `build/ingest_osm.py` read in full, the
relevant `pipeline.py` branch (both `osm_pbf_path` and `osm_cache_path` branches) read in full,
`tests/test_osm_pbf.py`'s new streaming-specific tests read in full, `roadnet/junctions.py` and
`store/reader.py`'s `all_features` read in full for the addendum spot-check, `ROADMAP.md`'s diff
scoped and read. All four verification commands run directly in the worktree against the real
venv, not trusted from a prior report, per the task's explicit instruction.
