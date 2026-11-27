# BL-16 mode 1 lift-vector law — explore notes

The user's founding words for this law are on `feature/bl16-desired-state-s34`,
`plans/flight-desired-state/explore-notes.md` ("Mode 1 control principles", the "lift vector can
never be known, only steered" note, "raw telemetry, what a pilot feels") and in
`body-layer/ROADMAP/BL-16.md` (lift-vector item, per-aircraft profile, rotor direction). Goal check:
`alignment.md` (this directory). Telemetry recon:
`aircraft-layer/research/2026-11-20-motion-telemetry-frames.md`.

## Answers to the goal check's questions (user, 2026-11-20, verbatim)

> 1 - remove the limit. Any speed. What does not work, I will bring back and we fix.
> 2 - speed
> 3 - it is usually ON. I'll write more about that in a moment.
> 4 - north/east velocity ?? If you mean that telemetry of x,y,z and a running delta on them would
>     allow calculation of position delta -> speed -> acceleration in 3D. That is approved.
> 5 - nose heading
> 6 - deliberate extra in hard turns

Settled:
- **Q1:** no minimum speed for the law; hover and low speed are in scope. The 80 km/h IAS hand-back
  goes. What fails in flight the user brings back and it gets fixed then.
- **Q2:** in an ordinary turn at the rotor limits, **speed gives first** (turn rate and altitude
  are kept as long as possible). Breaks keep the earlier answer: height gives within its 100 m
  budget.
- **Q3:** the SAU is usually on at handover; more from the user to follow.
- **Q4:** derive the 3D trajectory from the aircraft's own world position (x, y, z) over time:
  position delta → velocity → acceleration, world frame. This sidesteps the unconfirmed
  `LoGetVectorVelocity` horizontal axes; no separate probe is needed for them. The felt-load reading
  (`LoGetAccelerationUnits`) still serves lift length and coordination (goal check finding 1).
- **Q5:** hold nose heading in crosswind (drift with the wind), not ground track.
- **Q6:** in hard turns and breaks, a deliberate extra pedal into the turn beyond ball-centred; in
  ordinary flight the pedal centres the ball.

## Staging (user, 2026-11-20, verbatim)

> plan lift vector 1st stage without SAU. Go ahead with architecht.
> 2nd stage will use SAU.

So the first lift-vector stage neither uses nor depends on the SAU; using the SAU (usually on at
handover, Q3) is a second stage, planned once the user's SAU notes arrive.

## SAU in mode 1 (user, 2026-11-20, verbatim)

> # SAU in mode 1
>
> SAU has pitch, bank and heading stabilization channels. Each can be turned on/off by pilot (or
> Petrobrain regardless of seat).
> Mode 1 must work without SAU, but it can use SAU and can toggle channels on/off as needed. On
> handover to player (mode off), set pitch, bank and heading channels ON.
>
> ## What SAU does
>
> Each channel stabilizes flight on that axis: pitch, bank, yaw.
> When channel is turned on or trimmer is pressed, SAU then tries to stabilize the pitch/bank/heading
> value of that moment.
> SAU works by inducing "corrections" on pitch, bank, yaw controls. Not the cyclic axis, but Mi-24
> hydraulics. The effect is limited and player (or Petrobarin) control input will override it
> easily, but it does help stabilize attitude.
> Pressing cyclic trim button (DCS: 'Trim Button - press') resets the SAU pitch and bank channels to
> hold current pitch and bank on trim button release. While trim button is pressed, SAU does not
> stabilize the channel.
> Similarly for heading channel and pedals trim button (DCS: 'Pedals Microswitch, button - ON').
>
> ## SAU channels
>
> 'H' - heading
> 'K' - bank
> 'T' - pitch
> 'B' - adjustable stops cahnnel. Just keep it turned ON, needs no other actions. Affects pedals to
> tail rotor force stabilization.
>
> ## Using SAU and trim
>
> SAU is used to help maintain and stabilize current attitude (pitch and bank channels) and/or
> heading (heading channel).
> How I use it:
> - in stable flight, press trim to reset SAU to current attitude value, then SAU stabilizes
>   aircraft without need for player (or Petrovich) to do constant small cyclic adjustments. Same
>   thing for pedals trim and heading.
> - when changing attitude or heading, press and hold trim (cyclic trim for attitude change and/or
>   pedal trim for heading change) during the change. When stabilized on the desired
>   attitude/heading, release trim. Then SAU stabilizes to new attitude/heading.
> - Heading channel may disconnect automatically if aircraft turns too far for the heading it was
>   set on. Petrobarin can turn the channel back ON.
> - If rotor rpm drops too much -> generator drops -> loss of electrical power until rotor rpm rises
>   and generator trips back on. Loss of electrical power caues SAU channels to go OFF. Petrobrain ok
>   to turn back ON. This is s special case and would first need detection of loss of generators.
>   Defer.
>
> Not all helicotpers have SAU or similar system. Therefore mode 1 must work with and without SAU.
> In case of Mi-24 (and Mi-8) SAU is available and can be used.

Main-loop reading:
- **Handover rule, independent of the law:** whenever mode 1 hands the controls to the player
  (mode off), switch SAU H, K and T ON (and B ON). This doesn't wait for SAU stage 2; it fits the
  existing effector-sequence mechanism (a sequence file on a handover-to-player trigger). Any
  trigger that already exists for it should be reused.
- **B (adjustable stops):** always ON, no other action.
- **Stage 2 (using the SAU):** an aircraft-specific helper behind the per-aircraft profile (the
  Mi-24/Mi-8 have it, others don't). The law runs with it off and may switch channels and hold or
  release trim: trim held during an attitude or heading change, released once stable, so the SAU
  holds the new value. The heading channel can drop out on a large turn; Petrovich may switch it
  back on. Detecting and recovering from a generator drop is deferred.

SAU effectors (user, verbatim): *"In @body-layer/config/sequences/mi-24p/switch-reference.md there
are SAU-H-* SAU-K-* SAU-T-* and SAU-B-* , those are the effectors."*

## Answers to the plan's U1–U7 (user, 2026-11-20, verbatim)

> "filtered felt load" -> consider just using raw velocity and acceleration. No need to model how
> pilot would feel it. For flight control, code is allowed to know and act on raw telemetry data.
> Deltas probably need to be a running average to filter out vibration.
>
> Q1 - LV-1
> Q2 - yes. Minimun value on pitot based airspeed indicator is 50 km/h. Doppler based speed
> indicator has up to 45 km/h forward, up to 25 km/h back, left, right. Doppler speed is ground
> speed. There is also doppler vertical speed -10..+10 m/s. These are pilot instruments. Copilot
> does not have the doppler instrument, but does have pitot based airpeed and VSI. Regardless,
> Petrobarin is to use raw telemetry data to calculate speeds and accelerations and control inputs
> from that.
> Q3 - yes
> Q4 - yes, SAU after all this works without SAU
> Q5 - revert my idea about extra pedal. Just fly the slip ball.
> Q6 - yes
> Q7 - yes. I just tested DCS velocity is 3D, so sideways movement is reported as velocity. In all
> likelihood it is the 3D velocity vector length.

Settled:
- **No felt-load modelling.** The law steers on raw velocity and acceleration from telemetry,
  with deltas as running averages to filter vibration. `LoGetAccelerationUnits` is not needed as
  a "felt" channel. (This supersedes the plan's felt-load collective loop.)
- **U1:** remove the 80 km/h hand-back in **LV-1**, not LV-3.
- **U2:** yes: below 25 km/h "speed" is ground speed along the nose, blended to IAS above 50 km/h.
  Instruments for context: pitot IAS reads down to 50 km/h; the pilot's Doppler shows ground speed
  up to 45 km/h forward, 25 km/h back, left and right, plus Doppler vertical speed −10..+10 m/s (the
  copilot has only pitot IAS and VSI). The law uses raw telemetry regardless.
- **U3:** yes (ordinary turn: speed, then turn rate, then height; break: height, then speed, then
  turn rate).
- **U4:** SAU off on all LV cards; the SAU stage comes after the law works without it.
- **U5 reverted:** no deliberate extra pedal in hard turns or breaks. Pedals fly the slip ball,
  always. (Supersedes the goal-check Q6 answer.)
- **U6:** yes: a slow break turns more gently.
- **U7:** yes: use `LoGetVectorVelocity` if LV-0 confirms it matches the position deltas. User
  test: DCS's velocity is 3D (sideways movement shows), most likely the 3D vector's length.

## Slowing down (user, 2026-11-20, verbatim, on diagram 4's "1. speed gives: tilt back, trade speed for lift")

> Also needs less collective so that load on rotor blades decreaes. Rotor blade load is what causes
> both RPM drop and reatreating blade stall.
> Slowing down is always pitch back and also less collective.

So every deceleration (the "speed gives" step under limits, and any ordinary speed reduction) is
pitch back plus less collective, never pitch back alone. Blade load drives both rotor-RPM droop
and retreating-blade stall. Plan diagram 4 and "speed gives" amended.

## Diagrams approved (user, 2026-11-20)

Amended diagrams (after U1–U8 and the slowing-down note) shown as a throwaway artifact. User,
verbatim: *"diagrams ok, proceed"*. U8 answered *"no floor"* (plan.md). On the SAU: *"The DCS mi-24
PDF is the only source on the SAU we have. Not likely anything new there."* The user's own SAU
description above is the reference.

## LV-2 explore — breaks (2026-11-27)

Inputs put to the user: the fourth re-fly's break note (*"Break turn starts fine, but then nose rises
too much and bank smooths soon. Could fly breaks more agressively, it is an escape manouvre."*), the
plan's E5 target (60–80° bank, ≤ 100 m height loss), and the G limits from
`aircraft-layer/research/2026-11-27-mi24p-rotor-engine-limits.md` (1.8 G light / 1.5–1.6 G combat
above 200 km/h). Shown: level-turn bank and 180° time by G (1.5 G → 48°, 1.8 G → 56°, 2.0 G → 60°,
2.5 G → 66°; at 250 km/h a 180° takes 20 / 15 / 13 / 10 s), and that 70° bank at 1.8 G sinks
~3.8 m/s² and spends 100 m in ~7 s. Questions: G pulled and for how long; what "more aggressive"
means; what gives when it cannot be level; how a break ends.

User, verbatim:

> 1 - momentary overload accepted, I seem to go to about 2 G.
>
> 2 - with latest changes, roll-in is good, pull back is too much and causes too much nose up and
> resulting violent correction oscillation. So, less and smoother pull back than currently. Should
> not need much cyclic back, instead steep bank angle and some collective to get a fast turn rate.
>
> 3 - height gives first, as long as we're above 50 m AGL
>
> 4 - a break turn should be 90 degrees from the original heading. Or 180 in case of break away.
> Therefore, just set desired heading as usual and fly to it. The difference of break turn is faster
> turn rate, more aggressive manouvre to heading than normal turn.

Reading, for the LV-2 amendment:

- **G:** ~2 G momentarily in a break is accepted (above the 1.8 G reference); the reference limits
  still bound ordinary flight.
- **Shape:** roll-in already good. Less and smoother aft cyclic — the turn comes from steep bank plus
  some collective, not from pulling the nose. The current pull drives nose-up and a violent
  corrective oscillation.
- **What gives:** height first, down to 50 m AGL. (Plan had "within 100 m of entry, never below 40 m
  AGL" — the user's floor is 50 m and names no 100 m budget; the amendment must say which stands.)
- **Height budget, settled (user, verbatim, 2026-11-27):** *"In a break turn, we should not lose
  more than 100 m of altitude. The 50 m AGL is the safety floor below which we must not descend in a
  break."* Both stand: ≤ 100 m loss from entry, and never below 50 m AGL (replaces the plan's 40 m).
  The main loop's earlier reading ("50 m replaces both") was wrong.
- **End:** a break is an ordinary heading goal — entry +90° (break), +180° (break away) — flown with
  a faster turn rate and more aggressive capture than a normal turn. No separate end condition.
- **Roll-out overshoot, settled (user, verbatim, 2026-11-27):** *"break turn: overshoot is
  acceptable"* — the fix pass's ~5° (90° break) / ~7–10° (break away) single overshoot-and-settle
  stands; the card still asks for hunting or more than one correction to be reported.

## LV-3 explore (2026-11-27) — low speed and hover

Questions asked (main loop): (1) slowing through 80 → 60 km/h, what do your feet react to — ball,
nose movement, something else; lead or follow? Start the blend higher, or keep the ball loop and add
a damper for yaw the bank does not explain? (2) heading change at speed 0 — how fast, how soft?
(3) what a good stop from 150 to 0 looks like — nose-up, time, height? (4) drift at speed 0 with no
fixed-spot hold — acceptable for this stage? Context given: the sixth re-fly's 60 km/h left-yaw
runaway sits above the planned 25–50 km/h λ blend, where the plan keeps the pure forward law.

Answers (user, verbatim, 2026-11-27):

> 1 - nose moving sideways. Not the ball, but the yaw movement. I lead since I know more right pedal
> will be required. Start the blend higher. Would be a good idea to have some of that yaw based
> pedal in all flight, that's damped yaw oscillation that happens even when flying the ball.
>
> 2 - In hover, move calmly. Softer is better. But still not awfully slow, 45 degree turn can take
> some seconds, but not more than 10 s. Let's start by offsetting the pedals no more than 30% of
> pedal axis from the value where hover is stable.
>
> 3 - hold altitude, yes. Down to 80 km/h as implemented now. Below that, more gentle movements.
> It's not the pitch/bank angles themselves but how fast they change. Same for collective and
> pedals. While fast response may be needed to correct and stabilize, flight state changes should
> be more gradual than in fast flight. When changing collective pedals must also lead at the same
> time. In transitional lift and slower the need for collective and right pedal increases, but this
> can be done with the control law from vertical speed and yaw. In ground effect, very low AGL,
> rotor creates more lift, so less collective is needed. Again, control law can handle from
> telemetry data.
>
> 4 - this is acceptable

Reading, for the LV-3 amendment (main loop; each point to be confirmed where marked):

- **Yaw cue is nose movement, not the ball.** The pilot's feet answer the yaw *rate*. So:
  - **A yaw-rate damper in all flight**, on yaw the bank does not explain (`ψ̇` minus the
    coordinated-turn rate), alongside the ball loop. It damps the yaw oscillation seen "even when
    flying the ball". **Departs from plan F / finding 2** ("never a heading loop in forward
    flight"): a rate damper holds no heading, so the finding's reason (bank owns heading in forward
    flight) still stands; recorded as a deliberate change, not a reversal.
  - **The blend starts higher.** The user's own boundary in answer 3 is 80 km/h ("down to 80 km/h
    as implemented now"), so the reading is a λ blend from 80 down to 25 km/h (was 50 → 25). The
    60 km/h runaway then falls inside the blend.
  - **The pedal leads the collective, at the same moment** (answers 1 and 3). The existing
    collective-rate → pedal feed-forward (`k_pedal_from_collective_rate`) is that lead; the
    growing right-pedal need in transitional lift and below is left to the feedback loops (yaw rate,
    ball), per *"this can be done with the control law from vertical speed and yaw"* — no
    speed-scheduled pedal trim.
- **Hover heading change:** calm and soft, a 45° turn in no more than 10 s (≥ 4.5 °/s on average;
  a soft S-curve peaks higher). **Pedal authority: at most 30 % of the pedal axis away from the
  pedal value where the hover is stable** — a deflection bound around the learnt hover trim, not an
  absolute limit. *To confirm: 30 % of full stop-to-stop travel, or 30 % of centre-to-stop
  (`±0.3` in the command domain, −1…+1)?*
- **Below 80 km/h, slower rates of change, not smaller angles.** Above 80 km/h the current
  behaviour stands. Below it, the rate at which pitch, bank, collective and pedal *targets* change
  for a commanded change of flight state is lowered; the stabilising feedback may still act fast.
  In the law's terms: the shapers' rate/accel caps (and output rate limits for goal-driven moves)
  scale down below 80 km/h; the inner loops are not slowed. Height is held through the stop.
- **Transitional lift and ground effect need no model.** More collective and right pedal at low
  speed, less collective in ground effect — both left to the integrators on vertical acceleration
  and yaw, from telemetry (consistent with "feedback, not a model", 2026-10-26).
- **Drift at speed 0 accepted** for this stage; fixed-spot hold stays in BL-16 "Later — mode 1
  hover".

**Reading confirmed (user, verbatim, 2026-11-27):** *"looks good, go ahead. +-0.3 for the pedals,
we'll refine after testing if necessary"* — so: λ blend 80 → 25 km/h; a yaw-rate damper on
unexplained yaw at all speeds alongside the ball loop; pedal lead from the existing collective-rate
feed-forward, low-speed pedal need left to feedback; hover pedal bounded to **±0.3 in the command
domain (−1…+1) around the learnt hover-stable pedal value** (the existing absolute limits, right
+0.5, still apply on top); first cut, to be refined from the card.

## M4 SAU explore (2026-11-28)

Main loop opened with what was already on file (the 2026-11-20 "SAU in mode 1" section above, the
2026-10-26 addendum in `plans/flight-control/explore-notes.md`, M0-H unflown, the hand-back
sequence `controls-to-player.md` already built), a mock 90° turn with trim held through the change,
and five questions: (1) what the SAU should change in the cockpit when Petrovich flies; (2) take
with the channels as the player left them?; (3) trim held through a sustained turn, or trimmed in
the bank?; (4) does pedal movement release heading hold without the microswitch, given LV-3's yaw
damper moves the pedals constantly?; (5) lean on the SAU at hover?

Answers (user, verbatim, 2026-11-28):

> - " Trim: pressing trim stops the SAU holding while pressed, and on release it holds whatever
>   attitude or heading the aircraft has at that moment." -> Cyclic trim affects aircraft pitch and
>   bank channels, *not* heading channel. Pedal microswitch affects heading channel. On cyclic trim
>   release, SAU stabilizes (stabilize != hold, aerodynamics or cyclic movement overpowers SAU)
>   aircraft pitch and bank, not heading. On release of pedal microswitch SAU stabilizes current
>   heading. Each appropriate SAU channel must be ON, otherwise there is no stabilization of that
>   pitch/bank/heading.
>
> - "whether the SAU fights Petrovich's control writes" -> most likely yes. SAU fight Players
>   inputs too. Not by much, it will allow control movement to affect aircraft, but it stabilizes
>   the movements. SAU really is a stabilizer, not a full control autopilot.
>
> 1 - SAU adds a bit of stabilization that we don't then need to build in the control law.
> Alternative solution: when Petrovich has controls, turn off all SAU channels (not B) and when
> Player is handed conrols back, turn SAU channels back on.
> 2 - I normally fly with SAU on. On take, Petrovich can decide what SAU to use/not use. Do not
> assume any channel state set by Player.
> 3 - I stabilize pitch and bank and release trim -> SAU keeps the attitude stable. (Heading
> channel must be OFF or pedals microswitch pressed while turning.)
> 4 - I need to press the microswitch button (key 'Y' by default, I've mapped it to joystick
> button). It needs to be pressed for a moment while the SAU adjust, 1 s is enough. SAU heading
> hold might actually achieve that yaw dampening for us.
> 5 - There's hover mode in SAU, but holding 'well' is not certain at all.
>
> All this kinda leans towards option: not using SAU, since we have calculation based control law,
> not human moving stick.

Reading (main loop):

- **Corrections to the 2026-11-20 model:** cyclic trim re-references **pitch and bank only**;
  the pedal microswitch re-references **heading only** (pressed ~1 s, not by pedal movement). The
  SAU **stabilises, it does not hold** — aerodynamics or control movement overpower it. A channel
  stabilises nothing unless it is ON.
- **It fights control inputs, mildly** — the player's and, most likely, Petrovich's (M0-H's first
  question, answered from experience rather than a probe).
- **Direction, leaning: do not use the SAU in mode 1.** The law is computed, not a hand on a
  stick; the SAU's stabilisation duplicates what the law already does and mildly fights it. So:
  on take, switch **H, K, T OFF** (B stays ON); on hand-back, H, K, T ON (already built,
  `controls-to-player.md`). Never assume the channel state the player left.
- **Consequence for the LV cards:** the "switch SAU H, K, T off before every take" step becomes
  Petrovich's job once built.
- **Open, main loop's own concern, not the user's:** mode 2 (parked) flies through ED's AI, which
  is linked to the SAU device (`aircraft-layer/research/2026-10-31-mi24p-park-controls-ai-pilot.md`
  §2/§4, path (a) unresolved). The switch-off must apply to a **mode-1 take only**, including the
  unpark mode 2 → mode 1 take, and never while ED's AI is flying.

**Settled (user, verbatim, 2026-11-28):**

> M4 SAU
> 1 - yes, drop SAU usage from BL-16, build that handover SAU channels on/off as suggested.
> 2 - ED AI does *not* use SAU. Let ED AI do whatever it does with SAU, it may or may not flip
> switches. We're only concerned about Mode 1 and handing controls back to player from any mode.

So M4 is: **on entering mode 1** (voice take or unpark m2 → m1), SAU **H, K, T OFF**, B ON; **on
controls to the player from any mode**, H, K, T, B ON — already built (`controls-to-player.md`,
`controls_to_player_edge` covers `taking`/`m1`/`m2` → `off`). No SAU action on mode 2 entry; the law
never uses the SAU (no trim, no stage 2). The main loop's mode-2 concern above is answered: ED's AI
does not use the SAU.

**SAU switch timing (user, verbatim, 2026-11-28):** *"for the SAU channel on/off changes, do not
wait between them, just turn all on right away. (referring to the general rule of 1 s between
effector writes, this case is exception.)"* — applies to both the take-side (off) and hand-back
(on) SAU rows; the ~1 s default spacing stays for every other sequence.
