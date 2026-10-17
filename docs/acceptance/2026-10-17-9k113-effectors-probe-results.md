# 9K113 effector probe — pilot's observations, 2026-10-17

Captured verbatim before any planning pass, per root `CLAUDE.md`'s "Flight feedback is captured,
then explored, then planned". Card: `docs/acceptance/2026-10-17-9k113-effectors-probe.md`.
Script flown: `aircraft-layer/dcs-export/Export.probe-9k113-effectors.lua`.

## The observations, in the user's own words

> *"probe pilot observation:*
> *- several swithces moved -> assume we can move all*
> *- warmup sequence is wrong. Let it be, we'll fix later. I can setup the warmup for now.*
> *- Driving the sight: needs a separate run WITH NO SWITCH FLIPS. I will setup it so that OBSERV
> is ON and can be used id it is possible via code. Set test to happen at T+60s"*

## What this settles

**Question 1 — ANSWERED, positive.** `performClickableAction` moves cockpit switches on devices 6
(`WEAP_SYS`) and 7 (`I9K113`), from the pilot's seat, against the *operator's* panels. Neither
device had ever been written to before this run. The user's own reading — *"several switches moved
-> assume we can move all"* — is the operative one: this is treated as a general capability, not a
per-switch question, and `BL-B66` Stage 2's switch sequence is buildable.

**The warm-up sequence as this probe wrote it is wrong**, and that is deliberate for now: *"Let it
be, we'll fix later. I can setup the warmup for now."* The probe threw five switches in brief order
with no regard for the real procedure's dependencies, which is enough to answer *can we write* and
not enough to answer *does the sequence work*. **Not a defect to chase before the slew question** —
the user sets up warm-up by hand in the meantime.

**Questions 2, 3 and 4 are not answered**, because the switch flips contaminated the run they
shared. They need their own flight.

## What the next run must be

**No switch writes at all.** Not reordered, not fewer — none. The user sets the aircraft up by
hand, OBSERV on, and the probe only reads switches and drives the sight.

**Starts at T+60 s**, his number, so there is time to complete the manual setup before anything is
measured.

Script: `aircraft-layer/dcs-export/Export.probe-9k113-slew.lua`, card
`docs/acceptance/2026-10-17-9k113-slew-probe.md`.
