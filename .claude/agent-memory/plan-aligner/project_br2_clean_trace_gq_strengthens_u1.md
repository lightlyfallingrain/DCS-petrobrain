---
name: project-br2-clean-trace-gq-strengthens-u1
description: BR-2 plan traced cleanly (ALIGNED); gq.sh found stronger evidence for architect's own U1 recommendation than the architect cited
metadata:
  type: project
---

BR-2 (brain tool calls) plan checked ALIGNED 2026-10-31. All E1–E9 and all nine goal-check open
assumptions were traced to a named decision (D1–D9) or an explicit flagged user decision (U1–U4) —
no silence, no proxy substitution. Like [[project_bl_b104_clean_trace]], this happened because the
goal check (opus) had already run the open assumptions to ground via explicit user answers
(explore-notes.md A1–A10) before Architect wrote the plan.

**Worth repeating: running `gq.sh` on an architect's own "Recommend" line can turn up stronger
support than the architect cited, not just contradictions.** The plan recommended U1 (never call
the model on unprefixed/unanchored fallthrough) as its own judgment call, backed by A4/A10. A graph
query for the older inbound-speech routing design turned up `plans/inbound-speech/plan.md`'s
2026-09-19 "Two-tier routing" note (user-directed): unprefixed speech is "a command, matched
against this vocabulary" — no third path to the brain described at all for unprefixed text. That
makes U1 not a toss-up but close to the originally-intended design. Reported as a finding
(evidence lens), not filed away — it changes "recommend, ask the user" into "ask the user, expect
a quick yes."

**Why: `gq.sh` before "nothing found" isn't only a completeness gate; it can upgrade a weak
Recommend into a well-evidenced one**, and that is worth surfacing to the user even on an ALIGNED
verdict rather than only using the graph to hunt for CONCERNS.

**Also confirmed in this pass: a goal-check expectation (E1, "phrasebook untouched") can be
correctly *amended* rather than violated by a later user-answered decision (A4), and the architect
flagging this itself (as R7) rather than hiding it is the right shape.** The plan-aligner's job here
was to check the amendment is faithful to the user's actual words, not to treat "E1 changed" as
automatic grounds for CONCERNS.

See also [[project_bl_b104_clean_trace]] (why explore-notes pre-answering assumptions produces a
clean trace) and [[project_bl_b104_stage8_amendment]] (another case of a later decision legitimately
amending an earlier one).
