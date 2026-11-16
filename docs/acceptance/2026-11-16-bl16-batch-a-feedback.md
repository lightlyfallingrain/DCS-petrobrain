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
