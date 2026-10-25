### Implementation Summary

All four stages of `plans/that-it-referent/plan.md` (`BL-B102`) implemented: the core
mention-memory/resolver mechanism, `where_is_it`/`mark_target`'s referent forms,
`follow`/`select_target`/`engage`/the `watch` family's referent forms, and the regression pass
(full existing suites re-run unmodified, both subprojects).

### Files Changed

**body-layer**
- `src/belief/referent.py` (new) — `Mention`, `ReferentMemory`, `resolve_referent`,
  `REFERENT_WINDOW_S` tunable (`tuning.real`, 60.0 default, 15–180 range, `judgement` status).
- `src/belief/crew_console.py` — `_print`/`_speak_or_defer`/`_PendingPositionalReply` gain
  `mentions`; new `_pending_mentions` field (the "handler sets a narrow instruction, the caller's
  tail `_print` applies it" shape `last_command_target_contact_id` already uses) and
  `_referent_memory` field; `_report_scope` gains `restrict_to_ids` (skips the `certainty=="lost"`
  drop when set — Decision 4); new `_resolve_referent_target`/`_resolve_group_referent_target`
  helpers; `_handle_follow`/`_handle_watch_nearest`/`_handle_select_target`/`_handle_engage`/
  `_handle_mark_target`/`_handle_where_is_it`/`drain_where_is_it`/`_handle_report`/`_act` all
  thread mentions or a referent branch; `where_is_it_slots` co-moving field alongside
  `where_is_it_requested`.
- `src/belief/callouts.py` — `CalloutScheduler.last_spoken_mention`, set at every `tick` return,
  so the push path (`drain_events`) can record the same subject it just spoke.
- `src/belief/speech.py` — `"NO_REFERENT"` added to `_UNABLE_TEMPLATES`.
- `src/body.py` — clears `where_is_it_slots` alongside `where_is_it_requested` once
  `drain_where_is_it` has consumed it.
- `config/defaults.toml` — regenerated (`REFERENT_WINDOW_S`).
- `tests/test_referent.py` (new), `tests/test_crew_console.py` (extended).

**audio-adapter**
- `src/vocabulary.py` — `REFERENT_WORDS = ("it", "that")`, `parse_referent`; added to
  `recognised_words()`'s sources (user direction 2026-10-23: every slot word enters the whisper
  prompt).
- `src/command_matcher.py` — `referent` slot added to `_parse_follow_slots`/`_parse_select_slots`/
  `_parse_engage_slots`; new `_parse_where_is_it_slots`/`_parse_mark_slots`/`_parse_watch_slots`
  and their `match_transcript` branches; `_SELECT_TARGET_VERBS` gains `"target"` (see Deviations).
- `tests/test_vocabulary.py`, `tests/test_command_matcher.py` — extended.

### Tests Added

- `test_referent.py` — `ReferentMemory` (last-line-wins within one batch, window pruning, empty
  record doesn't disturb `last`); `resolve_referent` (bare-last, expired→unable, qualified-filter,
  target-priority over a qualified match, nearest-wins tie-break, group→lead-member reduction,
  the `group_membership_state is None` fallback, no-resolvable-group→unable, and the orchestrator's
  required case: a bare referent resolves a contact even after it has gone `"lost"`).
- `test_crew_console.py` — 13 new tests: `where_is_it` with no target selected but a referent
  resolves (not "No target"); target-priority during a run; a more-recently-mentioned contact
  beating the engaged target; **the required unseen/lost-contact end-to-end case** (mention
  recorded after the contact has already gone `"lost"`, `where is it` within the window still
  gives the positional answer, not "unable"); expired referent → "unable"; `follow`/`target`/
  `engage`/`mark`/`watch` referent forms end to end through `handle_command`; a `report` batch
  recording every in-scope contact as one mention; `follow that group` reducing to a member.
- `test_vocabulary.py` — `parse_referent`, `REFERENT_WORDS` membership in the prompt-word
  staleness check.
- `test_command_matcher.py` — `TestReferentSlots` (16 tests): every referent-bearing phrasing,
  the explicit-"target"-anchor split (`where is target`/`mark target` unchanged), branch-order
  pinning (source-position assertions, same convention as the existing `follow`-before-`report`
  test), and adversarial non-command sentences containing "it"/"that".

### Checks

**body-layer** (`.venv` invoked by absolute path from the main checkout — see memory note below)
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict): pass
- `pytest tests -q`: 2686 passed, 4 xfailed (was 2674 passed before this change — net +12
  test functions, no regressions)

