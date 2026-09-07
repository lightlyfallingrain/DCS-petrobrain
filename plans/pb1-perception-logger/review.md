### Review Summary

Reviewed `feature/pb1-perception-logger` (commits `08ba9c0`, `6cd5be6`, `90e749f`) against
`plans/pb1-perception-logger/plan.md` stages 2-3 only (stage 1 live spike and stage 4+ concrete
`PerceptionSource` tiers are out of scope by design, correctly not attempted). Scope matches the
plan closely: `body-layer/` BL-0 scaffolding (protocol, geometry helpers, replay harness,
aircraft-layer HTTP client, stub logger) and the aircraft-layer `world_objects` endpoint, nothing
more, nothing from stage 4+ (no concrete `PerceptionSource`, no `__main__`/CLI, no contact
association — all correctly left out).

All six implementer-flagged items were independently verified, not taken on faith:

1. **LOS-sampling bypass of `describe_position` is real and correctly scoped.** Confirmed
   `geometry.py`'s `elevation_at` does route through `query.describe_position` (single-point
   lookup), while `line_of_sight_clear`'s per-sample loop calls `store.reader.sample_grid`
   directly — the same underlying primitive `describe_position.elevation.dcs_m` is itself built
   on (`world-model/src/query/describe.py:390`), just without the road/settlement/navaid joins.
   This is a genuine perf-motivated deviation, not a correctness shortcut — it does not drop
   elevation data (absence is still propagated as `None` → skip-sample, never a fabricated
   default), and it's documented inline in both the module docstring and `body-layer/CLAUDE.md`.
2. **Lat/lon vs. DCS x/z mismatch is handled consistently, not assumed uniform.**
   `aircraft-layer/src/schema/world_objects.py` keeps `LoGetWorldObjects` output as raw
   `lat_deg`/`lon_deg`/`altitude_m` (explicitly not converted, since aircraft-layer has no
   world-model dependency), while `body-layer/src/perception/geometry.py`'s `GeoPosition`/
   `bearing_deg`/`range_m` all operate on DCS x/z. No code currently feeds one into the other
   uncorrected — there is no Tier 3 consumer yet (correctly deferred to stage 4) — and the gap is
   flagged explicitly in three places (research doc, aircraft-layer `CLAUDE.md`, implementer's
   Notable Discoveries) as "a concrete Tier 3 source will need to convert this itself." No
   silent-uniform-frame assumption found.
3. **mypy CWD quirk is genuine and pre-existing, but the documented canonical command is now
   broken for this subproject — see Required Fixes.** Reproduced directly: `mypy body-layer/src`
   run from repo root reports `Config File: Default` and two `import-not-found` errors
   (`query.describe`, `store.reader`); the identical command run with `cwd=body-layer/` reports
   `Config File: .../body-layer/pyproject.toml` and passes clean (6 files). This generalizes the
   existing `world-model`/mypy-config-discovery finding, but unlike that case (silent
   non-strict-but-passing), body-layer's cross-subproject `mypy_path` turns a repo-root
   invocation into a **hard failure**, not a silent pass. Ruff, by contrast, was proactively
   fixed with an explicit `known-first-party` list in `body-layer/pyproject.toml`, so
   `ruff check`/`ruff format --check` are confirmed CWD-independent (verified both ways) —
   good practice, exactly the fix the project's recurring ruff-cwd-quirk memory has been asking
   for elsewhere.
4. **Bearing reference is true heading throughout, confirmed, no magnetic leak.**
   `aircraft-layer/src/schema/__init__.py` explicitly names the wire field `heading_true_rad`
   ("Magnetic heading is not exported here"); `world_objects.py` uses the same
   `heading_true_rad` name; `OwnshipState.from_telemetry_dict` converts it straight to
   `heading_true_deg`; `geometry.bearing_deg`'s docstring and implementation match. Consistent
   end to end.
5. **No network assumption in the world-model seam.** `geometry.open_world_model` is a bare
   `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` — no HTTP, no client object, matching
   the plan's decision 3 (in-process, same-box only). The aircraft-layer seam
   (`aircraft_client.py`) is correctly the only real network call in the package.
