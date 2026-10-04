## Security Deep Analysis: silence-command

### Dependency Status
No dependency change. `git diff main..feature/silence-command -- body-layer/pyproject.toml
audio-adapter/pyproject.toml` is empty — confirmed directly, not taken from the plan's account.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/crew_console.py` `_print` (speech_client gate) | New boolean gate on the sole `push_speech` call site | Confirmed single choke point by grep: only one `push_speech` call site in `body-layer/src`, gated `if self.speech_client is not None and not self.silenced`, applying identically to routine and `bypass_gate=True` (urgent) branches | None |
| `body-layer/src/belief/crew_console.py` `_handle_silence` | Ack spoken via `_print` *before* `self.silenced = True` | Read in full: no-op branch returns immediately if already silenced; otherwise `_print` runs (unconditionally reaches the `speech_client is not None and not self.silenced` check while `self.silenced` is still `False`), then the flag flips. Every write inside `_print`'s per-sink pushes is wrapped in a scoped `except` (`AudioAdapterError`, `AircraftLayerError`, bare `Exception` for the log sink) — the one path not caught that way (`overlay_client.push_text_line` on a non-`AircraftLayerError` exception) would propagate *out* of `_handle_silence` before `self.silenced = True` executes, i.e. it fails toward "ack maybe not fully delivered but also not silenced" rather than toward "silenced without an ack." Fails safe, not stuck-on. | None |
| `body-layer/src/belief/crew_console.py` `handle_command` top | Clearing `self.silenced = False` | Plain in-memory assignment, executed before any fallible dispatch logic (parsing, I/O, scheduler calls) and before the token-specific branch. No exception from downstream dispatch logic can prevent this assignment from having already happened — "stuck on" is not reachable through this path. Confirmed by reading the full method body, not just the diff hunk. | None |
| `body-layer/src/belief/crew_console.py` `_handle_utterance` "handled" branch | Second clearing path for free-text intents | `self.silenced = False` is a plain assignment placed before `self._act(...)` is called — same fail-safe shape as above. The "escalated" (unmatched) branch does not clear it, matching the design intent (stray/unrecognised speech must not end silence). Confirmed by reading both branches. | None |
| `body-layer/src/belief/voice_commands.py` `CANCEL_TOKENS` / `classify_response` | Elevated `ACT_FLOOR_CANCEL` (0.80 vs. 0.60) confidence floor for `silence` | Not merely asserted in the plan — traced the actual decision path: `classify_response` (line ~430) computes `floor = ACT_FLOOR_CANCEL if token in CANCEL_TOKENS else ACT_FLOOR`; `CANCEL_TOKENS` now includes `"silence"`; this function is the one `handle_transcript` → `_act_on_voice_decision` actually calls for every live voice transcript. The elevated floor is live on the real voice path, not just a comment claim. | None |
| `audio-adapter/src/vocabulary.py` `PHRASES["silence"]` | Three static phrase strings added to a `dict[str, tuple[str, ...]]` | No interpolation of transcript text into anything executable — `command_matcher.py` (unchanged by this diff) does fuzzy string comparison (`difflib.SequenceMatcher`) against these literals, never `eval`/`exec`/subprocess/format-string construction from the match result. Confirmed `command_matcher.py` has zero diff in this feature. | None |
| `audio-adapter/src/vocabulary.py` | New token reachable only via `VOICE_ONLY_TOKENS`/`PHRASES`, consumed over the existing audio-adapter↔body-layer HTTP seam | The transcript's provenance (microphone → recognizer → HTTP POST into body-layer) is unchanged by this feature; no new ingress path was added for reaching the `"silence"` token — it goes through the same `match_transcript` → `classify_response` → `handle_transcript` pipeline every other voice token already uses. A replayed/forged POST to that seam is a pre-existing surface (LAN-only, single-user, no auth — out of scope per project posture), not something this feature newly opens or worsens. | None (pre-existing, not a regression) |

### Stuck-on / silenced-without-ack analysis (the two properties this review was asked to weigh most)

1. **Can `silenced` be set without the ack being heard?** No new way found. The only write site is
   `_handle_silence`, and it writes `self.silenced = True` strictly after the `_print` call that
   pushes the ack — never before, never in parallel, never in an `except` or `finally` block that
   could run regardless of outcome. An exception during the ack's own push fails toward *not*
   silencing (see table above), which is the safe direction.
2. **Can it get stuck on?** No. Both clearing sites (`handle_command`'s top, `_handle_utterance`'s
   `"handled"` branch) are plain boolean assignments placed before any fallible operation in their
   respective methods — there is no I/O, parsing, or external call between "a real command was
   recognised" and "the flag is cleared" that could throw and leave the flag set. The scheduler
   (`drain_events` → `scheduler.tick`) runs unconditionally regardless of `silenced`, so nothing
   about the suppressed state depends on code that could itself fail and leave the system wedged.
3. **Can it be set by anything other than the command itself?** Traced the one path in:
   `"silence"` only reaches `_handle_silence` via `handle_command("silence", ...)`, which is called
   from (a) the F10/token dispatch path, (b) `_act_on_voice_decision`'s `"act"` disposition (which
   requires `classify_response` to return `disposition="act", token="silence"` — gated by the
   elevated 0.80 floor, never by an `"escalated"`/unmatched/ambiguous/confirm-pending transcript),
   or (c) the `!voice` typed test harness. No path flows from an unresolved/ambiguous/low-confidence
   transcript, a stale queued utterance, or a replayed value straight into `self.silenced = True`
   without going through `_handle_silence`'s own gate.

### Verdict
APPROVED

No required fixes. This is a state-machine change confined to body-layer's `CrewConsole` and a
static phrase-table addition in audio-adapter; no new dependency, no new executable-from-input
surface, no new persistence or file-system path, and the two safety-relevant properties (ack always
heard before mute takes effect; mute cannot get stuck on) both hold by construction — verified by
reading the actual code paths and the confidence-floor decision function, not by trusting the plan's
or reviewer's account of them.

On the performance-pass question raised in the task: agreed no separate performance pass is
warranted — the change adds one `bool` check (`not self.silenced`) at the single existing
`push_speech` call site, on a path that already does synchronous HTTP I/O to the TTS engine. There
is nothing here for a performance review to measure.

### Checks run (from an isolated snapshot, both subprojects' own venvs — the branch tip was held by
another worktree, so verification ran against `git archive feature/silence-command | tar -x` into a
scratch directory, confirmed to be at tip `250270c` before anything else)
- body-layer: `ruff format --check src tests` clean, `ruff check src tests` clean, `mypy src`
  (`--strict`) clean (53 source files), `pytest tests -q` → 1398 passed, 4 xfailed.
- audio-adapter: `ruff format --check src tests` clean, `ruff check src tests` clean, `mypy src`
  (`--strict`) clean (15 source files), `pytest tests -q` → 219 passed, 1 skipped.

Both counts match the implementer's and reviewer's reported figures exactly.
