### Review Summary

Reviewed stages 1-4 of `feature/tts-voice-output` (`ac9cce5`..`3994d0a`, plan-relevant commits
`ac9cce5` through `5cbd4e8`) against `plans/tts-voice-output/plan.md`, the recon it cites, and
root `CLAUDE.md`. This is a well-scoped, well-documented implementation that matches its plan
closely. All eight "check hardest" items were verified directly against the code, not taken on
the implementer's word, and all three subprojects' format/lint/type/test suites were re-run from
their own venvs rather than trusting the reported numbers.

- **Module independence (item 1):** confirmed. `srs-adapter/pyproject.toml` declares
  `dependencies = []`. `body-layer/src/belief/srs_client.py` and `srs-adapter/src/aircraft_client.py`
  are each independent `urllib.request` clients with no import of the other subproject — grepped
  for cross-references and found only docstring mentions, no `import` statements. The seam is
  HTTP end to end in both directions, matching the plan's Decision 1.
- **`winsound` guard (item 2):** reproduced both forms myself with a throwaway `mypy --strict`
  file. `try: import winsound / except ImportError` genuinely fails `--strict` on the Mac
  (`Module has no attribute "PlaySound"`); the static `if sys.platform == "win32":` form genuinely
  passes. The implementer's reasoning holds. `test_audio_sender.py` exercises the real
  `AudioPlaybackSender` (queue, FIFO order, urgent-preempt, failure isolation) against a fake
  `WavPlayer`, not a no-op — confirmed by reading the test file: `test_urgent_preempted_lines_are_never_played`
  genuinely blocks a fake `play()` call on an `Event` and asserts drop/interrupt behavior. This is
  real logic coverage on the Mac, not a stage-5-only test.
- **Urgent preemption (item 3):** `AudioPlaybackSender._clear_queue` drops queued routine paths
  and `_interrupt_playback` calls `player.stop()` before the urgent file is enqueued — genuine
  clear-and-interrupt semantics, not queue-jump-and-wait. `_interrupt_playback` is exactly the one
  small, separately named function the plan asked for so stage 5 can swap the `SND_PURGE`
  mechanism without touching queue logic.
- **Failure posture (item 4):** all three swallow points verified by reading the code:
  `tts_engine.py`/`server.py` (synthesis → 503, delivery → 500, both caught inside `_handle_speak`);
  `aircraft_client.py`/`srs_client.py` raise, but the callers (`CrewConsole._print`) catch them;
  `AudioPlaybackSender.play_audio`/`_run` never raise out. `CrewConsole._print`'s `overlay_client`
  and `speech_client` pushes are two separate `try/except` blocks — confirmed the isolation test
  (`test_failed_speech_push_degrades_without_raising_and_does_not_block_overlay`) actually makes a
  speech push fail and asserts the overlay push for the same line still lands.
- **`bypass_gate` threading (item 5):** `_print` passes `bypass_gate` straight through as
  `push_speech(..., urgent=bypass_gate)` — no new signal, no re-derivation. Confirmed by reading
  `crew_console.py` line ~654 and the corresponding test.
- **Endpoint consistency (item 6):** `POST /audio/play`'s handler is a structural copy of
  `_handle_text_push`/`_handle_command_petrovich_search` (same JSON-body validate/`_respond_json`
  pattern), no second request-parsing path. Base64 decoding uses `base64.b64decode(..., validate=True)`
  wrapped in `except (binascii.Error, ValueError)`, and separately rejects an empty decoded result
  — malformed input degrades to `400`, not an exception leaking to the handler.
- **Docs (item 7):** `srs-adapter/CLAUDE.md` matches the depth/structure of
  `aircraft-layer/CLAUDE.md`/`body-layer/CLAUDE.md`. All three touched `CLAUDE.md`s plus
  `WORKFLOW.md` were updated with the new endpoint/flag/field and describe concrete user actions
  (new `curl` example, new CLI flags, run commands). No claim is stated as verified-on-Windows;
  every `winsound`/`SND_PURGE` claim is explicitly marked unverified/stage-5.
- **Scope (item 8):** nothing beyond stages 1-4 crept in. No stage-5/6 stubs pretending to be real
  (no Windows-only code path claims to have been tested live beyond what the implementation log
  states was actually run).

**Verification re-run by the reviewer** (not trusted from the implementation log):
- `srs-adapter`: ruff format/check clean, `mypy --strict` clean, `pytest -q` → 21 passed (matches).
- `aircraft-layer`: ruff format/check clean, `mypy --strict` clean, `pytest -q` → 126 passed (matches).
- `body-layer` (run as `cd body-layer && mypy src`, per this subproject's CWD-only mypy config
  discovery note): ruff format/check clean, `mypy --strict` clean, `pytest -q` → 600 passed, 1
  xfailed (matches, xfail is pre-existing/unrelated).

All three subprojects' reported numbers held up exactly on independent re-run.

### Required Fixes

None.

### Optional Refinements

- **Strip `.claude/agent-memory/implementer/` changes from this feature branch (commit
  `3994d0a`) before merge.** AGENTS.md's side-quest rule is explicit that cross-cutting,
  non-code bookkeeping like agent memory belongs in a disposable worktree on `main`, not bundled
  into a feature branch's history — this commit does exactly what that rule warns against. It
  isn't a correctness problem (the content itself is accurate and useful), but it's a process
  deviation worth flagging as the plan directed. Recommend: before merging this branch, either
  drop this commit from the branch and re-apply the same memory content via a disposable worktree
  on `main`, or — if the user considers this low-stakes enough to leave — explicitly accept the
  deviation rather than let it pass silently. Not blocking; this is a one-line judgment call for
  the user, not a required fix.
- **`POST /audio/play` has no payload size cap.** A short callout's WAV is trivially small as the
  plan notes, and this is a LAN-only, single-user, no-auth surface already accepted at this
  severity class (plan Decision 6's security note) — so this is not a required fix. But since the
  base64 body is read fully into memory via `self.rfile.read(length)` before any validation, an
  oversized or malformed `Content-Length` could be a minor nuisance (not a new exposure class
  beyond what already exists on `/text/push`). Worth a one-line note if this endpoint's threat
  model is ever revisited, not now.

### Verdict

APPROVED

### Review Confidence

Full read — every file changed in `ac9cce5..3994d0a` was read in full (not just diffed), all
eight "check hardest" items were independently verified against the code and, where the plan
specifically asked for it, reproduced directly (the `winsound`/mypy claim). All three
subprojects' format/lint/type/test commands were re-run from their own venvs rather than trusting
the reported numbers, and all three matched exactly.
