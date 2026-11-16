---
name: bl16-comoving-table-missed-amendment
description: a plan's Co-moving Fields table and its own "grep once this stage lands" instruction were both written before a later "Amended" sub-section added new state fields -- the amendment never updated the table, and the implementer never ran the grep the plan asked for
metadata:
  type: project
---

BL-16's "Revised 2026-11-16" plan section has a Co-moving Fields table (fields written by the
original 5-step takeover sequence) immediately followed by an explicit instruction: "Implementer's
grep, once this stage lands... confirm every write site matches a row here, and extend the table
with any that does not" -- citing `BL-B71`'s fourth construction site (found only by grep) as the
precedent this guards against.

The plan was then amended the same day ("Amended 2026-11-16 -- after the takeover rehearsal
probe"), which replaced part of the sequence with a quick correction path carrying its own new
state (`correction_substage`: `"quick_read1"`/`"quick_read2"`, plus a `correction_path = "quick"`
write). **The amendment never touched the Co-moving Fields table above it, and the implementer
never ran the grep the plan asked for** -- no grep result appears in `implementation.md`, and
`plan.md` carries no commit between the pre-implementation tip and the three implementation
commits. I ran the grep myself (`grep -n "correction_substage\s*=\|correction_path\s*="
Export.lua`) and found real write sites with no table row -- the exact failure mode the plan's own
citation warns about, recurring in the same plan that named it.

The code itself was internally consistent when traced by hand; this was a documentation-debt
finding, not a functional defect, but it was a plan-mandated step that was skipped, so it went in
`review-takeover.md` as a required fix (extend the table / record the grep) rather than optional.

**How to apply**: when a plan has an explicit "run this grep before merging" instruction attached
to a table, don't just check whether the table is internally consistent with itself -- check
whether the table predates a later amendment in the same plan file (section headers with dates are
the tell) and re-run the instructed grep yourself if the implementation log doesn't show it was
run. A table and the amendment that outgrew it can both look complete on their own.
