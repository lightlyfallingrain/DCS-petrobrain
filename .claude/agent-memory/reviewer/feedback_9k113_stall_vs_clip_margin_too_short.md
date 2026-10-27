---
name: 9k113-stall-vs-clip-margin-too-short
description: When reviewing a 9K113 AI-axis probe that distinguishes a "stall" (axis gate) from a true field/gimbal clip by a short time-based margin, check the margin against the documented gate-window durations before trusting the design
metadata:
  type: feedback
---

The 9K113 AI-axis has a documented intermittent command gate (cause unknown) that drops commands for
4-18 seconds at a stretch, and for an entire flight in at least one observed run
(`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`, runs 6-8). Any probe that distinguishes "the
mark stopped because it hit a real field/gimbal edge" from "the mark stopped because the gate ate the
command" using a short time-based margin (e.g. 3 seconds) is vulnerable to misreading a gate onset at
the very start of a seek as a confirmed plateau at/near the starting position (often ~boresight), not
the true edge — because 3 s is shorter than nearly every documented gate window.

**Why this matters for review, not just this one probe:** a multi-cycle consistency check (repeat the
sweep N times, compare plateau values) looks like it defends against this, but it does **not** if the
gate itself can be flight-duration (run 8) — every cycle would then plateau at the same wrong value
and read as "CONSISTENT (real clip)", a confidently-wrong result with no signal to the human reading
the summary that anything is off.

**What to check, concretely, on any future 9K113 slew/clip-measurement probe:**
1. What is the stall/clip discrimination margin, in seconds?
2. Does it exceed the documented gate windows in `docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`
   runs 6-8 (4-18s typical, up to flight-duration observed once)? If not, flag it.
3. Is there any signal (travel-from-start sanity check, or a flag distinct from "plateau confirmed")
   that would let a human reading the log tell a gate-stall from a true edge, given the consistency
   check alone is not reliable against a flight-duration gate?

This caught a real required-fix on `probe/9k113-hud-elevation-limits` (2026-10-27) before the flight
ran, rather than after a wrong `ASP17_FIELD_EL_HALF_DEG` got set from a confidently-wrong "measurement."

See also [[project_recurring_field_of_regard_enforcement_gap]] — same subsystem, a different
recurring defect shape (field-of-regard enforcement, not stall detection), but the same lesson that
this sight's intermittent-gate behaviour keeps surprising designs that assume it is rare or brief.
