### Goal

Add a per-optic field-of-view/magnification cone test — the "cone test and optics table" that
`body-layer/ROADMAP.md`'s "Cones, calibration and the sortie are interdependent" entry names as
slice 1 of the detection-cones milestone — as an explicit, opt-in extension of
`perception/visibility.py`'s existing gates, without changing today's default detection behaviour.

### Context this plan builds on (not re-derived)

- **Slicing is settled**: slice 1 = a direction, a FOV, and a magnification per optic, apparent
  size (true angular size × M) checked against the three thresholds already calibrated in
  `visibility.py`. **No scanning, no dwell, no attention state machine, no range uncertainty** —
  those are slice 2, gated on the ED-model research pass (`aircraft-layer/research/
  2026-09-19-ed-native-detection-identification-gap-analysis.md`), which has not happened.
- **The acuity ladder is optic-independent.** `LOWRES_ANGULAR_RADIUS_RAD` /
  `MEDRES_ANGULAR_RADIUS_RAD` / `HIRES_ANGULAR_RADIUS_RAD` in `visibility.py` are apparent-size
  thresholds; an optic supplies only magnification. No per-optic acuity curve is being invented
  here.
- **The cockpit occlusion mask (`cockpit_mask.py`) is the airframe visibility envelope, not an
  optic's FOV.** Slice 1 adds a *narrower* cone on top of it for optics that have one; it does not
  touch `COCKPIT_MASKS` or its measured angles.
- **The mode set is the diagram's** (`docs/concept/STATE_TRANSITIONS.md`): Scan, Watch, Observ
  (scan with 9K113), Track (9K113 attack), Observ off (9K113 doors closed) — not the earlier
  "peripheral/naked eye/binoculars/APS-17" guess, which is superseded. **The ASP-17V in particular
  was never a candidate**: it is the pilot's gunsight in the rear cockpit and Petrovich cannot
  manipulate it in any mode (user direction, 2026-09-20). Petrovich's optics are the naked eye,
  binoculars, and the 9K113 — nothing else.
- **Today's default is the binocular column.** `BINOCULAR_RANGE_MULTIPLIER` in `visibility.py` is
  what `NakedEyePerceptionSource` uses for every candidate, unconditionally.
  **Superseded 2026-09-20:** this bullet originally read "a calibration sortie is flying today …
  this plan must not change what gets detected by default." Both halves are now false — no sortie
  has flown (the user stopped to investigate the optics figures first), and the constant is
  deliberately changed from 4.0 to 8.0 by user direction. See "The binocular is 8×30" below. The
  don't-change-the-default constraint governed the first two revisions of this plan and explains
  several of its decisions, so it is left visible rather than deleted.

### Affected Modules / Files

