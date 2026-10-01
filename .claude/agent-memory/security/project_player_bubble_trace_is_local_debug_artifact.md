---
name: player_bubble_trace_is_local_debug_artifact
description: PLAYER_BUBBLE detection-trace rows are a local-disk debug join, no network/belief path — checked, not assumed, for the player-bubble feature.
metadata:
  type: project
---

`perception.detection_trace.GateOutcome.PLAYER_BUBBLE` (body-layer, `feature/
player-bubble`, 2026-10-02) records that a ground/air unit existed at a given
range/bearing even though the 10 km player bubble excluded it from perception
entirely. This is the one place in that feature that writes down a fact about
something Petrovich deliberately did not look at, so it earned explicit
tracing rather than a skip.

Traced the full path: `DetectionTraceWriter` (`src/detection_trace_writer.py`)
appends JSON lines to a local file only, buffered a few polls at a time. Its
one read is a read-only join against `ContactStore.contacts` to resolve
`object_id -> contact_id` for diagnostics (`observation_id_to_contact_id`) —
it never writes back into `ContactStore`, `Percept`, or any `Contact` field.
No network path. `perception/` gains no import of `belief/` from this, and
`belief/` gains no import of this module — same no-omniscience boundary as
every other admitted-candidate trace row (which already carries far more
detail: tier, cluster membership).

**Why this matters beyond this one feature**: any future `GateOutcome` or
trace field that records something filtered *out* (not just what was
admitted) deserves this same check — confirm the trace stays a local,
read-only diagnostic artifact and never becomes an input to `belief/`,
dialogue, or any network-facing path. If a future feature ever makes the
trace file itself consumed by something other than offline tooling
(`tools/summarize_detection_trace.py`), re-open this question — the "almost
certainly fine" conclusion rests entirely on the write-only/read-only-join
boundary holding.

See [[project_los_terrain_tolerance_accepted_omniscience_trade]] for the
project's other reviewed omniscience-adjacent exception.
