---
name: do-not-mint-an-id-when-siblings-live-on-another-branch
description: Minting a BL-B/X-B id from inside a feature worktree collides when the previous numbers were filed on a sibling branch; name the finding and let the orchestrator file it after that branch merges
metadata:
  type: feedback
---

**Do not mint a new backlog ID from inside a feature worktree without checking the other branches
first.** The mint command (`ls <dir>/ | grep -oE '^BL-B[0-9]+' | sort -V | tail -1`) is only correct
about the tree it runs in.

**Why:** on `feature/bl13-crew-query-path` (2026-10-10) the DoD pass found a real backlog-worthy gap
(the `report` *what* slot accepts seven singular words, so the user's own vocabulary — "trucks",
"air defence", "armour" — silently drops the filter). That branch's `body-layer/ROADMAP/` maxes at
`BL-B46`, so the mint would have produced `BL-B47`. But `BL-B47`, `BL-B48` **and** `BL-B49` already
existed on `chore/file-bl13-review-findings`, filed from the same feature's own review and security
passes. Minting would have created exactly the colliding ID the never-reuse rule exists to prevent,
and the collision would only have surfaced at merge — as two different items answering to one
number in two commit messages.

**How to apply.** Before minting, `git log --all --oneline --grep="<prefix>-B"` and
`git branch -a --contains <sha>` on anything it turns up. If a sibling branch holds higher numbers,
**do not mint**: name the finding in `dod-check.md` with the number it *should* take, say which
branch has to merge first, and leave the filing to the orchestrator. A named finding with no ID is
recoverable; a duplicated ID is not.

**Corollary worth stating in the DoD report itself:** a feature's escalations are often filed on a
separate chore branch, so *"filed as `BL-B49`"* is not the same as *"on `main`"*. Say which branch
carries them and that it must merge with or before the feature — otherwise the trunk gets the
feature and none of its recorded consequences. Related: [[feedback_verify_roadmap_prose_claims]].
