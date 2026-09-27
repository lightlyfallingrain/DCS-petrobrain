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
- `src/perception/geometry.py` — bearing/range helpers, shared by every tier (per both
  investigator sessions, no tier has a native range field). Calls world-model's
  `query.describe_position` for a single-point elevation lookup. `line_of_sight_clear` (LOS
  terrain-masking) is now a thin wrapper delegating to world-model's own
  `query.line_of_sight.line_of_sight_clear` (moved there so LOS is an ownship-agnostic
  point-A-to-point-B primitive, not body-layer-owned logic — `plans/
  world-model-los-generalization/plan.md`); this module's own docstring on the
  `sample_grid`-vs-`describe_position` sampling-cost tradeoff moved with it into that new
  module's docstring, not duplicated here.
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
  `plans/detection-cones-slice1/plan.md`) — `check_visibility`, the naked-eye channel's four
  composed plausibility gates (cockpit mask, per-optic field of view, angular-radius recognition
  tier, terrain LOS via `geometry.py`). `VisibilityResult.tier` is a **computed achieved tier**
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
- `src/perception/optics.py` (`plans/detection-cones-slice1/plan.md`, slice 1 of the "detection
  cones" milestone) — `Optic` (`name`, `magnification`, `fov_half_angle_deg: float | None`,
  `boresight_azimuth_deg: float = 0.0`) and two named instances: `UNAIDED_OPTIC` (M=1.0, no FOV
  restriction, **the default `check_visibility` optic as of 2026-09-20**) and `BINOCULAR_OPTIC`
  (M=`BINOCULAR_RANGE_MULTIPLIER` = 4.0, **no longer the default** — a deliberate, narrower,
  raised-to-the-eyes act). `BINOCULAR_OPTIC` is a Б-6 6x30 (~8.5 deg true field): magnification
  derived as 6x raw glass times a ~0.67 unstabilised-platform penalty (stated in prose, not a
  separate dataclass field — an earlier same-session `handheld_effectiveness`/
  `effective_magnification` split was tried and reversed, see `visibility.py`'s own docstring for
  why: a derating factor invented only to cancel out a magnification change is a behaviour knob
  dressed as optics), and `fov_half_angle_deg=4.25` (half the true field) — **the first real,
  non-`None` FOV value in this table**, safe now specifically because binoculars are no longer the
  default: no concrete `PerceptionSource` calls `check_visibility` with this optic yet (plan
  Decision 4), so the value cannot misfire a gate in the live path today. `within_optic_fov` tests a
  circular field of view (true angular separation from `(boresight_azimuth_deg, 0.0)`, spherical
  law of cosines, not an independent azimuth-box/elevation-box check); `None` means unrestricted.
  **The 9K113 sight is deliberately deferred out of this slice** (user, 2026-09-20) — its own
  magnification/FOV/field-of-regard figures, sourced and unverified alike, stay recorded in
  `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md` until it gets its own slice;
  `Optic` therefore carries no field-of-regard fields at all (how far an optic can be *pointed*, as
  opposed to what it shows once pointed) — with no sighted optic in the table they would all be
  `None` and untested. Pure, no I/O, mirrors `cockpit_mask.py`'s own posture.
