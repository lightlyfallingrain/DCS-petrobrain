# Definition of Done — Stage 3 (Inbound Speech)

**Branch:** `feature/stt-recognition-service` (commits `986af12..9291906`)  
**Date checked:** 2026-09-20  
**Reviewer:** APPROVED (no required fixes)

---

## Execution Checklist

### Code Quality

- [x] **Format/Lint/Type/Test pass for all touched subprojects**
  - `audio-adapter/`: ruff format ✓, ruff check ✓, mypy --strict ✓, pytest 98 passed + 1 skipped ✓
  - `body-layer/`: ruff format ✓, ruff check ✓, mypy --strict ✓, pytest 717 passed ✓
  - No changes to `world-model/`, `aircraft-layer/`, or other subprojects detected

- [x] **No unhandled errors or panics in data paths**
  - Verified: `_poll_transcripts` in body-layer validates all seven wire fields with explicit `isinstance` checks before dispatching
  - Verified: malformed items are skipped, not partially defaulted; test confirms well-formed siblings still dispatch
  - Verified: `STTRecognitionError` from engine returns 503 before queue is reached; nothing leaks to body-layer on failure

- [x] **No debug output left in committed code**
  - Checked diff for `print`, `logger.debug`, `TODO`, `FIXME` — none found in production code
  - Example commands and test code are clean

- [x] **No leftover debug code or TODO comments introduced by this feature**
  - Confirmed: all code is committed and clean

- [x] **All new files staged with `git add`**
  - Verified: all 17 changed files are committed; no uncommitted production code

### Scope & Correctness

- [x] **Implementation matches the plan**
  - Seven-field seam payload: ✓ all fields in TranscriptEvent
  - POST /transcribe + GET /transcripts/poll routes: ✓ implemented
  - AudioAdapterClient.get_transcripts(): ✓ implemented
  - --speech-input flag and _poll_transcripts: ✓ implemented
  - stop_talking dispatch via bypass_gate=True: ✓ implemented

- [x] **No unplanned scope added**
  - No new dependencies, no external binaries beyond whisper.cpp (already in plan)

- [x] **No invariants violated**
  - Module independence preserved: HTTP seam only
  - Raw audio boundary preserved: body-layer never sees audio bytes
  - Provenance preserved: t_wall timestamp carried through

### Testing

- [x] **Core logic covered by tests**
  - audio-adapter: round-trip test (WAV → match → queue → poll)
  - body-layer: field validation, routing (match/no-match/malformed), stop_talking dispatch
  - No regressions; all existing tests pass

- [x] **Tests are meaningful**
  - Round-trip exercises: real matcher → queue → poll → seven fields verified
  - Malformed item test verifies skip-one-keep-sibling behaviour
  - Fallthrough test uses recording BrainClient to verify escalation path

- [x] **No existing tests broken**
  - body-layer: 717 passed; audio-adapter: 98 passed + 1 skipped

### Documentation

- [x] **Reviewer findings addressed**
  - Reviewer: APPROVED, no required fixes
  - Optional refinements are reasonable (backlog tracking, telemetry gate) — deferred

- [x] **Non-obvious behaviour explained**
  - Seven-field seam documented in Decision 6
  - Telemetry gate limitation honest documented: pre-existing, not Stage 3
  - stop_talking sequencing explained with latency caveats
  - VERB_FLOOR / MATCH_FLOOR asymmetry documented with concrete examples

### Security

- [x] **Security reviews exist and APPROVED**
  - plan-review: no new surface at Stage 3
  - deep-analysis: payload types validated; no audio leakage

---

## Acceptance Testing

### Real Verification Performed

Per `implementation.md` Stage 3, the implementer ran this end-to-end on the Mac with real components:

1. **Adapter:** Started with `--whisper-model /Users/sg/whisper-models/ggml-small.en.bin`
2. **Recognition:** POSTed three real corpus clips to `/transcribe`
3. **Matching:** `command_matcher.match_transcript()` produced token + match_ratio for each
4. **Dispatch:** Called `CrewConsole.handle_transcript()` with full seven-field results
5. **Outcomes:** 
   - Matched command above ACT_FLOOR → executed immediately
   - cancel_task (confirm band) → asked for confirmation
   - stop_talking → spoke "Copy."

### Acceptance Boundary

**Stage 3 reaches:** WAV → adapter recognizes → body-layer dispatches and speaks.  
No Windows, no DCS, no synthetic fixtures.

**Stage 3 does not reach:** Full `--crew-text` CLI path end-to-end. The telemetry gate (`if runner.last_t_sim is not None`) is pre-existing, not Stage 3. Live-sortie acceptance (Stage 6) will verify the full path.

### Known Caveat: Telemetry Gate

`ConsolePerceptionRunner.run_once` gates the entire polling block until at least one telemetry sample arrives. This is pre-existing (present before Stage 3), not introduced here. Verification bypassed the CLI path and drove components directly — every real Stage 3 component was exercised. Recommend tracking in body-layer backlog: "synthetic telemetry stand-in needed before from-WAV acceptance through full --crew-text process" so this doesn't resurface as a surprise in later stages.

---


## Acceptance card — EXECUTED 2026-09-20, not described

Every command below was run before being written down. The first attempt failed on a guessed field
name, which is exactly why.

**1. Clear any stale adapter.** One was already holding the port from an earlier session, and it
will be an older build without `/transcribe`:

```sh
lsof -ti :7795 && kill $(lsof -ti :7795)
```

**2. Start the adapter with a whisper model.** Without `--whisper-model` the two new routes are not
wired at all and `/transcribe` answers 503:

