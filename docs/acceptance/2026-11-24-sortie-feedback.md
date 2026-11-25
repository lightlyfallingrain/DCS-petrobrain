# Sortie feedback 2026-11-24 — BL-16 LV-1 card, row 1

Branch flown: `feature/bl16-lift-vector-law` @ 97ffe624. Card:
`docs/acceptance/2026-11-23-bl16-lv1-card.md`.

## User's words, verbatim

> # LV-1 flight
> Petrobrain feature/bl16-lift-vector-law @ 97ffe624
>
> ## 1 Take into a held heading
>
> Fail - still creates bank and escalates out of control, logs attached

Logs: `aircraft_layer_flight_trace.log` (estimator trace only, t=0..144.9) and
`aircraft_layer_debug.log`. Only row 1 was flown.

## What the logs show (main loop's first read, not yet a diagnosis)

- Take at t=112.19 (`flight cmd kind=take seq=1`, ack `a:m1`), off→m1. Release at t=137.11
  (ack `a:m1 mode=m1`). Trace ends t=144.9.
- Before the take: steady, vg 55.9 m/s, v_u +1.1, a_r −0.07, ball −0.033, sideslip (aoss) −1.9°.
- **First 8 s after the take, before any bank oscillation:** ball moves monotonically
  −0.03 → +0.56, sideslip −1.9° → +18°, a_r 0 → +2.5 m/s² with psidot ≈ 0 (flight path curving,
  nose not following), v_u climbs 1.1 → 5.7 m/s. The ball running to +0.5 (≈ full left pedal on
  the 2026-11-20 calibration) is the earliest wrong thing.
- Then a growing lateral oscillation, period ~10 s: a_r +2.5 (t≈118) → −5.3 (t≈126) → +6.2
  (t≈130) → −10 (t≈136); roll rate peaks 30–37 °/s; v_u swings +11.5 → −3.5 → +6.9 m/s.
- The trace carries no law internals (phi_d, theta_d, t_r, t_p, t_y, u_c, r_d, a_*_d), so which
  loop drives it cannot be read from these logs.

## Hypotheses to check (not decided)

1. Pedal ball loop sign inverted (positive feedback). The loop's sign rests on
   "positive pedal command = right", derived from a weak (+0.23..+0.40) on-ground correlation of
   arg 1103 with yaw rate (`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`).
2. Collective→pedal torque feed-forward or the turn-coordination pedal overlay with a wrong sign.
3. Lateral trim loop (phi_i on a_r error) fighting sideslip-induced side force, and the vertical
   loop climbing for a reason not yet known.

## User's answer, after the first read

Asked whether the pedals moved after the take, and which way:

> yes, lot's of left pedal

Left pedal is what moves the ball right (2026-11-20 calibration), so this supports hypothesis 1:
the ball loop is driving the pedal away from centring.

## Re-fly after the pedal-sign flip (same day, 7f362fa4 + card)

User's words, verbatim:

> Actually, it's worse now, even more left pedal at takeover

> the pedal write is definetely reversed now, so apparently it was not before

Logs: `logs-2026-11-24/refly_flight_trace.log` (law internals now present; this flight starts at
the line whose `t=0.000` carries `mode=off phi_d=nil`) and `refly_debug.log`. Take t=24.97 (off→m1,
~135 km/h level), release t=34.98.

Main loop's read of the law trace:
- **The commanded pedal does not jump at the take**: `out_pedals` −0.302 at t=25.05, −0.295 at
  25.4, −0.28 at 25.7 — smooth, small. Yet **yaw rate goes −0.5 → −9 °/s within 0.8 s of the
  take** (heading decreasing, nose left), before the law's pedal changed by more than 0.03. Flight 1
  shows the same kick (−0.05 → −5.9 °/s within 1 s). Something at the take itself moves the
  aircraft, which no gain sign can cause — candidates: the actual pedal position is not where the
  captured value says (capture/write mismatch, i.e. a mirror at the take), or the hardware pedal
  and `LoSetCommand` combine.
- After that, the law ran right-pedal per its new convention: `t_y` to its −0.5 limit plus the
  turn-coordination term −0.33 (heading-hold asked +16 °/s right), `out_pedals` −0.83. The user saw
  heavy **left** pedal. So a negative command is physically left — the debugger's flip was wrong,
  matching the user's statement.
