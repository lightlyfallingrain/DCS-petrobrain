---
name: belief-truth-log-undersamples
description: dcs-belief-truth.jsonl only logs a row on a fresh naked-eye ADMITTED re-detection tied to a contact -- it is not a per-poll ContactStore dump, and will silently disagree with eyesight_view.py's live snapshot for any contact not being freshly re-admitted that poll.
metadata:
  type: project
---

`belief_truth_log.py::BeliefTruthLogWriter.write_poll` iterates `DetectionTraceCollector.records`
and writes a row only for entries where `outcome is GateOutcome.ADMITTED` **and** the observation
resolves to a contact via `detection_trace_writer.observation_id_to_contact_id`. Two consequences
that look like a contradiction if you don't know this:

1. A contact not being freshly re-detected by the naked-eye channel *this poll* (out of gaze cone,
   beyond `perception.visibility.NAKED_EYE_RANGE_CAP_M` = 10,000 m, masked) produces **zero** rows
   that poll, even though it is still live in `store.contacts`.
2. The scope/hybrid channel (HelperAI + `LoGetWorldObjects`) has **no** `DetectionTrace`
   instrumentation at all (`perception/detection_trace.py`'s own docstring says so) — a contact
   tracked purely by that channel never appears in this log, at any range, ever.

`eyesight_view.py`'s "believed" markers, by contrast, read `store.contacts` live every frame,
unfiltered by admission or channel. So a real sortie showed ~11 contacts at 11+ km in the ASCII
debug view while the belief-truth log for the same sortie had exactly one row beyond 10 km total
(a single-poll near-cap admission that tripped the range-cap tripwire, then was tracked on by the
untraced hybrid channel). Not a bug in either — they answer different questions. Before treating an
apparent mismatch between this log and any live-state view as a bug, check whether the log's
`ADMITTED`-this-poll join, not the belief itself, is the reason for the gap.

Also: `eyesight_view.py`'s printed `radius=` is `DEFAULT_RADIUS_M` (5 km), a **display canvas
scale**, unrelated to `NAKED_EYE_RANGE_CAP_M` (10 km) or `optic_policy.improvement_window_m`'s
binocular classification ceiling (1,750 m for a typical vehicle) — don't conflate the three when
reading a snapshot's footer.

See `plans/sortie-2026-09-26-fixes/diagnosis.md` for the full reconciliation and the two defects
this session diagnosed (crossing callouts firing for unseeable contacts; binoculars permanently
locked out for a contact after one command-interrupted look).
