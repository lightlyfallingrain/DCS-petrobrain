---
name: project_bl17_test_list_claims_a_fix_its_own_exclusion_rules_out
description: BL-17 Revision 2 (speech-rules) — a stage's own test list and flight card asserted "turn left thirty" would resolve, while that same revision's decision text explicitly excluded the slot type that would need to change; caught by reading D14's exclusion list against Stage 3a/4's test/card claims, then confirmed against the shipped parser.
metadata:
  type: project
---

BL-17 Revision 2's Stage 3a test list ("turn left thirty"/"Turn left, 30."/"turn left three zero"
all resolve, "closing the Reviewer-flagged gap") and Stage 4's flight card both asserted "turn left
thirty" (the user's own canonical example for wanting number-word support at all) would work. But
D14 explicitly said "`heading`, `angle`, `oclock` are **not** touched" by the new number-word
grammar, and Stage 4 item 2 confirmed `turn_heading_relative`'s `degrees` slot stays `<angle>`.
D13's fuzzy-literal fallback explicitly never applies to a `SlotElement`. So nothing in the
revision actually taught "thirty" to parse as 30 in that slot — the test list's claim and the
decision's own exclusion directly contradicted each other. Confirmed against the shipped
`audio-adapter/src/rule_patterns.py:220` (`"angle"` → `_consume_angle` → `_consume_digit_run` only,
no number-word branch).

**Why this matters:** a plan's test list and flight card are not independent evidence that a stage
works — they can just be the planner's (mistaken) belief restated. The planner reasoned "D13's
literal fuzz closes the Reviewer-flagged gap" without noticing the gap's root cause was a slot-level
grammar limit (D14's territory), not a literal-matching tolerance problem (D13's). A near-miss on a
*word in a slot* and a near-miss on a *literal* look superficially similar ("the pilot said
something slightly different and it still worked") but are fixed by entirely different mechanisms,
and the plan conflated them.

**How to apply:** when a stage's test list or flight card names a specific phrase/example as
"resolved," trace which D-decision's mechanism is supposed to produce that result, and check that
decision's own stated scope (inclusions *and* exclusions) actually covers it — don't take the
test-list sentence as proof. When the phrase is also a slot value (a number, a direction), check
which slot type the pattern uses for it and whether that type's own grammar changed in this
revision, independent of any literal-matching fuzz decision. A quick grep of the shipped parser
(one line) settled this one conclusively rather than arguing from the plan text alone — cheap
and worth doing whenever a contradiction like this is suspected.

See [[project_bl17_user_decision_narrows_e5_and_grep_derisks_r7]] for the sibling lesson from the
same feature (grep de-risking a plan's stated risk) — this is the same habit applied the other
direction: grep to *find* a plan's own internal contradiction, not just to de-risk one it already
names.
