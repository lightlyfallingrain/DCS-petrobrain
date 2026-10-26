### Review Summary

BL-B102 ("that"/"it" referent resolution), branch `feature/that-it-referent`, tip `7fc11f71`
(fast-forward merge into this worktree's HEAD, clean). Implements a single shared resolver
(`belief/referent.py`: `Mention`, `ReferentMemory`, `resolve_referent`) threaded through every
referent-bearing command (`where_is_it`, `mark_target`, `follow`, `select_target`, `engage`, the
`watch` family) via `CrewConsole._resolve_referent_target`, with mention-recording centralised in
`CrewConsole._print`.

Verified, not just read:

- **Re-grepped all 28 `self._print(` call sites** in `crew_console.py` against the plan's own audit
  table. Every call with a known subject passes `mentions`; every call with no subject (refusal,
  config-error, say-again, confirm-request, usage errors, point/scan readbacks, lost-contact lines)
  correctly passes none. `drain_events` is wired through `CalloutScheduler.last_spoken_mention`,
  reset unconditionally at the top of `tick()` and set on both the group and single-contact speak
  paths. `_handle_watch_nearest`'s mention (not in the plan's own table) is a correct, literal
  reading of Decision 2 and is traced through to `_speak_or_defer`. Found no silent miss.
- **Traced the mutable-list deviation** (`_handle_report`/`_handle_slotted_report`'s deferred-whole
  mention batch): the same list object flows from the handler's closure into either
  `self._pending_mentions` (immediate path) or `_PendingPositionalReply.mentions` (deferred path),
  and in both cases `render()` runs and mutates the list *before* `_print` reads it. Order is
  correct in both `_speak_or_defer` and `drain_pending_positional_replies`.
- **Target-priority rule (Decision 2, "that AAA" with a non-AAA target)**: confirmed in
  `resolve_referent` that the target only wins when its id survives the *qualifier-filtered*
  `matches` set, not merely because it is the active target — i.e. "where is that AAA" with the
  target being armor correctly resolves to the AAA, not the armor. Covered by
  `test_resolve_referent_target_priority_wins_over_a_qualified_match` (positive case: target is the
  AAA) and `test_where_is_that_aaa_...`/`test_where_is_it_referent_during_a_run` end-to-end in
  `test_crew_console.py` (negative case: target is armor, AAA still wins). Both branches exercised.
- **Decision 4 (lost-within-window still resolves from belief)**: mechanism is shared code, not
  per-handler — every referent handler calls the same `_resolve_referent_target` →
  `resolve_referent`/`_report_scope(restrict_to_ids=...)` path, and that path's "skip the
  `certainty == 'lost'` drop when `restrict_to_ids` is set" is a single `if/elif` in `_report_scope`.
  Bare referents bypass `_report_scope` entirely and never read `certainty` at all. Only
  `where_is_it` has an explicit end-to-end lost-contact test
  (`test_where_is_it_referent_resolves_an_unseen_lost_contact_from_belief`); `follow`/
  `select_target`/`engage`/`mark_target` rely on the shared mechanism rather than a duplicated one,
  which is why this is an optional gap, not a required fix (see below).
- **Branch-order / false-match check for `_SELECT_TARGET_VERBS`' new `"target"` entry**: computed
  the actual `difflib` ratios by hand (`ratio("target","engage")==0.5`, `ratio("engage","target")==
  0.5`, both exactly `VERB_FLOOR`) and traced that `_parse_select_slots`'s literal "target"-in-words
  gate (independent of the verb-anchor ratio) is what keeps bare "engage"/"engage target" correctly
  falling through to the engage branch rather than being hijacked by the new verb-anchor match —
  confirmed against `match_transcript` directly, not just the existing regression test asserting
  `"engage target"` still resolves to `"engage"`.
- **Regression**: ran `match_transcript` directly on every phrasing named in the review brief
  (`mark that`, `follow armor 2 o'clock`, `select target armor`, `mark target`, `where is target`,
  `watch nearest`/`watch nearest air defence`, `engage`, `engage target`, `target it`, `mark it`,
  `where is it`, `where is that AAA`, `follow it`, `follow that group`, `watch that`/`watch it`) —
  every pre-existing non-pronoun phrasing came back byte-for-byte unchanged (`None` slots, same
  token), every new pronoun phrasing resolved as designed.
