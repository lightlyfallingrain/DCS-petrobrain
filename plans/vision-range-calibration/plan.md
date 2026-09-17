### Goal
Land the calibration dataset, fixture, research doc, and regression tests that pin what
`visibility.py` currently computes against the 23-screenshot ground-truth set in
`win-mac-sync/from-windows/target acquisition screenshots/` — **no constant or behaviour change
this pass** (user decision, 2026-09-17; see "Settled Decisions" below). The actual retune is Pass
2, gated on a second sortie the user will fly for both close-range (200-800 m) and long-range
frames.

### Investigator check
No unverified DCS-internals claim is introduced here. The `min_angular_radius` table and its
tier semantics are already recorded in `aircraft-layer/research/2026-09-08-...` and
`2026-09-09-pb15-ambient-callout-live-probe.md` (including the explicit finding that tier
semantics are inference, not documented ED behaviour — unchanged by this plan). This milestone's
job is calibration against screenshots the Architect read directly, not new DCS reconnaissance —
`investigator` was not invoked.

### Calibration dataset (built from the screenshots directly)

Two distinct target complexes were photographed, both flat desert / clear weather / one altitude
band (Syria, 01/06/2020 0806, ownship ~765 m MSL / ~194 m radar alt, IAS 60):

**Complex A** — ZIL-135 (truck, 6 m) + BTR-70 (armored, 7 m) + 3× AK-74/AK infantry (1.8 m),
photographed once, F10 ruler 274°M / **1.89 km** ("group 0" filenames).

**Complex B** — a single sprawling ~14-unit cluster: T-62 (armored, 7 m), 2× SA-10SR + SA-10C2 +
SA-10TR + SA-15 (none matched by `object_model.py`'s keyword table today — falls back to
`DEFAULT_SIZE_M = 5.0` / `OP_GROUPSOMETHING`; a real gap, noted below but out of this plan's scope
to fix), 2× Smerch/BM-30 (6 m truck), 2× BM-27 (6 m truck), 2× HL B8M1 (unmatched, 5 m default),
BMD1 (armored, 7 m). Photographed three times as ownship closed on it — F10 ruler 355°M / **2.42
km** ("group 1"), 059°M / **0.895 km** ("group 2"), 340°M / **0.955 km** ("group 3") — so this one
cluster gives two independent close-range (<1 km) and one mid-range (2.4 km) datapoints, not three
different clusters.

Graded per (complex, range, optic) against the presence/class/type ladder `classification.py`
already uses. **Grading is conservative** — screenshots are compressed JPEGs; real in-game
graphics are crisper, so every "nothing"/"speck, no class" reading here is a floor, not a ceiling,
on what the constants should allow.

| Complex | Range | Naked eye (unaided) | Binocular | 9K113 wide | 9K113 narrow |
|---|---|---|---|---|---|
| A | 1.89 km | nothing | 2 specks, no class | vehicle-shaped blob, class-ish | vehicle-shaped blob, class-ish |
| B | 2.42 km | nothing | ~10 specks, no class | barely-visible dots, no class | multiple vehicle silhouettes, class recognizable |
| B | 0.955 km | faint specks, marginal | ~7 distinct blobs, no class | 5-6 clear vehicle silhouettes, type recognizable on closer ones | single tank, turret+barrel visible, type recognizable |
| B | 0.895 km | faint specks, marginal | 1 blob, no class | (not photographed at this bearing) | (not photographed at this bearing) |

### The central finding

