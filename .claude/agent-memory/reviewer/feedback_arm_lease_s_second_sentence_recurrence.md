---
name: feedback_arm_lease_s_second_sentence_recurrence
description: fourth confirmed instance of the generator-first-sentence-only gap (see [[feedback_verify_the_rendered_artifact_not_the_source_comment]]) -- BL-16 M1+M2 security-fix round's ARM_LEASE_S comment, not X-T26 -- the checklist step catches it only when actually run
metadata:
  type: feedback
---

BL-16 mode 1 M1+M2 perf/security change-request round (`plans/flight-control/`,
`4defba5e..307d6a81`), Security Finding B's fix: the implementer added a new second-sentence
explanation to `ARM_LEASE_S`'s `#:` comment in `body-layer/src/belief/flight_control.py` (why
`hi` dropped from 30.0 to 10.0, and the three-way coupling to `Export.lua`'s `FC_LIMIT_BOUNDS` and
the HTTP layer's own bound). The implementer's own check regenerated `config/defaults.toml` and
confirmed the **range number** (`0.5 .. 10.0`) rendered correctly -- but did not re-check whether
the **new sentence** survived the render. It did not: `generate_defaults.py`'s sentence-splitter
still only emits the first sentence, same as every prior instance. Caught in review by actually
reading the regenerated `config/defaults.toml` output, not by re-reading the diff.

**Why this is worth its own entry, not just a +1 on the X-T26 memory**: this is a different
module, a different plan, and a different (later) point in the project than the three X-T26
instances `[[feedback_verify_the_rendered_artifact_not_the_source_comment]]` documents. The
checklist step this role's own instructions name ("check the rendered file... three defects lived
in exactly that gap") was written specifically because of those three -- and it still took a
deliberate, separate regenerate-and-read step to catch a fourth, unrelated one. The lesson isn't
"watch `visibility.py`'s comments" (narrow and already stale) -- it's "every single `#:` comment
edit that claims new information for a tunable needs this check, every time, regardless of file
or round," because the implementer's own verification habit (confirm the number changed) does not
generalize to (confirm the prose changed) even when both were claimed in the same sentence of
their own implementation note.

**How to apply:** do not skip this check because "the X-T26 incident is old/fixed now" or because
the touched file isn't `visibility.py`. Any round that adds prose to a `tuning.*` declaration's
comment, anywhere in the codebase, gets the regenerate-and-read-the-actual-output step before
approval -- treat it as mandatory per-round, not per-incident.
