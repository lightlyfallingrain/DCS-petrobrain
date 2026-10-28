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

**Status:** fixed (`fix/9k113-el-probe-reverse`), to re-fly.
