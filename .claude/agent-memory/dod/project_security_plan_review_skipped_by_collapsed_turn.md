---
name: security-plan-review-skipped-by-collapsed-turn
description: RECURRING (2nd occurrence, AA-6) — Architect finishing a plan and moving straight to Implementer skips Security's plan-review gate silently, with no hook to catch it
metadata:
  type: project
---

**Second occurrence: AA-6 (audio-adapter-os-independent, 2026-10-20).** Architect's plan was
approved (commit `45756166`) and the very next commits are Implementer's Stage 1-3 work
(`62e5b70f` onward) — no Security plan-review commit, no `security-plan-review.md`, anywhere in
between. Found only because DoD checked for the file explicitly; Reviewer, Performance Reviewer
and Security's own deep-analysis pass all ran afterward without anyone noticing the earlier gate
was missing. Closed retroactively, same as the first occurrence.

**First occurrence**, `emitter-visibility` (BL-B72/AC-B7, 2026-10-15): the user answered Architect's
four open decisions and wrote "Go ahead and implement" in the same message. The role sequence
(Architect → Security plan review → Implementer → ...) jumped straight from decisions-recorded to
Implementer, with no Security plan-review commit in between — nothing in the commit log, no
`security-plan-review.md` file, no error anywhere. It was found only because DoD's own checklist
names the file explicitly and it was missing.

**This is now a confirmed pattern, not a one-off** — the "possible process fix" below was written
as speculative after the first occurrence; it should be treated as warranted after the second.

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

**Process fix, now warranted**: a dispatch-time hook on `Agent` for Implementer that checks
`plans/<featurename>/security-plan-review.md` exists before proceeding, mirroring the
flight-feedback-gate pattern (`flight-feedback-dispatch-gate.sh`). Report this to the user as a
process-debt signal at the next DoD pass that surfaces it — two silent misses of the same gate is
the threshold this file's own first version set for treating the fix as warranted rather than
speculative.
