---
name: group-collapse-perf
description: collapse(group, depth) is linear in members even at 4000-member adversarial scale, never routes through describe_contact (verified by grep+read), and is called redundantly once per member via the pre-existing describe_contact-per-member pattern -- but all of it is cheap enough (<3.3% of BL-11's 12.6ms poll at worst) that none of it is a NOW finding.
metadata:
  type: project
---

Reviewed 2026-10-13, `feature/group-collapse` @ `ed50840a2b43ef117773f4624951eb9a0c6c960b`. Full
report: `plans/group-collapse/performance-review.md`.

- **`collapse_members` scales sub-linearly per member** even at the worst-case shape (many `TYPE`
  values spread across all 5 air-defence sub-classes, forcing `_type_children`'s dict-build on
  every bucket at `CollapseDepth.CONTACT`): per-member cost *fell* from 6.24 us (n=52) to 2.45 us
  (n=4000). Single-pass bucketing + a bounded bucket count (5 sub-classes) is why. Re-tested with
  `plans/group-collapse/scratchpad/perf_review_adversarial_scaling.py`, 77x past the plan's own
  ceiling (real groups never exceed ~52 contacts *across the whole scene*, let alone one group).
- **Decision 3's `describe_contact` prohibition verified independently, not inherited**: grepped
  `group_view.py` for `describe_contact`/`enrichment`/`WorldEnrichmentCache`/`semantic_facts_for`/
  `terrain_divide` -- all hits are in the module's own docstring, zero in executable code. Confirmed
  by reading every line: only `Contact.classification`/`.cardinality`/`.position`/`.id` and
  `belief.decay.classification_confidence_at` are read. If this had been wrong, [[report-query-enrichment-dominates]]'s
  63.25 ms/contact cold figure would apply per member and a 6-member full-depth collapse would cost
  ~380 ms -- so this boundary is the entire reason the feature is cheap, and it is worth re-grepping
  on any future touch to this module.
- **A real but harmless redundancy: `collapse(SUBCLASS)` recomputes once per group member per poll**,
  because `belief.tools._group_facts` is reached via `describe_contact`, which both
  `speech._group_member_facts` (one call per member, pre-existing) and `callouts.py`'s per-event loop
  (one call per live event) can call once per member of the same group in one poll. This is dwarfed
  by the *existing* per-member `describe_contact` enrichment redundancy (same shape, 63.25 ms/6.77 ms
  per call vs. `collapse`'s ~12-70 us) -- don't propose fixing the cheap one in isolation; it rides
  the same pattern as the expensive one and should be fixed together if ever fixed.
- **The plan's own "~5 us/tick shallow" push-path arithmetic used the wrong depth.** Its per-member
  table gives depth-0 (`GROUP`)=0.45us, depth-2 (`SUBCLASS`)=5.2us, depth-4 (`CONTACT`)=7.8us for
  6 members; the push-path sentence computed 10x0.45us="~5us shallow", but the actual Stage 2 caller
  (`tools.py:328`) requests `CollapseDepth.SUBCLASS`, i.e. the real figure from its own table is
  ~52us, not ~5us. Measured with a realistic mixed roster (not the plan's uniform-armor sample):
  ~235us/tick at SUBCLASS (1.86% of 12.6ms), ~415us/tick at CONTACT (3.3%) for 10 groups x 6 members
  -- still trivial, but 5-47x higher than the plan's quoted percentages. **A plan's own per-depth
  table and its push-path summary sentence can silently use different depths — check which depth a
  caller actually requests before trusting an aggregate percentage built from that table.**
- **A caller-side observability gate can be a correctness mechanism with zero performance value**,
  and that's fine. `callout_observable`'s "any member, not all" gate costs O(members) field reads
  regardless of prune rate, and `collapse` is cheap enough that the gate's prune rate doesn't move
  poll cost either way — did not bother simulating a scene to measure it, because no possible result
  changes the verdict.

Related: [[report-query-enrichment-dominates]], [[bl11-measured-outcome]], [[benchmarks-must-be-able-to-fail]].
