# Condition factors — first analysis of the user's measurements

**Source data:** `docs/concept/detection-in-non-perfect-conditions.md` (the user's own in-game
measurements, Syria, 2026-09-25/26). **Status: analysis only — nothing is implemented, at the
user's direction** ("let implementation stand idle until test flight results"). More measurements
are coming; these are an initial indication, not a calibration.

## What was computed

Each measured range divided by the current clear-weather baseline for that optic and tier, giving a
dimensionless condition factor. Baselines are the merged calibration for a 7 m vehicle
(`perception/visibility.py`: presence 9333 m, class 2000 m, type 1000 m) times that optic's own
per-tier multipliers (`perception/optics.py`: binocular 2.42/3.50/3.00; 9K113 wide 3.55/7.00/6.50
and narrow 5.81/13.75/15.00, both still un-implemented and living only in that module's docstring).

| condition | optic | presence | class | type |
|---|---|---|---|---|
| Overcast+rain 2, daylight | eye | 0.13 | 0.15 | 0 |
| | binocular | 0.08 | 0.09 | 0.12 |
| | 9K113 wide | 0.11 | **0.20** | **0.25** |
| | 9K113 narrow | 0.07 | **0.04** | **0.04** |
| Overcast+rain 3, daylight | eye | 0.14 | 0.10 | 0 |
| | binocular | 0.12 | 0.09 | 0.13 |
| | 9K113 wide | 0.17 | **0.19** | **0.25** |
| | 9K113 narrow | 0.08 | **0.05** | **0.04** |
| Sunrise −18 min | eye | 0.05 | 0.10 | 0 |
| | binocular | 0.06 | 0.03 | 0 |
| | 9K113 wide | 0.15 | 0.07 | 0.08 |
| | 9K113 narrow | **0.22** | **0.12** | **0.12** |
| Sunrise −28 min | eye | 0 | 0 | 0 |
| | binocular | 0 | 0 | 0 |
| | 9K113 wide | 0.08 | 0.06 | 0.08 |
| | 9K113 narrow | 0.13 | 0.07 | 0.07 |
| Sunrise +2 min | eye | 0.19 | 0.40 | 0.25 |

## Finding 1 — one multiplier per condition cannot fit this, and the roadmap currently assumes it can

`body-layer/ROADMAP.md`'s conditions entry states the intended shape: *"optics multiply apparent
size up, conditions multiply detectability down, and the three calibrated angular thresholds stay
fixed in the middle."* That is clean, and these measurements do not support it.

Within a single condition the factor ranges from **0.04 to 0.25** depending on which optic is
looking. A scalar applied after the optic multiplier cannot produce that spread, because the optic
multiplier has already been applied.

## Finding 2 — the ordering between wide and narrow *reverses* between conditions

This is the finding that decides the model's shape, and it is not a matter of degree:

- **In rain**, the 9K113 **wide** field is the most robust instrument measured at class and type
  (0.19–0.25) while the **narrow** field is the weakest (0.04–0.05) — despite narrow having roughly
  twice wide's clear-weather multiplier at every tier. **The detection column is a different story
  and is corrected below.**
- **In low light**, that ordering **inverts**: narrow is best (0.12–0.22), wide behind it, and the
  unaided eye and binoculars collapse to near-zero.

So it is not that some instruments are generally hardier. **Rain and darkness attack different
things**, and each instrument is exposed to them differently:

- **Rain attacks the windscreen.** The user's own note is the mechanism: *"it's the rain drops on
  the windscreen, makes everything blurry... 9K113 not affected by rain drops on glass."* The eye
  and binoculars look *through* the canopy; the sight does not. This is a property of the optic's
  optical path, not of its magnification.
- **Darkness attacks contrast and available light.** Magnification does not add photons, and the
  narrow field's advantage in clear weather comes from magnification — yet narrow *wins* in low
  light, which the user attributes to the sight's orange filter raising contrast. Whatever the
  cause, the effect is real and it is not a magnification effect.

**Consequence for the model:** the condition term cannot be `detectability × f(condition)`. It has
to be at least `f(condition, optical path)` — where "optical path" distinguishes *through the
windscreen* from *not*, which is a new per-`Optic` property that does not exist today. A single
scalar would have to be wrong for one of rain or darkness no matter which value it took.

### Correction (user, 2026-09-26): the narrow sight's rain *detection* limit is not an instrument property

*"It's not the sight, it's the atmospheric condition, no optic can see through haze/fog/rain beyond
a certain limit. That is the meteorological visibility that e.g. METAR mentions."*

This is right, and the measurements carry its fingerprint: in rain 2, the 9K113 **wide and narrow
fields both detect at exactly 3.7 km**. Two instruments whose clear-weather presence multipliers
differ by a factor of 1.6 landing on the identical number is not a coincidence about the sight — it
is both of them hitting the same wall. Above that range there is nothing to magnify.

So the detection tier needs a different *kind* of term from the other two:

```
detection_range = min(instrument capability, meteorological visibility)
```

A **ceiling**, not a multiplier — and one that applies to every instrument equally, since it is a
property of the air rather than of the glass. The windscreen-blur term from finding 2 remains a
multiplier, and applies only to the instruments that look through the canopy. The two compose:
rain degrades the eye and binoculars twice over (blur *and* ceiling) and the sight once (ceiling
only), which is exactly the ordering measured.

**What this does not explain, and it stays open:** why narrow classifies and types *worse* than
wide in rain (1.1 vs 2.8 km class) when both targets sit well inside the 3.7 km ceiling. That is an
instrument-level effect — contrast loss under magnification, a harder-to-hold narrow field, or
something else — and it is not resolved by the ceiling. Do not fold it into the ceiling term.

ED's own model agrees on the shape, which is mild corroboration rather than proof: its legacy fog
density maps directly onto a **visibility distance in metres** (10000 down to 10), and it carries a
separate altitude-dependent visibility ceiling that our flat `NAKED_EYE_RANGE_CAP_M` approximates
badly (`aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md`, findings 7 and 9).

## Finding 3 — the tiers compress, they do not scale together

A uniform multiplier would preserve the ratios between presence, class and type. It does not
happen. Clear weather, naked eye: presence/class ≈ 4.7. Rain 2: 4.0. Sunrise +2 min: **2.25**.

Bad conditions do not merely shorten every range proportionally — they push the tiers toward each
other, so that by the time you can see the thing at all you are nearly close enough to classify it.
Type collapses hardest: **0 for the naked eye in every rain and low-light row measured**, while
class survives at short range. The user's own reading matches: *"classification possible by
silhouette at close range... type id not possible, not enough light to see details."*

## Finding 4 — rain 3 measures *better* than rain 2 in most cells, and the likeliest reason is measurement spread

Presence: eye 1.3 vs 1.2 km, binocular 2.7 vs 1.8, 9K113 wide 5.5 vs 3.7 — the heavier preset
producing longer detection ranges in six of the eight comparable cells.

**The user's own caution (2026-09-26) is the most probable explanation and is more important than
this inversion:** *"with poorer visual conditions, also the measurements themselves become more
imprecise."* That is not a caveat on the data, it is a property of the thing being measured — see
the section below. The inversion sits comfortably inside the error band that caution implies, so it
should not be read as "rain 3 is milder than rain 2" without a deliberate re-measurement.

Other candidates, none verified and none needed if spread explains it: the presets may differ in
cloud base or ambient light as well as precipitation, so two effects partly cancel; and "barely"
marks both 9K113 rows in rain 3 but neither in rain 2, which is a different judgement threshold.

It still deserves one re-measurement before either number is used — not because the inversion is
surprising, but because if rain severity is genuinely non-monotonic in DCS, a model that
interpolates along a severity axis is fitting an axis that does not exist.

## Finding 5 — two smaller things worth keeping

- **The narrow sight beat the naked-eye range cap.** 12 km detection at sunrise −18 min, against
  `NAKED_EYE_RANGE_CAP_M = 10000.0`. That cap is a sanity bound on the unaided channel; when the
  sight is implemented it must not inherit it, or the best instrument in the aircraft will be
  clipped by a constant named for the worst.
- **NVG is a dead branch, cheaply.** *"There's NVG in Mi-24, but it is completely useless for
  detection, it lets you see terrain so you don't fly into it."* The conditions backlog item asks
  whether Petrovich has any low-light aid; measured answer, no. Worth recording so it is not
  re-investigated.

## Measurement precision degrades with the conditions being measured

**User, 2026-09-26:** *"note that with poorer visual conditions, also the measurements themselves
become more imprecise."*

This is a structural property of the measurement, not an apology for it, and it changes how the
numbers above should be used.

In clear weather a target either resolves or it does not, and the range where that flips is sharp
enough to read off the F10 ruler. In rain or near-darkness the transition is a gradient: the target
fades rather than disappearing, and where you call it depends on how long you stared, whether you
already knew where to look, and what counts as "seen". The `barely` annotations in the source data
are exactly this — the user marking cells where the judgement itself was soft.

Three consequences:

1. **Treat these factors as bands, not points**, and expect the band to widen as the factor falls.
   A factor of 0.20 measured in rain is a weaker claim than 1.00 measured in clear air, and the
   0.04 cells are the weakest claims in the table.
2. **Do not fit anything narrow to them.** Differences between two poor-condition cells — finding
   4's inversion, or wide-vs-narrow gaps of a few hundredths — are probably not signal. The
   differences that *are* signal here are the order-of-magnitude ones and the reversal in finding 2,
   which is a factor of 3–5 in opposite directions and survives any plausible error band.
3. **It argues for coarse condition tiers over a continuous curve.** A model with three or four
   named condition states, each carrying a per-optical-path factor, can be supported by measurements
   of this precision. A smooth function of precipitation intensity or sun elevation cannot — it
   would be reading structure out of the noise floor, and the same discipline that made the
   screenshot ladder trustworthy (measure what you can see, state what you cannot) applies here.

That third point is the one to carry into the design, because it is cheap now and expensive later:
the shape of the model should match the precision of the data that will calibrate it.

## Open questions for the next measurement pass

0. **Where a cell was soft, is `barely` the only marker, or would a range band be easy to record?**
   Given the precision point above, a cell written as "3.5–5.0, called it at 4" is worth more than a
   point value, and costs nothing extra to write down while flying.
1. ~~**What does `-` mean in the tables?**~~ **Answered (user, 2026-09-26): never achievable at any
   range.** So the zeros in the factor table are real zeros — in rain and in low light the naked eye
   never reaches type identification at all, at any range. That is a floor effect, not a short
   range, and a multiplicative model cannot produce it from a non-zero baseline: the tier has to be
   switchable off entirely.
2. **Was the windscreen in the same state across the rain runs?** If finding 2's mechanism is right,
   windscreen wetting *is* the rain variable for two of the four instruments, and wipers (untested,
   and the user notes they cover only a small segment at boresight) would be a third state rather
   than a refinement.
3. **Rain 3 vs rain 2** — see finding 4.
4. **Can meteorological visibility be read out of DCS at all, and can *where it rains* be?**
   (User, 2026-09-26.) Two separate unknowns, both feeding this model and both landing on the same
   bridge as the LOS probe:
   - **The visibility value.** `Export.lua` carries no fog or weather getter — confirmed by reading
     the shipped file — so the mission-sandbox bridge is the only candidate route, unprobed.
     `world.weather.getFogThickness()` is the named candidate; ED's own fog representation is
     `fog2.manual = {{time, visibility, thickness}, …}`, a **time series**, so anything built here
     must sample rather than read once.
   - **Where it rains.** *"Rain and clouds are not uniform in DCS. Moving will get you in and out of
     rain."* Whether any API exposes the spatial distribution is genuinely open, and it is the harder
     of the two: a single ownship-local visibility figure would at least be sampled at the right
     place, but it says nothing about whether the *target* sits under a squall. If nothing exposes
     it, the honest fallback is an ownship-local reading applied to the whole scene, with the
     limitation stated rather than hidden.

5. **Terrain and vegetation are still unmeasured**, and they are the factor the statistical
   transmission model (`body-layer/ROADMAP.md`, the 2026-09-25 vegetation decision) needs a number
   for. These condition measurements do not feed that model; they are a separate axis.
