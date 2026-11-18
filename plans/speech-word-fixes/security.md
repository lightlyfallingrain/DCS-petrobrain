## Security Deep Analysis: speech-word-fixes (`[[BL-B129]]`)

Scope: `git diff c59087f8 e81ed908` — `audio-adapter/src/{command_matcher,rule_patterns,vocabulary}.py`,
`body-layer/config/rules/flight.lua`, plus tests/docs/research. Fast-forwarded this worktree from
`59192cfa` to `e81ed908` (strict ancestor, clean tree). Reviewer approved at this tip
(`plans/speech-word-fixes/review.md`).

### Dependency Status
No dependency change. Stdlib-only in `audio-adapter` per its own `CLAUDE.md`; no `pyproject.toml`/
lockfile touched by this diff.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `audio-adapter/src/rule_patterns.py` `_consume_digit_run`/`_DIGIT_WORD_HOMOPHONES` | New deterministic text->digit substitution reached from untrusted transcript text | Scoped correctly: only fires inside an already-anchored numeric slot's own digit run (`_consume_heading`/`angle`/`quantity`/`speed_target`), never a free-standing lookup. Confirmed by grep (table read only inside `_consume_digit_run`, called only by those four slot consumers) and by the shipped test `test_homophone_fuzz_never_fires_outside_a_numeric_slot`. No general char-ratio fallback was added — the implementer measured and rejected one (`degrees`~`three` = 0.5, `right`~`eight` = 0.8 at the shared floor) specifically because it would turn an unrelated word into a wrong digit. This is the right call from a security standpoint: a looser fallback is exactly the shape that turns background chatter into a spurious flight command. | None |
| `audio-adapter/src/rule_patterns.py` `_consume_heading`, `flight.lua:30` | Slot type changed from "word 'heading' + 3 digits" to "pure 3 digits", anchor moved into the pattern as a literal | Verified by grep (`grep -n "heading_deg\|:heading>"`) that `flight.lua`'s `turn_heading` is the **only** rule in the repo using the `heading` slot type, and its pattern is `"<verb:turn|fly> heading <heading_deg:heading>"` — full-consumption matching (`match_pattern_with_ratio`: `if end != len(words): return None`) means a bare 3-digit utterance ("270" alone) cannot match this rule; it still needs the verb literal and the "heading" literal to match first. So the pure-digit slot change does not let a bare number become a command today. **Latent risk, not introduced here**: a *future* rule reusing the bare `heading` slot type without its own anchor literal would accept a bare 3-digit number as a command (the slot itself no longer refuses one). Worth a one-line note where `SLOT_TYPES["heading"]` is declared, or left as a reviewer habit for whoever adds the next rule using this slot — see backlog item below. | Backlog note (see below); not a fix required now |
| `audio-adapter/src/command_matcher.py` `_BARE_WORD_ALIASES` (D4) | "alright"/"all right" alias onto "right", feeding `_HVRT_BARE_WORD_TOKENS` | Keyed on the *whole transcript's* word tuple, not a substring/global fold — confirmed in the diff and by the module's own documented counterfactual (a global fold in `vocabulary.normalize_for_match` was tried, found to turn "alright then let's go" into `point`, and reverted). Three free-speech pinned sentences containing "alright"/"all right" are tested to stay non-commands. This is the correct shape: it narrows a false-positive path (the bench's one WRONG case) without widening the HVRT bare-word shortcut's reach to ordinary sentences. | None |
| `audio-adapter/src/command_matcher.py` `_has_unaccounted_number`/D5 guard | New guard narrows `point`/`"what"` matching (rejects direction+bare-number) | This *removes* an existing false-command path rather than adding one — "right 45" no longer silently resolves to `point`. Net effect is safety-positive: fewer transcripts resolve to a command, more fall through to "say again". Verified by the reviewer's own mutation test (disabling the guard reproduces the old wrong match) and independently by reading `_has_unaccounted_number` — O(n) over the word list, no regex, no backtracking risk. | None |
| `audio-adapter/src/command_matcher.py` `strip_filler(..., preserve=...)` | New optional parameter widens what a filler-stripping call can keep | `preserve` defaults to `frozenset()` (today's behaviour) at every call site except the one new rule-matching path, which passes `_RULE_FILLER_PRESERVE` — a derived set (`frozenset(_DIGIT_WORD_HOMOPHONES) & FILLER_WORDS`), not a hand-maintained one, so it cannot silently drift wider than the homophone table itself. The legacy pipeline's own `words` (used for `_match_legacy`, `_has_unaccounted_number`, the HVRT bare-word path) is untouched — still fully filler-stripped, so D3's change cannot affect D5's or D4's matching. | None |

### Input handling / parsing-untrusted-text check

All new/changed functions in this diff (`_consume_digit_run`, `_consume_heading`, `_has_unaccounted_number`,
`strip_filler`, `_BARE_WORD_ALIASES` lookup) are single-pass over a `list[str]` already produced by
existing tokenisation, with no regex, no recursion, and no data-dependent loop bound beyond the
transcript's own word count — a long or adversarial transcript (e.g. a malicious WAV posted
straight to `audio-adapter`'s existing, unauthenticated `POST /transcribe`, per that subproject's
own `CLAUDE.md`) cannot drive any of this new code into quadratic behaviour or an unbounded loop.
No new file I/O, subprocess, `eval`/`exec`, or deserialization was introduced (`grep -nE
"eval\(|exec\(|subprocess|os\.system|pickle|yaml\.load|__import__"` over the three changed Python
files and the changed Lua rule file: no hits). `flight.lua`'s own diff is wording-only (`alt` ->
`altitude` literal removal) with no new slot or handler logic.

