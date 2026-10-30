# body-layer module reference

**The per-module detail for `body-layer/`: what each module owns, and why it is the way it is.**
Split out of `body-layer/CLAUDE.md` on 2026-09-27, verbatim — that file had reached ~97KB (~24K
tokens) and was the largest single always-loaded context item in the whole repo, while most of its
bulk is detail that only matters when touching a specific module.

**Read the entry for any module before you modify it.** This is not optional background: these
entries record decisions that were made, reversed, and re-made, with the reasoning attached —
calibration values that were derived twice, a formula that was shared between two gates and had to
be un-shared, a dual field that looks redundant and is not. `body-layer/CLAUDE.md` carries the
cross-cutting invariants; the reason *this* module does it *that* way is here.

The entries are in the order they were written, which is roughly perception → belief → surfaces.


- `src/perception/source.py` — the tier-independent `PerceptionSource` protocol
  (`poll(now_sim, ownship_state) -> list[Observation]`) plus the `OwnshipState`/`Observation`
  dataclasses every tier's implementation returns. No concrete tier lives here.
  `RelativeDirection` (`plans/attack-run/plan.md` Decision 16) and `Observation.
  relative_direction` are BL-14's ownship-relative perception datum — only `naked_eye_source.py`
  ever sets it, and only `belief.percept`/`belief.attack_run` may read the field name past the
  belief boundary (grep-fenced, `test_attack_run.py`). `Observation.aim_unit_direction`
  (`[[BL-B67]]` Stage 2) is its sibling: the direction to the one cluster member nearest the
  sight, not the centroid, set by `naked_eye_source.py` only on a sight-tier look — same setter,
  same fence.
- `src/perception/geometry.py` — bearing/range helpers, shared by every tier (per both
  investigator sessions, no tier has a native range field). Calls world-model's
  `query.describe_position` for a single-point elevation lookup. `line_of_sight_clear` (LOS
  terrain-masking) is now a thin wrapper delegating to world-model's own
  `query.line_of_sight.line_of_sight_clear` (moved there so LOS is an ownship-agnostic
  point-A-to-point-B primitive, not body-layer-owned logic — `plans/
  world-model-los-generalization/plan.md`); this module's own docstring on the
  `sample_grid`-vs-`describe_position` sampling-cost tradeoff moved with it into that new
  module's docstring, not duplicated here. `signed_angular_delta_deg` (signed sibling of
  `angular_delta_deg`) and `alignment_direction` (`body_relative_direction` with `bank_deg=0.0`
  pinned) are `plans/attack-run/plan.md` Decisions 3/6 — the bank-stabilised frame BL-14's
  guidance derivation reads both axes from.
- `src/perception/association.py` — pure, fixture-testable single-detection <-> world-object
  resolution: a range-cap + forward-hemisphere plausibility filter (no coalition/IFF filtering)
  over a `LoGetWorldObjects` candidate pool, keyword-overlap type-match scoring, and a
  confident/ambiguous/drop decision. No network I/O — see `plans/pb1-perception-logger/plan.md`'s
  "Association design" section for the full algorithm.
- `src/perception/hybrid_source.py` — `HybridPerceptionSource`, the only concrete
  `PerceptionSource` this project builds. Gates on HelperAI's real
  `list_indication(HELPERAI_DEVICE_ID)` classification text (via
  `aircraft_client.get_petrovich_indication_latest()`), debounces on text change, and calls
  `association.py` + `geometry.py` to resolve geometry against a `world_objects` candidate.
  `source: "petrovich_detection_associated"` on every emitted `Observation`.
- `src/perception/visibility.py` (PB-1.5, retuned BL-2.6, gains a per-optic gate at
  `plans/detection-cones-slice1/plan.md`) — `check_visibility`, the naked-eye channel's composed
  plausibility gates: gaze, cockpit mask, per-optic field of view, angular-radius recognition
  tier, terrain LOS via `geometry.py`, and (Stage 1/2, `plans/forest-occlusion/plan.md`) forest
  occlusion — six in total as of that plan, up from the four this bullet originally described
  before gaze/optic-FOV and forest were each added at their own time; see `forest.py`'s own
  Structure entry just below for the newest one. `VisibilityResult.tier` is a **computed achieved
  tier**
  (`"lowres"`/`"medres"`/`"hires"`, BL-2.6 Stage 6) rather than the constant `"medres"` PB-1.5
  originally returned — a candidate that clears the gate can resolve closer-in to a tighter tier
  than the gate itself requires. `NAKED_EYE_GATING_TIER_NAME` is the gate's own threshold and
  **moved `"medres"` -> `"lowres"` at BL-2.6 Stage 7** (its own commit, separate from Stage 6's
  tier-computation mechanism, per this plan's "mechanism and calibration never share a commit"
  rule) — this widened the detection envelope ~1.86x (~3.5x area) so the presence tier became
  reachable at all. The tier -> "existence/class/class/IFF" semantics reading is this project's own
  modeling choice, not verified against ED internals (investigator finding, `plans/
  classification-refinement/plan.md` Session 6 addendum Q1) — documented here so a future reader
  does not "correct" it toward an ED semantics that was never established.

  `check_visibility` also gained an additive `trace:
  perception.detection_trace.DetectionTraceCollector | None = None` parameter (BL-9) — see that
  module's own Structure entry; `None` (the default) is a true no-op, no change to this function's
  existing return value or gate order. **At the BL-9/cones merge the two features turned out to
  interact in two ways neither branch's tests could see**, both fixed in the merge commit: the
  traced `range_threshold_m` was computed with `BINOCULAR_RANGE_MULTIPLIER` hardcoded, which after
  the naked-eye default would have reported a threshold 4x larger than the gate actually applied —
  it now uses `optic.magnification`, so the traced figure is the applied one by construction; and
  the FOV gate returned without recording, which would have broken BL-9's one-entry-per-call
  invariant as soon as slice 2 selects a non-default optic, so `GateOutcome` gained `OPTIC_FOV`.

  `check_visibility` gains a keyword-only `optic: Optic | None = None` parameter, resolved inside
  the function body rather than as a literal default expression — a real circular import between
  this module and `optics.py` (each needs a name from the other) forces the lazy resolution.
  **The default is `optics.UNAIDED_OPTIC` (magnification 1.0), not `BINOCULAR_OPTIC`** — the
  slice's final scope change (2026-09-20, user direction): modelling Petrovich as permanently
  glassed-up, with binocular magnification and no field-of-view cost across the whole cockpit-mask
  envelope, was the single biggest source of over-detection in this channel. Real observation is
  naked-eye by default; binoculars are a deliberate, narrower, raised act (see `optics.py`'s
  `BINOCULAR_OPTIC`, which now carries a real field-of-view value for exactly this reason).
  `optic.magnification` replaces the old hardcoded `BINOCULAR_RANGE_MULTIPLIER` reference in both
  the range-threshold formula and `_achieved_tier` (which gains its own `magnification: float =
  BINOCULAR_RANGE_MULTIPLIER` parameter) — every existing call site, which passes no `optic`
  argument, now resolves to `UNAIDED_OPTIC` and a roughly 4x shorter default detection range than
  this slice's own original binocular-default baseline (`test_default_optic_is_naked_eye` in
  `test_visibility.py` pins the current default explicitly, with a worked before/after example in
  its own docstring).

  **`BINOCULAR_RANGE_MULTIPLIER`'s round trip, in one line**: 4.0 (inherited, unexamined, from
  `HelperAI.lua`'s `extra_eyesight_ratio`) -> 8.0 (a same-session excursion: an honest 8x30, no
  derating) -> **4.0 again (final)** — numerically identical to the first value but independently
  derived this time (a real Б-6 6x30's 6x magnification times a ~0.67 handheld-stabilisation
  penalty, `optics.py`'s `BINOCULAR_OPTIC` docstring has the arithmetic), and confirmed to match
  what the 2026-09-17 screenshot ladder's binocular column independently shows. Because the
  multiplier and the three angular-radius constants are both back to the values that calibration
  was run against, `test_vision_calibration.py` is fully green again with no `xfail`s — verified
  by actually running it, not assumed from the numbers matching on paper. `BINOCULAR_RANGE_
  MULTIPLIER` stays declared here (plan Decision 1) — `optics.py` imports it, not the reverse.
- `src/perception/forest.py` (`plans/forest-occlusion/plan.md` Stage 1, specification `docs/
  acceptance/2026-10-13-tree-cover-direction.md`) — `ForestOcclusion`, `check_visibility`'s gate 5
  (last in the chain, after terrain LOS). One public method, `occluded(x, z) -> bool`: `True` iff
  `(x, z)` falls inside a mapped `landcover` polygon whose `landcover_class` is in
  `FOREST_LANDCOVER_CLASSES` (`{"forest"}` only — `orchard` is a deliberately excluded user
  decision, Decision 6). `None` landcover (no mapped data) is **not** treated as forest — measured
  against the real `syria-full` store, unmapped is 42-96% of ground positions depending on region,
  so the opposite reading would blind Petrovich almost everywhere. Reads `store.reader.
  containing_polygons(conn, ["landcover"], x, z)`, not `query.describe.describe_position` (1120x
  cheaper measured: 0.075 ms vs. 84.6 ms median) — `containing_polygons` already honours a
  polygon's `inner_rings`, so a clearing inside a wood correctly answers `False` with no extra code
  here. A quantised-position memo (50 m cell, mirroring `belief.enrichment`'s
  `ENRICHMENT_CACHE_POSITION_GRID_M` cell-key arithmetic but 2D, no altitude term, and keyed on the
  cell itself rather than `object_id` — the public signature has no `object_id` to key on, and a
  cell-keyed cache is shared across every candidate in the same cell) keeps the steady-state cost
  at a dict lookup; uncached, 200 candidates at the gate's own 0.075 ms median would already exceed
  the 12.6 ms poll budget. Optic-independent (no new `Optic` field): magnification does not see
  through canopy. Target-position-only — tests `candidate.x/z`, never ownship's, and feeds no
  threat/engagement state (Decision 3); an already-detected contact that drives into forest simply
  stops receiving percepts and decays through the existing `OBSERVED_WINDOW_S`/
  `POSITION_HALF_LIFE_S`/`LOST_THRESHOLD_S` ladder — no new decay constant (Decision 5). Wired into
  `NakedEyePerceptionSource` only (`forest: ForestOcclusion | None = None`, Stage 2) via
  `body.py`'s `--forest-occlusion`/`--no-forest-occlusion` (`argparse.BooleanOptionalAction`,
  default off) — `None` is a true no-op, same posture as `trace_sink`/`live_los_coverage`.
- `src/perception/optics.py` (`plans/detection-cones-slice1/plan.md` slice 1, per-tier multipliers
  by slice 2A `plans/detection-cones-slice2/plan.md` / `body-layer/research/2026-09-21-slice2-model-
  decisions.md` decision 1, the two sight optics by `BL-B64` `plans/9k113-sight/plan.md` §11) —
  `Optic` and four named instances. Fields: `name`; **three separate range multipliers**,
  `presence_range_mult`/`class_range_mult`/`type_range_mult`, which `visibility.py`'s
  range-threshold formula and `_achieved_tier` apply to the `lowres`/`medres`/`hires` threshold
  respectively — per tier because glass buys recognition more than detection (ED's own
  `recognition_distance_ratio_threshold`, 0.25 naked vs. 0.5 optics, and the 2026-09-21 sortie
  agree), all BTR-60-derived; `fov_half_angle_deg` (what the optic shows once pointed);
  `peripheral: bool = True` (slice 2B — whether a wide change-detecting peripheral channel survives
  alongside the focused view; a `gaze_for` stimulus bypasses the gaze gate only when it is `True`);
  **three field-of-regard fields**, `regard_azimuth_half_deg`/`regard_elevation_up_deg`/
  `regard_elevation_down_deg` (how far the optic can be *pointed* at all — three because the 9K113
  envelope is asymmetric, +20/-15 deg; `None` = pointed by the head, unrestricted); and
  `range_cap_m: float | None` (`BL-B64` §12a, a per-optic range-admission cap; `None` defers to
  `visibility.NAKED_EYE_RANGE_CAP_M`, resolved by `visibility.py` so this module never imports from
  it).

  | optic | presence / class / type | FOV half-angle | peripheral | field of regard | range cap |
  |---|---|---|---|---|---|
  | `UNAIDED_OPTIC` — **the default `check_visibility` optic** | 1.0 / 1.0 / 1.0 | 90.0 | yes | head | default |
  | `BINOCULAR_OPTIC` — Б-6 6x30 | 2.42 / 3.50 / 3.00 | 4.25 | no | head | default |
  | `SIGHT_WIDE_OPTIC` — 9K113, x3.3 | 3.55 / 7.00 / 6.50 | 5.75 | no | ±60 az, +20/-15 el | 20 km |
  | `SIGHT_NARROW_OPTIC` — 9K113, x10 | 5.81 / 13.75 / 15.00 | 3.00 | no | ±60 az, +20/-15 el | 20 km |

  **Retired, not renamed:** the single `magnification` field (slice 2A — one number applied
  uniformly to all three tiers was never right) and `BINOCULAR_RANGE_MULTIPLIER`, the 4.0 constant
  that once lived in `visibility.py` and was imported here as the binocular magnification. Its
  deletion also dissolved the circular import between this module and `visibility.py`, which now
  imports `Optic`/`UNAIDED_OPTIC`/`within_optic_fov` at top level. `Optic.boresight_azimuth_deg` is
  gone too (slice 2B): an optic is pointed by the head, so the boresight is a parameter of
  `within_optic_fov`, not of the optic. `UNAIDED_OPTIC.fov_half_angle_deg` is 90.0, not `None`
  (`docs/acceptance/2026-10-15-9k113-sight-direction.md` §14), so no shipped optic reaches
  `within_optic_fov`'s `None` branch. Sight FOV figures are user-supplied and unverified; field of
  regard is sourced from the English Mi-24P manual §3.4 (`body-layer/research/2026-09-20-9k113-
  sight-optics-from-manual.md`).

  Two pure functions. `within_optic_fov(optic, boresight_azimuth_deg, azimuth_deg, elevation_deg,
  boresight_elevation_deg=0.0)` tests a circular field of view (true angular separation from the
  boresight, not an azimuth-box/elevation-box check). `within_field_of_regard(optic, azimuth_deg,
  elevation_deg)` tests the mount limit, body-relative and fixed to the airframe (azimuth symmetric
  about dead ahead, elevation against its two bounds independently, each field tested only if set);
  `belief.optic_policy._decide_sighting` uses it to **reject** an out-of-envelope look target
  rather than clamp it (`BL-B64` security fix, `plans/9k113-sight/security.md` required fix 1).
  Pure, no I/O, no DCS/world-model dependency — mirrors `cockpit_mask.py`'s posture.
