# Slip-ball calibration — test card (2026-11-20)

**Branch to fly: `main`**, once this batch is merged. `git pull` in the repo root.

**What this measures:** which way the slip-ball reading moves, and how far, so the pedal law can
keep the ball centred. Petrovich does not use the reading yet: **you fly this one yourself**, no
"you have controls". Source: `aircraft-layer/research/2026-11-20-slip-ball-recon.md`.

## Setup

Air start, the seat you normally fly from, straight and level, about 150 km/h, safe height.

Readout, from the Mac terminal running this session (one line every half second; Ctrl-C to stop).
The collector address comes from `run-scripts/petrobrain.env`:

```sh
source run-scripts/petrobrain.env
while true; do curl -s http://$DCS_COLLECTOR_IP:7791/flight_control/latest | python3 -c "import sys,json; d=json.load(sys.stdin) or {}; print(d.get('t'), d.get('fc_slip_ball_pilot_raw'), d.get('fc_slip_ball_operator_raw'), d.get('fc_slip_ball_lo_api'))"; sleep 0.5; done
```

Columns: sim time, pilot ball (arg 943), operator ball (arg 784), DCS's own `LoGetSlipBallPosition`.

## Steps

1. **Centred.** Ball in the middle, wings level, no turn, about 5 s. Note the three values.
2. **Left pedal.** Press a moderate amount of left pedal and hold about 3 s. Note **which way the
   ball moved** (left/right of centre) and the values. Release, let it settle.
3. **Right pedal.** Same with right pedal.
4. **More pedal.** If it's safe, repeat one side with more pedal, to see whether the reading stops
   growing before the ball reaches the end of its tube.

## Report back

- The values when centred.
- For each pedal step: which way the ball moved, and the values.
- Whether the third column (DCS's own call) moved with the ball, stayed constant, or was `None`.
- Anything odd: the readout not moving at all (then 943/784 are the wrong instruments), or only
  one seat's value moving.
