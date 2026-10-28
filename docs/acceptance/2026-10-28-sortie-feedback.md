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

**Status:** captured; log requested.
