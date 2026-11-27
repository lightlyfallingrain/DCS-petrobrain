# Mode 2 feedback 2026-11-27 — recovery from "align for launch"

Branch context: mode 2 (AI-pilot wheel) is on `main` (BL-16 P3+P4, merged `fefe8cea`). Item:
`[[BL-B139]]`.

## User's words, verbatim

> Mode 2, recovery from align-for-launch.
>
> * DCS AI needs a alt and speed change to react. Therefore, on recovery:
>    * first set alt to pre-alignment value. If already at that value, step it down a bit (enough
>      that the value changes, no more is needed) and then back to desired value.
>    * then set speed to pre-alignment value. If already at set value, this too needs first a step
>      away from set value (down) and then back to set value.

## Reading

- DCS's AI pilot acts only when its set altitude / set speed **changes**. If recovery's target equals
  what the wheel already shows, nothing is pressed and the AI does not react.
- Order stays as built (altitude, then speed — `seed_recovery_goal`, Decision 26).
- When the target equals the displayed value: step **down** by the smallest amount that changes the
  displayed value (one press / one increment), then back to the target. No more than that.
- Scope: recovery from align-for-launch only, as stated.

## Second item — "speed 250" gives MAX (`[[BL-B140]]`)

> Mode 2 bug:
> - command "speed 2 5 0" gets me 'speed max', though it should get 'speed 250'. There is 250 speed
>   option in AI overlay.
