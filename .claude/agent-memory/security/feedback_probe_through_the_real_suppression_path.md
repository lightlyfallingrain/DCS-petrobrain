---
name: probe-through-the-real-suppression-path
description: A repetition/flood probe that omits the consumer's own suppression check inflates every count; drive the gate, not just the renderer.
metadata:
  type: feedback
---

When sizing a repetition or denial-of-attention hazard, **drive the consumer's actual suppression
gate, not the renderer alone.** My first two probes on `BL-B47` called
`render_group_disclosure` + `mark_group_spoken` and counted lines — and reported 10 identical
`"Now leading: short range SAM."` lines in 10 ticks. The scheduler would have emitted **one**: it
checks `content_signature == belief_group.last_spoken_signature` and `continue`s
(`belief/callouts.py:1190`, again at `:1221`). Both probes were discarded.

**Why:** a renderer is allowed to be repetitive; the gate is what decides what the pilot hears. A
probe that stops at the renderer measures a function nobody listens to directly, and it fails in the
*alarming* direction — it manufactures a blocking finding out of a suppressed one. The published
review of this same fix showed the same shape of numbers without showing the gate applied, so this
is not a one-off trap.

**How to apply:** before counting anything on the speech path, grep the consumer for the suppression
it applies (`last_spoken_signature`, `_last_spoken_signature`, membership snapshots) and replicate
the whole sequence. Then measure **two** rates, per
[[project_bl_b47_air_defence_class_level_security]]:

- the **steady state** — no fault injected at all. This is the number the rating depends on, and it
  is the one a failure-mode story never produces.
- the **pre-fix vs post-fix** pair in the same configuration. If they are equal, the change is not
  what creates the hazard, whatever the mechanism suggests.

Two further instrument notes from the same pass, both of which cost a probe:

- **Check the line actually fired through the mechanism under test.** One probe's SAM line came via
  `leader_changed`, not the air-defence predicate, so pre- and post-fix were identical and the probe
  proved nothing about the fix. Print the text, not just the count.
- **A fixture that yields 0 lines everywhere is broken, not reassuring.** Instrument group
  membership and the branch taken before concluding a hazard is unreachable.
