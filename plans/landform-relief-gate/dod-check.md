### Definition of Done — `fix/landform-relief-gate`

Branch `fix/landform-relief-gate`, tip `5dc7ae0` (verified via `git rev-parse HEAD` before any
other step).

### Code Quality

- `ruff format --check src tests` — **PASS** (116 files already formatted)
- `ruff check src tests` — **PASS** (all checks passed)
- `mypy src` (run from inside `world-model/`) — **PASS** (71 source files)
- `pytest tests -q` — **PASS**, 539 passed, 3 skipped (matches the implementer's and Reviewer's
  and Security's own reported figures exactly; `main` baseline is 530 passed, 3 skipped — the 9
  new tests account for the difference)
- No unhandled errors/panics in data paths, no debug output, no leftover TODOs — confirmed by
  Reviewer's independent read of the diff (`review.md`, "APPROVED", no required fixes) and
  Security's deep analysis (`security-review.md`, "APPROVED", no required fixes).

Only `world-model/` is touched by this branch (checked: `git diff --name-only main...HEAD`
touches only `world-model/src`, `world-model/tests`, `world-model/tools`,
`world-model/data/renders/`, `world-model/ROADMAP.md`, and `plans/landform-relief-gate/`) — no
other subproject's commands are owed.

### Scope & Correctness

- Matches `plans/landform-relief-gate/implementation.md` — two named defects (no relief gate;
  ~16x-over-dense stored geometry), both fixed as described, plus one real bug found and fixed
  during the implementer's own verification (the windowed vs. whole-polyline deviation check),
  which Reviewer independently reproduced on real data rather than trusting the account.
- No unplanned scope — Reviewer's "Optional Refinements" are cosmetic (a ROADMAP wording
  direction fix, already applied in `01a36c3`; a hardcoded `*16` multiplier in a dev tool, noted
  but not required).
- No CLAUDE.md invariants violated: DCS/SRTM data stays authoritative and read-only (verification
  ran against the user's real store/tiles read-only, nothing copied or committed); provenance/
  uncertainty preserved (`elevation_range_m` carried through unchanged); no mission/forum claims
  encoded without verification.
- `git status --porcelain` clean on the branch tip before this DoD pass started (confirmed below)
  — all implementer files were already staged and committed.

### Testing

- 9 new tests added, exercising the relief gate (threshold behaviour, the exact Baalbek-adjacent
  22 m case), the decimation rewrite (reduction, deviation-cap fallback, the real-data regression
  for the windowed-check bug), `_smooth_for_storage`'s end-to-end path, and cache invalidation on
  the two new knobs — all independently verified as real (not vacuous) by Reviewer, who
  reconstructed the old windowed bug and ran it against the committed regression fixture to
  confirm the test discriminates.
- No existing tests broken; 7 pre-existing `test_ingest_terrain.py` tests gained an explicit
  `min_relief_m=0.0` to isolate them from the new gate (reviewed and found legitimate — the
  shared fixture traces a ridge flat along its own length by construction).

### Documentation

- Reviewer findings: **none required**. Both optional refinements are prose/robustness notes, not
  required fixes.
- Non-obvious behaviour explained in `plans/landform-relief-gate/implementation.md` and inline in
  `terrain/features.py`/`build/ingest_terrain.py`; the windowed-vs-whole-polyline bug is recorded
  both in the implementation doc and as a dedicated regression test name.

### Security

- `plans/landform-relief-gate/security-plan-review.md` does not exist — **expected under the
  current cadence** (security runs once per whole feature, immediately before DoD, not as a
  separate plan-review step for every fix; per `.claude/agent-memory/dod/project_current_cadence_
  one_security_pass_per_feature.md`).
- `plans/landform-relief-gate/security-review.md` exists — **APPROVED**, no required fixes. Deep
  analysis covered cache-invalidation correctness (independently re-verified, not just re-read),
  the decimation deviation guard's direction, and degenerate-input resource behaviour (2000
  collinear points, a 2-point line, and an adversarial 5000-point zigzag — the Douglas-Peucker
  O(n²) worst case) — explicitly assessed as not a security finding for this offline,
  single-player, operator-controlled-input pipeline, and noted for the record per the brief.

### Performance

No Performance Reviewer pass, by design, not by omission. The change only *removes* work from a
pipeline stage whose cost (~14 min terrain-stage CPU, ~1.75 GB peak RSS) was already measured and
signed off on `feature/landform-geomorphons`: `filter_by_relief` drops lines before they ever
reach `to_stored_features`, and `_decimate_for_storage` runs over the already-small
Chaikin-smoothed line (the implementation doc gives the real cost as
`O(len(original_points) * len(decimated))`, cheap because the decimated line is always short, far
below the `O(line_length^2)` cost the geomorphons plan's own performance doc already ruled out).
Security's deep analysis independently agreed with this framing while checking the one case that
could still blow up (Douglas-Peucker's adversarial worst case) directly, rather than taking the
framing on trust — see `security-review.md`'s "Resource behaviour" section. Recorded here as the
reasoning, not as an absent check.

### Mechanical check output (fresh `.venv` built from `world-model/pyproject.toml`, cwd inside
`world-model/`, this DoD pass's own run — not re-quoted from a prior report)

```
$ ruff format --check src tests
116 files already formatted

$ ruff check src tests
All checks passed!

$ mypy src
Success: no issues found in 71 source files

$ pytest tests -q
539 passed, 3 skipped in 20.45s
```

### Working tree

`git status --porcelain` clean before this pass started; this pass's own additions (this file,
the new/updated acceptance docs, `NOTES.md`, `ROADMAP.md`) are staged and committed separately —
see the handoff commit.

### Verdict: **PASS**

Acceptance boundary stated plainly: everything above is fixture/offline verification (unit tests,
a synthetic schema-matching SQLite used to confirm the relief-gate SQL query's logic, a synthetic
`.hgt`-format DEM used to confirm `tools/inspect_terrain.py`'s and `tools/build_world_model.py`'s
CLI invocations actually execute end-to-end) plus independent review of the implementer's claims
against the user's *existing* (pre-fix) real `syria-full.sqlite` and SRTM tiles, read-only. **No
agent has run, or can run, the real 131-tile `syria-full` rebuild** (execution-boundary rule) —
the store-size reduction (~2.4-2.5 GB), the post-gate count range, and the Bekaa/Palmyra renders
at full theatre scale are all still the user's own acceptance step. See
`docs/acceptance/2026-10-04-landform-relief-gate-rebuild.md` and the live-acceptance-debt entry in
`world-model/ROADMAP.md`.
