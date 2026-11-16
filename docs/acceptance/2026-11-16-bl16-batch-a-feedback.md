# BL-16 parked mode, batch A — sortie feedback 2026-11-16

**Status: captured, not yet explored.** Per root `CLAUDE.md` "Flight feedback is captured, then
explored, then planned": nothing here is a decided fix. Card flown:
`docs/acceptance/2026-11-15-bl16-batch-a-sortie.md` (branch `main`). Results belong on
`body-layer/ROADMAP/BL-16.md` once explored.

## What the pilot brought back, verbatim

> *"# BL-16 - Parked Mode Batch A card flight*
>
> *## P-ICS*
> *- works*
>
> *## P1*
> *this happens:*
> *- when I park controls, AI overlay gets current alt (radar), but AI starts immedia descent. That
> is ED bug.*
> *- Immediate centre AI push to toggle to barometric alt again sets current barometric alt as
> desired alt (although sometimes it has set something way incorrect) and halts descent. AI flies
> to desired alt.*
> *- Toggling between radar/barometric alt, the AI now flies to get to that alt.*
> *- Therefore: a workaround for that initial sink is to center press immediately. Since radar alt
> is more reliably set correctly, do this: when AI takes over, center press to switch to
> barometric, then center press again to swich to radar alt. Then we should get stable alt from the
> AI flying. After that proceed as player has instructed to reach desired flight params."*

```
➜  run-scripts git:(main) OMEN=192.168.0.85 ;curl http://$OMEN:7791/ai_pilot_wheel/latest
{"t": 12.397, "received_wall_clock_s": 1794827946.8487742, "apw_parked_active": false, "apw_mode_text": null, "apw_course_text": null, "apw_alt_text": null, "apw_alt_add_text": null, "apw_speed_text": null, "apw_last_press": null}%
```

> *"Though AI overlay is visible and AI actually is flying. Export.lua from main, the normal one."*

## Results by flight

- **P-ICS: pass** (pilot: *"works"*).
- **P0** (the seven-row AI-wheel probe): not reported this flight.
- **P1: the sink happens.** Pass criterion was "no altitude sink on park". Not met.

## What the code says — facts checked 2026-11-16, not yet a diagnosis

