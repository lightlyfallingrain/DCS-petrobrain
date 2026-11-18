### Implementation Summary

Implements `[[BL-B129]]` D1–D6 (D5 added mid-implementation, user-approved 2026-11-18; D6 added
mid-implementation, main-loop decision 2026-11-18, fixing a defect D5's own narration surfaced
while implementing D3). D2 was measured and explicitly **not** shipped (see below).

### Files Changed

- `body-layer/config/rules/flight.lua` — D1: `set_altitude`'s `<verb:alt|altitude>` and
  `hold_altitude`'s `hold <verb:altitude|alt>` lose "alt" entirely (now the plain literal
  "altitude"/"hold altitude"). Neither handler ever read `s.verb`, so this is a pure pattern edit.
- `audio-adapter/src/rule_patterns.py` — D3: `_DIGIT_WORD_HOMOPHONES` (to/too→two, for/fore→four,
  free/tree→three, won→one, ate→eight, niner→nine, oh→zero), wired into `_consume_digit_run` (the
  shared digit-run parser `angle`/`quantity`/`heading`/`speed_target` all call). **Deliberately does
  not** add the plan's own "existing char-ratio fuzz... with a cutoff" fallback — measured that at
  the shared `_WORD_REPAIR_FLOOR` (0.5), ordinary rule words (`"degrees"` 0.5, `"down"` 0.57,
  `"level"`/`"speed"` 0.6, `"flight"` 0.73, `"right"` 0.8) would fuzzy-match a digit word, which
  would have turned "turn left two zero degrees" (today: unconsumed trailing word, no match) into a
  wrong angle (203). Documented in the module as a deliberate, measured omission.
- `audio-adapter/src/command_matcher.py`:
  - D3's own integration fix: `strip_filler` gained an optional `preserve` parameter;
    `_RULE_FILLER_PRESERVE` (`frozenset(_DIGIT_WORD_HOMOPHONES) & FILLER_WORDS`, today exactly
    `{"to"}`) is passed when building the word list `_match_rules` sees, because "to" is both a
    digit homophone and an existing filler word — without this, `strip_filler` dropped "to" before
    `_consume_digit_run` ever saw it, silently defeating D3's own bench-measured fix for "heading
    **to** seven zero". The legacy pipeline keeps using the fully-stripped word list unchanged (its
    pinned "scan to the right" → `scan_right` case is unaffected).
  - D4: `_BARE_WORD_ALIASES` (`{("alright",): "right", ("all", "right"): "right"}`), consulted by
    the HVRT bare-word shortcut only — scoped to the *whole* bare transcript, not a per-word
    normalisation fold. A global fold in `vocabulary.normalize_for_match` was tried first and
    reverted: measured directly, it exposed the shortcut's own documented "right"~"sight" 0.8 fuzzy
    collision to every sentence *starting* with "alright" ("alright then let's go" resolved to
    `point` before narrowing) — a real widening of a pre-existing collision, not assumed safe from
    the mechanism alone.
  - D5 (added mid-implementation): `_has_unaccounted_number` — a digit or recognised number word
    not immediately followed by its own unit marker (`"km"`/`"kilometres"`/etc. or `"o'clock"`)
    blocks the `point`/`"what"` branches from resolving. Fixes "right 45"/"right forty five"/"left
    30" (whisper dropping "turn" from "turn right forty five") resolving to `point` on the
    `relative` slot alone with the trailing number silently unaccounted for
    (`research/2026-11-18-whisper-model-sweep-flight-corpus.md`, on `main`).
