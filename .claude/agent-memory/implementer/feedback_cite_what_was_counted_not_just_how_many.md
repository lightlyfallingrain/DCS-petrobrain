---
name: cite-what-was-counted-not-just-how-many
description: A quoted count must name the collections it summed, because a bare number is unresolvable when it disagrees with a re-run — cost a review round on BL-B47
metadata:
  type: feedback
---

**When citing a measured count in a docstring, test or log, say *what was counted*, not just how
many.** Name the collections, their individual sizes, and the expression that produced the verdict.

**Why:** `BL-B47` (2026-10-10) cited *"all 128 keyword entries in `perception.object_model`"* in
three places. The real figure is 131 — `_KEYWORD_PROFILES` 70 plus `_REPORTING_NAME_KEYWORD_PROFILES`
61 — and the module has **two** keyword tables, so `len()` on the one that looks like "the keyword
table" is 54% of the real population. The error cost a whole review round, and the user's reason for
spending it was precise: a bare wrong number costs the next person who re-runs it an hour working
out whether the table grew since, because there is nothing in the sentence to check against. `131
(70 + 61)` is self-diagnosing; `128` is not.

Second half of the same lesson: **round 1's enumeration was real but narrow** (~141 values, the
keyword tables plus the `op_class` values). Widening it to the 595-row
`reporting_names` mapping's keys *and* values brought it to 1060 and the conclusion got *stronger* —
still 0 lost / 4 gained. A keyword table enumerates the matcher's own substrings; the mapping
enumerates what the predicate actually sees at runtime. **Prefer the realistic population, and say
which one you used.**

**How to apply:** any time a number lands in committed prose — a docstring, a test docstring, an
implementation log, a memory file. Write the arithmetic, not the sum. And when a reviewer hands you
a corrected figure, re-run the measurement yourself and cite your own run, per
[[feedback_counterfactual_must_not_perturb_a_constant_the_test_imports]]'s rule that a measurement
is evidence only if you executed it — a transcribed correction is the same unresolvable number with
a different value.
