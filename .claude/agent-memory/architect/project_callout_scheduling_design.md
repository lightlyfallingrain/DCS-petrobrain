---
name: callout-scheduling-design
description: Callout scheduling/aggregation design (2026-09-22) — speech occupancy modelled in sim time, two distinct groupings that must not be unified, threat-band placeholder shape
metadata:
  type: project
---

The 2026-09-21 cones 2C sortie produced two linked speech findings, planned together in
`plans/callout-scheduling/plan.md`. Three decisions there are worth not re-deriving.

**Speech occupancy is modelled in sim time from the text, never signalled by real playback.**
**Why:** the playback queue lives in `aircraft-layer/src/collector/audio_sender.py`, two HTTP hops
from body-layer, on the Windows box. Any completion callback is wall-clock timed, absent when
`--speech-audio` is off, and unreproducible under replay — which breaks body-layer's hard
"replayable from a recorded stream" requirement. So `busy_until_sim = now_sim +
estimate_speech_duration_s(text) + gap`, a pure function of the string.
**How to apply:** if a future slice is tempted to add a `/audio/status` or a done-callback, that is
the rejected design, not an oversight. Say why before reopening it.

**There are now two distinct groupings, and unifying them is a known trap.**
`perception.clustering` asks whether two live candidates are optically *resolvable apart*
(magnitude: one target width, ground-truth positions). Callout aggregation asks whether two
*reports* are indistinguishable to a listener (magnitude: the reporting quantisation — 30° clock
bucket, rounded range word, belief facts only). **Why:** this is the identical mistake Stage 3b-i of
the group-contact model already made and reverted — `belief/association_over_time.py`'s docstring
argues it out at length. Reusing `cluster_candidates` here would also drag ground truth into
`belief/`, violating `belief/percept.py`'s boundary.
**How to apply:** when anything in `belief/` wants "group these contacts", group in report space off
`describe_contact` facts. Cite `association_over_time.py`'s docstring rather than re-arguing.

**The threat-model placeholder has a shape, not just a TODO.** `callout_priority` returns
`(threat_band, -attention_rank, range_m, -event.t_sim)` with `threat_band` constant today.
`docs/concept/threat-levels.md` is filed and gated behind coalition inference; when it lands it
replaces exactly that first element. Attention and proximity are used as ordering keys because both
already exist as first-class signals (attention is already the "usefulness" gate for
`speech._cardinality_phrase(attended=...)`), not because they approximate threat.
**How to apply:** a placeholder ordering is acceptable in this project when the eventual real key is
a named, separable tuple element. Prefer that over "sort by recency and revisit later".

Related: [[project_bl2_contact_memory_design]], [[project_cones_slice2_design]].
