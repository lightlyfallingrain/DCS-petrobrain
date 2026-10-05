### Review Summary

Reviewed `feature/spu8-intercom`, verified tip `d3444ffd54b003984ce348658b0c70558ec06794`
against a clean `git archive` snapshot (main checkout has this branch checked out, so the
worktree landed on `main` as expected — not reviewed). All checks re-run independently from the
snapshot using the main checkout's venvs:

- aircraft-layer: `ruff format --check` clean, `ruff check` clean, `mypy --strict` clean (19
  files), `pytest -q` **208 passed**.
- body-layer: `ruff format --check` clean, `ruff check` clean, `mypy --strict` clean (53 files,
  run with `cd body-layer && PYTHONPATH=src:../world-model/src`), `pytest -q` **1440 passed, 4
  xfailed**.
- audio-adapter: confirmed zero diff against the merge-base — untouched, as both plan and
  implementation log claim.

All numbers match the orchestrator's own measurement exactly. `git log main..feature/spu8-intercom`
is clean — every commit on the branch is on-topic for this feature (investigator recon, probe,
architect plan, amendment, implementation, the shadowed-`_ownship` fix); no side-quest commits.

This is a genuinely well-built slice: raw-plus-decided schema shape mirrors `PttSample` exactly,
the fail-safe-closed-vs-always-open default split (plan Decision 3) is implemented precisely where
documented, gate/volume are both checked at the single point the plan specifies (`_run`, immediately
before `play()`), and every doc comment I checked against the actual code was accurate rather than
aspirational — unusual for a branch that arrived with zero prior gate having run on it.

I empirically disabled four mechanisms and reran the targeted tests to confirm none are decorative:
gate check in `audio_sender._run` (2 tests failed as expected), `scale_wav_volume` call in `_run`
(1 test failed), the on-ground-silent branch in `maybe_apply_on_ground_default` (4 tests failed),
and the `spu8_gate_open` conjunction in `_handle_ptt_state` (2 tests failed). All four mechanisms
are real and covered; all files restored afterward and full suites re-passed (208 / 1440+4).

### Required Fixes

None.

### Optional Refinements

- `api/server.py`'s `_handle_ptt_state` re-derives "gate open" as
  `spu8_sample is not None and spu8_sample.gate_open` instead of calling
  `spu8_cache.gate_state().gate_open`, which already encodes exactly that fail-safe-closed logic
  and is the method the module's own docstring says exists for this. The two are provably
  equivalent today, but the gating rule now lives in two places that have to be kept in sync by
  eye rather than one. Low risk (both are three-line, well-commented, heavily tested), but worth
  collapsing to a single call next time this file is touched. (optional)
- `ON_GROUND_AGL_THRESHOLD_M = 10.0` and `MISSION_START_ICS_DELAY_S = 5.0` are both explicitly
  flagged in code/plan as uncalibrated guesses pending a live flight — correctly named, isolated,
  and documented per the plan's own risk list, not a defect, just noting it's not yet closed.
  (optional, tracked as a live-acceptance item below)
- Stage 5's on-ground default is wired into `_run_crew_text_poll_loop` only, not
  `_run_console_poll_loop` (the `--console` debug path). The plan explicitly scopes Stage 5 to the
  crew-text loop (not claimed as parallel across both), so this is not the "claimed-parallel-but-
  missing" pattern — just flagging that a developer debugging via `--console` won't see the
  mission-start silence behaviour and shouldn't be surprised by that. (optional)

### Verdict

APPROVED

### Review Confidence

