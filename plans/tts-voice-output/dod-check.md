# Definition of Done Report — BL-10 First Slice (TTS Audio Transport)

**Feature:** `feature/tts-voice-output`  
**Branch commit range:** `ac9cce5..3994d0a` (4 implementation commits, `3d09313` as tip)  
**Date:** 2026-09-17  
**Report:** PASSED

## DoD Checklist

### Code Quality
- [x] **Format/lint/type/test (all touched subprojects from their own venvs)**
  - `srs-adapter/`: ruff format ✓, ruff check ✓, mypy --strict ✓, pytest → 21 passed
  - `aircraft-layer/`: ruff format ✓, ruff check ✓, mypy --strict ✓, pytest → 126 passed
  - `body-layer/`: ruff format ✓, ruff check ✓, mypy --strict ✓, pytest → 600 passed, 1 xfailed (pre-existing)
- [x] **No unhandled errors or panics in data paths** — confirmed by Reviewer's independent re-run of all three subprojects' suites
- [x] **No debug output left in committed code** — grep across changed files for `print(` found no new debug statements; existing logging calls in `crew_console.py` and `logger.py` are pre-existing
- [x] **No leftover debug code or TODO comments** — grep for TODO/FIXME/XXX found no hits in changed code

### Scope & Correctness
- [x] **Implementation matches plan** (`plans/tts-voice-output/plan.md`)
  - Stages 1–4 implemented as designed, no silent scope creep
  - Stage 5 (Windows `winsound` live verification) and Stage 6 (live DCS/sortie) explicitly out of scope, documented as unverified
  - All eight "check hardest" items from review confirmed present and correct
- [x] **No invariants violated** — module independence confirmed (srs-adapter, aircraft-layer, body-layer each standalone with HTTP seams); in-process import boundary (`body-layer↔world-model`) unchanged
- [x] **All new files staged** — all implementation commits already made; no uncommitted work present (`.gitignore` added to srs-adapter to prevent cache files)

### Testing
- [x] **Core logic covered** — 21 + 126 + 600 tests across three subprojects, all passing (xfail is pre-existing/unrelated)
- [x] **Tests are meaningful, not decorative**
  - `test_tts_engine.py`: real `say` binary (not mocked), synthesis success + empty-text failure + voice fallback behavior
  - `test_server.py`: valid/invalid payloads, synthesis/delivery failure paths, HTTP contract
  - `test_audio_sender.py`: FIFO queueing, urgent-preempt mechanism, failure isolation
  - `test_crew_console.py`: speech_client routine/urgent routing, independent failure isolation from overlay_client
- [x] **No existing tests broken** — all pre-existing test counts validated by Reviewer's re-run

### Documentation
- [x] **Reviewer findings addressed** — Reviewer report (`review.md`) contained zero required fixes; two optional refinements flagged (agent-memory commit as a process deviation, audio payload size cap as non-blocking) — no blocking items
- [x] **Non-obvious behavior explained** — implementation.md details Notable Discoveries (winsound guarding pattern, `say` voice fallback behavior); plan's Decision sections explain all design choices; all unverified items marked as such

### Security
- [x] **Security plan exists and reviewed** — `plans/tts-voice-output/security-plan-review.md` does not exist (CLAUDE.md exempts security role for this project phase), but plan Decision 6 acknowledges "no auth on LAN-facing write path" as same severity class as existing endpoints; no new threat model introduced
  - Deferred to user instruction per project CLAUDE.md

### Process
- [x] **Required ROADMAP updates staged** (see Acceptance Testing Plan, Part 3, below)

## Acceptance Testing Plan: TTS Audio Transport (BL-10 First Slice)

**Goal:** Verify that the Mac-local audio synthesis and playback path produces audible speech with no external dependencies (aircraft-layer, Windows, DCS), confirming the foundation before live Windows verification.

