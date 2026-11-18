---
name: project-bl16-mode1-recut-u6-reopens-settled-e9
description: BL-16 mode-1 re-cut (2026-11-18) traced cleanly except U6, which frames an already-settled expectation (no optics while flying) as a fresh symmetric choice whose "alternative" ships a known regression
metadata:
  type: project
---

BL-16's mode-1 (unparked, raw-axes) re-cut traced cleanly against the 2026-10-31 goal check: all
ten E-expectations met or correctly deferred, and all five open assumptions / eight Q&A pairs from
that goal check were closed by a later, named user answer (A1-A9 in `explore-notes.md`). One
exception: **U6** ("build 'no optics while flying' now, for both modes, as part of M1?") is
written as a neutral 50/50 architectural choice with a recommendation, but its own text shows the
"alternative" branch ships mode 1 in direct contradiction of E9 — which the *original* goal check
already listed as **settled** (point 2, decided at the explore stage, not reopened by anything
since) — and of a standing user rule quoted verbatim in `todo/todo/X-T29.md` priority 3 ("no optic
can be used" in either mode). A `grep` of the live tree confirmed the factual claim behind U6
(`optic_policy.py` has no `flying`/`has_controls` input today) — the gap is real, not fabricated,
which is what let this be a Finding (CONCERNS) rather than a dismissal.

**Why this matters generally:** a later plan re-cut can correctly carry forward an old decision's
*conclusion* while accidentally reopening it as a *fresh choice* in the "Decisions Requiring User
Input" section, because the re-cut's own rationale ("it's about one input," "generalises cleanly")
reads as architecture, not as re-litigating something the player already has a right to expect.
The tell is: does the stated "alternative" to the open `U<n>` describe a ship state that
contradicts an E already marked "Settled" in an *earlier* goal check for the same feature? If yes,
this is not an ordinary open decision (which U5/U7/U8 all genuinely were, in the same plan, and
were left as plain restated questions) — it needs its own Finding, because silence from the user
on `U<n>` would read as "deferred, no harm" when it is actually "ship with a known regression."

**How to apply:** when a `deferred → U<n>` row's target decision has an "alternative" that
describes shipped behaviour contradicting an already-settled E from the same or an earlier goal
check, don't just mark the row `deferred` and move on — grep the live code to confirm the claimed
gap is real, then write a Finding naming the earlier-settled E and the standing-rule document (a
roadmap entry, a `todo/` priority list) that restates it, and recommend the user actually resolve
the decision (not leave it open) before the stage that ships it merges — auto-merge-on-DoD-pass
means an unresolved `U<n>` left at its stated default can go live the same day it passes.

See also [[project_bl_b111_decision_narrows_just_answered_expectation]] (a different shape: an
open `U<n>`/Decision narrowing an expectation the goal check had just answered) and
[[project_bl16_hvrt_unreachable_by_voice]] (an expectation that looked closed on paper but had no
live path to it at all).