Full read. Read the plan (all 5 stages + amendment), implementation.md, and the ROADMAP.md
provenance entry in full. Read every changed file in aircraft-layer (`schema/spu8.py`,
`collector/cache.py`, `collector/server.py`, `collector/audio_sender.py`, `api/server.py`,
`collector/__main__.py`, `Export.lua`'s diff) and body-layer (`crew_console.py`, `logger.py`) in
full, not excerpted. Cross-checked the live-probe figures (arg 377/664/457, thresholds, the
cross-seat write) against `audio-adapter/ROADMAP.md`'s Slice 2 entry, which carries the user's own
quoted spec and the 2026-10-05 probe results — no unverified-DCS-internals claim in this branch
lacks a research-directory citation. Ran every check myself from a clean snapshot rather than
trusting the implementation log's numbers, and empirically broke/restored four mechanisms to
confirm their tests are load-bearing rather than decorative. No part of this review was spot-
checked or skipped for time.

---

## Round 2: Security change request fix (`f1d39b9`)

**Verified tip:** `feature/spu8-intercom` @ `f1d39b9c63b17a5afdeffd9f2082414757e2c0c0` (matches the
expected sha given at dispatch). This worktree's own HEAD (`78c9ad6b`) is unrelated scaffolding, as
expected — the branch is checked out in the main checkout, so I snapshotted it: `git archive
feature/spu8-intercom | tar -x -C <scratch>` and ran every command with `cwd` inside
`<scratch>/aircraft-layer`, using the main checkout's `aircraft-layer/.venv/bin/{ruff,mypy,pytest}`.

### Scope

`git diff 5767168..f1d39b9 --stat` touches exactly three files:
`aircraft-layer/src/collector/audio_sender.py`, `aircraft-layer/tests/test_audio_sender.py`,
`plans/spu8-intercom/implementation.md`. No body-layer, audio-adapter, or `Export.lua` changes —
round 1's approval of those stands untouched.

### Checks (from the snapshot, `aircraft-layer/.venv` binaries)

- `ruff format --check src tests` — pass (48 files already formatted)
- `ruff check src tests` — pass (all checks passed)
- `mypy src` (`--strict`) — pass (19 source files, no issues)
- `pytest tests -q` — **210 passed**, matches the claimed baseline (208 + 2 new)

### Independent reproduction of the two guards (not taking the implementer's word)

Reverted each guard in the snapshot, in turn, and reran:

1. **Removed `ValueError` from `scale_wav_volume`'s `except` tuple** (left the `_run()` call-site
   wrap in place). Result: exactly one failure —
   `test_scale_wav_volume_handles_truncated_odd_length_pcm`, with the uncaught `ValueError:
   bytes length not a multiple of item size` surfacing at the `samples.frombytes(raw_frames)`
   line, as claimed. `test_run_survives_scale_wav_volume_raising` still passed — the call-site
   guard catches the (monkeypatched, directly-raised) error independently, confirming the two
   guards are not merely redundant copies of each other.
2. **Removed the `_run()` call-site `try`/`except Exception` around `scale_wav_volume(...)`** (left
   the parse fix in place). Result: exactly one failure —
   `test_run_survives_scale_wav_volume_raising`, with the worker thread dying on the first raise
   (visible as a `PytestUnhandledThreadExceptionWarning` with the full traceback) and the second
   queued item never reaching the player. `test_scale_wav_volume_handles_truncated_odd_length_pcm`
   still passed.

Both reverts restored; full suite reran clean (210 passed). The implementer's non-decorative claim
is correct: each guard fails its own test and only its own test, and they are genuinely independent
— the call-site wrap is defense-in-depth against a *future* unguarded path, not a duplicate of the
parse fix.

### Fixture fidelity

`_write_truncated_odd_length_pcm_wav` writes a real 10-sample 16-bit PCM WAV via the stdlib `wave`
writer (20 bytes of data, header declares `nframes` accordingly), then truncates the file to keep
only 15 (odd) bytes of that data chunk while leaving the header's declared `nframes` unchanged. This
is exactly Security's reproduced shape (`security-deep-analysis.md`): header `nframes` stale/too
large, `readframes` returns the truncated bytes without raising, odd byte count trips
`array("h").frombytes()`. Not a different malformed-file shape wearing the same name — confirmed by
reading the fixture against the bug report side by side.

### `except Exception` breadth at the call site

Judged justified, not too wide. The thing being guarded against is a daemon worker thread dying
*permanently and silently* while the LAN API keeps answering `200 {"ok": true}` — a failure mode
with no other signal anywhere, which argues strongly for breadth over precision here. It is not a
silent swallow: `logger.warning(..., exc_info=True)` logs the exception type and full traceback on
every catch, so a future unrelated `TypeError` from a refactor would still be diagnosable from logs,
just not fatal to the channel. The catch is scoped to the single `scale_wav_volume(...)` call, not
the whole loop body — `self._player.play(path)` two lines below keeps its own separate
`except Exception`, so a failure in one step can't be miscategorized as the other's.

### Required Fixes

None.

### Optional Refinements

None beyond what round 1 already recorded.

### Verdict

APPROVED

### Review Confidence

Full read, scoped to the three-file diff as directed. Reproduced both guard claims empirically by
reverting each in the snapshot and rerunning the suite, rather than trusting the implementation
log's account. Ran every mechanical check myself from the snapshot. body-layer, audio-adapter and
`Export.lua` were confirmed untouched by `git diff --stat` rather than re-reviewed — correctly out
of scope for a one-fix re-review, not a gap.
