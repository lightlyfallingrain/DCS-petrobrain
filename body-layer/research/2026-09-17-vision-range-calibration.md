# Vision range calibration — Pass 1: dataset, fixture, divergence pin

Date: 2026-09-17
Plan: `plans/vision-range-calibration/plan.md`
Scope: **no behaviour change** — `perception/visibility.py` and `perception/naked_eye_source.py`
are unmodified this pass (user decision, 2026-09-17). This document records the graded dataset,
the central finding, and the fixture/test artifacts that pin today's code against it, ahead of
Pass 2's actual retune.

## Source material

23 screenshots in `win-mac-sync/from-windows/target acquisition screenshots/` (gitignored,
read directly during this session — not committed anywhere). Two target complexes, one flight,
flat desert / clear weather / one altitude band:

- **Syria, 01/06/2020 08:06-08:13 local**, ownship ~765 m MSL / ~194 m radar altitude, IAS 60.
- **Complex A** — ZIL-135 (truck), BTR-70 (armored), 3× AK-74/AK infantry — one photographed set,
  F10 ruler 274°M / 1.89 km.
- **Complex B** — a single ~13-unit cluster (T-62, 2× SA-10SR, SA-10C2, SA-10TR, SA-15, 2× Smerch
  (BM-30), 2× BM-27, 2× HL B8M1, BMD1) — photographed three times as ownship closed on it: 355°M /
  2.42 km, 340°M / 0.955 km, 059°M / 0.895 km.

Every F10-ruler screenshot's displayed bearing/range was cross-checked against the plan's table
before transcription and matches exactly (274°/1.89 km, 355°/2.42 km, 340°/0.955 km, 059°/0.895 km).

## Grading (spot-checked against the images directly)

The plan's dataset table was read against the actual screenshots, not transcribed blind. All
four rows matched what the images show:

- **Complex A / 1.89 km** — naked eye: no visible object at all (just the reticle circle over
  bare desert). Binocular: two small dark specks, no discernible shape. 9K113 wide/narrow: a
  blob with a faint suggestion of vehicle shape, "class-ish" but not a confident type call.
- **Complex B / 2.42 km** — naked eye: nothing visible in the wide cockpit view. Binocular: a
  loose cluster of ~10 tiny dark marks, no shape to any of them. 9K113 wide: barely-visible dots,
  no class. 9K113 narrow: several distinguishable vehicle silhouettes — this is the row where the
  sight (not binoculars) actually resolves class.
- **Complex B / 0.955 km** — naked eye: faint, ambiguous specks (graded `marginal_speck`, not
  `nothing` — genuinely borderline in a compressed JPEG). Binocular: ~7 distinct blobs, still no
  resolvable shape/class. 9K113 wide: 5-6 clear vehicle silhouettes, several with enough shape to
  call type on the closer ones. 9K113 narrow: a single tank with a clearly visible turret and gun
  barrel — type recognizable.
- **Complex B / 0.895 km** — naked eye: same faint/marginal reading as the 0.955 km row. Binocular:
  a single blob, still no class. Not photographed through the 9K113 at this bearing (a different
  sub-unit was ranged for the F10 ruler shot instead of the sight itself).

No grade in the plan's table was found to disagree with the images on review — all four rows are
transcribed as given.

## `object_type` provenance (a finding beyond what the plan already flagged)

The plan's own text already documents that SA-10SR/SA-10C2/SA-10TR/SA-15 and HL B8M1 have no
`object_model.py` keyword-table entry and fall back to `DEFAULT_SIZE_M = 5.0` /
`DEFAULT_OP_CLASS`. Verifying the fixture's `object_type` strings against `profile_for` directly
surfaced two more instances of the same failure mode that the plan's prose does *not* flag,
worth recording so Pass 2 doesn't have to rediscover it:

- **`"T-62"` does not resolve to `OP_ARMORED`/7 m**, despite the plan's own prose describing it as
  "armored, 7 m." `object_model.py` does have a `"t-62"` keyword — but only in the *second*,
  reporting-name-keyed pass, which looks up the **raw** `LoGetWorldObjects` `object_type` string
  in `dcs_type_to_reporting_name.tsv` (raw key `"T-62M"` for this unit) and matches the keyword
  against the *resolved reporting name*, not the input string directly. The only `object_type`
  strings available from these screenshots are the DCS F10 map's displayed unit labels (no live
  `LoGetWorldObjects` dump was captured this session) — and `"T-62"` is not a raw type key in that
  table, so `reporting_name_for("T-62")` returns `None`, the second pass never runs, and
  `profile_for("T-62")` falls to the 5.0 m default.
- **`"BMD1"` (no hyphen, matching the F10 label) does not resolve either**, for a related but
  distinct reason: the raw-table keyword is `"bmd"` (a substring match against the raw
  `object_type`), and `"bmd1"`.lower() does contain `"bmd"` — so this one *should* match on paper.
  Confirmed live: `profile_for("BMD1")` in fact returns `OP_ARMORED`/7.0 correctly. (Recorded here
  to save a future reader re-deriving it, since the T-62 case immediately above looks similar but
  resolves the opposite way.)
