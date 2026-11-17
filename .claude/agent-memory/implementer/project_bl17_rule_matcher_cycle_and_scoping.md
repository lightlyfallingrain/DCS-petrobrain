---
name: project_bl17_rule_matcher_cycle_and_scoping
description: BL-17 (speech-as-Lua-rules) Stage 1b/2 — a real import cycle between rule_patterns.py and command_matcher.py resolved by dependency injection, and the deliberate full-consumption/exact-literal rule-matching scope choice
metadata:
  type: project
---

`plans/speech-rules/plan.md` Stage 1b (the rule engine) and Stage 2 (porting
"turn left/right NN") landed as two commits on `feature/speech-rules`:
`0ea8be96` (Stage 1b) and `e5d52333` (Stage 2). Two things worth knowing before
touching this area again:

1. **`rule_patterns.py` (audio-adapter) must never import `command_matcher.py`,
   even though the plan's own "Affected modules" list puts the whole D9
   collision check inside `rule_patterns.py`.** `command_matcher.py` already
   imports `rule_patterns` for its own D8 rule-matching branch, regardless of
   which rules are active — that import exists unconditionally. D9's
   rule×legacy check needs the *real* legacy matcher
   (`command_matcher.match_transcript`), so importing it back would be a
   genuine cycle, not a style nit. Resolved by dependency injection: `rule_
   patterns.compile_rules` takes a `legacy_probe: Callable[[str],
   LegacyProbeResult]` parameter; the concrete probe (`_legacy_probe`) lives
   in `server.py`, which already imports both modules. If a future stage
   wants to restructure this, keep the injection — don't try to merge the two
   modules to "simplify" it.
2. **Rule matching (this project's own, D8) is full-consumption and
   exact-literal, not the legacy matcher's fuzzy `_phrase_match_ratio`
   score.** `rule_patterns.match_pattern` requires every element to consume
   its words with no fuzzy tolerance on literals; `match_ratio` is always
   `1.0` for a hit. This was a deliberate scoping choice (documented in that
   module's own docstring and flagged in `plans/speech-rules/
   implementation.md`'s Notable Discoveries), not an oversight — Stage 1b/2
   ships exactly one rule, so there was no real evidence yet to calibrate a
   second fuzzy engine against. **If a later stage adds rules and real
   flight logs show STT noise defeats exact literals, that is the moment to
   revisit this — it was explicitly left open, not settled.**

Also: `handle_command`'s "a dropped rule id answers `NO_SUCH_COMMAND`, never
silent" (D4) needed a *second* tracked set beyond `enabled_rule_ids`
(`CrewConsole._ever_enabled_rule_ids`, grows-only, process lifetime) to
distinguish "a rule id that was enabled and got dropped" from "a token that
was never a command at all" (which must stay silent+logged, pinned by a
pre-existing test). Easy to miss if you only look at `enabled_rule_ids`.
