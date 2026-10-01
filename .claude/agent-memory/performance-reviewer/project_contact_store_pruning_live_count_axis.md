---
name: contact-store-pruning-live-count-axis
description: BL-B23's lost-contact clustering filter fixes the total-ever-seen growth axis only; simultaneous-live-contact count is still O(n^2) in GroupStore._cluster_contacts, unchanged by design.
metadata:
  type: project
---

After `BL-B23` (`fix/contact-store-pruning`, `90057c4`) excluded `lost` contacts from `GroupStore.reconcile`'s input, the implementer's "after" benchmark (flat 0.15-1.4ms across 22-1200 *total* contacts) fixed the live count at 20 and only grew the lost tail. That flatness is real but answers only one axis.

Measured separately (2026-10-02, this review): growing the *live* count itself (all contacts simultaneously fresh, `ContactStore.tick()` end to end) reproduces the original pre-fix quadratic exactly — 20->0.15ms, 50->0.77ms, 100->2.88ms, 200->11.19ms, 300->25.12ms, 500->69.80ms. This is correct and expected: `BL-B23` was never scoped to the live-count axis, only to total-ever-seen.

**Why:** a future reviewer (or the implementer reporting "after is flat") could mistake the BL-B23 fix for having solved clustering cost generally. It solved the long-sortie-accumulation axis only. The live-count quadratic is the same mechanism the `group-cohesion-redesign` performance review already found and MONITORed independently ([[group_reporting_cohesion_scale]]) — it was not introduced or changed by this fix.

**How to apply:** when asked whether `BL-B23`-style fixes resolved body-layer clustering performance, answer with both axes: total-ever-seen is now bounded (fixed), simultaneous-live-count is not (pre-existing, still quadratic). 300 live contacts in the 10km player bubble costs ~25ms/tick (12% of the 200ms 5Hz budget); 500 live costs ~70ms (35%). Whether a mission realistically reaches 300-500 *simultaneous* live contacts (not total-ever-seen) within the bubble is the open question for any future action here — not yet observed in this project's sorties. See [[contact_store_never_pruned]] for the fix itself and [[player_bubble_capped_by_existing_gates]] for what the bubble already filters before contacts reach the store.
