# First cones + BL-9 sortie — detection-range results

**Flown 2026-09-21**, first flight of the naked-eye default (`ce9baea`) with the BL-9 trace running
(`1553eb9`). User's own caveat: *"incomplete and not very clean flight/data, but telling."* It is
telling, and it reverses yesterday's expectation.

## The headline: the direction flipped

The naked-eye default was made to stop Petrovich being hawk-eyed. At the **presence** tier it
overshot — he now sees *less far* than the pilot does.

| Unit | model presence | observed | ratio |
|---|---|---|---|
| BMD-1 | 2329 m | 2800 m | 1.20× |
| BTR-60 | 2324 m | 3100 m | 1.33× |
| Tor 9A331 (SA-15) | 2999 m | 3900 m | 1.30× |
| T-72B | 2309 m | 5000 m | **2.17×** |

Median 1.33× for vehicles. The T-72 outlier at 2.17× may be the cleanest observation of the set (a
large, high-contrast MBT) or the least — it is a single reading either way.

## The finding that matters most: the tiers move in opposite directions

| Unit | presence ratio | class ratio |
|---|---|---|
| BMD-1 | 1.20× | 0.71× |
| BTR-60 | 1.33× | 0.82× |
| Tor 9A331 | 1.30× | 0.64× |
| T-72B | 2.17× | 1.04× |

**Presence is too short; class is about 20% too generous.** Median class ratio 0.82.

This settles a question that was explicitly left open. On 2026-09-20 the claim "one multiplicative
magnification cannot fit all tiers" was made from the screenshot fixture, then **withdrawn** as
unproven — the measured spread (2.2–4.0 across tiers) could plausibly have sat inside the grading
noise of a four-level scale (`plans/detection-cones-slice1/plan.md`, "One claim withdrawn").

It is no longer a spread inside noise. It is **opposite signs from live observation**: the same
constant is simultaneously too small at one tier and too large at the next. A single
`size_m / threshold × M` model cannot produce that. The thresholds must move apart — `LOWRES`
looser, `MEDRES` tighter — or the tiers need their own magnification treatment.

## A data bug, not a calibration error: the S-300 components

| Unit | model presence | observed | model class | observed class |
|---|---|---|---|---|
| S-300PS 40B6M tr (tall mast) | 1665 m | **6700 m** | 345 m | **4500 m** (13×) |
| S-300PS 64H6E sr (low trailer) | 1645 m | 5000 m | — | 2000 m |

Both fall back to `object_model`'s **5.0 m generic profile** — neither has an entry. A 64H6E mast is
a roughly 10 m vertical structure standing clear of the skyline; the model treats it as a van.

**No threshold change can fix this**, and tuning thresholds against these rows would corrupt the
vehicle calibration by dragging it toward an error that belongs to the profile table. The fix is
real `size_m` values for the large radars. Worth noting the general shape: **tall, thin, skyline-
breaking objects are exactly where a single characteristic size serves worst** — a 10 m mast and a
10 m-long truck are not equally visible at 5 km.

BM-21 and Grad-URAL share the same generic fallback and were flagged as such on the flight card, so
their rows carry no information either.

## The earlier screenshot ladder is compromised — and it does not explain this

**The user had DCS's "detection aid dots" enabled when the 2026-09-17 calibration screenshots were
taken** (disclosed 2026-09-21). Those draw a small dark dot at a target to make it findable at range.
They were **off** for this sortie.

The ladder is therefore **optimistic** as a record of unaided visibility, and every constant derived
from it inherits that. But note carefully what this does *not* explain: the dots would make the
screenshots show *more* than reality, so thresholds derived from them should make Petrovich see
*too far*. He sees too *little*. **The presence shortfall is a separate error from the dot
contamination, not a consequence of it** — and correcting for the dots alone would push the model
further in the wrong direction.

User's judgement on validity, recorded because it sets the target: the dots are aimed at
air-to-air spotting rather than helicopter work; real foliage and camouflage would make spotting
*harder* still; and DCS's own AI is "way too omniscient, so some balancing is necessary."

## The open question this cannot answer by itself

The observations are what a **player sees on a monitor at 1× zoom**, which is not the same thing as
a crewman's naked eye — screen resolution, field-of-view compression and the absence of real foliage
all cut differently. So "match what the player sees" and "model a real crewman" are two different
calibration targets, and this data serves the first directly.

Given the user's own framing (real-world spotting is harder, DCS AI is too generous), **a presence
tier that stays conservative relative to these numbers may be correct rather than defective.** That
is a judgement about what the project is modelling, not a number to fit — flagged for the user
rather than resolved here. The S-300 profiles are a bug under either target.

## Two smaller observations from the trace

- **Ownship appears as a candidate.** `object_id=16777472 object_type=Mi-24P` sits in the
  cleared-the-mask-but-never-admitted list. If that is the player's own aircraft it should be
  filtered upstream rather than surviving to the trace as a near-miss — worth a check.
- **The entire second cluster never admitted** (`16786432`–`16790784`: ZSU-23-4, T-72B, BTR-70,
  BMP-1, Infantry, T-55s, BMD-1s, an IKARUS bus). Consistent with never being approached or with
  terrain LOS, not evidence of a gate fault — but it means this sortie carries no data for them.
- **No `type` tier was reached for anything except the Tor** (314 m). The flight did not close
  inside ~250 m on most units, so the type tier is simply unmeasured rather than failing.
