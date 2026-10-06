---
name: watch-tag-amplification
description: Marking N contacts watched is a describe_position multiplier via event-emission gates, and a 50m per-tick memo gives zero relief for group members.
metadata:
  type: project
---

Two measured facts from the `feature/sortie-refinements` pass (2026-10-06, body-layer at `18da60e`,
real `syria-full.sqlite`).

**1. `Contact.attention == "watch"` is an event-production gate, not just a speech filter.** So any
feature that marks several contacts watched in one action multiplies `CalloutScheduler.tick` cost,
not just its output:

- `CONTACT_RANGE_CROSSED` is gated at **emission** (`belief/contacts.py`, "sixth block") — N watched
  contacts means N event streams where one meant one.
- `CONTACT_MOTION_CHANGED` is **not** gated at emission; it was always produced and discarded by
  `callouts.py`'s `_WATCHED_ONLY_KINDS` not-watched `continue`. Watching N members makes all N
  survive the filter.
- Each surviving watched-only event costs **two** `describe_contact` calls per tick (the filter's,
  then scoring's), and `tick` speaks only one candidate and **does not consume the losers**, so they
  are re-described every non-busy tick until `CALLOUT_MAX_AGE_S` (10 s).
- `WATCH_REPORT_MIN_GAP_S` is keyed on `contact_id`, so it does **not** damp across N *different*
  members. Only `busy_until_sim` does.

**Look at the gates, not the per-contact unit cost.** The `attention == "watch"` branch that *looks*
expensive — `enrichment.py`'s `max_iterations=5` fixed-point projection — is **0.12 ms**
(`project_terrain_aware` 0.03 ms at 1 iteration vs 0.15 ms at 5). The cost is the
`describe_position` immediately after it: **51 ms** for group-member positions, **78 ms** median for
positions scattered within 9 km. A plan that clears the projection branch has not cleared the
feature.

**2. A 50–100 m quantised per-tick `describe_position` memo gives near-zero relief for group
members**, and this is the trap: the memo is the right fix for the *same contact gathered 3×* in one
tick, so it reads as the fix for per-member cost too. It is not. 8 members spread 300 m land in
**8 distinct cells at a 50 m grid**, 6 at 100 m, 3 at 200 m — group members are separated by more
than the grid *by definition* (that is what `_cluster_contacts` means). Before claiming a landing
quantisation fix covers a per-member multiplier, compute the cell count at the actual grid size.

Related: [[project_group_reporting_cohesion_scale]], [[project_contact_store_pruning_live_count_axis]],
[[project_watch_reporting_scale_notes]].
