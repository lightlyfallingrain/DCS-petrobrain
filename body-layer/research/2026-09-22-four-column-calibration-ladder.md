# The four-column calibration ladder

**Captured 2026-09-21/22 by the user.** The naked-eye and zoom columns are the dots-off re-shoot
(`2026-09-21-no-dots-calibration-set.md`); the two 9K113 columns come from the earlier set, which is
uncontaminated because the detection-aid dots do not affect the sight views.

This is the best-attested calibration data in the project: four instruments, nine ranges, and — for
the first time — **two independent datasets that can be checked against each other**.

## Geometry

- **Target:** the twelve-unit complex, spread along a **200 m line**, all units facing the same way.
- **Naked eye / zoom columns:** ~60° AOB, 100–130 m AGL.
- **9K113 columns:** ~75° AOB, viewed **perpendicular to the line**.
- Ownship ~750 m MSL throughout; terrain ~620–650 m.

**The two sets are directly comparable despite the different AOB.** Projected extent for a 7×3 m
vehicle is 7.56 m at 60° and 7.54 m at 75° — under 0.3% apart, because the sine curve is flat near
its peak. **Aspect only bites sharply near head-on**; anything from roughly 55° to 90° presents the
same silhouette. Worth remembering for future captures: do not spend effort holding a precise AOB
in that range.

## The ladder

### Naked eye and hand-set zoom (dots off, 60° AOB)

| range | naked eye | zoom |
|---|---|---|
| 9.3 km | nothing | detection, group, cannot count |
| 5.44 km | barely visible group if looking intently | obvious detection + unit count (no infantry) |
| 4.00 km | detection, group, cannot count | " |
| 3.00 km | detection, "many" | " + class on radar, SAM launcher |
| 1.91 km | detection + unit count (no infantry) | detection incl. infantry, class on all |
| 1.00 km | " + class on SAM launcher and radar | type (fairly certain) on all except infantry |
| 0.5 km | class on all | certain type on all |
| 0.25 km | type on all | type + "radio antennas on vehicles" detail |

### 9K113 (uncontaminated, 75° AOB, perpendicular)

| range | wide | narrow |
|---|---|---|
| 8.9 km | clear dots in line | SAM launcher, radar, vehicles |
| 6.5 km | " | class on all (infantry not detected) |
| 5.0 km | class on radar, detection on others (no infantry) | class on all incl. infantry |
| 4.0 km | " | type on all (not quite certain) |
| 3.0 km | class: SAM launcher, radar, trucks, IFVs, tanks | type on all (mostly certain) |
| 2.0 km | " + AAA, infantry | very clear type on all |
| 1.5 km | hesitant type on all except infantry | " — group no longer fits the FOV |
| 1.0 km | certain type on all except infantry | " |
| 0.5 km | very certain type on all; group exceeds FOV | "I can see the AK47 on the soldiers" |

## Result 1 — the sight multipliers cross-validate

Implied by this ladder against naked-eye baselines, versus what `perception/optics.py` ships (which
came from the *separate* BTR-60 single-unit set):

| | implied here | shipped |
|---|---|---|
| wide, class vehicles | 6.0× | 7.00× |
| wide, type (certain) | 4.0× | 6.50× |
| wide, type (hesitant) | 6.0× | 6.50× |
| narrow, class vehicles | 17.8× | 13.75× |
| narrow, type | 16.0× | 15.00× |

**Same ballpark from unrelated observations.** This is the first genuine cross-validation any optic
constant in this project has had. The spread (4.0–6.5 on wide type) is roughly the width of the
"certain / mostly certain / hesitant" language, which is itself informative: the tier boundary is a
band, not a line.

**What this ladder does NOT constrain:** sight *presence*. Both modes still show "clear dots in
line" at 8.9 km, the top rung — the limit was never reached. The shipped 3.55/5.81 presence
multipliers still rest solely on the BTR-60 set.

## Result 2 — the 9K113 fields of view, measured

Both figures were UNVERIFIED, from an outside source, and carried a recorded internal
inconsistency: magnification goes ×3.3 → ×10 (a factor of **3.03**) while the quoted fields went
11.5° → 6.0° (only **1.92**). Something had to be wrong, and **6.0° was nominated as the figure to
doubt first**.

**The mismatch was real. The wrong number was the wide one.**

**Narrow — confirmed at 6.0°.** The group fits at 2.0 km and does not at 1.5 km, bracketing the
field between **5.72° and 7.63°**. The spec sits inside.

**Wide — measured at ~20°, not 11.5°.** At 0.5 km ground range / 96 m AGL (509 m slant), 180 m of
the 200 m line fits, with only the infantry on the ends outside:

```
FOV_wide = 2 · atan(90 / 509) = 20.0°
```

This also falls inside the independent 11.4°–22.6° bracket from the earlier fit/no-fit observations,
so two separate measurements agree.

**And the pair now scales as it should:** 20.0/6.0 = **3.34** against a magnification ratio of
**3.03** — agreement to ~10%, about what a hand-measured "these fit, those don't" can give.

**Consequence for the deferred 9K113 slice:** wide mode needs a **10.0° half-angle**, not 5.75°.
That is a 3.4× larger field, and the field is what the gaze gate tests — so it directly changes how
much a commanded sight scan covers.

**Still open (user, 2026-09-22): a better wide-FOV check is possible and deferred.** The ~20° figure
rests on one observation of where a 200 m line stops fitting. Good enough to refute 11.5°; worth
tightening before the sight slice is built.

## Result 3 — distinctiveness is not constant across optics

Radar versus ordinary vehicle, at the class tier:

| instrument | ratio |
|---|---|
| naked eye | 2.0× (1.0 km vs 0.5 km) |
| 9K113 wide | 1.67× (5.0 km vs 3.0 km) |

The distinctiveness advantage **shrinks as magnification rises** — which is what should be expected
if distinctiveness is partly a substitute for resolution: when the optic supplies the detail, the
shape's own conspicuousness matters less. `object_model.distinctiveness` is currently a per-type
scalar with no optic term. Not a defect at present, since only the naked eye is wired, but it will
be one when the sight is.

## Result 4 — infantry is late everywhere, and the clamp holds

Infantry is undetected at 1.91 km naked eye, undetected at 6.5 km through the narrow sight, and
classes at 5.0 km narrow / 2.0 km wide. Wherever it is detected at all it is *also* classified —
consistent with the distinctiveness clamp shipped in cones 2A (`class = min(presence, …)`), measured
independently here.