- `src/perception/clustering.py` (`plans/group-contact-model/plan.md` Stage 2, reworked
  anisotropic by Stage 3b-i, then reworked again to a true angular predicate by Stage 3b-i rev.2) —
  position-only resolution clustering. **Separability is a 3D angle subtended at the observer,
  compared against each candidate's own apparent angular size — not a world-space ellipse.**
  `angular_separation_rad(observer, a, b)` is the true angle between two observer→candidate unit
  vectors (`atan2(|cross|, dot)`, stable near zero); `angular_size_rad(size_m, slant_range_m)` is
  `size_m / slant_range_m`. Two candidates merge when they fail the two-apples criterion
  `theta_sep >= 0.5 * (theta_size(a) + theta_size(b))` — two discs of angular diameter `d_a`, `d_b`
  visually overlap exactly when their centre separation is under `(d_a + d_b) / 2` — **or** fail a
  named floor, `theta_sep * presence_range_mult >= RESOLUTION_ANGULAR_RADIUS_RAD`, where
  `presence_range_mult` is the *active optic's* own (`optics.Optic`, passed by the caller), provably
  non-binding for anything `visibility.py` actually admitted under either admission path at that
  same optic (kept as a one-line self-consistency check, not because it ever fires). No new
  constant — the optic's multiplier cancels out of the two-apples criterion entirely, since both
  sides are angles scaled by the same optic. This reproduces the old ellipse's anisotropy *for free*, because
  Petrovich is airborne: a down-range pair separates by depression angle (shrinks with range), a
  cross-range pair by the full bearing angle — no world-space ellipse required, and no
  acuity-derived radius shared with the association gate any more (see `belief.
  association_over_time`'s own docstring on why sharing that formula was Stage 3b-i's real defect).
  `ClusterCandidate` carries `alt_m`/`size_m` alongside `x`/`z`/`range_m` (no new plumbing — both
  were already in hand at `naked_eye_source._cluster_candidate`); `cluster_candidates(candidates,
  observer: perception.geometry.GeoPosition)` takes the observer's full 3D position rather than a
  bare `(x, z)` pair, since altitude is the term that makes the merge predicate anisotropic at all.
  Single-link, no chaining cap yet — a later calibration pass's job. **Counting is extent over unit
  width, with no free parameter**: a cluster's `count_bucket` is `floor(extent_rad / unit_rad) + 1`
  (`_extent_count`) — `extent_rad` the largest pairwise `angular_separation_rad` among the
  cluster's own members (its angular diameter), `unit_rad` the mean `angular_size_rad` across those
  members — literally "how many unit-widths long is this blob, plus one," the same disc geometry as
  the merge predicate, read as an extent instead of a pairwise test. This replaces the ellipse's
  grid-binning sub-clustering (`_count_cross_range_subclusters`, a free bin-width parameter and a
  documented boundary artefact) entirely. `floor`, not `round`, makes "a two-member cluster always
  reports `OP_1UNIT`" a **theorem** of the merge criterion (two candidates only merge when their
  separation is under one mean unit width, so `floor(<1) + 1 == 1` always) rather than an artefact.
  The along-line-of-sight twelve-object case reporting `OP_1UNIT` at 9 km and low altitude is the
  **correct, confident answer** — at that geometry the column genuinely subtends less than one
  vehicle's own width — and the *same* ground layout at a higher ownship altitude reports a plural
  count instead, because depression angle genuinely spreads the column out across a real axis at
  altitude; no world-space ellipse could produce that altitude-sensitivity. `count_bucket_for` (ED's
  `OP_1UNIT`…`OP_MORETHAN15UNITS` vocabulary, a non-overlapping partition for forward selection,
  deliberately narrower than `belief.cardinality`'s own — see that module's docstring) is otherwise
  unchanged. A cluster's aggregate classification is its members' shared value when all agree, else
  degrades to the presence root (`object_model.DEFAULT_OP_CLASS`) — clustering itself is
  class-agnostic, position-only; class only shapes the *label* a cluster reports, never whether it
  forms. This module's own reporting-quantisation range-bucket table (`_RANGE_BUCKETS_M` and
  friends) moved back to `belief.association_over_time` — this module has no use for a reporting
  quantisation of its own any more, only true angular geometry. `Cluster.centroid_alt_m`
  (`plans/attack-run/plan.md` Decision 4 REVISED/16) is the mean of the members' own `alt_m` — the
  cluster's real altitude, distinct from the flat-projection convention `naked_eye_source.
  _build_observation` substitutes for `derived_world_position`/`last_alt_m` elsewhere.
- `src/perception/naked_eye_source.py` (PB-1.5, retuned BL-2.6, clustering added Stage 2 of
  `plans/group-contact-model/plan.md`) — `NakedEyePerceptionSource`, the naked-eye/binocular
  channel: scans `LoGetWorldObjects` candidates through `visibility.py`'s gates and `geometry.py`'s
  bearing/range, then — the emission unit since Stage 2 — clusters the admitted candidates via
  `clustering.cluster_candidates` and emits **one `Observation` per resulting cluster**, not one
  per candidate. `_classification_for_tier` (BL-2.6 Stage 6) still maps a single candidate's
  achieved `VisibilityResult` tier to `(classification_raw, classification_level)` on the
  classification lattice (`belief.classification.SpecificityLevel`) — `hires` ->
  `reporting_names.reporting_name_for(object_type)` at level `TYPE` (Decision 1, 2026-09-09 — the
  naked-eye channel's own path to a specific type via ground truth, departing from the architect's
  original cap-at-class recommendation); `medres` -> the `OP_*` class at level `CLASS`; `lowres` ->
  `classification.PRESENCE_CLASS` at level `PRESENCE` — but that per-candidate claim now only feeds
  `clustering.ClusterCandidate`, and a cluster's own aggregate label (identical vs. mixed across its
  members) is what actually lands on the emitted `Observation`. Because `hires` values come from
  ground truth rather than a vocabulary match, "Petrovich can never mis-identify, only fail to
  identify" still applies to a singleton `hires` cluster.
  `Observation.count_bucket` carries `Cluster.count_bucket` straight through — the ED count
  vocabulary this channel previously deferred (Decision #5) for lack of a clustering mechanism.
  Bearing/range are quantised from the cluster's **centroid**, not any one candidate's own
  position; `derived_world_position` likewise becomes the cluster centroid (a documented meaning
  change from "one candidate's own ground truth" to "a cluster's mean position"). `_build_
  observations` resolves `continues_observation_id` by **majority object overlap** across the
  *whole* poll's clusters at once (not per-cluster in isolation): every member's own persistent
  `_object_id_to_last_observation_id` entry casts a vote, and only the cluster holding the global
  majority of votes for a given prior observation inherits it — a cluster splitting into several
  children never lets more than one of them claim the parent's continuity, per the plan's "the id
  follows the majority" splitting rule (ties broken deterministically, not physically meaningfully).
  The presence-tier merge veto that used to live in `belief.association_over_time.passes_gate` is
  **removed** as of this stage — see that module's own docstring for why a cluster's presence-tier
  report must be allowed to fold onto its contact, unlike a raw per-object one. **`NAKED_EYE_MAX_
  NEW_GROUPS_PER_POLL` caps cluster admission per poll, not individual-object admission**
  (`plans/detection-cones-slice2/plan.md`'s 2A.5, renamed from `NAKED_EYE_MAX_NEW_PER_POLL` —
  supersedes the Stage 2 scoping decision this paragraph originally described, where the cap ran
  ahead of clustering over individual objects and could under-report a cluster larger than the cap
  for several polls). Clustering (`cluster_candidates`) now runs over *every* gate-surviving
  candidate before the cap is applied, so admitting a cluster admits all of its members at once —
  a dense group larger than the cap is reported whole in one poll, not throttled member-by-member.
  Acquisition state (`_previously_visible_ids`/`_acquired_ids`) stays keyed on `object_id`, since a
  cluster has no stable identity across polls; `_acquire_on_change` only marks the members of
  *emitted* clusters as previously visible, so a capped-out group is retried on a later poll rather
  than dropped forever, unlike the earlier per-object behaviour. `trace_sink: perception.
  detection_trace.DetectionTraceCollector | None = None` (BL-9) is threaded into every
  `check_visibility` call this poll, and `poll()` annotates each admitted candidate's trace entry
  with its cluster's member `object_id`s and the emitted `Observation.id` once clustering/emission
  are done — see `detection_trace.py`'s own Structure entry. `forest: perception.forest.
  ForestOcclusion | None = None` (`plans/forest-occlusion/plan.md` Stage 2) is constructed by
  `body._build_sources` only when `--forest-occlusion` is passed and threaded straight into every
  `check_visibility` call this poll, alongside `trace_sink` — `None` (the default) is a true no-op.
  `_build_observation` populates `Observation.relative_direction` (`plans/attack-run/plan.md`
  Decision 16, Stage 2) only when the emitted cluster's `live_los_clear is True` — truth-to-truth
  geometry (the cluster's own `centroid_alt_m`, not ownship's), yaw-only rotated into the ownship
  frame at the observing poll's own heading, then run through `estimation.
  perturbed_relative_direction` (identity at `RELATIVE_DIRECTION_SIGMA_DEG == 0.0`). `trace_sink.
  annotate_admission` gained `relative_direction_set` alongside it, same call site.
- `src/aircraft_client.py` — HTTP client for the aircraft-layer LAN API
  (`GET /telemetry/latest`, `GET /world_objects/latest`, `GET /petrovich_indication/latest`). A
  real network call, unlike the world-model seam. `push_text_line` (BL-2.5,
  `plans/dcs-text-panel-output/plan.md`) is this client's one write call
  (`POST /text/push`, the aircraft layer's only inbound path) — unlike the
  `get_*` methods above, it raises `AircraftLayerError` on any failure
  rather than swallowing it, since `logger.ConsolePerceptionRunner`'s
  per-push try/except is where that failure is meant to be caught.
  `trigger_petrovich_search`/`get_petrovich_wheel_latest` (BL-6) are a
  second write call and its matching read. `get_f10_commands`
  (`plans/f10-crew-commands/plan.md`) is this seam's first *inbound* read
  (`GET /f10_commands/poll`): unlike every other `get_*` method here, its
  empty state is `[]`, not `None` (the aircraft layer's response is always
  a JSON list) — it still raises `AircraftLayerError` on transport/parse
  failure like the rest of them.
- `src/belief/audio_client.py` (BL-10 first slice, `plans/tts-voice-output/plan.md`) —
  `AudioAdapterClient`, an HTTP client for `audio-adapter`'s `POST /speak` endpoint. This subproject's
  own, independent copy of the same shape `aircraft_client.py` already has (not an import of
  anything in `audio-adapter/`, since that subproject must stand alone per root `CLAUDE.md`'s
  module-independence rule — the world-model seam is the sole sanctioned in-process exception).
  `push_speech(text, urgent)` raises `AudioAdapterError` on any transport failure, mirroring
  `push_text_line`'s raise-and-let-the-caller-catch contract — `CrewConsole._print`'s own
  `try`/`except` is where that failure is meant to be caught. `get_transcripts()` (Stage 3,
  `plans/inbound-speech/plan.md`) is this client's first inbound read — `GET /transcripts/poll`
  mirrors `aircraft_client.get_f10_commands`'s own drain-on-poll precedent (`[]`, not `None`, on
  an empty queue; raises `AudioAdapterError` on transport/parse failure, same as `push_speech`).
- `src/replay.py` — BL-0 replay harness: drives any `PerceptionSource.poll()` over a recorded
  sequence of ownship states, no live DCS/aircraft-layer connection required.
- `src/belief/position_belief.py` — the 2x2 covariance primitives and `PositionEstimate`
  (`plans/precise-position-belief/plan.md` Stages 3-4): `fold_position` (the real weighted
  information-form covariance fuse `Contact.record`/`from_percept` call), `plausible_speed_mps`
  (`BL-B51`'s one shared per-class-rate table, read by this module's own elapsed-motion inflation
  and by `belief.groups.group_matches` test 5 alike), and three deliberately *caller-invoked*
  post-fusion clamps, all with the same identity-when-nothing-to-bound-against shape:
  `clamp_to_detection_envelope` (a believed position cannot sit farther from the observer than
  that channel's own physical detection range), `clamp_fold_displacement` (`plans/
  bounded-fold-displacement/plan.md`, `BL-B58`/`BL-B59` — caps how far a single Stage 3
  within-group ambiguity fold may move a contact's fused mean, at `plausible_speed_mps(class) *
  elapsed`, applied *after* the envelope clamp so the bound is measured against the position
  actually adopted). None of the three is built into `fold_position` itself — each is a fact
  about the *caller's* situation (a channel's range cap, whether this specific call is folding an
  ambiguous percept) that the fuse itself must not need to know, the same boundary this module's
  own docstring draws for the first two and the plan draws again for the third. Read this
  module's own docstring before touching any of the three — it carries two live-flight-found
  defects' worked reasoning (runaway fusion, the no-envelope-gate) plus the fold-displacement
  plan's own.
- `src/belief/` — PB-2's observation-*consumption* package (`perception/` stays observation
  *production*): `percept.py` (`Percept`/`percept_of`, the structural no-omniscience boundary —
  belief code never sees `Observation.derived_world_position` or a DCS object id),
  `contacts.py` (`Contact`/`SightingSpan`/`ContactStore` — append-only observation log,
  `ingest`/`tick`). `Contact.record` takes a keyword-only `ambiguous_fold: bool = False`
  (`plans/bounded-fold-displacement/plan.md`) — set `True` at exactly one call site, `ingest`'s
  `len(passing) >= 2` fold branch — which is what tells `record` to resolve and apply the
  `clamp_fold_displacement` bound above; every other call leaves it `False`, `clamp_fold_
  displacement`'s own identity branch. `Contact.fold_displacement_m` (`BL-B58`) tracks the
  *clamped* displacement of the **worst single unretired fold** (`max()`, not an accumulated
  sum — Stage 3 of that plan: accumulation never retired in a dense scene, since every
  re-observation there is itself ambiguous) since this contact was last recorded from an
  unambiguous percept; read by `groups._cluster_contacts`'s admission gate and carried onto
  `GroupStore.reconcile`'s own trace record (`fold_budgets`, one `[contact_id,
  fold_displacement_m]` pair per member of that record's cluster — see that method's own
  docstring in `src/belief/groups.py`, which has no separate entry of its own here).
  `ingest` (`plans/group-contact-model/plan.md` Stage 3a) runs a read-only
  pre-scan over each batch before its main loop — memoizing `_resolve_continuity` per observation
  (so the main loop never calls it twice) and recording every continuity-resolved contact id under
  `claimed[(source, t_sim)]` — then, in the gate branch only, excludes a candidate contact already
  claimed under that same `(source, t_sim)` key before counting how many candidates pass. This
  enforces the rule that **two `Observation`s sharing both `source` and `t_sim` may never resolve
  to the same contact**: post-clustering naked-eye emits one `Observation` per resolution cluster
  and the scope/hybrid channel emits one per DCS `object_id`, so neither source can ever emit two
  reports of the same thing in one poll — a documented precondition a future source must satisfy to
  use this rule, not a re-checked invariant. Keying on `(source, t_sim)` rather than the whole batch
  is what keeps cross-channel fusion working (a naked-eye and a scope observation of the same thing
  in one poll must still fold together). The gate's own radius formulas
  (`association_over_time.spatial_gate_radius_m`/`passes_gate`) are untouched — this is association
  bookkeeping, the same category as `_resolve_continuity`, not a change to the gate's geometry.
  `Contact.classification` (BL-2.6) is the folded, monotone-non-decreasing best
  claim (`belief.classification.ClassificationBelief`, via `fold_classification`) and is what
  every user-facing surface reads. `Contact.last_class_raw` is kept **with its exact original
  meaning unchanged** — the most recent percept's raw classification string — because it, not
  `classification`, is `association_over_time.py`'s spatial-gate input; feeding the gate the
  folded best claim would make it monotonically stricter over a contact's life and start
  rejecting genuine re-observations of something already refined once. **This dual field is a
  real readability cost, not an oversight — read the two docstrings before touching either one.**
  `Contact.last_position_uncertainty_m` (a live-acceptance bug fix, 2026-09-09/10,
  `plans/classification-refinement/plan.md`) is `last_position`'s own error budget, fed
  symmetrically into `association_over_time.py`'s spatial gate alongside the incoming percept's —
  fixing a real duplicate-contact bug where the gate budgeted only the incoming percept's
  uncertainty and treated `last_position` as exact, so a stationary object's re-quantised implied
  position could jump a full bucket-width between polls and fail the gate.

  `Contact.cardinality` (`plans/group-contact-model/plan.md` Stage 1, folded Stage 2) is
  `classification`'s direct sibling — the folded best `belief.cardinality.CardinalityBelief`, via
  `fold_cardinality` — seeded from the founding percept's own `count_bucket` when one exists
  (Stage 2's naked-eye clusters) or `OP_1UNIT` when it does not (the scope/hybrid channel, which
  supplies no count evidence at all; a later percept whose `count_bucket` is also `None` leaves
  `cardinality` untouched — a hold, never treated as "exactly one"). `Contact.cardinality_lockout_
  until_sim` mirrors `classification_lockout_until_sim` exactly.

  `association_over_time.py` (percept→contact spatial + class-compatibility
  gating, distinct from `perception/association.py`'s within-one-poll detection→world-object
  resolution — **isotropic and quantisation-derived again, as of Stage 3b-i rev.2** of `plans/
  group-contact-model/plan.md`, which retires Decision 7. Stage 3b-i made this gate anisotropic and
  shared `perception.clustering`'s acuity-derived ellipse with it, on the premise that an isotropic
  gate would reopen the Stage 3a dead zone; that premise didn't hold — Stage 3a closes the dead zone
  with a same-source/same-poll candidate exclusion in `ContactStore.ingest`, which is
  radius-independent, so the gate was never obliged to track the cluster's own shape. Sharing the
  formula was the real defect: this gate asks whether a quantised *report* plausibly refers to a
  remembered thing (correct magnitude: the channel's own reporting vocabulary — the 30 deg clock
  bucket, the `OP_D*` range bucket — plus elapsed motion), while clustering's predicate asks whether
  two *live* candidates are angularly resolvable apart (correct magnitude: optical resolving power,
  ~one target width) — different questions about different things that a shared formula made look
  comparable. `passes_gate`/`spatial_gate_radius_m`/`uncertainty_radius_m` are reverted byte-for-byte
  to their pre-Stage-3b-i form: a scalar `gate_radius_m = uncertainty_radius_m(percept) +
  contact.last_position_uncertainty_m + GATE_GROWTH_RATE_MPS * elapsed_s`, tested against plain
  Euclidean `distance_m` (2D, x/z only). `uncertainty_radius_m` is source-derived: naked-eye gets
  `_naked_eye_uncertainty_m(range_m)` — `math.hypot(range_m * sin(half the 30 deg clock bucket),
  _range_bucket_width_m(range_m))`, this module's own private function again (moved back from
  `perception.clustering`, along with the `OP_D*` range-bucket table that feeds it — clustering has
  no use for a reporting quantisation of its own any more, only true angular geometry, see that
  module's docstring); everything else gets the fixed `SCOPE_UNCERTAINTY_M`. This revert is also
  what fixes the Stage 3b-i regression `tests/test_contacts.py::test_naked_eye_bucket_
  requantisation_does_not_spawn_duplicate_contacts` was `xfail`ed for (now passing, marker removed):
  the ratio of jitter to budget is a ratio of two angles, invariant under whatever representation
  computes it, so a shared acuity-derived formula was never going to fix a ~700:1 mismatch against
  bearing-bucket requantisation jitter — reverting to the quantisation-derived figure budgets the
  thing that is actually jittering, which is what fixed the bug the first time), `decay.py`
  (per-attribute half-lives, the `certainty` lifecycle ladder —
  `observed`/`tracked`/`estimated`/`lost`; `position_confidence` (BL-3) is the numeric,
  continuously-decaying counterpart to that ladder, keyed off `POSITION_HALF_LIFE_S`;
  `classification_confidence_at` (BL-2.6) finally consumes `IDENTITY_HALF_LIFE_S`, which had been
  declared since BL-2 and never read — decays `Contact.classification.confidence` only, never
  `.level`, which stays sticky by design — see `classification.py`'s entry below),
  `events.py` (`CONTACT_DETECTED`/`CONTACT_LOST`/
  `CONTACT_REACQUIRED`/`CONTACT_CLASSIFICATION_CHANGED` derivation, `CONTACT_CARDINALITY_CHANGED`
  added `plans/group-contact-model/plan.md` Stage 4b — `cardinality_event`, `classification_event`'s
  flat-comparison twin over `Contact.cardinality`'s `(lo, hi)` snapshot rather than a
  `ClassificationBelief`; `Event.previous_cardinality`/`cardinality` are plain `(lo, hi)` pairs, not
  `CardinalityBelief` itself. `ContactStore.tick` wires it between the classification and attention
  blocks — **lifecycle → classification → cardinality → attention** — reusing `EVENT_COOLDOWN_S`/
  `_cooldown_elapsed` unchanged, no new suppression mechanism; `Contact.last_emitted_cardinality` is
  `last_emitted_classification`'s direct twin. `belief.speech.route_event` gives this kind no
  template, joining `CONTACT_LOST`/`CONTACT_ATTENTION_CHANGED`'s pattern — settled decision 4: a bare
  cardinality move is not worth interrupting for at this stage's hedged register; the event is still
  logged and visible to `poll_events`/the debug console). `tools.py` (BL-2 Stage 4) —
  the brain-facing query API's body, minus a transport: `get_contacts`/`describe_contact`/
  `get_contact_history`/`find_contact` return `plans/body-layer/plan.md` §3.4's
  `{facts, summary, phrasing_hints}` triple, plus `watch_contact`/`unwatch_contact`/`get_stats`
  (a bare attention enum + source field on `Contact`, no policy/cooldown — that is BL-4). All four
  contact-facing functions take an optional `enrichment: belief.enrichment.EnrichmentContext |
  None = None` (BL-3, see `enrichment.py`'s entry below) — `None` (the default) leaves `facts` in
  exactly its pre-BL-3 shape, so existing callers/tests are unaffected; supplied, it adds
  `position.confidence`, `semantic`, `relative_now`, and (where derivable) `motion_when_seen`.
  `facts["cardinality"]` (`plans/group-contact-model/plan.md` Stage 4a) — `_cardinality_facts`,
  `_classification_facts`'s sibling: `{lo, hi, confidence}` read off `Contact.cardinality`
  (`confidence` through `belief.decay.cardinality_confidence_at`, decaying; `lo`/`hi` straight off
  the held claim, sticky). **Absent from `facts` entirely** (this module's documented
  absent-not-null convention), not present as `None`, whenever the held claim is still the
  cardinality lattice's root, `belief.cardinality.UNKNOWN` (0, inf) — every contact is seeded with
  a real claim at founding, so this is reachable only via a contradiction hull wide enough to span
  everything, not the common case. No `bucket_name` key: a folded interval (an intersection or a
  contradiction hull) need not match any one named `CountBucket`, so a name isn't always derivable.
  `_estimated_units_lower_bound` (Stage 4b, Sec 6, private — no `console.py` caller of its own, only
  `get_stats`/`get_situation`/`escalation._situational_header` consume it, so it follows
  `_cardinality_facts`/`_classification_facts`'s leading-underscore convention rather than
  `get_stats`' own public one) — the honest floor on total unit count, `sum(contact.cardinality.lo
  for contact in store.contacts)`, deliberately a lower bound rather than a point estimate (summing
  `.hi` is meaningless once any contact holds `OP_MORETHAN15UNITS`, `hi == math.inf`). `get_stats`
  gains `estimated_units` as a fourth key alongside `observations`/`contacts`/`events` — `contacts`
  keeps its existing record-count meaning, `estimated_units` is a different, additional figure, not
  a replacement. `get_situation` gains `facts["estimated_units"]` as a **new sibling top-level key**,
  not nested inside `facts["contact_counts"]` — that dict's existing `{total, visible, watched}`
  shape and every exact-equality test asserting it are unchanged; `summary` is untouched (wording
  fixes are out of this stage's scope, per the design's settled decision 5).
  `console.py` (BL-2 Stage 4) — a line parser + pretty-printer over `tools.py`, owning no belief
  logic of its own; every command (`contacts`, `show <id>`, `history <id>`, `find <text>`,
  `watch <id>`/`unwatch <id>`, `stats`) dispatches 1:1 into a `tools.py` function. `Console` carries
  the same optional `enrichment` field (BL-3), threaded into every dispatch, with the identical
  no-enrichment-means-no-change guard. `_SHOW_FACT_KEYS` (Stage 4a) gains `"cardinality"`, right
  after `"classification"`, so `show <id>` prints it whenever `facts` carries it.
  `format_event_for_overlay` (BL-2.5, `plans/dcs-text-panel-output/plan.md`) —
  `"<contact id>: <kind>, <summary>"` for one `belief.events.Event`, reusing
  `tools.describe_contact`'s existing `summary` field rather than new belief-reading logic, and
  reusing the `"<id>: ..."` convention `console.py`'s own `contacts`/`show <id>` rendering already
  uses rather than inventing a second one; the leading id is what lets the overlay tell six
  distinct contacts apart from repeated events on one (a live-acceptance follow-up fix,
  2026-09-09 — the original `"<kind>: <summary>"` line carried no contact id at all).
  `CONTACT_CLASSIFICATION_CHANGED` gets its own transition rendering (BL-2.6, `plans/
  classification-refinement/plan.md` Stage 4): `"<id>: CONTACT_CLASSIFICATION_CHANGED, <previous>
  -> <classification>, <summary>"` — only that kind, every other kind's line is untouched (BL-2.5's
  overlay restyle was flown and rejected once already; this is not a reopening of that question).
  An optional `enrichment` (BL-3) appends one short semantic fragment — the highest-confidence
  `SemanticFact.text` among `facts["semantic"]`, if any — to whichever line results, lifecycle or
  classification-transition alike. Consumed by `logger.ConsolePerceptionRunner`'s `--overlay`
  mirror, not by the console REPL itself.
