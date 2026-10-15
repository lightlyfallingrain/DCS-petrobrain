---
name: security-plan-review-skipped-by-collapsed-turn
description: user answering an architect's open decisions and saying "go ahead and implement" in the same message skips Security's plan-review gate silently
metadata:
  type: project
---

On `emitter-visibility` (BL-B72/AC-B7, 2026-10-15), the user answered Architect's four open
decisions and wrote "Go ahead and implement" in the same message. The role sequence
(Architect → Security plan review → Implementer → ...) jumped straight from decisions-recorded to
Implementer, with no Security plan-review commit in between — nothing in the commit log, no
`security-plan-review.md` file, no error anywhere. It was found only because DoD's own checklist
names the file explicitly and it was missing.

**Why:** there is no hook gating Implementer dispatch on a plan-review artifact existing, the way
`flight-feedback-dispatch-gate.sh` gates Architect/Implementer dispatch on the feedback-capture
marker. A single user message that both authorizes decisions and the next stage reads as license to
skip everything structurally in between.

**How to apply:** when a feature reaches DoD, check for `plans/<featurename>/security-plan-review.md`
before trusting the role sequence was followed — do not infer it ran just because `security.md`
(deep analysis) exists and is APPROVED; they are different gates with different purposes (plan-stage
catches dependency/surface-shape issues before code exists; deep-analysis catches what only exists
once code is written — see this feature's own retroactive review for why one does not substitute for
the other). If missing, it can be run retroactively against the finalized plan with little cost, but
it is a mechanical criterion DoD must check every time, not assume.

**Possible process fix** (not applied here, worth raising if this recurs): a dispatch-time hook on
`Agent` for Implementer that checks `plans/<featurename>/security-plan-review.md` exists before
proceeding, mirroring the flight-feedback-gate pattern. One occurrence is not yet a pattern; a second
would be.
