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

---

## Re-review, 2026-10-25 — `6aa3ad67` (`BL-B100`: `parse_utterance` strips the leading vocative)

Reviewed on top of `da1eafd7` (the AA-B7 routing fix above, already reviewed + DoD-passed at
`8c07487f`). This is the body-layer-side follow-up DoD found and the user asked built on the same
branch: once AA-B7 sends a wake-prefixed transmission to the brain as free text, body-layer's own
`parse_utterance` still rejected it (start-anchored patterns), so a wake-prefixed contact question
got "Unable, no such command." instead of an answer.

### What changed

`body-layer/src/belief/utterance.py`: `_VOCATIVE_PREFIX = re.compile(r"^(?:hey\W+)?petrovi?t?ch\W*", re.IGNORECASE)`,
applied once (`count=1`) to `text.strip()` before the `_PATTERNS` loop. Two new tests in
`test_utterance.py` (leading wake word handled; trailing "petrovich" left alone and the reference
fails to resolve instead). Doc updates to `BL-B100.md` and `AA-B7.md` recording the fix and what is
still open ("where are we?").

### Checks performed

- **Regex correctness/over-match.** Anchored at `^`, so it can only ever strip at the very start of
  the string — no risk of eating a contact reference or any other word mid-sentence (the second new
  test, `test_wake_word_later_in_the_sentence_is_left_alone`, pins exactly this: a *trailing*
  "petrovich" is left as part of the reference text, which then fails to resolve and escalates,
  rather than being silently swallowed). `petrovi?t?ch` matches both of whisper's observed
  spellings (`petrovich`/`petrovitch`) plus two non-words (`petrovch`/`petrovtch`) that cost
  nothing since they never occur in practice. "petroch"/"Petrovna"/similar near-words do not match
  (the required `petrov` stem is absent). `\W*` after the stem correctly eats the comma/space/
  exclamation between the name and the question in all four of the first test's phrasings.
- **Mutation check.** Reverted the `_VOCATIVE_PREFIX.sub` line to the old `text.strip()` and reran
  `test_utterance.py`: `test_leading_wake_word_is_not_part_of_the_question` goes red (`'escalated'
  == 'handled'`), confirming the new test is load-bearing, not vacuous. Restored; full suite green
  again (verified via `git status --porcelain` showing no diff after restoring).
- **Brain escalation still gets the original transcript.** Read `_handle_utterance`: `parse =
  parse_utterance(self.store, transcript, now_sim)` strips only internally for its own matching;
  the `PlayerUtterance`/`EscalationPayload` built right after still carries the original `transcript`
  parameter, vocative and all. Confirmed live (not just by reading) — see end-to-end run below.
- **`_match_radio_check_or_greeting` (checked in `handle_line` *before* `_handle_utterance`/
  `parse_utterance`) is correctly left untouched, not a gap.** Traced the voice path: for live voice,
  "radio check"/"good morning Petrovich" without a leading wake word are matched directly by
  audio-adapter's `command_matcher` and never reach this body-layer grammar at all. A **wake-prefixed**
  "Petrovich, radio check" is, by AA-B7's own explicit 2026-10-25 user decision ("'[hey,
  ]Petrovich' at start is intentionally the keyword that means free text for the brain"), never a
  command attempt — it is meant to reach the brain as free text, same as any other wake-prefixed
  phrase, and the previous review already traced this exact routing chain and approved it. So the
  fact that `_match_radio_check_or_greeting`'s own pattern doesn't see past a leading vocative is
  consistent with the design, not a defect this commit should have also fixed. (I initially read
  this as a gap and verified it live before concluding it is not — see "End-to-end" below.)
- **End-to-end, via the real production entry point** (`CrewConsole.handle_transcript`, not just
  `parse_utterance` directly), run against this worktree's venv:
  - `handle_transcript("Petrovich, where is <contact>?", verb_anchored=False, ...)` → `["BMP-2."]`
    — resolves `describe_contact` correctly, matching card A14's intent.
  - `handle_transcript("Petrovich, where are we?", verb_anchored=False, ...)` → `[]`, with the
    pending escalation's transcript preserved verbatim as `"Petrovich, where are we?"` — correctly
    still open, exactly as `BL-B100.md`/`AA-B7.md` now say.
  - `handle_transcript("Petrovich, radio check", verb_anchored=False, ...)` → `[]`, escalated to
    the brain with the transcript preserved — the AA-B7-intended behaviour, not a BL-B100 defect.
- **Tuning.** `_VOCATIVE_PREFIX` is a regex, not a bounded scalar (no `real`/`whole`/`sequence`/
  `table` shape fits a pattern), so it correctly stays a plain module constant rather than going
  through `tuning.py` — confirmed it is absent from `config/defaults.toml` and
  `test_tuning_defaults_toml.py` still passes (no staleness).
- **Vocabulary/STT prompt.** No new spoken word or phrasing introduced (this is a body-layer parse
  fix, not a vocabulary change); `audio-adapter/src/vocabulary.py` untouched by this commit, so no
  action needed there.
- **Comment pruning.** No comment removed by this diff — the `_VOCATIVE_PREFIX` docstring-comment
  and the `BL-B100.md`/`AA-B7.md` updates are purely additive, and the superseded status line in
  `BL-B100.md` (`[ ]` → `[~]`) keeps the original text rather than deleting it, consistent with
  "supersession is marked, not deleted."
- **Scope.** Matches the plan exactly: one grammar fix, in the one place ("the grammar is the thing
  that cannot see past the name"), no wire change, console-typed lines get it for free as a side
  effect of sharing the same function — no more, no less.
- **Checks**: `ruff format --check`, `ruff check`, `mypy --strict` (run from inside `body-layer/`),
  all clean; `pytest body-layer/tests -q` → 2659 passed, 4 xfailed.

### Required Fixes

None.

### Optional Refinements

- None beyond what the earlier pass already flagged (the `cancel_nevermind` wake-prefixed case,
  still untested but accepted as correct-and-low-priority).

### Verdict
APPROVED

### Review Confidence
Full read — the changed source file, both new tests (plus a mutation check on the core one), the
two updated ROADMAP entries, and the full call chain from `CrewConsole.handle_transcript` down
through `handle_line`/`_handle_utterance`/`parse_utterance`. Verified end-to-end against a live
`CrewConsole` in this worktree's own venv (three transcripts: a contact question, "where are we?",
and a wake-prefixed "radio check") rather than relying on the unit tests alone. Perf and security
passes skipped per user direction for this commit.
