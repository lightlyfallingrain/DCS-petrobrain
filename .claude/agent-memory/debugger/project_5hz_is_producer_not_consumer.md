---
name: 5hz-is-producer-not-consumer
description: "objects arrive at 5 Hz" in perception/motion.py is the aircraft-layer Export.lua producer rate, not body-layer's 1.0 s poll — correct as written, flagged as a defect twice
metadata:
  type: project
---

`perception/motion.py`'s `MOTION_VELOCITY_MAX_SKEW_S = 2.0` comment ("objects arrive at 5 Hz,
velocity at 1 Hz") is **correct and not a mis-calibration**. Verified 2026-10-06 against the
installed Lua, not against the plan that quotes it:

- `aircraft-layer/dcs-export/Export.lua:143` — `EXPORT_INTERVAL_S = 0.2` (5 Hz), gates the
  `LoGetWorldObjects` send at `:881`.
- `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua:91` — `POLL_INTERVAL_S = 1.0`
  (1 Hz), gates the velocity send.

**Why:** both numbers describe the *producers*. The skew the bound guards
(`naked_eye_source._resolve_velocity_by_object_id`) is
`|world_objects_t_sim − unit_velocity["dcs_model_time_s"]|` — a difference between two producer
sim stamps, so body-layer's own `_DEFAULT_POLL_INTERVAL_S = 1.0` cannot enter it at all. `BL-B30`
and `BL-B34` have each read this comment as a claim about the poll loop and filed it as a defect;
the comment now carries its own provenance so a third pass does not re-derive it.

**How to apply:** on this project, a rate in a docstring may be describing either side of the
aircraft-layer HTTP seam. Before concluding a constant is mis-calibrated against the tick rate, ask
*which clock the compared quantities are stamped by* — if both stamps come from DCS-side exporters,
the consumer's poll rate is irrelevant. Same family as the performance-reviewer's finding that there
is no 5 Hz spec in body-layer at all: the only 5 Hz in this system is `Export.lua`'s.
