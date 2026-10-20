# DoD Check: audio-adapter-os-independent (AA-6, Stages 1-3 batch)

Scope: Stages 1-3 only (Piper HTTP engine, Windows local-playback sink, CLI/run-scripts/docs
wiring). Stage 4 (live verification on Mac and Windows) is explicit scope that needs the user —
see "Stage 4 Acceptance Checklist" below, not run here.

Branch: `feature/audio-adapter-os-independent`. Tip checked: `6e200483b714d00f86b607e8aa59af59a7a6491d`
(`Security deep analysis: AA-6 Stages 1-3 (audio-adapter-os-independent) — APPROVED`).

## Code Quality

| Check | Status | Notes |
|---|---|---|
| `ruff format --check` (audio-adapter/src, tests) | PASS | 29 files already formatted |
| `ruff check` (audio-adapter/src, tests) | PASS | all checks passed |
| `mypy --strict` (`cd audio-adapter && mypy src`) | PASS | no issues in 15 source files |
| `pytest audio-adapter/tests -q` | PASS | 318 passed, 2 skipped (live-env-var-gated Piper/whisper tests) |
| body-layer checks | N/A | only `body-layer/ROADMAP/{BL-10,BL-B15}.md` touched (docs), no source — confirmed via `git diff --name-only` |
| Debug output in touched files | PASS | none found; `capture.py`'s `print()` calls are pre-existing CLI console output, untouched by this diff |
| TODO/FIXME/HACK/XXX in touched files | PASS | none found |
| Bare `except:`/silent suppression in touched files | PASS | none found |
| File size (`local_playback.py` now 451 lines, up from 259) | NOTE, not blocking | Crosses the 400-line split guideline, but this is a plan-approved, reviewed decision (Decision 2: Windows sink shares the file so the `sys.platform == "win32"` static guard keeps `mypy --strict` clean without `# type: ignore` — same shape as `audio_sender.py`'s own precedent). Not re-litigated here. |
| New files staged | PASS | `git status --porcelain` clean at tip; all new files present in the commit history (`run-piper-mac.sh`, `run-piper-windows.sh`, `run-audio-adapter-windows.sh`, plan/review/implementation docs, agent-memory files) |
| Agent-memory path | PASS | all new agent-memory files under repo-root `.claude/agent-memory/<role>/`, none nested under a subproject |

## Scope & Correctness

- Implementation matches `plans/audio-adapter-os-independent/plan.md` Decisions 1-8 — confirmed by
  Reviewer's decision-by-decision read (`review.md`) and independently spot-checked here (Piper
  bind address, outage-announcement log strings, CLI flag names, run-script shapes all match the
  plan's text).
- No unplanned scope added: `implementation.md`'s file list matches the plan's "Affected
  Modules/Files" list exactly, plus two grep-found stale-reference fixes outside `audio-adapter/`
  (`BL-10.md`, `BL-B15.md`) that the plan's own "Second-order effect" anticipated as needing
  cleanup.
- No CLAUDE.md invariants violated: `audio-adapter` stays stdlib-only (Piper lives in its own
  venv, never a declared dependency); the body-layer↔world-model in-process-import exception is
  not touched or extended; no DCS-authoritative-state claim is made or altered.
- All new/modified files staged — confirmed, see above.

## Testing

- Core logic covered: `PiperEngine`'s wire format, failure modes, and all four outage-state-machine
  transitions (`test_tts_engine.py`); the Windows sink's deliver/interrupt/concurrent-interrupt/
  cleanup paths against an injected `_WinsoundLike` fake (`test_local_playback.py`).
- Tests are meaningful, not decorative: Reviewer mutation-tested both the outage debounce logic and
  the "two concurrent deliveries both survive one interrupt" claim; the first review pass found and
  the fix commit closed a real gap (a stuck thread going unnoticed because the test never asserted
  `not thread.is_alive()` after a timed join — now fixed, see `review.md` and `NOTES.md`'s new
  "Testing & Provenance" entry on this exact gotcha).
- No existing tests broken: `pytest` is 318 passed / 2 skipped at the tip, matching the numbers
  `implementation.md` and both review passes report.

## Documentation

- Reviewer's two Required Fixes (test assertion gap, stale `AA-B1.md` `--voice` reference) are both
  addressed and re-reviewed APPROVED (`review.md`'s re-review section).
- Non-obvious behaviour explained: the outage-announcement state machine, the Windows sink's single
  global sound-slot limitation, and the "Piper must be running even for `--target local`" change
  are all documented in `audio-adapter/CLAUDE.md` and/or `tts_engine.py`/`local_playback.py`'s own
  docstrings. Two generalizable findings (Piper's macOS binary dead-end, the timed-join test
  gotcha) added to root `NOTES.md` — see "Notes Harvest" below.

## Security

- `plans/audio-adapter-os-independent/security-review.md` (deep analysis, post-Reviewer): **APPROVED**.
- `plans/audio-adapter-os-independent/security-plan-review.md` (plan-stage, post-Architect): **did
  not exist before this DoD pass** — the role sequence (Architect → Security plan review →
  Implementer → ...) skipped straight from plan-approval to Implementer, with no plan-review
  commit or document anywhere in the branch history. This is the second occurrence of this exact
  gap on this project (first: `emitter-visibility`/BL-B72, 2026-10-15); see
  `.claude/agent-memory/dod/project_security_plan_review_skipped_by_collapsed_turn.md`, updated
  this pass to mark it a confirmed recurring pattern, not a one-off, and to recommend a
  dispatch-time hook mirroring `flight-feedback-dispatch-gate.sh`.
  **Closed retroactively this pass**: dispatched Security to review the plan after the fact.
  Verdict: **APPROVED** (`plans/audio-adapter-os-independent/security-plan-review.md`, commit
  `4b4b49e0`). One finding not caught by the earlier deep-analysis pass: Piper's own transitive
  dependency `onnxruntime` carries a real advisory (CVE-2026-14647, OOB read/potential RCE via a
  crafted `.onnx` model file, fixed upstream in `onnx` 1.22.0) — assessed **not reachable** here,
  since voice models are hand-fetched by the operator and Piper's own `POST /download` (the only
  path that could load an untrusted model) is bound away to loopback-only per the plan's own
  Decision 1/5; `PiperEngine` never calls `/download` and no inbound `/speak` field influences
  which model loads. Not filed as a backlog item; recorded in security agent-memory with a
  re-open condition (if `/download` is ever exposed, or model selection ever becomes
  caller-influenced). Also flagged, non-blocking: the GPL-3.0-or-later license of the `piper-tts`
  package Piper is distributed as (vs. the archived MIT-licensed C++ binary this project can no
  longer use) is a documentation consideration given this project's public-open-source intent —
  surfaced for the user, not acted on here.

## Milestone-Completion Question (root CLAUDE.md)

Does landing Stages 1-3 change what the next milestone should be, or invalidate a downstream
assumption? **No for the code** — the plan's own "Second-order effect" already named AA-B1 (voice
character/accent) as unblocked at near-zero marginal cost, which still holds. **But AA-B1 cannot
itself be live-verified until this milestone's own Stage 4 runs** — Stage 4 is the first real
cross-machine hearing of the decided voice, which AA-B1's auditioning work depends on. Recorded on
`audio-adapter/ROADMAP/AA-6.md`.