6. **Fixtures are committed, small, and synthetic.** `git ls-files` confirms both fixtures are
   tracked (not gitignored); `body-layer/.gitignore` has no fixture exclusion; both fixture files
   are a handful of lines with obviously invented coordinates/timestamps, matching
   `body-layer/CLAUDE.md`'s Testing section and plan decision 4.

Standard checks: `ruff format --check`, `ruff check`, `mypy --strict` (from each subproject's own
directory), and `pytest` all pass clean for both `body-layer` (28 tests) and `aircraft-layer` (34
tests, 22 pre-existing + 12 new, none of the pre-existing tests modified). `test_api.py`'s and
`test_world_objects_api.py`'s backward-compatibility claim (`TelemetryAPIServer`/`CollectorServer`
constructor signature changes not breaking existing call sites) is independently proven by a
dedicated test (`test_default_world_objects_cache_answers_null_when_omitted`), not just asserted
in prose. `git status` is clean — nothing untracked, agent-memory files for architect/implementer/
investigator all staged and committed (the "unstaged agent-memory" issue that recurred across five
prior milestones is not present here).

### Required Fixes

- **`body-layer/CLAUDE.md`'s documented `mypy body-layer/src` command fails when run from repo
  root** (2 `import-not-found` errors, config file silently not discovered) and only passes with
  `cwd=body-layer/`. Every sibling subproject's CLAUDE.md documents the same repo-root-relative
  invocation style, and for `world-model`/`aircraft-layer` that happens to still work (their
  `mypy_path` never reaches outside their own `src/`). Body-layer's does, because of the
  in-process world-model seam, and the failure mode here is a hard error, not the softer
  "silently non-strict but green" failure mode the existing project memory already tracks. Anyone
  (a future session, CI, DoD) following the CLAUDE.md commands block literally will see a false
  "2 type errors" result on a clean tree. Fix by either: (a) adding a one-line CWD caveat directly
  in the Commands block itself (e.g. "run from inside `body-layer/`: `cd body-layer && mypy src`"),
  matching how the ruff-cwd-quirk memory now insists a *canonical-command failure* gets fixed
  rather than re-flagged as optional; or (b) restructuring the command so it's CWD-independent
  (e.g. `mypy --config-file body-layer/pyproject.toml body-layer/src`). This is a documentation-only
  fix, cheap, but load-bearing for correctness of future verification — not optional.

### Optional Refinements

- `Observation.ownship_at_observation` in the shipped code carries the full `OwnshipState`
  (including `t_sim` and `heading_true_deg`), while `plans/body-layer/plan.md` §5's worked
  example sketches it as a smaller inline dict (`{x, z, alt_m, heading_deg}`). The implementer's
  choice is more precise (explicit "true" in the field name) and not a functional problem, but
  worth a one-line note in `plans/body-layer/plan.md` §5 reconciling the two once BL-1 proper is
  planned, so the schema doc doesn't drift further from what's actually shipping (optional).
- `Observation.source` staying a plain `str` rather than a closed `Literal` is a reasonable,
  explicitly-justified deferral (two plans propose different candidate value sets, no concrete
  tier exists to settle it) — flagging only so it isn't forgotten once stage 4 picks a tier
  (optional, already tracked in the implementer's own Notable Discoveries).
- The stale "Mission Interpreter and Petrobrain Runtime modules do not exist yet" line duplicated
  across five `.claude/agents/*.md` files is now mildly inaccurate now that `body-layer/` is real
  code (even though it correctly isn't the full Runtime yet). The implementer correctly declined
  to edit agent-role definitions as out of scope; flagging again here so it doesn't get lost
  before the next planning pass touches those files (optional, not a blocker for this branch).

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — all changed source files in both subprojects were read in full (not diff-skimmed),
all six implementer-flagged deviations were independently reproduced/verified against the actual
code and, where applicable, actual command output (mypy CWD behavior, ruff CWD-independence,
`git ls-files`/`git status`), and both subprojects' full check suites (`ruff format --check`,
`ruff check`, `mypy --strict`, `pytest`) were re-run directly rather than trusted from the
implementer's session notes.
