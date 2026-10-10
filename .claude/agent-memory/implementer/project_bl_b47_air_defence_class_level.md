---
name: bl-b47-air-defence-class-level
description: _is_air_defence BL-B47 fix — _op_class_of is a strict superset of profile_for; OP_ZU23 resolved by accident, which made the parametrised test honest
metadata:
  type: project
---

`BL-B47` (2026-10-10, `fix/air-defence-class-level`): `belief.speech._is_air_defence` resolved a
*believed classification* through `perception.object_model.profile_for`, which keyword-matches DCS
**type** designations. A class-level belief carries the `OP_*` string itself and fell into the
default bucket. Fixed by routing through `_summary_op_class` (`classification.parent_class_of`).

**The load-bearing structural fact, reusable beyond this fix:**
`classification._op_class_of` is a **strict superset** of `object_model.profile_for` — it
early-returns any non-default `OP_*` string and otherwise delegates to `profile_for`. So switching a
predicate from the latter to the former can only widen, never trade. Measured over 1060 distinct
candidate values — all 10 declared `op_class` values, all **131** keyword entries
(`_KEYWORD_PROFILES` 70 + `_REPORTING_NAME_KEYWORD_PROFILES` 61) and all **595** DCS type names in
`reporting_names`' mapping plus its values: **0 verdicts lost, 4 gained.** Worth checking whether
any *other* predicate still resolves a believed classification through `profile_for`.

**The first write of this said "128 keyword entries"** and the Reviewer caught it: `len()` of only
one of `object_model`'s two keyword tables plus a miscount. See
[[feedback_cite_what_was_counted_not_just_how_many]].

**`OP_ZU23` resolves through `profile_for` by accident** — the literal class name matches that
table's own `"zu23"` keyword. So 4 of the 5 air-defence classes were broken and one was not. This is
why parametrising over `AIR_DEFENSE_OP_CLASSES` was honest: the counterfactual showed 4 red and
`OP_ZU23` green, which is the shape of the real defect. **A test that sampled only `OP_ZU23` would
have found nothing**, and any "all five behaved the same" reasoning is wrong.

**Related trap, cost one failing test:** the type-level fixture's first draft used a
plausible-looking `"S-300PS 5P85C ln"` that is not in the keyword table. It answered `False` and read
as a gap *in the fix* rather than as a bad fixture. The real entry is `"s-300ps 40b6m tr"`. Same
lesson as [[feedback_verify_keyword_vocab_against_real_strings]], now hit on the SAM table
specifically.

**Repetition hazard found while writing the push-path analysis, not fixed:** the callout scheduler's
`belief_group.last_spoken_signature` is a **single slot, not a history set**, so any alternating pair
of lines defeats it. Pre-existing and not air-defence-specific, but this fix widens what flows
through it — a class-level SAM oscillating in and out of a group under clustering jitter now speaks
on each rejoin. Worth filing if group-callout churn is reported from a sortie.

Also: a **third** copy of the air-defence class set lives in `crew_console.py` (~line 265), identical
membership to `AIR_DEFENSE_OP_CLASSES`, already lattice-resolved and correct.
