---
name: enrichment-cache-axes
description: WorldEnrichmentCache is keyed per contact_id, so the 50 m grid fixes the across-poll miss only and can never touch the N-members axis.
metadata:
  type: project
---

`belief.enrichment.WorldEnrichmentCache.get_or_compute` looks up `self._cache.get(contact.id)`
— **one entry per contact**. BL-11 Stage 3b quantised the *position* component of that key onto
a 50 m grid (`ENRICHMENT_CACHE_POSITION_GRID_M`, integer `math.floor` cell indices, not rounded
floats). Two axes, routinely conflated:

- **Across polls, per contact — fixed by Stage 3b.** A re-observed contact used to miss *by
  construction* (fresh fused position ⇒ exact-equality miss; a 1 m nudge cost the full 42 ms).
  Gone.
- **Across contacts, within one tick — structurally untouchable by any version of this key.** N
  group members are N `contact_id`s ⇒ N entries ⇒ N computes on first touch. The grain is
  irrelevant: they would occupy N entries standing on the same spot. The `sortie-refinements`
  reviewer's N-members finding is right, and for this stronger reason rather than "members are
  spread wider than 50 m".

**Measured outcome (2026-10-06, `8fa2ad6`):** overall 97.7 % hit rate; **within callout-bearing
ticks 89.7 %**, against the pre-branch 0 %. Describe calls per tick fell from median 13 / max 47 to
**median 3 / max 20**.

**Consequence for the omitted Stage 3a — mechanism right, consequence wrong.** A tick-scoped memo
keyed on quantised `(x, z)` is mechanically *not subsumed* (it is the only thing that collapses two
different contacts in the same cell). But measured, there is almost nothing left for it to collapse:
**189 describe calls against 187 distinct 50 m cells — 2 redundant, 1.1 %** (800 objects: 325 calls,
320 cells, 1.5 %). Stage 3b already absorbed BL-B26's 3× same-contact multiplier; the residual is
distinct positions. **3a is not worth building**, and reasoning from the mechanism alone pointed the
other way — this is why the in-situ count has to be taken before sizing a fix.

**Trap for anyone re-running the note's diagnostic:** `distinct_positions == describe_calls ==
cache_misses` **still holds in 37/37 callout-bearing ticks** and no longer means what it meant.
Before it held *with zero hits* (the cache did nothing); now each miss is a genuinely new cell. The
discriminator is the hit count beside it, never the equality alone.

**The remaining tail is not body-layer's.** `describe_position` is ~57-85 ms per call on
`syria-full.sqlite` and costs the same cold-distinct, repeated, 1 m apart, or within one cell — no
internal memo, no I/O warming. A hit saves the full unit cost; the grain only decides how often one
is available. Further tail work belongs in `query.describe`.

**Staleness axis the constant's comment misses:** it bounds error at the cell diagonal and names
`describe_position`, `relative_geometry`, `terrain_divide_qualifier` — but a hit also freezes the
cached `world_position`, and `_terrain_aware_world_position` takes its fixed-point **observer**
from the most recent contributing `Percept`. Under exact equality a hit implied no new percept;
under a 50 m cell it does not, so the quantisation widens staleness along the observer axis too.
Unquantified; the instrument is one diff of cached vs freshly-computed `world_position` on hits.

Related: [[project_divides_between_and_group_tick_multiplicity]].
