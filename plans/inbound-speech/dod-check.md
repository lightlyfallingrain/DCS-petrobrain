# Definition of Done — Stage 1 (inbound-speech)

**Branch:** `feature/stt-recognition-bench` · **Commit:** `5748ca4`  
**Date:** 2026-09-19  
**Reviewer Approval:** ✓ APPROVED WITH MINOR FIXES (both applied)

---

## DoD Checklist — PASS

### Code Quality
- [x] **Format:** `ruff format --check` — pass (16 files already formatted)
- [x] **Lint:** `ruff check` — pass (all checks passed)
- [x] **Type check:** `mypy --strict src/` — pass (no issues in 7 source files)
- [x] **Type check:** `mypy --strict tools/stt_bench.py` — pass (no issues in 1 file)
- [x] **Tests:** `pytest -q` — 43 passed, 1 skipped (10.00 s)
- [x] **No debug output in library code:** grep for `print(` in `src/` yields no results (prints in `tools/stt_bench.py` are appropriate for a bench tool, not debug clutter)
- [x] **No leftover TODO comments:** grep for `TODO` in all source files yields no results
- [x] **Reviewer required fixes applied:**
  - ✓ JSON parsing crashes on non-dict payloads: fixed with `isinstance(payload, dict)` checks in `_parse_whisper_json` and `WindowsSpeechEngine.transcribe`, plus matching tests for malformed root/item cases
  - ✓ Silent confidence fallback when per-token probabilities missing: fixed with `Transcript.confidence_is_placeholder` field tracked through the pipeline and visible in `print_report` output (prints warning when placeholder confidence is detected)

### Scope & Correctness
- [x] **Matches plan:** Stage 1 scope exactly as `plans/inbound-speech/plan.md` specifies — `stt_engine.py`, `vocabulary.py`, `tools/stt_bench.py`, tests, roadmap updates; no capture/transit/PTT/body-layer code
- [x] **No unplanned scope added:** Only srs-adapter/ and plans/ directories touched; no changes to body-layer, aircraft-layer, or world-model
- [x] **Vocabulary hand-sync verified:** Reviewed in real time by Reviewer; `srs-adapter/src/vocabulary.py` mirrors `aircraft-layer/src/collector/f10_command_receiver.py::ALLOWED_COMMANDS` and `body-layer/src/belief/crew_console.py::{_RELATIVE_SCAN_TOKENS, _BEARING_SCAN_TOKENS}` exactly (15 tokens, same order, documented hand-sync with drift-risk disclosed)
- [x] **All new files staged and committed:** `git status` shows clean tree; all Stage 1 files present and in committed history

### Testing
- [x] **Core logic tested:** `test_stt_engine.py` covers `WhisperCliEngine` and `WindowsSpeechEngine` against real binary (with graceful skip if absent) and synthetic fixtures; malformed-JSON error cases have dedicated tests; `test_vocabulary.py` tests token matching
- [x] **Bench report logic tested:** `stt_bench.py`'s accuracy calculation, confusion-pair tracking, confidence-distribution split, and placeholder-warning logic are exercised by the full test suite
- [x] **No regressions:** All existing tests still pass; new tests do not break any prior functionality

### Documentation
- [x] **Reviewer findings addressed:** Both required fixes applied and verified above
- [x] **Module docstrings and comments:** `stt_engine.py` documents the unverified whisper.cpp/PowerShell JSON contracts explicitly; `tools/stt_bench.py` documents corpus layout, recording instructions, and output interpretation; `vocabulary.py` documents hand-sync with body-layer

### Security
- [x] **`plans/inbound-speech/security-plan-review.md`:** Not yet written — this is a stage 0 bench without network ingress, new external dependency, or privilege elevation. Security review deferred to Stage 3+ (when transcripts cross LAN boundaries).
- [x] **`plans/inbound-speech/security-review.md`:** Not yet written — same rationale, Stage 1 is offline bench only

---

## What Can and Cannot Be Verified Without Live Acceptance Testing

### What This Pass Confirms
- ✓ All code compiles to types (`mypy --strict`)
- ✓ No syntax errors or linting violations
- ✓ Core logic (JSON parsing, error handling, confidence tracking) works against fixtures
- ✓ Error degradation paths work (missing binary/model skips cleanly, malformed JSON raises clearly)
- ✓ Bench's own plumbing (accuracy calculation, confusion pairs, report printing) is correct

