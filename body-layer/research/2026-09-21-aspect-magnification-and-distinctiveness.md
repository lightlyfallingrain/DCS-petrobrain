# Aspect, magnification and distinctiveness — the second observation set

**Flown 2026-09-21**, continuation of the same sortie. User's caveat: *"Not super precise values, but
close enough."* They are precise enough to settle three things, one of which contradicts code that
was implemented and reviewed the same day.

Test unit **BTR-60** (naked-eye baseline from the first set: presence 3.1 km, class 0.4 km, type
0.2 km), plus a single **Infantry AK** soldier.

| instrument | presence | class | type |
|---|---|---|---|
| binocular, AOB 20° | 7.5 | 0.75 | 0.45 |
| binocular, AOB 90° | 7.5 | 1.4 | 0.6 |
| 9K113 wide, AOB 90° | 11 | 2.8 | 1.3 |
| 9K113 narrow, AOB 90° | 18 | 5.5 | 3.0 |
| 9K113 wide, AOB 0° | 11 | 1.5 | 0.6 |
| 9K113 narrow, AOB 0° | 18 | 4.0 | 1.3 |

Infantry AK:

| instrument | presence | class | type |
|---|---|---|---|
| naked eye | 0.6 | 0.6 | 0.2 |
| binocular | 2.0 | 2.0 | 0.6 |
| 9K113 wide | 2.0 | 2.0 | 0.6 |
| 9K113 narrow | 4.5 | 4.5 | 1.3 |

## 1. Aspect affects recognition, not detection — and the code gets this wrong

| instrument | presence | class | type |
|---|---|---|---|
| binocular (90° vs 20°) | **1.00×** | 1.87× | 1.33× |
| 9K113 wide (90° vs 0°) | **1.00×** | 1.87× | 2.17× |
| 9K113 narrow (90° vs 0°) | **1.00×** | 1.38× | 2.31× |

Presence is **identical at every aspect** in all three instruments — 7.5/7.5, 11/11, 18/18. Class
and type move by 1.33×–2.31×.

Physically this is what should have been expected: detection is a contrast event, "something is
there against that terrain", and depends on the object's total presented area and contrast rather
than on which silhouette it turns. Recognition is a shape event and needs the shape.

**`feature/aspect-aware-profiles` applies `apparent_extent_m` to both gates.** That is correct for
`MEDRES`/`HIRES` and wrong for the presence gate and `LOWRES`. Left as merged, a broadside BTR-60
would be *detected* about 1.4× further than a head-on one, which this data says does not happen.

Caught before merge only because the data arrived first. Worth noting the branch was reviewed and
DoD-passed — the error was not a slip in the work, it was a wrong premise in the plan that no
amount of review would have found, because review checks the code against the plan.

## 2. Magnification scales *opposite ways* for the two tiers

Ratios against the naked-eye baseline:

| instrument | M | presence | class | type |
|---|---|---|---|---|
| binocular | 4.0 | **2.42×** | 3.50× | 3.00× |
| 9K113 wide | 3.3 | **3.55×** | 7.00× | 6.50× |
| 9K113 narrow | 10.0 | **5.81×** | 13.75× | 15.00× |

**Presence scales sub-linearly with magnification; class and type scale supra-linearly.** At ×10 the
sight buys 5.81× of detection range but 13.75× of classification range.

This kills the single-multiplier model conclusively. It is no longer an inference from opposite-sign
threshold errors (2026-09-21 first set) — it is directly measured on one unit, one sortie, four
instruments.

### The stabilisation penalty, now measured rather than assumed

