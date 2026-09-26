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

---

## Round 2: Re-review of `1b2e337` (fix for the round-1 required fix)

Diffed `1b2e337` against `64e9d37`. This is the round-1 required fix landing.

### On the rejected mechanism

Round 1 suggested spying/mocking `rfile.read` and asserting it is never called with a
negative/unbounded count. The implementer rejected that mechanism and reports it would not have
distinguished pre-fix from post-fix for this specific case, since `2802c4f`'s own
`self.rfile.read(length) if length > 0 else b""` ternary already keeps a negative `length` from
ever reaching `rfile.read()` in **either** version — verified independently against `2802c4f`'s
literal source (`git show 2802c4f:audio-adapter/src/server.py`, lines 138/190): both `_handle_speak`
and `_handle_transcribe` use exactly that ternary, with no shared `_read_body` helper at all pre-fix
(each handler inlines its own `int(...)` + ternary). **The implementer's reasoning is correct, and
the round-1 suggestion would not have worked** — this is the review process functioning as intended,
not a defect in the fix.

The substitute mechanism — asserting the response body equals the exact
`{"error": "invalid Content-Length: '-1'"}` — is the right call given that constraint: with `rfile.
read` never called differently between the two versions, the HTTP-visible response body is the only
remaining discriminator. It does trade in some brittleness (a future reword of either message breaks
the test on cosmetics, not behavior), which is an acceptable cost here given the test's clear
docstring explaining exactly why the exact match matters — a future maintainer rewording the message
will not be confused about why the test broke. Optional refinement below softens this without
losing the discrimination.

### Empirical reproduction (independent)

Extracted `1b2e337`'s `audio-adapter/` via `git archive` into a scratch copy (this worktree's own
checkout was on an unrelated branch, `bd28563` — the `fix/audio-adapter-review-findings` branch is
checked out in the main working copy, so it could not be checked out here too). Ran the two
strengthened tests against the genuine pre-fix `server.py` (`git show 2802c4f:...`, byte-for-byte,
not reconstructed from memory):

```
tests/test_server.py::test_speak_negative_content_length_returns_400 FAILED
tests/test_transcribe_api.py::test_transcribe_negative_content_length_returns_400 FAILED
```
Both failed with the predicted mismatch — `{'error': 'body must be valid JSON'}` vs. the expected
`{'error': "invalid Content-Length: '-1'"}`. (Also ran the two non-numeric tests against the same
pre-fix file for completeness: both failed too, one with an assertion mismatch and one with the raw
`ValueError`/`RemoteDisconnected` the original security finding described — confirming that half of
the finding was and remains real.) Restored the post-fix `server.py` and re-ran both strengthened
tests: both passed. This independently confirms the implementer's claim — not accepted on the
report.

### Collapsed `_read_body` branch

Confirmed no behavioral change for either input class. Non-numeric now sets `length = -1` in the
`except ValueError` clause and falls into the same `if length < 0` branch as a literal negative
value; the response message is still built from `raw_header` (the original string), not the
coerced `-1`, so `"invalid Content-Length: 'not-a-number'"` and `"invalid Content-Length: '-1'"` are
both still accurate to what was actually sent.

### Security-report correction

Confirmed the original wrong claim (negative-length → unbounded `rfile.read` → thread hang) is
annotated in place, not deleted — the correction quotes the original text verbatim, explains the
actual pre-fix mechanism, and cites this review's empirical check by name. The downstream
cross-reference in "Focus-area findings" §1 (the "only per-request wedge risk" sentence,
originally at row 111) is also annotated consistently with the correction above it — read both, they
agree with each other and with what I reproduced. No half-corrected claim left in the document.

### Scope

No body-size cap added (still out of scope, per the task). `--poll-hz` validation untouched
(`capture.py` unchanged in this diff, grepped to confirm). No drift.

### Verification (independent)

Ran against the same `1b2e337` extraction, using the existing `audio-adapter/.venv`:
- `ruff format --check src tests`: pass (29 files already formatted)
- `ruff check src tests`: pass
- `mypy --strict src`: pass, no issues in 15 source files
- `pytest tests -q`: **212 passed, 1 skipped** — matches the implementer's report, unchanged from
  round 1.

### Round 2 Required Fixes

None.

### Round 2 Optional Refinements

- The exact-match assertion (`resp_body == {"error": "invalid Content-Length: '-1'"}`) is slightly
  more brittle than necessary — asserting the message via `resp_body["error"].startswith("invalid
  Content-Length")` would still discriminate from the JSON-validation path's `"body must be valid
  JSON"` while surviving a cosmetic reword of the quoted value's repr. Not required: the docstring
  already explains the exact-match choice, and the two tests changed are small and isolated (optional).

### Round 2 Verdict

APPROVED

### Round 2 Review Confidence

Full read. Diff read in full against round-1 review and `implementation.md`'s Round 2 log;
`2802c4f`'s literal source read directly to verify the rejected-mechanism claim rather than taking
it on the report; pre-fix/post-fix behavior reproduced independently in a scratch extraction (not
the implementer's own scratch files); format/lint/mypy/test commands run independently and matched
the reported counts.
