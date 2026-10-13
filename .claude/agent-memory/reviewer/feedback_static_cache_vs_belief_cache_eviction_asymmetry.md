---
name: static-cache-vs-belief-cache-eviction-asymmetry
description: When a new memo is told to "mirror" an existing belief-layer cache's cell-key arithmetic, check whether the thing being cached is static data (never needs eviction) or a derived belief fact (must be bounded by the thing it's keyed on) -- the two caches can look structurally identical and have opposite correct eviction policies.
metadata:
  type: feedback
---

On `plans/forest-occlusion/plan.md` Stage 1, the plan told the implementer to mirror
`belief.enrichment.WorldEnrichmentCache`'s `ENRICHMENT_CACHE_POSITION_GRID_M` cell-key arithmetic
for a new `ForestOcclusion` memo. The implementer did exactly that for the key arithmetic, but the
new cache is keyed on the cell itself (`dict[tuple[int,int], bool]`), not on a bounded identifier
like `contact_id` the way `WorldEnrichmentCache` is (`dict[str, ...]` keyed on `contact_id`,
overwriting its own entry on every update).

**Why this is not automatically a defect, and why it's easy to flag as one anyway:** the two caches
differ because what they cache differs. `WorldEnrichmentCache` holds a *derived belief fact* about
a live contact (world position, semantic facts) that goes stale as the contact moves and must be
recomputed per contact-position-cell — its size is naturally bounded by the belief layer's live
contact count, which the belief lifecycle already caps. `ForestOcclusion` holds a *static spatial
fact* (is this fixed location inside a forest polygon) that never goes stale at runtime — landcover
doesn't change mid-sortie. So never evicting is the *correct* policy for `ForestOcclusion`, not an
oversight; the thing that bounds `WorldEnrichmentCache`'s size (contact lifecycle) has no analogue
here because there's no "this entry is now wrong" trigger to act on.

**How to apply:** before flagging an unbounded dict cache as a memory-leak risk, ask what
invalidates an entry. If nothing does (the cached fact is a function of static world data, not of
a live, decaying belief object), unbounded-by-key-space is fine as long as the realistic key-space
size for this project's actual session lengths (single-player, hours not days, per-process) is
small — here, a few thousand 50 m cells at most. The finding worth recording is not "add eviction"
but "the docstring should say this is a static-data cache so a future reader doesn't 'fix' it
toward the bounded-by-contact-count shape, which would be the wrong model for what it holds."

See [[feedback_bounded_magnitude_isnt_optional_severity]] for the adjacent but distinct lesson
(a measured magnitude, not just a mechanism, decides severity) — this is the same discipline
applied to cache-eviction review specifically.