The pre-existing fact that `/transcribe`/`/speak`/`/stop` carry no authentication
(`audio-adapter/CLAUDE.md`, "Running the server") is unchanged by this diff and is not a new
finding here — it is the project's own documented, accepted LAN-only posture, already on file
before this feature.

### Verdict
APPROVED

### Required Fixes (if any)
None.

### Low-risk items (not fixes, surfaced per the risk-communication format)

**Finding:** The `heading` `SlotType`'s `consume` function no longer requires its own anchor word —
a future rule written as, say, `"<heading_deg:heading>"` with no preceding literal would accept a
bare 3-digit utterance as a complete command (full-consumption matching needs nothing else to
satisfy the pattern). Today this cannot happen: `flight.lua`'s `turn_heading` is the only rule using
this slot, and it always pairs it with `"<verb:turn|fly> heading"` first.
**Location:** `audio-adapter/src/rule_patterns.py`, `SLOT_TYPES["heading"]` / `_consume_heading`.
**Probability:** low — it requires someone to write a new rule that misuses the slot; nothing in
today's code path can reach it.
**Impact:** low — this is a LAN-only, single-player cockpit voice command; a stray 3-digit heading
command would at most turn the aircraft to a heading nobody meant, not grant any computer access.
**Recommended action:** a one-line comment at the `SLOT_TYPES` declaration or `compile_rules`'s own
docstring, noting that a bare `heading`-slot-only pattern accepts a bare number, so a future rule
author pairs it with an anchor literal the way `flight.lua` does.

Options:
  (A) Ignore — document acceptance of this risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — I'll address it before continuing
  (D) Stop — do not proceed until this is resolved

**Not filed as a backlog ID, intentionally.** This is a one-line documentation note about a slot
type's own contract, not a defect in the shipped feature (no rule today can trigger it), and it
would be addressed for free the moment anyone writes the next rule using the `heading` slot and
runs `tools/check_rules.py`'s collision check against it. Filing a backlog ID for a note this small
would outlive its own relevance faster than leaving it here. If the user wants it tracked anyway,
option (B) mints a `BL-B` or `AA-B` item (prefix depends on which subproject's rule-authoring
convention owns it) at that point.

### Passed to Reviewer
None — nothing player-facing-correctness was observed that the Reviewer's own pass (already
APPROVED) had not already covered.
