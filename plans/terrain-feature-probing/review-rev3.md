# Review: terrain-feature-probing, Revision 3 (Stages 3a–5)

Branch `feature/terrain-callout-stages-345`, verified tip `4da9758` (base `947895d`). The main
checkout's worktree landed on `main` (`646af7c`, expected per the dispatch note) — reviewed via an
isolated snapshot: `git archive feature/terrain-callout-stages-345 | tar -x -C <scratch>`, scratch
path `/private/tmp/claude-501/-Users-sg-Code-DCS-petrobrain/912e8304-06e6-47eb-b21d-2480a8d16101/scratchpad/snapshot`.
All commands run with `cwd` inside `<scratch>/world-model` or `<scratch>/body-layer`, using the main
checkout's own `.venv/bin/{ruff,mypy,pytest}` binaries. Knowledge graph unavailable (`graphify-out/`
not built in this worktree) — not queried; flagged per the standing rule rather than skipped silently.

Reviewed against: `plans/terrain-feature-probing/plan.md` (Revision 3 section, lines 14–268),
`explore-notes.md`, `implementation-rev3.md`, `security-plan-review-rev3.md` (APPROVED, no
blockers). Six commits read in full: `d1d4a88`, `9125fe1`, `ecef698`, `b785376`, `4c59a41`,
`4da9758`.

### Review Summary

The design matches Revision 3 closely and the implementer's documented deviation (a separate
`closest_point_on_feature` instead of widening `nearest_feature`'s tuple) is the correct call —
verified against `describe.py`'s seven existing 2-tuple unpacking call sites, which a 3-tuple would
have broken silently. The mechanism/calibration split (`d1d4a88`/`9125fe1`) is real, not cosmetic —
confirmed by diff. `divides.py` samples no elevation and is not a second LOS implementation —
confirmed by reading the module, which touches only `features_in_bbox` and segment-segment
intersection. The ownship-relative divide count and the Stage 3a dominance rule are never written
into `WorldEnrichmentCache` — confirmed by reading `WorldEnrichmentCache.get_or_compute` and
`_add_enrichment_facts`, which computes `terrain_divide_qualifier` uncached, beside
`relative_geometry`, on `contact.last_position`-derived `world_position` (fused belief, not ground
truth) — the no-omniscience boundary holds. Group reports drop the qualifier by construction
(`render_group_report` never reads the key, not a special-cased guard). All mechanical checks
(ruff/mypy/pytest, both subprojects) reproduce the implementer's reported numbers exactly.

One real gap, detailed below: the Stage 5 wiring between `terrain_divide_qualifier`'s result and
the spoken contact-report text is completely untested end-to-end, confirmed empirically by disabling
both halves of the wire-up and re-running the full suite with zero failures.

### Required Fixes

- **The Stage 5 wiring (`tools.py` → `facts["terrain_qualifier"]` → `speech.py`'s priority override)
  has no test anywhere, and disabling it produces zero failures.** `terrain_divide_qualifier` itself
  is well tested in isolation (`test_enrichment.py`'s five `test_terrain_divide_qualifier_*` cases,
  calling the function directly). But nothing tests that `_add_enrichment_facts` actually writes its
  result into `facts["terrain_qualifier"]`, and nothing tests that `_contact_report_text` actually
  reads that key and replaces the `max(semantic, key=confidence)` selection with it. I confirmed this
  is a real gap, not a documentation oversight, two ways:
  - `grep -rn "terrain_qualifier" body-layer/tests/` returns **zero** hits — not one test file
    constructs a `facts` dict containing the key, whether by hand or by driving the real pipeline
    with `divides_between` patched to return `1`.
  - Empirically: wrapping the `if isinstance(terrain_qualifier, str):` branch in `speech.py` with
    `if False and ...`, and separately wrapping the `facts["terrain_qualifier"] = ...` assignment in
    `tools.py` with the same `if False and ...`, each independently leaves the full body-layer suite
    at **1430 passed, 4 xfailed** — identical to the real run. Neither change is detected by any
    test. (Both edits reverted after confirming; suite re-ran clean at the same count.)

  This is the actual deliverable of Stage 5 — "the divide-relative callout" — and it is the one part
  of the five commits with no test coverage at all. The five fixture files that gained a
  `divides_between` stub (`test_tools.py`, `test_console.py`, `test_crew_console.py` x2,
  `test_callouts.py`, `test_speech.py`) all stub it to return `0` unconditionally, which means
  `terrain_divide_qualifier` returns `None` in every one of those tests and the new branch in
  `_contact_report_text` is never exercised by them — they were patched only to stop an unrelated
  `sqlite3.OperationalError` against a schema-less fake connection, not to cover the new feature.

  **Fix:** add at least one test that drives `_contact_report_text` with
  `facts["terrain_qualifier"] = "next valley"` (or `"beyond the ridge"`) present alongside a
  populated `facts["semantic"]`, asserting the qualifier text appears and the semantic fragment does
  not — and one that drives `_add_enrichment_facts`/`_contact_facts` with `divides_between` patched
  to return `1`, asserting `facts["terrain_qualifier"]` is actually set. Given `render_group_report`
  already provably never reads the key (by not calling it, not by a guard), no equivalent fix is
  needed on the group path.

### Optional Refinements

- **`implementation-rev3.md`'s two-of-five-fixtures-passed-by-luck note is accurate and worth
  keeping, but the fix it describes (patching all five fixtures to stub `divides_between` to `0`)
  only prevents a crash — it does not give any of those five files actual coverage of the new
  feature.** Not a required fix on its own (the dedicated `test_enrichment.py` tests cover the pure
  function), but worth folding into whatever closes the Required Fix above, since the natural place
  to add real wiring coverage is probably one of these same fixtures with the stub changed from `0`
  to `1` for one test case, rather than a wholly new fixture.
- **`TERRAIN_QUALIFIER_MAX_M`, `TERRAIN_DOMINANCE_FACTOR`, and `DIVIDE_MERGE_M` are first-guess
  constants** (plan's own Risks section already says so, "tune by flying") — no action needed here,
  noted only so the DoD acceptance card states these are expected to move after a real sortie, not a
  defect to chase.

### Verdict

**NEEDS REVISION** — one required fix (test coverage for the Stage 5 wiring), everything else holds.

### Review Confidence

Full read of all six commits' diffs, the plan (Revision 3 section), `explore-notes.md`,
`implementation-rev3.md`, and `security-plan-review-rev3.md`. Mechanical checks
(`ruff format --check`, `ruff check`, `mypy --strict` equivalent `mypy src`, `pytest -q`) reproduced
for both subprojects against the isolated snapshot and matched the implementer's reported numbers
exactly (world-model 548/3, body-layer 1430/4). Empirically verified three mechanisms are
non-decorative by disabling each and re-running: the dominance-factor comparison (2 tests failed),
`DIVIDE_MERGE_M`'s merge step (1 test failed), and — the negative finding above — the Stage 5
wiring (0 tests failed, confirming the gap). Real-store numbers in `implementation-rev3.md` and
`world-model/ROADMAP.md` were not independently re-run against `syria-full.sqlite` (not available in
this snapshot; this is a read-only query against the user's own build artifact, not a build, and the
reported numbers are internally consistent with the plan's own predicted check). Knowledge graph was
not queried — `graphify-out/` does not exist in this worktree, consistent with the plan's own note
that the main checkout's graph is stale for this topic.
