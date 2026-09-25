---
name: scan-area-watch-conflation
description: scan_area used to register a "watch"-level AttentionArea, silently enrolling every scanned contact into watched-only callouts; fixed to "normal".
metadata:
  type: project
---

`belief/tools.py::scan_area` (body-layer) used to call `store.add_area(...,
level="watch", ...)` -- the same level `watch_area` defaults to -- so any
contact geometrically inside a *scanned* area (not a deliberately *watched*
one) became eligible for `belief.callouts._WATCHED_ONLY_KINDS` reporting
(`CONTACT_MOTION_CHANGED`/`CONTACT_RANGE_CROSSED`/`CONTACT_ENGAGEMENT_
CHANGED`). Fixed 2026-09-25 (`plans/scan-is-not-watch/debug.md`) by changing
`scan_area`'s registered level to `"normal"`.

**Why the fix was safe to make without an architecture pass**: neither
`belief/tasks.py` (`area_contains` only) nor `logger.py::_active_gaze`
(reads `relative_sector`/`relative_clock_hour`/`sector` only) ever reads
`AttentionArea.level` -- it has exactly one behavioural consumer,
`belief.attention.effective_attention`, which only the callout/report
family reads. Before touching `.level` on either `scan_area` or `watch_area`
again, grep for `.level` consumers first -- this is the check that made the
one-line fix low-risk.

**A live-observed "motion callout fires for out-of-sight units" symptom did
not need a second fix.** `Contact.motion.state` can only change via `belief.
motion.fold_motion`, called only from `Contact.record` during `ingest`, and
`perception/naked_eye_source.py` only computes `apparent_motion` for
candidates that passed `check_visibility`'s gaze gate *that same poll*. A
motion state transition is therefore structurally impossible without
contemporaneous witnessing -- the observed symptom was fully explained by
the scan/watch conflation above (scan swept up far more contacts than the
player ever deliberately watched). Don't add a freshness gate to `CONTACT_
MOTION_CHANGED`'s emission without first reproducing a case this reasoning
doesn't cover.

See also [[project_watch_report_sounds_live]] (the sibling finding that
`CONTACT_RANGE_CROSSED`'s wording is itself ambiguous between a live
sighting and a memory-based update -- still open, deliberately not touched
by this fix).