1. **Batch A's park-sink fix depends on its own park detection.** `aircraft-layer/dcs-export/
   Export.lua` `run_ai_pilot_wheel` decides "parked" from cockpit args 852 (stick park) and 952
   (pedals park). Only on that rising edge does it arm the one-shot nudge (a long "altitude up"
   press when the held altitude equals actual, within 20 m).
2. **The pilot's telemetry shows that detection reading not-parked** (`apw_parked_active: false`,
   every overlay field null) while the AI overlay was visible and the AI was flying. While
   not-parked the exporter clears every field and never arms the nudge. **So the nudge very likely
   never fired, and the sink observed is ED's AI with nothing from Petrovich.** That makes P1 a
   test of park detection first, and of the nudge not at all.
3. **`t: 12.397`** on the latest sample. If `t` is mission time, the newest AI-wheel line arrived
   about 12 s into the mission, which would mean the line stopped updating early. Unconfirmed:
   depends on when the query was made and what `t` counts.
4. **The pilot's workaround replaces the nudge.** Centre press toggles barometric/radar and makes
   the AI adopt the current altitude in the new reference. Centre, then centre again, ends on
   radar with the AI holding current radar altitude, and stops the sink. This is a different
   mechanism from Batch A's "altitude up" nudge.

## Explore, 2026-11-16 — the pilot's answers, verbatim

**How the AI takes over:**

> *"1 - In DCS control options there is "Request Aircraft Control" in Copilot-Gunner seat key
> bindings, category "Petrovich AI Helper, Multicrew". That is what activates the AI. There is
> control entry for 'Copilot Stick - PARK/UNPARK', but it does not actually do anything."*

**The `t: 12.397` sample:**

> *"2 - failry new mission, looks ok"*

**The workaround in practice, and ED's bug:**

> *"3 - a second or two after take over. I'd put a half second delay there. It held, I think
> there's a bug where the initial altitude setting is visible in the overlay, but does not actually
> go to the code in AI. Setting it via center press (or changing alt by up) resets it and it
> reaches the AI code. The bug is ED's, not ours, so we work around it."*

**Which altitude reference:**

> *"4 - barometric is a better choise for us, let's actually go for that and change later if
> needed. This needs observation from flight, will refine later."*

**The P0 probe:**

> *"5 - probe flight is next, I'll report on it shortly."*

## What this settles, as read (not yet a plan)

- **Batch A's trigger is wrong.** The AI takes over on the operator-seat binding "Request Aircraft
  Control" (category "Petrovich AI Helper, Multicrew"). "Copilot Stick - PARK/UNPARK" does
  nothing. So args 852/952, which Batch A watches, never show the handover, and the fix could not
  fire. The new trigger has to see the AI actually taking control. **Whether Export.lua can see
  that, for example from the AI overlay appearing in `list_indication(6)`, is what the P0 probe
  answers (P0-1),** so detection waits for that report.
- **The sink is ED's bug.** The starting altitude shows in the overlay but never reaches the AI's
  logic. *Any* altitude change pushes it through: a centre press (reference toggle) or an "up".
  Batch A's "up" nudge was a valid mechanism; it just never fired.
- **Fix shape: about 0.5 s after takeover, one centre press, radar → barometric.** The AI then
  holds the current barometric altitude. Barometric is the reference for now, to refine from
  flight. *Read from answers 3 and 4: this replaces the earlier radar-ending double press. Single
  press assumes the AI always starts on radar, as the pilot saw.*
- **Then carry on to whatever the pilot has asked for** (Stage P2's goals), from that stable state.
- **The `t` field is fine** — a fairly new mission. No second problem there.

## Flight P0 — the probe log, 2026-11-16

`Export.probe-ai-pilot-wheel.lua`, uploaded by the pilot as `aircraft_layer_probe_ai_pilot_wheel.log`,
verbatim:

```
13:44:55 BL-16 MODE 2 STAGE P0 PROBE -- AI-PILOT WHEEL
13:45:03   waiting 5s to settle, then waiting for you to park
13:45:27   t=23.8: park signal rising -- starting the sequence
13:45:27 P0-6: park-sink measurement
13:45:27   on park: overlay=mode=nil course=nil alt=nil alt_ref=nil speed=nil  actual_agl=189.63543701172 actual_msl=954.65881347656
13:45:27   held altitude already differs from actual -- no nudge issued
13:45:47   20s altitude trace (AGL): 0s:190m 1s:193m 2s:188m 3s:178m 4s:165m 5s:150m 6s:134m 7s:119m 8s:109m 9s:102m 10s:96m 11s:91m 12s:87m 13s:83m 14s:81m 15s:79m 16s:77m 17s:75m 18s:74m 19s:73m
13:45:47   nudge issued: false
13:45:48 P0-1: overlay content, wheel closed vs open
13:45:48   as found: mode=nil course=nil alt=nil alt_ref=nil speed=nil
13:45:49   after one ShowMenu toggle: mode=FLT course=88 alt=176 alt_ref=R speed=150
13:45:50   after second ShowMenu toggle (back to start): mode=nil course=nil alt=nil alt_ref=nil speed=nil
13:45:50 P0-2: one 0.7s held press per outer position, in FLT
13:45:50 P0-2: mode is nil, cycling toward FLT (attempt 1..3)
13:45:50 P0-2: WARNING: could not reach mode FLT after 3 attempts (now nil)
13:45:50   [1] UP / [2] DOWN / [3] LEFT long / [4] RIGHT long -- before and after: all nil
13:45:57 P0-3: speed tap sequence -- could not reach FLT; starting speed_text nil; taps 1-2 nil; "taking this as MAX"
13:45:59 P0-4: no readback change observed within 5s of release
13:46:04 P0-5: centre press -- before nil, after nil
13:46:05 P0-7: could not reach FLT; stopped at the tap safety cap without reaching speed 0
13:46:19 SEQUENCE COMPLETE
```

(Repeated banner and separator lines trimmed; every measured line kept.)

### What it shows — checked against the probe source, not yet explored

- **P0-6, the sink, measured:** 190 m AGL → 73 m in 20 s, still descending at the end. Steepest
  about 16 m/s (5 s → 6 s). No nudge, because the overlay read empty on park.
- **P0-1 answered: `list_indication(6)` carries the AI readback only with the command menu open.**
  Closed: every field nil. One ShowMenu toggle: `mode=FLT course=88 alt=176 alt_ref=R speed=150`.
  Toggled back: nil again. The plan treats "only with the overlay open" as a cosmetic limitation,
  not a redesign — but it does mean **Export.lua cannot see the AI's state, or detect its takeover,
  without opening the menu.**
- **The overlay held `alt=176 R` while the aircraft was about 73 m AGL and still sinking**, which
  fits the pilot's account of ED's bug: the held altitude is displayed but not applied.
- **P0-2 to P0-7 produced no data.** The probe closed the menu again after P0-1, so every
  later read was nil and every "cycle toward FLT" failed. Its presses were issued with the menu
  closed. Whether they did anything to the AI is not in the log.
- **Park detection disagrees between the two flights.** The probe watches arg 852 (stick park)
  ≥ 0.9, and it rose at t=23.8. Production Batch A watches 852 *or* 952 at the same threshold, yet
  the P1 flight's telemetry read not-parked while the AI flew. **Unexplained.** One hypothesis,
  unverified: 852 reaches 0.9 only briefly at takeover and drops back, which a rising-edge probe
  would catch and a level check later would not. In production that would also clear the armed
  nudge on the next frame, before the 5 Hz tick could fire it. **Refuted the same day:** the
  probe's own abort check read 852 every frame and never fired, so 852 stayed high (and the
  re-fly below measures it directly).

## Flight P0 re-flown with the fixed probe — 2026-11-16

Pilot's answers before the re-fly, verbatim: *"Q1 - yes, AI reacted. Q2 - I think the probe issued
alt change, that stopped the sink. Q3 - I use the same binding always."* Probe fixed on
`fix/bl16-p0-probe-menu-open` (`aebcfd79`): menu held open for P0-2..P0-7, P0-6 tests the
pilot's centre-press fix, args 852/952 logged.

The log, uploaded by the pilot (second session onward; a first session at 15:10 stopped 7 s
after its centre press, before P0-6 finished). The run of arg readings during the handover
animation is trimmed to its endpoints; every other measured line is verbatim:

```
15:11:22   t=5.0: arg852=0.00 arg952=1.00
15:11:30   t=12.8: arg852=0.04 arg952=0.96
           ... 852 rises and 952 falls in lockstep, 852 + 952 = 1.00 at every sample ...
