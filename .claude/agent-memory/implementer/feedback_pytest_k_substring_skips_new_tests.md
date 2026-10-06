---
name: pytest-k-substring-skips-new-tests
description: A `-k` selection can silently miss a test you just wrote and still report a clean pass — run the full suite before believing it.
metadata:
  type: feedback
---

**Never conclude new tests pass from a `-k` run. Run the full suite.**

**Why:** on `fix/callout-observability-gate` I added three tests and ran
`pytest tests/test_callouts.py -q -k "engagement or exemption"`. It reported `4 passed` — two
pre-existing plus two of mine — and read as full coverage of the new work. The third,
`test_exempt_line_discloses_only_belief_derived_facts`, was **never run**: `-k` is a plain
substring match and `"exempt"` does not contain `"exemption"`. The full suite then failed on it
immediately (a wrong expected string). Had I committed on the `-k` result, a broken test would
have gone in with a green report attached.

The danger is the shape of the output, not the mechanism: `4 passed` with zero failures and zero
errors is indistinguishable from success. A skipped test is invisible in a `-k` run — the
deselected count is the only trace, and it is a number you have nothing to compare against.

**How to apply:** `-k` is fine for the tight edit/run loop while getting one test working. The
moment you are about to report, commit, or believe a counterfactual, run the whole suite — this
one is ~12s, so there is no cost argument. If you must stay narrow, select by **node id**
(`tests/file.py::test_name`), which cannot silently match nothing, or check that the passed count
equals the number of tests you meant to run.
