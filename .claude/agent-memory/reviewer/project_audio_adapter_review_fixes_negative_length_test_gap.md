---
name: audio-adapter-review-fixes-negative-length-test-gap
description: audio-adapter fix for perf/security review findings (poll-hz default, Content-Length guard) — required fix found and how it was proven
metadata:
  type: project
---

`fix/audio-adapter-review-findings` (639a94c) fixed two review findings: `--poll-hz` per-PTT-source
default (`capture.py`, perf review finding 1) and a `Content-Length` guard (`server.py`, security
review RECOMMENDED #2). Both fixes were clean, correctly scoped, no adjacent bookkeeping disturbed —
the `_handle_transcribe` 503-before-body-read ordering the implementer flagged as a risk was checked
and confirmed still correct.

One required fix found: the new negative-`Content-Length` tests
(`test_speak_negative_content_length_returns_400`,
`test_transcribe_negative_content_length_returns_400`) pass against the **pre-fix** code too. The
pre-fix `server.py` already guarded the read with `self.rfile.read(length) if length > 0 else
b""` — a negative length takes the `else b""` branch and never reaches `rfile.read()` with a
negative count at all, so the security review's stated hang mechanism does not occur on this code
path pre-fix; a negative length already landed on 400 via the empty-body JSON-parse-failure path.
Confirmed empirically, per [[feedback_regression_test_empirical_check]]: restored 2802c4f's
`server.py` in a throwaway copy and ran the new tests against it directly — 3 of 4 new
`test_server.py` Content-Length tests passed unmodified (only the non-numeric case failed, as
expected). The fix is still worth keeping (explicit rejection beats an incidental guard, and it
turns a traceback into a clean 400 for the non-numeric case — a real, demonstrated regression the
tests do catch), but the negative-length test itself proves nothing about the hang it's named for
and would not catch a future regression that reintroduced an unconditional `rfile.read(length)`.

**Generalizable lesson:** when a security/perf review's stated mechanism involves a guard
(`if x > 0 else ...`) elsewhere in the same function, check whether that pre-existing guard already
prevents the exact bad input the new test targets, before trusting a new test's assertion on final
HTTP status alone. A test on outward status can pass for a completely different internal reason than
the one it's meant to protect.
