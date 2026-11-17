### Review Summary

Reviewed `feature/speech-rules-matching` at `c97731c0` (Stage 3a: literal fuzz D13, number-word
slot types D14, the two performance fixes D15) against `plans/speech-rules/plan.md` Revision 2's
Stage 3a section, `body-layer/ROADMAP/BL-17.md`'s user decisions, `plans/speech-rules/alignment.md`
(E11/E12/E3, the Revision 2 plan check's Finding 1), and `implementation.md`'s own "Stage 3a"
account. HEAD started at `fc282270` (a strict ancestor of the tip); fast-forwarded to `c97731c0`
with a clean tree, then worked in this worktree throughout (also cross-checked against the
sibling worktree `/Users/sg/Code/DCS-petrobrain-speech-rules-matching`, already parked on the same
commit).

**Scope confirmed**: `git diff 9e748923..c97731c0 --name-only` touches only `audio-adapter/`,
`plans/speech-rules/`, and three new `.claude/agent-memory/` files — no `body-layer/` file is in
the diff, matching Stage 3a's own stated boundary.

**Checks run myself** (no `.venv` existed in this worktree; built one from
`/opt/homebrew/bin/python3.14` rather than reusing the main checkout's, per the brief):
- `ruff format --check src tests`: pass, 36 files already formatted.
- `ruff check src tests`: pass, no findings.
- `mypy src` (the mandated command, run from inside `audio-adapter/`): pass, 17 source files, 0
  issues.
- `pytest -q` (full suite): **519 passed, 2 skipped** (the two pre-existing whisper/Piper
  env-gated live skips).
- `.claude/scripts/fast-tests.sh audio-adapter`: smoke + 15 targeted files, parallel — **465
  passed, 2 skipped**. (The implementer's claim that this script "could not resolve a venv" was
  specific to their worktree having none at all; it runs cleanly once one exists.)

The grammar (`_consume_natural_number`/`_consume_number_word_phrase`, the digit-run-vs-word-phrase
override, the terminating-at-first-complete-number design) was traced by hand against every Q10
form, the paired-form rejections, "hundred"/"zero" alone, and the digit/word-phrase boundary case
("three hundred" vs "three" + "hundred" as two numbers) — all match the plan and the tests. The
`match_transcript` cross-pipeline `SEPARATION_MIN` tie-break was traced for both the "legacy token
is None" short-circuit (correctly skips the tie-break, no spurious ambiguity) and the genuine-tie
case (correctly forces `ambiguous=True`, never silently resolves a near-tie into an action — E3
holds).

### Required Fixes

1. **The new number-word vocabulary (D14) never reaches whisper's prompt bias — the exact failure
   class this project has a standing rule against.** `quantity`/`speed_target`/`angle`'s new
   grammar teaches the *matcher* to accept "twenty", "thirty", ..., "ninety", the teens
   "thirteen"–"nineteen", and "hundred" — but `rule_words()`/`_words_in()` only walks a rule's
   `LiteralElement`/`WordSetElement` words into `extra_words` (by design, per its own docstring:
   "a slot's own value words... are already covered by `vocabulary.py`'s own digit/time words").
   That claim was true before this stage (only `angle`/`heading`/`oclock` existed, needing only
   0–9 and `o'clock`, both already in `vocabulary.py`'s tables) and is **no longer true** now that
   `angle`/`quantity`/`speed_target` accept composed number words that exist nowhere in
   `vocabulary.py`. Verified directly:

   ```
   >>> rule_words(turn_heading_relative_rule)
   ['turn', 'left', 'right']
   >>> 'thirty' in to_prompt(['turn', 'left', 'right']).lower()
   False
   ```

   So the canonical phrase this whole correction exists for — "turn left thirty", the user's own
   example, the reason D14's "Corrected 2026-11-17" note added number words to `angle` at all — is
   parsed correctly if whisper happens to transcribe "thirty" right, but whisper is given **no
   bias at all** toward hearing "thirty" correctly in the first place. This is precisely the
   "silence"→"violence" failure mode `audio-adapter/CLAUDE.md` and root `CLAUDE.md`'s standing rule
   (2026-10-23) exist to prevent, and `test_vocabulary.py`'s prompt-coverage test is structurally
   blind to it — it checks the prompt against `vocabulary.py`'s own tables, and these words never
   reached those tables, so there is nothing for that test to fail against. (Checked: neither
   `test_prompt_carries_every_word_of_every_phrasing` nor `test_prompt_carries_every_slot_word`
   enumerates anything from `rule_patterns.py`.)

   **Fix, suggested shape (Implementer's call on the exact mechanism):** give `SlotType` a second
   piece of per-type metadata alongside its existing `sample: Callable[[], str]` — e.g.
   `vocabulary_words: tuple[str, ...]`, populated for `quantity`/`speed_target`/`angle` with
   `_TEENS_WORDS`/`_TENS_WORDS`'s keys plus `"hundred"` (and `"max"` for `speed_target`, already
   covered via `PHRASES["set_speed"]` but harmless to include) — and have `_words_in`/`rule_words`
   include a `SlotElement`'s type's `vocabulary_words` in what it returns. This keeps the fix
   inside D10's existing extra_words→`to_prompt()` pipeline (the words only bias the prompt when a
   rule using that slot type is actually active), rather than adding every number word to
   `vocabulary.py`'s always-on static table. Needs a test mirroring
   `test_prompt_carries_every_slot_word`'s shape, but driven from `rule_patterns.SLOT_TYPES`
   through a pushed rule rather than from a `vocabulary.py` table — so a sixth slot type added
   later fails this test automatically if its own words are not wired the same way, rather than
   relying on a reviewer to re-derive the gap by hand each time.

### Optional Refinements

- **The D15 `anchor_words` cache reads can race with a concurrent `PUT /rules` under
  `ThreadingHTTPServer`.** `RuleRegistry.swap` sets `rules`, `version`, `anchor_words` as three
  sequential attribute writes (not a single atomic swap of one object), and
  `server.py`'s `_handle_transcribe` reads `rule_state.rules` and `rule_state.anchor_words` as two
  separate attribute accesses. A `PUT /rules` landing between those two reads could pair a new
  `rules` tuple with a stale `anchor_words` (or vice versa) for one in-flight `/transcribe` call.
  Low likelihood (body-layer is the sole writer, pushes are infrequent) and low consequence
  (worst case: the newly-pushed rule's own first literal is briefly missing from the legacy
  pipeline's widened anchor set for one transcript — matching, not just widening, is unaffected,
  since `_match_rules` reads `active_rules` directly). `rules`/`version` already had this
  non-atomicity before this stage (two separate assignments, per the implementation notes); D15
  just adds a third field to the same pattern. Worth a one-line note now, or folding
  `rules`/`version`/`anchor_words` into one frozen snapshot object swapped with a single
  assignment, before a future stage adds a fourth cached field to the same registry.

- **The widened D9 collision probe (one fixed adversarial word per literal) is necessarily
  partial, and demonstrably misses the real collision the implementer found by hand.** "tern"
  (a plausible mis-hearing of "turn") anchors `turn_heading_relative` at ratio 0.75 *and* legacy
  `step` at ratio 1.0 — but `_COLLISION_PROBE_WORDS`'s own list never tries "tern" against "turn"
  (it would pick "burn" first, which does not collide with `step`), so the load-time collision
  check would not have caught this specific pairing had it been a genuine new collision. In this
  instance it is provably benign: `step` already won this transcript before D13 existed (the rule
  could not match "tern left two zero" at all under exact-literal matching), so D13 changes
  nothing about the outcome, only adds a rule that loses the comparison it wasn't competing in
  before. The implementer's own test (`test_legacy_wins_outright_over_a_weaker_rule_match`)
  correctly documents and pins this. Flagging only because the probe's coverage is inherently
  one-sample-per-literal, not exhaustive, and the next rule with a richer literal vocabulary raises
  the odds that an *actually new* collision slips past load time the same way — matches the
  implementation notes' own flag for Performance/Security's batch review.

- **"Three hundred and twenty" (an "and"-joined hundreds form) does not parse** — the grammar
  leaves "and" unconsumed, so the whole rule fails full-consumption matching and falls through to
  "say again". This is consistent with the user's own quoted Q10 examples (`BL-17.md`: "three
  hundred twenty", "one hundred fifty three" — no "and" in either), so it is not a deviation from
  what was asked for, just worth naming in case the recorded corpus (Stage 3c) turns up "and" in
  this speaker's actual delivery despite the written examples. Cheap to add later (one more
  optional branch after "hundred") if the measurement shows it's needed.

### Verdict

CHANGES REQUIRED — one required fix (the number-word vocabulary gap), bounded and mechanical, not
a design problem. Everything else in Stage 3a — the literal fuzz, the number-word grammar itself,
the cross-pipeline `SEPARATION_MIN` tie-break, the performance caches' correctness, the two named
departures, and the full check suite — is sound and well tested. Once the vocabulary fix lands
(plus a test pinning it the way `test_prompt_carries_every_slot_word` does for the existing slot
tables), this is APPROVED.

### Review Confidence

Full read of `rule_patterns.py`, `command_matcher.py`, `vocabulary.py`'s changed and newly-relevant
sections, `server.py`'s rule-registry wiring, `__main__.py`'s diff, and both new/changed test
files (`test_rule_patterns.py`, `test_command_matcher_rules.py`), plus the relevant
`test_vocabulary.py` prompt-coverage tests. The grammar was traced by hand against every example in
the plan and the test list, not just read. `audio-adapter/CLAUDE.md`'s own updated prose was
checked against the shipped code and found accurate. Not independently re-verified: body-layer's
own compatibility with the widened `match_ratio`/`ambiguous` semantics for `turn_heading_relative`
(body-layer is untouched by this diff and out of this review's scope per the brief; its own test
suite is DoD's/Stage 3b's concern).

---

## Re-review — 2026-11-17

Reviewed `1cb9b0de` (one commit, "BL-17 Stage 3a review fix: number-word prompt bias rejected,
E12 revised for directive words"), cherry-picked on top of Stage 3b, against this file's own
Required Fix 1, `body-layer/ROADMAP/BL-17.md`'s three verbatim user decisions from 2026-11-17
("Numbers reach speech-to-text as numerals", "Directives are part of the command, and fuzzy; only
values are exact", "Unit class words are a fixed list, matched fuzzily"), and
`plans/speech-rules/implementation.md`'s "Stage 3a review fix" / "...round 2" accounts. HEAD
started at `fc282270` (a strict ancestor of the tip, clean tree); fast-forwarded to `1cb9b0de`.
**The commit message's own summary has the `SEPARATION_MIN` move direction backwards** ("moved
vocabulary.py -> command_matcher.py") — the diff and every in-code comment agree the real move is
`command_matcher.py` -> `vocabulary.py` (mirroring `_WORD_REPAIR_FLOOR`'s own prior move, for the
same import-cycle reason). Immutable history, code and docs are correct, not required to fix.

**Checks run myself** (no `.venv` existed in this worktree; built one from
`/opt/homebrew/bin/python3.14`):
- `ruff format --check src tests`: pass, 36 files already formatted.
- `ruff check src tests`: pass, no findings.
- `mypy --strict src` (from inside `audio-adapter/`): pass, 17 source files, 0 issues.
- `pytest -q` (full suite): 527 passed, 2 skipped (the two pre-existing whisper/Piper env-gated
  live skips).
- `.claude/scripts/fast-tests.sh audio-adapter`: 473 passed, 2 skipped.

### Required Fix 1 — closed, in the user's chosen shape

Verified against the commit itself, not just the account of it: the review's own suggested
per-slot-type `vocabulary_words` mechanism is **not** present in `SlotType`/`SLOT_TYPES`/
`_words_in`/`rule_words` — those are byte-identical to pre-fix Stage 3a apart from `rule_words`'s
docstring. `TestRuleWordsNeverCarriesComposedNumberWords` (3 parametrized cases, derived from
`rule_patterns._TEENS_WORDS`/`_TENS_WORDS` directly, not a hand-copied list) pins the opposite of
the review's suggested fix: a rule using `quantity`/`angle`/`speed_target` must add **no** teens/
tens word or `"hundred"` to the whisper prompt bias. This is the user's own direction verbatim
("Numbers STT as numeric, please... Writes all number formats as text vocabulary is very
impractical") and `BL-17.md`'s roadmap entry, correctly built.

**But the docstring's supporting claim overreaches its own citation, and this is a required
fix.** `rule_words()`'s docstring (and `TestRuleWordsNeverCarriesComposedNumberWords`'s mirroring
docstring) states as settled fact: *"whisper already writes recognised numbers as numerals
regardless of a prompt's wording"*, citing
`research/2026-09-19-whisper-contract-and-grammar-probe.md`. Read that file directly: its one
relevant measurement is *"report three o'clock"* decoding to `"3 o'clock"` on both benched
models — a **single digit** word ("three"), in a clock-position context, on synthetic `say`
audio with no accent. The file's own "Two findings" section states the finding as "the number"
(singular), and its own "What this does not tell us" section limits itself to the accent
question — it never claims anything about composed two/three-digit number words ("thirty",
"hundred", "three hundred twenty"), which is exactly the case D14's grammar and this fix concern.
Generalizing a single-digit-in-clock-position measurement to "whisper already writes **recognised
numbers** as numerals" (unqualified) is an extrapolation the citation does not support — and
`BL-17.md`'s own roadmap entry for this exact decision says the opposite about certainty:
*"Unknown what STT does, does it become 30 or thirty... Settle with real whisper output when the
re-plan picks this up."* The docstring now states as measured fact something the project's own
roadmap entry, two sections earlier in the same file, calls unmeasured.

This does not make the *decision* wrong — point 2 of the implementation's own three-point
rationale (the numeral-token path through `_consume_digit_run` already parses a numeral, and
D14's word-grammar fallback already parses a spelled word, so the fix is safe under **either**
outcome) stands on its own without needing point 1's generalization at all, which is why nothing
here is a design problem. It is a citation-accuracy problem: a future reader hits this docstring,
trusts the cited research as having settled the composed-number case, and does not know Stage 3c's
real corpus recording is still the thing that actually settles it.

**Fix needed (mechanical, no behaviour change):** reword `rule_words()`'s docstring and
`TestRuleWordsNeverCarriesComposedNumberWords`'s class docstring so the citation is scoped to what
was actually measured (a single digit word in a clock-position context) and the composed-number
case is named as an inference from that plus the digit-run/word-grammar fallback's existing
coverage, not as something the research itself measured — a one-line hedge pointing at
`BL-17.md`'s own "Settle with real whisper output when the re-plan picks this up" is enough so the
next reader knows Stage 3c's corpus bench is where this actually gets confirmed.

### E12 revision (directive words become fuzzy) — sound, well tested

- **Directive fuzz scores base word + directives as one phrase**: `_match_elements`'s
  `WordSetElement` branch now calls `_resolve_word_set` and folds its ratio into the same
  `word_ratios` list a `LiteralElement` feeds; `match_pattern_with_ratio` averages them together.
  Traced and measured by hand against the shipped `turn_heading_relative` pattern: "tern left"
  scores `(0.75 + 1.0) / 2 = 0.875`, matching both the production code and
  `test_mis_transcribed_literal_still_matches`/`test_mis_transcribed_literal_still_resolves_the_rule`.
- **Near-tie guard, verified at both the unit and the full-match level.**
  `_resolve_word_set("cab", ("cap", "cat"))` → `near_tie=True` (both score `2/3`, within
  `SEPARATION_MIN`), pinned directly by `test_word_set_near_tie_is_ambiguous_not_a_guess`; the same
  near-tie folded through the full grammar (`test_word_set_match_folds_near_tie_into_match_ambiguous`)
  comes back `ambiguous=True` from a **single rule with no competitor at all** — exactly E12's new
  claim, and `_match_rules` (`command_matcher.py`) correctly seeds its own `ambiguous` from
  `matches[0]`'s own `word_set_ambiguous` before the cross-rule separation check runs, so this is
  not lost or overwritten. `MatchResult`'s own pre-existing docstring contract (`ambiguous=True` ->
  "never treat this as a silent pick") is unchanged and still what a caller has to honour — not
  reverified here since body-layer is out of this diff's scope, same as the first review's own
  caveat.
- **"left"/"right" never silently swap.** `test_word_set_never_silently_flips_the_wrong_way`
  ("light" -> `"right"`, never defaulting to the first alternative) is a real test, not decorative —
  verified by hand that `_resolve_word_set` picks strictly by ratio, with tie-break only on an exact
  tie (`sorted` is stable, so the first-declared alternative wins a genuine tie — itself routed
  through `near_tie=True`, never silently committed).
- **Values (numeric slots) stay exact.** `SlotElement`'s branch in `_match_elements` is
  unchanged — no `_resolve_word_set` call, no ratio computed, `test_slot_value_is_never_fuzzy_
  repaired` still pins "free" (0.667 against "three", above `_WORD_REPAIR_FLOOR`) failing to parse
  as a digit.
- **The fuzzy-vs-exact split is documented as closed-set-vs-open-ended, not hard-wired to
  `WordSetElement`/`SlotElement`.** Confirmed in three places that all say the same thing
  consistently: the module docstring's revised E12 section, the `SlotElement` branch's own inline
  comment in `_match_elements`, and `implementation.md`'s own account of the user's
  self-correction on unit-class words. No code anywhere branches on `isinstance(element,
  SlotElement)` to decide fuzziness — it is a property of the element implementation each type
  happens to have today, exactly as documented.
- **`SEPARATION_MIN` relocation**: confirmed in both directions — `vocabulary.py` gains the
  constant with a comment explaining the move and its reason; `command_matcher.py`'s own former
  declaration is replaced by an import plus a pointer comment, consistent with how
  `_WORD_REPAIR_FLOOR` was handled in the first pass. `rule_patterns.py` imports it from
  `vocabulary`, never from `command_matcher` — no cycle reintroduced.
- **Interaction with Stage 3b's `category` field**: no conflict. `CompiledRule.category` defaults
  to `"always"` and this commit's own new `CompiledRule(...)` test constructions
  (`TestRuleWordsNeverCarriesComposedNumberWords`) rely on that default, same as every other
  pre-category fixture in this file. `server.py` (touched by Stage 3b, not by this commit) calls
  only `compile_rules`/`match_pattern` indirectly through `compile_rules`'s own collision checks,
  never `match_pattern_with_ratio` or `rule_words` directly, so the signature changes in this
  commit (3-tuple instead of 2-tuple) touch nothing `server.py` calls.
- **Widened collision probe**: `_sample_words_with_fuzzable_flags`/`_perturbed_sample` now treat a
  `WordSetElement` position as fuzzable, same as a `LiteralElement`. Verified this is a real
  widening, not cosmetic (`WordSetElement`'s own sample previously came back tagged `False`, now
  `True`). No new test proves the widened probe catching a *novel* word-set collision it would
  previously have missed — the implementation notes only claim (and the full `TestCompileRules`
  suite confirms) that nothing already shipped regressed. That is consistent with Stage 3a's own
  Optional Refinement on this exact point (the probe is "necessarily partial" by construction,
  one-sample-per-rule) — not a new gap this commit introduces, so not required here either.

### E3 — no near-tie becomes an action

Confirmed structurally: a `WordSetElement` near-tie sets `ambiguous=True` on the same `MatchResult`
field a cross-rule tie already uses, and nothing in this commit's diff touches whatever downstream
code (body-layer, out of scope) is responsible for honouring that flag. Within audio-adapter's own
contract, `ambiguous=True` always carries the *best*-scoring candidate in `token`/`slots` (never
`None`) specifically so a caller can describe it in a confirm question — this is the pre-existing
`MatchResult` docstring contract, unchanged, and correctly still respected by `_match_rules`'s new
code path.

### Required Fixes

1. **`rule_words()`'s docstring and `TestRuleWordsNeverCarriesComposedNumberWords`'s class
   docstring overstate what `research/2026-09-19-whisper-contract-and-grammar-probe.md` actually
   measured** — the citation supports a single-digit word decoding to a numeral in a clock-position
   context, not the unqualified "whisper already writes recognised numbers as numerals" the
   docstrings now assert, and `BL-17.md`'s own roadmap entry for this decision already calls the
   composed-number case unmeasured. Mechanical, no behaviour change: reword the citation to scope
   it to what was measured, note the composed-number case as an inference (safe either way, since
   `_consume_digit_run`/D14's word-grammar fallback cover both outcomes), and point at Stage 3c's
   real corpus bench as where it actually gets settled.

### Optional Refinements

- (Carried over, unaddressed by this commit and not required to be — see Stage 3a's own Optional
  Refinements section above): the D15 `anchor_words` cache-read race, the collision probe's
  inherent one-sample-per-rule partiality (now also true for word-set positions, not a new gap),
  and "three hundred and twenty" not parsing.

### Verdict

APPROVED WITH MINOR FIXES — Required Fix 1 from the original review is closed, correctly, in the
user's chosen shape; the E12 revision (directive-word fuzz, the near-tie guard, the closed-set-vs-
open-ended documentation, the `SEPARATION_MIN` relocation, the widened collision probe) is sound,
traced by hand against the shipped code, and well tested. One new required fix, of the same
"bounded and mechanical, not a design problem" shape as the original: correct the whisper-numerals
docstring citation so it does not claim more certainty than the cited research, or the project's
own roadmap entry two sections above it, actually supports.

### Review Confidence

Full read of this commit's diff (`command_matcher.py`, `rule_patterns.py`, `vocabulary.py`, both
changed test files) against the prior review's Required Fix 1, `BL-17.md`'s three verbatim
2026-11-17 decisions, and `implementation.md`'s two "Stage 3a review fix" sections. The grammar's
new fuzzy/near-tie behaviour was traced by hand against the shipped `turn_heading_relative` pattern
and the synthetic `cap`/`cat`/`cab` fixture, not just read. The whisper-numerals citation was
checked by reading the cited research file directly, not taken on the docstring's word. Not
independently re-verified: body-layer's own handling of the `ambiguous` flag from a word-set
near-tie (body-layer is untouched by this diff and stays out of this review's scope, per the
brief) and whether the widened collision probe would in fact catch a real word-set collision
beyond the regression check already run.
