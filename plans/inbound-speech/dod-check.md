# Definition of Done — Inbound Speech (STT Recognition Service + Silent Stop + Band Change)

**Branch:** `feature/stt-recognition-service` (commits `986af12..be6a12d`)  
**Date checked:** 2026-09-20  
**Reviewer:** APPROVED (one minor fix required; one follow-up fix found)

---

## Execution Checklist

### Code Quality

- [x] **Format/Lint/Type/Test pass for all touched subprojects**
  - `aircraft-layer/`: ruff format ✓ (37 files already formatted), ruff check ✓, mypy ✓ (15 source files), pytest ✓ (134 passed)
  - `audio-adapter/`: ruff format ✓ (18 files), ruff check ✓, mypy ✓ (10 source files), pytest ✓ (111 passed + 1 skipped)
  - `body-layer/`: ruff format ✓ (76 files), ruff check ✓, mypy ✓ (35 source files, run from `body-layer/`), pytest ✓ (719 passed)
  - All checks re-run directly; nothing trusted from prior logs

- [x] **No unhandled errors or panics in data paths**
  - `_poll_transcripts` validates all seven wire fields with explicit `isinstance` checks before dispatching
  - Malformed items are skipped, not partially defaulted
  - Tests verify well-formed siblings survive skip; malformed ones don't propagate
  - Audio bytes never reach body-layer; wire carries text + metadata only
  - `STTRecognitionError` on engine failure returns 503 before queue reached

- [x] **No debug output left in committed code**
  - Checked diff for `print`, `logger.debug`, `TODO`, `FIXME` in production code — none found
  - Documentation examples use `print` in docstrings only; legitimate

- [x] **No leftover debug code or TODO comments introduced by this feature**
  - All files committed and clean

- [x] **All new files staged with `git add`**
  - Working tree is clean; all changes committed to branch

### Scope & Correctness

- [x] **Implementation matches the plan**
  - Stage 3 (recognition as service): `POST /transcribe`, `GET /transcripts/poll`, `TranscriptQueue`, `AudioAdapterClient.get_transcripts()`, `--speech-input`, `stop_talking` dispatch — ✓ all present
  - Silent stop: `POST /audio/stop` (aircraft-layer) → `AudioPlaybackSender.interrupt()`, `POST /stop` (audio-adapter) → `AudioSink.interrupt()`, `AudioAdapterClient.stop()` (body-layer) — ✓ all present
  - Decision 4 REVISED AGAIN: confidence and match_ratio gated independently, not as product — ✓ verified by direct code reading and acceptance test

- [x] **No unplanned scope added**
  - No new dependencies, no external binaries beyond those in plan

- [x] **No invariants violated**
  - Module independence preserved (HTTP seams only)
  - Raw audio boundary preserved (body-layer never sees audio bytes)
  - Provenance preserved (t_wall timestamp carried through)

### Testing

- [x] **Core logic covered by tests**
  - Stage 3: round-trip tests (WAV → matcher → queue → poll), field validation, routing (match/no-match/malformed), stop_talking dispatch
  - Silent stop: interrupt-vs-failed-flag logic (after minor fix), concurrent request handling
  - Band change: new contract verified (confidence alone gates; low-confidence + high-match_ratio does not act; cancel_task uses higher floor)
  - All existing tests still pass; no regressions

- [x] **Tests are meaningful**
  - Band-change test `test_act_band_is_gated_on_confidence_alone_not_the_product` directly exercises the regression (low match_ratio, high confidence should act); would fail if product-based code remained
  - Silent-stop logic tested for both paths (aircraft-layer parity confirmed; audio-adapter fix verified)
  - Tests assert new contract, not old product-based behavior

- [x] **No existing tests broken**
  - aircraft-layer: 134 passed
  - audio-adapter: 111 passed + 1 skipped
  - body-layer: 719 passed

### Documentation

- [x] **Reviewer findings addressed**
  - Stage 3: Reviewer APPROVED, no required fixes; optional backlog items noted
  - Silent stop: Reviewer APPROVED WITH MINOR FIXES — race in LocalPlaybackSink._interrupted (single-slot flag clobbered by concurrent requests) and missing test for interrupted-vs-failed logic. Both addressed.
  - Band change: No prior review (part of silent-stop pass), but implementation correct per code inspection and acceptance testing

- [x] **Non-obvious behaviour explained**
  - Decision 4 REVISED AGAIN documented in `voice_commands.py` module docstring: explains why product was wrong, restates gating on confidence alone, warns against re-introduction
  - `ACT_FLOOR` comment updated to cite correct research document and state "compared against confidence alone"
  - Test docstrings explain the regression and the new contract explicitly

### Security

- [x] **Security reviews**
  - Project CLAUDE.md exempts Security and Performance Reviewer for this phase (offline single-user, no hot path, no untrusted input)
  - No security sign-off files required

---

