---
name: cancel-then-promote-ordering-for-singleton-tasks
description: when fixing a "mint without cancelling the prior active task" bug by adding a cancel-existing loop, cancel unconditionally (including same-contact) and promote the new state strictly after, or the demote-then-promote ordering silently undoes itself
metadata:
  type: feedback
---

Found implementing BL-14's security deep-analysis required fix (`plans/attack-run/plan.md`,
`tools.attack_target_task`). The bug: minting a new singleton-selection task
(`attack_target`) without cancelling an existing active one left two tasks active, and every
reader resolved the oldest via `next(... not cancelled)` — see security's own memory
`insertion-order-task-lookup-hides-reselection` for the bug shape itself. This note is about a
trap in the *fix*.

**First attempt got the ordering wrong and would have demoted the freshly-selected contact.**
Writing "if an existing active task's contact differs, cancel it" and only then promoting the new
contact to its priority attention level looks safe, but breaks the moment the "new" selection is
actually the *same* contact as the existing task (an ordinary re-select, not an edge case a pilot
would avoid): skip-cancel-on-same-contact plus promote-after leaves it fine, but skip-cancel is
easy to get backwards, and if cancel runs unconditionally *after* a conditional promote, the
cancel's own "always demote to normal" effect undoes the just-set promotion.

**The ordering that is actually safe regardless of overlap**: (1) confirm the new target exists
with no side effect first (so a bad reselection can't destroy a good existing selection to make
room for a failed one), (2) cancel *every* currently-active task of that kind unconditionally —
including one that already names the same contact — (3) only then set the new contact's promoted
state. Cancel-before-promote, not promote-before-cancel or skip-cancel-on-match, is what makes the
same-contact case a correct no-op instead of a demotion. A dedicated test reselecting the *same*
contact twice (not just two different contacts) is the one that catches the wrong ordering — it
passed silently with the wrong ordering until that specific case was tried.

**How to apply:** any time a fix adds "cancel the existing active X before creating a new X" to
close a singleton-task resolution bug, write the same-identity-reselection test, not just the
different-identity one, and check which order cancel-vs-promote runs in.
