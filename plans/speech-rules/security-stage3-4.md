## Security Deep Analysis: speech-rules (BL-17 Stages 3a, 3b, 3d, 4 + review fixes)

Branch `feature/speech-rules-matching`. Dispatch named expected tip `1e5ddd5e`; this worktree's own
`HEAD` (`fc282270`) was a strict ancestor of it and the tree was clean, but the tip was already
checked out in another worktree (`/Users/sg/Code/DCS-petrobrain-speech-rules-matching`, confirmed
at exactly `1e5ddd5e`), so per the dispatch's own fallback this was reviewed against an isolated
snapshot (`git archive 1e5ddd5e | tar -x`) rather than checking it out directly here. All reading,
greps, diffs and the empirical probes below ran with cwd inside that snapshot's `body-layer/`
(its `.venv` copied in from the matching worktree, same commit, to run real code rather than just
read it).

Reviewed: `body-layer/src/rules/{engine,actions,gates,loader}.py`, `body-layer/src/belief/
{crew_console,effector_engine,audio_client}.py`, `body-layer/src/body.py` (the `_poll_transcripts`/
`_request_effector_write`/poll-loop-drain regions), `audio-adapter/src/{command_matcher,
rule_patterns,server}.py`, `audio-adapter/src/audio_adapter/__main__.py`, the full diff
`c309092b..1e5ddd5e`, `plans/speech-rules/{plan,implementation,review-stage3a,review-stage3b,
review-stage3d,review-stage4}.md`, `body-layer/ROADMAP/BL-17.md`, the prior
`plans/speech-rules/security-stage0-2.md` and its Required Fix 1 (now confirmed landed, see
below), and the relevant test files (`test_rules_engine.py`, `test_rules_actions.py`,
`test_rules_effector_action.py`, `test_rule_gates.py`, `test_rules_flight_actions.py`, `test_body.py`'s
`_poll_transcripts` suite).

### Dependency Status

