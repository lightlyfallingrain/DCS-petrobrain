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

---

### Round 2: Reviewer required fix (`64e9d37`, negative-Content-Length test gap)

The Reviewer (re-review of `639a94c`) found that
`test_speak_negative_content_length_returns_400` and
`test_transcribe_negative_content_length_returns_400` pass against the
pre-fix `server.py` (`2802c4f`) too, so they proved nothing about the hang
they claim to guard against. Root cause: the pre-fix code already guarded
the *read* with `self.rfile.read(length) if length > 0 else b""` — a
negative `length` takes the `else b""` branch, so `rfile.read()` is never
called with a negative count either before or after the fix. The
distinguishing behaviour between pre-fix and post-fix is not whether
`rfile.read` gets called with a bad argument (it never does, in either
version, for the negative case) — it's *which* rejection path produces the
`400`: pre-fix falls through to the JSON-validation path
(`"body must be valid JSON"`, because `json.loads("")` fails on the empty
body), post-fix rejects at the header guard itself
(`"invalid Content-Length: '-1'"`). The Reviewer's own suggested mechanism
(mock/spy `rfile.read` and assert it's never called with a negative count)
would not have actually distinguished the two versions for this specific
case, since neither version ever makes that call — asserting on the
specific rejection-path error message is what makes the test fail against
`2802c4f` and pass against the fix, and this was the actual fix applied
(after checking the mock approach against the real pre-fix code first: see
"Notable Discoveries" below).

#### Files Changed (round 2)
- `audio-adapter/src/server.py` — `_read_body()`: collapsed the two
  identical-shaped `400` branches (non-numeric `ValueError`, negative
  `length`) into one. Non-numeric now sets `length = -1` in the `except`
  clause and falls into the same `if length < 0` rejection as a literal
  negative value, same message, same status. Optional refinement from the
  review, applied since it read cleaner with no lost distinction (the two
  branches always produced the identical message anyway).
- `audio-adapter/tests/test_server.py` —
  `test_speak_negative_content_length_returns_400` now asserts the full
  response body equals `{"error": "invalid Content-Length: '-1'"}` instead
  of only checking `status == 400` and `"error" in resp_body`. Docstring
  added explaining why the status-only assertion didn't catch anything and
  citing the empirical pre-fix run.
- `audio-adapter/tests/test_transcribe_api.py` — same change to
  `test_transcribe_negative_content_length_returns_400`.
- `audio-adapter/docs/reviews/security-audit-audio-adapter.md` — corrected
  finding 2 in place (not deleted): annotated that the negative-`Content-
  Length` hang mechanism it originally described does not occur on this
  code path, quoted the original claim verbatim, explained the actual
  pre-fix behaviour (`else b""` branch, then `json.loads("")` fails), and
  noted the correction came from the Reviewer's empirical check. Also
  annotated the downstream cross-reference in the "Focus-area findings"
  section (the "only per-request wedge risk" line) since it repeated the
  same now-corrected claim.

#### Tests Added / Changed (round 2)
- No new test files. Two existing tests strengthened (see above) — user
  instruction was explicit that these should be *strengthened*, not
  supplemented with new ones, and doing so keeps one canonical negative-
  length test per endpoint rather than two overlapping ones.

#### Verification (round 2, empirical)
Per the task's explicit instruction, verified the strengthened tests
against the real pre-fix code, not by reasoning alone:
1. Copied `git show 2802c4f:audio-adapter/src/server.py` to a scratch file
   outside the repo tree (this worktree's scratchpad), backed up the
   current (fixed) `src/server.py`, swapped the pre-fix version in.
2. Ran both strengthened tests: **both failed**, with the exact predicted
   mismatch (`{'error': 'body must be valid JSON'}` vs the expected
   `{'error': "invalid Content-Length: '-1'"}`).
3. Restored the fixed `src/server.py` (`git diff` after restore showed only
   the intended collapsed-branch change vs. the pre-round-2 committed
   version) and re-ran the same two tests: both passed.

#### Checks (round 2)
(audio-adapter/)
- ruff format --check: pass (29 files already formatted)
- ruff check: pass
- mypy --strict (`mypy src`): pass, no issues in 15 source files
- pytest -q: pass — 212 passed, 1 skipped (same counts as round 1, no
  regression)

No `.venv` existed in this worktree checkout either (a fresh worktree, per
`AGENTS.md`'s isolation rules) — recreated ad hoc the same way as round 1.

#### Notable Discoveries (round 2)
- The Reviewer's own suggested fix mechanism (spy on `rfile.read`, assert
  never called with a negative/unbounded count) does not actually
  distinguish pre-fix from post-fix for the *negative*-length case
  specifically, because the pre-fix code's `length > 0` ternary already
  prevents that call in both versions — confirmed by reading `2802c4f`'s
  literal source before writing the test, not assumed from the review's
  prose. Asserting on the response body's exact error message is what
  actually distinguishes the two `400`s that already existed on both
  sides of the fix. Worth remembering for any future "harden this
  regression test" task: the reviewer's suggested mechanism is a good
  starting hypothesis, not a substitute for checking what the two code
  paths actually do differently before writing the assertion.
- The worktree's own branch had not yet been fast-forwarded to
  `fix/audio-adapter-review-findings` (`64e9d37`) at task start — same
  situation round 1's "Notable Discoveries" recorded, `git merge --ff-only`
  applied again before starting.
