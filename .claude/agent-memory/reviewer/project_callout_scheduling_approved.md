---
name: project_callout_scheduling_approved
description: callout-scheduling-and-aggregation reviewed APPROVED clean — how to hand-verify sim-time-only occupancy and clock-merge boundaries beyond what the test suite covers.
metadata:
  type: project
---

`feature/callout-scheduling-and-aggregation` (belief/callouts.py's `CalloutScheduler`) reviewed
2026-09-22, APPROVED, no required fixes. 858 passed / 4 xfailed reproduced directly (ruff
format/check, `cd body-layer && mypy src`, `pytest tests -q`).

**Verification techniques worth reusing for any future speech-timing/occupancy module:**
- To check "never wall clock" claims, grep the module for `time\.|datetime|perf_counter|thread` —
  don't just read the docstring's claim. Zero hits here confirmed the claim.
- To check a chaining/clustering cap (`CALLOUT_GROUP_MAX_SPAN_HOURS` etc.) is real, don't stop at
  reading the test suite — call the private helper (`_chain_by_clock`) directly with hand-built
  boundary cases (exactly-at-span, one-over-span, a 4-member chain that should split). Here this
  caught that the boundary/cap logic was correct but had *no dedicated unit test* — it was only
  incidentally exercised inside one large fixture. See [[feedback_boundary_only_tested_via_fixture]].
- To check the perception/belief no-omniscience boundary (`belief/` must not import
  `perception.clustering`/see `ClusterCandidate`), grep the new module's own import list, not just
  its docstring prose about why it doesn't.

**A plan defect the implementer found and resolved correctly**: the plan's worked example wrote a
3-member group as "three infantry", but the actual reused mechanism (`_cardinality_phrase`,
`lo>=2 and hi<=3 -> "a couple of"`) renders it identically to a 2-member group. Implementer followed
the real mechanism over the plan's prose and documented the mismatch in the test's own docstring —
judged this the right call: the `"a couple of"` bucket is *pre-existing* Stage 4b behavior
(group-contact-model), not something this feature introduced; this feature only newly exposes it
through aggregation. Inventing a special case to match wrong prose would have been worse.
