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

## Second sortie, same evening — stamp `20261114-224028`

> at about T+5min commanded engage with missiles on BTR60. Distance about 1km
> at about T+5:30 - 6:00 held target manually in 9K113
> after that, around T+7 min manual slew to 9K113 limits, left, right, up, down.

| phase | mission t | matched to |
|---|---|---|
| engage (voice "engage missiles") | 302 s | `dcs-speech` |
| hand-hold | ≈ 332–377 s | BTR-60 `Ground-6-1` (id 16779520), 1.06–1.10 km, **189 m AGL**, el ≈ −11° |
| sweep | 376–435 s (log ends) | azimuth to both mark clips; elevation only 0.517 → 0.743 raw (−11.4° → −3.3°) before the log ends |

Logs: `aircraft_layer_slew_trace-20261114-224028.log` (this flight from line 436119),
`aircraft_layer_debug-20261114-224028.log` (session from line 166331), plus the body-layer jsonl.
No detection trace again.