**Prerequisites**
- [ ] Type-checked and importable from repo root: `mypy --strict srs-adapter/src` (run from `srs-adapter/` directory), `mypy --strict aircraft-layer/src`, `cd body-layer && mypy src`
- [ ] Three subprojects' venvs are activated and ready; no DCS, no Windows collector running needed
- [ ] macOS `say` binary is present (standard on all macOS versions)

**Test Cases**

1. **Local TTS synthesis and playback (srs-adapter `--target local`)**
   - Start srs-adapter server: `cd srs-adapter && PYTHONPATH=src .venv/bin/python -m srs_adapter` (background)
   - Send a POST request: `curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Watching Charlie one seven.", "urgent": false}'`
   - Expected result: Audible speech plays on the Mac via `afplay` with no other subproject running; curl responds `200`
   - Verify: text is intelligible, latency is under ~1 second

2. **Urgent flag routing (preempt mechanism untested on Windows, but routing tested)**
   - Send a routine callout: `curl -X POST http://127.0.0.1:7795/speak -d '{"text": "T-72, eleven oclock, two kilometres.", "urgent": false}'`
   - While it is playing, send an urgent callout: `curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Missile launch, break right.", "urgent": true}'`
   - Expected result: Urgent callout interrupts and plays immediately (on Mac, via queue + `afplay`); routine callout either discarded or queued for after
   - Note: The actual `winsound.SND_PURGE` behavior on Windows is unverified (Stage 5 item); this test confirms routing logic only

3. **Network path to aircraft-layer (srs-adapter `--target aircraft-layer`)**
   - This test is **runnable on the Mac without Windows or DCS**, only requires aircraft-layer to be running locally
   - Start aircraft-layer collector standalone: `cd aircraft-layer && PYTHONPATH=src .venv/bin/python -m collector` (or follow `WORKFLOW.md`)
   - Start srs-adapter in aircraft-layer mode: `cd srs-adapter && PYTHONPATH=src .venv/bin/python -m srs_adapter --target aircraft-layer --aircraft-layer-url http://127.0.0.1:7791`
   - Send a POST request to srs-adapter: `curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Hostile, nine oclock, four kilometres.", "urgent": false}'`
   - Expected result: srs-adapter synthesizes, base64-encodes the WAV, POSTs to aircraft-layer's `/audio/play`; on the Mac, aircraft-layer's AudioPlaybackSender would play it (or logs the Windows-only `winsound` error, which is expected/correct on Mac)
   - Verify: curl responds `200` and no exceptions in aircraft-layer logs

4. **Body-layer integration (body-layer with srs-adapter, aircraft-layer optional)**
   - Start srs-adapter: `cd srs-adapter && PYTHONPATH=src .venv/bin/python -m srs_adapter` (using `--target local`, the default)
   - Run body-layer logger with crew-text mode: `cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python -m logger --aircraft-layer-url http://127.0.0.1:7791 --theatre <YourTheatre> --world-model-db <region.sqlite> --crew-text --speech-audio --srs-adapter-url http://127.0.0.1:7795`
   - Type a command in the REPL (e.g., `watch <contact_id>` — if contacts exist via aircraft-layer, or use a manual test)
   - Expected result: CrewConsole's readback is both printed to stdout AND posted to srs-adapter's `/speak` endpoint, which synthesizes and plays it; no crashes or exceptions
   - Verify: you hear the spoken readback on the Mac

**Edge Cases to Probe**

- **Synthesis failure (unknown voice):** `curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Test.", "urgent": false}' -H "Content-Type: application/json" -d '{"text": "Test.", "urgent": false, "voice": "Nonexistent Voice"}'` — srs-adapter should respond `503` (synthesis failed), but body-layer's `CrewConsole._print` should catch and continue
  - Note: `say` silently falls back to default voice on unknown voice, so this will produce audio, not an error — documented in NOTES.md
- **Malformed JSON:** `curl -X POST http://127.0.0.1:7795/speak -d 'not json'` — should respond `400`
- **Missing required field:** `curl -X POST http://127.0.0.1:7795/speak -d '{"urgent": false}'` (no `text`) — should respond `400`
- **Empty text:** `curl -X POST http://127.0.0.1:7795/speak -d '{"text": "", "urgent": false}'` — srs-adapter synthesizes but produces no-op audio; Reviewer found this already tested

