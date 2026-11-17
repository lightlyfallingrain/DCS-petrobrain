---
name: project_bl17_stage3a_fuzz_cycle_and_test_list_defect
description: BL-17 Stage 3a (speech-rules matching foundation, D13/D14/D15) -- the shared _WORD_REPAIR_FLOOR constant has to live in vocabulary.py (not either matcher module) to avoid a real import cycle, and the Stage 3a test list's own "turn lift two zero" example contradicts E12 in the same sentence.
metadata:
  type: project
---

BL-17 Stage 3a (`plans/speech-rules/plan.md` D13/D14/D15) landed on
`feature/speech-rules-matching`. Two things worth knowing before touching this area again:

1. **A constant two modules both need, where one must never import the other, goes in a third
   module both already depend on -- not in either module "canonically."** D13 said `rule_patterns.
   py`'s new literal fuzz should reuse `command_matcher._WORD_REPAIR_FLOOR` "imported from
   `command_matcher.py`." That is a real cycle: `command_matcher.py` imports `rule_patterns`
   (for D8's rule-matching branch) at the top of its own file, before any of its own constants are
   defined, and `rule_patterns.py` would need to import a name from `command_matcher` that is
   likewise defined after ITS import statement -- genuine regardless of which module is imported
   first (prior implementer memory, `project_bl17_rule_matcher_cycle_and_scoping.md`, already
   flagged the sibling case: `rule_patterns.py` must never import `command_matcher.py` at all).
   Fix: relocated `_WORD_REPAIR_FLOOR` to `vocabulary.py`, which both modules already import
   from and which imports neither. Same value, same name, one declaration site -- satisfies the
   plan's real intent ("not a second hand-tuned number") without the cycle. **Generalizes**: when
   a plan says "import X from module A into module B" and A and B have a *mutual* import
   relationship (not just A importing B), check for the cycle before building it, and look for the
   shared-ancestor module to put the constant in instead.
2. **A plan's test-list example can contradict its own stated invariant in the same sentence,
   not just elsewhere in the document.** Stage 3a's own item 1 said: "a mis-transcribed literal
   ('turn *lift* two zero') still matches; 'right' is never fuzzy-repaired into a slot value
   anywhere (E12 pin)." But in the shipped `turn_heading_relative` pattern, "left"/"right" are a
   `WordSetElement`'s own *values*, not a `LiteralElement` -- and E12 (confirmed in
   `alignment.md`'s own resolution table, "a `SlotElement`/`WordSetElement` never gets the fuzzy
   fallback") says values must be heard exactly. Measured: `ratio("lift","left")=0.75` (would
   only match if word-sets were fuzzy, which they must not be), `ratio("lift","turn")=0.25`
   (nowhere near the literal "turn"). The example only parses as a word-set fuzz, which the very
   next clause of the same sentence forbids. This is the **same defect shape** the plan-aligner's
   own memory (`project_bl17_test_list_claims_a_fix_its_own_exclusion_rules_out.md`) found in an
   earlier check of this same revision -- a test-list sentence restating the planner's belief
   rather than being independently checkable. Resolved by computing both ratios before writing
   any test, then writing two tests: the literal fuzz against the rule's real literal ("turn" ->
   "turm", 0.75, matches) and a dedicated E12 pin ("turn lift two zero" does **not** match).
   **How to apply**: whenever a plan's test list names a specific garbled phrase as proof a
   mechanism works, identify which *element type* (literal vs. slot vs. word-set) the garbled
   word sits in before trusting the sentence -- a near-miss on a word-set/slot *value* and a
   near-miss on a *literal* look identical in prose but are governed by opposite rules here.

Also found, not a plan defect but worth knowing: "tern" (a plausible mis-hearing of "turn")
scores *exactly* `VERB_FLOOR` (0.5) against `step`'s own verb anchor, so once `match_transcript`
stopped early-returning on a rule match (D13's own cross-pipeline requirement), "tern left two
zero" genuinely anchors both `turn_heading_relative` and legacy `step` at once (`step` wins
outright, gap 0.25). Pick a different mis-transcription for a rule-only fuzz test ("turm" instead
of "tern") and keep the real collision as its own documented test rather than discarding it.
