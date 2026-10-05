---
name: contact-store-pruning-live-count-axis
description: BL-B23's lost-contact clustering filter fixes the total-ever-seen growth axis only; simultaneous-live-contact count is still O(n^2) in GroupStore._cluster_contacts, unchanged by design.
metadata:
  type: project
---

After `BL-B23` (`fix/contact-store-pruning`, `90057c4`) excluded `lost` contacts from `GroupStore.reconcile`'s input, the implementer's "after" benchmark (flat 0.15-1.4ms across 22-1200 *total* contacts) fixed the live count at 20 and only grew the lost tail. That flatness is real but answers only one axis.

Measured separately (2026-10-02, this review): growing the *live* count itself (all contacts simultaneously fresh, `ContactStore.tick()` end to end) reproduces the original pre-fix quadratic exactly — 20->0.15ms, 50->0.77ms, 100->2.88ms, 200->11.19ms, 300->25.12ms, 500->69.80ms. This is correct and expected: `BL-B23` was never scoped to the live-count axis, only to total-ever-seen.

**Why:** a future reviewer (or the implementer reporting "after is flat") could mistake the BL-B23 fix for having solved clustering cost generally. It solved the long-sortie-accumulation axis only. The live-count quadratic is the same mechanism the `group-cohesion-redesign` performance review already found and MONITORed independently ([[group_reporting_cohesion_scale]]) — it was not introduced or changed by this fix.

**How to apply:** when asked whether `BL-B23`-style fixes resolved body-layer clustering performance, answer with both axes: total-ever-seen is now bounded **for clustering**, simultaneous-live-count is not (pre-existing, still quadratic). 300 live contacts in the 10km player bubble costs ~25ms/tick; 500 live costs ~70ms. Whether a mission realistically reaches 300-500 *simultaneous* live contacts (not total-ever-seen) within the bubble is the open question for any future action here — not yet observed in this project's sorties. See [[contact_store_never_pruned]] for the fix itself and [[player_bubble_capped_by_existing_gates]] for what the bubble already filters before contacts reach the store.

**Two corrections from the 2026-10-05 whole-subproject pass ([[body_layer_poll_loop_diagnosis]]):**

- **"the 200ms 5Hz budget" in the line above was wrong** and is struck. body-layer's poll interval has been `1.0 s` by default since 2026-09-08; there is no 5 Hz configuration. Percentages against a 200 ms budget overstate every clustering number here by 5×. I took the 5 Hz figure from the same stale docstrings `BL-B30` took it from.
- **`BL-B23` bounded total-ever-seen for *clustering only*, not for the store generally.** `_contacts` still has no delete path, and two other consumers still walk every contact ever founded, every poll: `ContactStore.tick`'s eight per-contact blocks (`contacts.py:1088`) and `ingest`'s gate-scan comprehension (`contacts.py:957-963`, which also does not short-circuit at two passing candidates even though `len(passing) == 1` is the only distinction it makes). Measured small today — 6.4 ms and 0.7 ms at 142 live contacts — but they scale with total, and `BL-B24`'s churn inflates total well above live (554 contacts for 444 real objects on the 2026-10-05 sortie). This is the same shape of finding one consumer further along, so file it under `BL-B23`'s lineage rather than as something new.
