---
name: project-bl12-group-identity-perf
description: BL-12 (group-level contact identity) performance pass -- all terms sub-ms at realistic scale; GroupTraceLogWriter's own docstring overstates how rare its writes are
metadata:
  type: project
---

Reviewed BL-12 in full (Stages 0/0a/0b/1/2a/2b/3/3.5/4; Stage 5 skipped, Stage 6 deferred) against
the BL-11 budget (12.6 ms median/poll, 1.000 s period). Full report:
`plans/group-contact-identity/performance-review.md`.

**Headline: nothing in BL-12 moves the 12.6 ms baseline.** Full `GroupStore.reconcile()` measured
0.1-1.3 ms at realistic-to-busy sortie scale (12-60 contacts, 4-15 clusters), real `Contact`/
`GroupStore` objects, not mocks. `_cluster_contacts`'s O(n²) shape is pre-existing (noted in its
own docstring before BL-12); Stage 3.5's admission gate adds O(1) work per edge via a
pre-flattened `dict[str, frozenset]` lookup, exactly as that stage's own plan specified -- verified
by reading the code, not just trusting the plan's description of itself.

**One finding worth remembering for next time a writer's docstring justifies its own design**:
`group_trace_log.GroupTraceLogWriter`'s docstring says a trace write is "a handful of rows per
sortie... not hundreds per poll," used to justify staying unbuffered (open+write+close per call,
no batching). Reading the actual call site (`groups.py` `reconcile`'s trace-record loop) shows it
fires for **every active cluster on every reconcile call**, not just the rare phase-2/expire
events the docstring describes. The *measured* cost is still trivial today (~0.03 ms/write, so
~0.5 ms/poll at a busy 15-cluster scene) -- this is not a performance defect, just a stated
rationale that is false for the common case. Filed as a documentation-only change request rather
than hand-edited, per the project's "change request re-enters the implementation loop" rule.

**Transferable lesson**: a writer's own docstring claiming "this is rare, so unbuffered is fine"
is exactly the kind of self-justifying design note worth checking against the actual call site
before trusting it on a future, larger feature -- the claim can be true of the writer's *stated
purpose* (phase-2/expire) while false of what the code actually calls it for (every cluster).
