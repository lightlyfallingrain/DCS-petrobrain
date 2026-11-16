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
  pilot's own *"sometimes it has set something way incorrect"*, on the first try.
- **P0-1 confirmed:** readback only with the menu open; toggling is repeatable.
- **P0-2:** a 0.7 s hold reads as long on every outer position: altitude ±4 m, course ±2°.
  Small steps, so long holds cannot correct a target that is hundreds of metres off.
- **P0-3:** short UP in FLT steps speed 120 → 150 → 200 → 250 → MAX. ("120" was where the AI
  started; whether it is also a step below 150 is not shown.)
- **P0-4:** release → readback change in 0.007 s, i.e. the next frame.
- **P0-5: with the menu open, a centre press does not toggle ALT REF** (B before, B after each of
  two presses). With the menu closed (P0-6) it did. Centre press means different things depending
  on menu state.
- **P0-7:** speed held at 0 for 15 s in FLT, no automatic switch to HVR.
