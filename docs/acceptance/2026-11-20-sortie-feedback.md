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

## Mode 1 flight, `main` @ `a8b21de0` (user, verbatim)

> In mode 1: "turn right 50" -> turns but does not use pedals at all. Use pedals. All the axis are
> interdependent in helicopter flight. Use then all to maintain desired state.
>
> There is a slight bank when taking controls, but it nicely stabilizes to ~0 now.
>
> Mode 1 break turn banks steep, good.
> then too slowly pulls cyclic back -> do it faster.
> but pulls too much cyclic and speed drops fast-> less cyclic back.

- Take: the pedal-drift fix works (slight bank, settles to ~0).
- Break: bank good; the back-cyclic comes in too slowly, then too much, and speed bleeds off.
- Turns: no pedal at all. The pedal law has no slip-ball term (never probed) and no
  turn-coordination term; the only pedal inputs are the collective feedforward (now gated off,
  collective disabled) and the break bias.

Decisions (asked: enable collective; pedal into the turn plus a later slip-ball probe; tune the
pitch response via an M0-E probe or by feel), verbatim:

> 1 - absolutely yes. Now.
> 2 - yes
> 3 - cancel, add collective control first, then I'll retest

- Collective is written in mode 1 (`FC_AXES_ENABLED.collective = true`), in this batch.
- Turns get a pedal coordination term proportional to turn rate, in this batch; a slip-ball probe
  flight comes later so the ball can be centred properly.
- No pitch-loop tuning now: the user retests the break with collective on first.

> we need a to read the slip ball as one of the important values since it guides pedal adjustmens.

Slip ball moves from "later probe" to now: read it, report it on the flight-control status line
so a flight can calibrate its sign/units, then use it for pedal (ball-centring) feedback.

## Mode 2 → mode 1 handover crash, `main` @ `a8b21de0` (user, verbatim)

> In mode 2 I commanded from speed 0 to 200, AI accelerated.
> I changed to mode 1 -> controls fixed at what they were, no corrective movement -> crash as bank
> kept increasing.
> On change to mode 1, mode 1 must keep flying the set targets from mode 2 (heading, speed, alt).

Expected: on the unpark take, mode 1 actively flies (the control law runs from the first frame,
corrects attitude), with its heading/speed/altitude goals seeded from mode 2's set targets (the
overlay's set course/speed/alt), not from whatever the aircraft happened to be doing.

## After the batch: pedal fact and one desired state for both modes (user, verbatim)

> As collective increases, more right pedal is needed.
>
> Mode 2 > 1 change:
> Mode 1 to pick what player has commanded. The AI wheel probably shows it, but if mode transition
> is mid param adjust on AI wheel then AI wheel ha incorrect value. There should be a unified state
> of desired params that both modes use, mode 2 just has more limitations.

- Pedal: more collective → more right pedal, an aircraft fact from the user. The
  collective→pedal feedforward and the turn pedal both assume positive pedal command = right,
  which is still unmeasured. The M0 findings say pedal arg 1103 positive goes with positive yaw
  rate, so the mapping can be settled from DCS's yaw-rate sign convention plus the slip-ball
  flight, rather than guessed.
- Unified desired state: the unpark seed built tonight reads the AI wheel's displayed set values,
  which are wrong mid-adjustment (the wheel is still ramping toward the commanded value). Direction:
  one body-layer-owned desired heading/altitude(+reference)/speed, set by the player's commands;
  mode 2 drives the wheel toward it (within the wheel's limits), mode 1's law flies it directly, and
  a mode change hands over the desired state, never the wheel's display. Recorded as BL-16 work.
