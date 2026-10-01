# Definition of Done — terrain-landform-features (watershed, Stages 1-2 only)

Branch `feature/terrain-landform-features`, tip `edcb6bc`. This worktree started at `781ead5`
(unrelated history — the tree-LOS merge); reset with
`git checkout -B worktree-agent-a4650e6fa7a2a8081-dod edcb6bc`, confirmed via `git rev-parse HEAD`
before reading any code.

No `.venv` present (gitignored, per-worktree): built from `world-model/pyproject.toml`
(`python3 -m venv .venv && .venv/bin/pip install -e . && .venv/bin/pip install ruff mypy pytest`;
`ruff`/`mypy`/`pytest` have no declared `pyproject.toml` extra, so installed directly). Landed on
numpy 2.4.6 / scipy 1.18.1 — within the pinned `numpy>=1.26,<2.5` ceiling.

## Scope

Stages 1-2 of `plans/terrain-feature-probing/plan.md` only: replace the discrete-Laplacian
ridge/valley detector with a marker-controlled watershed (basin growth gated on relief, ridges
gated on saddle prominence, valleys gated on minor-axis width; both reduced to monotone
polylines). **Stages 3-5 (adjacency storage, bearing, callout) are deliberately not implemented
and their absence is not a DoD failure** — confirmed against the plan's own Implementation Plan
section, which marks them as separate numbered stages this branch does not touch.

Touched subproject: `world-model` only (`git diff --name-only main...HEAD` — every changed path
is under `world-model/`, `plans/terrain-feature-probing/`, or `.claude/agent-memory/`).

## Mechanical checks (all run from inside `world-model/`, this worktree)

| check | command | result |
|---|---|---|
| format | `.venv/bin/ruff format --check src tests` | **PASS** — 104 files already formatted |
| lint | `.venv/bin/ruff check src tests` | **PASS** — all checks passed |
| type | `.venv/bin/mypy src` | **PASS** — Success: no issues found in 62 source files |
| test | `.venv/bin/pytest tests -q` | **PASS** — 491 passed, 3 skipped in 18.86s |

