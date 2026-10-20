# BL-B86 — `join_voice_latency.py` crashes whole on one malformed JSONL line

- [ ] **BL-B86 — `tools/join_voice_latency.py`'s `_iter_jsonl` has no handling for a malformed or
  truncated JSONL line; one bad line aborts the entire reducer with an unhandled traceback.**
  Security deep analysis, `plans/voice-latency-instrumentation/security-review.md` (2026-10-20),
  confirmed by running it (not inferred): a two-line file with one valid row and one truncated
  (`json.loads` incomplete) row raises `json.decoder.JSONDecodeError` straight out of `main()`, with
  no rows from *any* file processed — not just the bad line skipped.

  No test in this diff exercises this path (`grep -n "def test_" body-layer/tests/
  test_join_voice_latency.py` has six tests, none feeding a malformed line).

  **Why this matters more than an ordinary parse-error would**: the realistic trigger is a process
  killed mid-write — a DCS crash, a mission reload, a Windows box power-cycling — which is exactly
  the scenario `BL-15`'s mission-restart handling and this project's own per-mission log-rolling
  exist to cope with, and exactly the moment a pilot/developer reaches for this reducer to find out
  what happened. The tool most likely to be run right after a crash is the one a crash can disable
  entirely.

  **Not blocking**: no security impact (no injection, no data corruption beyond the log file
  itself, `json.loads` is not an unsafe deserializer) — a robustness gap, not an exploitable one,
  and the underlying `--latency-log`/`--speech-log`/`--belief-truth-log` writers already guard
  against write failures on their own side (disable-after-first-failure). But it is the opposite
  of "low probability" — crashes mid-sortie are a known, recurring event this project already
  designs around elsewhere.

  **Recommended fix**: wrap `json.loads(line)` per line in `_iter_jsonl` with a
  `try`/`except json.JSONDecodeError`, log/print a one-line warning naming the file and line number,
  skip that line, and continue — the same "one bad item must not cost the whole batch" posture this
  project already applies to capture clips (`capture_loop.CaptureEvent`) and queued audio lines
  (`AudioPlaybackSender._run`'s per-item try/except).