**audio-adapter**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict): pass
- `pytest tests -q`: 390 passed, 2 skipped (was 371 passed/2 skipped before — net +19 test
  functions, no regressions)

### Notable Discoveries / Deviations from the plan

1. **`_SELECT_TARGET_VERBS` needed `"target"` added, not in the plan's "Affected Modules" list.**
   The user's own worked example uses `"target that/it"` to mean "select that as the target," but
   `"target"` was never a legal first word of `select_target`'s own grammar (only its *noun*, as
   in "select target"). Without this, "target it"/"target that" anchor at the cheap verb-anchor
   check (ratio exactly `VERB_FLOOR`) but then fail every slotted branch's own verb check and the
   phrase table, landing on "say again" — the exact gap the plan's own Facts section measured for
   the other four phrasings but did not flag for this one. Checked the ordering carefully:
   `ratio("target", "engage")` is *also* exactly `VERB_FLOOR` (0.5), so without `select_target`'s
   branch running first in `match_transcript`'s existing order, "target it" would be genuinely
   ambiguous between selecting and engaging. The existing branch order (select_target before
   engage) resolves it correctly by construction — documented in both `_SELECT_TARGET_VERBS`' own
   comment and a dedicated test (`test_target_with_a_qualifier_and_a_referent`, and a branch-order
   test covering the three *new* parsers).
2. **`descriptor == "group"` cannot be routed through `_report_scope`'s ordinary qualifier
   filter.** `descriptor_verdict`'s own `"group"` branch answers a different question — a single
   contact's own multi-unit cardinality estimate (`cardinality.lo > 1`), not `belief.groups.Group`
   membership (the same distinction `_mark_watched_with_group`'s docstring already draws). Routing
   "that group" through the ordinary qualifier path filtered out exactly the group mention it was
   meant to select (a group's own members are each singular, `cardinality.lo == 1`). Added a
   separate `_resolve_group_referent_target` that matches `Mention(kind="group")` directly,
   bypassing `_report_scope` for this one qualifier value. **Known limitation, not built
   speculatively**: any other qualifier (clock/sector/relative/band) accompanying `"group"` is not
   applied by this branch — not reachable from any of the plan's worked examples, and `"follow
   that 2 o'clock group"` would currently ignore the clock and just take the most recent group
   mention. Flagging for Reviewer/future work rather than guessing at the right combined semantics.
3. **"Moving" being deferred (Decision 5) really does collapse "follow that moving group" and
   "follow that group" to the identical slot dict** (`{"descriptor": "group", "referent": True}`)
   at the audio-adapter layer, exactly as the plan anticipated — confirmed by running
   `match_transcript` directly rather than assuming it.
4. **`_handle_report`'s mentions had to be a mutable container, not a value passed once.** The
   report is "deferred as a whole" (the scope is recomputed at the tick it is actually spoken, not
   at dispatch time), so the mention batch can only be known inside the `_render` closure. Passing
   a plain `list[Mention]` to `_speak_or_defer` at dispatch time (empty) and having `_render` mutate
   that same list object when it runs — read back afterward by both the immediate tail-`_print`
   path (via `self._pending_mentions`) and the deferred path (`_PendingPositionalReply.mentions`,
   the same list reference) — avoided changing `_speak_or_defer`'s contract for every other caller.
5. **`_handle_watch_nearest` records a mention even though the plan's own audit table does not
   list it.** Decision 2 says "every line... sets the referent," which is broader than the table's
   worked-example-driven list; included it as the more literal reading of the decision rather than
   waiting for Reviewer to flag the gap the plan itself warned about ("the audit's starting
   point").
6. **No test classification string "OP_AAA" exists.** `belief.classification`'s real AAA op-class
   is `OP_ZU23` (renders as "Triple A", not "AAA" — `_unit_type_display`'s own table), corrected
   after the first test run failed on a literal-text assertion; later assertions use the
   discriminating clock position instead of unit-type wording where that's more robust.
7. **A fresh git worktree has no `.venv`** (gitignored, not shared across worktrees) — invoked
   both subprojects' real venvs by absolute path from the main checkout rather than symlinking
   (a symlinked `.venv` is not matched by a trailing-slash `.gitignore` pattern, so it would show
   untracked and risk being swept into a commit). Saved as implementer agent memory
   (`feedback_worktree_missing_venv.md`).

### Risks carried forward (from the plan's own "Risks & Unknowns", unchanged)

- `REFERENT_WINDOW_S` (60 s) has no live-sortie data behind it; `judgement` status, expect it to
  move once flown.
- The nearest-wins tie-break for an ambiguous bare referent is a deliberate reuse of this
  project's existing convention, not a new "ask" flow — same posture as before.
