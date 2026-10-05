---
name: los-join-key-unit-name-not-total
description: X-B29's live LOS verdict joins on unit_name, which is None for scenery/statics, so nameless objects can never get a building-aware verdict and silently use the SRTM fallback forever
metadata:
  type: project
---

`perception/naked_eye_source.py:1066` `_resolve_los_by_unit_name` joins the DCS LOS snapshot onto
world objects by `unit_name`. `aircraft-layer/src/schema/world_objects.py:37-46` states that field is
`None` for scenery/statics. `isinstance(name, str)` is then False (line 1118), the candidate gets no
`live_los_clear`, and `visibility.py:785-790` falls through to world-model's **building-blind** offline
primitive with 12 m terrain slack — permanently for that object class, not as an outage.

**Why:** found in the 2026-10-05 whole-subproject audit, explaining the 2026-10-05 sortie's unexplained
"misses are closer" anomaly (no-verdict rows median 3,820 m vs with-verdict 6,750 m). Buildings/statics
are concentrated close in, and they are both the population that cannot be joined and the population
whose occlusion the feature exists to model. Deterministic, so it predicts the sign correctly where
truncation and producer-outage explanations did not.

**How to apply:** `DetectionTrace` (`perception/detection_trace.py:116`) carries `object_type` but not
`unit_name`, so this cannot be confirmed from an existing trace — adding `unit_name` + a `los_join`
reason enum is the verification step, not the fix. Second leg of the same defect: `name_counts[name] > 1`
(line 1120) drops both members of any duplicate-name pair, and unit names are mission-author text.
Check any future join between the `LoGetWorldObjects` export and the mission-scripting environment for
the same key-totality question — those two environments share no other identifier.

Related: [[project_dostring_in_numeric_splice_naN_clamp_gap]],
[[project_xb29_los_two_percent_d_splice_approved]].
