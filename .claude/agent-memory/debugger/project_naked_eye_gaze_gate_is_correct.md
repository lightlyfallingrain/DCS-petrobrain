---
name: naked-eye-gaze-gate-is-correct
description: perception/visibility.py's Gate 0 (gaze) and gaze.py's per-sector o'clock legs are correctly narrow (15deg half-width) -- verified 2026-09-25, not the source of an off-gaze callout.
metadata:
  type: project
---

Verified by reading (not just skimming) `perception/gaze.py` and `perception/visibility.py`:
`check_visibility`'s Gate 0 (`within_gaze`) runs first, unconditionally, for the naked-eye channel.
A commanded `scan right` resolves to `ScanPlan.commanded_sector="right"` -> `_SECTOR_LEGS["right"]
== (1, 2, 3)`, cycled by `gaze_at` through a narrow `FOCUS_CONE_HALF_WIDTH_DEG = 15.0` wedge --
never anywhere near 10 o'clock. `gaze_for`'s peripheral bypass (`stimulus_ids`) is a confirmed
no-op today (always an empty `frozenset` -- the attention-capture channel doesn't exist yet).

So a candidate outside the commanded cone genuinely cannot be admitted by the naked-eye channel.
`perception/hybrid_source.py` (HelperAI/`LoGetWorldObjects`) has zero gaze awareness at all, but
always emits `classification_level=3` (type-specific), so it can't explain a presence-level
("ground") callout either, unless a contact's folded classification was separately collapsed by a
classification contradiction (check `belief/classification.py`'s lockout before assuming this).

If an unprompted contact callout reports something outside the current commanded gaze, look at
`_WATCHED_ONLY_KINDS` / `CONTACT_RANGE_CROSSED` first -- see
[[project_watch_report_sounds_live]] -- before suspecting this gate.
