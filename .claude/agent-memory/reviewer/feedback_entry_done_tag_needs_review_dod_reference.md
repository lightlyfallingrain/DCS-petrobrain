---
name: entry-done-tag-needs-review-dod-reference
description: An entry marked #status/done without naming a Reviewer verdict or DoD sha is premature -- check against sibling entries on the same branch, not just the tag definition
metadata:
  type: feedback
---

An Implementer marking a ROADMAP entry `[x]`/`#status/done` right after writing the code, with no
Reviewer verdict and no DoD sha cited, is a recurring shape to catch -- `docs/TAGS.md` itself only
says `#status/done` means "complete as specified," which an Implementer's own code can satisfy
before anyone else has looked at it, so the tag definition alone does not catch this.

**Why it matters:** on `feature/bl16-lift-vector-law`, `BL-B139.md`/`BL-B140.md` (built the same
week, same branch) stay `#status/in-progress` + `#needs-flight` specifically because they are
unreviewed/unflown, while `BL-B141.md`/`BL-B117.md` (reviewed in this pass) were marked
`#status/done` by the Implementer with no Reviewer/DoD reference at all, on an un-merged commit.
The established pattern elsewhere on the same roadmap file (`BL-16.md`'s own batch entries) is
"done" always cites a Reviewer verdict and a DoD-passed sha ("DoD PASSED, merged `<sha>`"), with
`#needs-flight` added once merged but unflown. A tag-definition read alone would have missed this
("complete as specified" is arguably true of the code).

**How to apply:** when an entry under review already claims `#status/done`, before accepting the
wording, grep sibling entries in the same `ROADMAP/` directory (especially ones on the same
feature branch, built around the same time) for the actual pattern this project uses to record
"done" -- does it cite a Reviewer approval and a DoD sha, or just "implemented per plan"? A
numbering/wire-protocol change that unit tests alone cannot prove behaviourally safe (the plan's
own "no-op for the player, by design" framing is exactly this shape) is a required fix to flag,
not optional phrasing: ask for `[~]`/`#status/in-progress` until Reviewer+DoD actually land, then
`[x]` with the DoD sha and `#needs-flight` for the live-acceptance debt.
