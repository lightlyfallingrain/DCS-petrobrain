# BL-16 sortie feedback (2026-11-20)

Flown on `main` at `98174b54` (after the handover-ack / wire-format fix), card
`docs/acceptance/2026-11-20-bl16-handover-ack-sortie.md`. User's words, verbatim:

> 1 - in mode 1 if not turning (=maintaining heading) bank angle should be ~0
>
> 2 - mode 2 first a small turn worked then left break worked, then any turn after that was
> acknowledged but nothing happened. on command to turn right 30, overlay stayed in CMBT when
> should have changed to FLT. Possible reason, if completion waits to reach *exact* desired
> value, that may never happen. Everyhing is imprecice.

Not yet explored with the user. Main-loop reading only:

- Item 1 implies that while holding a heading in mode 1, Petrovich flies with a standing bank,
  not wings level.
- Item 2: after a break, the AI wheel stays in CMBT, and every later goal is acknowledged and then
  never flown. The user's hypothesis: the break's completion test waits for an exact value that the
  imprecise sim never reaches, so the overlay never returns to FLT and the goal dispatcher stays
  blocked.

## Explore, 2026-11-20

- User rechecked in the cockpit: the overlay text is **"CBTM"** (the code's spelling). Rules out a
  mode-text mismatch as the cause of item 2.
- Code reading: the break's completion does not wait for a value (it finishes when its press
  releases). A later goal sees the mode is not FLT/HVR and taps short-left to cycle, up to 3 tries,
  then a 3 s cooldown, repeated. Open hypothesis: ED holds CBTM while the player is in the CPG/sight
  view (user's own note, `plans/flight-control/explore-notes.md`), so the cycle never wins.
- Item 1, code reading: there is no slip-ball term on the pedal (never probed), and a break's pedal
  bias is integrated into `t_y` and never unwound, so the heading hold can end up corrected by bank
  with crossed controls.

User answers, verbatim:

> Mode 1 control handover. Petrovich increased left pedal quite a lot -> left yaw -> bank right to
> compensate -> ends up maintaining heading with right bank (5 deg this time) and unnecessary and
> unwanted left yaw.
> Second control transfer ended up in 10 deg right bank and "unable, not ready" nut still taking
> controls.
>
> Mode 2: break left -> ok > break right -> ok > turn heading 060 -> acknowledget, but nothing
> happens. Not in CPG. No flicker.
>
> 3 in CPG mode as well, left press changes mode.

So: the sight-view hypothesis is out (not in CPG view, and short-left changes mode there too). No
flicker means the goal channel is not even trying to cycle the mode. Expected behaviour, now
unambiguous:

- Mode 1: a take adds no pedal of its own; holding a heading means wings ~level, ball centred.
- Mode 1: a take never ends in "unable, not ready" while Petrovich in fact holds the controls.
- Mode 2: a heading goal after a break cycles CBTM → FLT and is flown.

Continuation, verbatim:

> Mode 2, continuation. I changed mode to FLT myself, commanded "turn left 15" -> acknowledged, but
> nothing happens

So the mode cycle is not the blocker: even in FLT the goal is never pressed. The goal channel
itself is gated off after the breaks (or body-layer never sends it).

Live sample from that state: `apw_cbtm_status: "done"`, `apw_cbtm_seq: 2`, `apw_goal_seq: 0`,
`apw_goal_progress: "idle"`, mode FLT. CBTM finished cleanly; Lua had accepted no goal at all in
the mission. Main-loop lead: goal and CBTM messages checked against one shared seq high-water mark
while numbered independently.

User direction, verbatim:

> If that is the reason, all commands should really use a mission wide unique running number, not
> individual numbering.

> if body layer resets, it could send a reset signal. that would then reset the counters and reset
> state at aircraft layer too. then body and collector would match

Decision (asked: on a body-layer restart mid-flight, does Petrovich let go of the stick?), verbatim:

> yes let go. A service reset is error situation, that should not happen. If player manually
> restarts, he knows it then.

So the reset clears all of Lua's command state: mode 1 releases the axes (player has the stick),
mode 2's open goal/CBTM/HVRT is dropped (ED's AI keeps flying).

## Mode 2 root cause and the "latest wins" direction

Root cause (debugger, `plans/flight-control/debug.md` third report): body-layer's F-P7 rule
dropped every heading goal for the rest of the parked activation once any break had been sent, so
no goal was ever POSTed (`apw_goal_seq: 0`). Not a shared-seq problem: Lua checks each channel's
seq independently. The first fix bounded the drop to "while the break runs". User, verbatim, on
being told the rule stops a turn interrupting a running break:

> Why? If player commands anything during a break, act on it. Latest player command *always* wins.

Consistent with the original F-P7 answer (2026-11-18, *"yes, as proposed"*: a break supersedes any
**outstanding** heading goal, i.e. one set before it, which would otherwise turn the aircraft back
toward the threat). The implementation over-reached to goals commanded after the break. Settled:
a goal older than the break is superseded by it; a goal commanded during or after a break is flown
at once, ending any remaining break press (including break away's second press).

## Reset and single running number, user direction (verbatim)

> handle the reset. having individual channels and their numbers sounds error prone. I'd still
> prefer single running number. Not critical immediately, but should be done in BL-16

- Reset on body-layer start: built in this batch (clears Lua's command state; mode 1 lets go, see
  the decision above).
- One mission-wide running number for every command channel: BL-16 work, recorded on
  `body-layer/ROADMAP/BL-16.md`, not this batch.

## Desired value must be exact; flying may be imprecise (user, verbatim)

> desired values: I've said that a certain band is acceptable, holding a value need not be exact.
> However, the value *set* as desired must still be what player commanded. Actual flight is then
> allowed to deviate from it a bit, but the desired value must be correct.
>
> Now oberver "altitude 100 radar" -> alt set to 116 R. should set to 100. This was mode 2, but
> just as well the desired value must be correctly set in mode 1. Flying itself is allowed to be a
> bit imprecice.

Main-loop reading: `ai_pilot_wheel.lua` stops pressing once the overlay's *set* value is within
`AI_PILOT_ALT_TOLERANCE_M` (20 m) of the target, and within `AI_PILOT_HEADING_TOLERANCE_DEG` (5°)
for heading. The "acceptable band" is applied to setting the value, not to flying it. Expected:
the set value lands exactly on what was commanded (or the nearest value the wheel can show), and
only the flown value may deviate. Same for mode 1's goal values.
