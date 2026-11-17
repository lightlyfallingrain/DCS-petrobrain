---
name: project_bl17_slot_type_grammar_words_never_reach_whisper_prompt
description: BL-17 Stage 3a -- rule_patterns.rule_words() only walks a rule's LiteralElement/WordSetElement words into the whisper prompt bias; a SlotType's own grammar words (D14's new number-word vocabulary -- "thirty", "hundred", etc.) never reach vocabulary.recognised_words()/to_prompt() at all, so whisper has zero bias toward the words the matcher was just taught to accept.
metadata:
  type: project
---

BL-17 Stage 3a (`plans/speech-rules/plan.md` D14) added `quantity`/`speed_target` slot types and
widened `angle` to accept composed English number words (teens, tens, "hundred"). `rule_words()`
(`rule_patterns.py`, feeding `server.py`'s `extra_words` into `vocabulary.to_prompt()`, D10's own
mechanism) only walks `LiteralElement`/`WordSetElement` words -- its own docstring says a slot's
value words "are already covered by `vocabulary.py`'s own digit/time words," which was true when
the only slot types were `angle`/`heading`/`oclock` (needing only 0-9 and `o'clock`, both already
in `vocabulary.py`'s tables) and became **false** the moment D14 added number words that exist
nowhere in `vocabulary.py`.

Verified directly, not inferred: `rule_words(turn_heading_relative_rule) == ['turn', 'left',
'right']`; `'thirty' in to_prompt(['turn', 'left', 'right']).lower()` is `False`. So "turn left
thirty" -- the user's own canonical example, the reason D14's "Corrected 2026-11-17" note exists
at all -- is parsed correctly by the matcher but whisper is given no bias toward hearing "thirty"
right in the first place. This is exactly the project's own named failure class
("silence"->"violence", `audio-adapter/CLAUDE.md`), and `test_vocabulary.py`'s own prompt-coverage
tests (`test_prompt_carries_every_word_of_every_phrasing`/`test_prompt_carries_every_slot_word`)
are structurally blind to it: both check the prompt against `vocabulary.py`'s own tables, and
these words never reached those tables, so there is nothing for the test to fail against.

**Why this nearly got missed**: the Implementer's own test list and `implementation.md` account
covered parsing correctness exhaustively (every Q10 form, both rejections, the digit/word-phrase
override) and the project's standing vocabulary-sync rule is phrased as "a word the matcher acts
on belongs in one of these tables" -- but "these tables" means `vocabulary.py`'s, and a slot
type's *own* grammar (declared entirely inside `rule_patterns.py`, a different module, with its
own `consume`/`sample` per type) is a second place new spoken vocabulary can be born that the
standing rule's own enforcement mechanism (`test_vocabulary.py`) cannot see. Reading the diff and
the tests would not have caught this -- it took actually calling `rule_words`/`to_prompt` on the
real shipped rule and checking the output string for the new words.

**How to apply**: whenever a plan adds a new `SlotType` (or widens an existing one) whose `consume`
accepts spoken words that are not already digits/`o'clock`/an existing `vocabulary.py` table, check
whether those words reach `to_prompt()` through *some* path -- not by reading `rule_words()`'s
docstring claim, but by actually calling `rule_words()` on a rule using that slot type and
`grep`-ing the resulting prompt string for the new words. `SlotType` has a `sample: Callable[[],
str]` field already, for collision-probe sampling; a parallel `vocabulary_words` field (or similar)
feeding into `_words_in`/`rule_words` is the natural extension point, keeping the fix inside D10's
existing extra_words pipeline (words only bias the prompt when a rule using that slot type is
active) rather than bolting every slot word onto `vocabulary.py`'s always-on static table. Full
report: `plans/speech-rules/review-stage3a.md`, Required Fix 1.

See [[project_bl17_test_list_claims_a_fix_its_own_exclusion_rules_out]] and
[[project_bl17_stage3a_fuzz_cycle_and_test_list_defect]] for the sibling lessons from this same
revision -- all three are instances of the same shape: a stated invariant ("slot values are
already covered," "fuzziness never touches slot values," a test-list phrase) that was true when
written and silently stopped being true once a later decision in the same revision widened what
the slot/mechanism actually does.