- `audio-adapter/tests/test_flight_rules_matching.py`, `test_rule_patterns.py`,
  `test_command_matcher.py` — updated to match D1's new grammar (no `"verb"` slot), added D1's
  `rule_words` omits "alt" tests, reworded one pre-existing pinned test
  (`test_slot_value_is_never_fuzzy_repaired`) that D3 directly falsified (it used "free" as its
  "not a digit at all" example; D3's own table now maps "free"→"three" by name) — swapped to
  "degrees" (same ratio ballpark, not in the homophone table) to keep pinning "no general
  char-ratio fallback."
- `audio-adapter/tests/test_rule_patterns.py` — D3 unit tests (`TestDigitWordHomophones`): each
  homophone in `angle`/`quantity`/`heading`/`speed_target`, a value-bound rejection ("turn left
  oh" → angle 0, still rejected), a digit-count-bound rejection (`heading` still needs exactly 3
  digits), and that the fuzz never fires outside a numeric slot (a `WordSetElement` test).
- `audio-adapter/tests/test_command_matcher.py` — D4 tests moved from a (reverted) vocabulary-level
  test to `TestHvrtBareWordShortcut` (the mechanism's real home): "alright"/"all right" resolve,
  three free-speech sentences (including the specific regression found and reverted) stay
  non-commands. D5 tests in `TestPointSlots`: the four reported bad phrases never match `point`,
  and a legitimate `relative`+distance phrase ("look right 5 kilometres") still does.
- `audio-adapter/tests/test_command_matcher_rules.py` — `TestDigitHomophoneFillerConflict`:
  end-to-end (`match_transcript`, not direct `rule_patterns` calls) pins for the "to" filler/digit
  conflict and its fix, plus the legacy "scan to the right" case repeated with a rule active.
- `audio-adapter/tests/test_vocabulary.py` — no net change (the global-fold tests were added, then
  removed on revert, leaving the file as it started).
- `body-layer/tests/test_rules_flight_actions.py` — `TestSetAltitude`/`TestHoldAltitude`'s
  hand-built `slots` fixtures no longer carry `"verb"`, matching what the real matcher now
  produces after D1 (these tests still passed unmodified, since the Lua handler never read
  `s.verb`, but the fixture was stale relative to reality — updated for accuracy).
- `audio-adapter/src/rule_patterns.py` — D6: `_consume_heading` no longer requires the literal word
  "heading" inside its own `consume` (pure 3-digit grammar, same homophone table, 0-360→0, no
  checksum, unchanged); the `heading` `SlotType`'s own `sample()` lambda drops the leading
  "heading" word it used to bake in (now `"two zero zero"`, matching `angle`/`quantity`'s own
  convention). Module docstring and the `rule_words` docstring both corrected — the latter
  previously claimed no pattern used a literal "heading" at all, which was false even before D6
  (`flight.lua`'s own pattern already did; the claim was simply wrong, not merely stale).
- `audio-adapter/tests/test_rule_patterns.py` — `TestHeadingSlot` tests rewritten for the bare
  slot's new pure-digit grammar (no "heading" word in the input any more) plus a new
  `test_no_anchor_word_of_its_own`; new `TestHeadingSlotWithPatternAnchor` class tests the real
  shipped pattern shape directly (resolves, homophone mid-run, the double-"heading" rejection, bare
  digits without the verb rejected); `TestDigitWordHomophones`'s own two heading tests updated to
  use the anchored pattern (`"heading <deg:heading>"`) instead of the bare slot, since the bare
  slot no longer has an anchor to test the homophone against in isolation — one of the two
  (`test_a_fuzzed_digit_count_still_fails_headings_exact_three_rule`) had started passing for the
  wrong reason after the slot-grammar change and was corrected to use the real pattern shape so the
  rejection is genuinely about the digit count again, not an unrelated anchor-word mismatch.
- `audio-adapter/tests/test_flight_rules_matching.py` — `_FLIGHT_RULE_PATTERNS`'s own
  `turn_heading` entry corrected to the real shipped pattern string (it had drifted to a bare
  `"<heading_deg:heading>"`, missing the `<verb:turn|fly> heading` prefix, since before this plan
  started — the double-"heading" defect was undiscovered until D3); `TestTurnHeadingAbsolute`
  rewritten to say the verb every test now requires, plus new tests for the homophone-through-the-
  real-pattern case, the double-"heading" rejection, and the bare-digits-without-verb rejection.
- `audio-adapter/tests/test_command_matcher_rules.py` — `TestDigitHomophoneFillerConflict`'s own
  `_HEADING_RULE` fixture corrected to the real pattern string for the same reason.
- `audio-adapter/research/2026-11-18-state-hint-bench.md` — appended the before/after bench table,
  the clip-by-clip trace of every kind-change between runs, the D2 prompt-experiment result and
  why it was not shipped, the D5 finding/fix summary, and the D6 finding/fix summary plus why the
  re-run bench shows zero change (the corpus's own "heading" clips never say "turn"/"fly").
- `plans/speech-word-fixes/plan.md` — added the D5 and D6 sections and updated Acceptance
  (coordinator scope additions, user-approved/main-loop-decided 2026-11-18).

### Tests Added

- `test_rule_patterns.py::TestDigitWordHomophones` (21 tests) — D3, see above.
- `test_flight_rules_matching.py::TestSetAltitude::test_rule_words_omits_alt`,
  `TestPlainPhrases::test_hold_altitude_rule_words_omits_alt`,
  `test_alt_still_fuzzy_repairs_onto_the_literal` — D1's actual mechanism (prompt-bias removal,
  not grammar rejection — "alt" still fuzzy-repairs onto the literal "altitude" at ratio 0.545,
  measured, not assumed).
- `test_command_matcher.py::TestHvrtBareWordShortcut::test_alright_and_all_right_resolve_to_hvrt_translate_right`,
  `test_alright_inside_a_free_speech_sentence_still_falls_through` — D4.
- `test_command_matcher.py::TestPointSlots::test_a_bare_direction_followed_by_a_number_never_becomes_point`,
  `test_a_bare_number_does_not_block_a_legitimate_distance_phrase` — D5.
- `test_command_matcher_rules.py::TestDigitHomophoneFillerConflict` (3 tests) — D3's filler
  conflict and fix, end to end.
- `test_rule_patterns.py::TestHeadingSlot::test_no_anchor_word_of_its_own`,
  `TestHeadingSlotWithPatternAnchor` (4 tests) — D6.
- `test_flight_rules_matching.py::TestTurnHeadingAbsolute::test_a_homophone_mid_run_resolves`,
  `test_double_heading_no_longer_matches`, `test_heading_alone_without_the_verb_does_not_match` —
  D6, against the real pattern.

### Checks

**audio-adapter/**
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (17 source files)
- pytest -q (full suite): 564 passed, 2 skipped
- `.claude/scripts/fast-tests.sh audio-adapter`: 412 passed, 1 skipped

**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy src: pass (91 source files)
- `.claude/scripts/fast-tests.sh body-layer`: 297 passed
- `tools/check_rules.py`: `ok: 1 rule file(s) checked` (lua syntax, declarations, wording via the
  real audio-adapter collision check, handler dry run — all four checks ran; no warnings)

### Bench (before/after, `phrase_bench.py`, `data/corpus/bl17-stage3c/`, `ggml-small.en`)

| prompt | ok (before → after) | miss (before → after) | WRONG (before → after) |
|---|---|---|---|
| A — today's full prompt | 141 → 139 | 22 → 25 | **1 → 0** |
| B — flight words first | 138 → 136 | 24 → 26 | 2 → 2 |
| C — out-of-state words removed | 129 → 128 | 32 → 34 | 3 → 2 |

WRONG drops to 0 on A_full (D4's fix). A_full's `ok` count drops by 2 — traced clip by clip in the
research note: entirely attributable to three recordings of the now-deprecated "alt" phrasing
(D1's own intended cost) plus a wash of two unrelated clips shifted by the shorter A_full prompt
text (a known property of prompt-conditioned decoding, not a defect). **D6 re-run: zero change**
from these numbers, clip for clip — expected, since this corpus's own `heading_*` clips never say
"turn"/"fly" and so never reach `turn_heading` either before or after D6. Full trace and D2/D5/D6
notes: `audio-adapter/research/2026-11-18-state-hint-bench.md`.

### Notable Discoveries

- **D2: no prompt change shipped.** Tried widening `_PROMPT_FRAMING` with numeral examples;
  benched worse on every count (136/27/1 vs. the unmodified 139/25/0) and did not improve the
  targeted "turn left thirty" phrase at all (still 0/4). Fails D2's own ship condition on both
  halves. The spoken form for composed numbers stays individual digits.
- **D1's own "alt" removal does not make "alt" stop matching — it stops whisper from being biased
  toward hearing it.** `_char_ratio("alt", "altitude") == 0.545`, clear of `LiteralElement`'s own
  `_WORD_REPAIR_FLOOR` (0.5), so a heard "alt" still repairs onto the literal "altitude" and the
  rule still matches. D1's actual mechanism is removing "alt" from `rule_words()` (the whisper
  prompt bias), not from the matching grammar's own tolerance — measured and pinned by a new test
  rather than assumed from the pattern edit alone.
- **D3's "existing char-ratio fuzz... with a cutoff" fallback was evaluated and rejected as unsafe**
  at the shared 0.5 floor — several ordinary words that sit immediately next to a numeric slot in
  the real rule set (the angle slot's own name "degrees", "down"/"level"/"speed"/"flight"/"right")
  score at or above it against a digit word. Shipped the deterministic homophone table only;
  documented the measured danger in `rule_patterns.py` so a future "it's not enough, add the fuzzy
  fallback too" does not repeat the same unsafe experiment.
- **A global `normalize_for_match` fold for D4 was tried and reverted after a measured
  regression**: it exposed the HVRT shortcut's own "right"~"sight" collision to ordinary sentences
  starting with "alright" ("alright then let's go" → `point`). Narrowed to a whole-transcript bare
  word alias instead, with zero new false-positive surface (verified: "it's all right with me",
  "that was alright I guess", "alright then lets go" all stay `token=None`).
- **D6 — a genuine pre-existing matcher defect, found while implementing D3, fixed by main-loop
  decision.** `flight.lua`'s real shipped `turn_heading` pattern,
  `"<verb:turn|fly> heading <heading_deg:heading>"`, needed the literal word "heading" **twice** to
  match at all — once from the pattern's own grammar, once more from inside `_consume_heading`'s
  own `consume`. "turn heading three one five" (what a pilot actually says, and every test's and
  the bench's own assumed wording) never matched the real rule before D6. Fixed by making the
  `heading` slot type pure digits and moving the anchor into the pattern, where `rule_words` (the
  whisper prompt bias) actually reads it from. `check_rules.py`'s own self-match step
  (`generate_samples`/`_expand` → `match_pattern`) missed this because the bug was *internally
  consistent*: the `heading` slot's own `sample()` lambda baked in the same "needs its own
  'heading' word" assumption the buggy `consume` required, so the generated self-test sample always
  matched the buggy grammar it was generated from. A self-match check built from a rule's own
  stated primitives cannot catch an error shared between the primitive (what a sample "should" look
  like) and the code that accepts it — it has no independent oracle for what a human actually says.
  Closing that gap generally (e.g. running the real bench corpus through `check_rules.py`) is a
  bigger change than "small and local" — noted here as a follow-up, not attempted.
- **A `grep` of the test suite surfaced four test files the plan did not name**
  (`test_rule_patterns.py`, `test_command_matcher.py`, `test_command_matcher_rules.py`, and
  `body-layer/tests/test_rules_flight_actions.py`), all touching D1/D3's own grammar/digit-run
  changes directly — one (`test_slot_value_is_never_fuzzy_repaired`) was a genuinely falsified
  pin, not merely stale.

### Flight (`#needs-flight`)

Say "altitude three hundred", "hold altitude", "turn left three zero", "alright" (expect
`hvrt_translate_right`), "right 45"/"left 30" said deliberately with no "turn" (expect "say
again", never a silent `point`), "turn heading two seven zero" (D6 — now resolves correctly;
bare "heading two seven zero" with no "turn"/"fly" must stay "say again").

D6 fixed what would otherwise have been a flight-test failure: the plan's own original line
("heading two seven zero", as "turn heading two seven zero") would not have worked as written
before D6 — the real shipped rule needed "turn heading heading two seven zero" (doubled) to match
at all. That is no longer true; the flight line above reflects the fixed behaviour.
