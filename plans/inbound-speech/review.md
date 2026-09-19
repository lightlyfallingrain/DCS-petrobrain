### Review Summary

Stage 1 of `plans/inbound-speech/plan.md` (`feature/stt-recognition-bench`, 4 commits, all under
`srs-adapter/`). Scope matches the plan exactly: `stt_engine.py`, `vocabulary.py`,
`tools/stt_bench.py`, tests, and doc/roadmap bookkeeping — no capture/transit/PTT/body-layer code,
as the plan requires for a stop/go gate stage. Re-ran `srs-adapter`'s full check sequence myself
(not trusted from the implementation log): `ruff format --check` pass, `ruff check` pass,
`mypy --strict` on `src` and on `tools/stt_bench.py` individually both pass, `pytest -q` →
36 passed, 1 skipped — matches the reported numbers exactly.

**1. Module independence / vocabulary duplication — verified correct.** Grepped
`aircraft-layer/src/collector/f10_command_receiver.py`'s `ALLOWED_COMMANDS` and
`body-layer/src/belief/crew_console.py`'s `_RELATIVE_SCAN_TOKENS`/`_BEARING_SCAN_TOKENS` tables
directly. All 15 token names and their order agree exactly with `vocabulary.py`'s `TOKENS`. The
module docstring and `srs-adapter/CLAUDE.md` both state plainly that this is a hand-synced
duplicate with no automated cross-check — the drift risk is disclosed, not buried.

**2. The unverified external CLI contract — real gap found (see Required Fixes).** The failure
posture is mostly right: a non-zero exit, a missing binary, a missing/unparsable JSON file, or a
missing `"transcription"` key all raise `STTRecognitionError` with an actionable message quoting
the binary's own stderr or naming the bad shape — none of those degrade silently into "the
recognizer just did badly." But two sub-cases fail the review's actual test (see below): a JSON
root that isn't a dict (either engine) crashes with a raw, uncaught `AttributeError` instead of an
`STTRecognitionError`, and a missing per-token-probability field degrades **silently** (debug-level
log only, invisible by default) rather than being visible in the printed report.

**3. Degradation — correct.** `WindowsSpeechEngine.is_available()` is a pure platform check (no
subprocess), `transcribe` raises immediately and clearly off Windows, and `stt_bench.py` skips that
row with a printed message rather than attempting it. Verified by test and by reading
`run_engine`'s skip path.

**4. Report format vs. "would I fly with this?" — satisfies the plan's requirement.**
`print_report` prints top-1 accuracy, every confusion pair (`expected -> heard as`) with actual
misheard sample text and per-sample confidence, and a correct/incorrect confidence-distribution
split — exactly what settled decision 2 asked for, not a bare percentage. This is undermined in
one respect by the confidence-placeholder issue below: if `WhisperCliEngine`'s per-token
probability field name is wrong, the confidence half of that report would be silently meaningless
without any hint. That's the same underlying defect as item 2, not a separate one.

### Required Fixes

- **Non-dict (or malformed-item) whisper.cpp/PowerShell JSON crashes with an uncaught
  `AttributeError` instead of `STTRecognitionError`.** Reproduced directly:
  `_parse_whisper_json(["oops"])` and `_parse_whisper_json({"transcription": ["scan left"]})` both
  raise a bare `AttributeError: 'list'/'str' object has no attribute 'get'` in
  `srs-adapter/src/stt_engine.py`. The same shape exists in `WindowsSpeechEngine.transcribe`'s
  `payload.get("text", ...)"`/`payload.get("confidence", ...)` calls (`stt_engine.py`, the
  `WindowsSpeechEngine` class) — a non-dict JSON root from PowerShell hits the same bug before the
  `isinstance` guard that already exists a few lines later ever runs. This is precisely the failure
  mode flagged as the review's central risk: if a flag name or JSON key assumption turns out wrong
  in a way that changes the root shape (not just a missing key), the user gets a traceback that
  looks like a crash, not "the model was wrong" or "the binary rejected this flag" — exactly the
  outcome that could be misread as an accent problem. Fix: validate `isinstance(payload, dict)`
  (and, for whisper, that each segment/token is a dict) before calling `.get()`, raising
  `STTRecognitionError` with the actual payload repr on failure, matching the existing "unexpected
  … JSON shape" pattern already used for the missing-`transcription`-key case. Add unit tests for
  both engines' malformed-root and malformed-item cases — `_parse_whisper_json` is a module-level
  function and the PowerShell JSON parsing is inline but equally testable without a real binary or
  a Windows host, so there's no reason this coverage needs live hardware.

- **A whisper.cpp per-token-probability schema mismatch degrades silently.** In
  `_parse_whisper_json`, when no `token_probs` are found the function falls back to a placeholder
  confidence of `1.0` and only records this via `logger.debug(...)` — invisible by default, since
  neither `stt_engine.py` nor `tools/stt_bench.py` configures logging. If the real `"tokens"`/`"p"`
  field names differ from what was assumed (entirely plausible, per the module's own
  "unverified" disclaimer), every whisper.cpp result in the bench would silently report
  `confidence=1.00`, and the report's confidence-distribution section (`correct` vs `incorrect`,
  both pinned at 1.00) would look like a real, if uninteresting, number rather than a broken
  assumption — undermining Decision 4's explicit requirement that every confidence-band constant be
  "set from Stage 1's measured distribution, not guessed." Not raising is the right call (a missing
  confidence figure shouldn't crash the bench), but it must be visible in the printed report, not
  just a debug log line. Fix: have `run_engine`/`print_report` (or `ClipResult`) track and surface
  when placeholder confidence was used — e.g. a count/warning line in `print_report`'s output
  ("N/M whisper.cpp results used a placeholder confidence — per-token probabilities were not found
  in the JSON output; treat the confidence columns above as unreliable until this is checked") —
  so the user isn't handed a plausible-looking but meaningless confidence column without warning.

### Optional Refinements

- `srs-adapter/tests/test_stt_engine.py`'s `TestWhisperCliEngineReal` class only asserts
  `Transcript` shape/bounds on a synthetic tone WAV — once the user has a real binary, it would be
  worth a follow-up test asserting `_parse_whisper_json` against a captured real JSON sample (fixed
  as a committed fixture), so a future whisper.cpp version bump that changes the output shape is
  caught by CI rather than only by the next live bench run. Not blocking for Stage 1.
- `stt_bench.py`'s `_MATCH_CUTOFF = 0.6` and the bench's own `difflib`-based matcher are explicitly
  simpler than Stage 2's future matcher, and this is well-documented — no action needed, just noting
  it was checked and is intentional, not an oversight.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — read both new `src/` modules in full, `tools/stt_bench.py` in full, both new test
files, `srs-adapter/CLAUDE.md`/`ROADMAP.md`/`pyproject.toml` diffs, and
`plans/inbound-speech/implementation.md`. Re-ran the full `srs-adapter` check sequence directly
rather than trusting the reported numbers, and reproduced the two Required Fixes with direct
function calls against the actual code rather than inferring them from reading alone.