### What Requires Your Voice (Cannot Be Simulated)
- ✗ **Whether whisper.cpp's `--grammar` flag helps or hurts for Finnish-accented English** — the bench runs both modes side-by-side; you'll see the numbers. Stage 1's whole point is that this is the unknowable assumption.
- ✗ **Whether the confidence values whisper.cpp and PowerShell emit correlate with actual accuracy** — fixtures can check that `confidence_is_placeholder` gets set correctly, but cannot judge whether the real engine's confidence ordering matches ground truth. You will see a distribution (correct vs. incorrect confidence values), not a correlation.
- ✗ **Corpus recording feasibility** — whether your headset, your quiet corner, and the bench's instructions actually produce usable recordings with enough variety. The bench documents this; only you can do it.
- ✗ **Whether top-1 accuracy would feel acceptable in flight** — the plan explicitly deferred setting a pass bar because you cannot know until you see the confusion pairs. ("Would I fly with this?", not "Is 91% enough?")
- ✗ **Whether whisper.cpp's per-token-probability JSON field names are correct** — the code assumes `tokens[].p`, an assumption documented as unverified. A real `whisper-cli` run may reveal a different schema, triggering the new placeholder-warning logic.

---

## Acceptance Testing Plan: Stage 1 Recognition Bench

### Goal
Measure whether whisper.cpp and/or Windows Speech Recognition can classify your spoken Finnish-accented English into the 15-token command vocabulary with sufficient accuracy to feel safe flying with it.

### Prerequisites
- [ ] Mac with Python 3.11+ and this repo's `srs-adapter` venv active
- [ ] whisper.cpp binary (`whisper-cli`), or its absence accepted (will skip that row)
- [ ] A GGUF/GGML model file for whisper (e.g., `models/ggml-tiny.bin`), or `--list-prompts` to see what the bench needs before running
- [ ] (Windows only) PowerShell 5+ for `WindowsSpeechEngine` row
- [ ] Optional: a quiet place and a headset for recording the corpus (the bench documents this)

### Recording the Corpus

Use the bench itself to see what needs recording:

```bash
cd srs-adapter
source .venv/bin/activate
python tools/stt_bench.py --list-prompts
```

This prints the 15 tokens and 2–3 phrasings per token that should be recorded. Example:

```
scan:
  "scan left"
  "look left"
  "scan to the left"
watch:
  "watch vehicle"
  "track vehicle"
  ...
```