The handheld ×4 binocular buys **2.42×** of presence. The gyro-stabilised ×3.3 sight buys **3.55×**.
**Lower magnification, more detection range** — exactly the effect the user predicted when rejecting
the 8×30 in favour of a 6×30 ("there's not a chance anyone can keep the binoculars stabilized enough
to actually detect anything at all").

As a fraction of nominal magnification: binocular **0.61×**, 9K113 wide **1.08×**, 9K113 narrow
**0.58×**. The binocular figure is close to the ~0.67 stabilisation penalty adopted on 2026-09-20 by
argument alone — an independent arrival at roughly the same number.

> **CORRECTION 2026-09-21 (same-day audit) — the binocular figure above is not an independent
> arrival, and the number is wrong.** The `M` column gives the binocular as **4.0**, but 4.0 is not
> its nominal magnification: `BINOCULAR_OPTIC` is a **Б-6 6×30**, and 4.0 is *already* 6× glass
> times the ~0.67 handheld-stabilisation penalty (`optics.py`'s `BINOCULAR_OPTIC` docstring,
> `plans/detection-cones-slice1/plan.md` "The binocular is 8×30", `NOTES.md`). So dividing the
> measured 2.42 by 4.0 divides by a figure that has the penalty baked in, and recovering ~0.67
> from it is **circular, not confirmatory** — the penalty was put in and then read back out.
>
> Against the real nominal magnification of **6×**, the measured presence gain is
> **2.42 / 6 = 0.40×**, not 0.61×. The true stabilisation penalty this sortie measures is
> therefore materially harsher than the 0.67 adopted by argument, not "roughly the same number."
> The 9K113 figures (wide 1.08×, narrow 0.58×) are unaffected — ×3.3 and ×10 are genuine nominal
> magnifications.
>
> **Why it was plausible:** every other row in that table takes its `M` straight from the
> instrument's real magnification, so reading the binocular's `M` the same way is the natural
> move — and 0.61 landing next to 0.67 supplied exactly the confirmation that stops a second look.
> A derived constant sitting in a column of measured ones is the trap.
>
> Nothing else in this section changes: the stabilised-sight-beats-handheld-binocular result
> (3.55 presence at ×3.3 against 2.42 at a handheld instrument) stands on the raw numbers and does
> not depend on this ratio at all, and no multiplier in `optics.py` was derived from it.

The ×10 fall-off is a different effect: not stabilisation (the sight is stabilised) but the
atmospheric-contrast limit at 18 km. Magnification cannot magnify contrast that is not there.

## 3. Distinctiveness, measured: infantry class range *equals* presence range

| unit | presence | class | class ÷ presence |
|---|---|---|---|
| Infantry AK (naked eye) | 0.6 | 0.6 | **1.00** |
| Infantry AK (binocular) | 2.0 | 2.0 | **1.00** |
| Infantry AK (9K113 wide) | 2.0 | 2.0 | **1.00** |
| Infantry AK (9K113 narrow) | 4.5 | 4.5 | **1.00** |
| BTR-60 (naked eye) | 3.1 | 0.4 | 0.13 |

**For a human figure, classification costs nothing beyond detection.** If it is visible at all, it is
recognisably a man — four instruments, no exceptions. For the BTR-60 classification happens at
**7.75× closer** than detection.

This is the "silhouette distinctiveness" term hypothesised after the first set (see
`2026-09-21-first-cones-sortie-results.md`), now measured. It is a per-object-type property, not a
threshold: a human shape is unmistakable, and a boxy hull is one boxy hull among many. The S-300
mast behaves like the infantry (identifiable far out, because nothing else looks like that); armour
behaves like the BTR.

**Implication: the three tiers are not a fixed ladder.** The model assumes class always needs more
angular size than presence by a constant factor. For infantry that gap is zero, and no tuning of
`LOWRES`/`MEDRES` can produce both 1.00 and 0.13 from one pair of constants.

### Incidental check

The current model puts naked-eye infantry presence at exactly **600 m**; observed **0.6 km**. Not a
calibration of anything wider, but the one place the existing constants and reality agree exactly.

## What this changes

- **Immediate, on the unmerged branch:** aspect must feed recognition only. The presence gate and
  `LOWRES` keep the aspect-invariant `size_m`.
- **Still deferred, and now better understood:** threshold recalibration needs a per-type
  distinctiveness term and a tier-dependent magnification treatment. Both are model-shape changes,
  not constants. Designing them is not attempted here.
- **Superseded:** the working assumption that one magnification multiplier serves all tiers, and
  that aspect scales detection. Both are now measured false.
