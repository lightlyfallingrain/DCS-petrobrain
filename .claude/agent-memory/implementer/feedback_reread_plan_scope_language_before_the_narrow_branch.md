---
name: feedback_reread_plan_scope_language_before_the_narrow_branch
description: A plan sentence like "written whenever X happens for any reason" is scoping language, not a hint attached to the one branch that made you think of it -- the first, narrower implementation that only satisfies the branch you were looking at when you read it is a common miss.
metadata:
  type: feedback
---

Found during `raster-chart-viewer` Stage 3 (`cache.py`'s `compose_view_tile`,
`plans/raster-chart-viewer/plan.md`, "Cache" section: *"Written whenever an entry is inflated for
any reason, and by the warm-up"*). My first draft populated the small-mip cache only on the branch
that was already checking the small-mip cache (`mip >= SMALL_MIP_MIN`) — the one case I was
focused on while writing that branch. Rereading the sentence afterward: "for any reason" plainly
includes the middle-zoom and full-res branches too, which read an entry's bytes just as much and
were simply discarding the opportunity to populate small mips from that same read.

**Why this is an easy miss:** the sentence is physically written in the section about the
small-mip cache, so it reads, at a skim, as a detail of *that* cache's own population path. It is
actually a scope statement about every call site that inflates an entry, which is a broader claim
than the paragraph's own heading suggests.

**How to apply:** when a plan uses "whenever X" / "for any reason" / "every time Y happens"
language, before writing the code, list every call site or branch where the triggering condition
(here: "an entry is inflated") can occur — not just the one the surrounding prose is nominally
about — and check the implementation covers all of them. Caught this time before committing, by
writing the test cases from the plan's own acceptance wording first ("a request at k >=
SMALL_MIP_MIN after any inflate of the entries it covers opens none either") and finding the
narrower implementation failed a test built from a *different* branch than the one I'd been
reading the sentence against.