15:11:30   t=13.2: arg852=0.90 arg952=0.10
15:11:30   t=13.2: park signal rising (arg 852) -- starting the sequence
15:11:30 P0-6: park-sink fix -- centre press 0.5s after takeover, menu closed
15:11:30   on takeover: overlay=mode=nil course=nil alt=nil alt_ref=nil speed=nil  actual_agl=155.09912109375 actual_msl=920.53997802734  arg852=0.91 arg952=0.09
15:11:31   centre press issued at +0.50s (menu closed)
15:11:50   20s altitude trace (AGL/MSL m): 0s:155/921 1s:155/921 2s:155/921 3s:158/924 4s:162/927 5s:166/931 6s:170/936 7s:176/942 8s:184/949 9s:192/957 10s:201/966 11s:211/976 12s:221/986 13s:231/997 14s:242/1008 15s:254/1019 16s:265/1030 17s:276/1041 18s:288/1053 19s:299/1064
15:11:50   20s park-arg trace: 0s:arg852=0.91 arg952=0.09 | 1s..19s: arg852=1.00 arg952=0.00
15:11:51 P0-1: overlay content, wheel closed vs open (ends OPEN)
15:11:51   as found (closed): mode=nil course=nil alt=nil alt_ref=nil speed=nil
15:11:52   after one toggle (open): mode=FLT course=95 alt=1658 alt_ref=B speed=120
15:11:53   after second toggle (closed): mode=nil course=nil alt=nil alt_ref=nil speed=nil
15:11:54   after third toggle (open, held for P0-2..P0-7): mode=FLT course=95 alt=1658 alt_ref=B speed=120
15:11:54 P0-2: one 0.7s held press per outer position, in FLT
15:11:54   [1] UP (altitude+) -- before: mode=FLT course=95 alt=1658 alt_ref=B speed=120
15:11:56       after:  mode=FLT course=95 alt=1662 alt_ref=B speed=120
15:11:56   [2] DOWN (altitude-) -- before: mode=FLT course=95 alt=1662 alt_ref=B speed=120
15:11:58       after:  mode=FLT course=95 alt=1658 alt_ref=B speed=120
15:11:58   [3] LEFT, long (heading CCW) -- before: mode=FLT course=95 alt=1658 alt_ref=B speed=120
15:12:00       after:  mode=FLT course=93 alt=1658 alt_ref=B speed=120
15:12:00   [4] RIGHT, long (heading CW) -- before: mode=FLT course=93 alt=1658 alt_ref=B speed=120
15:12:01       after:  mode=FLT course=95 alt=1658 alt_ref=B speed=120
15:12:01 P0-3: speed tap sequence (short UP), reading speed_text
15:12:01   starting speed_text: 120
15:12:02   tap 1: speed_text = 150
15:12:04   tap 2: speed_text = 200
15:12:05   tap 3: speed_text = 250
15:12:06   tap 4: speed_text = MAX
15:12:07   tap 5: speed_text = MAX
15:12:07   speed_text stopped changing -- taking this as MAX
15:12:07 P0-4: press-release-to-readback latency
15:12:07   release -> readback change: 0.007s (before=MAX after=250)
15:12:07 P0-5: centre press x2 (ALT REF radar/baro toggle), menu open
15:12:07   before:        mode=FLT course=95 alt=1658 alt_ref=B speed=250
15:12:08   after press 1: mode=FLT course=95 alt=1658 alt_ref=B speed=250
15:12:09   after press 2: mode=FLT course=95 alt=1658 alt_ref=B speed=250
15:12:09 P0-7: FLT -> HVR speed criterion (tap speed to 0, watch mode_text)
15:12:29   speed at 0 for 15s with no automatic mode flip observed
15:12:29 closing the command menu (left open since P0-1)
15:12:30   after close: mode=nil course=nil alt=nil alt_ref=nil speed=nil
15:12:30 SEQUENCE COMPLETE
```

### What it shows — not yet explored

- **Arg 952 is not "pedals park"; it is the mirror of arg 852.** At rest (AI not flying) 852 = 0
  and 952 = 1. At "Request Aircraft Control" both animate over about 0.4 s, summing to 1.00 at
  every sample, and settle at 852 = 1, 952 = 0. **Production Batch A treats 952 ≥ 0.9 as
  "parked"**, so it reads "parked" whenever the AI is *not* flying, has a not-parked gap mid-
  animation, and reads parked again once 852 passes 0.9. **Arg 852 alone is the handover signal.**
  This also corrects BL-16's earlier note that "Request Aircraft Control" does not move 852: it
  does. Why the P1 telemetry read not-parked at all stays unexplained.
- **P0-6, the fix: the sink stopped, but the AI then climbed.** Flat for 2 s after the press, then
  +144 m in 17 s, about 11 m/s at the end, still climbing. The overlay read 20 s later:
  **`alt=1658 alt_ref=B`, against an actual 921 m MSL at the press.** The centre press did flip
  radar → barometric, but the barometric target it set was about 740 m too high. This is the
  pilot's own *"sometimes it has set something way incorrect"*, on the first try. **Pilot, same
  day:** *"this is what I mean with my earlier comment that the barometric alt setting may get a
  wildly incorrect initial value. That too is ED bug."* So both the sink and the wild barometric
  target are ED bugs to work around, not ours to fix.
- **P0-1 confirmed:** readback only with the menu open; toggling is repeatable.
- **P0-2:** a 0.7 s hold reads as long on every outer position: altitude ±4 m, course ±2°.
  Small steps, so long holds cannot correct a target that is hundreds of metres off.
- **P0-3:** short UP in FLT steps speed 120 → 150 → 200 → 250 → MAX. ("120" was where the AI
  started; whether it is also a step below 150 is not shown.)
- **P0-4:** release → readback change in 0.007 s, i.e. the next frame.
- **P0-5: with the menu open, a centre press does not toggle ALT REF** (B before, B after each of
  two presses). With the menu closed (P0-6) it did. **Pilot, same day:** *"it should. If it did not
  that is ED bug"* — a centre press with the menu open is meant to toggle the reference. **One
  cause on our side is not ruled out:** the probe presses and releases centre in the same frame (a
  zero-length press). That registered with the menu closed, but the open menu may need a real
  pulse (the probe's own `SHORT_PRESS_PULSE_S`, 0.15 s). Untested.
- **P0-7:** speed held at 0 for 15 s in FLT, no automatic switch to HVR.

## Explore, round 2 — the pilot's answers to the re-fly, verbatim

> *"* This is easier when the overlay is open. Therefore Petrobrain must make certain that the
> overlay remains open while AI controls flight. If Player closes it, Petrobrain must reopen it
> immediately. This is acceptable tradeoff.*
> *\* I'd prefer barometric alt, which means that after it's engaged the first thing to do is get
> is to a correct reading. After that it's easy.*
> *\* "Long presses take small steps." -> yes, but press and hold will have it keep incrementing
> the change. Single long press, no hold -> increment a bit. Press and hold for some seconds ->
> value keeps changing while hold lasts.*
> *\* "No automatic hover." -> that was ED's AI bug, it prioritized climbing to alt and only
> slowed down after reaching desired alt. Automatic hover transition works normally."*

## What this settles, as read (not yet a plan)

- **The command menu stays open for as long as the AI flies.** Petrovich opens it on takeover and
  reopens it at once if the player closes it. The pilot accepts the visual cost. That makes the
  AI's state readable all the time and removes the P0-1 limitation.
- **Barometric is the reference, and the first job after takeover is to make its target
  correct.** Takeover → centre press (radar → barometric, which also stops the sink) → read the
  target → if it is wrong, drive it to current MSL → then carry on to the pilot's goals.
- **Correcting the target is a press-and-hold, not repeated taps.** A 0.7 s hold moves ±4 m, but
  holding longer keeps it changing for as long as the hold lasts. So a large error is a closed
  loop: hold up or down, watch the readback, release on reaching the target. Stage P2's planned
  "release when readback reaches target" already has this shape. The rate while held is not
  measured.
- **P0-7 was not a real limit.** The AI was busy climbing to the wild barometric target and slowed
  only once it got there. FLT → HVR works normally.
- **Open question carried forward:** P0-5 found that a centre press with the menu open did not
  toggle the reference. The pilot says it should (ED bug, or our zero-length press). With the menu
  now always open, the one centre press after takeover must happen *before* the menu is opened,
  or that press needs testing with a real pulse. **Answered by the takeover probe below: a real
  0.15 s pulse toggles it. The failure was our zero-length press, not ED.**

## Takeover rehearsal probe — 2026-11-16

`Export.probe-ai-pilot-takeover.lua` on `fix/bl16-p0-probe-menu-open` (`5a3a15e9`), uploaded by the
pilot as `aircraft_layer_probe_ai_pilot_takeover.log`, verbatim apart from the banner lines:

```
15:38:52   t=5.0: arg852=0 arg952=1
15:39:04   t=17.1: arg852=0.90205132961273 arg952=0.097948655486107
15:39:04   t=17.1: takeover (arg 852 >= 0.9)
T1: takeover -- centre press (menu closed), then open menu
15:39:04   on takeover: mode=nil course=nil alt=nil alt_ref=nil speed=nil  agl=159.44555664062 msl=924.67248535156  arg852=0.90503454208374 arg952=0.094965443015099
15:39:05   +0.50s centre tap (menu closed)  msl=924.43096923828
15:39:05   +1.01s menu toggle (opening)
15:39:06   +2.01s read: mode=FLT course=81 alt=1662 alt_ref=B speed=150  actual msl=919.79803466797
15:39:06   baro target error: +742 m (target 1662, actual 920)
T2: correct the baro target to actual MSL (closed-loop hold)
15:39:06   start: target=1662 actual=920 error=+742 m
15:39:06   holding DOWN
15:39:20   released after 13.96s: reached tolerance
15:39:20   target while held: 0.0s:1662 0.5s:1662 1.0s:1654 1.5s:1646 2.0s:1640 2.5s:1632 3.0s:1606 3.5s:1582 4.0s:1556 4.5s:1530 5.0s:1506 5.5s:1480 6.0s:1456 6.5s:1430 7.0s:1406 7.5s:1380 8.0s:1354 8.5s:1330 9.0s:1304 9.5s:1280 10.0s:1254 10.5s:1230 11.1s:1204 11.6s:1180 12.1s:1154 12.6s:1130 13.1s:1104 13.6s:1078
15:39:20   mean rate while held: 43.3 m/s
15:39:21   after release: mode=FLT course=81 alt=1058 alt_ref=B speed=150  actual msl=1050.1588134766
15:39:41   20s trace (actual msl / target): 0s:1050/1058 2s:1058/1058 4s:1049/1058 6s:1047/1058 8s:1048/1058 10s:1049/1058 12s:1058/1058 14s:1060/1058 16s:1058/1058 18s:1059/1058
T3: hold rate -- UP 5s, then DOWN 5s
15:39:46   UP held 5.00s: 0.01s:1058 0.26s:1058 0.51s:1058 0.76s:1062 1.02s:1066 1.27s:1070 1.52s:1074 1.78s:1078 2.03s:1080 2.28s:1084 2.53s:1090 2.79s:1102 3.04s:1116 3.29s:1128 3.55s:1140 3.80s:1154 4.06s:1166 4.31s:1178 4.56s:1192 4.82s:1204
15:39:47   after release: mode=FLT course=81 alt=1214 alt_ref=B speed=150
15:39:52   DOWN held 5.00s: 0.01s:1214 0.26s:1214 0.51s:1214 0.77s:1210 1.02s:1206 1.27s:1202 1.52s:1198 1.77s:1194 2.03s:1192 2.28s:1188 2.53s:1182 2.78s:1170 3.03s:1156 3.29s:1144 3.54s:1132 3.79s:1118 4.05s:1106 4.30s:1094 4.55s:1082 4.80s:1068
15:39:53   after release: mode=FLT course=81 alt=1058 alt_ref=B speed=150
T2: correct the baro target to actual MSL (closed-loop hold)
15:39:53   start: target=1058 actual=1092 error=-34 m
15:39:53   holding UP
15:39:55   released after 1.90s: reached tolerance
15:39:55   target while held: 0.0s:1058 0.5s:1058 1.0s:1066 1.5s:1074
15:39:55   mean rate while held: 11.6 m/s
15:39:56   after release: mode=FLT course=81 alt=1080 alt_ref=B speed=150  actual msl=1089.4204101562
15:40:16   20s trace (actual msl / target): 0s:1089/1080 2s:1076/1080 4s:1073/1080 6s:1074/1080 8s:1081/1080 10s:1084/1080 12s:1081/1080 14s:1081/1080 16s:1081/1080 18s:1080/1080
T4: centre press, menu OPEN, 0.15s pulse
15:40:16   before: mode=FLT course=81 alt=1080 alt_ref=B speed=150
15:40:17   after pulse: mode=FLT course=81 alt=328 alt_ref=R speed=150
15:40:17   RESULT: open-menu centre pulse DID toggle ALT REF
15:40:17   restoring baro: close menu, centre tap, reopen
15:40:20   after restore: mode=FLT course=81 alt=1080 alt_ref=B speed=150
T2: correct the baro target to actual MSL (closed-loop hold)
15:40:20   start: target=1080 actual=1084 error=-4 m
15:40:20   within tolerance -- no hold needed
15:40:40   20s trace (actual msl / target): 0s:1084/1080 2s:1082/1080 4s:1082/1080 6s:1081/1080 8s:1081/1080 10s:1080/1080 12s:1080/1080 14s:1080/1080 16s:1080/1080 18s:1080/1080
T5: keep-open -- close the menu by hand; the probe reopens it
15:40:53   reopen #1: closed seen for 3 frames (0.011s), toggling open
15:40:53   reopen #1: reads open 0.006s after the toggle (0.017s after close)
15:40:54   reopen #2: closed seen for 3 frames (0.011s), toggling open
15:40:54   reopen #2: reads open 0.005s after the toggle (0.016s after close)
15:40:57   reopen #3: closed seen for 3 frames (0.012s), toggling open
15:40:57   reopen #3: reads open 0.005s after the toggle (0.017s after close)
15:41:00   reopen #4: closed seen for 3 frames (0.012s), toggling open
15:41:00 *** t=133.1: control taken back -- held press released, probe idle ***
```

### What it shows — not yet explored

- **The sequence works end to end.** Takeover on 852 → centre tap at +0.5 s (menu closed) → menu
  open → wild target found → corrected by a held press → the AI then holds within about ±10 m of
  its target for 20 s (both T2 traces).
- **The wild barometric target reproduced, and the same size:** +742 m (1662 against 920). The
  first re-fly had 1658 against 921, about +737. Ground elevation was about 765 m both times
  (MSL − AGL). *Possibly* the bad target scales with terrain height; two samples at one place
  cannot say.
- **The correction took 14 s, and the AI climbed meanwhile.** Actual MSL went 920 → 1050 while
  the target came down, so the AI ended up holding about 1058, some 140 m above the altitude it
  was handed. "Correct" here meant "match wherever the aircraft is when the loop finishes".
- **A held press has a profile, the same up and down (T3):**

  | while held | change per 0.25 s | rate |
  |---|---|---|
  | 0 – 0.5 s | none | dead time |
  | 0.5 – 2.3 s | 4 m | about 16 m/s |
  | after about 2.5 s | 12 – 14 m | about 50 m/s |

  After release the value moved on by about one more step (1204 → 1214 at the fast rate), so a
  release at "within 20 m" lands close; both corrections finished inside tolerance.
- **The open-menu centre press works with a real 0.15 s pulse (T4):** B → R, and the radar target
  it set (328 m) is close to the AGL at the time. So P0-5's failure was our same-frame press.
  BL-16's later voice "radar/barometric" toggle is reachable.
- **Toggling back R → B in flight gave a *correct* barometric target** (1080 against 1084). The
  wild value has so far appeared only on the first toggle after takeover.
- **Keep-open works:** each hand-close was seen in 3 frames and the menu read open again about
  17 ms after it closed. The fourth close coincided with the pilot taking control back.

## Explore, round 3 — the pilot's answers to the takeover probe, verbatim

> *"I found out that AI overlay has maximum radar alt of 700 m. Any value above that
> automatically switches to barometric. That is probably why the incorrect marometric setting
> would not let change to radar alt, because the alt was above 700 m AGL. When the desired alt
> (baro) is set to no more that 700 m AGL level, then center press swithces to radar alt.*
>
> *Q1 - handolver alt. The barometric initial bug is there sometimes, but I'm not sure why and
> when it happens. Workaround: hold down until current altitude at that moment is reached. That
> sends the value to DCS AI and stops the climb. Then continue adjusting the altitude value to
> what it was at handover moment. That way we get back to the correct altitude.*
>
> *Q2 - Yes, but with the caveat of my observation I wrote on the first line. -> If AGL is < 700m,
> yes do that to fix it.*
>
> *Q3 - merge."*

## What this settles, as read (not yet a plan)

- **The goal after takeover is the handover altitude** — actual MSL at the moment of takeover.
- **Radar reference is capped at 700 m AGL.** A target above that forces barometric, and a centre
  press cannot switch to radar. That explains why the wild barometric target could not be toggled
  away by hand.
- **The correction has two phases, per the pilot:** hold toward the *current* altitude and release
  there — *"That sends the value to DCS AI and stops the climb"* — then hold again toward the
  handover altitude. *Inference consistent with the probe: the AI applies a held value only on
  release. During the 14 s T2 hold the aircraft kept climbing toward the old target.*
- **The quick path (centre → radar → centre → barometric) is used only below 700 m AGL.** *Read
  carefully:* the limit is on the radar *target*, and the wild target was about 740 m above the
  handover altitude, so with that error a switch to radar would be refused at any height. The
  robust form is to try the toggle, read whether the reference actually became R, and fall back
  to the two-phase hold if it did not.
- **The probes merge to `main`** (pilot: *"merge"*).

## The barometric bug — the pilot's theory, verbatim (after the takeover fix merged, `b1b96738`)

> *"I may have figured out the AI barometric alt bug.*
> *AI takes the barometric alt from the copilot's altimeter, I think. If the pressure setting there
> is incorrect, the barometric alt value is wildly off.*
> *This means that when mission starts, Petrovich must set altimeter pressure setting to the actual
> pressure value from weather or briefing.*
> *Mi-24 copilot effectors: 'Baro Pressure Knob - CCW' decreases pressure setting and same but 'CW'
> increases. Press and hold until desired value."*

### What is already known — checked 2026-11-16, not yet a plan

- **The numbers fit the theory.** Both wild targets were about +740 m (1662 vs 920; 1658 vs 921),
  with ground about 765 m below both times. A pressure setting off by about 88 hPa shifts a
  barometric altimeter by about 740 m (~8.4 m per hPa near sea level) — roughly the QNH/QFE gap for
  a field at that elevation. *Consistent with: the copilot's altimeter set to the wrong reference;
  the AI adopting its reading as "current altitude" and then flying to that number on true
  altitude.* Two samples from one mission; not proven.
- **The effector exists in the generated reference** (`body-layer/config/sequences/mi-24p/
  switch-reference.md`, "Device 42 -- BAROALT_O"): `ALTIMETER-KNOB-OP-PTR`, "Operator Baro
  Pressure Knob", operator seat, `default_axis`, command 3001, arg 788, "0 to 1 continuous (gain
  0.6)". The pilot's own altimeter is device 41 (`ALTIMETER-KNOB-PTR`, arg 18). **How a write
  turns the knob (step per write, or rate while held) is not measured,** and the CW/CCW key
  bindings the pilot names are input commands, not yet mapped to clickable actions.
- **No readback of the pressure setting is known.** Arg 788 is the knob's own rotation, not
  necessarily the value in the altimeter's pressure window. A closed-loop "hold until the desired
  value" needs a gauge arg (or other readout) for the window. **Unknown; needs a probe.**
- **The mission's pressure has a proven route.** `aircraft-layer/dcs-export/petrobrain-mission-
  start-hook.lua` already reads `env.mission.theatre` through `net.dostring_in("scripting", ...)`
  at each mission start; the same route can read the mission weather's QNH (`.miz` stores
  `weather.qnh` in mmHg). The field name is standard in `.miz` files but not yet read live here.
- **The trigger exists.** The effector-sequence engine already has `mission-start` and
  `mission-start-in-air` triggers with sequence files (`body-layer/config/sequences/mi-24p/
  mission-start.md` sets two switches today). A "hold until the window reads X" step is not a row
  type the engine has.
- **The takeover fix stays as the safety net** either way: if the altimeter is set right, the
  wild target should stop appearing and the correction finds nothing to correct.

### Explore — the pilot's answers, verbatim

> *"the altitude thing:*
> *1 use QNH for copilot*
> *2 set at mission start, both ground start and air start*
> *3 moves steadily*
>
> *ok for asking windows session"*

Settled, as read (not yet a plan):

- **Petrovich sets the copilot's (operator's) altimeter to the mission's QNH,** so it reads altitude
  above sea level, consistent with what the AI's barometric hold flies.
- **At mission start, both ground and air starts.** The existing `mission-start` trigger fires on
  both.
- **The knob moves the setting steadily while held** (no speed-up like the AI wheel's holds), so a
  closed-loop hold-until-value is straightforward once the window can be read.
- **Next: the Windows session looks up the operator altimeter's readout args and knob behaviour in
  the Mi-24P cockpit files,** before a probe or a plan.
