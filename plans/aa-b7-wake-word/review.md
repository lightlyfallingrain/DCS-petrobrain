### Review Summary

Branch `fix/aa-b7-wake-word-routing` (tip `29f1f2f2`), fast-forwarded cleanly onto the pre-review
HEAD (`b46be8f7`, strict ancestor, clean tree). One commit: `command_matcher.opens_with_wake_word`
plus an early-return in `match_transcript` that returns `verb_anchored=False` when a transcript
opens with `[hey, ]petrovich` (fuzzy-matched at `WAKE_FLOOR=0.8`), before any verb anchoring runs.
body-layer is untouched — `verb_anchored=False` already routes to `"fallthrough"` in
`voice_commands.classify_response`, which `crew_console._act_on_voice_decision` sends to
`handle_line` → `_handle_utterance` → brain escalation. Verified that chain by reading
`voice_commands.py` and `crew_console.py` directly (no live probe needed; the routing is pure code,
no DCS dependency).

**Scope matches the plan and the user's decision exactly** — no more, no less. The fix lives in
the one file the defect is actually in (`command_matcher.py`), ahead of all verb-anchor logic
including the wake-greeting-only and bearing/slot branches, so a wake-prefixed command of any
shape (bare, slotted, bearing) now falls through uniformly. `opens_with_wake_word` is a small, pure
function with its own unit tests, not inlined logic duplicated at the call site.

**Mutation check** (not merely reading): commented out the new early-return block and reran
`test_command_matcher.py -k wake_word`. 11/11 of the new parametrized cases failed red, confirming
the guard is load-bearing and not a comment pinned by nothing. Restored cleanly before committing.

**Vocabulary sync rule** (`audio-adapter/CLAUDE.md`, "the whisper prompt is in sync... by
construction"): this fix adds no new spoken word or phrasing — `WAKE_FLOOR`/`_WAKE_WORD`/
`_WAKE_GREETING` reuse `vocabulary.PHRASES["wake_petrovich"]`'s existing two phrasings unchanged.
Nothing new needed to reach `to_prompt()`/`recognised_words()`, and `test_vocabulary.py` is
unaffected. Not applicable here, correctly.

**Edge cases checked against the task list:**
- Filler before the name ("um, Petrovich, where are we?") — covered, passes (`strip_filler` runs
  before the wake check).
- "hey" alone, "hey scan left" — covered by `test_wake_floor_rejects_words_that_only_begin_like_
  the_name`; both correctly do NOT count as the wake word (bare "hey" with nothing after it, and
  "hey" + a word that isn't "petrovich", both reject).
- Punctuation ("Petrovich.", "Hey, Petrovich! What do you see?") — covered, passes.
- Empty transcript — pre-existing `test_empty_transcript_does_not_anchor`, still passes; the new
  wake check sits after the empty-words short-circuit and is unreachable on empty input, correctly.
- **"Petrovich, where are we, never mind" (cancel_nevermind ending a wake-prefixed transmission)**
  — traced but **not tested**, and worth a decision. `opens_with_wake_word` fires first and returns
  immediately, so the trailing "never mind" is never seen by `cancel_nevermind`'s own branch; the
  entire utterance (including the retraction) goes to the brain as free text. Before this fix, the
  same transmission anchored on "petrovich" as a verb and almost certainly still failed to resolve
  `cancel_nevermind` (a 2-word phrase scored against a much longer sentence under
  `_phrase_match_ratio`'s length-normalised scoring falls well under `MATCH_FLOOR`), landing on
  "say again" instead — so this is not a regression from a working case, it changes one failure
  mode (say-again) into a different one (free text to the brain, retraction unobserved). This
  reads as consistent with `vocabulary.py`'s own stated design — "every decision happens at PTT
  release, with no exceptions" is about *command* decisions, and a wake-prefixed utterance is by
  the user's own 2026-10-25 decision never a command attempt at all, so there is no command
  decision for `cancel_nevermind` to retract here. Still, this specific case (a question followed by
  a correction, inside one wake-prefixed transmission) was not explicitly covered by the user's
  decision text and has no test. Flagging as optional, not required — see below.

**Stale-doc grep**: no file states the pre-fix behaviour as current. The hits found
(`plans/inbound-speech/implementation.md`, `plans/watch-reporting/implementation.md`,
`docs/acceptance/*.md`) are dated implementation/acceptance records describing an earlier stage's
design or an unrelated use of "anchors as a verb" (describing `follow`, not the wake word) — none
asserts, in the present tense, that the wake word currently anchors as a command verb.
`BL-B52.md`'s "closed by this decision" claim checks out: a wake-prefixed `report left` now goes to
the brain whole (verified via `opens_with_wake_word` firing before the slotted-report branch), so
there is no longer a slot to silently drop.

**Checks**: `ruff format --check`, `ruff check`, `mypy --strict` (run from inside `audio-adapter/`),
and `pytest` all clean/green (371 passed, 2 skipped — the two pre-existing live-binary/live-Piper
skips, unrelated to this change).

### Required Fixes

None.

### Optional Refinements

- **Add a test for a wake-prefixed transmission ending in `cancel_nevermind`** (e.g. `"Petrovich,
  where are we, never mind"`), asserting the current (and, per the analysis above, reasonable)
  outcome — `verb_anchored=False`, routed to the brain whole — so the behaviour is pinned rather
  than incidental. Not required because it was not asked for by the user's 2026-10-25 decision and
  the current behaviour is arguably correct, but it is exactly the kind of case this project's own
  checklist calls out, and a future change to branch ordering could silently flip it either way
  with nothing to catch it.
- `WAKE_FLOOR`'s own comment already flags it as "not measured against the user's own voice" — no
  action needed now, just worth remembering to revisit once a flight sample of the user saying
  "Petrovich" exists (the comment already says this; not a gap in the fix).

### Verdict
APPROVED

### Review Confidence
Full read — plan/decision record (`AA-B7.md`), the changed source file in full, the full test
file, the body-layer routing chain it depends on (`voice_commands.classify_response`,
`crew_console._act_on_voice_decision`/`handle_line`/`_match_radio_check_or_greeting`), `BL-B52.md`,
and a targeted stale-doc grep. Verified the end-to-end brain-routing claim by reading body-layer
code rather than running a live probe (no DCS/brain dependency in that path, so reading is
sufficient evidence). One mutation check performed on the core guard.
