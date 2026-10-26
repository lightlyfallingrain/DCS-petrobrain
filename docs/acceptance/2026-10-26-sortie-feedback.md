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

**Status:** explored; fixed and merged (`fix/optic-views-actual-look`, `2a04e947`).

## 2. Scanning and optics look right now; simulated and DCS 9K113 drift apart

Same day, after the view fix, on `main`. **User, verbatim:**

> *"Now that the debug views are fixed, the scanning and optics logic seems to work fairly well.
> Though I only did a quick test.*
>
> *However, the simulated and DCS 9K113 do not stay in sync, there's a lot of error it seems.*
>
> *I flew with AI overlay off. What did we establish about reading the 9K113 actual pointing
> direction? It was in some way dependent on what DCS AI is doing?"*

**Already established** (`plans/9k113-sight-pointing/explore-notes.md`, `plan.md`, `dod-check.md`;
`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`):

- The only true readback of where the DCS sight points is the **ASP-17 mark** (args 566 az / 555
  el), valid only while the sight's line is inside the ASP-17 field (±~4–6°). 874/876 echo the
  demand and are not a position.
- The drive channel is the 9K113 AI axis: a **rate** command with a deadzone, obeyed only when the
  written value changes frame to frame (dither), and **intermittently ignored** — 3–100+ s,
  invisibly — by DCS.
- Probe run 11: the DCS AI overlay is **not required**. Flying with it off is the supported case.
- User decision: Petrobrain's simulated sight *is* Petrovich's sight. Outside the ASP-17 field the
  DCS sight is driven **open loop** on an estimate; inside it, closed loop on the mark (re-anchored
  whenever the mark is valid). So drift outside the field is expected and cannot be measured from
  inside DCS.

**User, answering (same day), verbatim:**

> *"I observed the cross hair moving in HUD when the debug view showed that the simulated sight
> was pointing clearly to the side.*
>
> *Driving the sight is not the problem, not having the readback channel is. We have no way of
> knowing the drift outside the HUD area and that is a small area.*
>
> *A workaround is needed"*

So: the error was seen **inside** the ASP-17 field (DCS mark in the HUD while the simulated sight
was well off to the side). The ask is not a better drive but a **workaround for the missing
readback outside the field**.

Already ruled out as readbacks (`aircraft-layer/research/2026-10-21-9k113-slew-readback-probe-findings.md`):
args 874/876 (echo), an all-argument scan of 3001 cockpit + 3001 draw args (nothing tracks the
head), device 7 getters (none), `list_indication(0)` (static text).

**Explore, 2026-10-26.** Workarounds offered: A home against the gimbal stop, B re-fix on each
pass through the field, C re-home before an attack, D detect DCS ignoring the drive by the mark not
moving. **User, verbatim:**

> *"The problem with this is that a might turn the helicopter towards where the sight is pointing.
> If the cross hair is wildly off target, so will be my turn.*
>
> *One option I'm thinking is only moving the real DCS sight when the target is within HUD area.
> Use simulated sight elsewhere and not keep moving the actual sight. Then when the simulated sight
> is within the HUD region, then keep the actual sight in sync with the simulated one.*
>
> *This would then allow attack runs where the sight points to the target, but does not drift to
> unknown angles. It's clunky, but we can't read the sight angles by any means."*

So the pilot **steers by the ASP-17 mark**, and a mark that is wrong is worse than none. Direction:
the real DCS sight never leaves the region where the mark reads it; outside that region only the
simulated sight moves.

Parking options offered: 1 boresight, 2 field edge nearest the simulated sight, 3 last valid
position. **User, verbatim:**

> *"Option 2, that is the closest to what it should behave like.*
>
> *The way it works is the ASP-17 shows direction to 9K113 sight by parking the cross hair to edge
> of HUD. Like a line drawn from boresight point in HUD to 9K113 position outside visible HUD area
> and then the cross is shown where that line intersects the HUD limits. We could use that logic,
> but achieve it by moving the sight to that position. Keep it just within the HUD limit so that we
> do get a read back value. The when the simulated sight moves within HUD, keep the two synced.
> That'd be a very close approximation of the sight behaviour from the pilots perspective."*

**Decided.** Real DCS sight goal = the simulated sight's direction **projected radially from
boresight onto the field limit, inset just inside it**, so the mark stays readable (unclipped) and
the loop stays closed. Inside the field the goal is the simulated direction itself. The real sight
is always closed loop on the mark; open-loop pointing outside the field is dropped.

```
   sim sight (outside) ●
                      /
        +-----------/--+   ASP-17 field
        |         ○    |   ○ = real sight goal, inset from the limit
        |       /      |
        |     ⊕        |   ⊕ = boresight
        +--------------+
```

Inset margin, **user, verbatim:** *"As close to edge while still keeping the read back values."*

Open for the plan, not for the user: measuring that margin (clip vs. valid; elevation 555 clip edges
were never measured, `plans/9k113-sight-pointing/plan.md` risks), the field shape the projection
uses, and what happens when DCS ignores the drive inside the field (the mark shows it now).

**Clarified same day, verbatim — load-bearing for the plan:**

> *"'parks where the line from boresight toward the simulated sight meets the field edge' -> yes
> and it keeps it at the intersect point as the simulated sight moves and thus the intersect point
> moves."*

So the park is continuous, not a one-shot action: the real sight slides along the field edge,
tracking the intersection point as the simulated sight moves, for as long as the simulated sight
stays outside the field.

**Status:** explored; planned (`plans/9k113-sight-pointing/plan.md`, "v3 (2026-10-26)").