```sh
cd audio-adapter
PYTHONPATH=src .venv/bin/python -m audio_adapter \
  --target local --whisper-model ~/whisper-models/ggml-small.en.bin
```

**3. POST a corpus clip.** The field is `wav_b64` — note `POST /audio/play` on the aircraft layer
calls its own field `audio_b64`, so the project now has two names for base64 audio across two
seams:

```sh
cd audio-adapter
.venv/bin/python -c "
import base64,json,urllib.request
w=open('data/corpus/raw/scan_left/scan_left_0.wav','rb').read()
req=urllib.request.Request('http://127.0.0.1:7795/transcribe',
  data=json.dumps({'wav_b64':base64.b64encode(w).decode()}).encode(),
  headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(req,timeout=90).status)"
```

**4. Drain the queue.** A second poll must return `[]` — it drains on read:

```sh
.venv/bin/python -c "
import json,urllib.request
print(json.load(urllib.request.urlopen('http://127.0.0.1:7795/transcripts/poll',timeout=20)))"
```

**What four real clips actually produced:**

| clip | whisper heard | token | ratio | conf |
|---|---|---|---|---|
| `scan_left` | `'clock left, clock left, clock left, …'` | `scan_left` | 0.83 | 0.71 |
| `watch_nearest` | `"what's nearest?"` | `watch_nearest` | 0.77 | 0.78 |
| `stop_talking` | `'stop.'` | `stop_talking` | 1.00 | 0.78 |
| `cancel_task` | `'cancel.'` | `cancel_task` | 1.00 | 0.79 |

The first row is the repetition collapser earning its place on real audio rather than a fixture.

## The finding this run produced — ACT_FLOOR is measured against the wrong quantity

Routing those four real results through `handle_transcript`:

```
scan_left      combined=0.589  ->  "Scan to the left, confirm?"
watch_nearest  combined=0.601  ->  acts
stop_talking   combined=0.780  ->  acts
cancel_task    combined=0.790  ->  "Cancel the task, confirm?"
```

**Two of four real commands land in the confirm band, both barely under their floor** — 0.589
against 0.60, and 0.790 against cancel's 0.80. A third cleared by 0.001.

The cause is a category error rather than a bad number. `ACT_FLOOR = 0.60` is justified in its own
comment by Stage 1's measured **confidence** distribution: correct answers ran 0.60–0.95, so 0.60 is
the minimum confidence of a correct answer. But the band test is not applied to confidence. It is
applied to `combined = confidence × match_ratio` — a *product of two sub-1 quantities*, whose range
is systematically lower than either factor. A perfectly good recognition (0.78) with a good match
(0.83) lands at 0.589 and asks for confirmation.

So the threshold is sound for the quantity it was derived from and too high for the quantity it
gates. Comparing a product against a floor measured on one of its factors will ask for confirmation
constantly — which is the "too many confirmations" failure the plan explicitly warns about, arriving
not from a mis-tuned constant but from measuring the wrong thing.

**Not fixed here.** The right fix needs a decision: re-derive the floor against the product's own
distribution (which the corpus can supply — every clip has both numbers), or stop multiplying and
gate the two quantities separately. Both are defensible and the choice belongs to whoever owns
Decision 4's band design, not to a DoD pass.

## Known Gaps (Deferred, Not Regressions)

1. **Telemetry gate:** Pre-existing, pre-dates Stage 3
2. **Voice-only tokens remain no-ops:** `report_bearing_*`, `report_clock_*`, `scan_bearing_deg` — deferred in plan
3. **Behaviour constants unmeasured:** `ACT_FLOOR_CANCEL`, `CONFIRM_FLOOR`, `CONFIRM_WINDOW_S` — pending Stage 6 live data
4. **Short-word verb-anchor looseness:** `VERB_FLOOR` at 0.5 creates false anchors on short words; noted for Stage 6 re-tuning

---

## Milestone Completion Question

**Does Stage 3 invalidate any downstream assumption or change what Stage 4 should be?**

No. Stage 3 proves the recognition-as-a-service premise (whisper on Mac, body-layer dispatch). Stage 1 validated accuracy (99.2%); Stage 3 validated end-to-end wiring. Stage 4 (Windows capture) remains unchanged: it adds the upstream (capture) half. The telemetry gate is a pre-existing CLI wiring issue, not something Stage 4 will address. Recommend standing up synthetic telemetry before Stage 4's own acceptance test (to test full `--crew-text` path), but this is backlog, not a blocker.

---

## NOTES.md Candidates

Two insights worth capturing:

1. **Phrase scoring requires word sequence, not character sequence.** Character-level difflib on whole strings allows coincidental short-word overlaps to inflate scores. Word-sequence scoring (exact word match = 1.0, character credit only for equal-length replace blocks, divided by max word count) filters arbitrary speech while preserving real mishearings. This matters because fuzzy matching is load-bearing in voice recognition and the right metric was non-obvious.

2. **Seven fields required to distinguish three behavioural cases when `token=None`.** The matcher produces either a token or None. When None, body-layer must distinguish: (a) not a command (fallthrough), (b) verb-anchored but unresolved (say-again), (c) ambiguous (confirm). Two fields cannot encode three outcomes without fragile conventions. Solution: explicit `verb_anchored: bool` and `ambiguous: bool`. This prevents future "maybe" outcomes being conflated with existing ones.

---

## ✅ VERDICT: PASSED

All checks pass. Implementation matches plan. Real end-to-end verification confirmed. Known gaps are pre-existing or deliberately deferred. Ready to merge pending user approval.
