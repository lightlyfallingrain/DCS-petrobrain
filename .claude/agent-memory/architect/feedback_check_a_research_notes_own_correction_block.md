---
name: check-a-research-notes-own-correction-block
description: A research note's later CORRECTION block can refute a premise the dispatching brief and three roadmap entries all repeat as settled — read the note's corrections, not just its findings, before planning on a cited claim
metadata:
  type: feedback
---

When a plan's premise cites a research note, **read that note's own later CORRECTION/amendment
blocks before planning on it** — not only the finding the brief quotes. A note that has been
corrected still reads as authoritative in the section the correction invalidated, and downstream
documents quote the pre-correction version.

**Why:** On the `BL-B66` planning pass (2026-10-15) the dispatching brief, `BL-B66.md`, `BL-B63.md`
and `plans/9k113-sight/plan.md` §15c **all four** stated that pointing the 9K113 requires a closed
rate loop, making `BL-B63`'s fast lane a hard correctness dependency, with a proportional controller,
an empirical deadband and a Windows probe to size it. `aircraft-layer/research/mi24p-command-surface.md`
§4.1.2 and its **CORRECTION of 2026-09-21** had already measured the AI axis (3060/3061) live at five
points as an exactly linear *position* target settling in 0.25 s — *"pointing is a single write — no
closed loop"* — and said of the rate axis *"do not use it as an effector"*. The same note records
that generalising between those two channels **already cost this project two probe flights**. The
note's §4.2 still carries the pre-correction paragraph ("the axes are velocity, not position")
directly below the correction, which is how four documents inherited the wrong half.

**How to apply:** `grep -n "CORRECTION\|SUPERSEDED\|Amended" <note>` before citing any of its
findings. Then separate *what the user described* from *what our implementation must do* — the user's
§12 ("the copilot slews with a rate joystick") was entirely true and simply did not select our
command channel, which the roadmap entry had itself flagged as open. Distinguishing those two let the
premise be corrected without contradicting a word of the direction. Pairs with
[[find-n-in-the-repo-before-accepting-n-is-unknown]]: the same pass found the "unknowable" maximum
slew rate published in DCS's own `Devices_specs/9K113.lua` (20°/s az, 10°/s el).
