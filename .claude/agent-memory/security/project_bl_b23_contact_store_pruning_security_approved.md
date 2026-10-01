---
name: bl-b23-contact-store-pruning-security-approved
description: BL-B23 lost-contact clustering filter checked clean for the memory/false-absence invariant that matters on this project
metadata:
  type: project
---

`fix/contact-store-pruning` (`90057c4`, tip `2992d91`) filters `ContactStore.tick`'s call to
`GroupStore.reconcile` to `certainty_of(contact, now_sim) != "lost"`, fixing an O(n²) clustering
cost that scaled with total-contacts-ever-seen rather than live contact count (403 ms → 1.4 ms at
n=1200).

Checked independently (not inherited from the Reviewer's note) and confirmed clean:
- `describe_contact`/`get_contact_history`/crew-console/speech report-pull paths all read
  `ContactStore.contacts` (`contacts.py:699`, unfiltered `_contacts.values()`), never the local
  filtered comprehension passed inline to `reconcile`. A `lost` contact stays fully answerable.
- `GroupStore.reconcile` fires no event when a cluster shrinks/disappears (its own docstring); the
  group-speech delta taxonomy already treats membership loss as silent-at-group-level, deferring to
  that contact's own pre-existing `LOST` lifecycle event. No new "departed/destroyed" claim is
  introduced — "not clustered" is never conflated with "not there" anywhere in this diff.
- Re-admission on reacquisition needs no sticky state (`certainty_of` is pure on
  `now_sim - last_seen_sim`).

Residual, noted but not a finding: `tick`'s other seven per-contact blocks still scan all of
`_contacts` every tick (O(n_total), linear) — `_contacts` has no delete path. Not the DoS shape the
original finding was (that was the O(n²) clustering specifically); worth a MONITOR if total-contact
counts grow another order of magnitude.

See [[project_bl_b23_memory_vs_clustering_filter_pattern]] for the generalizable pattern.
