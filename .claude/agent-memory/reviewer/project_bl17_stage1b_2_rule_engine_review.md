---
name: bl17-stage1b-2-rule-engine-review
description: BL-17 Stage 1b (lupa rule engine) + Stage 2 (turn_heading_relative ported) review outcome, approved with minor fixes -- what to recheck when Stage 4+ ships more rules
metadata:
  type: project
---

Reviewed `feature/speech-rules` at `4dc79825` (Stage 1b `e417d852`, Stage 2 `41c8d72e`),
`plans/speech-rules/review-stage1b-2.md` has the full report. Verdict: APPROVED WITH MINOR
FIXES -- one required fix, a documentation-only correction to `plan.md`'s D8 text (see
`[[feedback_architecture_decision_text_vs_scoped_down_build]]`).

**What this stage actually built, for the next Reviewer pass on Stage 3/4+:**
- The sandbox (`body-layer/src/rules/sandbox.py`) isolates by omission (a fresh allowlisted `_ENV`
  table per file), not by lupa constructor flags or runtime mutation -- confirmed the code matches
  the Stage 0 research note's own probed findings exactly (fresh `string` copy, the `debug.sethook`
  Lua-shim wrapper, binary-chunk refusal).
- `rule_patterns.py`'s matching is **full-consumption, exact-literal**, not the fuzzy
  `_phrase_match_ratio` scoring D8's text describes -- a deliberate, disclosed scope-down for this
  one short-literal rule. Upstream filler/punctuation stripping (`strip_filler`/
  `normalize_for_match`) already absorbs most of the practical risk (verified by running
  `"turn left 30"`/`"Turn left, 30."`/`"turn left thirty"` through the real matcher). **Revisit
  when Stage 4+ ships rules with longer/more varied literal phrasing** (scan/report/watch) --
  exact-literal tolerance for a *mis-transcribed* literal word itself (not a filler insertion, not
  a digit-format variant) is the one dimension this choice is weaker on than the legacy path, and
  it has no test yet.
- `enabled_rule_ids` vs `_ever_enabled_rule_ids`: the second, grows-only set is necessary, not
  redundant -- it is what lets `handle_command` answer `NO_SUCH_COMMAND` for a *dropped* rule id
  while staying silent for a token that was never a command at all. Caught correctly by
  `test_mission_start_reset.py`'s generic reset-completeness check on the implementer's first full
  run (per `implementation.md`) -- that check is doing its job; no action needed, just note it for
  future fields added to `CrewConsole`.
- The import cycle between `rule_patterns.py` (needs the real legacy matcher for D9's rule×legacy
  collision check) and `command_matcher.py` (needs `rule_patterns` for D8's own rule branch) is
  resolved by injecting a `legacy_probe` callable from `server.py`, the one module that already
  imports both. Correct, not a workaround.
- A flaky full-suite failure (`test_slew_trace_is_written_from_the_real_poll_loop`, "ValueError:
  I/O operation on closed file") did not reproduce across two of my own full-suite runs; traced to
  unrelated pre-existing `pytest-xdist` teardown flakiness in code this stage never touched. Not
  a BL-17 defect.

**Checks run myself** (no venvs existed in this worktree): built fresh `.venv`s for both
subprojects from `/opt/homebrew/bin/python3.14`; `ruff format --check`/`ruff check`/`mypy --strict`
clean for both; `fast-tests.sh` and `fast-tests.sh --full` both pass clean for both
(body-layer 3472 passed/4 xfailed, audio-adapter 480 passed/2 skipped).

See `[[feedback_architecture_decision_text_vs_scoped_down_build]]` for the one required fix's
general lesson.
