# 2026-11-14 — 9K113 hands-off calibration sortie

Flight stamp `20261114-215821` (collector session 21:57:55, mission t 0–1173 s). `aircraft_layer_sight_hands_off.flag`
active, so Export.lua did not write the AI axes. Analysis: `aircraft-layer/research/2026-11-14-9k113-mark-staleness-hand-hold.md`.

## The pilot's account, verbatim

> at about T+8 set target (BMD1 on map)
> at T+12 mins held target in 9K113 sight myself for a while, distance about 1 km, self 580 m AGL hover
>
> Same target unit, distance 3 km
> Manually held at 9K113 sights at about T+19:30
> self at 498 m ALG, hover

## Matched to the logs

| hold | mission t | target | range | AGL | target vs airframe |
|---|---|---|---|---|---|
| 1 | ≈ 680–780 s | BMD-1 `Ground-51-1` (id 16790016) | 1.12–1.15 km | 582 m | az +6…+12°, el −30…−32° |
| 2 | ≈ 1080–1173 s | same unit | 2.98–3.00 km | 506 m | az −1.5…+3°, el −9.8…−10.9° |

Unit identity: matched on azimuth to the session's LoGetWorldObjects dump. The account's
distances and heights agree with this to within 10 m AGL.

## Logs (gitignored, local to the Windows machine's WSL checkout)

`body-layer/logs/`: `dcs-slew-trace-20261114-215821.jsonl`, `dcs-speech-20261114-215821.jsonl`,
`aircraft_layer_slew_trace-20261114-215821.log` (copied from Saved Games; **this flight is the last run in
the file, from line 324554** — the file held 25 runs), `aircraft_layer_debug-20261114-215821.log` (this
session from line 160387). **No `--detection-trace` or belief-truth log was written this flight**, so
truth came from the debug log's world-object dump. The units were static, so that is sufficient here.
