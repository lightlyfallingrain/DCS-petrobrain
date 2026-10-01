### Definition of Done: landform-geomorphons (WM-B6)

Branch `feature/landform-geomorphons`. Worktree landed on `main`'s tip (`955e17f`, on branch
`worktree-agent-a7eaded93c4f9bbcc`) before any check ran — `git rev-parse HEAD` caught it
immediately, matching exactly the failure class `AGENTS.md` rule 4 documents. Checked out
`feature/landform-geomorphons` directly; `git rev-parse HEAD` then returned `be502fd537f8fc64f032
d592d0796b61c9b5fef9`, the exact tip named in the task. All checks below ran against that commit.

No `.venv` existed in the fresh worktree; built one from `world-model/pyproject.toml` (host Python
3.14 — no 3.11/3.12/3.13 available locally; numpy 2.4.6/scipy 1.18.1 installed cleanly, matching
the pin in `pyproject.toml`). `ruff`/`mypy`/`pytest` installed directly (no dev-dependency group
declared).

### Prior sign-off (not re-litigated here)

- Reviewer: 3 rounds, all APPROVED — round 1 (APPROVED WITH MINOR FIXES, `4ed1853`), round 2
  (fix verification, APPROVED, `cc68f48`), round 3 (performance-fix review, APPROVED, `be502fd`).
  All three verified their own tip via `git rev-parse HEAD` first and re-ran the full mechanical
  suite from a fresh `.venv` rather than trusting a prior report.
- Security: one deep-analysis pass per the project's current cadence (root `CLAUDE.md`'s "Agents"
  section — security runs once per whole feature, immediately before DoD, not as a separate
  plan-review stage). `security-review.md`, tip `cc68f48`, APPROVED. No `security-plan-review.md`
  exists for this feature, and **that is expected under the current cadence, not a gap** — it
  supersedes the generic two-document DoD template for features going through this cadence.
- Performance: `performance.md` found one blocking issue (unbounded whole-theatre memory
  accumulation, ~29 GB extrapolated) and one non-blocking one (O(N²) Chaikin deviation check,
  ~25 min extrapolated full-theatre CPU). Verdict: NEEDS MITIGATION. Both were fixed in `b4d38cf`
  and independently re-verified by Reviewer round 3 on different tiles/different tooling than the
  implementer used (45,578 lines re-traced for the smoothing-equivalence claim, a direct re-run of
  `ingest_terrain()` over 6 real tiles for the memory claim, correcting for the macOS `ru_maxrss`
  units pitfall this project's own agent-memory already documents).

### Mechanical checks (from `world-model/`)

```
.venv/bin/ruff format --check src tests   -> 116 files already formatted
.venv/bin/ruff check src tests            -> All checks passed!
.venv/bin/mypy src                        -> Success: no issues found in 71 source files
.venv/bin/pytest tests -q                 -> 510 passed, 3 skipped
```

Matches the task's expected 510/3 exactly (494-collected baseline on `main` + this branch's net
+16 test files/functions across `test_geomorphons.py`, `test_resample.py`, `test_skeleton.py`,
`test_terrain_cache.py`, plus the streaming-contract test from the perf fix, minus the deleted
`test_terrain_curvature.py`).

`git status --porcelain` in the worktree: clean, before and after. All work (plan docs, code,
tests, roadmap, renders) already committed on the branch by the prior rounds — DoD added no new
commits to the feature branch itself (see "Handoff" below for what *is* new, on top).

### Code Quality

- **No debug output, no TODO/FIXME introduced.** `git diff main...feature/landform-geomorphons --
  world-model/src` grepped for `print(`/`TODO`/`FIXME`/`XXX`/`pdb.set_trace`/bare `except:` /
  `except Exception:` — zero hits in added lines.
- **No unhandled errors in data paths** beyond what Security's deep analysis already characterized
  (a pre-existing, off-diff 0-byte-`.hgt` edge case, accepted, not blocking).
- Subprojects touched: `world-model` only (`git diff main...feature/landform-geomorphons
  --name-only` — all paths under `world-model/`, `plans/`, `.claude/agent-memory/`). No other
  subproject's commands are owed.

### Scope & Correctness

- Implementation matches `plans/landform-geomorphons/plan.md`'s stated scope (Stages A-F: detector,
  caching, pipeline wiring) — confirmed against `implementation.md`'s file list and Reviewer's own
  scope check (`git diff --stat` compared against the plan's "Affected modules" each round).
  Stage G (full-theatre build) correctly left to the user throughout, per the project's execution-
  boundary rule.
- No unplanned scope added silently — the one addition outside the plan's own scope (removing
  M8's chunk-scoped terrain extraction, since geomorphons' per-tile-with-margin design has no
  chunk-scoped equivalent) is disclosed in `implementation.md`'s "Notable Discoveries" and recorded
  in `ROADMAP.md`'s `WM-B6` entry, not hidden.
