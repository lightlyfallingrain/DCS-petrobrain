---
name: project_bl16_m3_answered_decision_not_backfilled_into_risks_card_tests
description: BL-16 M3 terrain floor — U22 answered against the recommendation; the design sections were updated but the Risks bullet, one card row and the Tests section still read as if the recommendation had landed.
metadata:
  type: project
---

BL-16 M3 (terrain floor and look-ahead) landed U20 (ease-down cap 10 m/s, not the recommended 5) and
U22 ("every climb trades speed," not the recommended "terrain only") after a diagram review, and the
Architect correctly rewrote sections A–F, the diagrams and the Co-moving table to the answered
values — no stale number or branch survived there.

**What a plan-wide grep for the old number/branch missed on a first pass**: three spots outside the
design sections still assumed the *recommendation*, not the answer:
1. A Risks bullet ("big climbs go to available power (U22)") — exactly what "terrain only" would
   mean, the opposite of what was answered.
2. One card row ("speed per U22") — written generically to survive either answer, so it never got
   filled in with the concrete behaviour once the answer landed, unlike every sibling row.
3. The Tests section had no toy-plant case for the *specific* scenario U22's answer added (an
   ordinary, non-terrain climb trading speed) — only the terrain-bound case (E2) was tested, so a
   future regression narrowing the governor's lead back to the "terrain only" shape would pass every
   existing test.

**Why this matters generally:** a `U<n>` answered against its own plan's recommendation is a signal
to re-grep the *whole* amendment for that `U<n>`'s name, not just the Decisions section and the
design body — Risks, card rows and Tests cite `U<n>` by number too, and a bullet that cites the
decision without restating its content is exactly the kind of text that silently drifts when the
decision changes. A vague card-row phrase ("X per U<n>") is a tell: compare it against sibling rows
that do state the concrete expected reading.

See also [[project_bl_b111_decision_narrows_just_answered_expectation]] and
[[project_bl17_user_decision_narrows_e5_and_grep_derisks_r7]] for the sibling pattern (a decision
narrows/changes an expectation and the trace has to follow the decision, not the plan's first
draft).