`visibility.py` models **binocular** observation (module docstring's binocular premise), not the
9K113 sight and not true unaided naked eye. Against the one channel the code actually represents
(binocular), **class was never achieved at any tested range, down to 895 m** — the closest tested
point. Today's code claims class-tier (`medres`) recognition out to **900 m for infantry, ~3.0
km for a 6 m truck, ~3.5–4.5 km for 7–9 m armor/SAM launchers** — i.e. class recognition claimed
3-5× further out than the data supports for the mid-size objects that actually failed to resolve
at 895 m (BM-27/HL B8M1/BMD1, 6-7 m objects, `medres` threshold today ≈3.0-3.5 km). This is a real
omniscience bug in the direction the project explicitly guards against ("if the player cannot see
it, Petrovich must not").

The **presence tier (`lowres`, the current gate)** is not contradicted by this data: every
binocular frame across both complexes and all four ranges (895 m–2.42 km) showed at least a speck,
consistent with `lowres`'s existing thresholds (1.67 km for infantry alone, capped at 5 km for
6-9 m objects) at every tested range. No retune is indicated there from this data.

The 9K113 sight is a separate optic that *does* resolve class/type at these same ranges — but that
channel isn't modeled by `visibility.py` at all, and has no path into `Percept`/`Observation` today
(the F10 scan effector merged in `74f0fff` drives the naked-eye/binocular channel, not the sight).

### Settled: optic dimension deferred

**User decision, 2026-09-17: defer the optic dimension, as recommended below.** This dataset's
9K113 wide/narrow columns are handed off as founding evidence for the roadmap's separately-deferred
"Attention direction and detection cones" milestone, not built here. Effort/value read that
produced the recommendation:

- **The challenge of an optic dimension**: four independent curves (naked eye / binocular / 9K113
  wide / 9K113 narrow), each needing its own gate + tier ladder, a new "which optic is Petrovich
  using right now" state machine, and a new feed into `Percept`/`Observation` distinct from what
  the F10 scan effector currently drives. That is exactly the scope the roadmap already reserves
  for "Attention direction and detection cones" — a described, deliberately-deferred, "well after
  BL-4" milestone.
- **Why the value is smaller than it looks right now**: nothing in the current system consumes a
  9K113-driven class/type claim — there is no code path today where Petrovich's belief state is
  fed from the sight. Building the curve without the consuming mechanism (scan-state tracking,
  optic selection) produces four calibrated numbers with no caller. The single fact this
  milestone's ground truth actually forces a fix for — binocular over-claims class — is fully
  addressed by retuning one channel.
- **Cheaper path that gets most of the value**: tighten `visibility.py`'s existing single-channel
  tiers to match what binocular alone was shown to do, and explicitly hand the 9K113-driven
  class/type capability to the detection-cones milestone as its founding evidence (this dataset's
  9K113 columns), rather than half-building it now.

This matches the roadmap entry's own instruction ("the cheaper option should win unless the data
forces otherwise") — the data here does not force an optic dimension; it forces a correction to
the one channel that exists.

### Affected Modules / Files

**No changes to `body-layer/src/perception/visibility.py` or `naked_eye_source.py` this pass** —
constants, gate, `_achieved_tier`, and `_classification_for_tier` are all untouched. Neither file
is on this pass's change list.

- `body-layer/tests/fixtures/vision_calibration.json` (new) — the calibration dataset itself, see
  below.
- `body-layer/tests/test_vision_calibration.py` (new) — regression tests reading that fixture: pin
  today's `_achieved_tier`/`check_visibility` output per row, and separately, explicitly assert the
  known divergence from observed ground truth (see "Regression tests" below).
- `body-layer/research/2026-09-17-vision-range-calibration.md` (new) — dated findings doc,
  matching this project's research-doc convention (`aircraft-layer/research/` precedent); records
  the graded table above, the central finding, the "no constant changes this pass" rationale, the
  capture request for Pass 2, and the open gaps (below). `body-layer/research/` doesn't exist yet —
  this is its first entry.
- `body-layer/ROADMAP.md` — mark the roadmap's existing "Vision range calibration" entry as **Pass
  1 done, Pass 2 pending the next sortie** rather than fully done; add the capture request and the
  new gaps this pass surfaced as backlog items distinct from the roadmap's original "no long-range
  frames" gap.

### No constant changes this pass

**User decision, 2026-09-17.** Every constant in `visibility.py` (`LOWRES`/`MEDRES`/
`HIRES_ANGULAR_RADIUS_RAD`, `NAKED_EYE_GATING_ANGULAR_RADIUS_RAD`/`_TIER_NAME`,
`BINOCULAR_RANGE_MULTIPLIER`, `NAKED_EYE_RANGE_CAP_M`) stays exactly as it is today. The over-claim
finding above is real and stays the headline reason this milestone exists — today's code reaches
`medres`/`hires` at ranges (infantry ~900 m, 6-9 m armor/trucks ~3.0-4.5 km) the data shows
binocular cannot actually resolve, down to the closest tested point (895 m) — but the user wants
the fuller dataset (both close-range and long-range frames, see "Capture request for Pass 2"
below) in hand before any threshold moves, rather than retuning twice against two different slices
of evidence. This pass's job is narrower: transcribe the ground truth that already exists into a
durable fixture + tests + research doc, so Pass 2 has a fixture to extend and a pinned "here is
what the code claims today" baseline to diff against, not a new derivation to redo.

Concretely, this means `_achieved_tier` and `check_visibility` are called by the new tests only to
observe and pin their current output — never to derive a new threshold from.

### Fixture format

`body-layer/tests/fixtures/vision_calibration.json` — a list of records, one per (complex, range)
observation set, built to extend without a rewrite when the user supplies more screenshots (closer
range, longer range, different theatre/weather/altitude):

```json
{
  "complex": "B",
  "range_m": 895,
  "bearing_deg_mag": 59,
  "date": "2020-06-01",
  "conditions": "flat desert, clear, Syria, ownship ~765m MSL / ~194m radar alt, IAS 60",
  "objects": [
    {"object_type": "BM-27", "size_m": 6.0},
    {"object_type": "HL B8M1", "size_m": 5.0},
    {"object_type": "BMD1", "size_m": 7.0}
  ],
  "grades": {
    "naked_eye": "marginal_speck",
    "binocular": "speck_no_class",
    "9k113_wide": null,
    "9k113_narrow": null
  },
  "source_images": ["2 1 km.jpg", "2 binocular unit at 12 oclock.jpg"],
  "conservative_note": "JPEG-compressed screenshot; real in-game visibility is likely marginally better."
}
```

Grade vocabulary: `"nothing"` / `"marginal_speck"` / `"speck_no_class"` (= presence achieved, class
not) / `"class_recognizable"` / `"type_recognizable"`, `null` where that optic wasn't photographed
at that range. This mirrors the presence/class/type ladder `classification.py` already defines
(plus a below-presence "nothing" and a below-that "marginal" for the honestly-ambiguous frames).

### Capture request for Pass 2 (what the user should fly)

Both ends of the curve are missing, so the next sortie should cover **both** in one flight rather
than two separate ones:

- **Close range, 200-800 m** — the gap that actually matters for the central finding: today's
  binocular `medres` threshold is reachable down to 895 m in the data we have, but nothing closer
  was photographed, so "unreachable" is only pinned as an upper bound, not a real threshold.
  Concentrate on **mid-size (6-7 m) targets** — trucks/APCs like the ZIL-135/BTR-70/BM-27/BMD1
  class already in this dataset — since that's exactly where today's code over-claims class 3-5x
  further out than observed. A few infantry-only frames at this range would also help (infantry's
  `lowres` threshold is the tightest of any size class, so it's the first to be tested by closing
  range).
- **Long range, >2.5 km** — the roadmap's original, still-open gap: nothing here confirms or
  contradicts `NAKED_EYE_RANGE_CAP_M` (5000 m) in either direction.
- **All four optics per range/target** (naked eye, binocular, 9K113 wide, 9K113 narrow) — even
  though this pass defers the optic dimension, the 9K113 columns are the founding evidence for
  "Attention direction and detection cones," so keep capturing all four, not just binocular.
- **One F10 ruler shot per set**, pairing the ground-truth range with the frame the way the
  existing dataset does (see `bearing_deg_mag`/`range_m` in the fixture format below).
- **The unit roster in frame or nameable from the F10 map**, same as today's `objects` list, so
  `object_model.profile_for` sizes are known per row.
- Same weather/time-of-day/theatre/altitude band as this dataset if practical (flat desert, clear,
  similar ownship altitude/speed) — keeps the two passes comparable; a different band is fine too,
  just record it in `conditions` per row as today's rows already do.

New rows drop straight into `vision_calibration.json` in the same shape (see "Fixture format"
below) — no format change anticipated for Pass 2's data.

### Regression tests

**No pre/post-constants-change comparison this pass** — there is no "after" (see "No constant
changes this pass" above). `test_vision_calibration.py` instead does three things:

1. **Fixture validity.** Loads `vision_calibration.json`, asserts every record has the required
   keys, a non-empty `objects` list, `grades` using only the defined vocabulary (or `null`), and
   that `object_model.profile_for` resolves every `object_type` referenced (a smoke check the
   transcription didn't typo a unit name).
2. **Pin today's computed envelope.** For every record with a non-null `binocular` grade, computes
   `visibility._achieved_tier(range_m, size_m)` for the **largest** object's `size_m` in that
   record (largest = easiest to classify — if it doesn't resolve, nothing in the group does) and
   asserts it equals whatever tier the code *actually* returns today. This is a pin, not a
   correctness claim — its only job is to fail the moment someone edits `visibility.py`'s
   constants without updating this test, giving Pass 2 (or a future editor) a hard trip-wire
   pinned by evidence, not by re-deriving the numbers by eye.
3. **Explicit expected-divergence assertions.** A clearly-named test (e.g.
   `test_known_divergence_binocular_overclaims_class`) that, for the same rows, asserts the
   *documented gap* between what `_achieved_tier` computes and what the screenshot ground truth
   showed — e.g. "row B/895m computes `medres` (code claims class recognizable) while the fixture
   grade is `speck_no_class` (ground truth: no class)." This is written as a normal passing
   assertion on the known mismatch (`computed_tier != ground_truth_tier_for(grade)` documented as
   *expected* to diverge, with a comment naming the finding it encodes), not `xfail`/`skip` — a
   reader must see the disagreement by reading the test, and if Pass 2's retune later makes the
   assertion wrong, that's the signal Pass 2 succeeded and this test itself needs deleting/updating
   as part of that change, not silently rotting green.

A small table in the research doc (row → computed tier vs. ground-truth grade vs. match/diverge)
backs this same set of assertions, so the divergence is visible in prose as well as in test code.

### Known gaps (state explicitly, don't assume away)

- **Close-range gap (why Pass 2 exists at all)**: nothing closer than 895 m was photographed, so
  the medres/hires over-claim finding is only pinned down to that point, not to a real close-range
  threshold. This is the primary driver of the Pass 2 capture request above.
- **Existing roadmap gap, unchanged**: no long-range (>2.5 km) frames yet; `NAKED_EYE_RANGE_CAP_M`
  still unconfirmed either direction. Folded into the same Pass 2 capture request rather than a
  separate sortie.
- One weather/time-of-day/theatre/altitude band; flat desert with no obstruction is the easy case
  — nothing here calibrates contrast, haze, dusk, or cluttered backgrounds
  (`min_contrast_f`/`min_fog_transparency`, already flagged unaddressed in `visibility.py`'s
  docstring).
- **`object_model.py` keyword-table gap, carried forward, not fixed here**: SA-10SR/SA-10C2/
  SA-10TR/SA-15 and the HL B8M1 have no keyword-table entry and fall back to `DEFAULT_SIZE_M = 5.0`
  / `OP_GROUPSOMETHING` (`object_model.py` line 81 default, confirmed absent from the
  keyword table alongside the SA-15/`tor 9a331`/`chap_torm2` entries that *do* exist). This
  distorts any size-derived threshold computed for those specific units — a fallback 5.0 m read
  for an SA-15 (actually ~9 m per the two matched SA-15 entries) understates its true angular size
  and thus understates the range at which it should resolve.
  **Whether Pass 2 should be gated on fixing this: no** — recommend fixing it as a small
  prerequisite *step within* Pass 2's implementation (cheap, mechanical: add the four missing
  keyword-table entries with sizes from the same references used for the SA-15 entries already
  present) rather than a blocking dependency, since it only affects threshold accuracy for the
  specific unmatched units, not the overall binocular-over-claims-class finding this milestone
  exists to fix. Stated explicitly here so Pass 2's plan doesn't have to rediscover it.

### Acceptance

This pass makes no behaviour change, so acceptance is about the artifacts, not a live-DCS
comparison. DoD's acceptance-testing step should confirm:
1. The fixture accurately transcribes the screenshots (spot-check a couple of rows against the
   images).
2. The fixture-validity and pinned-envelope tests pass against `visibility.py` as it stands today
   (unchanged), and the expected-divergence test correctly encodes the over-claim finding — a
   reviewer reading only the test file can tell which rows the code and the data disagree on.
3. The research doc records the central finding, the "no constant changes this pass" rationale,
   the capture request, and the known gaps (including the `object_model.py` gap and its
   not-gating-Pass-2 status).
4. `body-layer/ROADMAP.md`'s entry reflects Pass 1 done / Pass 2 pending, not fully done — since
   `visibility.py`'s actual constants are unchanged, `body-layer/CLAUDE.md`'s Structure section
   description of the naked-eye channel needs **no edit** this pass (it still accurately describes
   current behaviour).

### Settled Decisions (2026-09-17)

- **Tier pivot: no.** Leave `medres`/`hires` reachable exactly as today; no constant in
  `visibility.py` changes this pass.
- **Optic dimension: deferred**, per the effort/value read above — 9K113 columns feed the
  "Attention direction and detection cones" milestone as founding evidence when that milestone
  starts.
- **Dataset extension: yes, before any constant changes.** The user will fly a second sortie
  covering both close-range (200-800 m) and long-range (>2.5 km) frames across all four optics
  before Pass 2's retune. This milestone splits into Pass 1 (this plan: fixture + tests + research
  doc, no behaviour change) and Pass 2 (the actual constant retune, a separate future plan gated on
  that sortie's data landing in the same fixture).
