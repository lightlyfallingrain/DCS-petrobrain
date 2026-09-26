### Implementation Summary

Two fixes from the 2026-09-26 whole-subproject reviews of `audio-adapter`
(`audio-adapter/docs/reviews/perf-review-audio-adapter.md` finding 1,
`audio-adapter/docs/reviews/security-audit-audio-adapter.md` RECOMMENDED
#2). No plan.md — user pre-approved both fixes directly, spec was the two
review reports.

### Files Changed
- `audio-adapter/src/audio_adapter/capture.py` — `--poll-hz` now defaults to
  `None` on the parser and is resolved after parsing by `_resolve_poll_hz(ptt,
  poll_hz)`: `ptt_source.DEFAULT_DCS_POLL_HZ` (30 Hz) for `--ptt dcs`, the
  renamed `DEFAULT_LOCAL_POLL_HZ` (60 Hz, was the undifferentiated
  `DEFAULT_POLL_HZ`) for `key`/`joystick`. An explicit `--poll-hz` always
  wins for every source. `--help` text now states the source-dependent
  default explicitly rather than requiring a code read.
- `audio-adapter/src/server.py` — added `SpeakRequestHandler._read_body()`,
  one shared helper both `_handle_speak` and `_handle_transcribe` now call
  instead of each doing its own bare `int(self.headers.get("Content-Length",
  "0") or "0")`. Guards non-numeric (`ValueError`) and negative values,
  answering `400` before ever calling `self.rfile.read()` — a negative
  length previously reached `rfile.read(n)` with a negative `n`, which reads
  until EOF rather than a bounded amount and can block a handler thread
  indefinitely. No max-body-size cap added (explicitly out of scope per the
  task — that is RECOMMENDED #1, the twin of aircraft-layer's already-
  accepted `POST /audio/play` gap, deferred to be handled together with it).

### Tests Added
- `audio-adapter/tests/test_capture_cli.py` (new file — no existing test
  covered `capture.py`'s CLI parsing) — `_resolve_poll_hz` for each `--ptt`
  value's default (`dcs` -> 30 Hz, `key`/`joystick` -> 60 Hz), an explicit
  `--poll-hz` overriding both, and that the parser's own default is `None`
  (guards against reintroducing the bug via per-source parser mutation
  instead of post-parse resolution).
- `audio-adapter/tests/test_server.py` — `/speak` with a hand-set
  `Content-Length` header via a new `_post_raw_content_length` helper
  (`http.client.HTTPConnection`, since `urllib.request.Request` always
  computes a correct header from `data` and so can't reach this guard):
  missing, non-numeric, negative -> `400`, and a correct explicit length ->
  `200` with synthesis/delivery still happening.
- `audio-adapter/tests/test_transcribe_api.py` — the same three guard cases
  plus a valid-length success case for `/transcribe`, using
  `running_server_with_stt` (a real `stt_engine` configured) rather than
  `test_server.py`'s plain `running_server` fixture, since `/transcribe`
  answers `503` before ever reaching the header guard when no `STTEngine` is
  configured.

### Checks
(audio-adapter/)
- ruff format --check: pass (one file needed `ruff format` after the edit;
  reformatted and reverified clean)
- ruff check: pass
- mypy --strict (`mypy src`): pass, no issues in 15 source files
- pytest -q: pass — 212 passed, 1 skipped (the pre-existing
  `AUDIO_ADAPTER_WHISPER_BINARY`-gated real-whisper-cli test class)

No `.venv` existed in this worktree checkout (gitignored); created one ad
hoc with `python3 -m venv .venv && pip install ruff mypy pytest` to run the
above — same situation `project_worldmodel_no_dep_tooling` memory records
for `world-model`.

### Notable Discoveries
- The worktree's own branch (`worktree-agent-...`) started two commits
  behind `main` — missing exactly the two review commits this task's spec
  depends on. Fast-forward merged `main` into it before starting (no
  destructive reset needed, since the worktree branch had no commits of its
  own yet).
- `/transcribe`'s existing plain `running_server` fixture in `test_server.py`
  has no `stt_engine` configured, so any `/transcribe` Content-Length test
  written against it would exercise the `stt_engine is None -> 503` early
  return, never the header guard. The `/transcribe`-side guard tests
  therefore belong in `test_transcribe_api.py`'s `running_server_with_stt`
  fixture instead, not `test_server.py` (which owns `/speak`'s equivalent
  tests) — this is exactly the kind of test-inventory mismatch the process
  says to check for, and it also naturally dictated *where* new tests should
  live given the plan's "extend existing files" instruction.
