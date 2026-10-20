---
name: entry-gate-vs-continuation-gate-share-one-predicate
description: When a user-requested fix widens a "worth starting" gate, grep for a sibling "worth continuing"/"is finished" function built on the exact same underlying predicate — fixing only the entry gate can silently reintroduce the defect one poll later, with a less obvious symptom.
metadata:
  type: project
---

Found 2026-10-20 reviewing `feature/9k113-narrow-search` (`plans/9k113-narrow-search/review.md`).
A mid-review user direction asked for a fix to `body-layer/src/belief/optic_policy.py`'s
`is_worth_a_look` (gates which contacts become sight-look *candidates*) — it was built on
`can_still_improve`, hardcoded to the naked-eye/binocular optic pair, so a contact beyond
binoculars' own reach was never admitted and the 9K113's narrow setting was never triggered live.

**The same `can_still_improve` call also lives inside `look_is_finished`** (a sibling function,
same module), which governs whether an *already-started* look continues past its first poll. If
only the entry gate (`is_worth_a_look`) is widened, a newly-admitted far contact gets picked on
poll N, and on poll N+1 `look_is_finished` evaluates the *same unwidened* predicate, finds the
contact already outside the old window, and reports the look finished — one poll after it started.
Worse, the "finished" path in this codebase commits retry/attempted-at bookkeeping as if the look
had actually resolved something, which then suppresses re-selection for a retry interval — quietly
reintroducing the exact defect the fix was meant to close, one poll later and much harder to
notice in a quick manual test (a target *does* get picked; it just never actually completes).

**How to apply.** Whenever a review involves widening or redirecting a gate function (anything
named `is_worth_*`, `can_*`, `*_is_finished`, `should_*`), grep the whole module for every other
call site of the predicate it delegates to, not just the one site the request named. A state
machine's "start" and "continue" questions are usually two functions sharing one answer, and a fix
aimed at only one of them is a half-fix that looks complete in isolation. This is the same shape as
the project's standing "cross-key couplings" tuning check and the "parallel treatment across
sibling files" grep rule in `.claude/agents/reviewer.md` — generalize it to sibling *functions*
within one file, not only sibling files.
