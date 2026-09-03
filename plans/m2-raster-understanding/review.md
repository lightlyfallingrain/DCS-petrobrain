## Stage 4 Review — `feature/m2-stage4-refine` (commit `00d5ef4`)

### Scope reviewed
Plan item 5 ("Stage 4 — Refine") of `plans/m2-raster-understanding/plan.md`: (a) confirm
`inspect_raster.py`/registration code picks a sensible default tile group, (b) add a
genuinely held-out control point as an independent accuracy check. Diff: `tools/inspect_raster.py`
(`scan --theatre`), `tests/test_raster_registration.py` (`test_held_out_control_point_gemerek`),
`world-model/research/2026-09-03-m2-rastercharts-recon.md` (session 12), plus a re-fix of the
recurring `test_coordinates.py` import-sort finding.

### Review Summary

The substantive Stage 4 work is sound and does what the plan asked. Verified directly, not
just read:

- **`--theatre` annotation**: ran `inspect_raster.py scan <sample_dir> --theatre Syria`
  against the locally sampled tiles — output correctly annotates `Grid layout: 64m sheet='aa'
  level='00'  <- 'Syria' registration default`, matching the claimed behavior exactly.
- **Gemerek held-out point is genuinely independent**: `registration.py`'s `source` field and
  the module comments confirm `origin_x` was fit from Sivas/Kahramanmaras/Hama (tiles
  `x0_z1`/`x3_z1`/`x7_z1`) and `origin_z` from Sivas/Erzincan (tiles `x0_z1`/`x0_z4`).
  Gemerek lands on `x0_z0` — a tile touched by none of the four fit points. No leakage.
- **Residual math is internally consistent**: predicted `(px=403, py=977)` vs. by-eye-read
  `(px=490, py=975)` gives the claimed ~2px/~129m (row/x-axis) and ~86px/~5,515m
  (column/z-axis) residual, both inside the existing tolerances (100px row / 350px column),
  and the z-axis residual (~8.4% of tile edge) is consistent with session 7's already-documented
  ~9%. `confidence` in `registration.py` correctly stays `"provisional"` — it was not
  (wrongly) upgraded off the strength of one held-out point, and the research doc explicitly
  says a second held-out point is still worth doing rather than treating this as closing the
  matter.
- **`level` semantics left unresolved is a reasonable stopping point, not an escalation
  failure**: the agent had no WSL access this session, correctly declined to reason by
  analogy from the unrelated `clipmaps`/`.tif.clipmap` container's confirmed `level*32`
  header finding, and `default_level="00"` is justified on process grounds (it's the level
  the fit was actually run against) rather than a guessed content-based claim. This is
  exactly the discipline `docs/CONVENTIONS.md` asks for. It does not need to have gone to
  `investigator` this session — the finding is already staged as a documented open item
  (in both the research doc and a new `implementer` agent-memory note) for a future
  session that does have WSL access, which is the correct deferral path per
  `world-model/CLAUDE.md`'s investigator-invocation pattern.
- **No Stage 5 leakage**: diff touches only `implementation.md`, the research doc,
  `test_coordinates.py`, `test_raster_registration.py`, `inspect_raster.py`. `ROADMAP.md` and
  `world-model/CLAUDE.md` (Tech stack) are untouched, correctly deferred to close-out.
- **mypy --strict clean, pytest clean**: `mypy world-model/src` — 0 issues. `cd world-model
  && mypy src tools tests` — 0 issues, 10 files. `pytest world-model/tests -q` — 14 passed.
  These all reproduce the implementation log's claims.

### Required Fixes

- **Canonical `ruff check world-model/src world-model/tests` (run from the repo root — the
  exact invocation in `world-model/CLAUDE.md`'s Commands section) currently FAILS**, with
  I001 (import-block un-sorted) in both `test_coordinates.py` and the newly-touched
  `test_raster_registration.py`. This directly contradicts `implementation.md`'s "pass"
  claim for this stage. Reproduced mechanically (not a transient issue):
  ```
  world-model/.venv/bin/ruff check world-model/src world-model/tests   # from repo root
  -> Found 2 errors (I001, both files)
  ```
  Running the same check with cwd=`world-model/` (`ruff check src tests`) passes — this is
  the same cwd-relative isort-resolution flip noted after Stage 3
  (`.claude/agent-memory/reviewer/project_ruff_cwd_dependent_isort.md`), but this time it is
  the *canonical* documented invocation that fails, not a secondary one, so it's a real
  failure against the project's own Definition of Done, not a false alarm to wave off. This
  is also the third-plus recurrence of the same class of finding (implementer's own new
  memory note and `implementation.md`'s Notable Discoveries both flag this) — re-fixing it a
  fourth time without addressing the root cause will just recur again on the next branch.
  Fix required before merge:
  1. Run `ruff check --fix world-model/src world-model/tests` from the repo root (the
     canonical cwd) and re-verify both `ruff check` and `ruff format --check` pass from that
     same cwd.
  2. Add explicit isort config to `world-model/pyproject.toml` (e.g.
     `[tool.ruff.lint.isort]` with `known-first-party = ["coordinates", "raster",
     "control_points"]` or equivalent) so first-party/local-module grouping stops being
     inferred from invocation cwd. Three fix-and-recur cycles is enough evidence that
     leaving this as an implicit default isn't going to hold.

- **Working tree is not clean** — `.claude/agent-memory/implementer/MEMORY.md` is modified
  and `.claude/agent-memory/implementer/project_m2_raster_open_questions.md` is untracked,
  neither staged nor part of commit `00d5ef4`. Root `CLAUDE.md`'s Definition of Done requires
  "All new/modified files staged and committed — run `git status` and confirm a clean
  working tree." The content itself is fine (a legitimate, useful implementer memory note
  about the level-semantics and import-sort recurrence) — it just needs to be staged and
  committed, either folded into this stage's commit or as a small separate one.

### Optional Refinements

- A second held-out control point at a different z-tile-index, to further stress-test the
  weaker z-axis fit, is already flagged by the implementer as future work — reasonable to
  leave for a later session (optional, not blocking Stage 4).
- `world-model/tools/` has its own I001/EXE001 findings (`inspect_raster.py`,
  `report_control_point_errors.py`, `decode_raster_tile.py`) — confirmed out of the
  officially enforced lint surface per `world-model/CLAUDE.md`'s Commands section
  (`src`/`tests` only), so not a blocker, but worth folding into the `known-first-party` fix
  above since it's the same root cause surfacing in a third location now.

### Verdict

APPROVED WITH MINOR FIXES

The held-out control point and `--theatre` diagnostic are correctly scoped, correctly
independent, and verified by direct reproduction — not just plausible-looking. The two
required fixes are process/lint issues (a currently-failing canonical check and an unstaged
memory file), not defects in the raster/registration logic itself, and are both quick to
close.