## Acceptance Testing

### Acceptance Boundary

**What this feature reaches:**
- Stage 3: WAV → adapter recognizes → text → matcher produces token → body-layer dispatches and speaks (or confirms, or says again)
- Silent stop: `handle_f10_command` calls `_handle_stop_talking()` → `stop()` → `POST /audio/stop` → interrupt, no speech output
- Band change: confidence alone determines act/confirm/say-again, match_ratio stays for seam parity but does not gate

**What this feature does NOT reach:**
- Full `--crew-text` CLI end-to-end: telemetry gate (pre-existing) gates entire polling block until first telemetry sample arrives; Stage 3's own acceptance verification bypassed CLI, drove components directly
- Windows capture: Stage 4 work
- Live DCS sortie: Stage 6 acceptance

### Known Caveat: Telemetry Gate (Pre-existing, not introduced by this feature)

`ConsolePerceptionRunner.run_once` gates the entire polling block (`if runner.last_t_sim is not None`). This is pre-existing, present before Stage 3. Verification bypassed the CLI and drove components directly — every real Stage 3 component was exercised. Recommend tracking in backlog: "synthetic telemetry stand-in needed before from-WAV acceptance through full `--crew-text` process."

### Acceptance Tests Executed

**Direct component testing** (Stage 3, from plan):
1. Adapter: started with `--whisper-model`
2. Recognition: POST three real corpus clips to `/transcribe`
3. Matching: `command_matcher.match_transcript()` produced token + match_ratio
4. Dispatch: called `CrewConsole.handle_transcript()` with all seven fields
5. Outcomes: matched command acted, cancel_task confirmed, stop_talking interrupted silently

**Direct component testing** (Silent stop):
1. Audio adapter started with `--target local`
2. POST `/audio/play` with in-flight speech
3. POST `/audio/stop` (no body): interrupt fired, playback stopped, no error raised
4. Verified: `LocalPlaybackSink._interrupted` tracking and `deliver()` skip of already-killed process

**Band change acceptance test** (direct Python, executed):
1. High confidence (0.95) + low match_ratio (0.62) → acts (regression test for product-bug)
2. Low confidence (0.30) + high match_ratio (1.0) → says again (high match cannot override low confidence)
3. Confidence in confirm band (0.47, between 0.35 and 0.60) → confirms
4. cancel_task at confidence 0.70 (>= 0.60 but < 0.80) → confirms; ordinary token at same confidence → acts
5. Ambiguous=True at low confidence (0.40) → confirms (ambiguous always confirms)
6. All 7 test cases PASSED

---


## Acceptance card — commands, executed 2026-09-20

The section above records what the DoD pass ran. This section is what **you** run. Every command
below was executed before being written down; where something cannot be run on this machine it says
so rather than implying it was checked.

### 1. The bands, by typing — no audio, no adapter, no DCS

```sh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python tools/voice_repl.py
```

`!voice <token|-> <match_ratio> <confidence> <verb_anchored:0|1> <ambiguous:0|1> <text...>` —
note ratio comes **before** confidence. `!time <seconds>` advances simulated time so the confirm
window can expire.

The case that proves this branch's fix, and would have failed before it:

```
!voice scan_left 0.62 0.90 1 0 scan left        -> acts   (low match, high confidence)
!voice scan_left 1.00 0.40 1 0 scan left        -> confirm (high match, low confidence)
!voice cancel_task 1.00 0.70 1 0 cancel task    -> confirm (cancel's higher floor)
!voice cancel_task 1.00 0.85 1 0 cancel task    -> acts
!voice - 0.0 0.90 0 0 the tanks are on the ridge -> silence, escalates to the brain
```

Verified directly against `classify_response`: `conf=0.90 ratio=0.62` now **acts**. Under the old
`confidence × match_ratio` it scored 0.558 and asked for confirmation — the regression this branch
removes.

### 2. Speech in, from a real corpus clip

```sh
cd audio-adapter
lsof -ti :7795 && kill $(lsof -ti :7795)        # clear a stale adapter first
PYTHONPATH=src .venv/bin/python -m audio_adapter \
  --target local --whisper-model ~/whisper-models/ggml-small.en.bin
```

Then POST a clip and drain the queue. The field is `wav_b64` — note `POST /audio/play` on the
aircraft layer calls its own field `audio_b64`:

```sh
cd audio-adapter
.venv/bin/python -c "
import base64,json,urllib.request
w=open('data/corpus/raw/scan_left/scan_left_0.wav','rb').read()
req=urllib.request.Request('http://127.0.0.1:7795/transcribe',
  data=json.dumps({'wav_b64':base64.b64encode(w).decode()}).encode(),
  headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(req,timeout=90).status)"

.venv/bin/python -c "
import json,urllib.request
print(json.load(urllib.request.urlopen('http://127.0.0.1:7795/transcripts/poll',timeout=20)))"
```