- `src/perception/clustering.py` (`plans/group-contact-model/plan.md` Stage 2, reworked
  anisotropic by Stage 3b-i, then reworked again to a true angular predicate by Stage 3b-i rev.2) —
  position-only resolution clustering. **Separability is a 3D angle subtended at the observer,
  compared against each candidate's own apparent angular size — not a world-space ellipse.**
  `angular_separation_rad(observer, a, b)` is the true angle between two observer→candidate unit
  vectors (`atan2(|cross|, dot)`, stable near zero); `angular_size_rad(size_m, slant_range_m)` is
  `size_m / slant_range_m`. Two candidates merge when they fail the two-apples criterion
  `theta_sep >= 0.5 * (theta_size(a) + theta_size(b))` — two discs of angular diameter `d_a`, `d_b`
  visually overlap exactly when their centre separation is under `(d_a + d_b) / 2` — **or** fail a
  named floor, `theta_sep * BINOCULAR_RANGE_MULTIPLIER >= LOWRES_ANGULAR_RADIUS_RAD`, provably
  non-binding for anything `visibility.py` actually admitted (kept as a one-line self-consistency
  check, not because it ever fires). No new constant and no magnification term — `M`
  (`BINOCULAR_RANGE_MULTIPLIER`) cancels out of the merge criterion entirely, since both sides are
  angles scaled by the same optic. This reproduces the old ellipse's anisotropy *for free*, because
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
  quantisation of its own any more, only true angular geometry.
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
  are done — see `detection_trace.py`'s own Structure entry.
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
- `src/belief/` — PB-2's observation-*consumption* package (`perception/` stays observation
  *production*): `percept.py` (`Percept`/`percept_of`, the structural no-omniscience boundary —
  belief code never sees `Observation.derived_world_position` or a DCS object id),
  `contacts.py` (`Contact`/`SightingSpan`/`ContactStore` — append-only observation log,
  `ingest`/`tick`). `ingest` (`plans/group-contact-model/plan.md` Stage 3a) runs a read-only
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
  threaded through `tools.py`/`console.py`/`logger.py` above. `semantic_facts_for` (osm-landcover-
  optimization, `plans/osm-landcover-optimization/plan.md` Design D7) reads world-model's newer
  `SettlementInfo`/`WaterInfo.subtype` for wording ("a built-up area" for an unnamed built-up
  settlement; "a river"/"a lake"/"a reservoir" for unnamed water) and appends two more facts after
  every pre-existing one: a landcover fact ("in forest"/"in orchards"/"in scrubland"/"in open
  fields"/"on barren ground") whenever `inside_landcover` is non-`None` and its class isn't
  `"built_up"` (already covered by `inside_settlement`), and a coast fact ("over the sea, off the
  coast (Nm)" or "near the coast (Nm)") within the new `COAST_FACT_RADIUS_M` (5000m) or whenever
  `nearest_coastline.side == "sea"`.
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
- `src/logger.py` — the PB-1 deliverable: `PerceptionLogger` polls ownship telemetry + a list of
  `PerceptionSource`s, formats each `Observation` as flat text; fully tested against a fake
  source, tier-agnostic. `main()` is the one place that plugs in the concrete
  `HybridPerceptionSource` and (PB-1.5) `NakedEyePerceptionSource` and drives the poll loop
  (`python -m logger --aircraft-layer-url ... --theatre ... --world-model-db ...` — see
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
- `src/perception/detection_trace.py` (BL-9) — `GateOutcome` (`COCKPIT_MASK`/`RANGE_OR_SIZE`/
  `TERRAIN_LOS`/`ADMITTED`), the mutable `DetectionTrace` record (one per candidate per poll,
  ground truth by construction, same footing as `Observation`/`WorldObjectCandidate` — no
  `belief/` import), and `DetectionTraceCollector`, the small accumulator
  `visibility.check_visibility`'s new optional `trace` parameter and `NakedEyePerceptionSource`
  append/annotate into. `check_visibility` records one entry per call, at whichever of its three
  gates decided a candidate's fate (or `ADMITTED`); `range_threshold_m`/`threshold_bound`
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
  `Observation`/`Contact`/`Event` streams are identical.
- `src/detection_trace_writer.py` (BL-9) — `DetectionTraceWriter`, the one module in this
  codebase deliberately allowed to hold both ground truth and belief at once: given a
  `DetectionTraceCollector` and a `ContactStore`, it resolves each admitted entry's `Contact.id`
  by scanning `store.contacts`' `Contact.contributing_observation_ids` for the entry's
  `observation_id` (an `O(contacts x history)` rebuild every poll, an accepted cost for a
  single-sortie debug artifact, not a standing index), appends one JSON line per record to a
  file, and clears the collector. **Read-only and one-directional** — it never calls anything
  that mutates `ContactStore`, and no ground-truth field is ever passed into `ContactStore.
  ingest`/`Percept`/`Contact`; `belief/percept.py`'s structural no-omniscience boundary is
  untouched. Deliberately sits beside `logger.py`, not inside `perception/` or `belief/` — neither
  package gains an import because of this module. Buffers `DEFAULT_FLUSH_EVERY_N_POLLS` (5) polls'
  worth before flushing, so disk I/O never sits on the poll loop's own critical path.
- `body-layer/tools/summarize_detection_trace.py` (BL-9) — the post-flight reducer, not a test
  (same "dev acceptance aid" posture as `speak_samples.py`): reads a `--detection-trace` JSONL
  file and prints the actual flight-debrief table — per object, the range at which the
  presence/class/type tiers were first admitted, and the list of objects that cleared the cockpit
  mask (plausibly "on screen") but never reached `ADMITTED` at any tier. That second list is
  stated in its own output as an approximation, not a verified claim — code can confirm an object
  cleared the geometric gates, not that the pilot's own monitor rendered it large enough to
  notice.
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
  trailing `.0` (`_format_range_km`); a semantic fragment's embedded trailing distance (e.g. `"near
  a road (439m)"`) is separately rounded to the nearest 100 m with a `~` prefix
  (`_round_enrichment_fragment`, a display-only regex post-process — `enrichment.py`'s
  `SemanticFact.text` itself is untouched and stays shared with the unaffected `belief.console`
  debug path). A real coalition implementation should eventually *infer* coalition from unit-type
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
- `src/belief/crew_console.py` (BL-5a) — `CrewConsole`, the typed-input/printed-output player-facing
  session, deliberately **not** an extension of `belief.console.Console` (that module is an explicit
  developer debug tool; `CrewConsole` runs typed sentences through `parse_utterance`'s grammar and
  speaks proactively, neither of which `Console` does — see the plan's "Module boundary" decision).
  `handle_line` dispatches a `"handled"` parse to `belief.tools.set_attention`/`describe_contact` +
  a `belief.speech` template, and an `"escalated"` one to `handle_player_utterance` (silent, since
  neither stand-in `BrainClient` speaks). `drain_events` (called from `logger.py`'s `--crew-text`
  poll loop after each `tick()`) runs `store.unacknowledged_events` through `route_event` — reading
  the unacknowledged queue directly rather than tracking a separate high-water mark works because
  `route_event` itself acknowledges any event it renders, so a handled kind drops out on the next
  call and an unrendered kind (`CONTACT_ATTENTION_CHANGED`) is harmlessly re-skipped every poll.
  `!inject-urgent <contact_id> <text>` is Stage 5's clearly-labelled test harness for the
  bypass-gate/urgent-call path — not a production intent or a real detector.
  `drain_brain(now_sim)` (`plans/brain-layer/plan.md` BR-1, called from `logger.py`'s
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
  was spoken. `logger.py`'s `--crew-text` branch wires this field the same way `--console`'s own
  `overlay_client` wiring already works: `aircraft_client if args.overlay else None`.
  `speech_client: AudioAdapterClient | None` (BL-10 first slice, `plans/tts-voice-output/plan.md`) is
  a third, separate optional-sink field, read by the same `_print` funnel alongside
  `overlay_client` — `bypass_gate` is threaded straight through as `push_speech`'s `urgent`
  argument instead of a text prefix (no new signal invented, an injected urgent call is the only
  line that ever sets it), and a failed speech push is caught by its own `try`/`except
  AudioAdapterError`, independent of `overlay_client`'s own try/except for the same line — one
  sink's failure never blocks the other's push. `logger.py`'s `--crew-text --speech-audio` branch
  wires this to a `belief.audio_client.AudioAdapterClient` built from `--audio-adapter-url`.
  `tasks: TaskStore | None` + `handle_command` (`plans/f10-crew-commands/plan.md`, vocabulary
  widened to 15 tokens and made non-hollow by `plans/f10-command-vocabulary/plan.md` Stage 6) are
  `CrewConsole`'s second, non-text input surface: `logger.py`'s `--crew-text --f10-commands` poll
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
  `logger.py` wires it to the same `ConsolePerceptionRunner.tasks` instance its poll loop already
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
  once more.
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
  compass scan never steered gaze at all** — see `perception/gaze.py`'s and `logger.py`'s own
  Structure entries below for the mechanism (`ScanPlan.commanded_legs`, `logger._active_gaze`'s
  absolute→relative conversion). The nine new tokens are **unbenched**, same cost class as
  `cancel_scan`/`cancel_watch` before 2026-09-23.
- `src/perception/gaze.py` — `ScanPlan` (module docstring: pure per-`t_sim` `gaze_at`), unchanged
  in its core shape since 2C except for one Stage 5 addition (`plans/voice-command-completeness/
  plan.md` Decision 5): a `commanded_legs: tuple[int, ...] | None` field carrying o'clock legs
  directly, mutually exclusive with the existing `commanded_sector: RelativeSector | None` —
  **the architect's own generalisation, deliberately not a wider `RelativeSector` literal**: a
  single o'clock hour (`scan_clock_1`) is a one-leg `commanded_legs` tuple, exactly as `ahead`
  already degenerates to one leg under `commanded_sector`, and an absolute compass scan converts to
  its current-heading-relative legs the same way (see `logger.py`'s entry). `legs_within_wedge(
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
  written only from `logger.py`'s poll thread (`.update()`) and read-only from the REPL/`Console`
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
  `logger.py` gains `--mission-understanding PATH` to load it. `key_locations` (MI-6's
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
