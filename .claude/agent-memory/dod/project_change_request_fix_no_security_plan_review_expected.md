---
name: change-request-fix-no-security-plan-review-expected
description: A Security/Performance-Reviewer change-request fix branch correctly has no plan.md or security-plan-review.md/security-review.md of its own — don't flag their absence as a DoD failure
metadata:
  type: project
---

Confirmed on `fix/audio-adapter-review-findings` (2026-09-26) and consistent with
`feature/aircraft-layer-hardening` before it: when a fix branch exists solely to implement findings
from an already-committed whole-subproject Security/Performance review (per `AGENTS.md`, "A change
request from Security or Performance Reviewer re-enters the loop"), the correct role sequence is
Implementer -> Reviewer (review of the fix) -> DoD, with **no fresh Architect plan and no fresh
per-feature security-plan-review.md/security-review.md**. The applicable security artifact is the
whole-subproject audit document itself (e.g. `<subproject>/docs/reviews/security-audit-*.md`),
already committed on `main` before the fix branch existed.

**Why:** DoD's own checklist item ("`security-plan-review.md` exists and is APPROVED") is written
for the New-feature/Refactor sequences where Architect produces a plan Security reviews first. A
change-request fix has no such plan by design — checking for the wrong artifact here would either
fail a correctly-scoped branch or (worse) train future DoD passes to demand plan.md ceremony for
what AGENTS.md deliberately made a lighter loop.

**How to apply:** before flagging a missing plan.md/security-plan-review.md/security-review.md as a
DoD gap, check whether `implementation.md`/`review.md` state the branch is a Security or
Performance-Reviewer change request against an already-approved whole-subproject review. If so,
confirm instead that (a) the underlying whole-subproject review document is committed and reachable,
(b) any factual correction the Reviewer made to that document is coherent and applied everywhere the
claim appeared (not just the first hit — checked by grepping every occurrence of the corrected
claim's key terms), and (c) a deferred/out-of-scope finding from that review is durably recorded
somewhere permanent (the review document's own cross-reference counts) rather than only living in
chat or a plan file that gets archived. Also worth doing at this gate: propose a one-line
`ROADMAP.md` Status entry for the fix even though it isn't a milestone, following the precedent
`aircraft-layer/ROADMAP.md` set for `aircraft-layer-hardening` ("Hardening: ... — done <date>, merged
`<sha>`").
