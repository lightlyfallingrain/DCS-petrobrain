---
name: bl13-selective-freshness-marker
description: BL-13 round 3 — a hedge attached to the clause that names a thing is dead whenever that clause is suppressed; and which air-defence predicate is the live one.
metadata:
  type: project
---

Round 3 of `feature/bl13-crew-query-path`: `speech._summary_air_defence_freshness_clause`, the
selective freshness marker in `render_report_summary`.

**Two non-obvious things, both of which would have shipped as silent dead code.**

1. **"Attach the marker to the clause that survives the budget" is not sufficient, because that
   clause is sometimes absent.** The brief said to ride along with
   `_summary_air_defence_clause`, which does survive both word-budget drops. But that clause
   **suppresses** any tier the dominant-class clause already named, and when the dominant class
   folds into the count (`"Two short range SAMs"`) there is no air-defence clause at all — so a
   marker hung off it would be missing in precisely the all-SAM scene. The marker therefore names
   its own subject and is appended in *every* budget candidate. **Before attaching anything to an
   existing clause, enumerate the cases where that clause returns `None`.**

2. **`speech` has two air-defence predicates and only one works on a class-level belief.**
   `_is_air_defence` resolves via `object_model.profile_for`, which keyword-matches DCS *type*
   names — `profile_for("OP_SRSAM")` falls to the default bucket, so it does **not** recognise a
   class-level SAM (`BL-B47`). `_summary_op_class` walks `classification.parent_class_of` and does.
   `_summary_air_defence_clause` already used the correct one and says so in its docstring; the fix
   inherited it. Reaching for the obvious `_is_air_defence` would have been dead in the target
   scene with every test green.

**The marker pushes the measured scene to 28 words against `REPORT_SUMMARY_MAX_WORDS` = 25.** That
is designed — it buys room by forcing the deferral and the dominant class out, and nothing below
count/direction/band exists to drop. If that budget is ever halved as its own comment anticipates,
this is now a **second** never-dropped clause to re-read.

Related: [[feedback_an_honesty_marker_can_be_a_new_false_claim]] (why the user's exact phrase could
not be used at every age), [[project_bl13_crew_query_path]] (rounds 1–2).
