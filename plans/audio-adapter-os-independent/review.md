### Review Summary

Reviewed AA-6 Stages 1-3 on `feature/audio-adapter-os-independent`, tip `b3c4623d` (5 commits:
`62e5b70f`..`b3c4623d`), against `plans/audio-adapter-os-independent/plan.md` (Decisions 1-8),
`implementation.md`, `audio-adapter/ROADMAP/AA-6.md`, `audio-adapter/research/2026-10-19-piper-
cross-platform-recon.md`, and `audio-adapter/CLAUDE.md`.

Verification note: this worktree's HEAD (`1b777fe7`) is on `main`, not an ancestor of the target
tip, so verification was done against `git archive b3c4623d | tar -x`, with `ruff`/`mypy`/`pytest`
run from inside that archive's `audio-adapter/` directory, borrowing `main`'s own `audio-adapter/
.venv` (no dependency changes between `5488d7d7` and `b3c4623d`, confirmed via `git diff --
audio-adapter/pyproject.toml`, so this is a faithful substitute for creating a fresh venv).

**Stage 1 (PiperEngine + outage state machine) and Stage 3 (CLI/run-scripts/docs) are solid** —
read in full, matched against the plan decision by decision, and verified correct by mutation
(flattening the outage state machine's warning/debug branch broke exactly the test meant to catch
it). **Stage 2 (Windows sink) has one real test gap**, found the same way: the test whose own name
and docstring claim "both survive one interrupt" does not actually observe both threads complete,
and passes unchanged when `interrupt()` is mutated to release only one of two in-flight waits.

### Required Fixes

- **`test_winsound_two_concurrent_delivers_both_survive_one_interrupt` (audio-adapter/tests/
  test_local_playback.py) does not prove its own claim.** Mutated `_WinsoundLocalSink.interrupt()`
  to release only the first of two in-flight `threading.Event`s (`for event in events[:1]:
  event.set()` instead of iterating all of them) — the full `test_local_playback.py` suite still
  passed, this test included. Cause: `thread.join(timeout=5)` returns silently if the thread is
  still blocked after 5s, and the test never asserts `not thread.is_alive()` afterward, so a thread
  stuck waiting out `_WIN_PLAYBACK_FALLBACK_S` (10s, since the test payload `b"not-a-real-wav"`
  is not a parseable WAV) is never noticed — the assertions (`purge_calls == 1`, `errors == []`)
  pass whether or not the second thread ever actually returned. Confirmed by timing: the mutated
  run of just this test takes ~5.1s (both the timeout and the stuck thread), the unmutated run
  takes ~0.03s (both release immediately) — the test's own runtime already hints at this, but
  nothing fails on it. Fix: assert both threads terminated (e.g. `assert not thread_a.is_alive()`
  and `assert not thread_b.is_alive()` after the joins, with a timeout comfortably below the 10s
  fallback), or use a short *valid* WAV fixture so `_wav_duration_s` returns a small number instead
  of hitting the 10s fallback on a bogus payload, removing the silent-timeout path entirely. Either
  is cheap; the second is probably cleaner since it also makes the test faster and deterministic
  rather than timing-dependent.