- Sideslip reached 67°, ball +0.65. Collective drove steadily down from 0.106 to −0.01 (u_c_rate
  −0.05/s) from the take until it stopped — not yet explained.
- The trace still lacks the **actual** axis args (1100–1103) next to the commands, so the take
  mismatch cannot be confirmed from the logs.

## User's answer on the take (after the re-fly read)

> Ah, this is a lead.
> When Petrovich takes controls (with current branch code and before the axis sign flip) There is an immediate pedal movement to left. It does not hold, what player was holding, but moves immediately. That causes the initial yaw.
> I suspect that either the pedal read is old, or it is wrong.

So the take is not bumpless on the pedal, in both code versions. That is independent of the
ball-loop gain sign.

## User's further observation and rule

> Take over from when player is in copilot seat is a bit smoother.
> Could be that pedals are read from copilot.
> -> controls must be read and written from which ever seat player is in

## User's controls and DCS settings (answer to the trim questions)

> These flights were with SAU off, so I did not press pedal trimmer.
> The Pedal Damper and/or Adjustable stops (SAU thing) may affect this. But I did also try with them off and still the pedal take over jumps.
>
> My Mi-24 special settings:
> - Stick Trimmer Mode: Joystick Without Springs and FFB
> - Pedals Trimmer Mode: Instant Trim
> - Pedals Microswitch Logic: Enable/Disable by presence/absence of pedal movement
> - Pedals Trimmer Button: do not trim
>
> I have the Pedals Microswitch Button bound to my joystick and that is what I use (and refer to as pedal trimmer) when I want the SAU to hold my heading.
> My controllers are not spring centered, cyclic, pedal and collective axises remain where I put them. Not FFB, I just removed the springs.

Main loop's note: the stick runs a no-springs trimmer mode and holds exactly at a take; the pedals
run "Instant Trim", a mode meant for spring-centred pedals, and only the pedals jump. That points the
trim-offset hypothesis (`plans/flight-lift-vector/debug-2026-11-24b.md`) at the pedal trimmer mode,
not at a trimmer press. Not proven; the next trace (`a1103` next to `out_pedals`) gives the offset.

## User's correction on pedal trim

> In DCS settings there inly two options for the Pedals Trimmer Mode:
> - Instant Trim (default)
> - Central Position Trimmer Mode
>
> For pedals without spring centering, Instant Trim is the correct choise.
>
> However, since I also have Pedals Trimer Button set to Do not trim, it actually does not trim the pedals.
> Trim in this case of pedals meaning:
> - player offsets pedals
> - player presses trim
> - current pedal offset is set to be pedals neutral position
> This is mainly for spring centered pedals, so that the player does not need to keep pressing the pedal all the time againt the spring force. But since I don't have spring centering, I do not need this trimmer and can just leave the pedals at the offset they are on and they stay there.
>
> Not, the Pedals Microswitch Locig is the actual Mi-24 pedals "trim". When SAU is active (or rather channels that affect the heading/tail rotor) then the microswitch activation is the "trim" that then attempts to smooth the controls so that set heading/tail rotor force is maintained, just as the other SAU channels.