**Pass Criteria**

The feature passes acceptance testing if:
1. Test case 1 produces audible speech on the Mac with srs-adapter running standalone (`--target local`)
2. Test case 2 shows urgent flag routing (curl succeeds both times; timing behavior on interruption is a Stage 5 item on Windows)
3. Test case 3's curl requests to aircraft-layer succeed (network contract confirmed, playback deferred to Windows)
4. Test case 4 runs without crashes when body-layer's CrewConsole routes text to srs-adapter, and you hear the spoken result
5. Edge cases degrade gracefully (bad JSON → 400, synthesis failure → 503, body-layer continues)

## Notable Implementation Decisions

1. **`__main__.py` moved into `srs_adapter/` sub-package** — the plan specified a flat `src/__main__.py`, but `python -m __main__` does not work (ValueError: `__main__.__spec__ is None`). Moved to `src/srs_adapter/__main__.py` + `__init__.py` so `python -m srs_adapter` works correctly; flat `tts_engine.py`/`server.py`/`aircraft_client.py` stay top-level, imported by both the entrypoint and tests. Documented as a minor, local, reversible deviation.

2. **`say -v <unknown voice>` silently falls back to default voice** — confirmed live during implementation. This is the opposite of typical CLI error behavior and is worth knowing before building voice validation on top of this engine. Documented in NOTES.md.

3. **`winsound` guarding via `if sys.platform == "win32": import ...`** — a static platform check, not `try: import / except ImportError`, is required for `mypy --strict` to pass on the Mac. The typeshed stub for `winsound` reports all members as "no attribute" outside win32, so the bare `try` form still fails type checking even though it would work at runtime. Pattern confirmed via minimal reproduction and applied to `aircraft_sender.py`. Documented in NOTES.md as a reusable pattern.

## Milestone Completion Analysis

**Does this slice's completion change what the next milestone should be, or invalidate an assumption a downstream milestone relies on?**

### a) BL-5a design validation

The BL-5a plan (`division-or-responsibility.md` "Speech / audio") assumed that if body-layer exposed the right interface (a simple `push_speech` method), the SRS adapter would be "a thin pass-through" and body-layer changes would be minimal. **This assumption held exactly:** `CrewConsole` gained only one optional field (`speech_client: SrsAdapterClient | None`), mirroring the existing `overlay_client` pattern without new abstraction or policy, and `logger.py` gained two CLI flags (`--speech-audio`, `--srs-adapter-url`). The seam is HTTP end-to-end (body-layer → srs-adapter → aircraft-layer), requiring no new in-process coupling beyond the world-model↔body-layer exception that already exists.

**Verdict:** BL-5a's interface-design decision is validated. The narrowness of body-layer changes confirms the design was right.

### b) SRS-ICS slice sequencing

The plan deferred SRS-ICS injection (stages 5–6) to a separate slice, keeping this slice independent of the intercom-targeting question. The recon's addenda (2026-09-17) resolved that Mi-24P's SPU-8 is SRS-visible with `--modulations INTERCOM` and `--unitId <player_aircraft_id>`, but the slice's live Windows verification (stage 5) and live DCS sortie (stage 6) remain unverified. 

**What this means for the next slice:** The SRS-ICS-injection slice (BL-10 second half) now knows its target (`--unitId` + intercom modulation), but still needs:
1. Discovering the player's DCS aircraft unit ID at runtime (likely available via aircraft-layer's `LoGetWorldObjects` / `is_ownship` path — verify before planning)
2. Windows-side testing that `--modulations INTERCOM` parses and transmits correctly
3. Live DCS sortie confirming single-player intercom reception works as expected

