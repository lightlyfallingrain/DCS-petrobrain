---
name: recurring-approved-plan-wrong-on-real-data
description: 2nd occurrence this week of a reviewed, approved design that only broke against real sortie/tile data, never a fixture
metadata:
  type: project
---

`contact-report-flood` (2026-10-05): the plan's literal `CONTACT_DETECTED` suppression check,
implemented as specified and passed by Architect review, silenced *every* contact in a same-poll
mutually-close cluster — the opposite of the plan's own "at most 2, not 6" bound — found only by
running the real scheduler against a real sortie snapshot, never by a synthetic fixture.

Same week, same shape: `landform-geomorphons` performance work — a design (Chaikin-smoothing
deviation check) that passed review broke only when profiled against a real tile; the plan's own
risk assessment had flagged the wrong step as dominant cost.

**Process signal, not code debt**: this is the second time in one week that real data, not review,
caught a design flaw that had already cleared Architect/Reviewer sign-off. If a third instance
appears, consider whether Architect should require a real-data sanity pass (not just a fixture)
before approving any plan whose correctness depends on per-batch/per-poll behavior or on
measured-not-assumed cost — i.e. push a cheap probe earlier in the sequence rather than relying on
Implementer to discover it empirically each time.

See NOTES.md "Planning & Process Lessons" for both worked examples.