No new dependency. `lupa==2.8` (the one dependency this feature family added) is unchanged since
the prior stage's clean assessment (`security-stage0-2.md`); confirmed via `git diff c309092b..
1e5ddd5e -- '*/pyproject.toml'` (no output).

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/body.py:3982-3989` (`_poll_transcripts`) | `isinstance(value, (int, str))` slot-value filter, never widened to admit `dict` | **Confirmed defect, empirically reproduced.** Stage 4 ships `set_speed`'s `speed_target` union slot (`{"kind": "max"}` / `{"kind": "number", "value": N}`) — the first shipped rule to carry a non-scalar slot value across the real audio-adapter→body-layer wire. The sending side (`audio-adapter/src/command_matcher.py:566-570`, `_match_rules`) was correctly widened to `isinstance(value, (int, str, dict))`. `body.py`'s own mirror validator was not — confirmed by `git diff c309092b..1e5ddd5e -- body-layer/src/body.py` showing zero lines touched in this block, and by a standalone probe feeding `_poll_transcripts` the exact wire shape a real "speed two hundred" utterance produces: `console.calls == []`, the whole item silently `continue`d, never reaching `handle_transcript`. **`plans/speech-rules/implementation.md:1474-1479` explicitly claims this side was also fixed ("widening `body.py`'s own validator's `isinstance` check") — it was not; the written account is wrong**, caught only by reading the actual current source and reproducing the drop, not by trusting the stage's own notes. None of the 13 existing `test_poll_transcripts_*` tests exercise a dict-valued slot (the "malformed value" test uses `bool`, a different, deliberately-rejected case). | **Required Fix 1** |
| `body-layer/src/rules/engine.py:218-226` (`_make_action_wrapper`), `:340-341` (`_digits_readback`) | Prior stage's Required Fix 1 (`math.isfinite` guard on every Lua→Python `int()` conversion) | **Confirmed landed and correct.** Both sites now reject a non-finite float the same way as any other out-of-contract value (the action wrapper degrades to `{"ok": false}`; `digits()` raises `RuleRuntimeError`, correctly routing through `run_rule`'s own D6 error path rather than masquerading as a graceful "Unable." — matches `review-security-fix.md`'s own correction that these are architecturally different sites). No new Lua→Python `int()` conversion introduced by this batch lacks the guard — every new action in `rules/actions.py` (`FLIGHT_ACTIONS`, `EFFECTOR_ACTIONS`) routes through the same `_make_action_wrapper`, so the fix is structural, not per-action. | None |
| `body-layer/src/rules/engine.py:373-428` (`run_rule`) | New bare `except Exception` alongside `(RuleRuntimeError, RuleBudgetExceeded)` | **Sound, not a silent swallow.** Logs the rule id, file, and the exception's own type name before degrading to D6's `ACTION_FILE_ERROR_LINE`/`error=True` — a real stderr trace for debugging, never a crash of the poll loop or the REPL thread's `for line in sys.stdin` loop (the exact two propagation paths the prior stage's Required Fix 1 traced). `BaseException` subclasses (`KeyboardInterrupt`/`SystemExit`) are correctly left to propagate, since `except Exception` does not catch them. Matches the user's own BL-17.md decision ("failure is clear... body-layer does not crash"; rollback of a broken rule's own effects is explicitly not required). | None |
| `body-layer/src/rules/actions.py:294-324` (`_write_effector`), `body.py:6584-6594` (`_request_effector_write`) | `effector.write(name, value, says)` validated against `effector_registry_entries` (name exists, value is one of that effector's declared values) before `queue_effector_write` | **Sound — a rule cannot write any effector outside the curated `effectors.toml` registry, nor any value not declared for it.** Matches the existing BL-B66 allow-list pattern (security memory `project_cockpit_write_vocabulary_invariant.md`). `says` is capped at `MAX_SAY_LEN` (500) before the closure is ever called, matching `say()`'s own cap (Stage 3d review Required Fix 3, confirmed present). | None |
| `rules/actions.py` `ACTION_NAMESPACES` vs. `rules/gates.py` `GATE_REGISTRY` | A rule's declared category gates whether its *handler* runs at all (`rules.gates.check_gate`, before dispatch) — but every action namespace (`flight`, `effector`) is built once and handed to *every* rule file's environment regardless of that file's categories; nothing couples "which category may call which action/effector." | **Not exploitable today.** `GATE_REGISTRY` has no seat-specific category yet (`"always"`/`"flight_control"`-family only; the module's own docstring defers `"copilot_sight"`/pilot-seat categories "when those rule groups are ported"), and no shipped rule calls `effector.write` (`actions.py`'s own comment: "no shipped rule calls this yet"). Will become a real gap the moment a seat-restricted category *and* a seat-restricted effector both exist — nothing would then stop a pilot-category rule's handler from writing a copilot-only effector, since `effector.write`'s only check is "does this name/value exist in the registry," never "is the calling rule's category allowed to touch it." The user's own decision ("copilot rule cannot execute when Petrovich is in pilot seat and vice versa," `BL-17.md`) is about *dispatch*, not about which effectors a dispatched rule may then write — this is the unaddressed second half. | Filed `[[BL-B127]]` — not blocking this batch (no shipped rule exercises it) |
| `body-layer/src/belief/crew_console.py:3285-3326` (`drain_pending_rule_dispatch`) | Reads `self.pending_rule_dispatch` into a local, then (every branch but "still HOLD") writes `self.pending_rule_dispatch = None` unconditionally, no identity check against what it read | **A narrow cross-thread race, not a security boundary issue.** `handle_command`/`_handle_rule` is reachable from both the poll thread (voice) and the REPL thread (typed input); if the REPL thread sets a *new* hold inside this function's own read-decide-clear window, the new hold is silently wiped with no dispatch, no timeout, no spoken line. Same race *shape* this feature's own Stage 3d Fix 4 round 2 already fixed once for `pending_effector_writes` (buffer-then-commit, `project_bl17_fix4_rollback_races_fix1_drain.md`) — not applied here. Steady-state probability is low (requires a voice command *and* a typed command to both gate-`HOLD` inside the same poll's drain window; `check_gate`/`current_crew_state` do no I/O, so the window is a handful of bytecode instructions), and impact is low (a dropped hold, user repeats the command — no data or security loss). Not an attacker-reachable path. | Filed `[[BL-B128]]` — not blocking |
| `audio-adapter/src/server.py` (`_handle_put_rules`) | `category` field validated the same way `id`/`pattern` already are (non-empty string, 400 otherwise); carried through unchanged, read back by nothing on the adapter side this stage | Clean — matches `security-stage0-2.md`'s prior assessment of this endpoint's posture; no new unauthenticated capability. | None |
| `audio-adapter/src/rule_patterns.py` collision check (`_rules_collide`/`_is_genuine_collision`, D13's perturbed samples) | O(n²) over the pushed rule set, each pair now also generating one perturbed sample and (for the legacy-probe direction) running the real legacy matcher | Unchanged risk classification from `[[BL-B126]]` (filed last stage: no body-size/list-length cap on `PUT /rules`, not reachable under the default loopback-only `--host`). The per-pair constant factor is modestly higher than D9's original (one extra sample, a legacy-probe call), but `PUT /rules` is still only ever driven by body-layer pushing its own local, user-authored rule-file-derived set (≤19 rules shipped) — not reachable from a LAN scan under the current default. | None — `[[BL-B126]]` already covers this, not re-filed |
| `audio-adapter/src/stt_engine.py` prompt path (`D15`'s `CachedRulePromptProvider`) | Prompt now rebuilt only on `rule_registry.version` change, not per-transcript; still built from rule *literal* words only, never slot values | Same posture as `security-stage0-2.md`'s prior assessment — ASR decoder-bias text, `subprocess.run` with a list argument, no `shell=True`, no LLM reads this text. No new surface. | None |
| Grep across the diff for `eval`/`exec`/`pickle`/`subprocess`/`os.system`/`__import__`/`marshal`/`yaml.load` | — | No new hits anywhere in `c309092b..1e5ddd5e`. | None |

### Empirical verification

```
$ .venv/bin/python3 -I probe_speed_target_wire.py
calls recorded: []
CONFIRMED: the set_speed/speed_target item was silently dropped by _poll_transcripts's own
isinstance(value, (int, str)) filter.
```
(Full probe script and the real `.venv` run are described above; reproducible against the real
`body.py::_poll_transcripts` at this tip.) Existing suites, re-run against the snapshot, all still
pass — `tests/test_rules_engine.py tests/test_rules_actions.py tests/test_rules_effector_action.py
tests/test_rule_gates.py tests/test_rules_flight_actions.py`: 97 passed; `test_body.py -k
poll_transcripts`: 13 passed, 211 deselected — confirming the gap is real and genuinely untested,
not a probe artifact.

### Passed to Reviewer

- The consequence of Required Fix 1 above is player-facing ("speed max"/"speed <number>" does
  nothing, says nothing) — noted here as the security finding's own symptom, not given a separate
  correctness verdict.

### Verdict

**CHANGES REQUIRED** — Required Fix 1 only.

### Required Fixes

1. **Widen `body-layer/src/body.py`'s `_poll_transcripts` slot-value filter (~line 3984-3987) to
   admit a `dict` value, matching `audio-adapter/src/command_matcher.py`'s own `_match_rules`
   fix**: change `isinstance(value, (int, str))` to `isinstance(value, (int, str, dict))` (keep
   excluding `bool` as today). Recommend bounding the admitted dict's own shape at the same point
   — exactly one level of nesting, string keys, `int`/`str`/`bool`-excluded-`int` values only,
   matching the tagged-table convention `_consume_speed_target` actually produces — rather than
   accepting an arbitrary dict wholesale: `audio-adapter` is a separate process over this
   project's own named threat surfaces (supply-chain-compromised dependency, or a malfunctioning
   process), and `sandbox.table_from` hands a nested Python dict to Lua as raw "userdata" with no
   depth limit of its own (per `implementation.md:1480-1483`'s own account of why one level is
   tolerated) — bounding depth/shape at the validation boundary, rather than trusting the sender
   to keep producing only the tagged-table shape, is the cheaper place to hold that invariant.
   Add the mirror regression test `test_poll_transcripts_threads_a_dict_valued_slot_into_handle_
   transcript` (a `speed_target` item, asserting it reaches `handle_transcript` with the dict
   intact) alongside the existing `test_poll_transcripts_threads_slots_into_handle_transcript`, so
   a future slot-type widening on one side of this wire is caught here rather than requiring
   another full security pass to notice.

### Filed, not blocking

- `[[BL-B127]]` — `effector.write` has no coupling to the calling rule's category/seat; not
  exploitable today (no seat-restricted category or effector exists yet), flagged for whoever
  plans the seat-gating stage.
- `[[BL-B128]]` — `drain_pending_rule_dispatch`'s unconditional clear can lose a concurrent
  REPL-typed hold to the poll thread's own drain; low probability, low impact, not a security
  boundary issue, same race shape this feature already fixed once elsewhere.
- `[[BL-B125]]`/`[[BL-B126]]` (prior stage) — unchanged, not re-filed.
