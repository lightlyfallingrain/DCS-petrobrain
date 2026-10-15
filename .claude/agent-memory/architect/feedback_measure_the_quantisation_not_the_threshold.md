---
name: measure-the-quantisation-not-the-threshold
description: when a change-detection threshold guards a quantised output, compare the two grains before tuning the threshold -- a threshold finer than the output's own vocabulary cannot do anything but re-fire
metadata:
  type: feedback
---

**Before accepting that a change-detection threshold is mis-tuned, compare its grain against the
grain of the thing it gates.** If the threshold is finer than the output's own quantisation, no value
fixes it — the comparison is structurally incapable of meaning anything, and the clause should be
deleted rather than retuned.

**Why:** `BL-14`'s attack-run cadence emitted on `text_changed OR angular_delta > 3.0°`. The spoken
vocabulary quantises at **10°** (elevation word gate — deliberately wide, direction §11), 30°
(o'clock sector) and 7.5°/5.0° (azimuth word rows). So the angular clause could only ever fire on
text that had not changed. Measured: **47 of 125** utterances in one sortie were byte-identical to
the one before (38%), driven mainly by elevation deltas of 4–9° against azimuth deltas as low as
0.09°. The brief framed the fix as *"compare the rendered utterance, not the believed state"* — but
the rendered-utterance comparison **already existed** as the first arm of the disjunction. The real
fix was to make it a veto and delete the other arm.

**How to apply:** whenever a plan touches an emit/suppress/change-detect rule, write down (a) the
threshold and (b) the coarsest quantisation step of whatever the rule gates — word tables, buckets,
enum levels, rounded phrases. If (a) < (b), the rule is not tunable and the plan should say so. This
generalises past speech: any `if delta > X: act` guarding a discretised output has the same defect
available to it.

Corollary, learned the same pass: **read the predicate before adopting a brief's fix shape.** Two of
the four items in that plan had their shape changed by reading the existing code first — this one,
and `", obstructed"`'s cause being already available as a tri-state on `Contact` with a documented
fail-open precedent two modules away. See [[find-n-in-the-repo-before-accepting-a-sizing-argument]]
for the sibling rule about numbers.
