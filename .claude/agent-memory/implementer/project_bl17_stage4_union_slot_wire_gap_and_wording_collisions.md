---
name: bl17-stage4-union-slot-wire-gap-and-wording-collisions
description: BL-17 Stage 4 (flight-control rules) found a union-slot wire-type gap (speed_target silently dropped), an HVRT self-collision bug in compile_rules, and five genuine wording collisions the project's own fuzzy matching surfaces -- read before porting any further rule group with a union slot or bare-word pattern
type: project
---

Building real differential matching tests for BL-17 Stage 4 (`plans/speech-rules/plan.md` D18,
`[[BL-17]]`) against the *real* `compile_rules`/`match_transcript` (not synthetic fixtures) surfaced
two genuine bugs in shared, not-stage-specific infrastructure, plus five real wording collisions.
Relevant to any future BL-17 stage (marks' `direction`/`origin` union types, Stage 5/6's own bare
words) or any new rule using a union slot or a single-word pattern.

**1. A union slot's own tagged table value (`speed_target`'s `{"kind": ..., ...}`) was silently
dropped crossing the audio-adapter -> body-layer wire**, never a crash -- `command_matcher.
_match_rules`'s own `typed_slots` filter kept only `isinstance(value, (int, str))`, and `body.py`'s
own `/transcripts/poll` row validator `continue`d (dropping the *whole* transcript) on any slots
dict with a non-scalar value. D7/D14's "a union arrives in Lua as a table" design had never been
exercised end to end before this stage -- the one shipped union slot, `speed_target`, is the first.
Fixed by widening both filters to admit a flat `dict[str, object]` one level deep (`SlotValue = int |
str | dict[str, object]`, `MatchResult.slots`/`TranscriptEvent.slots` become `Mapping[str, SlotValue]`
-- `Mapping` not `dict`, covariant, so every existing scalar-only `_parse_*_slots` branch needs no
change per mypy's own suggestion). Confirmed via direct lupa probes that a nested Python `dict`
crosses into Lua correctly as "userdata" under the real sandbox's `attribute_filter` (`sandbox.py`'s
own `_deny_all_attributes` docstring already names this as tolerated, not a new risk).

**2. Every bare-word rule whose own exact string is intercepted by a pre-rule shortcut
"collides with itself" in `compile_rules`'s rule x legacy check.** `rule_patterns.
_collides_with_legacy` flagged *any* non-`None` legacy-probe token as a collision, including when
that token is the rule's own id -- which happens for every one of HVRT's seven bare-word rules,
since `command_matcher._HVRT_BARE_WORD_TOKENS` resolves "left"/"hold"/etc. to that exact token
regardless of whether any rule is active. Fixed by requiring the legacy token to differ from the
rule's own id. Any future rule ported onto an existing exact-match shortcut (not just HVRT) will
hit this same false positive until encountered and would need the same check.

**3. Five real, measured wording collisions were found and deliberately NOT forced through**
(renaming a spoken command is a product decision, not an Implementer's): `set_speed`/`altitude_step`
(mutual, `ratio("speed","descend")==0.5`, exactly `_WORD_REPAIR_FLOOR`), `level_off`/the existing
`observ_off` (`0.75`, word-sequence scoring against "observe off"), `straight`/`point` and `straight`/
`hvrt_translate_right` (`0.77` both), `hvrt_translate_right`/`point` (via the perturbed-sample probe:
"right"'s own near-miss "light" resolves to `point` -- the *exact* collision `_HVRT_BARE_WORD_TOKENS`'s
own comment already named as the reason that shortcut exists, which protects only an *exact* "right,"
not a mis-transcribed "light" landing outside it). `body.py`'s `_push_rules` already degrades an
adapter-rejected rule exactly like a load-time failure (D6's own banner + "Action file error.") --
no new code was needed for this to fail gracefully. Full table and recommended fixes in
`plans/speech-rules/implementation.md`'s "Stage 4" section.

**Lesson for the next rule-porting stage**: before accepting any new rule using a word-set/bare-word
pattern, actually run it through the real `compile_rules` + real `vocabulary.PHRASES`/`FREE_SPEECH_
GUARD`, not just a synthetic fixture pair -- a rule that reads as obviously fine in isolation can
still collide with an *existing*, unrelated shipped command via the project's own fuzzy-matching
tolerance (`_WORD_REPAIR_FLOOR`/`MATCH_FLOOR`), and the only way to find that is to run the real
check, not reason about it.
