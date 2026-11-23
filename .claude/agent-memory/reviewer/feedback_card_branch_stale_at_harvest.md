---
name: card-branch-stale-at-harvest
description: a test card naming the implementer's own disposable worktree branch (impl/<stage>) goes stale the moment that branch is harvested onto the feature branch -- check git branch -a for the named branch's existence, not just that the card names *a* branch
metadata:
  type: feedback
---

BL-16 LV-0 review (2026-11-23, `feature/bl16-lift-vector-law`, review-lv0.md): the implementer wrote
`docs/acceptance/2026-11-23-bl16-lv0-card.md` naming "Branch to fly: `impl/lv0`" with a conditional
fallback ("if already harvested, fly `feature/bl16-lift-vector-law` instead"). By the time the card
landed in the same commit that also harvested the work onto the feature branch, `impl/lv0` was
already gone (`git branch -a` showed no trace, local or remote) -- the card's *primary* instruction
was already wrong at the point the user would read it, not just eventually stale.

**Why this is a distinct check from [[feedback_card_branch_name_goes_stale_at_merge]]` (DoD's own
memory)**: that one is about a card going stale *after* this review, at merge-to-main. This one is
about a card that was *already* stale at the moment of review, because the implementer named their
own disposable `impl/<stage>` worktree branch (deleted at harvest, same session) rather than the
feature branch the work actually lives on by review time.

**How to apply**: when a card names an `impl/<stage>` or any agent/implementer worktree branch
(as opposed to the feature branch), run `git branch -a | grep <name>` before approving. If it does
not exist, the card's primary instruction is wrong now, not just eventually -- a conditional
fallback sentence in the card does not fix this, since the user has no way to know which branch
"has already been harvested" without running the same check. Required fix: the card should name
whatever branch *currently* carries the work, full stop, not the implementer's own transient
worktree branch with a conditional escape hatch.
