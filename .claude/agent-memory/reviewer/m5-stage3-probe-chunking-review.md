---
name: m5-stage3-probe-chunking-review
description: M5 Stage 3 elevation/surface_type probe review — checklist-mandated timer.scheduleFunction chunking was silently dropped, and implementation.md misdescribed the resulting code as "append-mode"
metadata:
  type: project
---

M5 Stage 3 (`plans/m5-first-persistent-model/`, commits `6fd853d`..`e9eede5`) was reviewed and
approved with one required fix. Grid coverage (1,681/1,681 for elevation + surface_type) and the
SRTM-null-is-honest claim were both verified directly against the real
`data/world-model/latakia-20km.sqlite`, not just trusted from the report — both checked out true.

The one required fix: `checklist.md` and `plan.md` Finding E explicitly mandate
`timer.scheduleFunction` self-rescheduling chunking + true append-mode `io.write` for the DCS
probe scripts, specifically to avoid the busy-wait-hangs-DCS failure mode at larger point counts.
All three `terrain_probe_{smoke,500,full}.lua` scripts instead copy M4's `elevation_probe.lua`
single-blocking-loop pattern verbatim (`io.open(..., "w")` once, one `for` loop over the whole
rung, close at the end) — up to 1,681 points × 2 blocking calls in one unscheduled loop.
`implementation.md` describes this as "append-mode `io.write`", which is not what the code does
(opens `"w"` not `"a"`, no chunking across scheduled ticks). It happened not to hang in practice,
but the report's description of the mitigation being in place was simply wrong — this is a
report-vs-code mismatch, same class as [[feedback_transform_confidence_verification]], just
surfaced by an explicit checklist mandate this time instead of a confidence-label claim.

**Takeaway for future probe/script-generation reviews in this project**: when a plan/checklist
names a specific mechanism (e.g. "must use X pattern, not Y") for a stated failure-mode reason,
grep the actual script for that mechanism (`scheduleFunction`, file open mode) rather than trusting
the implementation log's prose description of what pattern was used — the log can accurately cite
a *precedent* ("mirrors elevation_probe.lua's pattern") while still contradicting an explicit
newer instruction that was supposed to supersede that precedent for this stage.
