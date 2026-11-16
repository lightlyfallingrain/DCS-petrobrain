---
name: bl16-quick-path-misattributed-brief-quote
description: an implementer justified skipping a tolerance re-check by quoting "the plan's own" wording; the phrase was not in plan.md but in the main loop's dispatch brief -- trace a quoted citation to its real source (plan, brief, or nowhere) before judging it
metadata:
  type: project
---

Reviewing BL-16's "Revised 2026-11-16" takeover revision (`d3bfe9df`, `plans/flight-control/
review-takeover.md`): the quick correction path's second centre pulse (radar -> barometric)
resolved the whole takeover with no re-check that the resulting target was within tolerance of the
handover altitude. The implementer's comment and `implementation.md` justified this as "trusted per
the plan's own 'then go on to step 6's checks'".

**That phrase is not in `plan.md`**, current or history (`git log --all -p -S"step 6's checks"`
finds nothing). The review first recorded this as a fabricated citation. **Corrected by the main
loop the same day: the phrase came from the main loop's own dispatch brief to the implementer**
("If the reference reads R, pulse again → read. Then go on to step 6's checks."), which was
ambiguous. The implementer quoted the brief and attributed it to the plan. So: a misattribution plus
a loosely worded brief, not an invented quote. The required fix stands either way — the plan is
silent, the second-pulse target is evidenced by one sample, and an unchecked wrong target leaves
the aircraft with nothing correcting it.

**How to apply**: when a diff or its log attributes a choice to "the plan's own" wording, grep the
plan (and its history). If the phrase is not there, check the dispatching brief before calling it
fabricated — a brief can introduce wording the plan never had. Either way, the decision lacks the
plan's sanction and needs full scrutiny. Related but distinct from
[[bugfix-comments-citing-nonexistent-plan-md]] (citing a *file* that does not exist).
