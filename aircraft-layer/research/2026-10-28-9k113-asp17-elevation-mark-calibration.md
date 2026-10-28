# 2026-10-28 — ASP-17 elevation mark (arg 555): boresight and clip edges, measured

Probe `aircraft-layer/dcs-export/Export.probe-9k113-hud-elevation-limits.lua`, card
`docs/acceptance/2026-10-27-9k113-hud-elevation-limits-probe.md`. DCS 2.9.30.28738, pilot seat,
DCS AI overlay off, AI elevation axis commanded at 0.05 (nominally 0.5°/s, `v_axis_velocity =
rad(10)/s`) with the production dither on. Logs: `research/logs/2026-10-28/` (air run: second run
in `aircraft_layer_probe_9k113_hud_elevation_limits.log`; landed run: `..._ground.log`). Flight
account and the pilot's own observations: `docs/acceptance/2026-10-28-sortie-feedback.md` §1–§4.

## Measured

| quantity | value | evidence |
|---|---|---|
| boresight (sight at OBSERV + 15 s) | **555 ≈ 0.83** | 0.829 air, 0.833 ground; pilot: *"about boresight"* |
| top clip | **555 = 1.00000** (the arg saturates) | both runs, confirmed by reversal |
| bottom readback limit | **555 = 0.278** | air run, linear descent into a flat stop, confirmed by reversal; below the pilot's normal view of the HUD |
| 556 | tracks 555 to ~0.0005 | both runs |
| slope at 0.05 command | 0.0162 / 0.0139 raw/s up, 0.0140 / 0.0128 down (air / ground) | |

The landed run's bottom (0.407) is **not** a limit: at 555 ≈ 0.78, with the command unchanged, the
mark sped up and 566 began stepping right (*"suddenly started jerkingly moving right in steps"*,
pilot), then both settled exponentially. Not a slew; cause unknown; seen only on the ground.

## Not settled: the degree scale

The degrees per raw unit are **not measured** — only implied, two incompatible ways:

- **From the commanded rate** (0.5°/s): ≈ 0.030 raw/°, top +5.7°, bottom −18.4°. But −18.4° is
  past the sourced gimbal limit of −15° (`body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`),
  which the head cannot exceed.
- **If the bottom stop is the −15° gimbal**: ≈ 0.037 raw/°, top +4.6°, and the real slew rate
  ≈ 0.39°/s. Close to azimuth's measured 0.039.

The flat stop's shape does not tell the two apart. Settling it needs a known angle (a pitch change
read against the attitude), not a commanded rate.

**Shipped: 0.037** (user, 2026-10-28, on the reviewer's recommendation): physically consistent with
the gimbal, near azimuth's 0.039. Field becomes ≈ +4.6° / −14.9° around boresight 0.83.
