### Definition of Done: BL-B23 — lost contacts excluded from group clustering

Branch `fix/contact-store-pruning`, tip `b2f4b31` (confirmed via `git rev-parse HEAD` as first
action — matched the sha named in the dispatch). Worktree checked out directly onto the branch.

### Mechanical checks (`body-layer/`, fresh `.venv` built from `pyproject.toml`, Python 3.14 — no
3.11 available in this environment, nothing in the diff is version-sensitive)

```
$ .venv/bin/ruff format --check src tests
114 files already formatted

$ .venv/bin/ruff check src tests
All checks passed!

$ .venv/bin/mypy src
Success: no issues found in 53 source files

$ .venv/bin/pytest tests -q
1384 passed, 4 xfailed in 16.02s
```

Matches the expected 1384/4 (main baseline 1379/4 + 5 new tests). `git status --porcelain` clean
before and after the ROADMAP/BACKLOG/NOTES updates below (all staged and committed).

### Code Quality — PASS
- Format/lint/type/test all pass per body-layer's own `CLAUDE.md` Commands section (only
  subproject touched — diff is confined to `body-layer/` plus plan/agent-memory files).
- No debug output, no panics, no TODOs introduced. `_contacts` untouched — nothing deleted, no new
  error-suppression path.

### Scope & Correctness — PASS
- Matches `BL-B23`'s Backlog spec exactly: filter `GroupStore.reconcile`'s input to not-`lost`,
  leave `_contacts` untouched. No unplanned scope. `BL-B24` filed as a separate, clearly-scoped
  backlog item for the orthogonal `association_over_time` finding, not folded into this fix.
- No invariant violated: no-omniscience boundary untouched (pure filter on an existing lifecycle
  field, no new ground-truth exposure); `Contact.last_class_raw`/`classification` dual-field and
  decay/certainty ladder both reused as-is.
- All new files staged (confirmed below).

### Testing — PASS
- 5 new tests, each exercising a distinct real behaviour (exclusion, group-shrink-keeps-id,
  reacquisition, continued answerability, scaling-by-composition-not-timing) — not decorative.
  No existing test broken (1379/4 baseline preserved in full).

### Documentation — PASS
- Reviewer: APPROVED, required fixes: none (one optional refinement — file `BL-B24** — done,
  filed in the branch's third commit).
- `implementation.md`'s "Notable Discoveries" records the orthogonal `association_over_time`
  long-gap ambiguity so a future reader doesn't mistake it for a BL-B23 regression.

### Security — PASS
- `plans/contact-store-pruning/security-review.md`: APPROVED. No plan-review doc exists for this
  branch and none is expected — this is a bug/perf fix (Debugger-shaped path), not a new-feature
  Architect plan; `security-plan-review.md` is only produced after an Architect plan, which this
  work never had (consistent with prior `change-request-fix` precedent in dod agent-memory).

### Performance — PASS (APPROVED, MONITOR)
- `plans/contact-store-pruning/performance.md`: independently reproduced both "before" (418.66 ms
  vs implementer's 402.99 ms vs original 405.8 ms, all within noise) and "after" (1.37 ms at
  n=1200) numbers. Confirms the fix removes the total-ever-seen growth path. The live-count axis
  is unchanged and still quadratic by design (20 live 0.15 ms -> 500 live 70 ms) — correctly kept
  under the pre-existing `group-cohesion-redesign` MONITOR finding rather than filed as a new item,
  with the scenario-design framing ("can a mission realistically reach 300-500 simultaneously-live
  contacts inside the 10 km bubble") recorded in `body-layer/ROADMAP.md`'s new BL-B23 Status entry
  so a future reader finds the judgement without re-deriving it.

### Overall: PASS

### Acceptance boundary, stated explicitly

This is a pure timing fix on `ContactStore.tick`/`GroupStore.reconcile` — the observable
("clustering cost stops scaling with sortie length") is a closed measurement question, not a
cockpit-perceptible behaviour. No candidate that was admitted, clustered, or reported before this
fix is admitted/clustered/reported differently now; the only thing that changes is how long
`reconcile` takes to produce the identical result. A fixture can observe this completely because
"how long does a pure function take on a given input shape" has no dependence on DCS, audio,
terrain, or anything outside the benchmark harness.

**What a fixture structurally cannot show, named rather than hand-waved**: whether a real
multi-hour sortie's `_contacts` shape (how many long-lost records accumulate, how many stay live)
actually resembles the synthetic 20-live/rest-long-lost shape the benchmark assumed, and whether a
live sortie ever drives the live-count axis itself (the still-quadratic one) into the 300-500 band
Performance flagged as a scenario-design question. Both are empirical-shape questions a flight
settles and a fixture cannot, by construction — not because the fixture is weak, but because it has
no sortie-length or threat-density axis to be wrong about.

**Decision: no dedicated acceptance card.** A long sortie is already pending for the
group-cohesion-redesign work and exercises this exact `tick()`/`reconcile()` path end to end on
whatever contact shape that flight actually produces — the first thing it would reveal is whether
BL-B23's assumed shape holds, incidentally, with no separate card needed. If that flight's
`_contacts` count at the end of the sortie, and the peak simultaneous-live count, get noted when it
happens, that is enough to retire this feature's open question; it does not need to be the flight's
purpose.

### Milestone completion question
Does not change what's next. It narrows (does not invalidate) the pre-existing
`group-cohesion-redesign` live-count MONITOR: that risk is now measured to be exactly as large
post-fix as pre-fix, so whoever next revisits that MONITOR item should treat BL-B23 as having
tested, not changed, the number.

### NOTES.md harvest
Two entries added (see `/Users/sg/Code/DCS-petrobrain/NOTES.md`):
1. Exclude-from-clustering vs. delete-from-store — the obvious wrong fix for an unbounded-growth
   defect is pruning the memory, not excluding stale records from the one expensive consumer.
2. "The fix works" and "the cost is now bounded" are different claims — a benchmark that holds one
   axis fixed (total-ever-seen) and confirms flat cost along it says nothing about a second axis
   (live-count) that is still quadratic by design; Performance caught this by sweeping the axis the
   implementer's benchmark never varied.
Skipped: the `association_over_time` long-gap reacquisition-ambiguity discovery — durable but
narrow to one module's gate mechanics, already fully recorded in `BL-B24` and two test docstrings;
adding it to NOTES.md would not generalise beyond that one file.

### Recurring-fix pattern check
`review.md`'s Required Fixes: none, so there is nothing to compare against
`.claude/agent-memory/dod/MEMORY.md`'s prior recurring-fix entries this round.