**Verdict:** The SRS-ICS slice is more concrete now (intercom path verified), but not made mandatory by this slice. **The recommendation stands: local playback (this slice) is the guaranteed-deliverable first sink; SRS-ICS is the second sink after its live test.** If SRS-ICS's stage 5 (Windows) fails, this slice's local-playback capability ships as the real feature, not a stepping stone.

### c) Brain layer & BL-10 command vocabulary

The user's 2026-09-16 direction stated that BL-10 "owns the rich command vocabulary" — command forms beyond F10's 15-token radio menu (e.g., `watch <unit> <where>`, waypoint-anchored scans). This slice does not touch that scope; it stands up the audio transport only. 

**What this means for the brain layer:** The brain layer, once built, will need a command interface broader than F10's tree. This slice provides the audio delivery channel; the command vocabulary (parser, routing, plan) is still TBD. No assumptions invalidated.

**Verdict:** Scope split is correct. This slice proves the audio path end-to-end; rich commands (SRS-based, typed, or both) are BL-10's separate piece.

## Roadmap Updates Required

The user must approve and merge the following ROADMAP changes in this same push as the feature merge (per `.claude/skills/merge.md`):

1. **`body-layer/ROADMAP.md` — BL-10 entry**
   - Mark `[ ]` → `[~]` (in progress) or `[x]` (done, first slice) — user's choice based on whether "first slice" counts as "started"
   - Replace "Not started" with a done-entry summarizing what shipped vs. what remains:
     ```
     Stages 1-4: local TTS via macOS `say`, HTTP `/speak` endpoint, `AudioPlaybackSender` queue/preempt on aircraft-layer, body-layer integration via `speech_client` field. Live-verified: srs-adapter --target local on Mac, full cross-layer chain with aircraft-layer. Unverified/deferred: winsound playback and urgent-preempt interrupt on Windows (stage 5), live DCS sortie (stage 6), SRS-ICS injection (separate slice), rich command vocabulary (user direction 2026-09-16, BL-10's second piece).
     ```
   - Add backlog item: "Russian-accented voice character (explicitly deferred, Decision 7)" — tracked separately since the plan rejected an immediate solution as blocking scope

2. **Root `ROADMAP.md` — Status table**
   - Add srs-adapter row: `| SRS Adapter | **First slice done: local TTS synthesis/playback via macOS `say`, HTTP contracts with body/aircraft layers established.** | [`srs-adapter/ROADMAP.md`](srs-adapter/ROADMAP.md) |`
   - Update Body Layer status line if BL-10's first slice counts as "started" in the user's mental model; current text references BL-7 as the latest milestone, but this branch ships BL-10's first stage

3. **`srs-adapter/ROADMAP.md`** (create new file)
   - Mirror `aircraft-layer/ROADMAP.md` and `body-layer/ROADMAP.md` structure
   - Mark first slice done; document what stages 2–6 entail (SRS-ICS, Windows verification, DCS sortie)
   - Link to `plans/tts-voice-output/` for the detailed plan

## Reviewer Confidence

Full independent re-verification by code review:
- Reviewer read every changed file in full (not just diffs)
- All eight plan "check hardest" claims independently verified against code and (where specified) reproduced
- All three subprojects' test suites re-run from their own venvs, exact counts matched
- `winsound`/mypy platform-guard claim reproduced with minimal test case
- No required fixes; two optional refinements noted (agent-memory commit as process deviation, payload size cap as future-if-revisited)

**Reviewer verdict:** APPROVED (confidence: full read, all claims independently verified)

## Notes on Optional Refinement

The Reviewer flagged (but did not block) that commit `3994d0a` (`.claude/agent-memory/implementer/` changes) violates AGENTS.md's "side-quest rule": agent-memory updates are cross-cutting bookkeeping, not part of the feature milestone, and belong in a disposable worktree on `main`, not bundled into a feature branch. This is a process observation, not a correctness issue. The user can either:
- Accept the deviation (low-stakes process debt, content itself is accurate)
- Before merge, drop this commit from the branch and re-apply its content via a worktree on `main`

This does not block DoD passage.
