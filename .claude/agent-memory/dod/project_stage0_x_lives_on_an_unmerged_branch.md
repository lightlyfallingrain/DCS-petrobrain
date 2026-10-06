---
name: stage0-x-lives-on-an-unmerged-branch
description: A dispatching prompt said "Stage 0 is already [x]"; the [x] existed only on a second unmerged branch, so main's roadmap still read IN FLIGHT — check which branch a status claim lives on
metadata:
  type: project
---

**2026-10-06, `BL-11`.** The DoD task stated *"Stage 0 is already `[x]` from the other branch's
DoD"*. True of `fix/callout-observability-gate`, which had indeed passed DoD — and **false of
`main` and of the branch under gate**, where `body-layer/ROADMAP.md` still read
*"Stage 0 — ... IN FLIGHT as `fix/callout-observability-gate`"*. The `[x]` was sitting on the second
branch, unmerged, along with a live-acceptance-debt entry inserted at the top of the same list.

**Why it matters, concretely:** two branches editing the same milestone entry in one roadmap file
will conflict at merge. Having checked, the fix was to **scope the roadmap edits to the stages this
branch owns and leave Stage 0's paragraph untouched**, and to insert the new live-acceptance-debt
entry *away from* the other branch's insertion point (mid-list rather than at the top) so both
merge cleanly. Had the prompt been trusted, the natural move — mark Stage 0 `[x]` too — would have
produced a conflict on exactly the line two agents both rewrote.

**How to apply.** When a milestone has concurrent branches, a status claim is a claim *about a
particular branch*. Resolve it mechanically before editing a shared roadmap:

```sh
git branch -v --sort=-committerdate | grep -v 'worktree-agent-'   # what else is live
git show <other-branch>:<path/to/ROADMAP.md> | grep -n "Stage 0"  # where the [x] actually is
git log --oneline main..<other-branch>                            # has it merged?
```

Then edit only the paragraphs this branch owns, and choose insertion points the other branch is not
also touching.

This is [[feedback_verify_state_not_the_account_of_it]] applied to a *roadmap status* rather than
code, and the sibling of [[project_roadmap_edit_target_feature_vs_main]] — that one is about which
*base* to edit from, this one is about which *branch a claimed status lives on*.
