### Review Summary

Reviewed `[[BL-B129]]` speech word fixes (D1, D3, D4, D5, D6; D2 measured and explicitly not
shipped) on `feature/speech-word-fixes`, tip `54741349`. Fast-forwarded this worktree from
`59192cfa` to the tip cleanly (strict ancestor, clean tree).

Read the plan's Decisions section by hand (no `U<n>` ids in this plan — `accepted-items-ledger.sh`
returns nothing for it, as expected for a plan written directly from the user's verbatim words
rather than through the Architect/`U<n>` convention). All six decisions (D1, D3, D4, D5, D6, and
D2's deliberate non-ship) are accounted for: built with tests, or explicitly declined with a
measured reason recorded in the research note and `implementation.md`. Nothing in the plan's
Decisions or Acceptance sections is unaccounted for.

**Checks run (full read, not spot-checked):**

- `audio-adapter`: `ruff format --check` pass, `ruff check` pass, `mypy src` pass (17 files),
  full `pytest -q -m "not slow"` — 564 passed, 2 skipped (matches `implementation.md`'s reported
  full-suite count).
- `body-layer`: `ruff format --check` — 2 pre-existing unformatted files, both unrelated to this
  diff (confirmed via `git diff --name-only` against the plan's base commit — only
  `flight.lua`/`test_rules_flight_actions.py` touched, and the latter formats clean on its own);
  `ruff check` pass; `mypy src` pass (91 files); `pytest -q -m "not slow"` — 3530 passed, 27
  deselected, 4 xfailed.
- `tools/check_rules.py` (body-layer), run with `--adapter-python` pointed at the real
  audio-adapter venv (absent from this worktree by default) — `ok: 1 rule file(s) checked`, all
  four checks (lua syntax, declarations, wording via the real collision check, handler dry run)
  ran, no warnings.
- Mutation/counterfactual checks performed directly (not just read):
  - Disabled D5's `_has_unaccounted_number` by hand → "right 45" resolves to `point` again
    (`{"relative": "right"}`); re-enabled → `token=None`. The guard is load-bearing, not vacuous.
  - D6: `match_pattern` against the real shipped pattern confirms "turn heading three one five"
    now resolves and "turn heading heading three one five" (the old-only-accepted wording) is
    rejected — exactly the claimed before/after.

**Judgment calls, addressed per the task's own list:**

- **D3** ("to"/"for"/"free"/"won"/"ate"/"niner"/"oh" → digits): deterministic table, read only
  from inside `_consume_digit_run`, which only `angle`/`quantity`/`heading`/`speed_target` call —
  confirmed structurally (grep) and by a dedicated test
  (`test_homophone_fuzz_never_fires_outside_a_numeric_slot`, a `WordSetElement` case). The
  `strip_filler`/`preserve` fix for "to" (also a filler word) is scoped to the rule-matching word
  list only inside `match_transcript`; the legacy pipeline's own `words` is untouched and its
  pinned "scan to the right" → `scan_right` case is re-tested with a rule active
  (`TestDigitHomophoneFillerConflict`). The char-ratio fallback the plan floated is deliberately
  **not** shipped — measured and rejected as unsafe (ordinary words like "degrees"/"down"/"right"
  would fuzzy-match a digit word at the shared 0.5 floor) and documented in the module as a
  named, deliberate omission. No homophone can turn a non-numeric utterance into a wrong command
  outside an anchored numeric slot — verified structurally, not merely assumed.
- **D4** ("alright" → "right"): scoped to `_HVRT_BARE_WORD_TOKENS` via a whole-transcript alias
  map (`_BARE_WORD_ALIASES`), not a global fold. The global-fold attempt and its measured
  regression ("alright then let's go" → `point`) are documented in both
  `vocabulary.normalize_for_match`'s docstring and `command_matcher._BARE_WORD_ALIASES`'s —
  genuinely tried and reverted, not assumed safe. Three free-speech sentences containing
  "alright"/"all right" are pinned to stay non-commands.
- **D5**: never resolves direction+number to `point`; "look right 5 kilometres" (legitimate
  relative+distance) still resolves — both directions tested, and the guard is checked only at
  the two `point`/`"what"` call sites in `_match_legacy`, not folded into `_parse_point_slots`
  itself (a deliberate, stated scoping choice).
- **D6**: `heading` slot is pure digits now; the anchor literal lives in `flight.lua`'s pattern,
  which `rule_words` already walks. Grepped for every `:heading>` slot reference across both
  subprojects — the **only** rule using it is `flight.lua`'s own `turn_heading`; no other rule
  file, doc, or stale sample references the old bare-slot-with-anchor shape. "heading 315" alone
  (no verb) is tested and confirmed rejected.
- **D1**: `flight.lua`'s diff is exactly the two "alt" removals claimed — no other wording in the
  file touched. Neither handler read `s.verb`, confirmed by the unaffected body-layer handler
  tests (plus the updated fixtures, which were stale relative to reality before this change, not
  newly broken by it).
- **Bench**: WRONG 1→0 as claimed. A_full's `ok` count genuinely drops 141→139, which is the
  literal opposite of the plan's own acceptance line ("correct count up"). This is flagged
  explicitly in both the research note and `implementation.md` rather than glossed over, and the
  trace is convincing: 3 clips are recordings of the now-retired "alt" phrasing (the user's own
  stated choice to drop it), and 2 more are an unrelated prompt-text-length wash the note
  correctly attributes to whisper's prompt-conditioned decoding rather than a defect. I accept
  this as a reasonable, well-evidenced judgment call rather than a required fix, but note that the
  plan's own acceptance wording is not literally met — worth saying to the user in plain terms
  alongside the WRONG-count win.
  `test_slot_value_is_never_fuzzy_repaired`'s edit ("free" → "degrees") is legitimate: D3 directly
  falsifies the original example by naming "free" in its own homophone table, and the replacement
  preserves the same ratio ballbark and the same claim (no *general* char-ratio fallback for a
  digit run).
- **Tuning**: no behaviour-affecting constant here goes through `body-layer/src/tuning.py` (it
  can't — this is `audio-adapter`, where the loader does not exist). The new tables
  (`_DIGIT_WORD_HOMOPHONES`, `_BARE_WORD_ALIASES`, `_RULE_FILLER_PRESERVE`,
  `_TENS_WORDS_FOR_NUMBER_DETECTION`) carry no "would want X-T26" note, but neither does any
  existing audio-adapter constant of the same shape (`VERB_FLOOR`, `MATCH_FLOOR`,
  `SEPARATION_MIN`, `_WORD_REPAIR_FLOOR`, the whole `PHRASES`/`TOKENS` vocabulary) — this is
  consistent with the subproject's existing convention, not a new departure, so I'm not treating
  it as a gap.

### Required Fixes

None.

### Optional Refinements

- State the bench's `ok` count drop (141→139) to the user in plain terms alongside the WRONG-count
  win when reporting this out — the plan's acceptance line says "correct count up," and the actual
  result is down by 2, fully explained but literally not what was promised. Not a code fix; a
  communication item for the hand-off. (optional)
- `check_rules.py`'s self-match step cannot catch an error shared between a slot type's own
  `sample()` and the `consume` it is meant to test (exactly what let D6's defect ship undetected
  for as long as it did) — `implementation.md` already names this as a follow-up rather than
  scope creep into this plan. Worth keeping on the backlog rather than letting it drop. (optional)

### Verdict
APPROVED

### Review Confidence
Full read — plan, implementation notes, research note, and the complete diff for every changed
source and test file; all checks re-run directly in this worktree (not taken on the implementer's
word), plus two independent mutation/counterfactual checks against the real code.
