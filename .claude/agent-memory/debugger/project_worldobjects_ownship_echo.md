---
name: worldobjects-ownship-echo
description: LoGetWorldObjects includes the player's own aircraft; any body-layer channel consuming it needs an explicit ownship-position exclusion or the ownship shows up as a phantom near-zero-range contact.
metadata:
  type: project
---

`LoGetWorldObjects` (aircraft-layer `GET /world_objects/latest`) is confirmed global/unfiltered
ground truth with no own-aircraft exclusion built in (per a primary-source forum thread cited in
`aircraft-layer/src/schema/world_objects.py`'s docstring: "in multiplayer it returns data from
all devices"). Any body-layer code that builds a candidate list from that endpoint and computes
bearing/range against `OwnshipState` will, without an explicit filter, occasionally treat the
player's own aircraft as a target: range collapses to ~0 (quantises to the smallest bucket if
the consumer buckets range), bearing becomes numerically meaningless (near-zero-baseline
`atan2`, jitters wildly poll to poll), and classification falls back to whatever "unclassified"
bucket the type-keyword table uses (own airframe type matches no keyword).

**Why:** This caused a real PB-1.5 bug (`plans/pb1.5-naked-eye-detection/debug.md`,
2026-09-09) — first live sortie produced a phantom `OP_GROUPSOMETHING` contact at a pinned
minimum range bucket with erratic bearing on nearly every poll. `naked_eye_source.py` and
`association.py` both independently built `WorldObjectCandidate` lists from the same unfiltered
snapshot with no exclusion. Fixed by `perception.association.exclude_ownship()` (drops any
candidate within `OWNSHIP_ECHO_EXCLUSION_RADIUS_M = 50.0` m of ownship's own position), called
by both `NakedEyePerceptionSource.poll()` and `HybridPerceptionSource.poll()` right after
building their candidate list.

**How to apply:** Any *new* consumer of `GET /world_objects/latest` in body-layer must call
`association.exclude_ownship()` on its candidate list before doing anything geometry-based with
it — don't rediscover this by tracing a new phantom-contact bug. If a future channel needs a
tighter or looser exclusion radius than 50 m, that's a local, reversible constant change, not a
redesign.

**Still open, needs live DCS** (not resolved by the 2026-09-09 fix): whether `LoGetWorldObjects`'s
`pairs()`-iteration key (`object_id`) is stable for the same physical object across polls. A
reproduction that session showed the existing per-object-id debounce works correctly *given* a
stable id, so this is an independent question from the ownship-echo bug, not a cause of it — but
worth resolving with a live capture before leaning on `object_id`-keyed debounce more heavily
elsewhere.
