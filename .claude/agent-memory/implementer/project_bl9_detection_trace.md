---
name: project_bl9_detection_trace
description: BL-9 detection-trace implementation -- mutable-trace-entry annotation pattern, the ground-truth/belief join module, and what was verified without live DCS
metadata:
  type: project
---

Implemented on `feature/bl9-detection-trace`, not merged. Instrumentation, not a new mechanism:
`visibility.check_visibility` already short-circuits on the first failing gate, so the trace
records what that control flow already decided.

**Mutable-record annotation pattern**: `perception.detection_trace.DetectionTrace` is
deliberately *not* frozen. `check_visibility` records one entry per candidate per poll at
whichever gate fired; `NakedEyePerceptionSource.poll` later mutates that *same* entry in place
(via `DetectionTraceCollector.annotate_admission`, keyed on a `_last_by_object_id` dict) once
clustering/emission have happened. This is the first place in body-layer a record is written by
two different call sites over one poll's lifetime -- every other dataclass in this codebase
(`Observation`, `VisibilityResult`, etc.) is frozen-and-constructed-once.

**Uniform row shape over strict laziness**: `range_threshold_m`/`threshold_bound` are computed
unconditionally in `check_visibility`, even before the cockpit-mask gate runs, so every trace row
(including a `COCKPIT_MASK` failure) has the same shape. This is a real, deliberate departure
from "eagerly compute nothing extra when trace=None" -- justified only because the extra cost is
one dict lookup + one `min()`, and because a duplicated traced/untraced code path would have been
a much larger and more error-prone diff. The behavioral-equivalence test is what actually backs
this judgment call, not the reasoning alone -- see `test_trace_sink_does_not_perturb_...`.

**The ground-truth/belief join module** (`detection_trace_writer.py`) resolves `Contact` ids by
scanning `Contact.contributing_observation_ids` across `store.contacts` for a matching
`observation_id` -- there is no public `observation_id -> contact_id` accessor on `ContactStore`
(`_observation_id_to_contact_id` is private), so this is an `O(contacts x history)` rebuild every
poll. Accepted for a single-sortie debug artifact; would need a real index if this ever became
standing infrastructure.

**Verified without live DCS**: per [[feedback_full_build_execution]]-class rules (never run a real
live/full pipeline yourself), used `replay.py` over the committed `telemetry_frames.json` fixture
plus synthetic world-objects to generate a real JSONL trace and ran the reducer against it --
confirmed the reducer's two tables (first-admitted-range, never-admitted-but-in-FOV) work on real
generated data, but real-sortie volume/pacing is still unverified. This is the correct middle
ground when "verify on real data" collides with "never execute the real live pipeline yourself":
synthetic-but-real-code-path data beats neither.

Two decisions the plan flagged were picked (not user-confirmed, logged as open in
`plans/bl9-debug-visualization/implementation.md`): trace-only (no live view), and a 5-poll flush
cadence with no default `--detection-trace` path (explicit path required, matching
`--mission-understanding`'s convention).