- `"AK-74"` / `"AK"` (Complex A infantry) also do not match the `"infantry"`/`"soldier"` keywords
  and fall to the 5.0 m default, contrary to the plan's "1.8 m" figure for infantry — the real
  raw `object_type` for DCS infantry units is a `"Soldier ..."`-style string, which the F10 label
  abbreviates away.

**Net effect on this fixture**: `tests/fixtures/vision_calibration.json` records each object's
`size_m` as an independently-known real-world figure (matching the plan's dataset table), *not*
`profile_for`'s resolved value — the fixture's `size_m` field is ground-truth metadata, not a
transcription of what today's lookup returns. `test_vision_calibration.py`'s pin test computes
`_achieved_tier` directly from that recorded `size_m` (the largest in each record), so this
`object_type`-resolution gap does not affect what the pin test asserts. It matters only for a
future caller that runs `profile_for` on these same F10-style labels through the real pipeline —
worth fixing alongside the plan's already-noted SA-10/SA-15/HL B8M1 gap in Pass 2, not blocking
this pass.

## The central finding (per the plan, unchanged by this session's verification)

`visibility.py` models **binocular** observation, not the 9K113 sight and not unaided naked eye.
Against that one channel, **class was never achieved at any tested binocular range, down to
895 m** — the closest tested point in this dataset. Today's code (unchanged this pass) claims far
more:

| Complex | Range | `_achieved_tier` (size = largest recorded object, see fixture) | Ground truth (binocular) | Match? |
|---|---|---|---|---|
| A | 1890 m | `medres` (class claimed, confidence 0.4) | `speck_no_class` (no class) | **diverge** |
| B | 2420 m | `medres` (class claimed, confidence 0.4) | `speck_no_class` (no class) | **diverge** |
| B | 955 m | `hires` (type claimed, confidence 0.55) | `speck_no_class` (no class) | **diverge** |
| B | 895 m | `hires` (type claimed, confidence 0.55) | `speck_no_class` (no class) | **diverge** |

All four tested rows diverge, and the divergence *worsens* at closer range (955 m/895 m claim
`hires`/type, two tiers past what the screenshots show) rather than closing — consistent with the
plan's framing that today's constants over-claim class 3-5x further out than the data supports,
in the direction the project's own invariant guards against ("if the player cannot see it,
Petrovich must not").

The **presence tier (`lowres`, the actual gate `check_visibility` applies)** is not contradicted:
every binocular frame across both complexes and all four ranges showed at least a speck, and
`lowres`'s own thresholds (1.67 km infantry, capped at 5 km for larger objects) are not tested
against by anything in this dataset closer than the gate would allow. No retune is indicated
there by this data.

`tests/test_vision_calibration.py::test_known_divergence_binocular_overclaims_class` encodes this
table's four rows as passing assertions (not `xfail`) — see that test's own docstring for why.

## No constant changes this pass

Per the plan and the user's 2026-09-17 decision: every constant in `visibility.py` — the
angular-radius tiers, `BINOCULAR_RANGE_MULTIPLIER`, `NAKED_EYE_RANGE_CAP_M` — is untouched. The
fuller dataset (both close-range 200-800 m and long-range >2.5 km frames, across all four optics)
is being captured in a second sortie before any retune, so the constants move once against
complete evidence rather than twice against two different slices of it.

## Capture request for Pass 2

Unchanged from the plan's own "Capture request for Pass 2" section — restated briefly here so
this doc stands alone: **close range (200-800 m)**, concentrating on 6-7 m mid-size targets where
today's over-claim is worst, plus a few infantry-only frames; **long range (>2.5 km)** to bound
`NAKED_EYE_RANGE_CAP_M`; all four optics per range/target (the 9K113 columns feed the
separately-deferred "Attention direction and detection cones" milestone, not this one); one F10
ruler shot per set; the unit roster nameable from the F10 map. New rows drop into
`vision_calibration.json` in the same shape — no format change anticipated.

## Known gaps (carried forward from the plan, plus this session's `object_type` finding)

- **Close-range gap** — nothing closer than 895 m was photographed; the medres/hires over-claim
  finding is pinned only down to that point, not to a real close-range threshold.
- **Long-range gap** — nothing beyond 2.42 km was photographed; `NAKED_EYE_RANGE_CAP_M` (5000 m)
  is unconfirmed in either direction.
- **One weather/time-of-day/theatre/altitude band** — flat desert, clear, no obstruction is the
  easy case; nothing here calibrates contrast, haze, dusk, or cluttered backgrounds.
- **`object_model.py` keyword-table gap** — SA-10SR/SA-10C2/SA-10TR/SA-15 and HL B8M1 (plan's own
  finding) plus T-62 and AK-74/AK (this session's finding, see "`object_type` provenance" above)
  do not resolve to their true size/class through `profile_for` when looked up by their F10-map
  display label, the only `object_type` string available from these screenshots. As with the
  plan's original instance of this gap: recommended as a small step *within* Pass 2's
  implementation (add the missing keyword-table entries, or capture real
  `LoGetWorldObjects.object_type` strings alongside future screenshots), not a blocking
  dependency — it affects lookup accuracy for specific units, not the binocular-over-claims-class
  finding this milestone exists to fix.
