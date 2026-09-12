### Review Summary

M10 (road-junction detection) reviewed against the locked plan (`plans/m10-road-junctions/plan.md`,
commit `aa27fc6`), the Implementer's decision log (`implementation.md`), and its agent-memory note.
Read `world-model/src/roadnet/junctions.py`, `build/ingest_junctions.py`, `build/pipeline.py`,
`query/describe.py`, both new test files, and ran world-model's own format/lint/type/test commands
directly rather than trusting the reported numbers.

The clustering algorithm, arm-counting rule, grid-bucketing correctness, pipeline integration,
query surface, and the ridge/valley docstring-only change are all sound and match the plan. The one
required fix is a plan-scope gap: Stage 5 (the `world-model/ROADMAP.md` M10 entry) was never done.

**Checks (world-model/, run from repo root per `world-model/CLAUDE.md`):**
- `ruff format world-model/src world-model/tests --check` — pass (87 files already formatted)
- `ruff check world-model/src world-model/tests` — pass
- `mypy world-model/src` (`--strict`) — pass, 51 source files
- `pytest world-model/tests -q` — pass, 266 passed (matches the Implementer's reported count)
- `git status` — clean tree, all new files committed in `aa27fc6`, nothing gitignored staged

### Required Fixes

- **`world-model/ROADMAP.md` has no M10 entry.** The plan's Stage 5 explicitly requires "a new
  **M10 — Road-network junctions** entry once Stage 3/DoD numbers are known, following the existing
  per-milestone entry format" (plan.md lines 134-136), and `implementation.md`'s "Implementation
  Summary" claims "all 5 stages" were implemented, but `grep -in "m10\|junction"
  world-model/ROADMAP.md` returns nothing, and `todo/todo.md` has no M10 reference either. This
  isn't a documentation nicety — it's the mechanism the project uses to track milestone status
  (root `CLAUDE.md` "Current priority": "each subproject's own `ROADMAP.md` ... is that
  subproject's source of truth for milestone status") and to satisfy root `CLAUDE.md`'s "Milestone
  Completion" requirement (does this milestone change what the next milestone should be / invalidate
  a downstream assumption — M10's own "Second-order effect" section about the bridges backlog is
  exactly the kind of note that section exists to capture, and it currently lives only in the plan,
  not the ROADMAP). Needs a real ROADMAP.md entry with Stage 2/3's actual numbers (3,266 roads →
  3,634 junctions, the ~32/3,634 known false-positive population, tuned tolerance/min-degree left at
  their first-guess values) before this milestone can be called done.

### Optional Refinements

- **The high-degree coincident-route false-positive (~32/3,634) is documented but not tested.**
  `junctions.py`'s docstring and `implementation.md` both describe this population accurately and
  the backlog fix (dedupe arms by bearing) is correctly identified as a design change, not a
  threshold tune — appropriately left out of scope. A synthetic regression test asserting the
  current (known-imperfect) behavior on a 2-coincident-road fixture would pin this down for whoever
  eventually attempts the bearing-dedupe fix, but this is genuinely optional since the real-data
  regression test already exercises the real store where this population lives, and the limitation
  is honestly documented rather than silently present (optional).
- **`test_junctions.py`'s near-miss test uses a distinct-feature gap of exactly `3 * tolerance_m`**,
  which is comfortably outside tolerance and doesn't exercise the tighter boundary case (a pair just
  barely over `tolerance_m`, e.g. `tolerance_m * 1.01`) or the adjacent-bucket case specifically
  (two points on either side of a bucket boundary but within tolerance of each other). I verified the
  bucketing math by hand instead (cell_size = 3×tolerance guarantees any two points within
  tolerance_m never differ by more than one bucket index, and the 3×3 neighbourhood scan covers
  that), so this isn't a correctness gap, but a tighter boundary-value test would make that guarantee
  self-evident from the test suite rather than requiring a reviewer to re-derive it (optional).

### Verdict

APPROVED WITH MINOR FIXES

### Review Confidence

Full read — `junctions.py` (clustering/union-find/arm-counting), `ingest_junctions.py`,
`pipeline.py`'s new stage and `_TOTAL_STAGES` renumbering, `describe.py`'s new `JunctionInfo`/
`_junction_info`/`nearest_junction` wiring and the ridge/valley docstring diff, and both new test
files were all read in full, not sampled. World-model's format/lint/type/test commands were run
directly rather than trusted from the report. The Stage 3 rebuild/canonical-file-safety question
(review item 8) was independently verified by filesystem inspection: `data/world-model/
latakia-20km.sqlite` is 8,994,816 bytes with an mtime of Sep 5 — predating this session and not
matching the reported rebuild's 9,805,824-byte figure — confirming the Implementer's full
`build_region` rebuild went to a separate output path, not the canonical `latakia-20km.sqlite`, and
that `implementation.md`'s process-note disclosure is accurate rather than glossed over.
