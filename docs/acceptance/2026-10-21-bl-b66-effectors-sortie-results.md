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

Open until the per-frame Windows log is read:

- Did the head visibly move in the sight view?
- Which seat, and which binding, drove the slew?
- Does `aircraft_layer_slew_trace.log` show 874/876 at 0 every frame?

**Side finding:** 213 of the 358 rows share a timestamp with the row before, meaning the body-layer
slew trace writes most polls twice. Cosmetic, but triage counts are inflated by it.
