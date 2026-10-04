---
name: project_silence_command_approved
description: silence command (body-layer+audio-adapter) reviewed APPROVED clean; how the single-choke-point and suppressed-not-deferred claims were independently verified
metadata:
  type: project
---

`feature/silence-command` (b0674ce) reviewed APPROVED, no required fixes. Two commits:
body-layer `493ba6a` (crew_console gate + ack), audio-adapter `b0674ce` (phrase wiring).

What held up under independent verification, not just reading the implementer's account:

- **Single choke point confirmed by grep, not trust.** Only one `push_speech` call site exists in
  `body-layer/src` (`CrewConsole._print`), gated `speech_client is not None and not self.silenced`
  on both the routine and `bypass_gate=True` urgent branches. `speech_client.stop()` is a separate,
  correctly-untouched call.
- **"Suppressed, not deferred" verified by reading `drain_events`**: `scheduler.tick` runs
  unconditionally every poll regardless of `silenced`; only the final `push_speech` is skipped. A
  real `ContactStore.ingest`/`tick` test (not a mock) pins both the suppression and the later resume
  in one place.
- **The "quiet"/"quite" collision reasoning was re-derived against the real matcher**, not taken on
  faith — `VERB_ANCHOR_WORDS` is the first word of every `PHRASES` entry, so a bare one-word
  `"quiet"` phrase really would anchor near `"quite"`. Worth the re-derivation whenever an
  implementer reports "measured a collision and dropped a candidate phrase" — cheap to confirm,
  and exactly the kind of claim that's easy to skim past.
- `CANCEL_TOKENS`/`NO_RETURN_VALUE_COMMAND_TOKENS` each had exactly one reader — confirmed via grep
  before trusting the "floor only, no other behaviour" claim.
- One real but harmless gap found and logged as optional only: `stop_talking` issued while silenced
  also clears `self.silenced` (falls through the same general reset every other token gets) — a
  literal reading of "any subsequent command ends silence," untested directly, not a bug.

Both subprojects' checks (`ruff format/check`, `mypy --strict`, `pytest`) run from fresh venvs
built in the worktree from each `pyproject.toml`, matching the implementer's reported counts
exactly (body-layer 1398 passed/4 xfailed; audio-adapter 219 passed/1 skipped). Confirms
body-layer's `pyproject.toml` now declares numpy transitively (world-model `coordinates` import) —
same cross-subproject dependency class flagged in [[feedback_check_agent_memory_staged]] and prior
memories about running both subprojects' suites, not just one.
