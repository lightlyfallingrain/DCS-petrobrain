---
name: project-bl11-tick-cost-round2-review
description: BL-11 round 2 — APPROVED WITH REQUIRED FIXES; ruled to delete two now-uncalled production functions, and three claims-vs-code mismatches
metadata:
  type: project
---

`feature/bl11-tick-cost` round 2 (tip `57715dc`, 2026-10-06): both round-1 required fixes landed
correctly; verdict APPROVED WITH REQUIRED FIXES on three small claim-accuracy items plus a scope
ruling. 1512 passed / 4 xfailed, all `/invariant-check` rows PASS.

**Why:** two things generalise beyond this branch.

1. **A fix can create dead code whose justification the earlier review supplied.** Round 1
   approved keeping `_cohesive` / `_resolvable` *because they were the reference implementation*.
   Round 1's own required fix was to stop the reference using them — so the approval's premise was
   consumed by the fix, and both functions became uncalled. The implementer correctly declined to
   delete production code nobody asked to delete and escalated instead. **When a review's
   rationale for keeping something is "X uses it", and the same review asks X to stop using it,
   rule on the leftover in the same breath.**
2. **The dangerous half was `_cohesive`, not the dead-code tidiness.** It is a second,
   hand-maintained copy of the per-candidate term computation that `group_salient_ids` hoists —
   uncalled and untested, so it drifts silently if the hoisted term set changes. That is what made
   deletion a maintenance call rather than a style one.

**How to apply:** on this project, dead production code with an honest "currently has no caller"
docstring is still worth deleting when it duplicates arithmetic that lives elsewhere; a direct
test is the worse option, because the only honest test of a delegation wrapper is tautological.
Delete on the branch that created the deadness, not as a backlog item — the context is the diff.

Three defects found, all one class — **a docstring or test name claiming something the code does
not do**, which is now this branch's signature defect across both rounds:

- the equivalence test's "only the tuning constants are shared" (four leaf geometry helpers are
  shared too — correctly, but the claim was false);
- the healthy-case `close()` tests (see
  [[feedback_healthy_case_guard_test_needs_buffered_state]]);
- `_resolve_speech_log_path`'s paragraph saying explicit `--speech-log` directory failures are
  left to per-write handling, immediately above the new code that overrides it.

A real find worth remembering structurally: **adding `mkdir(parents=True)` to a path helper turns
every bare relative path in the tests into repo pollution**, and no check reports it — format,
lint, mypy and pytest all pass either way, while an untracked `logs/` at the repo root makes a
later unrelated agent's `git worktree remove` refuse. The implementer caught it and rerooted the
two tests onto `tmp_path`; I confirmed by running the suite from both documented CWDs and checking
`git status --porcelain` empty after each. **Run the suite from every documented CWD and check for
an untracked tree whenever a diff adds directory creation.**
