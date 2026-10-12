---
name: feedback_widening_a_tested_helper_vs_a_sibling_function
description: Before widening a shared helper's signature/return arity to add one more thing of the same shape, check how many existing tests unpack its return positionally -- a sibling function can be the smaller diff and the one that doesn't touch tests at all
metadata:
  type: feedback
---

`BL-12` Stage 1 review required fix 2: wire `--group-trace` through the same per-run stamping/mkdir/
degrade policy `logger._per_run_log_paths` already applies to `--detection-trace`/
`--belief-truth-log`/`--speech-log`. The review's own recommended phrasing was "one line in
`_per_run_log_paths`" — i.e., widen it to a fourth parameter and a 4-tuple return.

**That function's three-log arity is literally what nine tests in `tests/test_run_log_paths.py` are
written against** — every one of them does `trace, truth, speech = logger_module.
_per_run_log_paths(...)`, a positional 3-tuple unpack. Widening the signature to four would force
touching all nine call sites' unpacking for a reason that has nothing to do with what any of them
test — exactly the shape of "modifying existing tests without explicit permission" this role is
told to avoid, except it would be hidden inside "just adding a parameter."

**What I did instead**: wrote a standalone sibling function (`_resolve_group_trace_log_path`) that
reproduces the same stamp/`expanduser()`/`mkdir`/`except _RESOLVE_FAILURES` policy verbatim (reusing
the shared `_RESOLVE_FAILURES` tuple, not re-declaring it), called once from `main()` right after
the original three-log call, printed through the same per-log stderr loop. Zero existing tests
touched; the new function got its own three small tests mirroring the existing ones' shapes.

**Why:** a shared helper's *signature and return shape*, not just its logic, can be the thing a test
suite is actually pinned to. A review's "one line" framing describes the logical change, not the
blast radius of the literal edit — check the blast radius (how many call sites unpack the return,
and how) before accepting the literal suggested edit.

**How to apply:** before widening a tested function's parameter list or return arity to add one more
of the same kind of thing, `grep` for its call sites and look at *how* they consume the return (one
value vs. unpacked tuple, positional vs. keyword). If most are positional-unpack tests of exactly
the old arity, a sibling function (even one that duplicates a few lines of policy) is very often the
smaller, test-safe diff — flag the choice explicitly in the implementation log rather than silently
picking one, since it is local and reversible but a reviewer might reasonably prefer the literal
"one line" over the duplication.