- `body-layer/src/perception/optics.py` (**new**) — `Optic` dataclass (`name`, `magnification`,
  `fov_half_angle_deg: float | None`, `boresight_azimuth_deg: float = 0.0`) and two named optics:
  `UNAIDED_OPTIC` (M=1.0, `fov_half_angle_deg=None` — the cockpit mask is the only envelope) and
  `BINOCULAR_OPTIC` (M=4.0, `None` — **today's implicit default, now an explicit named value**).
  Plus `within_optic_fov(optic, azimuth_deg, elevation_deg) -> bool`: true angular separation from
  `(boresight_azimuth_deg, 0.0)` compared against `fov_half_angle_deg`; `None` means "no
  restriction," always `True`.

#### Final shape: naked eye by default, binoculars as a mode

The single largest correction in this slice, and it is not the multiplier.

`check_visibility`'s default optic is **`UNAIDED_OPTIC` (M=1.0)**. It was `BINOCULAR_OPTIC`, applied
unconditionally by `NakedEyePerceptionSource` to every candidate — Petrovich modelled as permanently
glassed-up, receiving binocular magnification across the entire cockpit-mask envelope at no cost in
field of view. That is the free-lunch version of binoculars and it was the biggest single
contributor to over-detection. **Default detection range drops roughly 4×.**

| Optic | Magnification | FOV half-angle | Default? |
|---|---|---|---|
| `UNAIDED_OPTIC` | 1.0 | `None` — cockpit mask is the only envelope | **yes** |
| `BINOCULAR_OPTIC` | 4.0 | **4.25°** (8.5° true field) | no — a mode, selected in slice 2 |

`BINOCULAR_OPTIC` is a **Б-6 6×30**, Soviet standard compact. Its 4.0 is *derived*: 6× glass times a
~0.67 unstabilised-platform penalty, because handheld 6× on a vibrating helicopter does not deliver
6× of usable acuity. Higher magnification would be worse, not better — without the 9K113's gyro
stabilisation, more magnification means less usable image and a narrower straw to look through.

**The FOV is set, not deferred, and that only became safe here.** While binoculars were the
unconditional default, a 4.25° field would have blinded Petrovich outside a narrow forward cone,
because nothing models lowering them. Now that nothing calls with this optic, the gate cannot
misfire, and `within_optic_fov` finally holds a real value for slice 2 to enforce. Binoculars must
cost field of view; that tradeoff *is* what makes them an instrument rather than free acuity.

##### The multiplier's round trip: 4.0 → 8.0 → 4.0

It ends where it started and the excursion was not wasted — record this so a later reader does not
read it as churn.

| | Value | What it was |
|---|---|---|
| Before | 4.0 | `HelperAI.lua`'s `extra_eyesight_ratio`, relabelled. Unexplained. |
| Excursion | 8.0 | An honest 8×30 instrument — which **the screenshots then refuted**. |
| Now | 4.0 | 6× glass × ~0.67 stabilisation penalty. Independently derived. |

The final 4.0 is not the inherited constant restored. It is a different number that happens to share
a value, and the excursion is what established that: taking 8.0 seriously produced four failures
against the 2026-09-17 photographic ladder, which is how the stabilisation penalty stopped being a
fudge and became a measured correction. **The physical argument and the photographic evidence
arrived at the same number independently**, which neither had done before.

##### Consequences, checked rather than assumed

- **`test_vision_calibration.py` passes in full again** — the `_STALE_AT_8X_MULTIPLIER` xfail set is
  removed entirely, not emptied. 46 passed, 0 xfailed.
- **`NAKED_EYE_RANGE_CAP_M` is healthy at M=1.0** — it now binds only for ships (≥30 m). The
  pathological case at 8.0, where it bound for every vehicle ≥3.75 m and silently undid the
  2026-09-17 cap increase, is gone.
- **The test blast radius went well beyond the one named test.** `test_naked_eye_source.py` needed
  real geometric re-derivation rather than a distance rescale (a flat rescale would have silently
  broken the merge/split relationships those fixtures exist to exercise), and
  `test_mock_flight_chain.py` changed substantively — object 102 is now never naked-eye-visible in
  that 20-frame fixture, taking it from 2 contacts/56 observations to 1/36. Both were confirmed by
  running the pipeline, not computed on paper.

##### One claim withdrawn

While arguing for recalibration I asserted that the binocular:naked-eye range ratio is ~4 at the
`class_recognizable` tier but only **~1.3** at the presence tier, and that one multiplicative model
therefore cannot fit both. **The ~1.3 does not survive checking against the fixture.** The class-tier
ratio is confirmed (~3.96), but the presence-tier ratio computes to **≥2.2–3.0**, and binocular's
true presence threshold lies beyond the farthest photographed range, so the real figure may be
larger still.

A spread of 2.2–3.0 against 4.0 may well sit inside the grading noise of a four-level scale. The
tier-dependent-magnification idea is therefore a **hypothesis for the recalibration pass to test**,
not an established finding, and must not by itself justify redesigning the detection model.

#### Scope cut 2026-09-20: the 9K113 is deferred (user direction)

Slice 1 builds the unaided and binocular optics only. An earlier revision of this plan added two
9K113 entries and four field-of-regard fields on the strength of figures that arrived the same day;
the user's call is that this got ahead of the slice, and it did — the sight has no perception
channel, no mode selector, and no caller, so every one of those entries would have been unreachable
table data.

**The field-of-regard fields go with it.** They existed solely to carry the sight's ±60°/−15°/+20°
bounds. With no 9K113 entry, both remaining optics would carry `None` on all four — fields nothing
sets and no test can exercise, which is the same objection that kept the regard *gate* out even
while those entries still existed. `Optic` is four fields, not seven.

The figures themselves are not lost and were not wasted: they live in
`body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`, sourced and marked by
confidence, ready for whichever slice wires the sight up. Research outliving the slice that prompted
it is the normal case, not a loss.

**The FOV gate stays** even though neither shipped optic restricts its field. `within_optic_fov` is
the mechanism this slice exists to establish, its `None` path is exercised by both real optics, and
its restricting path is exercised by a synthetic `Optic` in the tests — a reachable branch with a
real caller, unlike the regard check. That asymmetry is the whole rule being applied here: carry
mechanisms that something exercises, defer data that nothing reads.

- `body-layer/src/perception/visibility.py` — `check_visibility` gains `optic: Optic =
  BINOCULAR_OPTIC` as a keyword-defaulted parameter. Internally: (a) after the existing cockpit-mask
  gate, add `within_optic_fov(optic, body_direction.azimuth_deg, body_direction.elevation_deg)` as a
  new cheap geometric gate; (b) thread `optic.magnification` through the range-threshold formula and
  through `_achieved_tier` (which gains a `magnification: float = BINOCULAR_RANGE_MULTIPLIER`
  parameter) in place of the hardcoded module constant. `BINOCULAR_RANGE_MULTIPLIER` stays declared
  (as `BINOCULAR_OPTIC`'s own magnification value) so `optics.py` has one source of truth without a
  circular import — `optics.py` imports the constant from `visibility.py`, not the reverse... **(see
  Decision 1 for which module actually owns the constant — this is one of the two things flagged for
  user input)**.
- `body-layer/tests/test_visibility.py` (or wherever `check_visibility` is tested today) — new
  tests: default-arg call produces byte-identical results to pre-slice-1 behaviour (the regression
  guard for "must not change default detection"); a synthetic optic with a narrow
  `fov_half_angle_deg` rejects a target outside it and admits one inside; a synthetic optic with a
  different magnification shifts the range threshold as `size_m / threshold_rad * M` predicts.
- `body-layer/tests/test_optics.py` (**new**) — `within_optic_fov` unit tests: `None` FOV always
  passes; boundary case at exactly the half-angle; off-boresight-azimuth case.
- **Not touched**: `perception/naked_eye_source.py`, `perception/clustering.py`,
  `perception/cockpit_mask.py`, anything under `belief/`. See "Seam: upstream of belief" below.

### Decisions

1. **Where `BINOCULAR_RANGE_MULTIPLIER` lives is a real, if small, ownership question — flagged for
   user input, not resolved silently.** Two options: (a) keep the constant in `visibility.py` as
   today, have `optics.py` import it into `BINOCULAR_OPTIC.magnification`; or (b) move the constant's
   definition into `optics.py` (since it is now one entry in a table of optics, not a lone module
   constant) and have `visibility.py` import it back for its own docstring/back-compat references.
   Recommendation: (a) — smaller diff, `visibility.py`'s extensive existing docstring already
   explains the binocular premise in detail and shouldn't be split across two files. Stated as a
   recommendation, not a silent resolution, because it is the kind of local-but-visible naming
   decision `AGENTS.md`'s escalation rules leave to project taste.
2. **The FOV cone is circular (one half-angle), not a separate az/el rectangle**, matching
   `clustering.py`'s existing angular-separation approach and `cockpit_mask.py`'s own stated
   coarseness philosophy ("no need to take to canopy beam, that's too much detail"). A single number
   per optic is enough for slice 1's static-forward-cone scope.

   **Re-examined 2026-09-20 and kept.** The 9K113's sourced ±60°/−15°/+20° figures briefly looked
   like a refutation — an asymmetric rectangle no half-angle can hold. They were not: those describe
   the *field of regard*, where the head can be pointed, which is a different bound from what the
   eyepiece shows once pointed. An eyepiece field genuinely is circular. The distinction is now moot
   for this slice (the 9K113 is deferred) but is recorded because it will matter the moment the
   sight is built, and because someone re-reading this should find the resolution rather than
   rediscover the objection.
3. **The 9K113 optics' `boresight_azimuth_deg` is fixed at `0.0` (dead ahead)** — this is the
   "static forward cone" the roadmap entry names for slice 1. No traverse/slew model exists; that is
   explicitly slice 2's attention/scanning territory.
4. **`check_visibility`'s new `optic` parameter is not wired into `NakedEyePerceptionSource` or any
   other concrete `PerceptionSource` in this slice.** There is no consumer today that would call it
   with anything but the default — Observ/Track have no concrete perception channel yet, and Scan's
   existing behaviour *is* the default. Wiring a real optic-selection call path (which mode is
   active, whose FOV applies) is attention/mode-state-machine work, i.e. slice 2. Building that
   wiring now against a not-yet-built state machine would be scope creep the roadmap entry already
   warns against.

### Implementation Plan

1. **`optics.py`**: `Optic` dataclass + `within_optic_fov` + the two named optics
   (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`). Pure, no I/O, no DCS/world-model dependency — mirrors
   `cockpit_mask.py`'s own posture.
2. **Wire into `visibility.py`**: add the `optic` parameter, the FOV gate, and thread
   `optic.magnification` through the range-threshold formula and `_achieved_tier`. Keep every
   existing call site (which passes no `optic` argument) producing identical output — this is the
   commit to get right first.
3. **Regression test**: assert `check_visibility(...)` called with no `optic` argument today, on a
   handful of the existing calibration fixture cases, matches pre-change output exactly. This is the
   test that actually enforces "must not change the default" rather than just documenting the intent.
4. **New-behaviour tests**: FOV rejection/admission, magnification-driven range-threshold shift, one
   test exercising a non-default optic end-to-end through `check_visibility`.
5. **Docstring updates**: `visibility.py`'s module docstring gains a short pointer to `optics.py` and
   a note that the binocular premise section now describes `BINOCULAR_OPTIC` specifically, not an
   unnamed implicit default. `body-layer/CLAUDE.md`'s `visibility.py`/structure entry needs a
   corresponding addition (Implementer's job, per that file's own convention of listing every
   module's current shape).

No performance or scale stage — this is a handful of pure functions and one new gate on an
already-cheap geometric check; existing test/lint/type-check commands are the whole verification
loop.

### Risks & Unknowns

- **`clustering.py` imports `BINOCULAR_RANGE_MULTIPLIER` from `visibility.py` directly**, for its
  provably-non-binding acuity-floor term, independent of any per-candidate optic. That import stays
  correct as long as every live caller uses the default `BINOCULAR_OPTIC` — true today, since this
  slice doesn't wire a non-default optic into any concrete source. **If a future slice wires a
  non-default optic into a channel that also clusters, `clustering.py`'s floor term would silently
  keep assuming binocular magnification.** Not fixed here — noted so slice 2 doesn't rediscover it
  the hard way.
- **Neither shipped optic restricts its field**, so `within_optic_fov`'s restricting branch has no
  production caller — only a synthetic `Optic` in the tests. That is deliberate (the mechanism is
  what slice 1 buys) but it does mean the gate's real behaviour is unproven against live data until
  something sets a non-`None` field. Worth knowing rather than discovering later.
- **No mechanism yet decides which optic applies when.** Building the table without a selector is
  the deliberate scope cut (Decision 4) but means slice 1 alone cannot yet make "scan north" mean
  anything operationally — that requires slice 2's attention direction. Worth being explicit that
  slice 1's value is the cone-test *mechanism* and *table*, not a working scan command.
- **Doors-open/closed gating for the 9K113 (Observ off) is not modelled as code** — no boolean
  "sight available" flag exists yet, since there's no caller to gate. Left as a slice-2/wiring
  question (see Open Questions).

### Seam check: upstream of belief

This plan changes only `perception/visibility.py` and adds `perception/optics.py` — both strictly
upstream of `Percept`/`Observation` production, same layer `naked_eye_source.py` already occupies.
**Nothing in `belief/` needs to change.** `Percept`, `Contact`, `ContactStore`, `association_over_time.py`,
`decay.py`, `classification.py`, `cardinality.py` all consume `Observation`s that this slice does not
alter the shape or default values of (Decision 4 — no concrete source calls `check_visibility` with a
non-default `optic` yet, so `Observation.confidence`/`tier`/every downstream field is unchanged for
every currently-running pipeline). This was checked against the module boundary stated in
`perception/source.py`'s own docstring ("`perception` must not import `belief`") — `optics.py`
introduces no new dependency in either direction.

### Second-order effect

This buys the vocabulary (named `Optic` values, a magnification-generalised range formula) that
slice 2's attention/mode state machine will need to actually select an optic per mode — without
that vocabulary existing first, slice 2 would have had to invent both the state machine and the
optics table in one pass. It also means the calibration sortie flying today, and any that follow
before slice 2 lands, keeps producing binocular-column data comparable across all of them, since
the default path is provably unchanged.

### Decisions Requiring User Input

- **`BINOCULAR_RANGE_MULTIPLIER`'s home module** (Decision 1 above) — recommend leaving it in
  `visibility.py`, but this is a naming/ownership call the user may want to weigh in on rather than
  have silently picked.
- ~~**9K113 magnification and FOV half-angle** — genuinely unresearched placeholders.~~
  **Moot for slice 1 as of 2026-09-20** — the 9K113 is deferred (see the scope-cut note above). The
  figures were researched anyway and are recorded, by confidence class, in
  `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`. Three things that slice will
  need and this one does not resolve:
  - magnification is **switchable in flight** (`LCtrl+X`, search at ×3.3 and identify at ×10), so a
    single `magnification: float` per mode will not hold it — two optic entries, selected by mode,
    rather than a zoom state layered on a mode;
  - **field of view and field of regard are separate bounds** and must be separate fields;
  - the **6.0° narrow field is the weakest number in the set** and wants a sim measurement.
- **Whether Observ off (doors closed) should be modelled as a hard "9K113 optic unusable" flag now**,
  even with no caller to gate — cheap to add as a boolean on the optic table entry, but it's inventing
  state for a mechanism (doors) nothing in this codebase currently tracks. Left out of the
  Implementation Plan above; flagging in case the user wants it added preemptively rather than
  revisited at slice-2 wiring time.
- **Which optic Petrovich selects, and whether he chooses for himself** — explicitly a slice-2/attention
  question, not answerable from what exists today; raised here only so it isn't lost.
