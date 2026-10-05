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
