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
