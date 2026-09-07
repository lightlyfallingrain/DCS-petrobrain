---
name: body-layer-plan-review
description: Body-layer plan review outcome — invariants held, but plan contradicted its own provenance rule in worked examples and asserted an open question as decided in a concept doc.
metadata:
  type: project
---

Reviewed `plans/body-layer/plan.md` (2026-09-07, planning-only, two opus Architect passes).
Verdict APPROVED WITH MINOR FIXES.

**The two findings worth generalizing:**

1. **A plan can state an invariant correctly in prose and violate it in its own worked example.**
   §1 required world-model provenance to be carried through to the brain; §3.4/§3.6 rendered
   `semantic` as bare strings. Prose sections and schema/example blocks in the same plan drift —
   check example payloads against the plan's own stated rules, not just against CLAUDE.md.
   See [[provenance_confidence_pattern]].

2. **Cross-file hedge drift.** An Architect pass that touches a plan *and* concept docs can leave
   the same question open in the plan and settled in the docs (here: SRS debounce/gate placement,
   open in plan §7/§10.5, asserted flat in `division-or-responsibility.md` and baked into
   `PETROBRAIN_RUNTIME.md`'s pipeline + PB-8). When a plan and concept docs are staged together,
   diff the open-questions list against what the docs assert.

**Milestone-ordering check that paid off:** BL-5 "freeze the tool set" listed tools whose
machinery three *later* milestones build (BL-5a, BL-6, BL-7). Reading a milestone's deliverable
against the API surface it claims to freeze catches inversions the milestone list alone hides.

**Structural note:** `plans/aircraft-layer/plan.md` is the house precedent for plans. The body plan
omitted its "Affected Modules / Files" section — worth checking any future plan carries it.

**Round 2 (same day):** 3 of 4 fixes fully resolved; the fix that added a *derivation table* to
replace a judgement call shipped with an unreachable row (top-down first-match order put a
narrower threshold below a broader one that subsumed it) and an over-broad first row. Generalizable:
**when a fix converts a vague field into a top-down first-match rule table, evaluate the rows in
order against edge cases — the ordering bug is the characteristic failure of that fix shape**, and
it is invisible if you only check that the table exists and references real fields.
