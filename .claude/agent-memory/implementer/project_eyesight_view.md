---
name: eyesight-view-belief-truth-log
description: Real-time ASCII eyesight view + belief-truth-log consistency log — draw-order gotcha and test-collision gotcha
metadata:
  type: project
---

Built `body-layer/src/eyesight_view.py` (real-time top-down ASCII debug view, `--eyesight-view`,
default radius 5km per user correction mid-task) and `body-layer/src/belief_truth_log.py`
(`--belief-truth-log`, a ground-truth/belief consistency JSONL log with a stderr tripwire for
physically-impossible readings). Both additive/no-op-when-absent, wired into `logger.py` alongside
`--detection-trace`, sharing one `DetectionTraceCollector` with a fixed read-then-clear order.

**Range-0 rays silently hide a `set_if_blank` marker at the origin.** Any ray/cone trace that starts
its walk at `range=0` (a gaze centreline, a boundary ray) will draw through the observer's own cell
first. If the observer/ownship marker is drawn with `set_if_blank` *after* those rays, it never
shows — found only by rendering a sample frame and looking at it, not by any assertion-based test.
Fix: draw ownship unconditionally, positioned after background layers (rings/cone) but before
foreground markers (ground truth/believed), so a real marker at range≈0 still wins per draw order.

**A rendered legend/header line containing every marker's own vocabulary (e.g. "AA air defence, AR
armour...") makes `"AR" in frame`-style substring tests pass regardless of whether the canvas
drew anything.** Any test of draw order/clipping on a view with a legend must scope to the canvas
lines only (`frame.splitlines()[2:]` or similar) or assert an exact computed cell — a plain substring
check is a false-pass trap specific to self-documenting ASCII views.

**`PRESENCE_CLASS` and `DEFAULT_OP_CLASS` are the same literal string** (`belief.classification`) —
a presence-level contact's classification *value* cannot be told apart from "cluster degraded to the
group root" by string alone. Any short-label/group-detection feature reading classification should
use an independent field (here: `Contact.cardinality.lo > 1`) rather than trying to read "group-ness"
off `classification.value`.

Reused `detection_trace_writer.py`'s ground-truth/belief join (`observation_id_to_contact_id`, made
public from `_observation_id_to_contact_id`) rather than building a second one — the coordinator
explicitly asked for this, and it is the right general pattern whenever two debug/calibration tools
need the same belief↔ground-truth pairing.
