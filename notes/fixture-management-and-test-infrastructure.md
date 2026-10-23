# Fixture Management & Test Infrastructure

- **A blocked stage that looks like a product fork can actually be a fixture pinning an unreachable state — check whether a real producer can emit the fixture's exact field combination before trusting the "fork."** `group-collapse` Stage 3's first pass hit an existing, unmodified test asserting `classification_raw="BMP-2"` paired with `classification_level=CLASS` (class-level) and read it as a genuine semantic fork between two valid renderings, reverting the stage. Reading the real producers (`naked_eye_source.py`, `hybrid_source.py`) showed no live channel ever emits a type-shaped raw string at class level — `hires` emits a type string only at `TYPE` level (falling back to `op_class` at `CLASS`), `medres` emits `op_class` at `CLASS`, the scope channel hardcodes `TYPE`. The fixture's pairing was simply wrong, not a case the code needed to handle; correcting the fixture (`classification_level=2` → `3`) unblocked the stage with no behaviour change. Lesson: before treating a test-driven blocker as a design question, check reachability against the real producers, not just whether the assertion is internally sensible (`plans/group-collapse/implementation.md`, "Stage 3 — landed (second pass)").

- **Local world-model fixture `.sqlite`s have non-uniform schema/coverage — no single fixture is complete.** Two fixtures are available locally: (1) `latakia-20km.sqlite` (small, feature-rich, per M5) predates M7 Stage 2's `grid.provenance` schema bump and fails on any `describe_position` call with `sqlite3.OperationalError: no such column: provenance` — pre-existing gap, not a feature defect. (2) `syria-full.sqlite` (full theatre, post-M7) has current schema but incomplete feature layers: `airfield`/`named_place`/`navaid`/`road`/`runway` present, but `settlement`/`water`/`ridge`/`valley` missing (ingestion apparently never ran for full theatre). Testing that exercises all feature kinds currently requires fakes or a newly-built schema-current regional fixture. Future fixture work should target a complete build: either rebuild `latakia-20km.sqlite` with current M7+ schema, or run missing ingestion stages against `syria-full.sqlite` (BL-3 implementation note).

- **`caplog.at_level(level, logger=name)` only scopes the *level* of the named logger — it does
  not limit which records land in `caplog.records`.** pytest's `LoggingPlugin` attaches its
  capture handler to the root logger unconditionally for every test's call phase, so any logger
  anywhere in the process that propagates to root (the default, and nothing in this codebase sets
  `propagate = False`) can contribute a record to whichever test happens to be running when it
  fires. body-layer has several `daemon=True` background threads (`BrainLayerClient._poll_loop`)
  that are started by one test against an unreachable URL, retry forever, and are never stopped —
  so a test asserting an exact `caplog.records` list must filter by `record.name` (and, if two
  leaked instances can share a logger name, by `record.thread == <own thread>.ident`) rather than
  trusting the `logger=` argument to `at_level` to have already done that filtering. The pollution
  is wall-clock-coincidental, not seed-deterministic — repeated runs of the identical
  `--randomly-seed` did not reproduce the same failure (`connection-reporter-flaky` debug report,
  2026-10-23).
- **A test that passes when run alone is not proof its assertion is actually discriminating —
  it may be passing because nothing happened to collide with it that run.** The pre-fix
  `test_unreachable_brain_logs_one_line_without_traceback` took `caplog.records[0]` unconditionally
  with no thread filter; it was passing on `main` whenever no other leaked `BrainLayerClient`
  thread happened to log into the same capture window, not because the code distinguished its own
  record from a different leaked instance's. Correctness was accidental, not demonstrated, even on
  runs where the test went green (`connection-reporter-flaky`, DoD pass 2026-10-23).
- **body-layer has no shared fixture module for world-model's `query.describe` info dataclasses** (`SettlementInfo`/`WaterInfo`/`RoadInfo`/...) — each test file that monkeypatches `enrichment.describe_position` declares its own private `_FakeInfo` stand-in. As of `landmark-words-no-names` (F7, 2026-10-20) that shape is independently duplicated across five files (`test_enrichment.py`, `test_speech.py`, `test_console.py`, `test_tools.py`, `test_crew_console.py`). When a plan makes `semantic_facts_for` read an existing field unconditionally instead of only in one branch, every one of those copies needs the new field added or the affected test raises `AttributeError` at fixture-construction time, not a wrong assertion — so a plan's test-impact list naming only one file is not enough; grep the whole `body-layer/tests/` tree for `class _FakeInfo` first.