- **`audio-adapter/ROADMAP/AA-B1.md` still tells the reader to use `--voice`**, which no longer
  exists (replaced by `--piper-voice`, Decision 4): *"Auditioning candidates costs one `--target
  local --voice <name>` command each"* (line 10). This is the exact stale-reference pattern that
  was correctly fixed in `body-layer/ROADMAP/BL-B15.md` in this same diff (its own `--voice` →
  `--piper-voice` edit) but missed in `AA-B1.md`, inside `audio-adapter/`'s own `ROADMAP/` — the
  one place this plan's own "Second-order effect" section says AA-B1 picks this work up next.
  One-line fix: `--target local --voice <name>` → `--target local --piper-voice <name>`.

### Optional Refinements

- `run-scripts/run-piper-mac.sh`/`run-piper-windows.sh` do not check `$PIPER_VENV_PYTHON`/
  `$PIPER_VOICES_DIR` are set before using them — an unset var just runs `-m piper.http_server`
  with an empty leading token, which fails but not with a message naming the missing variable.
  Not a required fix: no existing run script in this repo does this check either (`run-brain.sh`,
  `run-console.sh`, etc. all use `$VAR` directly with no guard), so adding one here would be a new
  convention invented for this script alone rather than reuse of an existing one (root `CLAUDE.md`,
  "Do not reinvent the wheel"). Worth a repo-wide backlog item if the user wants this generally,
  not a per-script fix.

### Checklist Evidence

- **Outage state machine**: lock-guarded `_down` flag in `PiperEngine`, correct critical-section
  shape (read-and-set under one `with self._lock:`, log outside it) — verified this is race-free
  for the "two simultaneous failures" case the plan called out, since the mutation happens
  atomically inside the lock. First-failure-ever and first-failure-after-success both take the same
  path (`was_down` starts `False`). Non-200 vs unreachable get distinct messages (`Piper returned
  <code>` vs `Piper unreachable at <url>`). Recovery line fires once, on the first success after
  `_down`. All four transitions unit-tested against the loopback double; mutation-tested (see
  Summary) by disabling the debug/warning split, which broke `test_second_consecutive_failure_
  logs_only_debug` as expected.
- **Windows sink**: `sys.platform == "win32"` static guard (matches `audio_sender.py`'s
  `_WinsoundPlayer` precedent), no `type: ignore` anywhere in `local_playback.py`/`tts_engine.py`
  (grepped), `mypy --strict` passes clean. `interrupt()` is supposed to set every in-flight event,
  not just the latest — see Required Fixes for the gap in how this is tested, though the
  **implementation** itself is correct (`for event in events: event.set()` over the full tracked
  set, read with the lock held). Temp file cleanup confirmed on every path: `os.remove(tmp_path)`
  sits in the outer `finally`, which wraps the inner try/finally that discards the event — covers
  the success path, the `play_async` `RuntimeError` path, and the timeout-wait path alike.
  Exercised via the injected `_WinsoundLike` fake throughout, no real `winsound` call needed off
  Windows.
- **`piper.http_server -m/--model` requirement**: both new run scripts pass `--model
  en_GB-northern_english_male-medium`; both bind `127.0.0.1` explicitly (not the default
  `0.0.0.0`, which would expose `POST /download`); `$PIPER_VENV_PYTHON`/`$PIPER_VOICES_DIR` are
  read from `petrobrain.env` (sourced, not hardcoded), matching the project's existing per-machine-
  variable convention (`$DCS_COLLECTOR_IP` etc.) — confirmed `petrobrain.env` itself is not
  committed anywhere in the repo, consistent with every other run script's machine-specific vars.
- **`run-audio-adapter-windows.sh`**: mirrors `run-collector.sh`'s bare-`python.exe` pattern
  exactly (`pushd $PETROBRAIN_PATH/<subproject>/src && python.exe -m <module>`, no venv, no
  `PYTHONPATH`) — side-by-side diff confirms the same shape, consistent with `audio_adapter`
  having zero runtime dependencies (same reasoning `run-collector.sh` already applies to
  `collector`).
- **Stale `MacSayEngine`/`say`/`--voice` references**: grepped the whole archived tree. All
  remaining `MacSayEngine`/`say` hits are either historical/dated records (plans, ROADMAP items,
  `NOTES.md`, `docs/reviews/*`, left untouched on purpose per `implementation.md`'s own account)
  or correctly phrased as past-tense ("removed entirely", "used to for") inside the touched files
  themselves (`tts_engine.py`, `audio-adapter/CLAUDE.md`, `BL-10.md`). The one miss is
  `AA-B1.md`'s `--voice` command example (Required Fixes above) — not found by the Implementer's
  own grep pass, which per `implementation.md` covered `body-layer/ROADMAP/{BL-10,BL-B15}.md` but
  not `audio-adapter/ROADMAP/AA-B1.md`.
- **Behaviour constant**: `_SYNTHESIS_TIMEOUT_S` kept at 10.0s, `#:` comment correctly updated to
  cite the measured warm case (0.054-0.098s) and the unmeasured first-use-of-a-voice cost as the
  reason 10s stays generous headroom rather than being tightened to the warm number (Decision 7).
  Confirmed `body-layer/src/tuning.py` was correctly **not** used — this stays an ordinary module
  constant with a doc comment, per root `CLAUDE.md`'s explicit "outside body-layer the loader does
  not exist" rule, which this plan cites directly.
- **Docs outside audio-adapter**: `body-layer/ROADMAP/BL-10.md` and `BL-B15.md` diffs read
  accurate — `BL-10.md`'s historical "Slice 1" narrative is correctly left describing its own
  dated state (Mac/`afplay`-only) with a parenthetical noting the later supersession, not rewritten
  wholesale; `BL-B15.md`'s `--voice` → `--piper-voice` example is correctly updated (the one that
  `AA-B1.md`, above, was not).
- **Checks** (run from the archived tip, `audio-adapter/` only — the only subproject with code
  changes): `ruff format --check` — 29 files already formatted. `ruff check` — all checks passed.
  `mypy src` (strict, CWD-run) — success, no issues in 15 source files. `pytest` — 318 passed, 2
  skipped (the two live-env-var-gated Piper/whisper tests), matching `implementation.md`'s own
  reported numbers exactly.
- New files staged: confirmed via `git show b3c4623d --stat` — all new files (`run-piper-mac.sh`,
  `run-piper-windows.sh`, `run-audio-adapter-windows.sh`, the implementer-memory file,
  `implementation.md`) are present in the commit, nothing left untracked.
- No leftover debug code or TODOs found in the diff.

### Verdict

**CHANGES REQUIRED** — both fixes are small (a test assertion gap and a one-line doc edit), not a
rework. Once addressed, re-run `pytest audio-adapter/tests/test_local_playback.py -q` to confirm
the strengthened test still passes and would now fail under the same mutation, and this is
approvable without a further full pass.

### Review Confidence

Full read of Stages 1 and 3 (`tts_engine.py`, its tests, `__main__.py`, all run scripts, `CLAUDE.md`,
`BL-10.md`/`BL-B15.md`) and the Windows sink's implementation in `local_playback.py`. Stage 2's
*tests* were spot-checked by mutation rather than read line-by-line against every assertion in
`test_local_playback.py` (23 tests in that file, 12 new) — the mutation findings above are from
targeted runs against the two riskiest claims (outage-announcement debounce, "both survive one
interrupt"), not an exhaustive line audit of the remaining ~21 tests in that file.