Main loop: this rules out a trimmer offset — nothing trims. What remains that fits every data
point is that **the pedal write is added to the player's own (non-centring) hardware pedal
position** instead of replacing it: cockpit pedal = hardware − command. On the ground (M0-B) the
hardware pedals were centred, so the write looked like a clean −1 mirror. At a take Petrovich
captures the cockpit pedal (= the player's hardware offset) and writes it back, so the offset is
counted twice: J3's exact doubling (0.062 → 0.123), probe v2's constant ~0.16 in both seats (the
player's pedal offset then), and the left kick at every take. The stick holds exactly at a take,
so the stick write replaces rather than adds — why the pedals differ is unknown. Not proven;
predictions: `a1103` doubles at the take; a take with the hardware pedals centred has no kick.

## Take B result: additive hypothesis falsified

> I tried the take with pedals centered. Still the kick. No matter what pedal position I hold, there is always the kick. Both seats.

So the kick does not scale with the player's pedal offset. That points to a constant offset on the
pedal write or capture, not to an added hardware position. Probe v2's constant ~0.16 in both seats
fits a constant offset better. The trace from this flight (`a1103` next to `out_pedals`) gives its
size and sign.

## Data flight with actual args (logs `logs-2026-11-24/data_*`)

> There may be multiple flights in these logs. In the last one, I tried the take with both pedals centered and then approximating the kick and pushing pedal right by about that amount to see what happens. I think I did that from both seats.

Main loop's read (six takes, both seats, pedals centred and pre-offset right):

- **The pedal write carries a constant offset.** In steady state, actual pedal arg
  `a1103 ≈ 0.32 − out_pedals` at every take and throughout every active period: 0.30–0.36 over
  speeds 40–61 m/s and collective 0.26–1.0, both seats. Before the first write `a1103` equals the
  captured value (bumpless read); within ~0.6 s of writing it settles 0.32 higher (= left pedal).
  Pitch, roll and collective args follow their commands with no offset. On the ground (M0-B) the
  pedal write had no offset. Where the 0.32 comes from in DCS is unknown.
- With the hardware pre-offset right (`a1103 = −0.375` before the take), the pedal still ended at
  `0.32 − command` — the write overrides the hardware pedal; nothing is added from it.
- **New: the collective goes to full up (arg 1.0) within ~3 s of every take** and stays there.
  Not yet explained (the RPM-guard unlock is the only collective change since the re-fly).

## Third re-fly (pedal bias + collective/pitch LAW_DIR, 5859838b) — logs `logs-2026-11-24/refly3_*`

> Fail on the cyclic logic - complete loss of control is a couple of seconds

Take t=52.318, pilot seat, captured p=0.190 r=0.077 c=0.211 y=0.006.

Main loop's read (one take, ~40 m/s, climbing 4 m/s at the take):

- **Take bumpless on all four axes**, pedal included: `a1103` 0.006 → 0.009 first frame,
  `bias_pedals` 0.320. The pedal-bias fix works.
- **Pitch ran away nose-down**: pitch −0.5° → −14.4° in 5.5 s, rate accelerating to −13 °/s.
  Meanwhile `theta_d` rose to +0.8° (law wants nose up), `t_p` rose (law asks more nose-up), and
  `out_pitch`/`a1100` fell 0.19 → −0.63/−0.55. A 0.74 move of the stick arg *with* an
  accelerating nose drop: the stick moved the way that drops the nose. So **arg 1100 positive =
  nose up (aft)**, and `LAW_DIR.pitch = −1` is the positive-feedback sign.
- Independent check, steady trim at each take of the data flight and this one: higher speed →
  lower `a1100` (40 m/s 0.19 … 58 m/s 0.04). Faster needs more forward stick, so lower = forward:
  same conclusion. The M0 −0.56 correlation (pitch attitude vs arg, SAU on, A3) and the data-flight
  pitch reading (collective then running to full up) were both confounded.
- Other axes did what the law asked: collective eased down from the take (law levelling a 4 m/s
  climb), pedal went left (ball loop centring a −0.16 ball; ball reached 0.00), bank followed
  `phi_d` with ~0.5 s lag — roll direction looks right.

User, answering "did the stick go back or forward?":

> I think the pitch angle axis is flipped in our code.
> On take Petrovich pulled the cyclic full back -> significant nose up.

Main loop: this conflicts with every motion channel in the trace, not only the ADI pitch. From the
take to t≈58 (before the tumble): ADI pitch −0.5° → −16.6°; body pitch rate (`LoGetAngularVelocity`
z, a separate sensor) −15 °/s; load factor `au_y` 1.00 → 0.50 (a push-over, not a pull — a pull
is above 1 g); vertical speed +4.2 → −3.5 m/s; ground speed 40.0 → 42.7 m/s. Nose up with full aft
stick would show pitch rising, g above 1, speed falling. Pitch reaches −86° at t=60.3, then the
bank flips to −140° and pitch comes back up while inverted (tumble). Open: either the stick in fact
went full **forward** (arg 1100 −1 = forward, the take-trim evidence) and the cockpit picture
misled, or aft stick did not raise the nose. Decisive, cheap checks: the track replay in external
view, and a ground check of which way `a1100` moves when the player pushes the stick forward.

User's answer, closing the open question:

> you are correct, it was pitch down. I remembered the flight before that where it went up.

So the nose went down and the stick went forward: arg 1100 −1 = forward, positive = aft/nose up.
Corroborated by `a1100` vs pitch acceleration, positive (+0.25..+0.57) in every hand-flown stretch
of both flights. Fixed in 2ff15f05 (`LAW_DIR.pitch = 1`, `plans/flight-lift-vector/debug-2026-11-24d.md`).
The checks named above were not needed.

## Fourth re-fly (pitch direction reverted, 38302851) — full card

No logs brought back with this report. User's words, verbatim:

> # LV-1 test flight
>
> ## Item 1
>
> passes now. The take over is a bit wobbly, but it stabilizes. It'll do for now.
>
> ## 8-9 Take from a bank, and mid-turn
>
> Levels off from the turn. There's some oscillation, but it subsides and aircraft stabilizes - OK. However, when Mode 1 engages in a turn, it should continue that turn, turn engage heading hold on the heading at handover time. Not immediate big problem, but needs fixing in BL-16.
>
> Mode 2 to Mode 1 mid turn: first goes for bank 0, then resumes turn to heading set in Mode 2. Resuming set heading is correct, leveling off mid turn is not, should just continue turn.
>
> ## 2 Turns: 30° and 90°, both ways, 120 and 220 km/h
>
> Turns OK, accepted.
>
> ## 3 Speed 150 → 220 → 150
>
> Speed changes work, but are very slow. Way too slow. Need much more pitch and collective input.
>
> ## 4 Climb 100 m, descend 100 m
>
> Climb and descent work, but on collective movements, especially increase, pedal correction lags behind causing yaw offset and oscillation.
>
> ## 5 Heading hold in a crosswind
>
> Pass.
>
> ## 7 Take at about 70 km/h
>
> OK. Though pedal inputs change quite slowly, which may cause overshoot and oscillation.
>
> ## R2 Handback with a seat change
>
> OK, pass.
>
> ## 10 Slow flight — expected to find the edge
>
> Around 50 km/h developed left yaw, which quickly got out of control. Not enough right pedal.
>
> ## general observations
>
> * cyclic and pedal changes are slow and because of that corrections sometimes lag the actual flight state.
>
> * Break turn starts fine, but then nose rises too much and bank smooths soon. Could fly breaks more agressively, it is an escape manouvre.
>
> * Accelecating from 150 to 250:
>    * slow pith down increase to about -8 deg.
>    * How I fly it:
>       * level flight, 150 km/h
>       * pitch down ~15 deg, lot's more collective and right pedal to compensate for added collective. All this in 1-2 s.
>       * Keep flying -15 pitch until speed about 230, then start settling for 250 by bringning nose up, lowering collective, adjusting pedals.
>       * Same thing for decelaration, but opposite ways.

User's correction to the 8–9 sentence:

> " OK. However, when Mode 1 engages in a turn, it should continue that turn, turn engage heading hold on the heading at handover time" - correction "not turn engage heading hold on"

So: a take in a turn continues the turn; it does **not** engage heading hold on the handover
heading. This restates BL-16 decision 3 (*"keep the turn going, that is what I mean by
maintaining current state"*, `body-layer/ROADMAP/BL-16.md`), which LV-1 does not meet.

Asked whether, with no command after a take in a bank, he keeps circling:

> Mode 1 takeover. Let's say that if bank is less than +-5 degrees, engage heading hold. If bank is more than that, maintain bank.

Rule for a mode 1 take with no standing goal: |bank| < 5° → heading hold (on the take heading);
|bank| ≥ 5° → hold the bank (keep turning) until commanded. The 5° is a first cut, tunable. Mode 2 →
mode 1 with a mode-2 heading goal: keep the turn toward that heading, never level first.

Explore answers on speed changes and input shape:

> 1 - Acceleration 150 to 250 takes about 20 s when I fly it. Petrovich took about a minute. I might use more than -15 momentarily, but -15 is about the max that the collective can create lift to maintain altitude. If I decide to sacrifice alt for speed, I can push beyound -15 deg for a a few seconds.
>
> 2 - pretty much the same, except that  at stabilization collective needs to be raised fairly slowly to give the engines time to spool up and create more torque, otherwise rotor RPM drops fast. Say ~5 seconds smooth nose down and collective up.
>
> 3 - The input cahnes themselves can be fast always, that's how a human needs to do them. But the amount of delta needs to get slower as speeds slows. Therefore: Any cyclic movement can be fast, even very fast. Pedals move more slowly in Mi-24 anyhow. Collective small movements can be fast, large movements especially increase need to be more gently. What the movememts should not be is a lot of delta at fast rate. Rather lots of smaller incremental corrections at fast rate.

Main loop's reading:
- **Speed change target:** 150 → 250 km/h in ~20 s (he took ~60 s). Level acceleration pitch about
  −15°, the most at which the collective can still hold height; beyond −15° only for a few seconds
  and only when trading height for speed.
- **Deceleration** mirrors it, except the roll-out at the end: nose down and collective **up** over
  ~5 s, smooth, so the engines spool and rotor RPM does not drop.
- **Input shape:** fast, frequent, small corrections — never one big delta at a fast rate. Cyclic
  may move fast; pedals are slower in the Mi-24 anyway; collective small moves fast, large moves
  (above all increases) gentle. The size of each correction shrinks as speed falls.
- Not answered (assumed): holding a bank after a take also holds height and speed. Oscillation
  size after a take from a bank: left to the next logs.

Main loop's first summary (not a diagnosis): rows 1, 2, 4, 5, 7, 8–9 stabilise, R2 pass, row 10
lost at ~50 km/h (left yaw, not enough right pedal). Common thread: everything is **slow** —
cyclic, pedal and speed changes lag the flight state. Two behaviour gaps: a take mid-turn should
**keep the turn** (heading hold on the take-time heading, or the mode-2 heading), not level off
first; and the user's own acceleration technique (−15° pitch, collective and right pedal in
1–2 s, hold until near target, then settle) as the reference for speed changes. Breaks:
nose rises too much and bank eases too soon.

### Answers to the goal check's five questions (`plans/flight-lift-vector/alignment.md`)

> 1 - at higher speed, collective can be increased faster. At level flight the engines are already at high/normal output, so increasing collective is no problem. When descending or decelerating or both, the engines spool down as torque is not needed. Then adding lot's of collective in that state quickly slows down the rotor. Collective increase triggers the engine control unit to increase power, but it takes a few seconds for the engines to spool up and provide torque. That is why collective increase need to be gradual, when engine RPM is low initially. When engine RPM is high initially, the collective increase can be fast as well.
>   - More collective -> more rotor blade angle -> more torque needed -> engine control unit commands more power.
>   - Lees collective -> less rotor blade angle -> less torque needed -> engine control unit commands less power. If needed torque is very low for several seconds (slowing down and/or descending) engine RPM drops low until torque is needed again.
>
> 2 - brisk
>
> 3 - as recommended
>
> 4 - as recommended
>
> 5 - The Mi-24 limits pedal movement speed. We have measurements of pedal movemnt from earlier, commanded vs actual. From there you can get the actual pedal delta speed.

Main loop's reading:
1. The collective-increase rate depends on **engine state**, not on the manoeuvre: engines at
   normal output (level flight, higher speed) → fast increase is fine; engines spooled down after
   several seconds of low torque demand (descending, decelerating) → increase gradually over a few
   seconds while they spool up. Needs an engine-RPM/torque reading or a proxy (recent low-collective
   time); today's RPM guard runs on a placeholder reading.
2. A take with a speed gap flies the brisk speed change at once.
3. Only heading-type commands ("turn heading", "turn N left/right", "stop turn"/"level flight") end
   a held turn; height and speed are held while it circles.
4. A take during a roll-out with |bank| ≥ 5° keeps the bank (the rule as stated); "stop turn" levels.
5. The aircraft itself rate-limits pedal travel. Get the real rate from commanded-vs-actual pedal
   in the traces, and make the law's pedal command keep up with that rate rather than lag it.
   Measured: M0 (ground, 0.15–0.20 steps) first-order lag τ ≈ 0.25 s
   (`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`); fourth re-fly,
   hand-flown, pedal arg rate clusters at **0.90–0.91 /s** and never sustains more (0.3 s windows:
   p99 0.72, max 1.29 /s including seat-switch steps) — an aircraft rate cap of ~0.9 /s on top
   of the τ 0.25 s lag. Petrovich's own pedal moved at p99 **0.16 /s**, p95 0.06 /s: about 5×
   below what the aircraft allows.

### Engine and rotor RPM, user's cockpit readings

> In level flight, 170 km/h
>
> * engine RPM steady at ~93%
> * rotor RPM steady at ~96%
>
> Fast acceleration
>
> * engine RPM ~98-100%
> * rotor RPM ~88%
>
> Fast descent at collective full down
>
> * engine RPM ~74%
> * rotor RPM ~100%
>
> When rotor RPM drops below ~85%, the generator trips off -> loss of electrical power. Therefore 85% is the rotor RPM low limit.
>
> using cockpit instrument readings, not raw data

Main loop: **engine RPM and rotor RPM move in opposite directions** across these states. "Engines
spooled down" (Q1) shows on **engine** RPM (74% in a fast descent) while rotor RPM is then at its
highest (100%). So the collective-increase rate must be gated on engine RPM, not rotor RPM — a
rotor-RPM gate would allow a fast increase exactly when the engines are spooled down. Rotor RPM's
own role is the hard floor: 85% = generator trip (electrical loss), so the RPM guard's floor is
85% plus margin, and a fast acceleration already runs at ~88%, close to it.

### Fourth re-fly logs (`logs-2026-11-24/refly4_*`, session starting trace line 3532)

Main loop's read:

- **Acceleration, user vs Petrovich.** User hand-flown (t=2042–2064): 146 → 257 km/h in ~20 s,
  dV/dt 1.6–1.9 m/s² sustained, pitch −13…−14°, collective arg to **1.00** (full) within ~6 s,
  pedal arg 0.35 → −0.13 (right) with it. Petrovich (t=1815–1891): 167 → 250 km/h in ~75 s.
  The shaper asked for up to `a_f_d` = 1.78 m/s² but he got only 0.6: `theta_d` reached only
  −8.4°, collective 0.35. Near the target `a_f_d` stayed 0.8 with achieved ~0 and `theta_i` crept
  only −3.0 → −4.2 in 75 s. So the shaper is not the limit. The pitch the law derives from a
  desired acceleration is about half what is needed (`c_theta = 0.5`, the plan's deliberate "half
  feed-forward"), and the trim loop that should make up the rest is far too slow. The user needed
  about 12° of extra nose-down for 1.9 m/s², slightly more than `atan(a/g)` (10.9°).
- **Collective → pedal.** In the row-4 climb (t=976–995) the collective rose at only
  ~0.05/s (−0.02 → 0.49 over 10 s). The nose drifted left (ψ̇ −0.9 °/s), the ball went
  0.03 → 0.12, and `t_y` took ~15 s to move 0.32. The torque feed-forward gave 0.25 × Δu_c ≈ 0.13
  of that; the rest came from the ball integrator (`k_ball_pedal` 0.3/s per ball unit, **integral
  only, no proportional term**). The heading hold then banked ±4° to fix the yaw, giving a ~20 s
  weave. The pedal needed was ~0.6 per unit collective here, not 0.25.
- **Take from a bank, heading-hold case.** Take at t=366.5 in −23° bank, ψ̇ −8 °/s: heading hold
  on the take heading swung bank to **+34°**, then −18°, +5°; settled in ~15 s. Take at t=409.5
  in +31°: −35°, +11°, −3°. The outer heading loop over-corrects a turn already under way. The
  new 5° rule removes this case; heading capture after turn commands (row 2) was accepted.
- **Slow flight (row 10), t=1505–1534.** Decelerating 81 → 64 km/h ground speed, sideslip from the
  trace's own `aoss` grew 25° → 42° while the ball stayed centred (wind: ground-referenced
  velocity, ~40° crab). At t=1527 the nose broke left: ψ̇ −0.4 → −15 °/s in 3 s. The pedal went
  right only at ~0.09/s (arg −0.03 → −0.46 in 5 s), driven by the ball loop and the turn-entry
  nudge from heading hold (r_d +17 °/s, bank to 30°). No yaw-rate term exists in forward flight by
  design (plan F, finding 2), so nothing reacts to the yaw itself; the right-pedal limit (0.5) was
  not reached. LV-3 scope, but the same slow pedal is the cause.

Logs kept locally (gitignored): `docs/acceptance/logs-2026-11-24/` in the `DCS-petrobrain-epochfix` worktree.

## Fifth re-fly (LV-1 amendment, caec92f1) — 2026-11-25 — logs `logs-2026-11-25/refly5_*`

User, verbatim:

> *"BL-16 refly*
>
> *Bank take - OK*
> *Climb and descend - OK*
> *Level take, no wobble - OK*
> *Speed change - Still very slow*
>
> *Speed change:*
>
> *\* pitch changes more now, but not enough and above all it takes much too long to reach the
> pitch"*

So rows 8–9 (bank take), 4 (climb/descend) and 1 (level take) pass. Row 3 (150 → 250 → 150) fails:
pitch reaches further than last flight but not far enough, and the dominant complaint is the time
to reach the pitch. Not reported this flight: the RPM calibration readings (U9) — the trace carries
args 40/41/42/838/839/845 regardless.
