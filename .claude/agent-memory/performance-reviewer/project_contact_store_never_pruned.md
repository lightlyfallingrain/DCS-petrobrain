---
name: contact-store-never-pruned
description: ContactStore._contacts has no removal path; belief.groups._cluster_contacts reconciles over every contact ever seen, not just live ones, so its O(n^2) cost grows with sortie length, not simultaneous contact count.
metadata:
  type: project
---

`body-layer/src/belief/contacts.py::ContactStore` has no delete path for `_contacts` (grepped, confirmed 2026-10-01 on `fix/group-undermerging`). `ContactStore.tick`'s "Eighth block" calls `self._groups.reconcile(list(self._contacts.values()), now_sim)` — the full historical set, not a live/currently-tracked filter.

`belief.groups._cluster_contacts` is O(n^2) in that count (measured same date: 22->0.17ms, 100->3ms, 300->25ms, 500->70ms, 800->180ms, 1200->406ms, clean quadratic from n=100 up). At the real sortie's instantaneous scale (22 objects) this is nothing. The actual risk is a 90-minute sortie accumulating hundreds of long-LOST `Contact` records that `reconcile` still pays for every tick, forever. (**Corrected 2026-10-06**: this said "at 5 Hz". The poll loop has never run at 5 Hz -- `logger._DEFAULT_POLL_INTERVAL_S` is 1.0 s and always has been; 5 Hz is `Export.lua`'s producer rate. So the per-tick cost here is paid 5x less often than this entry assumed, and any budget percentage derived from it was 5x too high. See `project_body_layer_poll_loop_diagnosis.md`.)

**Why:** discovered while reviewing `fix/group-undermerging`'s per-pair cohesion backstop redesign — that diff only adds a few dict lookups per pair (same complexity class), but surfaced that the real growth-over-time exposure lives in what `reconcile` is handed, which predates this diff (group-reporting Stage 2) and is unrelated to it.

**How to apply:** if a future performance review (or the user) asks about body-layer hot-path cost at long-sortie scale, check `ContactStore`'s total ever-seen contact count trajectory, not just simultaneous-contact counts — that is where a budget violation would actually come from. Recommend as a `BL-B` backlog item (filter `reconcile`'s input by lifecycle/age before clustering) rather than blocking whatever diff happens to surface it next, unless that diff is the one introducing the unfiltered call site. See [[group_reporting_cohesion_scale]] for the clustering benchmark itself.

**FIXED 2026-10-02** (`BL-B23`, `fix/contact-store-pruning`, `90057c4`): `ContactStore.tick`'s eighth block now filters to `certainty_of(contact, now_sim) != "lost"` before calling `reconcile` — `_contacts` itself still has no delete path (deliberately: a `lost` contact stays answerable via `describe_contact`/`get_contact_history`), but clustering's input is now bounded by live count, not total-ever-seen. Independently reproduced: before 418.66ms/after 1.37ms at n=1200 (matches implementer's 402.99/1.37 and this file's own original 405.8ms within noise). See [[contact_store_pruning_live_count_axis]] — the fix only flattens the total-ever-seen axis; the live-count axis is still the same O(n^2) this entry originally measured, now MONITOR under that still-open finding rather than this one.
