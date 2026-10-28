# Sortie feedback — 2026-10-28

Captured before any diagnosis, per root `CLAUDE.md` "Flight feedback is captured, then explored,
then planned". Branch flown: `main` (`d641ca3b` or later).

## 1. HUD elevation-limit probe: up, but never down

Probe `aircraft-layer/dcs-export/Export.probe-9k113-hud-elevation-limits.lua`, card
`docs/acceptance/2026-10-27-9k113-hud-elevation-limits-probe.md`. **User, verbatim:**

> *"probe: sight moved up, but did not come down"*

**First reading of the code (not run, log not yet seen).** The edge check reverses for
`REVERSE_CHECK_S = 1.0` s at the same rate it seeks. But by the time the 1 s no-change window has
filled, the head has already gone ~0.5° past the edge (the mark is clipped, the head is not), and
the rate command's own response lag eats part of the reversal. So the reversal can end still past
the edge, 555 never moves, the check calls it a stall and resumes pushing up: about +0.5° each
round, never back inside. That predicts exactly a cross that goes to the top edge and stays there,
with repeated `stall, not an edge` lines in the log. To confirm: the log
`Saved Games\DCS\Logs\aircraft_layer_probe_9k113_hud_elevation_limits.log`.

**Log read (same day) — the first reading above was WRONG.** No `plateau candidate` and no
`stall` line anywhere: the probe never left `SEEK_POS`. 555 climbed 0.831 → 1.00000 by t ≈ 44.3 s
(≈ 0.0163 raw/s at 0.5°/s commanded) and then sat at exactly **1.00000** for 70 s while the probe
kept pushing. Cause: `push_hist` trimmed the history on its *first* sample, which removed exactly
the sample `window_flat` needed to prove the window was a full second long, so "flat" could never
be true. Replaying the flown log through the probe's own two functions: old code "never flat", fixed
code "plateau at t=44.98 555=0.99883".

Measured on the way: **the top clip is the arg saturating at 1.00000**; 556 tracks 555 to ~0.0005.
The reversal concern of the first reading is still real (the head is ~0.5° past the clip once the
1 s window fills), so the reversal now runs until 555 moves, giving up after 10 s.

**Status:** fixed (`fix/9k113-el-probe-reverse`), re-flown (§2).

## 2. HUD elevation-limit probe, re-flown: both edges found

Log: `aircraft-layer/research/logs/2026-10-28/aircraft_layer_probe_9k113_hud_elevation_limits.log`
(second run in the file, from 11:31:29). `PROBE DONE up=0.99856 down=0.27988`.

| | 555 raw | reached at | confirmed by reversal |
|---|---|---|---|
| start (OBSERV + 15 s) | 0.829 | t = 37.8 s | — |
| top clip | **1.00000** (arg saturates; plateau mid 0.9986) | t = 49.0 s | moved at t ≈ 50.6 s |
| bottom clip | **0.2784** (not 0: a real limit, not saturation) | t = 102.1 s | moved at t ≈ 103.1 s |

- Travel at the commanded 0.5°/s: **~5.6° up** from the start position, **~26° down** from the top
  (~20° below the start). The rate is commanded, not measured, so these degrees are only as good
  as the AI-axis rate; 555's slope was 0.0162/s going up and 0.0140/s going down.
- **The field is strongly asymmetric** about where the sight started, and far larger downward than
  the ±4.3° azimuth half-field. Production `Export.lua` carries one symmetric
  `ASP17_FIELD_EL_HALF_DEG = 4.3` placeholder with `MARK_BORESIGHT_EL = 0.556` and
  `MARK_DEG_PER_UNIT_EL = 1/0.039`, all unmeasured; this run does not fit a ±4.3° field around 0.556.
- 566 (azimuth mark) drifted 0.43 → 0.33 during the descent and sat at exactly **0.33333** from
  t ≈ 84 s on, which looks like an azimuth clip reached as a side effect.
- Open, for the pilot: where the cross stood on the glass at each end, whether the bottom stop was
  the HUD's bottom edge, and where it was at the start (boresight or not).

**Pilot, verbatim:**

> *"1 about boresight.*
> *2 below what I can normally see as pilot, but apparently the ASP-17 crosshair can move that low*
> *3 a little, but that is from the helicopter movement"*

So: **555 boresight ≈ 0.829** (production's placeholder `MARK_BORESIGHT_EL = 0.556` is far off).
The top clip (1.0) is ~5.6° above boresight; the **bottom readback limit (0.278) lies below the
pilot's normal view of the HUD** — readable, but not seen. The sideways drift was the airframe.

**Status:** measured; observations in.

## 3. Same probe, landed (no airframe movement)

**User, verbatim:** *"Tried again. New log. This time I landed first, so no airframe movement."*
Log: `aircraft-layer/research/logs/2026-10-28/aircraft_layer_probe_9k113_hud_elevation_limits_ground.log`.
`PROBE DONE up=0.99850 down=0.40655`.

- **Start 555 = 0.833** (air run 0.829): boresight ≈ 0.83 holds.
- **Top**: linear climb, 0.0139/s, clip at 1.0 after ~12 s (air: 0.0162/s, ~11 s). Same edge.
- **Down**: linear at −0.0139/s from the top to 555 ≈ 0.78 (t ≈ 147 s, slightly below boresight).
  Then, with the command unchanged, a **step change**: 555 suddenly drops at −0.036/s, and 566
  starts moving sideways (0.488 → 0.63) at the same instant, both then decaying smoothly to a
  stop at 555 = 0.407 / 566 = 0.63 — an exponential settle, not a slew. The air run had no such
  break: linear all the way to 0.278 with 566 fixed by airframe motion only.
- Not understood. Candidate readings, none tested: the head reaching a limit relative to the
  airframe (on the ground the nose sits higher); the sight's line of sight meeting the ground close
  by; something done in the cockpit at that moment.

**Pilot, verbatim, on the break:** *"at that ~30 s down it suddenly started jerkingly moving
right in steps. That was odd."* Matches the log: 566 rises in steps (2 s bins alternate ≈ +0.005/s
and ≈ +0.001/s) from the same instant 555 speeds up. Something other than our command moved the
sight; not identified. Seen only on the ground, only below boresight; the airborne run was clean, so
its bottom limit (0.278) is the one taken.

**Status:** measured; the ground-only break recorded, not investigated.
