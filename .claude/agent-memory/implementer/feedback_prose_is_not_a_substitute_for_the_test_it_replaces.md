---
name: prose-is-not-a-substitute-for-the-test-it-replaces
description: Never take a docstring paragraph in place of an optional test that would assert the same fact — the prose goes stale and nothing fails.
metadata:
  type: feedback
---

When a review offers both "document what this actually does" and "add a test asserting what it
actually does", **do not treat taking the first as discharging the second.** They are not two
strengths of the same mitigation. Write the test; the prose is then optional.

**Why:** `fix/callout-observability-gate` did exactly this across two rounds. Round 2 raised an
optional test pinning the exempt callout line's *enriched* rendered form. Round 3 took a different
optional item instead — a docstring paragraph recording that same rendered form, with an example
string — and the test was left unwritten. By round 4 the example string was **wrong**:
`_OBSERVABILITY_EXEMPT_KINDS`' docstring said `"six o'clock, 1.0 km."` while the real render was
`"6 o'clock, 1 kilometre."`, because `belief/speech.py`'s `_format_range_km` had changed the
wording and no mechanism connected the two. Writing the test found it in one run. The paragraph
had been standing in for the test for three rounds and had, in that time, become a confident
false statement about the code sitting six lines above the code.

**How to apply:** if a review item's value is "a future reader will know X", ask what fails when X
stops being true. If the answer is nothing, the item is a test, whatever form it was proposed in.
Specific smell: a docstring containing a quoted example output string. That string is an
unasserted expectation — pin it, and have the prose cite the test's name rather than restate the
value. Related: [[feedback_counterfactual_must_not_perturb_a_constant_the_test_imports]], same
file, same branch, same shape of failure (a verification that looked done and was not).
