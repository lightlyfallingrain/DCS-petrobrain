# 2026-10-21 — BL-B66 effectors sortie: results

Card: `docs/acceptance/2026-10-21-bl-b66-effectors-sortie.md`. Flown on `main` with the
`safe_call` ordering fix (`cd6ae472`) deployed.

## Pilot's report, verbatim

> *"1 - 6: pass."*
>
> *"5 - check log folder, hand slew to limits at full slew axis deflection. Then smaller and tiny
> movements."*

So all six flight blocks passed. Block 5 (hand slew) was flown as: full deflection to the limits,
then smaller movements, then tiny ones.

## Logs

- body-layer per-poll: `body-layer/logs/dcs-slew-trace-20261021-213454.jsonl` (358 rows),
  with `dcs-detection-trace-` / `dcs-belief-truth-` of the same stamp.
- The Windows per-frame `aircraft_layer_slew_trace.log` was not brought over.

## Analysis

**The sight-position readback never moved.** All 358 rows have `raw_sight_az = raw_sight_elev =
0.0`, including the 113 s with OBSERV on (t 442–555), when the hand slew was flown.

**This is almost certainly DCS returning 0, not the pipeline dropping values.** Args 874/876 travel
in the same Export.lua line as OBSERV (886). That line reached body-layer, because
`observ_observed` flipped to true on time. Export.lua resends the line when 874 or 876 moves by more
than 0.0005, so a moving head would have produced fresh lines carrying non-zero values. None
arrived.

**Against that:** the 2026-10-17 probe saw 874 move (0 → 0.165 → 0.33) when *the script* wrote the
player axis (3025/3026) with `SetCommand`. So DCS can report the head moving. What differs today is
the input: the pilot's own hardware slew, not a script write.

**Pilot's answers** (verbatim, 2026-10-21):

> *"1 - yes"* (the head visibly moved in the sight view)
> *"2 - copilot seat. In DCS the bindings are under Mi-24P CPG Aiming Station → Aiming Station
> Left/Right (Joystick), Aiming Station Up/Down (Joystick)"*

So the head moved and 874/876 still read 0. The input was flown from the copilot (CPG) seat with
the CPG Aiming Station joystick axes. The 2026-10-17 probe wrote 3025/3026 by script from the
pilot's seat.

**Per-frame Windows log** (`aircraft_layer_slew_trace.log`), pilot's reading: *"observ changed
value 1 or 0. az and elev 0 always"*. **So Export.lua itself read 874/876 = 0 every frame while the
head moved.** The pipeline is cleared: DCS does not report CPG-seat hand slew on 874/876.

**Consequence for `[[BL-B80]]`:** the slew loop's planned feedback term (874/876) does not exist
in the case that matters. It needs another source of sight position before any controller can be
designed. Candidates for a probe:

- an all-argument diff scan during a hand slew;
- the 9K113 device's `get_param_handle` parameters;
- the camera orientation while in the sight view.

Seat (pilot vs CPG) is the leading suspect for why 2026-10-17 differed.

**Correction, same day: the case above is not one Petrovich is ever in.** The user's rule, verbatim:

> *"If player sits in copilot seat, slew is his responsibility. This is not implemented or even
> planned yet, but as a general rule, Petrovich can only operate the controls of the cockpit he
> occupies. That is the opposite of what player occupies. So, if player switches to copilot role,
> then all the copilot things are his responsibility and Petrovich is *not* doing them. But, this
> is for later and only as information for now."*

So the case BL-B80 actually serves is the player in the pilot seat with Petrovich slewing from the
copilot seat. That matches the 2026-10-17 setup (pilot seat, script write), where 874 did move.
**BL-B80 is not blocked by this sortie.** What it still needs to know is whether 874/876 track the
head finely and continuously enough to close a loop on: 2026-10-17 saw 22.5° plateaus rather than
a ramp. BL-B66 Stage 4b's per-frame trace answers that the first time BL-B80 writes the axis, so
the first BL-B80 stage can serve as the probe.

Originally open until the per-frame Windows log is read:

- Did the head visibly move in the sight view?
- Which seat, and which binding, drove the slew?
- Does `aircraft_layer_slew_trace.log` show 874/876 at 0 every frame?

**Side finding:** 213 of the 358 rows share a timestamp with the row before, meaning the body-layer
slew trace writes most polls twice. Cosmetic, but triage counts are inflated by it.
