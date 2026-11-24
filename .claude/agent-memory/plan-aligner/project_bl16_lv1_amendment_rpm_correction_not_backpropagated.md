---
name: bl16-lv1-amendment-rpm-correction-not-backpropagated
description: BL-16 LV-1 amendment, a same-day correction box inside a plan section did not reach text written above it in reading order (header, decision paragraph, a "no new telemetry needed" claim) — a scoped correction needs grepping forward AND backward.
metadata:
  type: project
---

LV-1 amendment (`plans/flight-lift-vector/plan.md`, "LV-1 amendment (2026-11-24, fourth re-fly)",
section C): the main loop added a dated correction box mid-section switching the collective-rate
gate from rotor RPM to **engine** RPM (args 40/41/838/839), after the user's cockpit readings
showed the two move in *opposite* directions (spooled-down engines at 74% coincide with the
*highest* rotor RPM, 100%). The box says "wherever the text *below* says RPM, read engine RPM" and
explicitly calls out diagram 2 (located *above* the box, earlier in the document) as covered too.

But three other passages, also above or around the box, were never touched and still assert the
old (wrong) reading: the section's own header ("...the rotor-RPM-gated schedule"), the "Decisions
answered" Q1 paragraph ("Built as a rotor-RPM-gated... reading the existing
`read_rotor_rpm_pct()`"), and "What reading the code turned up" point 2 ("no new telemetry needs
inventing — this is the calibration flight that reading was always waiting for") — which directly
contradicts the correction, since the corrected design *does* need a new read (engine args) no
cited function covers.

**Why:** a scoped "read X as Y" correction note, placed mid-document, only reliably covers the
text physically after it unless the note itself names every earlier passage it also overrides — and
even an explicit callout of one earlier passage (diagram 2) does not imply the others were checked.
Caught by grepping every occurrence of "rotor RPM" / "engine RPM" across the *whole* amendment
section, not just reading forward from the correction box.

**How to apply:** whenever a plan carries a same-day correction note that changes what an earlier
design decision means, grep the full section (and anything it summarizes, like a "decisions
answered" recap) for the corrected term — both directions, not just the text visually below the
note — before marking the expectation it serves as cleanly met. A near-identical case:
[[project_lift_vector_u8_floor_removed_but_not_grepped_everywhere]] (a removed floor left stale
references elsewhere in the same plan).