## Notes Harvest

Added to `NOTES.md`:
- "External Binaries & CLI Utilities": no standalone Piper binary works on macOS (the archived
  "aarch64" asset is actually x86_64); `piper.http_server`'s `--model` flag has no default.
- "External Binaries & CLI Utilities": Win32 `winsound.PlaySound(..., SND_ASYNC)` has a single
  global sound slot per process — a second overlapping async call silently replaces the first.
- "Testing & Provenance": a timed `thread.join(timeout=N)` returning tells you nothing about
  whether the thread actually finished — always assert `not thread.is_alive()` afterward when a
  test's claim depends on real completion, not just the join call returning.

Skipped as not NOTES.md-worthy (already documented elsewhere or too narrow): port-7800 choice
(operational detail, lives in the plan/CLAUDE.md); the live Mac verification of `PiperEngine`
(process note, not a generalizable finding); comment-pruning (routine cleanup).

## Verdict

**Mechanical gate: PASS.** Reviewer/Performance Reviewer/Security(deep)/Security(plan, retroactive)
all APPROVED. AA-6 stays `[~]` — Stage 4 below is outstanding and needs the user; this is a
deliberate deferral (root CLAUDE.md: "never block a merge on live acceptance the user cannot
currently perform"), not a gap in Stages 1-3's own completeness.

---

# Stage 4 Acceptance Checklist (live verification, needs the user)

**Goal:** confirm Piper-backed speech actually works end to end on both machines, that the outage
announcement is heard as designed, and that `--target aircraft-layer` still round-trips now that
the adapter can run co-located with the collector on Windows.

**Everything below was read from the committed scripts/code at tip `6e200483b714d00f86b607e8aa59af59a7a6491d`,
not reconstructed from the plan — command names and flags are quoted exactly as the files have
them. None of it has been run live (no Piper venv or Windows box reachable from this check) — every
command below is UNVERIFIED in the sense that it was not executed, only read; flag anything that
doesn't match on first attempt.**

## Prerequisites (both machines)

- [ ] A Piper venv, pinned to an interpreter `onnxruntime` ships wheels for — measured by the
  investigator: `python3.12` on Mac, Windows's only installed interpreter (`3.14`) on Windows.
  `pip install 'piper-tts[http]'` in that venv.
- [ ] The voice model `en_GB-northern_english_male-medium` downloaded into a voices directory on
  each machine (Piper's own `.onnx`/`.onnx.json` pair for that voice name).
- [ ] `petrobrain.env` (per machine, not committed — same file every other run script already
  sources) has these two variables set, read exactly as named by `run-piper-mac.sh`/
  `run-piper-windows.sh`:
  - `PIPER_VENV_PYTHON` — full path to that machine's Piper venv's `python`/`python.exe`
  - `PIPER_VOICES_DIR` — directory containing the downloaded voice model
- [ ] Mac: `mypy --strict audio-adapter/src` passes from inside `audio-adapter/` (sanity check that
  the checked-out tree is the one this report describes).

## Mac: Piper + `--target local`

1. Start Piper:
   ```sh
   cd run-scripts && ./run-piper-mac.sh
   ```
   (Reads `petrobrain.env`, runs `$PIPER_VENV_PYTHON -m piper.http_server --host 127.0.0.1 --port 7800 --model en_GB-northern_english_male-medium --data-dir $PIPER_VOICES_DIR`.)
   **Verify:** no immediate error; process stays up (Piper's own startup takes a few seconds).

2. Start the adapter with `--target local` explicitly — **`run-audio-adapter.sh` as committed
   hardcodes `--target aircraft-layer`**, so for this test run the module directly instead:
   ```sh
   cd audio-adapter && PYTHONPATH=src .venv/bin/python -m audio_adapter --target local
   ```
   **Verify:** startup log line `audio-adapter ready (target=local, speech-input=off)`.

3. Speak a line:
   ```sh
   curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Watching Charlie one seven.", "urgent": false}'
   ```
   **Verify:** `{"ok": true}` (or equivalent 200), and the new Piper voice is heard aloud through
   the Mac's speakers — not the old `say`-backed `Daniel` voice.

4. Run the live-gated test against this same Piper server:
   ```sh
   AUDIO_ADAPTER_PIPER_URL=http://127.0.0.1:7800 cd audio-adapter && .venv/bin/pytest tests/test_tts_engine.py -q
   ```
   **Verify:** the previously-skipped live test now runs and passes (0 skipped in that file's run,
   up from the usual 1).

## Windows: Piper + the new winsound sink

1. Start Piper:
   ```sh
   run-piper-windows.sh
   ```
   Same invocation shape as the Mac script, sourcing the Windows box's own `petrobrain.env`.

2. Start the adapter (new script, bare `python.exe`, no venv — `audio_adapter`'s own code has zero
   dependencies):
   ```sh
   run-audio-adapter-windows.sh --target local
   ```
   (`run-audio-adapter-windows.sh` is `pushd $PETROBRAIN_PATH/audio-adapter/src && python.exe -m audio_adapter --host 0.0.0.0 "$@"` — the `--target local` above is forwarded via `"$@"`.)
   **Verify:** same `audio-adapter ready (target=local, ...)` log line.

3. Speak a line (same `curl` as the Mac step, against this Windows box's own IP/port):
   **Verify:** audible playback through the new `_WinsoundLocalSink`, not a crash/no-op.

4. Interrupt mid-line:
   ```sh
   curl -X POST http://<windows-ip>:7795/stop
   ```
   **Verify:** `POST /stop` returns `200 {"ok": true}` and playback audibly cuts off (this exercises
   `winsound.PlaySound(None, SND_PURGE)` for real, which no unit test can — Reviewer's own "Two-OS
   test coverage gap" risk).

5. `--target aircraft-layer`, adapter and collector co-located on the same Windows box (a topology
   this project has not exercised before):
   ```sh
   run-audio-adapter-windows.sh --target aircraft-layer --aircraft-layer-url http://127.0.0.1:7791
   ```
   **Verify:** a `/speak` call round-trips through the collector's `POST /audio/play` and is heard,
   with no port collision or address confusion from both processes running on one machine.

## Either machine: outage announcement (Decision 3's amendment)

1. With the adapter running and Piper **not** running (or stopped mid-session), send `/speak`.
   **Verify:** adapter terminal logs exactly one loud line —
   `Piper unreachable at http://127.0.0.1:7800 -- Petrovich is silent until it is back (start run-piper-*.sh): <reason>`
   (exact wording from `tts_engine.py`'s `_report_failure` call site).
2. Send a second `/speak` immediately after, still with Piper down.
   **Verify:** no second `WARNING`-level line (only `DEBUG`, invisible at default log level) — the
   debounce is working, not spamming the terminal.
3. Start Piper, send a third `/speak`.
   **Verify:** one recovery line — `Piper back at http://127.0.0.1:7800 -- speech restored` — and
   the line is actually heard (not just logged).

## End-to-end `/speak` latency (both machines)

The plan's own open question (recon only measured the two halves — Piper's warm-request time and
the CLI-per-line cost — never the whole HTTP round trip through the adapter). Time from sending
`/speak` to audible playback start, on each machine, for a short line and a longer one. Report the
numbers back — this is what answers whether Piper is a net win over the old `say` path (`say` was
measured at ~0.6-0.8s) for the pilot, not a pass/fail check on its own.

## Pass Criteria

Stage 4 passes if: Piper-backed speech plays correctly on both machines under `--target local`;
the Windows sink's `/stop` interrupt and `--target aircraft-layer` co-located round-trip both work;
the outage-announcement sequence (one loud failure line, debounced repeats, one recovery line) is
heard exactly as designed; and the measured end-to-end latency is reported (no fixed numeric bar —
the plan deferred that judgment to this live measurement). No regression versus the old `say`-backed
path's basic behaviour (a line is heard, in a reasonable time, on request).
