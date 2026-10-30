---
name: project-bl-b104-stage8-amendment
description: BL-B104's Stage 7/8 amendment traced cleanly to the user's verbatim growth-rate rule; one partial gap on "flights" plural accepted because the review's own required-fix bar was looser than the user's literal wording
metadata:
  type: project
---

The Stage 8 (motion-aware growth) + Stage 7 (Turn leg) amendment to BL-B104 checked ALIGNED,
mapping each clause of the user's verbatim rule (`explore-notes.md`, "E5 fold on a closing
run — decision") to one line of `contact_growth_rate_mps`: not-observed-moving (`None` or
`"stopped"`) → tiny rate; observed moving → class-table rate; "most typical case is stationary"
→ `None` folded in with `"stopped"` rather than kept separate. The plan was also honest that the
fold-fix itself is an order-of-magnitude argument, not yet demonstrated against the real scenario
— named its own follow-up condition rather than claiming "fixed."

**One partial finding worth remembering the shape of:** review.md's Required Fix for "no
manoeuvre anywhere" accepted *"add a leg with real lateral/attitude change ... to at least one
scenario"* as sufficient, but the user's own words were plural — *"mock flights that still
contain some aircraft manoeuvre."* The amendment satisfied the review's bar (fixed 2 of 4
scenarios) without re-checking it against the user's literal plural. **This is a shape to watch
for generally**: a Required Fix can accidentally relax a user's own wording when it translates it
into an engineering acceptance criterion, and a later amendment that satisfies the Required Fix
can still under-satisfy the original sentence. Worth a line back to the user rather than assuming
the review's translation was exact — treated as non-blocking here since it's test scaffolding
with no cockpit-facing effect, but would not be non-blocking if the same gap existed in
behavioural code.

See also [[project_bl_b104_clean_trace]] — the main-line Stages 1–5 trace, which had no gaps.
