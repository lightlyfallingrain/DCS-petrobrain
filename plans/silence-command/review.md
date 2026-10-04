### Review Summary

Reviewed `feature/silence-command` at tip `b0674ce` (confirmed via `git rev-parse HEAD` before
reading anything), two commits: `493ba6a` (body-layer) and `b0674ce` (audio-adapter). Read
`plans/silence-command/implementation.md` in full, the full diff of both subprojects, and ran all
four checks in each subproject's own fresh `.venv`.

**The choke point is genuinely singular.** Grepped every `speech_client` use in `body-layer/src`
— the only `push_speech` call site is `_print`'s, now gated `if self.speech_client is not None and
not self.silenced`, applying identically to the routine and `bypass_gate=True` urgent branches.
`speech_client.stop()` (used by `_handle_stop_talking`) is a separate, unrelated call and is
correctly left untouched by `silence`. No second route to TTS exists.

**Acknowledgement ordering is correct and tested.** `_handle_silence` checks `self.silenced` first
(no-op, nothing spoken again) and otherwise calls `_print([ack], now_sim)` *before* setting
`self.silenced = True` — confirmed by reading the code and by
`test_silence_speaks_one_word_acknowledgement_then_goes_quiet` /
`test_silence_twice_is_a_no_op_not_a_toggle`, which pin the exact pushed tuple, not just truthiness.

**Clearing is scoped correctly.** `handle_command` checks `token == "silence"` before the general
`self.silenced = False` reset, so a repeated `silence` sees prior state; every other token
(including `stop_talking`, and including a token this method has no dispatch branch for) clears it
unconditionally at the top, matching the design note's "any subsequent command — including one this
class doesn't act on". `_handle_utterance`'s `"handled"` branch clears it too; the `"escalated"`
branch (stray/unmatched speech) does not — verified by reading and by
`test_unrecognised_free_text_does_not_end_silence` /
`test_recognised_free_text_command_ends_silence`, both of which assert the actual boolean rather
than inferring it. The confirm/say-again paths in `_act_on_voice_decision` never reach
`handle_command` until a committed `affirm`, so an in-flight confirm question correctly does not
end silence on its own (matches the module docstring's claim that these three tokens are handled
above `handle_command` entirely).

**Suppressed, not deferred, confirmed by reading `drain_events`.** It calls
`self.scheduler.tick(...)` unconditionally every poll regardless of `silenced`, then `_print`s
whatever that returns — so an event is chosen/rendered/consumed at the scheduler's normal pace and
only the final `speech_client.push_speech` is skipped. `test_silence_suppresses_a_drained_callout_
that_would_otherwise_be_spoken` exercises this with a real `ContactStore.ingest`/`tick` cycle, not a
mock, and asserts both `len(spoken) == 1` and `speech_client.pushed == []` in the same test — this
is the one place a flood-on-resume bug would show up, and it is covered both for the suppression
side and the resume side (`test_silence_ends_and_the_next_drained_callout_is_heard`).

**The "quiet"/"quite" collision reasoning holds up against the actual matcher**, not just the
implementer's account of it. Independently traced `VERB_ANCHOR_WORDS`' derivation
(`command_matcher.py`'s own docstring: first word of every `PHRASES` entry) and confirmed a
one-word `"quiet"` phrase would indeed anchor and would sit close enough to `"quite"` to misfire —
the `TestSilence.test_adversarial_sentences_do_not_falsely_fire` class now pins the surviving
three-phrase set against exactly the adversarial sentences named in the design notes, and separately
confirms `"stop"` still resolves to `stop_talking`, not `silence`, and the cancel family is
untouched. Phrasing-vs-matcher collision risk (the diff's own stated highest-risk area) is covered,
not merely asserted.

**`CANCEL_TOKENS` membership is floor-only.** The frozenset has exactly one reader
(`voice_commands.py`'s own floor-selection line); `silence` joining it gives it nothing but the
elevated confidence floor, no cancel-family behaviour.

**The modified test** (`test_dispatched_command_tokens_all_return_something`) is a mechanical
consequence, not a weakening: it still iterates every token in `DISPATCHED_COMMAND_TOKENS` and
asserts a non-empty result for all but the now-two-member `NO_RETURN_VALUE_COMMAND_TOKENS` set,
where it still asserts the return value is exactly `[]`. The loop running in sorted order with one
shared `console` is safe because every non-`"silence"` token resets `self.silenced = False` at the
top of `handle_command`, before that token's own `_print` call — so `silence`'s position in the
loop cannot cause a later token to go silently unspoken.

Ran, independently, from each subproject's own fresh `.venv` built against this worktree's
`pyproject.toml` (body-layer now pulls in numpy transitively, as the task flagged; audio-adapter
stayed stdlib-only):
- body-layer: `ruff format --check`, `ruff check`, `mypy --strict src` all clean; `pytest -q` →
  **1398 passed, 4 xfailed** — matches the implementer's reported count exactly.
- audio-adapter: same three checks clean; `pytest -q` → **219 passed, 1 skipped** — also matches
  exactly.

### Required Fixes

None.

### Optional Refinements

- `stop_talking` issued while silenced also clears `self.silenced` (it falls through the general
  reset at the top of `handle_command` like any other token) and then calls
  `speech_client.stop()` — harmless today (nothing is queued to interrupt, since nothing was ever
  pushed while silenced), and it is a literal reading of "any subsequent command ends silence," not
  a bug. But it's an interaction the design notes don't call out explicitly and no test exercises
  it directly. Worth a one-line docstring note or a test if `silence`+`stop_talking` ever becomes a
  real two-command pilot habit — optional, not blocking.
- `HELP_TEXT` deliberately omits `silence`, matching `stop_talking`'s precedent (token-level
  commands reachable only via F10/voice, not the typed grammar). Consistent with the existing
  convention; no action needed, noting only because it's the kind of thing that looks like an
  omission on a skim.

### Verdict
APPROVED

### Review Confidence
Full read — both commits' diffs read in full, every `speech_client`/`CANCEL_TOKENS`/
`VOICE_ONLY_TOKENS` call site grepped and inspected, both subprojects' full check suites run from
fresh venvs built in this worktree (not reused from the implementer's report).
