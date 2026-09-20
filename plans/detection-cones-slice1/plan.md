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
  "peripheral/naked eye/binoculars/APS-17" guess, which is superseded.
- **Today's default is the binocular column.** `BINOCULAR_RANGE_MULTIPLIER = 4.0` in
  `visibility.py` is what `NakedEyePerceptionSource` already uses for every candidate, unconditionally.
  A calibration sortie is flying today and more will follow — **this plan must not change what gets
  detected by default**, or pre/post-slice-1 calibration data stops being comparable.

### Affected Modules / Files

- `body-layer/src/perception/optics.py` (**new**) — `Optic` dataclass (`name`, `magnification`,
  `fov_half_angle_deg: float | None`, `boresight_azimuth_deg: float = 0.0`) and a small table of
  named optics: `UNAIDED_OPTIC` (M=1.0, no added FOV restriction beyond the cockpit mask),
  `BINOCULAR_OPTIC` (M=4.0, no added FOV restriction — **the current implicit default, now made an
  explicit, named value**), and placeholder 9K113 optics for Observ/Track (magnification and
  FOV half-angle both marked unresearched — see Open Questions). Plus `within_optic_fov(optic,
  azimuth_deg, elevation_deg) -> bool`: true angular separation from `(boresight_azimuth_deg, 0.0)`
  compared against `fov_half_angle_deg`; `None` means "no restriction," always `True`.
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

1. **`optics.py`**: `Optic` dataclass + `within_optic_fov` + the four named optics
   (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`, `SIGHT_OPTIC_OBSERV`, `SIGHT_OPTIC_TRACK` — last two with
   docstring-flagged placeholder numbers). Pure, no I/O, no DCS/world-model dependency — mirrors
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
- **The 9K113 magnification and FOV numbers are placeholders, not researched.** My own earlier
  design sketch's numbers are explicitly wrong per the roadmap entry; this plan does not supply real
  numbers either. `optics.py`'s docstring must say so plainly so a future reader doesn't treat them
  as measured.
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
- **9K113 magnification and FOV half-angle** — genuinely unresearched placeholders. Implementer
  should pick clearly-marked round placeholder numbers (e.g. the plan's own docstring convention
  elsewhere: "documented-unmeasured, same debt class as `WAYPOINT_CAPTURE_RADIUS_M`") rather than
  inventing precision; real numbers need either a forum/manual source or a cockpit measurement,
  neither of which is in scope for slice 1.
- **Whether Observ off (doors closed) should be modelled as a hard "9K113 optic unusable" flag now**,
  even with no caller to gate — cheap to add as a boolean on the optic table entry, but it's inventing
  state for a mechanism (doors) nothing in this codebase currently tracks. Left out of the
  Implementation Plan above; flagging in case the user wants it added preemptively rather than
  revisited at slice-2 wiring time.
- **Which optic Petrovich selects, and whether he chooses for himself** — explicitly a slice-2/attention
  question, not answerable from what exists today; raised here only so it isn't lost.
