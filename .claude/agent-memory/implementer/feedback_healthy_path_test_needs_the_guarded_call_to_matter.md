---
name: healthy-path-test-needs-the-guarded-call-to-matter
description: A "the guard is not hiding a failure" test must be built so the guarded call is load-bearing; assert the precondition inline or the test has no teeth.
metadata:
  type: feedback
---

When a `try`/`except` or `contextlib.suppress` is added around a call, the
companion test that says *"the guard must not be hiding a failure on the
ordinary path"* only earns that docstring if the **guarded call is the thing
that produces the asserted effect**. Set up the fixture so the effect is
*absent* before the call, assert that inline, then call and assert it is
present.

**Why:** on `feature/bl11-tick-cost` both writers' healthy-close tests
asserted `path.read_text().strip() != ""` after `close()` — and gutting
`close()` to a bare `return` in both writers left **all four** close tests
passing. The rows were already on disk: `flush_every_n_polls=1` in one case,
and `write_speech` flushing eagerly by design in the other. The docstring's
claim was simply false, and nothing in the suite could tell.

**How to apply:**

- Find the knob that defers the effect past the guarded call. Here it was
  `flush_every_n_polls=2` with **one** poll written — one short of the flush
  interval, so the row sits in the file object's own buffer.
- **Assert the precondition inline, with a message that names the failure
  mode** (`assert path.read_text() == "", "row flushed before close(); test
  has no teeth"`). That line is what stops a later fixture change silently
  re-breaking it; a comment would not.
- **Re-run the mutation after the fix, not only before.** Before tells you the
  test was weak; after tells you it is now strong. Back the file up to the
  scratchpad first and restore from that copy — never `git checkout --`, which
  would take unstaged work with it ([[revert-test-scratch-copy]]) — then
  `shasum` to prove the restore is byte-identical.
- **Expect the raises-case half to be undetectable by this mutation**, and do
  not read that as the mutation failing. A `close()` that does nothing also
  does not raise, so only the healthy half can carry the teeth. The same
  asymmetry showed up in [[project-group-salience-equivalence]]-style optic
  cases: a fixture whose parameter is the identity (here `presence_range_mult
  = 1.0`) cannot detect a mutation to the term it multiplies.