- **Rendered `config/defaults.toml`**, not the `#:` comment: `REFERENT_WINDOW_S` renders correctly
  (first sentence, value, range, source line all consistent with the declaration), and
  `tools/generate_defaults.py` (run against the real venv) reports the file already up to date —
  not stale.
- **Full test/lint/type suites**, run from inside each subproject against its own `.venv` (this
  worktree had none — used the main checkout's per `implementation.md`'s own noted deviation):
  body-layer 2686 passed/4 xfailed, audio-adapter 390 passed/2 skipped, `ruff format --check`/
  `ruff check`/`mypy --strict` clean in both. Matches the implementer's self-reported numbers.
- `/invariant-check`-equivalent grep pass: no omniscience leak, no cross-subproject import, no
  `BINOCULAR_RANGE_MULTIPLIER` return, no stray `print()`, no bare `except`, no new TODO/FIXME. The
  two pre-existing `type: ignore` sites this diff adds are in test setup code
  (`store._contacts[...] = ...`), the same pattern already used elsewhere in the test suite
  (`test_belief_truth_log.py`).
- `git status --porcelain` clean; new files (`referent.py`, `test_referent.py`, plan/explore-
  notes/implementation/security-review docs, `BL-B102.md`) were already staged in the merged
  commit.

No scope drift found: the feature is confined to the referent mechanism and the six named command
tokens, per the ROADMAP entry's own "do not build new commands" scope note. Resolution logic lives
in a new `belief/referent.py` module per root `CLAUDE.md`'s actions/params shaping, not inlined into
`crew_console.py`'s dispatch — correct module boundary. No new dependency. Security plan review
(APPROVED, no required changes) is consistent with what the diff actually ships.

### Required Fixes

None.

### Optional Refinements

- **End-to-end lost-contact tests for `follow`/`select_target`/`engage`/`mark_target`** (not just
  `where_is_it`) would make Decision 4's "every referent-taking command" guarantee visible at the
  handler level, not only inferred from shared code — cheap to add (copy the `where_is_it` test's
  shape, swap the handler) and would catch a future per-handler regression (e.g. an added
  certainty filter on one handler's own result processing) that a shared-mechanism argument alone
  would not. Not required because the mechanism genuinely is shared, not reimplemented.
- **`descriptor == "group"` combined with another qualifier is a known, undocumented-to-the-user
  limitation** ("follow that 2 o'clock group" ignores the clock) — correctly flagged by the
  implementer in `implementation.md` and not reachable from any of the plan's worked examples. Left
  as-is per the implementer's own call; worth a one-line note in `BL-B102.md`'s roadmap entry if
  this surfaces in a live sortie.
- **`NO_REFERENT`'s wording** ("Unable, I don't know what you mean.") reads slightly more
  conversational than the project's other fixed `_UNABLE_TEMPLATES` entries ("Unable, on ground.",
  "Unable, attack run."), which are terser and name the blocking condition rather than describe
  Petrovich's own state of mind. Cosmetic; not worth a required fix, and changing it is a one-line,
  reversible edit if it reads oddly in the cockpit.

### Verdict

APPROVED

### Review Confidence

Full read — plan, explore-notes, implementation summary, security plan review, and the full diff
(`referent.py`/`test_referent.py` in full; every `crew_console.py` call site touching `_print`,
`_resolve_referent_target`, `_speak_or_defer`, `drain_pending_positional_replies`, `_handle_*` for
all six referent-bearing tokens, `drain_where_is_it`; `callouts.py`/`speech.py`/`body.py`'s diffs in
full; `vocabulary.py`/`command_matcher.py`'s diffs in full, including hand-computed `difflib` ratios
for the new verb candidates). Both subprojects' full test suites, formatter, linter and `mypy
--strict` run directly against their real `.venv`s, not taken on the implementer's word. One area
taken on the strength of shared-mechanism reasoning rather than a direct end-to-end test per
handler (lost-contact resolution for `follow`/`select_target`/`engage`/`mark_target` specifically,
versus the one handler — `where_is_it` — that has an explicit test) — flagged above as optional,
not a gap in this review's depth.