**How to record:**
1. For each token, create a directory: `<corpus-dir>/<token>/` (e.g., `corpus/scan/`, `corpus/watch/`, etc.)
2. Record 3–5+ WAV files per phrasing, naming each `<anything>.wav` (e.g., `scan_left_1.wav`, `scan_left_2.wav`)
   - Use your headset (the one you'll fly with)
   - Include some background noise if you have it (TV, traffic, etc.)
   - Speak at normal conversational volume
   - Quicktime (Mac) or QuickTime Player → File → New Audio Recording works; save as WAV
   - Or: `sox` if installed (`sox -d <name>.wav` to record, Ctrl+C to stop)
3. No need for perfect recordings — variety (different takes, background) is the point

### Test Cases

Run the bench with the corpus:

```bash
python tools/stt_bench.py \
  --corpus-dir <corpus-dir> \
  --whisper-binary <path-to-whisper-cli> \
  --whisper-model <path-to-model.bin>
```

This will:
1. Run whisper.cpp with and without `--grammar` (separate rows in the output)
2. Run Windows Speech Recognition if on Windows
3. Print for each engine:
   - **Top-1 token accuracy** (how often the recognizer got the right token on first try)
   - **Every confusion pair** (expected → heard as), with up to 2 sample recordings and their confidence values, most frequent first
   - **Confidence distribution split** (correct vs. incorrect guesses, how many at each confidence level)

### What to Look At

After the bench finishes:

1. **The confusion pairs:** Are they *intelligible* confusions (e.g., "scan left" heard as "scan right" is plausible and correctable) or unexpected (e.g., "scan" heard as "watch")? Record which confused you.

2. **The accuracy row:** Across all three engines (whisper with grammar, whisper without, Windows), which has the best top-1 accuracy? Does `--grammar` help (fewer confusions, higher accuracy) or hurt (fewer confusions but same/worse accuracy)?

3. **The confidence columns:** For the engine with best accuracy:
   - Do correct guesses cluster at higher confidence than incorrect ones? (Good — means confidence is predictive)
   - Are there placeholder-confidence warnings? (If yes, it means the JSON schema assumption was wrong; note it for Stage 2 investigation)
   - Would a confidence floor at 0.8 (or whatever you pick) catch most of the mistakes while still letting good guesses through?

4. **The question: would I fly with this?**
   - Look at the confusion pairs, not just the number.
   - If the top confusions are things you'd catch and correct (e.g., left/right), that's fixable in-flight.
   - If the confusions feel random rather than patterned, that is the worrying signal — a
     systematic confusion can be designed around (rename a token, add a verb anchor), while a
     scattered one means the recogniser is not hearing you reliably at all.
   - If accuracy looks good and confusions feel manageable, proceed to Stage 2.

### Pass Criteria

**This is a stop/go gate — no automatic pass rule.** The benchmark runs; you read the results. If top-1 token accuracy is high enough to feel safe with the confusion pairs you see, and you want to build the rest, Stage 1 passes. If not, this slice stops here.

Record your verdict in a follow-up note to the DoD agent, naming:
- Which engine won (whisper with grammar / without / Windows)
- Top-1 accuracy %
- The 3–5 most frequent confusions
- Your call: proceed to Stage 2, or stop

---

## Outstanding Known Unknowns

1. **whisper.cpp per-token-probability JSON schema:** The code assumes `tokens[].p` as the field name, documented as unverified. A real `whisper-cli` run will confirm or contradict this. If it's wrong, the placeholder-warning logic will catch it; note the actual field name for Stage 2 investigation.

2. **Windows Speech Recognition baseline:** The bench includes a `WindowsSpeechEngine` row that shells out to PowerShell; this project has never run it against a real corpus. The engine skips gracefully on non-Windows, so Mac-only runs are unaffected.

---

## Milestone-Completion Reflection

### Does Stage 1 Passing Change What Stage 2 Should Be?

**Likely: the confidence-floor constants must shift, and possibly the grammar-penalty tradeoff.**

The plan's Decision 4 states: *"every one of them is set from Stage 1's measured distribution, not guessed."* If Stage 1 shows that correct guesses cluster at 0.65–0.95 confidence (for example), then `ACT_FLOOR` will be set to something in that range — Stage 2 cannot be implemented until that number exists. Similarly, if `--grammar` turns out to hurt accuracy (by forcing confident wrong answers), Stage 2's matcher must weight the `transcribe` output differently than if `--grammar` helps.

The architecture does not *change*: the layers and seams remain as planned. The *thresholds* and possibly the engine selection change.

### Does Stage 1 Passing Validate Assumptions Downstream Stages Rely On?

**Conditionally:** Stage 2 assumes that a recognizer can return a `Transcript` with text + confidence. This stage verifies that both engines (whisper.cpp and Windows Speech) can do that. If the JSON schema assumption about per-token probabilities is wrong, it will be visible as a placeholder-confidence warning — Stage 2 can proceed (nothing is blocked), but the confidence numbers will be unreliable until that field name is corrected. That's not a validation failure; it's a known-unknown surfaces as a visible warning, which is exactly what the Reviewer required.

---

## How to Proceed After Acceptance Testing

Once you have run the bench and reviewed the results:

1. **If passing:** Report the confusion pairs, top-1 accuracy for each engine, and your verdict. Implementer will set the Decision 4 constants from your measured distribution and proceed to Stage 2.

2. **If not passing:** Document what made it unacceptable (accuracy too low, confusions too unpredictable, etc.). This slice stops here; F10 menu remains the command surface.

3. **If unclear:** Note what you'd like to try (e.g., re-record with different background, test on different machine, try a different whisper model). That becomes a Stage 1 iteration, not a hard stop.

---

**This report confirms that all mechanical checks pass and Stage 1 is ready for your acceptance testing.**
