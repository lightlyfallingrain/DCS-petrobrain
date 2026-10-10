---
name: a-fix-can-merge-while-its-own-entry-reads-open
description: When the entry for the defect being fixed lives on a sibling branch, the fix can merge with its own backlog item still open — state the merge order, and check the acceptance card's checkout line names a branch that has the fix
metadata:
  type: project
---

**A fix whose backlog entry lives on another branch can merge onto the trunk while that entry still
says the defect is open — and nothing will ever correct it.** The mirror image of
[[feedback_do_not_mint_an_id_when_siblings_live_on_another_branch]]: that one is about *filing* an
id you cannot see, this is about being unable to mark **done** the entry for the very defect you
just fixed.

**Why:** on `fix/air-defence-class-level` (2026-10-10, `BL-B47`) the branch's
`body-layer/ROADMAP/` maxed at `BL-B46`, while `BL-B47`–`BL-B54` sat on
`chore/file-bl13-review-findings`. Declining to mint is correct and already covered. What is *not*
covered is the consequence: `BL-B47.md` is `[ ]` / `#status/open` on a branch the fix does not
contain, so merging the fix alone leaves `grep '#status/done'` reporting the defect open forever —
the entry file is the only place status lives, and `push-roadmap-gate.sh` is satisfied by any
`ROADMAP.md` being touched. **Second occurrence of this branch-split situation in one session.**

**How to apply.** When the entry is absent from your worktree, do not treat it as a bookkeeping
footnote — make it a condition of the pass. State the **merge order** explicitly in `dod-check.md`
and in the report (chore branch first, then the feature, then the fix), and say what has to be
written to the entry file afterwards, in its own worktree.

**The second half, which is easy to miss: the acceptance card's checkout line.** The same split
means the card on the sibling branch names a branch that **does not contain the fix** — a pilot
following it judges the new behaviour against the old code. Check which branch actually carries both
before trusting the card's own command: `git log --oneline <yours>..<sibling>` and then
`git show --stat` on each commit it lists. On `BL-B47` the three commits the fix branch lacked
touched no `src/` or `tests/` file at all (review prose, DoD report, card), so the *fix* branch held
all of the feature's code plus the fix and was the only single checkout that could fly both — the
opposite of what the card said. Related: [[project_main_doc_describes_unmerged_branch_behaviour]].

**Also expect a tail conflict in `NOTES.md`.** Both branches' DoD harvests append at the end of the
file, so the second merge conflicts there. The resolution is always "keep both, in order" — say so
in the report rather than letting the merge discover it.
