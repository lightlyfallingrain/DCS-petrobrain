---
name: readback-classes-poll-vs-read-at-need
description: User rule (2026-10-24, BL-B90 Stage 4) — poll only the few cockpit args code needs continuously; sequence/effector switches are read once at need (trigger fire), never added to a polled set that grows with switch count
metadata:
  type: feedback
---

Cockpit readback has two classes, and they must not be merged into one watched set. **Continuous**
is a small fixed set of code constants (886/898/960 today), polled at the 5 Hz tick. **At need** is
everything a sequence or effector touches, read once when its trigger fires: a synchronous one-shot
read through the collector, re-read after a wait row. Writes are then assumed to succeed.

**Why:** the user rejected my first spec, which made the polled set the union of every
sequence-file arg: *"the number of switches that we use will increase. Also the sequences can flip
any switch. Most of them we really only need a few times per flight"*. Offered A (write and assume
success, drop the already-set skip) or B (read once at fire, keep the skip), they chose B. My
"8 reads at 5 Hz cost nothing" argument was true today and wrong about the growth the user had in
mind.

**How to apply:** when a feature needs some piece of cockpit state, first ask whether code reads
it continuously (then it joins the fixed polled set) or only at a decision point (then it is a
one-shot read at that point). Size a design against the stated growth, not today's count. A
one-shot read that fails must never blind-write a non-absolute effector (toggle/button); only
`default_2_position_tumb` is confirmed absolute. See [[readback-consumer-rate-audit]].
