### Review Summary

Reviewed `62a8529b` (`feature/attack-run-los`) against `plans/attack-run-los/plan.md` and
`plans/attack-run-los/implementation.md`. Covers F2 (tier-keyed loss/regain register, replacing the
`cause == "too_far"` keying that let a stale `"obstructed"` verdict's decay to `"unknown"` read as
"regained sight" with no fresh look), Decision 2 (`terrain_blocked_held`, holding a genuine
`"obstructed"` verdict's consequence across its own freshness window), and F3 ("where is it?",
voice-only, answerable whenever a target is selected per Decision 1, "No target." otherwise per
Decision 1's verbatim wording).

Read `attack_run.py`, `speech.py`, `crew_console.py`, `logger.py`, `vocabulary.py` diffs in full,
plus every changed/added test in `test_attack_run.py`, `test_crew_console.py`, `test_logger.py`.
Ran format/lint/type/test for both touched subprojects (body-layer, audio-adapter) from this
worktree using the root checkout's `.venv` binaries (this worktree has none) — all pass, matching
the implementer's reported counts (body-layer: 2663 passed, 4 xfailed; audio-adapter: 349 passed,
2 skipped). Independently re-ran two of the implementer's mutations (`now_unresolved` reverted to
`cause == "too_far"`; the `effective_cause` substitution reverted to plain `cause`) and reproduced
the reported failures exactly.

### Rule-by-rule findings (per dispatch brief)

1. **Five changed `test_attack_run.py` tests.** Read each against the user's F2/Decision 2/Decision
   1 words directly. All five were pinning the pre-fix bug (via `_contact_at`'s documented
   tier-2-forcing, or a tier-1-then-stale shape that let range/cause alone "regain sight" with no
   live look) and were updated to assert the specified behaviour, not to work around an unrelated
   failure — confirmed by my own mutation run above, which fails exactly these (plus the three new
   F2 tests) when the fix is reverted. No changed test loosens or removes a user-stated guarantee.
2. **`terrain_blocked_held`/`effective_cause` scope.** Grepped the whole tree: both names appear
   only in `attack_run.py`, never in `contacts.py`/any `PositionBelief`/`Contact` field. No new
   consumer of `Percept.relative_direction` outside the pre-existing file set
   (`attack_run.py`/`contacts.py`/`optic_policy.py`/`percept.py`/`sight_head.py`/
   `perception/{detection_trace,estimation,geometry,naked_eye_source,source,visibility}.py`) — this
   diff only touches `attack_run.py` among that set. Set/clear rules match the plan's spec exactly
   (masked freezes, tier 1 clears, `cause == "obstructed"` sets, otherwise carries forward), and the
   update is committed in `decide()` only after the masked early return, so a masked tick genuinely
   commits nothing.
3. **`query()`/`drain_where_is_it`.** `query()` never calls `_should_emit` (grep confirms that name
   appears only inside `decide()`/its own docstring) and never calls `replace(state, ...)` — purity
   confirmed by both the identity-equality test and by reading the function body. `drain_where_is_it`
   is gated in `logger.py` by `if crew_console.where_is_it_requested:`, so it is a true no-op when
   not requested, and it clears the flag itself afterward. "No target." text is exact (`"No
   target."`, grepped both source and test).
4. **Voice-only vocabulary.** `vocabulary.py` adds `"where_is_it"` to `VOICE_ONLY_TOKENS` and three
   phrasings to `PHRASES` ("where is it" / "where is target" / "where is it now") — no filler
   article, consistent with the module's own rule. `PHRASES`/`TOKENS` parity is asserted in the
   module itself, so `recognised_words()`/`to_prompt()` picks the new phrasings up for free — the
   STT-prompt-agreement rule is satisfied without a separate check needed. `crew_console.py`'s typed
   surfaces (`handle_line` → `_handle_utterance` → `parse_utterance`'s set_attention/describe_contact
   grammar, and `_match_radio_check_or_greeting`) are untouched by this diff and have no path to the
   `"where_is_it"` token — confirmed by reading `_handle_utterance`, which only ever calls `self._act`
   (from `parse_utterance`'s own grammar) or escalates to the brain; `handle_command`'s token
   dispatch (where `"where_is_it"` lives) is reached only via `handle_transcript`/the dev harness's
   `!voice`, per Decision 3.
5. **Checks + mutation.** All green, as reported above; two independent mutation reproductions
   confirm the implementer's own results rather than merely trusting the report.

### Required Fixes

None.

### Optional Refinements

- **Command map is stale** (`python3 .claude/scripts/command-map-check.py` reports `not on the map:
  where_is_it`) — plan step 7 names this as an explicit step. The implementer correctly deferred it
  to the main loop (`/command-map`) rather than improvising it from inside the Implementer role; flag
  it here so it is not forgotten before merge/DoD, not as a defect in this diff.
- `test_decide_tier_transition_speaks_the_qualifier_without_flipping_direction` and
  `test_decide_lined_up_tier_transition_speaks_once_each_way` now each assert through one extra
  "transition text differs from steady text, so it speaks once more before settling" tick
  (documented in both the plan's "Notable Discoveries" and the test docstrings). This is pre-existing
  `_should_emit` behaviour, not new, and is already called out — no action needed, noted only so a
  future reader of the speech log for an "obstructed" episode is not surprised by two lines close
  together.

### Verdict
APPROVED

### Review Confidence
Full read — plan, implementation notes, and every changed/added line across all code and test
files in the diff; mechanical checks (ruff/mypy/pytest) run for both touched subprojects from this
worktree; two independent mutation reproductions run directly rather than trusting the implementer's
report.