491 passed + 3 skipped matches the stated fresh-worktree baseline exactly (the 3 skips are
gitignored real-data fixtures — `latakia-20km.sqlite`, `syria-260911.osm.pbf` — absent in any
worktree; the main checkout's 494 passed reflects those 3 extra real-data tests running there).

**Working tree**: `git status --porcelain` is empty before this DoD pass's own writes — every file
the implementation/review/security/performance rounds touched was already committed.

## Code Quality

- No unhandled errors/panics in data paths: the two review-round fixes (`_saddle_elevations`
  per-contact-pair formula, `_build_component`'s `len(points) < 2` guard, `store.writer.
  insert_features`'s 1-point-LineString guard) are all fail-closed `ValueError`s on a bounded,
  non-externally-controlled grid — confirmed by the Security deep analysis (`security-review.md`,
  APPROVED, no findings).
- No debug output or leftover TODOs introduced by this feature: `ruff check` (which flags
  `print`/debug patterns in this codebase's config) passes clean; no new TODO comments found in
  the diff (`git diff main...HEAD -- world-model/src | grep -i todo` — no hits).

## Scope & Correctness

- Implementation matches `plan.md`'s Stage 1/2 scope exactly (verified above); Stage 3's
  adjacency-via-basin-growth claim and Stages 4-5 are explicitly future work in the plan itself,
  not silently dropped.
- No unplanned scope added: the diff is confined to `terrain/curvature.py`, `terrain/features.py`,
  `build/ingest_terrain.py`, `build/pipeline.py`, `build/region.py` (two new test regions,
  `baalbek-20km`/`palmyra-20km`), `store/writer.py` (one new guard), their tests, and
  documentation/research notes.
- No CLAUDE.md invariants violated: DCS elevation data stays authoritative (SRTM is external-DEM
  augmentation of the *existing* M7 pipeline, unchanged by this feature); no provenance/timestamp
  fields removed; `world-model/data/` stays gitignored (confirmed — no `data/` paths appear in
  `git status` or the diff).
- All new files staged: confirmed via the `main...HEAD` diff list above — every file the
  implementation/review/security/performance rounds added is already committed on the branch.

## Testing

- Core logic covered: `test_terrain_curvature.py`, `test_terrain_features.py`,
  `test_ingest_terrain.py`, `test_pipeline_build_region.py`, `test_store_roundtrip.py`,
  `test_probe_chunk_pipeline.py` all rewritten/extended for the watershed mechanism (confirmed by
  reading `review.md`'s full-diff read and reproducing the acceptance numbers independently below).
- Tests are meaningful, not decorative: Reviewer's round 1 caught a real case where a test's
  generous threshold margin could not distinguish a correct formula from the rejected one
  (`test_qualifying_ridges_recovers_the_single_divide`'s old margin), and round 2 confirms the
  fixed test's threshold (200.0) sits strictly between the naive (140) and correct (300) saddle
  values — this DoD pass did not re-derive that by hand, but the review's own empirical check
  (hand-running both formulas against the fixture) is itself independently reproducible from the
  fixture code, which I read.
- No existing tests broken: 491/494 pass (3 skips are pre-existing real-data fixture gaps, not new
  breaks — confirmed these are the same 3 names in both this worktree's run and `review.md`'s
  round-2 run).

## Independent re-verification of the acceptance numbers (this DoD pass's own run)

Built a small region end-to-end through the real `build_region` pipeline (not reused from
Reviewer's report) to confirm the mechanism runs correctly on real code paths, including
`inspect_terrain.py` against a real, freshly-built `.sqlite`:

- A synthetic 19x19, 500 m-spacing probe grid matching the shipped `_RIDGE_CHUNK_COLS`-style
  double-V profile (`tests/test_probe_chunk_pipeline.py`'s fixture shape, scaled to a full-grid
  probe rather than a chunk) produced **1 ridge, 6 valleys** through the real
  `build.pipeline.build_region` → `ingest_terrain` path.
- `tools/inspect_terrain.py` run against that real `.sqlite` with both `--center`/`--radius-km`
  and `--near <nonexistent>` (confirming the clear-error path) renders correctly and reports basin/
  component counts matching the stored `feature` rows exactly.
- The fragmentation/sinuosity SQL+Python snippet used in the acceptance card (Block B) was run
  against this same real `.sqlite` and produced sane, non-degenerate output (`ridge: n=1
  pct_under_15_cells=0.0 median_sinuosity=1.000`; `valley: n=6 pct_under_15_cells=66.7
  median_sinuosity=1.080`) — confirming the query itself is correct before handing it to the user
  for the real full-theatre numbers.

This is a correctness/plumbing check on this DoD pass's own part, not a re-run of the three-region
(`latakia-20km`/`baalbek-20km`/`palmyra-20km`) acceptance numbers already independently reproduced
twice by Reviewer (round 1 and round 2) and once by the Implementer — re-reproducing those a third
time was judged unnecessary given two independent prior reproductions already exist in
`review.md`, and the goal here is confirming no regression since Reviewer's round 2, not
re-deriving numbers Reviewer already verified twice.

## Documentation

- Reviewer findings addressed: both round-1 required fixes (saddle formula, degenerate-LineString
  guard) are confirmed fixed in round 2 (`review.md`, APPROVED, no required fixes). The one
  optional refinement from round 2 (document the saddle-gate asymmetry somewhere a Stage 3
  implementer would see it) was acted on: commit `7329ec3` adds it to `plan.md`'s Risks & Unknowns
  section, confirmed present in this worktree.
- Non-obvious behaviour explained: `plan.md`'s Risks section, `implementation.md`'s dated log
  (including its own explicit correction of a false "already fixed" claim), and docstrings in
  `features.py`/`curvature.py` all carry the reasoning a later reader would need.

## Security

- `plans/terrain-feature-probing/security-review.md`: **APPROVED**, no findings (no new network/
  auth/secrets surface; numpy/scipy dependency addition checked against current advisories; two
  new `ValueError` guards confirmed fail-closed).
- No separate `security-plan-review.md` for this plan in `plans/terrain-feature-probing/` —
  checked and this is consistent with the project's actual practice: this feature's plan went
  through multiple Architect revisions in-session rather than a single upfront plan-review gate,
  and the deep analysis (which did run) is the gate that matters for a Stage-1/2-only merge. Not
  treated as a gap.

## Performance

- `plans/terrain-feature-probing/performance.md`: **APPROVED — MONITOR**. Two forward-looking
  monitor items (mildly superlinear `grow_basins`/`extract_components` scaling, ~2 GB peak RSS for
  the terrain stage), neither blocking this merge, both already carried into the acceptance card's
  "what to expect" section so the user isn't surprised by either number.

## Verdict: PASS

All mechanical checks pass, both review rounds are closed out (round 2: APPROVED, no required
fixes), security is approved with no findings, and performance is approved with two documented,
non-blocking monitor items. Scope matches the plan exactly (Stages 1-2 only), and the one
optional-refinement loose end from round 2 review was already closed before this pass started.

## Acceptance boundary — what these fixtures structurally cannot reach

**Every fixture in this test suite is small, hand-built, and known in advance to have exactly the
shape the test asserts.** None of that proves what the real `syria-full` theatre's SRTM grid will
produce once run through this detector end to end — different terrain variety, different basin
adjacency patterns, and (per the saddle-gate asymmetry risk already recorded in `plan.md`) a
region whose true saddle sits inside the gap between the naive and correct formula near the
production `relief_threshold_m`. The three region-scoped rebuilds (`latakia-20km`/`baalbek-20km`/
`palmyra-20km`) are real SRTM data, but still only 20 km windows chosen specifically because their
behaviour was already known (the Bekaa exclusion, Palmyra's isolated ridges) — they confirm the
mechanism does what it was designed to do on the cases that motivated the design, not what it
does on terrain nobody has looked at yet. **A fixture pass here is not a flight pass, and in this
case it is not even a full-theatre-build pass** — that is still entirely ahead of this gate, by
design (the full build is the user's own action, not an agent's).

A second, narrower gap: nothing in this feature's own tests exercises `inspect_terrain.py`'s
rendering output visually (confirmed in `review.md`'s own "Review Confidence" section, and true
again in this DoD pass) — its code was read and, in this pass, run against a small real `.sqlite`,
but no agent has looked at a rendered PNG. The acceptance card asks the user to do exactly that for
Latakia, specifically because no automated check can.

## Live acceptance debt

**Deferred, not waived.** The plan's own Stage 1 acceptance criteria require confirmation against
the real whole-theatre SRTM grid, which only the user can build. This is **not** a case of live
testing being scoped out of the plan — it is pending the user's next desk/Windows session, the
same distinction `world-model/ROADMAP.md`'s "Live acceptance debt" section exists to track. Added
to that list below, worded to match its existing entries' form, and distinguished from the
existing `fix/los-elevation-tolerance` entry (that one needs a real sortie; this one needs a real
build-and-inspect session, no flying required) — one Windows-box session can plausibly clear both
if the user is doing other DCS-adjacent work that day, but they are not the same action and
shouldn't be conflated.

## Milestone Completion question (root CLAUDE.md)

**Yes — the saddle-gate fix changes Stage 3's own input.** Stage 3's landform-adjacency work is
defined over the set of *qualifying* ridges (basin pairs whose saddle clears the relief gate), and
this branch's saddle-formula fix makes that gate strictly more permissive than the first
implementation round shipped — a ridge the naive formula would have rejected can now qualify.
`plan.md`'s Risks & Unknowns section already records this explicitly (added in commit `7329ec3`,
specifically so a Stage 3 implementer sees it before building adjacency on top of ridge
qualification) — this DoD pass confirms that note is in place and accurately reflects the shipped
code (re-read `qualifying_ridges`/`_saddle_elevations` directly, matches the note's description).
No other downstream assumption is invalidated: Stages 4-5's design (bearing, callout) doesn't
change shape based on anything this branch did.
