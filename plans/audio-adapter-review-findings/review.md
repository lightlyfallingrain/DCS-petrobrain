### Review Summary

Re-review of `fix/audio-adapter-review-findings` (639a94c, diffed against 2802c4f; HEAD 77953e3
adds only an implementer-memory note, no code). This is a fix written against two whole-subproject
review reports (`audio-adapter/docs/reviews/perf-review-audio-adapter.md` finding 1,
`security-audit-audio-adapter.md` RECOMMENDED #2) — per AGENTS.md, reviewed the same as any other
new code.

Both fixes do what they were asked to do, cleanly, with no scope creep:

1. **`--poll-hz` per-source default** (`capture.py`) — parser default moved to `None`,
   `_resolve_poll_hz(ptt, poll_hz)` resolves `DEFAULT_DCS_POLL_HZ` (30 Hz) for `dcs` /
   `DEFAULT_LOCAL_POLL_HZ` (60 Hz, renamed from the old undifferentiated `DEFAULT_POLL_HZ`) for
   `key`/`joystick`, explicit `--poll-hz` always wins. `--help` text states the source-dependent
   default. Grepped the whole subproject for other readers of `args.poll_hz`/`DEFAULT_POLL_HZ` —
   `capture.py`'s own `main()` is the only call site; `tools/probe_joystick.py` has its own
   unrelated `--poll-hz` flag, untouched and correctly out of scope.
2. **`_read_body()` Content-Length guard** (`server.py`) — one shared helper now fronts both
   `_handle_speak` and `_handle_transcribe`, rejecting missing/non-numeric/negative
   `Content-Length` with a clean `400` (matching the module's existing `{"error": ...}` shape)
   before `rfile.read()` is ever called. Verified the ordering claim in `implementation.md`: in
   `_handle_transcribe`, the `stt_engine is None -> 503` check still precedes the call to
   `_read_body()` (`server.py` current: the `if stt_engine is None` block, then `raw_body =
   self._read_body()`) — the 503-before-guard behavior is unchanged, and the reasoning for putting
   those tests in `test_transcribe_api.py` rather than `test_server.py` holds.

No body-size cap was added — correctly left out, matching the task's explicit exclusion (RECOMMENDED
#1, the twin of the accepted aircraft-layer gap). No files were touched outside the two named fixes
and their tests plus `implementation.md`/agent-memory.

**One required fix**, found by doing exactly what the task asked — empirically disabling the fix and
re-running the new tests against it (see `feedback_regression_test_empirical_check` in reviewer
memory, applied again here): the negative-`Content-Length` tests in both `test_server.py` and
`test_transcribe_api.py` pass against the pre-fix code too, for a reason that has nothing to do with
the hang they claim to guard against.

### Required Fixes

- **`test_speak_negative_content_length_returns_400` (`test_server.py`) and
  `test_transcribe_negative_content_length_returns_400` (`test_transcribe_api.py`) pass against the
  pre-fix code and so prove nothing about the hang the security review flagged.** Reverted
  `server.py` to 2802c4f and ran these tests against it directly: 3 of the 4 new `test_server.py`
  Content-Length tests passed unmodified (missing, negative, and valid-length-succeeds — only the
  non-numeric case failed, with the raw `ValueError` traceback the security review described).
  The reason: the pre-fix code already guarded the *read* with `self.rfile.read(length) if length
  > 0 else b""` — a negative `length` takes the `else b""` branch, never reaches `rfile.read()`
  with a negative count, and the resulting empty body fails `json.loads("")` on its own, landing on
  `400` through the pre-existing JSON-validation path. The security audit's stated mechanism
  ("`self.rfile.read(length)` with a negative `n`... blocks a handler thread indefinitely") does
  not occur on this code path in the pre-fix code — the `length > 0` guard already prevented it.
  The fix itself is still correct and worth keeping (explicit rejection before any body-reading
  logic is better than relying on an incidental `length > 0` guard staying in place forever, and it
  turns a would-be traceback into a clean `400` for the non-numeric case, which *is* a real,
  demonstrated regression the tests correctly catch). But the negative-length test as written adds
  no regression protection: if a future refactor reintroduced exactly the hang the review described
  (e.g. an unconditional `self.rfile.read(length)` with no `length > 0` guard anywhere), this test
  would not catch it, because it never observes whether `read()` was invoked with a negative count
  or an unbounded one — it only observes the final HTTP status, which was already `400` before the
  fix existed.
  **Fix:** strengthen (or add alongside) a test that actually distinguishes the two code paths —
  e.g. construct the handler with a spied/mocked `rfile` (or monkeypatch `_read_body` at the
  `self.rfile.read` call site) and assert `read()` is either never called or called with a
  non-negative argument when `Content-Length` is negative, rather than only asserting the outward
  HTTP status. A raw-socket approach that sends more bytes than any legitimate read should consume,
  then asserts the connection is not left waiting/hasn't consumed them, would also demonstrate the
  fix directly rather than incidentally.

### Optional Refinements

- `_read_body()`'s two `_respond_json(400, ...)` call sites for non-numeric and negative are
  identical in shape and only differ in nothing (same message on both branches) — could collapse to
  one `except (ValueError,) / if length < 0:` combined branch, but this is a readability preference
  only, not a correctness or scope issue (optional).
- `--poll-hz 0` or a negative `--poll-hz` is not validated anywhere in `capture.py` — falls through
  to `interval = 1.0 / poll_hz if poll_hz > 0 else 0.0`, i.e. a busy-poll loop with no sleep. This
  is **pre-existing** behavior, unchanged by this fix (the same `if args.poll_hz > 0 else 0.0`
  guard existed before, just reading `args.poll_hz` directly instead of the resolved `poll_hz`) —
  not introduced by this change, and out of scope for a fix whose task was per-source *defaults*,
  not general `--poll-hz` input validation. Naming it, not requiring it.

### Verdict

APPROVED WITH MINOR FIXES

### Review Confidence

Full read. Both diffs read in full against both review reports and `implementation.md`; ordering
and scope claims verified directly in the current `server.py`; the negative-Content-Length finding
was confirmed empirically (pre-fix `server.py` restored in a throwaway copy, new tests run against
it directly — 3/4 passed unmodified) rather than by inspection alone. `ruff format --check`, `ruff
check`, `mypy --strict` (`mypy src`), and `pytest -q` all run independently in a fresh
`audio-adapter/.venv` created for this review: format clean (29 files), lint clean, mypy clean (15
source files), tests **212 passed, 1 skipped** — matching the implementer's reported numbers.