- `src/belief/enrichment.py` (BL-3, `plans/bl3-world-enrichment/plan.md`) — the world-enrichment
  orchestration: `SemanticFact` (`{text, confidence, provenance, feature_id}`), `semantic_facts_for`
  (calls world-model's `query.describe_position` once per contact, maps the result into that flat
  list, combining each feature's confidence with `position_confidence` above), `WorldEnrichmentCache`
  (keyed by `contact_id`, recomputes only when a contact's `last_position` actually changed —
  deliberately outside `belief.contacts.Contact` to keep zero shared surface with BL-2.6's
  concurrent work on that file), `relative_geometry` (bearing/clock/range/relative-altitude from a
  *current* ownship position — never cached, since ownship moves every poll), `motion_when_seen`
  (direction derived from a contact's two most recent distinct implied positions, `None` when fewer
  exist). `EnrichmentContext` bundles `conn`/`theatre`/`ownship`/the cache and is the one object
  threaded through `tools.py`/`console.py`/`body.py` above. `semantic_facts_for` (osm-landcover-
  optimization, `plans/osm-landcover-optimization/plan.md` Design D7) reads world-model's newer
  `SettlementInfo`/`WaterInfo.subtype` for wording ("a built-up area" for an unnamed built-up
  settlement; "a river"/"a lake"/"a reservoir" for unnamed water) and appends two more facts after
  every pre-existing one: a landcover fact ("in forest"/"in orchards"/"in scrubland"/"in open
  fields"/"on barren ground") whenever `inside_landcover` is non-`None` and its class isn't
  `"built_up"` (already covered by `inside_settlement`), and a coast fact ("over the sea, off the
  coast (Nm)" or "near the coast (Nm)") within the new `COAST_FACT_RADIUS_M` (5000m) or whenever
  `nearest_coastline.side == "sea"`. **`landmark-words-no-names` (F7 settled, 2026-10-20):**
  `settlement`/`inside_settlement`/`water` facts now carry a generic landmark word
  ("village"/"town", `_settlement_size_word`; "a river"/"a lake"/"a reservoir"/"water") as an
  unconditional middle segment of `feature_id` (`f"settlement:{size_word}:{name}"`, etc.) — not
  only in the name-absent branch as before — so `belief.speech` can speak it without ever reading
  the proper name. `_settlement_size_word` falls back from `SettlementInfo.subtype` to the new
  `SettlementInfo.area_m2` (world-model, surfaced from the same `area_m2` tag
  `_preferred_settlement` already reads) against `BUILT_UP_VILLAGE_MAX_AREA_M2` (1 km², tunable)
  only when `subtype` isn't one of the three named place values, defaulting to "village" with no
  size evidence at all. `SemanticFact.text` itself is unchanged — `belief.console`/mission memory
  still read the full name.
- `src/belief/classification.py` (BL-2.6, `plans/classification-refinement/plan.md` Stages 1-2) —
  the classification specificity lattice: `SpecificityLevel` (`UNKNOWN`/`PRESENCE`/`CLASS`/`TYPE`,
  a total order 0-3) over a shallow tree of *values* (a `TYPE` value's parent is its `CLASS`
  value). `ClassificationBelief` is one contact's held claim (`value`, `level`, `confidence`,
  `established_sim`). `fold_classification` is the fusion rule `Contact.record` calls instead of
  overwriting: higher level + parent-consistent (or unresolvable) refines; same level + same value
  reinforces; **lower level holds — the held claim survives untouched, which is the fix for the
  last-writer-wins oscillation this milestone replaces**; same-or-higher level + resolvable +
  incompatible contradicts, collapsing to the deepest common ancestor and starting a
  `CLASSIFICATION_CONTRADICTION_LOCKOUT_S` (30 s) lockout against re-promotion. Also re-homes
  `_op_class_of`/`class_compatibility` from `association_over_time.py` (a pure move, Stage 1 — that
  module still imports both names so its own callers are unaffected) since `parent_class_of` needs
  the identical ED-vocabulary resolver. An unresolvable parent (scope free text `object_model.
  profile_for` can't match) always yields `unknown` comparability, on both the association gate's
  check and this lattice's — one vocabulary bridge serving both, not two. Confidence is an
  explicitly-placeholder per-level constant (not calibrated), decayed over time by
  `decay.classification_confidence_at` (`IDENTITY_HALF_LIFE_S`) — **the level itself never decays**,
  only confidence does; a contact identified as a T-72 two minutes ago does not revert to
  "something," he becomes less sure of it.
- `src/belief/cardinality.py` (`plans/group-contact-model/plan.md` Stage 1) — `classification.py`'s
  deliberate sibling: `CountBucket`, ED's own count vocabulary (`OP_1UNIT`…`OP_MORETHAN15UNITS`,
  verbatim from `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-
  detection.md`), plus `UNKNOWN`/`OP_GROUP`. `CardinalityBelief` (`lo`, `hi`, `confidence`,
  `established_sim`) is `ClassificationBelief`'s field-for-field twin; `fold_cardinality` is its
  fusion rule, with interval **containment** standing in for the lattice's specificity level:
  strictly-narrower-and-containing refines, identical reinforces, strictly-wider-and-containing
  holds, disjoint contradicts (collapses to the interval *hull*, confidence floored, arms
  `CARDINALITY_CONTRADICTION_LOCKOUT_S` — 30 s, declared separately from `classification.py`'s own
  lockout though defaulting to the same value, following the `decay.OBJECT_ID_MEMORY_S` precedent).
  A genuine partial overlap (neither claim contains the other — reachable from `OP_TO5UNITS (4,5)`/
  `OP_5TO7UNITS (5,7)`'s own deliberate boundary overlap, kept exactly as ED's vocabulary states it
  rather than "fixed") refines to the intersection, a generalisation this module's own docstring
  argues for beyond the plan's four named cases. **Counts legitimately change** (a vehicle drives
  off, one is destroyed) and this model cannot distinguish that from a perception error — both
  converge identically (widen, then re-narrow after the lockout), an accepted, stated asymmetry.
  `cardinality_belief_from_bucket_name` resolves a `perception`-emitted `count_bucket` string.
  `decay.cardinality_confidence_at` (Stage 1) is `classification_confidence_at`'s twin, reusing
  `IDENTITY_HALF_LIFE_S` rather than declaring a new half-life.
- `src/belief/group_view.py` (`plans/group-collapse/plan.md`, Stages 1-4) — `collapse(store, group,
  depth, now_sim)`/`collapse_members(members, depth, now_sim)`: a read-time derivation of the
  user's own group -> class -> sub-class -> type -> contact tree, deliberately **not** homed in
  `groups.py` (that module owns identity/cohesion/matching, reads `last_class_raw` through
  `object_model.profile_for`, and takes `Sequence[Contact]` rather than a `ContactStore`; this
  derivation reads the *other* field — `Contact.classification` — through the *other* resolver —
  the classification lattice — and needs id -> contact resolution, which is exactly the
  cross-contamination shape `BL-B47`'s family is made of). `CollapseDepth` (`GROUP`/`CLASS`/
  `SUBCLASS`/`TYPE`/`CONTACT`) is an `IntEnum`, `SpecificityLevel`'s own posture; one recursive
  `CollapseNode` type at every depth (`label`/`level`/`contacts`/`units_lo`/`units_hi`/`children`,
  plus `contact_id`/`x`/`z`/`radius_m`/`confidence` at `CONTACT` only — `confidence` is this
  module's one addition beyond the plan's named field list, routed through `decay.
  classification_confidence_at`, never `ClassificationBelief.confidence` raw). `units_lo`/
  `units_hi` is a `CardinalityBelief` interval summed across members, never `len(members)` — a
  contact is not a unit, and `CONTACT` (not `UNIT`) is this derivation's honestly deepest rung.
  Level-1 vocabulary is `classification.CLASS_GROUP_OF` (air-defence `op_class`es collapse to
  `"air defense"`; everything else stands alone) — Stage 4 (`groups.py`'s `group_matches` test 4)
  reads the same table instead of its own inline `AIR_DEFENSE_OP_CLASSES` carve-out, one definition
  of that partition rather than two. **`_subclass_label` gates on `Contact.classification.level`
  before resolving `.value` through the lattice at all** — a claim held below `SpecificityLevel.
  CLASS` has no class claim by the lattice's own definition regardless of whether its raw value
  happens to be a keyword-matchable string (a common test-fixture default across this codebase);
  without this gate a presence-level member is silently promoted into a real sub-class bucket.
  Nothing new is stored; `tools._group_facts` (Stage 2) gains a `tree` key, a shallow
  (`CollapseDepth.SUBCLASS`) collapse, gated caller-side on `ContactStore.callout_observable` (any
  member, not all) — the gate decides *whether* `collapse` runs at all, never *what* it returns, so
  a remembered-but-currently-unobservable group's tree is omitted entirely rather than filtered.
  **Stage 3 is landed**: `speech._group_composition_clause` is re-expressed as a renderer over
  `collapse_members(..., CollapseDepth.TYPE)` — this module supplies the grouping structure,
  `speech.py` supplies the words. The first pass's attempt surfaced what turned out to be a
  fixture defect, not a product question: two `test_crew_console.py` fixtures hardcoded a
  type-shaped `classification_raw` (`"BMP-2"`) at `classification_level=2` ("class"), a pairing no
  real producer ever makes (`perception.naked_eye_source._classification_for_tier`'s `medres`
  emits an `op_class` bucket string at level 2, never a type string; `hybrid_source.py` hardcodes
  level 3) — corrected to level 3 rather than left as the unreachable state the old literal
  `(value, level)` grouping happened to render correctly by accident. Canonical sorting (alphabetical
  by label at every level, this module's own invariant) also now governs the push-path composition
  line, replacing first-seen insertion order; every existing test's input already sorted that way,
  so no assertion changed, but a group observed in non-alphabetical class order now always speaks
  in the same order. **One deliberate, reviewed wording divergence survives**: `_subclass_label`
  resolves `"OP_GROUPSOMETHING"` (ED's unclassified-ground-unit fallback, `object_model.
  DEFAULT_OP_CLASS`) to `"unknown"` by design (`classification.parent_class_of` excludes that value
  from ever resolving, for the lattice's own parent-consistency reasons) — so inside a *group's*
  composition clause specifically, such a member now folds into the undifferentiated aggregate
  (`"something"`/`"N contacts"`) rather than speaking as `"group"`. The single-contact report path
  (`render_contact_report`/`_unit_type_display`) is untouched and still says `"group"` for this
  value — the two paths deliberately disagree, reviewed and pinned
  (`test_speech.py::test_group_composition_clause_folds_op_groupsomething_into_undifferentiated`),
  not a bug to fix here.
- `src/body.py` — the PB-1 deliverable: `PerceptionLogger` polls ownship telemetry + a list of
  `PerceptionSource`s, formats each `Observation` as flat text; fully tested against a fake
  source, tier-agnostic. `main()` is the one place that plugs in the concrete
  `HybridPerceptionSource` and (PB-1.5) `NakedEyePerceptionSource` and drives the poll loop
  (`python -m body --aircraft-layer-url ... --theatre ... --world-model-db ...` — see
  "Running the live logger" above; `--world-model-db` is required by `NakedEyePerceptionSource`'s
  terrain LOS gate) — untested by design, same posture as `aircraft-layer/src/collector/
  __main__.py`'s own live-process entrypoint. PB-2 Stage 3 adds `ConsolePerceptionRunner` and a
  `--console` flag alongside it: same file, same `main()`, a second poll-loop branch that builds
  both sources at `emit_mode="every_poll"` and ingests+ticks a `belief.contacts.ContactStore`
  instead of formatting text lines — `ConsolePerceptionRunner` itself *is* tested (against fakes,
  mirroring `PerceptionLogger`'s own tests), only `main()`'s CLI wiring is not. The default
  (no `--console`) path is unchanged and still uses `emit_mode="on_change"`. Stage 4 adds
  `_run_console_poll_loop`/`_run_console_repl`: `main()`'s `--console` branch now runs the poll
  loop on a background daemon thread and a `belief.console.Console` REPL over stdin in the
  foreground, both against the same `ContactStore`, coordinated through
  `ConsolePerceptionRunner.last_t_sim`. A Stage 6 live-testing fix renamed
  `_run_poll_loop` → `_run_console_poll_loop` and moved `world_model_conn`'s open (and
  `_build_sources`) onto that thread itself — `sqlite3.Connection` is thread-affine, and only the
  poll thread ever touches it, so it must be opened there rather than on the main thread before
  spawning. The runner no longer prints its periodic contact-count line in `--console` mode
  (`output=None`) — that line was spamming the REPL's own prompt/output on every poll; state is
  queried on demand via `contacts`/`stats` instead. BL-2.5 adds `ConsolePerceptionRunner.
  overlay_client: AircraftLayerClient | None` (mirroring `output`'s optional-sink pattern) and a
  `--overlay` flag (`main()`, default off, only meaningful with `--console`): when set, every
  lifecycle event newly appended by a poll's `tick()` call is formatted
  (`belief.console.format_event_for_overlay`) and pushed (`AircraftLayerClient.push_text_line`)
  to the in-cockpit text overlay, one `try`/`except AircraftLayerError` per push — the one place
  in this file a defensive try/except is load-bearing rather than cosmetic, since a failed push
  must degrade to "no overlay line for this event," never stop the poll loop or skip the rest of
  the batch. `PerceptionLogger`'s plain per-`Observation` stream does not get this wiring
  (line-noise vs. signal tradeoff). BL-5a adds `--crew-text` (mutually exclusive with
  `--console`; `--overlay` combines with either, see below) and `--brain-client http|debug|null`
  (`http` added `plans/brain-layer/plan.md` BR-1, requires `--brain-url`; talks to a real
  `brain-layer` instance and speaks real replies — `debug`/`null` are the pre-BR-1 stand-ins,
  never speaking anything):
  `_run_crew_text_poll_loop`/
  `_run_crew_text_repl` mirror `_run_console_poll_loop`/`_run_console_repl` exactly, reusing the same
  `ConsolePerceptionRunner`, except the poll loop also calls `belief.crew_console.CrewConsole.
  drain_events` after each `run_once()` — the same post-`tick()` hook point `--overlay` uses — and,
  right after it, `belief.crew_console.CrewConsole.drain_brain` (`plans/brain-layer/plan.md`) —
  and the REPL dispatches into `CrewConsole.handle_line` instead of `belief.console.Console.handle_line`.
  `--f10-commands` (`plans/f10-crew-commands/plan.md`, only meaningful with `--crew-text`, same
  additive-no-op-when-absent posture as `--overlay`) adds a `_poll_f10_commands` call to
  `_run_crew_text_poll_loop` right after `drain_events`, draining `aircraft_client.
  get_f10_commands()` and dispatching each token through `CrewConsole.handle_command` — its own
  `try`/`except AircraftLayerError` (log-and-continue), the same per-call isolation shape the
  `--overlay` push loop above uses, so one failed poll never stops the loop. `main()`'s
  `--crew-text` branch also now wires `CrewConsole(tasks=crew_runner.tasks, ...)`, the same
  `TaskStore` `ConsolePerceptionRunner.run_once` already ticks — needed for the F10 "Cancel Task"
  item. `--speech-audio --audio-adapter-url URL` (BL-10 first slice, `plans/tts-voice-output/
  plan.md`, only meaningful with `--crew-text`, same additive-no-op-when-absent posture as
  `--overlay`/`--f10-commands`) builds a `belief.audio_client.AudioAdapterClient` and wires it as
  `CrewConsole.speech_client` — independent of `--overlay`'s own `AircraftLayerClient` wiring
  (a different process, a different URL); `parser.error`s if `--speech-audio` is passed without
  `--audio-adapter-url`. `--speech-input` (Stage 3, `plans/inbound-speech/plan.md`, same
  additive-no-op-when-absent posture) adds a `_poll_transcripts` call to `_run_crew_text_poll_loop`
  right after `_poll_f10_commands`, draining `audio_client.get_transcripts()` and dispatching each
  transcript through `CrewConsole.handle_transcript` after validating all seven wire fields
  (`transcript`/`confidence`/`token`/`match_ratio`/`verb_anchored`/`ambiguous`/`t_wall` — the last
  unused, `now_sim` is this poll's own sim time) — its own `try`/`except AudioAdapterError`
  (log-and-continue), the same per-call isolation `_poll_f10_commands` uses. `--speech-audio` and
  `--speech-input` share one `AudioAdapterClient` instance when both are set (one process, one
  URL), but either works independently of the other. `--detection-trace PATH` (BL-9, `plans/
  bl9-debug-visualization/plan.md`) is the same additive-no-op-when-absent shape again: both
  `_run_console_poll_loop` and `_run_crew_text_poll_loop` build a `perception.detection_trace.
  DetectionTraceCollector`, thread it into `_build_sources`'s new `trace_sink` parameter (only
  `NakedEyePerceptionSource` consumes it), and call `detection_trace_writer.DetectionTraceWriter.
  write_poll` immediately after each `runner.run_once()` — after `ingest`/`tick` have already run
  against that poll's `Observation`s, so writing the trace can never influence what was ingested.

  **`_active_gaze` (Stage 5, `plans/voice-command-completeness/plan.md` Decision 5) now takes a
  `heading_true_deg` parameter** and resolves every directional field `AttentionArea` can carry, not
  only `relative_sector`: a `relative_clock_hour` (the new o'clock scan tokens) resolves to a
  one-leg `ScanPlan.commanded_legs`; a compass-only `sector` (previously silently skipped, falling
  through to `FREE_SCAN_PLAN`) converts to relative legs via the new `perception.gaze.
  legs_within_wedge`, computed fresh every poll from that poll's own ownship heading — this is the
  fix for the measured pre-existing defect that `scan north` registered an `AttentionArea` and spoke
  a readback while Petrovich kept free-scanning. `run_once` passes `ownship.heading_true_deg`; test
  call sites default it to `0.0`. `_search_sweep`/`_format_gaze_line` stay gated on `commanded_
  sector` alone for the binocular band, extended only for the debug overlay's own label.

  **Obsolete note, 2026-10-24 (`BL-B96`, `plans/default-crew-pipeline/plan.md`):** the above
  narrates `body.py`'s evolution up to and including the `--console`/`--overlay`/`--crew-text`/
  `--f10-commands`/`--speech-audio`/`--speech-input` mode-flag era and is kept as the historical
  record of how each piece arrived. `BL-B96` deleted every one of those flags along with the
  plain-text-logger `else:` branch and the `--console` REPL/poll-loop pair they names above
  (`_run_console_poll_loop`/`_run_console_repl`, `belief.console.Console`,
  `format_event_for_overlay`, `overlay_client`, `push_text_line`, `get_f10_commands`,
  `_poll_f10_commands`): the crew session described from `--crew-text` onward is now the only
  thing `main()` does, unconditionally, and speech in/out are always on through the now-required
  `--audio-adapter-url`. `body-layer/CLAUDE.md`'s "## Commands" section is the current reference;
  this entry is not rewritten in place because the sequence of *why* each piece was added is
  still the right account of how the module got here.
- `src/perception/detection_trace.py` (BL-9) — `GateOutcome` (`GAZE`/`COCKPIT_MASK`/`OPTIC_FOV`/
  `RANGE_OR_SIZE`/`TERRAIN_LOS`/`FOREST`/`ADMITTED`/`PLAYER_BUBBLE` — `FOREST` added `plans/
  forest-occlusion/plan.md` Stage 1, the answer to "lost in forest" vs. "lost to terrain LOS" a
  debrief needs, never fires while `check_visibility`'s `forest` parameter is `None`), the mutable
  `DetectionTrace` record (one per candidate per poll,
  ground truth by construction, same footing as `Observation`/`WorldObjectCandidate` — no
  `belief/` import), and `DetectionTraceCollector`, the small accumulator
  `visibility.check_visibility`'s new optional `trace` parameter and `NakedEyePerceptionSource`
  append/annotate into. `check_visibility` records one entry per call, at whichever gate decided a
  candidate's fate (or `ADMITTED`); `range_threshold_m`/`threshold_bound`
  (`"size_curve"` vs `"range_cap"`, recovering the two distinct reasons a single `min()`
  expression collapses) are populated unconditionally, even on a `COCKPIT_MASK` failure, so every
  row has a uniform shape. `NakedEyePerceptionSource.poll` then annotates each admitted
  candidate's own entry, in place, with its cluster's member `object_id`s and the emitted
  `Observation.id` once clustering/emission are done — an `ADMITTED` outcome does not by itself
  guarantee that annotation exists, since `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` can still throttle a
  gate-admitted candidate out of a given poll's emission (a documented, intentional gap: "visible,
  but throttled" is itself useful debrief information). `trace`/`trace_sink` default to `None`
  everywhere, a true no-op — proven, not just asserted, by
  `tests/test_detection_trace.py::test_trace_sink_does_not_perturb_the_observation_contact_or_event_streams`,
  which replays the same fixture twice (trace attached vs. not) and asserts the resulting
  `Observation`/`Contact`/`Event` streams are identical. `DetectionTrace.relative_direction_set`
  (`plans/attack-run/plan.md` Decision 16, Stage 2's own stated acceptance alongside the test
  suite) records whether the emitted `Observation`'s `relative_direction` was populated, set via
  `annotate_admission`'s new keyword-only parameter.
- `src/detection_trace_writer.py` (BL-9) — `DetectionTraceWriter`, the one module in this
  codebase deliberately allowed to hold both ground truth and belief at once: given a
  `DetectionTraceCollector` and a `ContactStore`, it resolves each admitted entry's `Contact.id`
  by scanning `store.contacts`' `Contact.contributing_observation_ids` for the entry's
  `observation_id` (an `O(contacts x history)` rebuild every poll, an accepted cost for a
  single-sortie debug artifact, not a standing index), appends one JSON line per record to a
  file, and clears the collector. **Read-only and one-directional** — it never calls anything
  that mutates `ContactStore`, and no ground-truth field is ever passed into `ContactStore.
  ingest`/`Percept`/`Contact`; `belief/percept.py`'s structural no-omniscience boundary is
  untouched. Deliberately sits beside `body.py`, not inside `perception/` or `belief/` — neither
  package gains an import because of this module. Buffers `DEFAULT_FLUSH_EVERY_N_POLLS` (5) polls'
  worth before flushing, so disk I/O never sits on the poll loop's own critical path.

  **Two `BL-11` Stage 5 changes worth knowing before reading a row.** Rows omit `None`-valued
  annotation fields (`asdict` emitted all 25, and ~13 are `None` on a rejected candidate —
  roughly half the bytes of a 290 KB/poll artifact), so **an absent key means `None`**, the same
  absent-not-null convention `belief/tools.py` uses for its `facts`. `observation_id` and
  `contact_id` are the deliberate exception and stay present even when null: they are the join
  keys, and for those two an absent key would read as *unknown* rather than the definite *never
  admitted* that a `null` states. Narrowing the rule to exempt them was not an aesthetic choice —
  the blanket version broke `test_writer_leaves_contact_id_null_when_never_admitted`, and that
  test was right. Second, a write failure (`ENOSPC` is the realistic case) is reported **once** on
  stderr and then this writer stops for the rest of the run, having previously been swallowed by
  the poll loop's own broad `except Exception` one traceback per poll with nothing saying the log
  had gone truncated. A disabled writer still clears the collector, or a lost debug log becomes a
  memory leak.
- `src/run_log_paths.py` (`BL-11` Stage 5) — `per_run_log_path`, which stamps the run's start time
  into a log filename before its suffix (`logs/trace.jsonl` → `logs/trace-20261006-143500.jsonl`).
  All three JSONL writers used to open with `"a"` and never roll, so one path accumulated every
  sortie ever flown and the 2026-10-05 analysis had to seek to byte offset 2,448,471,603 to find
  that flight. **Timestamping rather than truncate-on-open is the decision here**: truncating also
  removes the seeking and is shorter, but silently destroys the previous flight's log, which the
  user reads after landing. Applied at the CLI boundary by `body._per_run_log_paths` (one stamp
  shared by all three logs, so a sortie's files are recognisable as a set), never inside a writer —
  a writer handed an exact path still writes exactly there, which is what keeps them testable and
  lets `tools/` read a named file.
- `body-layer/tools/summarize_detection_trace.py` (BL-9) — the post-flight reducer, not a test
  (same "dev acceptance aid" posture as `speak_samples.py`): reads a `--detection-trace` JSONL
  file and prints the actual flight-debrief table — per object, the range at which the
  presence/class/type tiers were first admitted, and the list of objects that cleared the cockpit
  mask (plausibly "on screen") but never reached `ADMITTED` at any tier. That second list is
  stated in its own output as an approximation, not a verified claim — code can confirm an object
  cleared the geometric gates, not that the pilot's own monitor rendered it large enough to
  notice. `outcome_histogram` (`plans/forest-occlusion/plan.md` Stage 2) adds a third, simpler
  section: a count of every candidate-poll row by `GateOutcome`, so a sortie flown with
  `--forest-occlusion` can answer "how many rows were `forest`" without the per-object tables
  above, which were never designed to distinguish *which* gate most often blocked a never-admitted
  object.
- `src/belief/utterance.py` (BL-5a, `plans/bl5a-text-mode-crew-interaction/plan.md`) — the
  deterministic intent parser: `PlayerUtterance`/`PartialParse` (§5/§3.5's shapes, trimmed to what
  this milestone populates) and `parse_utterance`, a small ordered table of `(regex, intent)` pairs
  evaluated top-down, first match wins — the same evaluation shape `belief.classification`'s lattice
  and `belief.attention.effective_attention` already use elsewhere. A verb match alone never yields
  a `"handled"` disposition — only a verb match *and* exactly one resolved reference candidate do;
  zero or several always escalate with `reason_escalated` (`unmatched`/`ambiguous_reference`) rather
  than guessing. Reference resolution is a literal `CONTACT_<n>` id, or `belief.tools.find_contact`
  after stripping leading filler words (`that`/`the`/`a`/`an`) — place-name phrasing (`find_place`)
  stays unmatched until BL-5 merges (documented gap, not a bug). No fabricated per-candidate score —
  `find_contact` (BL-2) has no ranking to carry through.
- `src/belief/speech.py` (BL-5a, extended twice by `plans/overlay-speech-callouts/plan.md`'s two
  addenda) — `OutgoingSpeech` (§5's record, trimmed), the three body-written templated classes
  (§2.1/§3.6): `render_readback`, `render_contact_report` (single-contact only — no clustering
  exists yet, `docs/concept/PETROBRAIN_RUNTIME.md` line 336), and `route_event`, the outbound
  routing gate. **Contact-report format (2026-09-10 user decision, extended 2026-09-11 twice —
  terser crew-text is the current, live behaviour):**
  `"<unit type>[, <clock> o'clock, <range> km][ <best semantic fact text>]."`, built by a shared,
  id-less, coalition-less `_contact_report_text(facts)` helper — no longer a verbatim echo of
  `tools.describe_contact`'s `summary`. `render_contact_report` and `_render_lifecycle_text`'s
  `CONTACT_DETECTED`/`CONTACT_REACQUIRED` branches both call this one helper directly, with **no id
  spoken anywhere** (a pilot cannot track `CONTACT_<n>` ids by ear; the id still exists on
  typed/console surfaces, only what is *spoken* changed) and **no coalition token** (the original
  `"UNKNOWN"` placeholder was removed entirely — a pilot hearing "UNKNOWN" on every single callout,
  when no callout can ever say anything else yet, is net noise). `CONTACT_LOST` has **no template at
  all** — `_render_lifecycle_text` returns `None`, joining `CONTACT_ATTENTION_CHANGED`'s existing
  no-template pattern — a lost contact has no current position worth interrupting the pilot to
  report. `CONTACT_CLASSIFICATION_CHANGED` speaks a new position-bearing line,
  `"unit at {clock} o'clock, {range} km is {unit type}."` (range clause omitted when unenriched),
  built from the contact's *current* `facts["classification"]` via `_unit_type_display` — not the
  raw `event.classification` enum string as before. Range is rounded to the nearest 0.5 km with no
  trailing `.0` (`_format_range_km`). **`landmark-words-no-names` (F7 settled,
  `docs/acceptance/2026-10-20-sortie-feedback.md`, 2026-10-20):** a semantic fragment's name and
  embedded trailing distance (e.g. `"near a road (439m)"`) are both dropped for speech —
  `_landmark_speech_text` replaces a proper name with the feature's own generic landmark word
  ("a village"/"in the town"/"a road"/"a river", read off `SemanticFact.feature_id`'s `kind:`
  segment) and strips the distance parenthetical entirely rather than rounding it, superseding the
  earlier `_round_enrichment_fragment` (which only rounded the figure and never touched the name).
  `enrichment.py`'s `SemanticFact.text`/`feature_id` themselves are untouched and stay shared with
  the unaffected `belief.console` debug path and mission memory, which both keep the full name. A
  real coalition implementation should eventually *infer* coalition from unit-type
  vocabulary + which side's terrain the contact sits in, not ground truth (`ROADMAP.md` backlog,
  deferred, unaffected by the token's removal here). Unit type reads the classification lattice's
  level+value (`_unit_type_display`/`_OP_CLASS_DISPLAY`, all lowercase): `"ground"`/`"contact"` at
  presence/unknown, a human word for a `class`-level `OP_*` bucket, the reporting name verbatim at
  `type` level. The semantic fragment is the highest-confidence `belief.enrichment.SemanticFact.text`
  among `facts["semantic"]`, mirroring `belief.console.format_event_for_overlay`'s own selection;
  omitted (not "unknown") when no `EnrichmentContext` was supplied or no semantic facts exist, same
  absent-not-null convention as clock/range. **The count clause (`plans/group-contact-model/plan.md`
  Stage 4b)** — a plural `Contact.cardinality` prepends a hedged quantity word ahead of the unit
  type: `_cardinality_phrase(lo, hi)` reads interval magnitude directly (never a `CountBucket` name,
  since a folded interval need not match one) — `None` (no clause) for an exactly-one interval,
  `"many"` for `lo >= 16`, `"a handful"` for `OP_TO5UNITS` exactly, `"several"` for everything else
  plural including any non-named fold-derived interval. **Never an exact number** — precision needs
  a caller holding an actual question, and none exists yet (settled decision 2); this vocabulary is
  structurally incapable of pairing a precise count with a vague class or vice versa (settled
  decision 3), since one side of that pairing never happens. `_plural_unit_type_display` is
  `_unit_type_display`'s plural sibling (`_OP_CLASS_DISPLAY_PLURAL`, its own table, no
  `"OP_GROUPSOMETHING"` entry either) — `type` level stays unpluralized on purpose (a raw DCS type
  string has no general pluralization rule, and inventing one is exactly the wording-fix class of
  work settled decision 5 keeps out of this stage); the presence/fallback branch returns
  `"contacts"`, not `_unit_type_display`'s `"ground"`/`"contact"` split. `_contact_report_text` gains
  one guard at its top (`facts.get("cardinality")` → `_cardinality_phrase`); on the singular path
  (absent, or a `(1, 1)` interval) it calls the exact same `_unit_type_display` with the exact same
  arguments and executes no new code — the regression guard every pre-existing test in this module
  is. Reaches `render_contact_report`, `CONTACT_DETECTED`/`CONTACT_REACQUIRED`, and
  `render_watch_nearest_readback` for free (all three call `_contact_report_text` directly);
  `CONTACT_CLASSIFICATION_CHANGED` does **not** gain it, by construction — it builds its own line
  directly from `_unit_type_display`, never through `_contact_report_text` (settled decision 4: a
  classification-change callout volunteering count chatter on an event about something else would be
  exactly the unrequested cardinality narration that decision warns against). `_OP_CLASS_
  DISPLAY["OP_GROUPSOMETHING"]` was **removed** at this stage — dead code, not a live mis-statement:
  `classification._op_class_of` already excludes `DEFAULT_OP_CLASS` from ever being returned as a
  class-level value, so a `class`-level classification can never hold that value; a presence-level
  contact already says `"ground"` unconditionally, which is what disambiguates it now, structurally,
  not a dict entry. `route_event` gives `CONTACT_CARDINALITY_CHANGED` (`belief.events`) no template
  either — see that module's own entry above. `route_event` accepts `belief.events.Event | UrgentCall`
  and checks which one it got *before* anything else — an `UrgentCall` (Stage 5's manual bypass-gate
  test harness, constructed only by `crew_console.py`'s `!inject-urgent` command; no real
  threat-detection channel exists) speaks immediately with `bypass_gate=True`, no ack/cooldown
  touched; a `belief.events.Event` renders through a per-kind template and auto-acknowledges
  (`belief.tools.acknowledge_event`) the moment it is spoken, so a future brain's `poll_events` never
  re-surfaces it — a kind with no template (`CONTACT_LOST`, `CONTACT_ATTENTION_CHANGED`) is left
  unacknowledged, since body never actually spoke it. `UrgentCall` is a separate small type rather
  than a `bypass_gate` field grafted onto the shared BL-4 `Event` dataclass — `events.py` is out of
  this milestone's Affected Modules.
  `plans/brain-layer/plan.md` BR-1 Stage 1 adds four small templates, all body-written per D5 (the
  decider only ever names a reason/token, never phrasing): `render_unable(reason)` (D11's closed
  `NO_SUCH_COMMAND`/`NO_MATCH`/`NO_LINE_OF_SIGHT` set, an unrecognised reason degrading to a bare
  "Unable." rather than raising), `render_lost_contact()` ("Lost him.", D4's "not silence" case),
  `render_stand_by()` ("Stand by.", D8), and `render_disambiguation(candidates)` (D9's A/B
  question, built only from `ReferenceCandidate.why` strings — no id spoken, this module's
  existing convention — capped at the first three candidates for the spoken phrase).
  `plans/attack-run/plan.md` Stage 1/3 adds `render_target_readback(facts)` (`select target`/
  `step`'s shared "Target, armor, 2 o'clock." readback, no range — the engage readback, not this
  one, speaks range once) and the `render_alignment_*` family: `render_alignment(azimuth_deg,
  elevation_deg, *, tier, azimuth_table, elevation_table)` is the ongoing guidance utterance —
  outside the 12 o'clock sector speaks the clock hour, inside it reads the two word tables
  (`_alignment_phrase_for`, shared by both axes) and says "lined up" once both clear their own
  gate. The two tables are declared in `belief.attack_run` and passed in as data, never imported
  by this module, so `belief.speech` -> `belief.attack_run` -> `belief.speech` is not a circular
  import. **`tier: Literal[1, 2]`** (widened Stage 6, from the Stage 5 `Literal[1]` narrowing) —
  tier 2 (Decision 17 REVISED's `"obstructed"` register) is `", obstructed"` appended to whatever
  the branches above would otherwise have rendered, **uniformly**, including the o'clock branch
  and the `"lined up"` case (`"lined up, obstructed"`, the user's own words, 2026-10-14 second
  direction pass) — one rule, not a second table of pre-qualified phrases, and no tier-aware
  branch in `belief.attack_run._should_emit` either: the qualifier's presence is part of the
  rendered text, so a tier transition is simply a text change the existing change-driven cadence
  already re-fires on, in both directions (entering *and* leaving the obstructed register, pinned
  by `test_decide_lined_up_tier_transition_speaks_once_each_way`/
  `test_decide_tier_transition_speaks_the_qualifier_without_flipping_direction`). `Template` gained
  `"attack_run"`. Stage 5 adds `render_engage_readback(facts)`
  (`engage`'s own readback — unit type, clock, *and* range, once, plus an acquisition-only terrain
  fragment identical in shape to `_contact_report_text`'s own but deliberately not shared with it,
  since that helper also carries a count clause and a `", moving"` tail this milestone's
  vocabulary never calls for) and `render_attack_run_off()` (`"Attack run off."`, `disengage`'s
  readback).
- `src/belief/attack_run.py` (new, `plans/attack-run/plan.md` Stages 2-7) — BL-14's alignment
  derivation. This module and `percept.py` are the only two files under `belief/` allowed to
  mention `relative_direction`/`RelativeDirection` (grep-fenced, `test_attack_run.py`, mirroring
  `belief.contacts`'s `derived_world_position` fence). `AttackRunState` (frozen, `last_spoken_
  azimuth_deg`/`last_spoken_elevation_deg`/`last_spoken_text`/`last_spoken_tier`/`last_known_
  target_alt_m`) is the change-driven cadence's own baseline (Decision 7) — compared against the
  *last spoken* value, never the previous sample. `last_known_target_alt_m` (Stage 6) is separate
  memory, not a speech baseline: it is updated on **every** tick tier 1 succeeds, whether or not
  that tick speaks, so a later tier-2 tick always reads the freshest reconstruction rather than
  one frozen at the last *spoken* moment.
  `decide(state, *, now_sim, ownship, contact, group=None)` is pure, no I/O: it reads `contact.
  last_percept.relative_direction` (Stage 2's own storage mechanism — a whole `Percept` kept on
  `Contact`, not a second per-field store), re-derives the *current* azimuth/elevation from the
  carried offset via `_tier1_alignment` (undo the observing poll's own yaw rotation, add ownship's
  translation since the look, re-rotate via `geometry.alignment_direction`), renders through
  `speech.render_alignment`, and applies the change-driven emit rule. **Tier 2 (Stage 6)**: no
  fresh relative observation (absent, or older than `ATTACK_RUN_RELATIVE_MAX_AGE_S`, two polls)
  falls through to `_tier2_alignment` rather than returning silence — `Contact.position` always
  exists, so there is always *something* to guide on once a target is selected; silence is now
  only the change-driven cadence rule, never "no tier had anything to say." Tier 2's horizontal is
  world-anchored belief (`contact.position.x/z`), **projected forward if `contact.motion.state ==
  "moving"`** (Stage 7/Decision 10) using `group.heading_deg` for direction (`contact.motion is
  None` — never observed for movement — is held exactly like `"stopped"`, never treated as
  moving) and `belief.association_over_time.contact_growth_rate_mps` for speed (the same per-class
  table position-fusion/group-matching already share, not a second one) — **never written back to
  `Contact.position`**. Tier 2's vertical is the **remembered** relative height
  (`remembered_target_alt_m`: `percept.ownship_at_observation.alt_m + relative.up_m`, carried on
  `AttackRunState.last_known_target_alt_m`), never `Contact.last_alt_m` (the ownship's own
  altitude at the last look, Decision 4's finding) and never a world-model query (Decision 4
  REVISED) — `None` (no elevation word at all) only before the very first tier-1 look this
  contact has ever had. **`remembered_target_alt_m` is public, not module-private**
  (`plans/atgm-run-sight-tracking/debug.md`): `body._look_target_position` is a second sanctioned
  caller, mirroring `seen_world_direction`'s existing role for `belief/sight_head.py` — the
  9K113's own "belief" aim row had been reading `Contact.last_position.alt_m` directly (the exact
  value this paragraph's own "never" already rejected for attack-run guidance), a second,
  independent occurrence of the same defect nothing had caught before that debug pass. `TIER2_AZIMUTH_WORD_TABLE` is a separate, narrower one-row table (bare
  `"right"`/`"left"`, not `"come right"`/`"a bit right"` — those words are structurally
  unreachable through it); the elevation axis reuses `ELEVATION_WORD_TABLE` unchanged in both
  tiers. The three named constants (`ATTACK_RUN_LINED_UP_AZIMUTH_DEG`/
  `ATTACK_RUN_ELEVATION_GATE_DEG`/`ATTACK_RUN_CHANGE_THRESHOLD_DEG`) and the word tables are
  declared here, the single source of truth Decision 11 REVISED calls for. `CrewConsole.
  drain_attack_run` (Stage 3) is this module's one caller — **wired into
  `body._run_crew_text_poll_loop` as of Stage 5**, called immediately before `drain_events`
  every poll once `ConsolePerceptionRunner.attack_run_state` is non-`None` (set by `engage`, via
  `CrewConsole.attack_run_transition`'s one-shot signal — this class cannot replace `runner.
  attack_run_state` directly, so it leaves an instruction for the poll loop instead); as of Stage
  7 it also resolves `self.store.group_for_contact(contact.id)` and passes it to `decide` as
  `group`. Decision 13's end condition (the target's own contact record vanishing, e.g. a merge
  abandoning its id with no successor) is handled inside `drain_attack_run` itself, not deferred
  to the wiring: speaks `render_lost_contact()` once, cancels the standing task, and returns
  `None`.
  **`[[BL-B67]]` Stage 2 ("Single unit, never a cluster")**: `seen_world_direction(...,
  single_unit=True)` prefers `percept.aim_unit_direction` (the one cluster member nearest the
  sight, set only on a sight-tier look) over the cluster-centroid `relative_direction`, falling
  back to the latter when it is `None` — the ATGM run's aim, since a two-vehicle centroid misses.
  `_tier1_alignment` never reads `aim_unit_direction`: guidance still aligns on the cluster.
  `aim_unit_direction` sits under the same two-file fence as `relative_direction`
  (`test_attack_run.py`). Stage 1 also adds `vertical=False` (azimuth-only guidance), done by
  forcing an empty elevation table rather than a new branch.
- `src/belief/atgm_run.py` (`[[BL-B67]]`, `plans/bl-b67-atgm-run/plan.md`) — the ATGM run's own
  per-poll state and "when". `AtgmRunState` is carried on `ConsolePerceptionRunner.atgm_run_state`
  **beside** `attack_run_state`, never as a field on it: `AttackRunState` is reset wholesale on
  every re-point, which would silently drop a weapon field. `None` means "no ATGM run engaged".
  Its lifecycle is tied to the attack run (one construction site, `body.py`'s engage-apply block,
  on `engage … missiles`). Stage 1 carried only `contact_id`, which the "Observ on, wait."
  dispatch (`CrewConsole.drain_atgm_engage`) and the sight lock / single-unit aim threading read.
  **Stage 3 adds the state machine itself**: `decide(state, inputs) -> (state, speech, actions)`,
  modelled on `attack_run.decide`/`optic_policy.decide` — pure, no I/O, `speech` a tuple (a poll
  can carry two lines, e.g. launch-and-gone in the same poll), `actions` restricted to `Fire`/
  `SelectStation` (`say` stays a `speech` entry, not an action — a deliberate reading of root
  `CLAUDE.md`'s "Behaviour as actions and params" table, flagged in the module docstring). Phases
  (`AtgmPhase`): `PREPARING` (waits on `observ_observed`, then picks the first loaded station) →
  `TRACKING` (range calls, launch detection, the count-drop-without-launch grace) → `IN_FLIGHT`
  (the backstop, Decision N1: silent after `ATGM_MAX_FLIGHT_S`, no `own_feed_fresh` check — the
  25 s timer alone is authoritative, per round 8's own wording) → `RESETTING` (waits on
  `impact_sequence_running`) → resolves straight through `SELECTING` (never observed as the
  returned state — `_resolve_station_selection`'s one shared rule: stay if still loaded, else next
  loaded step cyclic, else `EMPTY`) back to `TRACKING`/`EMPTY`. **Against synthetic events, by
  design** (Stage 3's own scope) — `LaunchEvent`/`FailedLaunch` are declared here, not imported
  from `perception.own_weapons` (Stage 5, not built), and `Fire.trigger` is a plain string
  (`"atgm-impact"`), not `effector_sequences.EffectorTrigger` (Stage 6's new members, not added
  yet). `family_of` matches a loose substring table (Shturm/Ataka, a stand-in for `atgm.toml`'s
  real DCS-confirmed names, Stage 5/6); `_current_family` prefers the launch event's own type name
  once one exists, else the selected station's store name. Tunables:
  `SHTURM_SPEED_MPS`/`SHTURM_MAX_RANGE_M`/`ATAKA_SPEED_MPS`/`ATAKA_MAX_RANGE_M`/`ATGM_MIN_RANGE_M`
  (Wikipedia figures, round 1), `ATGM_UNCONFIRMED_DROP_GRACE_S` (judgement), `ATGM_MAX_FLIGHT_S`
  (derived from the slower family's own max range/speed plus margin). **`attack_run.decide` also
  gains `guidance_floor` this stage** (settling Stage 1/2's own flagged deferral): `SIGHT_WIDE_
  OPTIC` while an ATGM run is engaged, `UNAIDED_OPTIC` otherwise, threaded through `drain_attack_
  run`/`body.py` at the same `runner.atgm_run_state is not None` granularity `vertical` already
  uses — see that function's own docstring for why not narrower. **`belief.callouts.
  CalloutScheduler.tick` gains `hold_routine`** (the in-flight silence mechanism) — see that
  module's own docstring for the pass-through set and why `CONTACT_ENGAGEMENT_CHANGED` is
  deliberately not in it (round 8, N2). **Not wired into `body.py`'s poll loop yet** — that is
  Stage 7. **Discovered gap, not fixed here** (out of this stage's scope — poll-loop wiring):
  `body.py`'s current engage-apply block (Stage 1) always constructs a *fresh* `AtgmRunState` on
  every `engage … missiles`, including a re-point while an ATGM run is already active. The plan's
  own Co-moving Fields table's "ATGM run active, new target" row instead calls for `atgm` to *keep*
  `phase`/in-flight/`selected_step` and only reset the range latches and `contact_id` — harmless
  today (Stage 1 only carried `contact_id`, nothing to lose), but a real bug once Stage 7 wires
  `decide` in: a re-point mid-flight would silently forget the missile is in flight. Stage 7 (or
  whoever next touches that block) must fix it, not re-introduce it unexamined.
- `src/belief/escalation.py` (BL-5a) — `handle_player_utterance` (§3.5), the one body→brain entry
  point: builds `EscalationPayload` (transcript + `belief.utterance.PartialParse`, never the bare
  transcript alone — the brain disambiguates, it never parses from scratch) and hands it to a
  `BrainClient` (a two-method `Protocol` for a later `ask_player` round trip). `situational_header`
  is a documented stand-in (`{contact_counts, our_position}`, `our_position` present only when an
  `EnrichmentContext` is supplied) — §3.5's "D2 header" is a design discussion, not a data-model
  entry, and no code builds the real header yet. `estimated_units` (`plans/group-contact-model/
  plan.md` Stage 4b) is unconditional, unlike `our_position` — `belief.tools.
  _estimated_units_lower_bound(store)` needs no ownship data; `contact_counts` keeps its existing
  bare-int shape unchanged. `NullBrainClient` does nothing (the honest "no
  brain yet" behaviour — §3.5: "if the brain does nothing, body says nothing"); `DebugPrintBrainClient`
  additionally prints the payload to stderr for session visibility, still producing no spoken output.
  `plans/brain-layer/plan.md` BR-1 Stage 1 adds `BrainReply` (`utterance_id`/`kind` — `"pick"`/
  `"ask"`/`"confirm"`/`"unable"` — plus the fields only the matching `kind` populates) and
  `poll_replies() -> list[BrainReply]` on the `BrainClient` protocol, the asynchronous-reply half
  D2's "the brain replies into its own queue" needs — both stand-ins above simply return `[]`,
  their documented behaviour unchanged.
- `src/belief/brain_reply.py` (`plans/brain-layer/plan.md` BR-1 Stage 2, D10) — the deterministic,
  body-side, pure-function validator every `BrainReply` passes through before
  `CrewConsole._handle_brain_reply` acts on it: a `"pick"`'s id must be one of the candidates
  *this payload offered*; its `BECAUSE` words must appear literally (case-insensitively) in both
  the original transcript and the chosen candidate's own `why` text, and not in any other
  candidate's `why` — the pure-substring reading of "must not be equally true of another
  candidate" (a wrong `PICK CONTACT_7 BECAUSE "tank"` fails because "tank" names *neither*
  candidate's own `why` text, both saying "T-72"; `"near Gemerek"` passes because it names one
  `why` and not the other). A `"confirm"`'s token must be in `DISPATCHED_COMMAND_TOKENS`; an
  `"unable"`'s reason must be one of D11's three. Any rejection degrades to `"ask"` if the payload
  offered candidates, else `"unable" NO_MATCH` — never silence, never a guess. `"ask"` itself
  always passes through unchanged (nothing to validate). `tests/test_brain_reply.py`'s
  `test_wrong_pick_because_tank_degrades_to_ask` is the plan's own required test.
- `src/belief/brain_client.py` (`plans/brain-layer/plan.md` BR-1) — `BrainLayerClient`, the first
  real (non-stand-in) `BrainClient`: an independent copy of `aircraft_client`/`audio_client`'s
  stdlib-`urllib` shape (module independence — no import of `brain-layer/`), except `handle()`
  never blocks the caller (D2) — it hands the payload to a single-slot background worker thread
  and returns in microseconds; the worker does the actual `POST /escalate`. A `handle()` call
  landing while the worker is mid-POST overwrites that slot (this client's own local mirror of
  `brain-layer`'s server-side `job.JobSlot` newest-wins, D3) rather than queuing — the worker,
  once free, only ever posts the most recently handed-over payload.
  **`poll_replies()` no longer performs its own network call on the caller's thread**
  (a pre-Stage-2 prerequisite, `plans/brain-layer/performance-review.md`: a wedged-but-up brain
  process used to cost the full `poll_timeout_s`, 5s, on *every* poll with no backoff — an ~83%
  tick-rate loss on the shared crew-text poll thread at its 1s default interval). It now mirrors
  `handle()`'s own shape: a persistent background thread, started lazily on first call, loops
  forever doing the actual `GET /replies/poll` round trip into an internal buffer;
  `poll_replies()` itself only drains that buffer and returns, in microseconds, regardless of
  whether the far side is healthy, down, or wedged — **never raises** any more (a behaviour change
  from Stage 1's synchronous version; `BrainLayerError` is now raised and caught only inside the
  background thread's own loop, logged and retried after backoff). `_reply_from_dict` is a
  defensive structural parse only (skip malformed items, never raise) — **not** D10's semantic
  validator (`belief.brain_reply`, see its own entry below), which checks a `PICK`'s id was
  actually offered and a `BECAUSE` clause's words actually appear in the transcript.
- `src/mission_memory/entries.py` (BL-8, `plans/bl8-mission-memory/plan.md`) — `Entry`, the
  append-only record every write produces, and its per-`kind` payload dataclasses
  (`GroupPayload`/`AirDefencePayload`/`AttackRunPayload`/`MarkPayload`/`FiredOnPayload`). Decision
  2's split: `EntryPosition.y` is `Contact.last_alt_m` (a last-observed value, no fused estimate,
  `uncertainty_m` says nothing about it), and `as_of_sim` is kept separate from the entry's own
  `t_sim` on purpose — an entry written now may record a look taken moments earlier.
  `AttackRunPayload.outcome`'s `AttackOutcome` literal carries an explicit `"unknown"` (never
  `None`) so a Stage-4-less entry, if one is ever written before that trigger exists, still has a
  real value to serialise. `MotionInfo.dir` and `.outcome` both ship nullable-forever-until-later
  — no direction belief and no destruction-determination signal exist yet (plan's own Risks &
  Unknowns), not an oversight.
- `src/mission_memory/store.py` — `MissionMemory`, the in-memory JSONL-backed log.
  `MissionMemory.append` is the **single construction site** for `Entry` across this whole
  package: `admission.py`/`marks.py`/`query.py`/`tools.py` contain no `Entry(` call at all,
  grep-enforced (`tests/test_mission_memory_store.py`'s
  `test_admission_and_marks_never_construct_entry_directly`, mutation-tested by the Reviewer —
  injecting a second `Entry(` call anywhere in `admission.py` fails it immediately). Decision 4's
  append-only rule means a strike is itself a separate append (`strikes=<seq>` on the new entry),
  never an edit of the struck one; `struck_by` is **rebuilt by replaying the log**
  (`rebuild_struck_by`), tested against both the in-memory store and a genuine JSONL round-trip.
- `src/mission_memory/admission.py` — the `group`/`air_defence`/`fired_on` admission rules
  (Decision 3). **Driven by belief-state transitions, not by percepts or callouts** — `step` is
  called once per poll from `body._mission_memory_step`, after `ContactStore.tick()` has settled
  that poll's belief and before any speech is drained. `_seen_how` reads `Contact.sighting_spans
  [-1].source` for `SeenHow.optic`, deliberately never `Contact.last_percept` (that field's own
  docstring names `belief.attack_run` as its one sanctioned reader outside `Contact`'s pulled-on
  fields, and this module has no standing exception); `SeenHow.range_m` stays `None` — a real fact
  genuinely unavailable from this channel, not fabricated. `_build_entry_position` is Decision 8:
  `lat`/`lon` come from `coordinates.dcs_to_wgs84` on the *believed* `x`/`z`, never DCS ground
  truth, and are `None` for an unregistered theatre — the `ValueError` `dcs_to_wgs84` raises for
  that case is caught here and must never propagate past a memory write into the poll loop.
  Holds the four tuning constants: `GROUP_ENTRY_CONFIDENCE_FLOOR` (a new key — searched for an
  existing "is this nameable yet" threshold on the describe/callout path and found none),
  `RESIGHT_MOVE_M`, `RESIGHT_MIN_INTERVAL_S`, `FIRED_ON_FOLD_WINDOW_S` (the user's own "~2 min").
  `FiredOnTracker` is the one admission rule's own per-shooter suppression bookkeeping, owned by
  the poll loop's caller, deliberately not state on `MissionMemory` itself.
- `src/mission_memory/marks.py` — the commanded-mark path (Decision 6), `mark_here`/`mark_target`,
  reachable by voice and the brain tool only — no new F10 radio-menu entry, per BL-10's explicit
  instruction not to re-expand that tree. **Deliberately does not share `admission.py`'s
  `_build_entry_position`**: that helper is keyed on a `Contact` (it reuses `EnrichmentContext.
  cache.get_or_compute`'s per-contact cache); a mark's subject is sometimes ownship itself, which
  has no `Contact`. The small `dcs_to_wgs84`/landmark duplication in this module's own
  `_mark_position` is accepted rather than forcing one shape neither call site wants. Same
  unregistered-theatre posture as `admission.py`: caught, never raised.
- `src/mission_memory/query.py`, `src/mission_memory/tools.py` — the recall/query surface:
  `recall_memory`'s filters and `get_contact_history`'s fold of belief history with this store's
  own chain for a contact, plus the brain-facing tool wrappers that grew `TOOL_SET` from 15 to 17
  (Decision 5 — `tool_api.py`'s own docstring records the fold-vs-extend reasoning BL-7 argued
  against reopening, and why these two new tools have no existing tool's question to be a subset
  of).
- `src/mission_memory/log.py` — JSONL read/write for the store; no admission or query logic.
- **Import direction (Decision 1) is structurally enforced, not a convention**:
  `mission_memory/` may import `belief`; no module in `belief/` may import `mission_memory`,
  except `belief/tool_api.py` (the composition root of the brain-facing tool surface) —
  grep-enforced against `src/belief/*.py` by `tests/test_mission_memory_import_direction.py`,
  mutation-tested by the Reviewer (injecting an import into `contacts.py` fails it immediately).
  `crew_console.py`'s need to trigger a write without importing `mission_memory` (Decision 6's
  tension with Decision 1) is resolved by **closure injection in `body.py`** — the same pattern
  `speech_log_sink` already uses — rather than carving a second exception.
- `src/belief/crew_console.py` (BL-5a) — `CrewConsole`, the typed-input/printed-output player-facing
  session, deliberately **not** an extension of `belief.console.Console` (that module is an explicit
  developer debug tool; `CrewConsole` runs typed sentences through `parse_utterance`'s grammar and
  speaks proactively, neither of which `Console` does — see the plan's "Module boundary" decision).
  `handle_line` dispatches a `"handled"` parse to `belief.tools.set_attention`/`describe_contact` +
  a `belief.speech` template, and an `"escalated"` one to `handle_player_utterance` (silent, since
  neither stand-in `BrainClient` speaks). `drain_events` (called from `body.py`'s `--crew-text`
  poll loop after each `tick()`) runs `store.unacknowledged_events` through `route_event` — reading
  the unacknowledged queue directly rather than tracking a separate high-water mark works because
  `route_event` itself acknowledges any event it renders, so a handled kind drops out on the next
  call and an unrendered kind (`CONTACT_ATTENTION_CHANGED`) is harmlessly re-skipped every poll.
  `!inject-urgent <contact_id> <text>` is Stage 5's clearly-labelled test harness for the
  bypass-gate/urgent-call path — not a production intent or a real detector.
  `drain_brain(now_sim)` (`plans/brain-layer/plan.md` BR-1, called from `body.py`'s
  `--crew-text` poll loop right after `drain_events`) drains `brain_client.poll_replies()`,
  speaks D8's deterministic "stand by" (`STAND_BY_AFTER_S`, once per outstanding escalation, via
  `_speak_stand_by_if_due`), runs the reply through D10's validator
  (`belief.brain_reply.validate_brain_reply`, see its own entry below), and applies D4's
  revalidation table to whatever comes back (`_handle_brain_reply`): a reply older than
  `BRAIN_REPLY_MAX_AGE_S` is discarded silently; a `"pick"` whose contact is gone, or an `"ask"`
  whose candidates have all vanished, speaks `belief.speech.render_lost_contact` ("Lost him.")
  rather than acting on a stale id; an `"ask"` narrowed to exactly one still-present candidate is
  **confirmed, not acted on** (D4: "only one left" is not the same as "the pilot meant this one")
  via a new `PendingConfirmation.contact_pick: tuple[str, PartialParse] | None` field
  (`belief.voice_commands`) — a mutually-exclusive sibling of the existing `token` field for a
  confirm question that resolves a *contact reference* rather than a command token, committed by
  `handle_transcript`'s existing affirm branch via `dataclasses.replace(parse,
  referenced_contact_id=contact_id)` into `_act`. A `"confirm"` reply reuses
  `PendingConfirmation`/`CONFIRM_WINDOW_S` exactly as the voice confirm-band does — "there is not
  a second confirm mechanism" (D9); its own inline `DISPATCHED_COMMAND_TOKENS` membership check
  is now a second, redundant line of defence behind D10's validator, which already ran first.
  `_pending_escalations: dict[str, tuple[float, PartialParse, str]]` (keyed by `utterance_id`,
  written by `_handle_utterance`) is what `_handle_brain_reply` revalidates against and what
  `_speak_stand_by_if_due` reads for elapsed time — the third tuple element (the original
  transcript, added for Stage 2) is D10's own input, needed to check a `BECAUSE` clause's words
  were actually said.
  `overlay_client: AircraftLayerClient | None` (`plans/overlay-speech-callouts/plan.md`) is a
  second, deliberately separate optional-sink field from `aircraft_client` above — `aircraft_client`
  is BL-6's reserved-for-a-different-purpose field (live search-trigger commands, no reader today),
  while `overlay_client` is read every time `_print` runs. `_print` (the single funnel point both
  `handle_line` and `drain_events` already call for every line of spoken text) is where the overlay
  push lives: after printing a line to `output` it also pushes the same text to
  `overlay_client.push_text_line`, wrapped in its own `try`/`except AircraftLayerError`
  (log-and-continue), the same per-push isolation shape `logger.ConsolePerceptionRunner.run_once`'s
  BL-2.5 push loop uses. A line whose source `OutgoingSpeech` carried `bypass_gate=True` (i.e. only
  an injected urgent call, never a routine readback/contact report/lifecycle line) gets a `"!! "`
  prefix on the *pushed* overlay copy only — `output`'s printed copy stays exactly the text
  `belief.speech` produced, since the prefix is an overlay-display concern, not a change to what
  was spoken. `body.py`'s `--crew-text` branch wires this field the same way `--console`'s own
  `overlay_client` wiring already works: `aircraft_client if args.overlay else None`.
  `speech_client: AudioAdapterClient | None` (BL-10 first slice, `plans/tts-voice-output/plan.md`) is
  a third, separate optional-sink field, read by the same `_print` funnel alongside
  `overlay_client` — `bypass_gate` is threaded straight through as `push_speech`'s `urgent`
  argument instead of a text prefix (no new signal invented, an injected urgent call is the only
  line that ever sets it), and a failed speech push is caught by its own `try`/`except
  AudioAdapterError`, independent of `overlay_client`'s own try/except for the same line — one
  sink's failure never blocks the other's push. `body.py`'s `--crew-text --speech-audio` branch
  wires this to a `belief.audio_client.AudioAdapterClient` built from `--audio-adapter-url`.
  `tasks: TaskStore | None` + `handle_command` (`plans/f10-crew-commands/plan.md`, vocabulary
  widened to 15 tokens and made non-hollow by `plans/f10-command-vocabulary/plan.md` Stage 6) are
  `CrewConsole`'s second, non-text input surface: `body.py`'s `--crew-text --f10-commands` poll
  loop drains player-selected DCS F10 radio-menu tokens (`aircraft_client.get_f10_commands`,
  `GET /f10_commands/poll`) and dispatches each through `handle_command`, the same `_print`
  funnel `handle_line`/`drain_events` already use, via two lookup tables (`_RELATIVE_SCAN_TOKENS`,
  `_BEARING_SCAN_TOKENS`) rather than a 14-branch if/elif. `watch_nearest` (a new
  `_nearest_contact_id` helper — nearest contact by `facts["relative_now"]["range_m"]`, requires
  `enrichment` — plus `set_attention`; its readback, `speech.render_watch_nearest_readback`, speaks
  `"Watching <contact report>."` via `_contact_report_text` since the player named no id) is
  unchanged. `scan_ahead`/`scan_left`/`scan_right`/`scan_full` and the eight `scan_bearing_*`
  tokens replace the old hollow `scan_forward` (D4 — not kept as a synonym): `_handle_scan`
  registers a real `belief.tools.scan_area` `PendingIntent` over an ownship-anchored (relative
  tokens) or compass-absolute (bearing tokens) `AttentionArea` centered on ownship's own position
  at radius `F10_SCAN_RADIUS_M` (an uncalibrated placeholder, same debt class as
  `DEFAULT_SCAN_DEADLINE_S`), *then* fires `aircraft_client.trigger_petrovich_search("forward")`
  wrapped in its own `try`/`except` (D5) — a failed live trigger no longer prevents the task from
  being registered, which is also what makes `cancel_task` (cancels the most-recently-created
  still-`pending` task in `self.tasks`, regardless of source) non-hollow in `--crew-text` sessions
  for the first time. Each scan speaks a fixed readback (`speech.render_scan_readback`,
  `"Scanning <sector label>."`). `tasks` mirrors `aircraft_client`'s own reserved-field pattern;
  `body.py` wires it to the same `ConsolePerceptionRunner.tasks` instance its poll loop already
  ticks. `stop_talking` (Stage 3, `plans/inbound-speech/plan.md`; revised by that plan's Stage 3
  follow-up, user direction 2026-09-20 — "no readback or confirmation, just stop talking... more
  of a debug tool than crew feature") is `handle_command`'s one token with **no readback at
  all** and no `_print` call: `_handle_stop_talking` calls `speech_client.stop()`
  (`belief.audio_client.AudioAdapterClient.stop`, `POST /stop`) when a `speech_client` is
  configured and otherwise no-ops, then `handle_command` returns `[]` directly. `stop()`
  reaches `audio-adapter`'s `AudioSink.interrupt()` without synthesizing or delivering any audio —
  for `--target aircraft-layer` that forwards to `collector.audio_sender.AudioPlaybackSender.
  interrupt` (`POST /audio/stop`), which clears the routine queue and stops in-flight playback
  exactly as `play_audio(..., urgent=True)` already did. The original Stage 3 shipment spoke a
  short `"Copy."` acknowledgement (`speech.render_stop_acknowledged`, now removed) pushed urgent
  through `_print` — that acknowledgement was itself the defect the follow-up fixes: it had to go
  out over the same channel it was interrupting, so asking Petrovich to stop talking made him talk
  once more. `silence` (`plans/silence-command/plan.md`, user direction 2026-10-04) is this
  method's sibling with the opposite relationship to speech: "make Petrovich not talk until my
  next command," chosen **absolute** (nothing is spoken at all while silenced, including an
  injected urgent call) after the user was shown the risk explicitly and accepted it. Handled by
  `_handle_silence`, dispatched from `handle_command`'s own top -- checked *before* the general
  `self.silenced = False` reset every other token now runs there, since `_handle_silence` needs to
  see whether silence was already in effect (a repeated `silence` is a no-op, not a toggle — a
  toggle would make a repeated press ambiguous once the pilot has lost track of state). It speaks
  one fixed word (`speech.render_silence_ack`, `"Quiet."`) *before* setting `self.silenced`, so its
  own acknowledgement is not self-suppressing — the inverse of `stop_talking`'s removed `"Copy."`
  paradox above, not a repeat of it, since the mute is not yet in effect when this line goes out.
  `self.silenced` gates exactly one thing, in exactly one place: `_print`'s push to `speech_client`
  (both the routine and, deliberately, the `bypass_gate=True` urgent branch). `output` and
  `overlay_client` are untouched — the use case is audio ("during radio traffic," "near a friendly
  airbase"), so crew-text/overlay keep working — and so is `speech_log_sink`/the scheduler's own
  `note_reply`/`note_urgent` bookkeeping, which keeps running exactly as if each chosen line had
  been spoken. That last point is what makes this **suppressed, not deferred**: `drain_events`
  keeps calling `self.scheduler.tick` every poll regardless of `silenced`, so belief events are
  still chosen, rendered, and consumed by the scheduler's existing "lost, not deferred" posture for
  anything it does not get to — nothing backs up to be dumped the instant silence ends. Ending
  silence is "any subsequent command," read narrowly on purpose: a token reaching `handle_command`
  (F10, a voice `"act"`, or a committed confirm-band `"affirm"`) ends it, and so does a free-text
  utterance `belief.utterance.parse_utterance` actually resolves to an intent (`_handle_utterance`'s
  own `"handled"` branch) — but an utterance that resolves to nothing (`"escalated"`, stray radio
  chatter the use case exists for) does not, and neither does a voice `"confirm"`/`"say_again"`
  disposition that has not yet committed to a token. `silence` was also added to
  `voice_commands.CANCEL_TOKENS` (`ACT_FLOOR_CANCEL`'s higher confidence floor) — a misfire here is
  arguably worse than a misfired `cancel_task`, since it is Petrovich going quiet near something
  the player never asked to stop hearing about. **Not wired into `brain_reply.
  OFFERED_CONFIRM_VOCABULARY`** (the brain-layer classify prompt's own offered-token mirror) —
  that is a cross-subproject change (`brain-layer/src/prompts.py` plus its own mirrored test) out
  of this change's scope; the asymmetry fails safe per that constant's own docstring (a brain
  `CONFIRM silence` degrades to `ASK`, never misdispatches). Likewise, no DCS-side F10 radio-menu
  button exists for it yet (`aircraft-layer`'s Hook script owns that enumeration) — `silence` is
  reachable today via `!voice silence <ratio> <confidence> 1 0` in the typed harness, and will be
  reachable for real once either side's vocabulary is extended, with no further body-layer change
  needed (`handle_command` already dispatches the token generically).
  `plans/attack-run/plan.md` Stage 1/3 adds `select_target`/`drop_target` to
  `DISPATCHED_COMMAND_TOKENS` (`_handle_select_target`/`_handle_drop_target`,
  `_resolve_attack_target`'s own "watched beats unwatched, then closest" tie-break reusing
  `_report_scope` directly — not `_resolve_follow_target`, whose docstring forbids reuse),
  `attack_target` branches in `_describe_task_for_speech` (`"target"`) and `_describe_token_for_
  confirm`, and `drain_attack_run` (Stage 3) — modelled on `logger.decide_optic`'s `(state_in,
  ...) -> state_out` shape, calling `belief.attack_run.decide` and `_print`ing its speech when
  one is returned, gated on `self.scheduler.busy_until_sim` same as every other reply-lane
  speaker.

  **Stage 4 adds `step`** (`_handle_step`, `_step_candidates`) and **`attack_target_task`
  (`belief.tools`) gains a `descriptor` parameter**, stored on `PendingIntent.descriptor` so a
  later `step` can filter its candidate set by the same `<what>` word the selecting command heard,
  via the shared `descriptor_verdict`, without re-parsing the original command. `_step_candidates`
  reads `store.group_for_contact(target_id)`, never `group_view.collapse` (that function's own
  `units_hi` can be `math.inf`, and nothing here needs the tree). Ordering is **not** sorted once
  and indexed — every press recomputes `facts["relative_now"]["bearing_deg"]`/`["range_m"]` (the
  world-anchored belief channel, deliberately, per Decision 6 — not the tier-1 relative-direction
  channel, which stays Decision 16's single-consumer fence) for the current target and every
  candidate, then picks the smallest strictly-signed `perception.geometry.
  signed_angular_delta_deg`/range delta in the asked direction (`left`/`right` on bearing,
  `near`/`far` on range) — this is what makes `step right` pick a different unit after the
  aircraft circles the formation, proven directly in `test_crew_console.py` by issuing the
  identical command from two different ownship positions. Reaching the end of the ordering speaks
  `render_unable("LAST_IN_ORDER")` rather than wrapping (wrapping would silently re-target a unit
  just stepped past); an ungrouped target speaks `render_unable("NO_GROUP_MEMBERS")`.

  **Stage 5 adds `engage`/`disengage`** (`_handle_engage`, `_handle_disengage`) and **`drain_
  attack_run`'s live wiring**. `_handle_engage` reuses `_parse_target_slots`/`_resolve_attack_
  target` exactly as `_handle_select_target` does when the heard slots carry a what/where
  descriptor (select-then-engage, the spec's `"engage <what> <where>"` form); with no slots it
  resumes whatever is already selected (`_active_attack_target_task`, the helper this stage
  factors out of `drain_attack_run`'s own lookup and reuses for `_handle_step` too). Neither
  handler replaces `ConsolePerceptionRunner.attack_run_state` directly — that field lives on the
  poll-loop runner, not this class (mirroring `OpticState`'s own split) — so each sets `self.
  attack_run_transition` (`"engage"`/`"disengage"`, reset to `None` at the top of every `handle_
  command` dispatch, the same convention `last_command_target_contact_id` follows) as a one-shot
  instruction body.py's poll loop consumes and clears. `_handle_disengage` clears the phase only
  ("stop the run, keep the watch," Decision 2) — the standing `attack_target` task, and the
  selection it represents, survives; `drop_target`/the existing cancel path are the separate
  commands that end the selection. `drain_events` now also reads `_active_attack_target_task()`'s
  contact id and threads it to `scheduler.tick`'s new `attack_run_target_contact_id` keyword
  (Decision 5's suppression gate, below). `_print` gained a fourth `attack_run_fields` argument
  (and `speech_log_sink`'s own callable type grew a third parameter to match) — `drain_attack_run`
  is the only caller that ever supplies it, carrying the target contact id, tier, and current
  azimuth/elevation error for the sortie log.
- `src/belief/voice_commands.py` (`plans/inbound-speech/plan.md` Stage 2, Decision 4 REVISED's
  split) — the act/confirm/say-again band decision (`classify_response`, given `audio_adapter.
  command_matcher.MatchResult`'s fields reproduced as plain arguments — body-layer holds no import
  of that subproject or its vocabulary, module independence) and `classify_yes_no`, a small,
  body-owned affirm/negative word check (not a copy of the adapter's phrase table — a different,
  much smaller closed set answering a yes/no question, consulted only while a confirmation is
  pending). `ACT_FLOOR`/`CONFIRM_FLOOR`/`CONFIRM_WINDOW_S` are behaviour constants split out from
  Decision 4's original five — `VERB_FLOOR`/`MATCH_FLOOR`/`SEPARATION_MIN` stay in `audio-adapter`'s
  `command_matcher.py`. `ACT_FLOOR` is grounded in Stage 1's measured confidence distribution
  (`audio-adapter/research/2026-09-19-corpus-bench-results.md`, holds only while `--prompt` is in
  use — the whisper-model-sweep doc has no confidence distribution, a reviewer-caught wrong
  citation fixed 2026-09-19); `ACT_FLOOR_CANCEL`/`CONFIRM_FLOOR`/
  `CONFIRM_WINDOW_S` are documented-unmeasured placeholders (their own comments say so), pending
  Stage 6 live-sortie data. **`classify_response` gates `confidence` and `match_ratio`
  independently, never as a product** (Decision 4 REVISED AGAIN, `plans/inbound-speech/plan.md`,
  user 2026-09-20, fixing a real category error: `ACT_FLOOR` was measured against confidence alone
  and had been applied to `confidence * match_ratio`, a product systematically lower than either
  factor — four real corpus clips run end to end put two in the confirm band that should have
  acted). `ACT_FLOOR`/`ACT_FLOOR_CANCEL`/`CONFIRM_FLOOR` now compare against `confidence` alone;
  `match_ratio` is accepted for signature parity with the seven-field seam but plays no role in
  the floor comparisons, since it already cleared the adapter's own `MATCH_FLOOR` upstream by the
  time `token` is non-`None` — a second body-side match threshold would just re-penalise something
  already filtered. `verb_anchored=False` (not confidence) is what routes a transcript to the
  brain layer via `"fallthrough"` — this is the revision's second, implicit route into the brain,
  alongside the pre-existing explicit wake word: well-heard speech matching no command pattern is
  exactly what the brain should receive, while a verb-anchored-but-unresolved attempt ("scan
  somethinggarbled") still says again rather than falling through, since the player plainly tried
  to issue a command. `PendingConfirmation` is the one piece of state a confirm question needs
  between two calls — owned and mutated by `crew_console.py`, not this module.
  `CrewConsole.handle_transcript(transcript, confidence, token, match_ratio, verb_anchored,
  ambiguous, now_sim)` (`crew_console.py`) is the new sibling entry point this module's docstring
  predicted: pending-confirmation check first (affirm commits via `handle_command`, negative
  discards silently, anything else discards the stale question and falls through to treat the new
  transcript as its own input), then `classify_response`'s disposition — `"fallthrough"` routes to
  the unchanged `handle_line`; `"act"` reuses `handle_command` directly. `"confirm"`/`"say_again"`
  speak `belief.speech.render_confirm_request`/`render_say_again` through the usual `_print`
  funnel. `!voice <token|-> <match_ratio> <confidence> <verb_anchored:0|1> <ambiguous:0|1>
  <transcript...> [<bearing_degrees>]` is a `!inject-urgent`-style typed test harness for this
  whole pipeline (Stage 2 has no audio and no adapter HTTP wiring yet — Stage 3 adds `GET
  /transcripts/poll`; body-layer cannot compute a real match itself, so this command takes the
  already-matched fields as literal arguments, exactly Stage 3's wire shape). The optional trailing
  integer is `bearing_degrees` (`plans/voice-command-completeness/plan.md` Stage 3) — peeled off
  the transcript's last word when present, so every pre-existing `!voice` invocation with no
  trailing number is unaffected.

  **The report family and the two numeric-bearing tokens are no longer a graceful no-op**
  (`plans/voice-command-completeness/plan.md` Stages 1-3, closing the gap this paragraph used to
  describe: 20 of the 41 recognised voice tokens reached `handle_command` and silently did
  nothing). `report_all`/the nine `report_clock_*`/the eight `report_bearing_<compass>` tokens
  dispatch to `CrewConsole._handle_report` — **a read of current belief only**: no `AttentionArea`,
  no task, no gaze change, no `aircraft_client` call ("report is always about current belief. Scan
  tells to go look" — user, 2026-09-23). It drops `certainty == "lost"` contacts (contacts are
  never pruned, so a report would otherwise grow monotonically over a sortie) and any contact with
  no `relative_now`, applies the family filter, groups via `belief.callouts.group_facts` (the
  bucket+chain merge rule extracted from `group_candidates` so the report and callout paths share
  one aggregation rule rather than two that could drift), and speaks **one utterance**
  (`belief.speech.render_report`, capped at `REPORT_MAX_GROUPS` groups with a trailing `"And
  more."` when truncated) — never one line per group, the same "nothing pre-rendered ahead of
  being spoken" discipline `plans/callout-scheduling/` established. An empty result speaks
  `belief.speech.render_clear` (`"Clear."`, or `"<direction>, clear."`) — **except** a compass/
  numeric-bearing request whose direction sits past the cockpit mask's `rear_cutoff_deg` relative
  to current heading, which speaks `render_no_view` (`"Can't see <direction>."`) instead: answering
  "clear" there would claim a look that is physically impossible, the no-omniscience invariant's
  mirror image. A contact actually believed to sit in the rear hemisphere is still reported
  normally — only the *absence* claim is withheld. `scan_bearing_deg`/`report_bearing_deg` quantise
  their parsed bearing onto the nearest of the eight compass `Sector`s (`_nearest_sector`, 45°
  buckets) and then behave exactly like their compass-word sibling tokens, including the readback/
  confirm-prompt naming the sector rather than the raw number — `PendingConfirmation.
  bearing_degrees` carries the parsed value across a confirm round trip so an "affirm" commit does
  not lose it. `DISPATCHED_COMMAND_TOKENS` (module-level in `crew_console.py`) is the canonical set
  of tokens with real dispatch behaviour; `handle_command` now logs a warning (still returns `[]`)
  for anything outside it, rather than swallowing an unrecognised token silently. `CrewConsole.
  _print`'s non-`bypass_gate` path now also calls `belief.callouts.CalloutScheduler.note_reply` —
  fixing a separate latent defect this milestone's reports made audible: every command readback had
  been unbudgeted since readbacks existed, so a routine callout could queue immediately behind one
  instead of waiting for it to finish speaking.

  **Stage 5 adds `scan_clock_1..12`, the ownship-relative o'clock scan family** (`plans/
  voice-command-completeness/plan.md` Decision 5, user 2026-09-23) — `_CLOCK_SCAN_TOKENS` dispatches
  into `_handle_scan`'s new `relative_clock_hour: int | None` parameter, exactly like the existing
  `sector`/`relative_sector` parameters, registering a `belief.tasks.PendingIntent` whose
  `AttentionArea.relative_clock_hour` is set instead. `_describe_task_for_speech`/`_describe_token_
  for_confirm` gained matching branches so cancel/confirm wording names the hour the same way the
  other two families already do. **Stage 5 also fixes the measured pre-existing defect that a
  compass scan never steered gaze at all** — see `perception/gaze.py`'s and `body.py`'s own
  Structure entries below for the mechanism (`ScanPlan.commanded_legs`, `body._active_gaze`'s
  absolute→relative conversion). The nine new tokens are **unbenched**, same cost class as
  `cancel_scan`/`cancel_watch` before 2026-09-23.
- `src/perception/gaze.py` — `ScanPlan` (module docstring: pure per-`t_sim` `gaze_at`), unchanged
  in its core shape since 2C except for one Stage 5 addition (`plans/voice-command-completeness/
  plan.md` Decision 5): a `commanded_legs: tuple[int, ...] | None` field carrying o'clock legs
  directly, mutually exclusive with the existing `commanded_sector: RelativeSector | None` —
  **the architect's own generalisation, deliberately not a wider `RelativeSector` literal**: a
  single o'clock hour (`scan_clock_1`) is a one-leg `commanded_legs` tuple, exactly as `ahead`
  already degenerates to one leg under `commanded_sector`, and an absolute compass scan converts to
  its current-heading-relative legs the same way (see `body.py`'s entry). `legs_within_wedge(
  center_azimuth_deg, half_width_deg)` is the new public helper this conversion needs: every o'clock
  hour whose own gaze center falls within a wedge, ordered by signed offset (a left-to-right sweep)
  — `_SECTOR_LEGS`'s per-sector tables generalised to an arbitrary wedge. `gaze_at` picks
  `commanded_sector` over `commanded_legs` over free scan, in that order (mutual exclusivity means
  at most one of the first two is ever set).
- `src/belief/mission_phase.py` (BL-7, `plans/bl7-mission-phase-relevance/plan.md`) — parses
  Mission Interpreter's MI-6 `--emit-compact` JSON output directly (a plain file read, not a
  Python import — mission-interpreter isn't the body-layer↔world-model in-process exception) into
  `MissionUnderstandingData` (phases + route). `MissionPhaseTracker` sequences ownship past route
  waypoints via a capture-radius check (`WAYPOINT_CAPTURE_RADIUS_M`, an uncalibrated placeholder —
  same debt class as `visibility.py`'s tier constants) and is **monotonic**: phase progression
  never decrements even if ownship temporarily drifts back outside a waypoint's capture radius
  after being captured once. Pure in-memory state (ints/tuples, no sqlite/thread-unsafe object),
  written only from `body.py`'s poll thread (`.update()`) and read-only from the REPL/`Console`
  thread (`.current_phase()`) — deliberately mirrors `EnrichmentContext.ownship`'s existing
  cross-thread split to avoid this codebase's own recurring sqlite thread-affinity defect class
  (BL-2 Stage 6, BL-5). `load_mission_understanding` raises `ValueError` on schema violation,
  tolerates empty `phases`/`route`. **`get_mission_phase` does NOT extend `TOOL_SET`** (resolves a
  stale roadmap flag from when the tool-freeze point moved to BL-6) — mission-phase proximity
  instead folds additively into `get_situation`'s existing facts payload (`tools.py`,
  `mission_phase_tracker: MissionPhaseTracker | None = None` param, `None` → unchanged output) and
  becomes a **tie-breaker only** under attention rank in `_highest_attention_contact`
  (`_select_from_tier` helper — never overrides a higher attention level, only orders within one).
  `Console.mission_phase_tracker` threads the tracker to `get_situation`'s real call site.
  `body.py` gains `--mission-understanding PATH` to load it. `key_locations` (MI-6's
  `CompactLocation`) carries no position field, so relevance can only be scored against route
  waypoints, not named mission-critical areas — a real, documented gap, not worked around.
- `tools/speak_samples.py` — a dev acceptance aid, not a test: renders sample crew callouts through
  `belief.speech`'s real functions and can POST each to a running `audio-adapter --target local` so
  phrasing is *heard* rather than read. It exists because accepting a speech change through the real
  `--crew-text` pipeline needs a live aircraft layer and therefore the Windows box, which would gate
  a phrasing judgement on hardware access. Assertion-free by design — it is for a human ear, which
  is the one thing the suite cannot be. It found `"a handful trucks"` (a missing connector) on its
  first run, while every unit test of the phrase itself was passing, because the defect existed only
  in the composed sentence. Needs both `PYTHONPATH` entries and this subproject's own interpreter,
  same as the live logger.
- `tests/fixtures/` — committed fixture frames for the replay harness's own tests (see Testing).
  `association.py`'s own fixtures (including the ambiguous multi-candidate scene) are
  hand-authored directly in `tests/test_association.py` rather than as separate files, since a
  live ambiguous scene is harder to stage than a single-target one — noted in that test module's
  own docstring.
