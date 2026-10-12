---
name: bl12-stage3-5-admission-gate
description: BL-12 Stage 3.5 (BL-B58) pattern -- reading a store's own about-to-be-reassigned state as "the previous tick's truth", and re-running a scratchpad probe against the real pipeline (not just the isolated predicate) to catch what the predicate-only re-run can't.
metadata:
  type: project
---

Implementing `plans/group-cohesion-admission-gate/plan.md` (BL-12 Stage 3.5, `BL-B58`): the
cohesion admission gate needed "the previous reconcile's group rosters" as an input to *this*
reconcile's clustering pass. The plan asserted `GroupStore.reconcile` already has this for free,
because `self._groups` is not reassigned (`self._groups = new_groups`) until the very end of the
method -- so reading `self._groups` right before calling `_cluster_contacts` gives exactly the
prior tick's state, with zero new bookkeeping.

**Verified by reading the method directly rather than trusting the plan's claim** -- grepped both
line numbers (`persisted = dict(self._groups)` and the reassignment) and confirmed the read
genuinely precedes the write with nothing in between that could mutate `self._groups` first. This
is a reusable pattern worth recognising elsewhere in this codebase: a method that holds "old state"
in an instance attribute until its own last line, rather than in a local copied early, lets a late
caller read "before" for free -- but it is fragile to a refactor that moves the reassignment
earlier, so any new reader added this way should cite the exact line it depends on (as the
docstring here now does), not just describe the behaviour in prose.

**The stronger verification step: re-run a plan's own scratchpad probe against the real pipeline,
not just its isolated-predicate reimplementation.** This plan's probe 3
(`probe_b58_candidate.py`) reimplements only the predicate and was always going to match once the
real `_cluster_contacts` matched its own reasoning -- a somewhat circular check. Probe 2
(`probe_b58_second_incident.py`) drives the real `ContactStore.tick()` → `GroupStore.reconcile()`
pipeline unmodified, so re-running it after the implementation landed is a genuine end-to-end
check, and it caught something the predicate-only probe could not have: `BL-B59`'s eviction half
(a real, correctly-identified member dropping out of the group) still fires through the real
pipeline even with the admission gate correctly blocking the absorption, in the *same* probe run.
Running only the predicate reimplementation would have reported "fixed" without ever showing that
sibling defect was still live. [[feedback_re_derive_the_figures_a_review_hands_you]]
