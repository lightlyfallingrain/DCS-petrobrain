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

## Open for the explore conversation

To be settled with the pilot before any plan.
