---
name: card_branch_name_goes_stale_at_merge
description: a test card/acceptance doc naming a feature branch is correct when published but goes stale the moment that branch's content merges to main -- check and republish at DoD time, do not trust the plan's input-file list
metadata:
  type: feedback
---

`BL-B67` batch A's Stage 0 test card and `docs/acceptance/2026-10-29-bl-b67-stage0-probe.md` both
named `feature/bl-b67-atgm-run` — correct when the Reviewer pass published them, before batch A
existed as a merge candidate. By the time this DoD pass ran, the probe `.lua` files the card
instructs the user to copy were part of batch A's own diff, about to land on `main`. Flying the
card as written would have the user `git checkout feature/bl-b67-atgm-run` — a branch that gets
harvested/deleted once merged, per this project's worktree protocol — instead of `main`, where
the files actually are after this DoD's merge.

**Why this needed reading the live card, not trusting the dispatch's input-file list**: the DoD
dispatch listed the card and the acceptance doc as inputs to confirm "are present" — it did not
ask whether their *content* was still accurate against this report's own action (merging to
`main`). Reading the published artifact via `Artifact action: "read"` (not just grepping the local
`docs/acceptance/*.md` copy, which held the same stale text) is what surfaced it — this is the
same standing rule ("run every command before you write it down," "state the tip sha your verdict
is scoped to") applied to an acceptance card instead of a shell command: a card's instructions are
a claim about the world at the moment they were written, and a DoD pass that moves the world (by
merging) can falsify its own inputs.

**General rule for this role**: whenever a DoD pass is about to merge a branch whose diff a
published test card or acceptance doc refers to by branch name, re-read the card itself (not just
confirm the file exists) and check whether the branch name it gives is still the one the user
should check out *after* this merge. If it names the feature branch and this DoD is merging that
branch's content to `main`, update both the doc and the card (republish to the same URL, same
`action: "publish"` call with `url` set) before writing the final report — the fix is cheap and
the alternative is the user's first action on the card failing.
