---
name: group_collapse_units_hi_inf_latent
description: CardinalityBelief.hi can be math.inf (OP_MORETHAN15UNITS/UNKNOWN buckets); group_view sums it unguarded into CollapseNode.units_hi, latent not exploitable yet
metadata:
  type: project
---

`belief/cardinality.py`'s `OP_MORETHAN15UNITS` and `UNKNOWN` buckets both declare `hi = math.inf`
by design (open-ended "more than 15 units" / "no claim" shapes). `belief/group_view.py`'s
`_units_hi` (`plans/group-collapse/plan.md`, merged 2026-10-13) sums `member.cardinality.hi`
across every member in a bucket with no guard, so `CollapseNode.units_hi` — and every ancestor's,
summed up the tree — becomes `math.inf` whenever any contributing member holds one of those
buckets. `tools._collapse_node_to_dict` passes it through unguarded into
`facts["group"]["tree"]`.

**Why this was rated low-risk, not blocking, in the group-collapse deep analysis
(`plans/group-collapse/security-review.md`):** no current consumer does `int()`/`math.floor()`/
`round()` on `units_hi`, and no current serialization path strict-JSON-encodes this particular
dict — `console.py`'s `show <id>` renders it via an f-string (prints the literal text `inf`, no
crash); the only `json.dumps` reachable from belief state (`brain_client.py`'s escalation payload)
carries a different, already-int figure (`_estimated_units_lower_bound`), not this tree.

**Why it is worth re-checking, not re-deriving, the next time `units_hi` grows a consumer.** This
project has fixed the exact shape of defect this resembles — an unguarded non-finite float reaching
an integer conversion or a strict serializer — three times in one day elsewhere in body-layer
(`position_belief.py` ×2, `perception/forest.py` ×1, see
`[[forest_occlusion_nonfinite_position_crash]]`). The difference here: those were NaN/inf reaching
`math.floor`/`int()` directly; this is inf sitting in a float field with no current arithmetic
consumer, so the defect is dormant rather than live. **Before approving a future feature that reads
`CollapseNode.units_hi`/`units_lo` arithmetically or serializes `facts["group"]["tree"]` through a
strict encoder (a candidate: any future brain-layer HTTP surface for this fact), check whether that
consumer guards `math.isfinite` first** — it was flagged as a one-line docstring note to add, not
required as a code fix, because guessing at a representation policy (cap? keep inf? render "15+"?)
ahead of the attention-tier milestone that actually consumes this field would be inventing scope.
