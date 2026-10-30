# 9K113 hands-off elevation calibration flight

<!-- doc-provenance:start -->
**Topics:** #cockpit-manipulation #9k113 #sight-slew
**Flight for:** [[BL-B80]]
<!-- doc-provenance:end -->

**Branch: `main`** (merged `feature/9k113-hands-off-switch`, DoD-passed 2026-10-30).
`git checkout main`, then redeploy `aircraft-layer/dcs-export/Export.lua` to
`Saved Games\DCS\Scripts\Export.lua` per `aircraft-layer/WORKFLOW.md`.

**Why.** 2026-10-30's sortie showed the ATGM mark correct in azimuth but clearly low in
elevation. One observation cannot separate a scale error from a boresight error in
`MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL` — both shift a single reading the same direction. Your
own choice: hand-slew the real 9K113 to two known depression angles with Petrovich's own per-frame
servo write suppressed, rather than walk the ASP-17 instead (*"I can point the 9K113 by hand -
Petrovich must not write axis values then. This would be the most reliable measurement of 9K113 vs
ASP-17 alignment"*).

## What is not testable here

This flight exercises the hands-off switch itself and gathers calibration data — it does **not**
verify the corrected scale/boresight fixes an ATGM shot. That needs a second, follow-on flight once
the numbers from this one are applied. The one required fix the Reviewer flagged (closing the
generic `cockpit_switch` write channel against the same AI-axis commands while hands-off) was
declined as unnecessary for a short-lived testing aid — nothing in today's body-layer switch
sequences can reach that channel's pointing axis — so this is not a concern to watch for in flight,
just recorded as accepted risk.

## Setup (Windows)

1. Before launching the mission, create the empty flag file:
   `Saved Games\DCS\Scripts\aircraft_layer_sight_hands_off.flag`
   (checked once at `Export.lua` load — no mid-sortie toggle; if you forget it, land, create it,
   and restart the mission).
2. Also create `Saved Games\DCS\Scripts\aircraft_layer_slew_debug.flag` for the per-frame raw
   555/566 + gimbal trace (`aircraft_layer_slew_trace.log`), and `aircraft_layer_debug.flag` if you
   want the one-line load-time confirmation (`9K113 hands-off switch is ACTIVE...` in
   `aircraft_layer_debug.log`).
3. Launch `body.py` with `--slew-trace <path>` so the ownship attitude/position and per-poll servo
   state are logged alongside the Lua trace (see `body-layer/CLAUDE.md`, "## What this is" →
   `--slew-trace`).
4. Air start, guidance unit warm. OBSERV on. DCS AI Petrovich overlay off (no bearing on this
   test, but keep the usual posture).
5. **Check `aircraft_layer_debug.log` (or the console) for the hands-off confirmation line before
   you trust the flight** — if it never activated (flag file missing/misnamed/wrong folder), the
   servo will still be writing and every reading below is contaminated. See do/expect/record below.

## Do / expect / record

1. **Do:** hover near a ground target at a known, measurable depression angle (e.g. a target at a
   known range with ownship at a known height AGL — your choice of method for getting a reliable
   angle). Hand-slew the 9K113 by its own player-axis control onto that target and hold steady for
   a few seconds.
   **Expect:** the sight holds where you put it — no drift, no fight from an invisible AI-axis
   write.
   **Record:** the target, the geometric depression angle you computed, and roughly when (sim time
   or wall clock) you held it, so the log rows can be matched up afterward.
2. **Do:** repeat at a second target with a clearly different depression angle (the plan calls for
   "near and far target" — pick two angles far enough apart that scale and boresight stop being
   confusable).
   **Expect:** same — a steady hold, no contest with Petrovich's servo.
   **Record:** same as above for the second point.
3. **Do:** glance at the raw mark readback if you have any way to see it (debug overlay, prior
   knowledge of the 555/556 args) while holding each point.
   **Record:** anything you can read off directly — not required, the logs are the real source of
   truth, but a cross-check is useful.

**The prize: the two held (target, true depression angle, mark reading) triples.** Everything else
downstream — the corrected `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL` — is derived from these two
points and nothing else.

## Bring back

- The two depression-angle/target pairs above, and roughly when you held each one.
- Whether the hands-off confirmation log line actually appeared at mission start.
- Whether the 9K113 ever felt like it was fighting your input (a sign the flag did not take
  effect) — should not happen if the confirmation log appeared, but worth saying either way.
- `Saved Games\DCS\Logs\aircraft_layer_debug.log`, `aircraft_layer_slew_trace.log`, and
  `body-layer`'s `--slew-trace` output file.
- Anything that surprises you is worth more than anything on this list.

## Results

*(to be filled in after the flight)*