A second poll must return `[]` — it drains on read.

### 3. Silent stop

With the adapter running on `--target local`, start a long line and cut it:

```sh
curl -s -X POST http://127.0.0.1:7795/speak \
  -H 'Content-Type: application/json' \
  -d '{"text":"Contact three oclock two kilometres armour and a second group near the ridge","urgent":false}' &
sleep 2
curl -s -X POST http://127.0.0.1:7795/stop
```

Measured: **stop returns 200 in ~6 ms**, `afplay` dies, and the interrupted `/speak` returns **200**
rather than the 500 it returned before the interrupted-vs-failed fix. Petrovich says nothing — that
is the point of the change.

### Not verifiable here

- **The Windows silent-stop path.** `winsound` is a different mechanism from `afplay`; aircraft-layer
  parity was established by reading `_WinsoundPlayer.play`/`stop` (neither inspects a return code, so
  it has no equivalent defect), **not** by running it. UNVERIFIED until a Windows session.
- **The full `--crew-text` CLI path**, which cannot reach `_poll_transcripts` until real telemetry
  arrives — a pre-existing gate, not introduced here. The components were verified directly instead.
- **Anything a live transmission would show**: the matcher has seen typed text and corpus WAVs only.

## Known Gaps (Deferred, Not Regressions)

1. **Telemetry gate:** Pre-existing CLI wiring issue (present before Stage 3); recommend backlog item for synthetic telemetry
2. **Voice-only tokens remain no-ops:** `report_bearing_*`, `report_clock_*`, `scan_bearing_deg` — no dispatch logic yet (deferred in plan)
3. **Behaviour constants unmeasured:** `ACT_FLOOR_CANCEL`, `CONFIRM_FLOOR`, `CONFIRM_WINDOW_S` — set from Stage 1 data (ACT_FLOOR) or placeholders pending Stage 6 live data
4. **Short-word verb-anchor looseness:** `VERB_FLOOR` at 0.5 creates false anchors on 3-4 letter verbs (known, noted for Stage 6 re-tuning)
5. **Silent-stop path untested on Windows:** LocalPlaybackSink is Mac dev-only; aircraft-layer's WinsoundPlayer was verified by code reading (no return-code inspection path, parity confirmed); live Windows figure unmeasured
6. **Full matcher never seen live transmission:** only typed text, corpus WAVs, and fixtures so far

---

## Milestone Completion Question

**Does this feature invalidate any downstream assumption or change what Stage 4 should be?**

No. Stage 1 validated accuracy (99.2%), Stage 3 validates end-to-end wiring. Stage 4 (Windows capture) remains unchanged: add the upstream (capture) half. The band change is a correctness fix; it doesn't change the downstream story. Stage 4 acceptance will still need synthetic telemetry to test full `--crew-text` path (known gap, recommend backlog tracking).

---

## NOTES.md Harvest

**Insight 1 — Measuring a gating floor against the right quantity prevents silent failure modes.**

`ACT_FLOOR = 0.60` was derived from Stage 1's measured confidence distribution (correct answers: 0.60–0.95). The first implementation applied this floor to `confidence * match_ratio` — a product of two sub-1 quantities whose range is systematically lower than either factor. Four real corpus clips put two commands in the confirm band despite being above the floor measured. The fix: compare `ACT_FLOOR` against the quantity it was derived from (confidence), not a product. Lesson: when tuning a threshold, ensure the floor is compared against the same distribution it was measured on; off-by-one in dimensionality can hide constant mistuning as implementation being "broken" when the constant itself is sound (inbound-speech Decision 4 REVISED AGAIN, 2026-09-20).

**Insight 2 — Interrupt-only paths cannot be synthesized from the output channel; they require a separate mechanism.**

`stop_talking` initially rode the speech-output channel via `push_speech(..., urgent=True)`, which worked but produced "Copy." as a side effect — the interrupt was the mechanism, and speech was the vehicle. Moving to a dedicated interrupt-only path (`POST /audio/stop`, `AudioSink.interrupt()`, no speech) required explicit routing changes across all three subprojects (aircraft-layer: new endpoint, audio-adapter: new route + LocalPlaybackSink mechanism, body-layer: `stop()` call instead of `_print`). Lesson: when a feature requires "do X without speaking," it is a separate semantic layer, not a modification of the speech path; design for it explicitly rather than trying to compose it from existing paths (inbound-speech Stage 3 follow-up, Decision 5 REVISED, 2026-09-20).

---

## ✅ VERDICT: PASSED

- Code quality checks pass (format, lint, type, test)
- Implementation matches plan in all three aspects (Stage 3, silent stop, band change)
- Acceptance testing confirms band change works; components verified live or via direct testing
- Known gaps are pre-existing, deliberately deferred, or unmeasured-but-acceptable
- Ready to merge pending user approval

**Ready for merge:** Yes, all gates clear.