- No CLAUDE.md invariants violated: DCS/SRTM data stays read-only, no write path to the DCS
  install; no provenance/confidence field dropped (`StoredFeature`'s `confidence`/`source_id`
  machinery is untouched by this diff, confirmed in Security's review).
- All new files staged and committed — confirmed via the clean `git status --porcelain` above.

### Testing

- Core logic covered: geomorphons classification (synthetic DEM profiles with known expected
  classes), resampling (lattice convention, void/outside-every-tile edge cases), thinning (checked
  bit-for-bit against the reference pixel-loop implementation), the terrain cache (fresh build,
  warm hit, partial-resume — the last one verified by fault injection in Review round 2, not just
  by reading the test), and the streaming-insert memory fix (a dedicated contract test asserting
  one `on_tile_features` call per tile).
- Tests are meaningful, not decorative: Review round 2 caught and fixed one test
  (`test_ingest_terrain_resumes_a_partially_completed_cache`) that was named for resumability but
  actually tested a different, already-covered path — confirmed by patching the real skip-path code
  and watching the renamed/new tests diverge correctly under that break. This is exactly the
  "assert shape, not the real behaviour" failure class this project has hit before; it was caught
  before merge this time.
- No existing tests broken: 510/3 against `main`'s own passing baseline, no regression.

### Documentation

- Reviewer's required fixes (round 1) all addressed and re-verified in round 2: stale
  `docs/M8_PROBE_STORE.md` text corrected, the region-bbox-clipping gap now recorded in
  `ROADMAP.md`'s `WM-B6` "Implementation status" (not just `implementation.md`), and the
  resumability test fixed as above.
- Non-obvious behaviour explained via code structure/docstrings: the junction-walking tracer's
  order-dependent, race-like behaviour on isolated synthetic junctions (vs. real dense skeletons)
  is documented directly in `terrain/skeleton.py` and backed by dedicated fixtures in
  `tests/test_skeleton.py`, per `ROADMAP.md`'s own disclosure of the plan-vs-reference-
  implementation discrepancy.

### Security

- `security-review.md` (deep analysis, tip `cc68f48`): APPROVED. No new dependency. One low-risk,
  pre-existing, off-diff finding (0-byte `.hgt` edge case) accepted, not blocking.
- No `security-plan-review.md` — expected under the current once-per-feature-before-DoD cadence
  (see "Prior sign-off" above), not a missing artifact.

### Verdict: PASS

All mechanical checks green, matching the task's expected figures exactly. Scope matches plan.
Reviewer and Security sign-offs are both substantive (independent re-derivation of empirical
claims, fault-injection-verified test fixes), not rubber-stamped. Proceeding to acceptance.

---

## Acceptance boundary — what these fixtures structurally cannot reach

This passed on real SRTM data and real rendered windows, not synthetic fixtures — a step better
than the F10-vocabulary worked example this role's own instructions warn about. But the acceptance
boundary is still real, and three real agents (Reviewer, Performance Reviewer, this DoD pass) all
hit the same ceiling: **no agent can run, or has run, the actual 131-tile full-theatre build.**
Every number in this report and the acceptance card — the ~14-minute timing, the ~1.8 GB peak RSS,
the resumability claim, the 1.3M-feature extrapolation — is either a direct measurement on a
sampled subset of real tiles (27, or 6, or 22, depending on which pass took it) or a linear
extrapolation from one. None of it is the real run. A full-theatre-scale interaction the sampled-
tile measurements cannot see — a pathological single tile with a genuinely multi-hundred-kilometre
traced crest line hitting the Chaikin deviation check's remaining O(N) term at an unfavourable
constant, or a two-adjacent-tile seam artifact on a real tile boundary, which `performance.md`
itself flags as never having been exercised against real data — would not show up until the user's
own run.

The density finding (≈1.3M features theatre-wide, vs. the old detector's 10,503) is itself an
acceptance-boundary item in a different sense: it is a known, named, unresolved product question
("too many lines to ever *speak*," per `ROADMAP.md`'s own words), not a defect this DoD pass can
close. A fixture, or a 20 km test window, cannot tell a reviewer whether 1.3M lines is navigable
data or noise — only Stage 5 (the callout, unbuilt) and a real flight will.

## Live acceptance debt

**This is debt, not a deliberately-scoped waiver.** The plan never scoped live/full-theatre
verification out — Stage G was always "the user's own run," meaning pending, not skipped. Recording
per `body-layer/ROADMAP.md`'s "Live acceptance debt" pattern, generalized to `world-model`'s own
roadmap since that section doesn't yet exist there:

- **Outstanding:** the full 131-tile `syria-full` rebuild, covering both `WM-B6` (this feature) and
  `WM-B1` (Latin-script names, merged to `main` same day) — one sortie's worth of desk time clears
  both, per the combined acceptance card below.
- **Clears when:** the user runs the build in `docs/acceptance/2026-10-02-geomorphons-latin-names-
  rebuild.md` and reports Blocks A-E back. Record which rebuild (date/host) cleared it in
  `world-model/ROADMAP.md`'s `WM-B6` entry when that happens — don't just tick a box.
- **Not blocking this merge.** Per root `CLAUDE.md`/`AGENTS.md`: live verification happens in
  bursts and must not gate the work. `WM-B1` already merged under the same deferral, naming this
  exact rebuild as what would clear it.

## Acceptance card

Published: https://claude.ai/artifact/DKf9eTTWKmJtAKmKF96FdW
Source: `docs/acceptance/2026-10-02-geomorphons-latin-names-rebuild.md` (+ `-card.html`).

**Every command in both files was executed during this DoD pass against the real
`data/raw/dem/syria-full` tiles** (read-only from the main checkout's filesystem, per this
project's execution-boundary rule — never copied, never committed), except the actual 131-tile
`build_world_model.py syria-full` invocation itself, which is explicitly the user's to run and is
labeled as an extrapolation, not a measurement, everywhere it appears:

- `tools/inspect_terrain.py --center -5000,15000 --radius-km 8` -> `ridge: 299 lines, longest
  7.18 km` / `valley: 289 lines, longest 7.70 km` — exact match to the task's stated expectation
  and to `implementation.md`'s own figure.
- `tools/inspect_terrain.py --center -114453.8,25280.8 --radius-km 20` (Baalbek) — the rendered
  hillshade's flat Bekaa floor is clean of ridge/valley lines; all detections sit on the bordering
  slopes. Spot-checked by eye against the real render, consistent with the falsifiable check this
  whole redesign was built to satisfy — but this is still one DoD pass's own-eye read of one window,
  not a substitute for the user's judgment the project has consistently relied on for this exact
  call.
- `tools/inspect_terrain.py --center -54775.0,217141.7 --radius-km 20` (Palmyra) — long isolated
  ridge chains visible crossing flat desert in the render, consistent with the expected pattern.
- The WM-B1 SQL query and the ridge/valley count query were both carried forward from
  `world-model/ROADMAP.md`'s `WM-B1` entry and confirmed to reference real schema (`feature` table,
  `tags_json` column) rather than guessed ORM-style names.

One card, not two — `WM-B1`'s own DoD (`8c6719f`) explicitly deferred its acceptance to this same
shared rebuild, since neither feature produces an observable effect without a full-theatre build
and both would otherwise cost the user two separate desk sessions for one underlying trigger.

## Milestone Completion question

**Does this change what the next milestone should be, or invalidate a downstream assumption?**
Yes, in the direction the roadmap already anticipated rather than a surprise: `WM-B6` landing
unparks Stages 3-5 of `plans/terrain-feature-probing/plan.md` (landform adjacency, bearing in
`describe_position`, the actual "at the foot of the hill"/"next valley" callout), which have been
blocked on detection quality since 2026-10-01. It does **not** yet unblock them in practice — the
roadmap's own "consumer half" section (`ROADMAP.md`'s `WM-B6` entry, "The consumer half") still
needs its own design pass, and the 1.3M-feature density question has to be answered (which lines
are worth saying) before Stage 5 can be scoped concretely. The next actionable piece of work this
unblocks is that design pass, not Stage 3 code directly.

## Recurring-fix pattern check

Checked `review.md`'s three required fixes (stale `M8_PROBE_STORE.md` doc, an undocumented
roadmap gap, a misnamed test) against `.claude/agent-memory/dod/MEMORY.md`'s existing pattern
entries (`recurring_plan_test_file_naming`, `recurring_keyword_table_vocabulary_mismatch`,
`recurring_multiround_threshold_widening`). None of the three match an existing category at the
2+-occurrence threshold — the misnamed-resumability-test is adjacent to but distinct from the
existing "plan names a wrong test file" pattern (that one is an Architect-stage authoring defect;
this one is an Implementer-stage test that passes but doesn't test its own claim, caught by
Reviewer). Not graduating this to a tracked pattern on a single occurrence — noting it here so a
second occurrence (a test whose name overstates what it actually exercises) would be recognized
rather than rediscovered.

## Handoff

Committed on `feature/landform-geomorphons`, on top of `be502fd` (the tip this DoD pass verified):
this report (`dod-check.md`), the acceptance doc + card (`docs/acceptance/2026-10-02-geomorphons-
latin-names-rebuild.md` and `-card.html`), the `NOTES.md` harvest, and `world-model/ROADMAP.md`'s
`WM-B6` entry update (status, counts reproduced, live-acceptance-debt note). No code changes. No
merge performed, per the task's explicit instruction — reporting back for the orchestrator to
sequence.
