# Sortie feedback — 2026-10-26

Captured before any diagnosis, per root `CLAUDE.md` "Flight feedback is captured, then explored,
then planned". Branch flown: not stated (ask).

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
- **The contact's bearing**: roughly 11–12 o'clock in the top view, about +6° in the POV view.
  Rough estimate from character positions, and it depends on whether `^` in the top view is the
  nose (heading-up) or north (north-up) — not yet checked.

Also on screen, not commented on by the user: `live LOS coverage: 0/1 gate-4 evaluations had no
live verdict this sortie`.

**Status:** captured, not yet explored.
