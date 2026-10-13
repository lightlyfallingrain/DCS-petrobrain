# Definition of Done: forest-occlusion (Stages 1–2)

**Verdict scoped to branch `feature/forest-occlusion`, tip `ba6bd3943c20aa2d0b607a003ab2d7b1204ab57e`.**
Worktree HEAD (`f444370`) was a strict ancestor of this tip and the tree was clean both before and
after fast-forwarding; no divergence. This verdict describes that one commit, not the branch in
general — if the branch moves, re-run this gate before trusting it again.

## Acceptance boundary — state this before anything else

**Fixtures cannot show the one thing this feature is for.** Every check below (format/lint/type/
test, the mutation-verified guard, the security fix's independent re-mutation) runs against a
synthetic store and synthetic candidates. None of it can tell you whether a pilot, looking at a
unit standing in real DCS canopy over the Latakia coastal belt, actually stops hearing it called
out. The worked example this project already has: the F10 command vocabulary passed DoD on
fixtures (2026-09-16) and the next day's sortie found `Scan` driving the wrong subsystem and
`Cancel Task` speaking a raw id aloud — neither visible to any fixture. This feature's own honest
analogue: the blast radius is 1–3% of ground positions theatre-wide and genuinely **zero** at
Latakia itself, so even a real sortie will show nothing unless units are deliberately parked in
and at the edge of the coastal forest belt. A fixture pass here is a statement about the mechanism,
not about what the pilot will hear.

## Checks run myself

From `body-layer/`, binaries borrowed from the main checkout's `.venv` by absolute path (no
`.venv` in this worktree, as expected — worktrees don't carry gitignored dirs), `cwd` kept in this
worktree:

```
cd body-layer && .venv/bin/ruff format --check src tests && .venv/bin/ruff check src tests \
  && .venv/bin/mypy src && .venv/bin/pytest
```

- `ruff format --check src tests`: **pass** (122 files already formatted)
- `ruff check src tests`: **pass**
- `mypy src` (run from inside `body-layer/`): **pass**, 56 source files
- `pytest -q`: **1726 passed, 4 xfailed** — matches the expected number exactly, not taken on
  trust from the implementer's or reviewer's reported figures.

**world-model is also touched by this branch** (`world-model/tools/measure_landcover_coverage.py`,
new, read-only — no change to `world-model/src` or `world-model/tests`), so its own commands were
run too, confirming the touched subproject's gate isn't silently skipped:

- `ruff format --check world-model/src world-model/tests`: **pass** (118 files)
- `ruff check world-model/src world-model/tests`: **pass**
- `mypy src` (from inside `world-model/`): **pass**, 72 source files
- `pytest world-model/tests -q`: **568 passed, 3 skipped**

The new tool file itself was also format/lint-checked directly (`ruff format --check
world-model/tools/measure_landcover_coverage.py` / `ruff check` — both pass). Two *pre-existing*,
unrelated world-model tool files fail `ruff format --check` when `tools/` is included wholesale
(`validate_m7_stage3.py`, one other) — neither touched by this branch, and `tools/` is outside the
Commands section's stated scope (`src`/`tests` only) in any case; named here so it isn't mistaken
for something this branch introduced.

## Required fixes — closed, verified independently

Security raised exactly one required fix (non-finite `x`/`z` reaching `math.floor` unguarded in
`ForestOcclusion.occluded`). Verified it is genuinely closed in the code, not only in a document:

- Read `forest.py`'s guard directly: `if not math.isfinite(x) or not math.isfinite(z): return
  False`, placed before `_cache_cell_key` is ever reached, matching the fail-open posture the
  security review asked for.
- `grep -n "_cache_cell_key"` in `forest.py`: one definition, one call site, inside `occluded`
  itself, immediately after the guard. No second path into the unguarded `math.floor`.
- `pytest tests/test_forest.py -v`: all 8 forest tests pass, including the 7-case parametrized
  non-finite test and the not-cached test.
- Both Reviewer's and Security's own re-mutation of this exact guard (removing it, confirming the
  exact `ValueError`/`OverflowError` at `_cache_cell_key`'s `math.floor`, restoring it with a
  byte-identical sha1) are documented in `review.md` and already independently reproduce the
  failure mode the fix closes — not re-run a third time here, since nothing has changed since
  those rounds.

## Scope, invariants, staging

- Implementation matches `plan.md`'s Stages 1–2 exactly: Stage 3 (flip default on) and Stage 4
  (in-loop cost measurement) are absent, as instructed — confirmed by reading `visibility.py`'s
  gate 5 (`forest: ForestOcclusion | None = None`, default `None`, the CLI flag defaulting off) and
  `logger.py`'s `--forest-occlusion`/`--no-forest-occlusion` (`BooleanOptionalAction`, `default=False`).
- No unplanned scope: `git diff --name-only main...HEAD` touches only `body-layer/src/perception/
  {forest.py,visibility.py,detection_trace.py,naked_eye_source.py}`, `body-layer/src/logger.py`,
  `body-layer/tools/summarize_detection_trace.py`, `body-layer/docs/STRUCTURE.md`, the plan/review/
  security/performance docs, `todo/backlog/X-B31.md`, `world-model/tools/measure_landcover_coverage.py`
  (new, read-only), and agent-memory files. No touch to `world-model/src/**`, `belief/decay.py`,
  `belief/enrichment.py`, `belief/contacts.py`, `events.py`, `aircraft-layer/**` — confirmed by
  direct diff, not inferred from the plan's own claim.
- No-omniscience: the gate reads `candidate.x`/`candidate.z`, the same `LoGetWorldObjects`-derived
  ground truth every earlier gate in this chain already reads; `detection_trace_writer.py` is
  untouched by this branch's diff. No new ground-truth source.
- `git status --porcelain` on this worktree after the merge and before this file was written:
  clean (confirmed below, after this file and the other outputs are staged).
- `body-layer/CLAUDE.md:279`'s stale "four composed gates" phrase is deliberately left untouched on
  this branch per both Reviewer and Security's explicit calls — a cross-cutting doc fix belongs on
  its own bookkeeping branch (`AGENTS.md`), not folded into this feature's commits. Confirmed still
  present, not silently drifted back in by a later commit on this branch.

## Testing

Core logic (containment, hole handling via world-model's own machinery, the memo's cell-key
arithmetic, gate ordering, the `None`-default no-op, the non-finite guard) is covered, and the
tests are meaningful: `review.md`'s mutation table shows every one of 7 targeted mutations caught
by a real assertion, independently re-verified by the Security round's own mutation of the guard
(byte-identical restore confirmed by sha1). No existing test was broken — the baseline 1704/4 is
intact as a subset of the final 1726/4.

## Documentation

- `review.md` carries two APPROVED verdicts (Stages 1–2, and the security-fix round) with full
  reads, not spot-checks.
- `performance-review.md`: APPROVED — MONITOR. Its own open item (gate 5's real per-poll input
  population, and the 10 m/s ground-speed assumption) is correctly deferred to Stage 4, not treated
  as a blocker here.
- `security-review.md`: NEEDS FIXES → the one required fix closed and re-reviewed clean (see above).
- `todo/backlog/X-B31.md` carries a completion note for the trees-only slice (added by this gate,
  below) — the architect's earlier amendment documented the framing change; this gate adds the
  DoD-PASSED/branch/sha/card pointer that amendment didn't yet have, since it predates this check.

## Milestone question

**Does this change what the next milestone should be, or invalidate a downstream assumption?**
Yes, in one direction only: it makes the treeline `/explore` (the asymmetric canopy-blocks-some-
bearings case the user explicitly deferred) buildable as an internal change to `ForestOcclusion`
rather than a new subsystem — the mechanism, cache shape, and `GateOutcome` slot are now in place.
It does **not** by itself produce the evidence that `/explore` needs; that still requires a sortie
with units deliberately parked in the Latakia coastal belt. It also narrows `todo/backlog/X-B31`
to its buildings half only, decoupling that half's real question (the LAN topology, `X-B27`) from
anything about trees.

## Roadmap/backlog update

`todo/backlog/X-B31.md` updated with a DoD-PASSED completion note for the trees-only slice (branch,
tip sha, sign-offs, acceptance-card link, `#needs-flight` tag — merge pending user approval, per
this project's "deferred vs. waived" distinction: live acceptance is debt, not scoped out). Verified
against `.claude/scripts/roadmap-tag-vocabulary-gate.sh todo/backlog/X-B31.md` → `OK`. No
`<subproject>/ROADMAP.md` pointer touched. No root `ROADMAP.md` status-table edit needed — X-B31 is
not referenced there and no subproject's overall phase status changed.

## Recurring-fix pattern surfaced

**Process signal, not a blocker on this feature.** Security's one required fix here (non-finite
`x`/`z` reaching `math.floor` unguarded) is the **third** occurrence of the same category within
body-layer in one day: `position_belief.py`'s `clamp_to_detection_envelope` (incidental protection
only), `clamp_fold_displacement`'s first guard (missed a second operand), and now `forest.py`. Added
a pattern memory (`.claude/agent-memory/dod/project_recurring_unguarded_nonfinite_float_before_
conversion.md`) naming the category and recommending a single finiteness-validating gate where
ground-truth floats first enter the perception/belief pipeline, raised at Architect for the next
feature touching this chain, rather than re-catching each new function's missing guard at Reviewer
or Security.

## NOTES.md harvest

Two additions, neither duplicate of an existing entry (checked by grep against relevant keywords
first): (1) mutate the dependency, not the module, when the module under test is a thin pass-
through with no logic of its own — `forest.py`'s hole-handling test is the worked example; (2) a
plan's own cost-reasoning prose can carry a stale numeric assumption (here, "5 Hz" vs. the real
1 Hz poll interval) that is internally consistent and still wrong, because nothing checked it
against the actual constant in code.

## Verdict

**PASS** on the mechanical/scope/documentation gate, scoped to `ba6bd394` as stated above.
**Acceptance testing is outstanding** — see the published card
(https://claude.ai/artifact/T7dPmNq3h91hXNeZRvCRyS) for the A/B the user needs to fly before this
merges. Per this project's live-acceptance posture, that outstanding flight does not block the
merge decision being made with full information; it blocks only the claim that the feature has
been seen to work in the air.
