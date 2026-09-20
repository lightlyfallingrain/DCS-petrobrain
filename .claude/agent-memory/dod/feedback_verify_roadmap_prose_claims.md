---
name: verify-roadmap-prose-claims
description: Cross-check factual claims in ROADMAP.md/plan.md prose ("filed in todo.md", "recorded in X") against the actual diff, not just plausibility
metadata:
  type: feedback
---

A ROADMAP.md entry written during a rapidly-redirected feature (detection-cones-slice1, four
in-session reversals) stated the cut 9K113 sight's figures were "filed in todo/todo.md" — plausible,
consistent with the project's general pattern of filing deferred work there, and wrong: `todo/
todo.md` was untouched by the branch's diff and contains no reference to the new research file. The
figures were correctly filed elsewhere (`body-layer/research/2026-09-20-*.md`), just not where the
roadmap said.

**Why:** narrative claims in ROADMAP.md/plan.md prose ("recorded in X", "filed in Y", "added to Z")
read as settled facts to a future session that trusts ROADMAP.md as the milestone-status source of
truth (per root CLAUDE.md). A plausible-sounding claim that doesn't check out is worse than an
obviously-missing one, because nothing signals it needs verification.

**How to apply:** when a DoD pass reads ROADMAP.md/plan.md prose that names a specific file or
location something was "recorded"/"filed"/"moved" to, grep for it or check `git log -- <that path>`
before accepting the claim — don't rely on the sentence sounding right. This is distinct from and in
addition to re-deriving arithmetic/test claims (already the role's habit per the run-it-before-you-
write-it rule) — prose claims about *where documentation lives* need the same treatment as claims
about *what a computation returns*.
