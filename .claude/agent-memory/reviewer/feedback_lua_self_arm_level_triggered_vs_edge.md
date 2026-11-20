---
name: flight-control-lua-self-arm-level-triggered
description: A plan's "nothing re-arms until the next park edge" requirement needs an explicit edge flag in Lua -- a level condition (is_parked and fc_mode=="off") re-fires every frame
type: feedback
---

BL-16 desired-state Stages 1-2 (`plans/flight-desired-state/plan.md`, review-s12.md, 2026-11-20):
the plan says, in so many words, "After `reset(epoch)` while parked, `armed` is cleared and
nothing re-arms it until the next park edge." The implemented Lua
(`flight_control.lua`'s `run_flight_control`, the off→armed self-arm) is `if is_parked == true and
fc_mode == "off" then ... if lease_fresh then fc_mode = "armed" end end` — a level condition with
no tracked "was this already true last frame" flag. Since body-layer sends its lease
unconditionally every poll, the lease becomes fresh again within about a second of a reset, and
this branch re-arms Petrovich with no unpark/re-park having happened at all — confirmed by driving
the real module through `luajit` with a reset-then-fresh-lease-still-parked sequence.

**Why:** "X until the next edge" in a plan is an instruction to track the edge explicitly (a
`was_parked`/`armed_since_reset` local), not just to gate on the condition that happens to be true
at the edge. A level-triggered Lua branch that happens to only fire today because of *when* a test
calls it will silently start firing continuously once the surrounding system (here: a lease sent
every poll) keeps the gating condition satisfied. This project's Lua modules in this area
(`flight_control.lua`, `ai_pilot_wheel.lua`) otherwise track edges carefully (`fd_mode_n`,
`derive_cause` in `flight_desired.lua`) — this one branch is the exception, and it's exactly the
kind of thing that reads as correct from the code alone (the condition does describe "parked and
not yet armed") without running it.

**How to apply:** whenever a plan states an edge-only requirement ("until the next X", "only on
the transition", "not on every poll while Y holds"), find the Lua/Python branch that's supposed to
implement it and check for an actual edge-detection variable, not just the right-sounding
condition. If none exists, write the sequence by hand (reset → wait → let the surrounding state
recover → check nothing changed) and run it — reading the branch will not show this, since the
branch's *logic* is a correct description of "should be armed," just not of "should only become
armed on an edge."

Related: [[deleted-branch-drops-state-sync-not-just-speech]] (same review).
