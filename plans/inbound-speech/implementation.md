### Implementation Summary

Stage 1 only (`plans/inbound-speech/plan.md`) — the recognition bench, a stop/go gate before any
capture/transit/PTT/body-layer wiring is built. Built in `srs-adapter/`, branch
`feature/stt-recognition-bench`. Deliverable is a script that produces numbers and a judgement, not
a working pipeline — see plan Decision 4/settled decision 2 for why the report is built around
"would I fly with this?" rather than a single accuracy threshold.

**Not run for real.** The corpus is the user's own voice and does not exist yet; no `whisper-cli`
binary and no Windows box were available in this environment. Everything below was verified
structurally (tests, a synthetic-tone WAV fixture, a hand-run against an empty/fake corpus showing
clean degradation) but the actual accuracy numbers, confusion pairs, and go/no-go judgement are
still pending the user recording a corpus and running `tools/stt_bench.py` for real.

### Files Changed
- `srs-adapter/src/vocabulary.py` (new) — 15-token vocabulary (`TOKENS`), spoken phrasings
  (`PHRASES`, several per token), and helpers (`spoken_phrases`, `token_for_phrase`, `to_gbnf`). A
  deliberate hand-synced duplicate of `body-layer/src/belief/crew_console.py`'s
  `_RELATIVE_SCAN_TOKENS`/`_BEARING_SCAN_TOKENS` and `aircraft-layer`'s `ALLOWED_COMMANDS` —
  `srs-adapter` cannot import either (module independence rule).
- `srs-adapter/src/stt_engine.py` (new) — `STTEngine` protocol, `Transcript` dataclass,
  `STTRecognitionError`, `WhisperCliEngine`, `WindowsSpeechEngine`. Mirror image of `tts_engine.py`.
- `srs-adapter/tools/stt_bench.py` (new) — the bench: loads a `<corpus-dir>/<token>/*.wav` corpus,
  runs each available engine (whisper.cpp with/without `--grammar` as separate rows, Windows only
  attempted on Windows), scores top-1 token accuracy via a simple `difflib`-based match against
  `vocabulary.py`'s phrase table, and prints accuracy + confusion pairs with sample misheard text +
  confidence distribution split by correct/incorrect. `--list-prompts` prints what to record.
- `srs-adapter/tests/fixtures/sample.wav` (new) — a small stdlib-generated (`wave` module) 16kHz
  mono tone, used only to exercise the WhisperCliEngine test class's shape (not real speech; that
  class skips entirely without a real binary+model anyway).
- `srs-adapter/tests/test_stt_engine.py`, `srs-adapter/tests/test_vocabulary.py` (new).
- `srs-adapter/pyproject.toml` — added `stt_engine`, `vocabulary` to ruff's `known-first-party`.
- `srs-adapter/CLAUDE.md`, `srs-adapter/ROADMAP.md` — documented the new files/commands and Stage 1
  status (landed, not yet run for real; Stage 2 must not start before the bench is).

### Tests Added
- `test_vocabulary.py` — 15 tokens, no duplicate phrases across tokens, `spoken_phrases`/
  `token_for_phrase`/`to_gbnf` round-trip correctly.
- `test_stt_engine.py` — `WhisperCliEngine.is_available()` true/false paths; missing-model,
  empty-audio, and missing-binary raise `STTRecognitionError` with actionable messages;
  `WindowsSpeechEngine` rejects an empty phrase list, reports itself unavailable on this platform,
  and raises (not tracebacks) if `transcribe` is called off Windows. A `TestWhisperCliEngineReal`
  class exercises the real binary end to end but is `skipif`-gated on
  `SRS_ADAPTER_WHISPER_BINARY`/`SRS_ADAPTER_WHISPER_MODEL` env vars — skipped in this environment.

### Checks
(srs-adapter/ only)
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`src`, and `tools/stt_bench.py` individually — `tools/` isn't in the mandated
  command list per `CLAUDE.md`'s own precedent for `world-model/tools/`, checked anyway): pass
- pytest -q: pass (36 passed, 1 skipped — the real-whisper-binary class, correctly absent here)

### Notable Discoveries
- **Neither engine's CLI/JSON contract could be verified against a real binary.** No `whisper-cli`,
  no `ffmpeg`, no `sox`, and no Windows box exist in this environment. `WhisperCliEngine` assumes
  `-ojf`/`-of`/`--grammar`/`--grammar-penalty` flags and a `{"transcription": [{"text", "tokens":
  [{"p"}]}]}` JSON shape from whisper.cpp's public docs; `WindowsSpeechEngine`'s PowerShell script
  assumes `System.Speech.Recognition`'s documented .NET API shape. Both are flagged prominently in
  `stt_engine.py`'s module docstring as unverified — running the bench for real is exactly what
  validates or corrects them, which is consistent with Stage 1's own purpose but is a real gap the
  user should know about before trusting a confusing first result to mean "STT is bad" rather than
  "the flag name was wrong."
- **No recording helper script was written.** The task allowed either a helper or clear
  documentation; a helper would itself need `ffmpeg`/`sox` (another unverified external-binary
  dependency in an environment where neither exists), so `tools/stt_bench.py`'s docstring documents
  QuickTime+`afconvert` and `sox`'s `rec` instead.
- **The bench's own text-to-token matcher is deliberately simpler than Stage 2's future
  `belief/voice_commands.py`.** No verb anchor, no separation check, no confidence bands — a single
  `difflib.get_close_matches` pass against the flat phrase list, since the bench only needs to score
  "which token does this look like," not decide whether to act on it. Documented in
  `stt_bench.py`'s `_match_token` docstring so a future reader doesn't mistake it for Stage 2's real
  matcher or try to reuse it as one.
- Confirmed via `grep` that `body-layer/src/belief/crew_console.py`'s `_RELATIVE_SCAN_TOKENS`/
  `_BEARING_SCAN_TOKENS` and `aircraft-layer/src/collector/f10_command_receiver.py`'s
  `ALLOWED_COMMANDS` agree exactly on the 15 tokens and their names — `vocabulary.py` mirrors that
  confirmed set, not a guess.
