# Sortie feedback — 2026-10-26

Captured before any diagnosis, per root `CLAUDE.md` "Flight feedback is captured, then explored,
then planned". Branch flown: `main` (user, same day) — `fee96cdc` at the time.

## 1. Optics debug views disagree

**User, verbatim:**

> *"# flight*
>
> *debug views of optics. they really do not match"*

Screenshot: `2026-10-26-optics-debug-views.png` (this directory) — `--eyesight-view` (top-down,
5 km radius) above, `--pov-view` (forward azimuth/elevation) below, same poll.

**What the screenshot shows** (read off it, not diagnosed):

| | `--eyesight-view` (top) | `--pov-view` (bottom) |
|---|---|---|
| optic | `sight_wide` | `sight_wide` |
| where it says he is looking | `gaze: 3_oclock centre=+90 deg +/-15 deg`; the `'` sector is drawn to the right of `^` | `boresight az=+6 el=+1`; grey field-of-view block at about 0…+10 az, −5…+7 el |
| contact `U` (watched, orange) | up and slightly left of `^`, roughly 1 km | az ≈ +6, el ≈ −2, inside the grey block |

So, at face value, two disagreements:

- **Direction of view**: 3 o'clock (+90°) in the top view, about +6° in the POV view, for the same
  optic in the same poll.
- ~~**The contact's bearing**~~ — on a closer read the `U` sits slightly right of `^` and ahead
  in the top view too (about +10°), so it agrees with the POV view's +6° within the top view's
  character resolution. Not a disagreement.

**First reading of the code (2026-10-26, not run, not yet explored with the user).** The two views
take "where he looks" from different places. `--pov-view` uses the 9K113 sight head's direction
whenever the optic is a sight (`body.py` `_render_pov_frame`). `--eyesight-view` always draws
`gaze_at(runner.scan_plan)`, the naked-eye scan plan (`body.py` `_render_eyesight_frame`). Perception
itself does not use that plan while on the sight: `_apply_active_gaze` replaces it with a fixed
look at the sight head's direction. So this looks like the top view drawing a stale naked-eye scan
sector, not Petrovich looking in two directions at once.

Also on screen, not commented on by the user: `live LOS coverage: 0/1 gate-4 evaluations had no
live verdict this sortie`.

**Explored with the user, 2026-10-26.** Direction, verbatim:

> *"both should show what Petrovich is really looking at and with what optic. Scan *plan* is
> useless data unless he actually looks there. I need to know where he is looking."*

So both views draw the **actual** look direction and the optic in use, taken from the same place
perception takes it — never the scan plan as such. When he is scanning with the naked eye the plan
*is* where he looks; on the sight, the binoculars, or a fixed `look <o'clock>`, it is not.

**Status:** explored; going to a fix.
