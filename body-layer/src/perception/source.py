"""The `PerceptionSource` interface: the seam every concrete perception tier
(Tier 1 real Petrovich feed, Tier 3 ground-truth proxy) implements, built
*before* either tier so which one wins `plans/pb1-perception-logger/plan.md`
stage 1's live spike is a config choice, not a rewrite trigger.

`poll()` deliberately takes only `(now_sim, ownship_state)` — a concrete
source is responsible for fetching whatever tier-specific data it needs on
its own (a Petrovich `list_indication` feed, or the aircraft layer's
`world_objects` endpoint via `aircraft_client.AircraftLayerClient`), usually
through an injected client a test can swap for a fixture-backed fake. This
keeps `replay.py`'s harness generic: it only has to drive the ownship half
of the loop, never any one tier's payload shape.

`Observation` here is the tier-independent subset of
`plans/body-layer/plan.md` §5's `observation:` schema — the fields every
tier can fill in without knowing about contact association, which is BL-1+
work this plan does not build. `contact_id` is always `None` from a
`PerceptionSource.poll()` call; association happens downstream, later.

`source` is a plain `str`, not a closed `Literal`/enum: the plans this
package was built against enumerate different candidate values
(`petrovich_detection`/`inferred`/`player_report` in `plans/body-layer/
plan.md` §5, `proxy_heuristic` added in `plans/pb1-perception-logger/
plan.md`'s Affected Modules section) and, at the time this module was
written, no concrete tier existed yet to settle which values were actually
needed -- closing the type then would have either under-covered or baked in
a guess. Two concrete tiers exist now (`hybrid_source.
SOURCE_PETROVICH_DETECTION_ASSOCIATED`, defined in that module, and
`SOURCE_NAKED_EYE_VISUAL_FILTERED` below), but a third source value still
isn't enough of a settled set to justify closing the type -- revisit if a
third tier ships.

`SOURCE_NAKED_EYE_VISUAL_FILTERED` is documented here rather than in
`naked_eye_source.py` (unlike `hybrid_source.py`'s own
`SOURCE_PETROVICH_DETECTION_ASSOCIATED`) per
`plans/pb1.5-naked-eye-detection/plan.md`'s Affected Modules section --
`naked_eye_source.py` imports it from here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final, Protocol, runtime_checkable

#: `perception.naked_eye_source.NakedEyePerceptionSource`'s `Observation.
#: source` value -- see module docstring for why this constant lives here
#: rather than in that module.
SOURCE_NAKED_EYE_VISUAL_FILTERED: Final[str] = "naked_eye_visual_filtered"

#: Per-source `Observation.id` prefixes (`plans/pb2-contact-memory/plan.md`'s
#: Interface confirmation gap 1). `HybridPerceptionSource` and
#: `NakedEyePerceptionSource` each mint ids from their own per-instance
#: counter (`f"{prefix}_{count}"`) -- without a distinct prefix per source,
#: two independently-numbered `"OBS_1"`s from the two channels would collide
#: in an append-only observation log keyed by id (`belief.contacts.
#: ContactStore`), silently overwriting one another. Declared here rather
#: than in each source module, mirroring `SOURCE_NAKED_EYE_VISUAL_FILTERED`
#: above -- both sources import both their `source` value and their id
#: prefix from this one shared home.
OBSERVATION_ID_PREFIX_HYBRID: Final[str] = "HYBRID_OBS"
OBSERVATION_ID_PREFIX_NAKED_EYE: Final[str] = "NAKEDEYE_OBS"


@dataclass(frozen=True, slots=True)
class OwnshipState:
    """Ownship kinematic state at one instant, in the units `perception`
    works in throughout: DCS x/z metres, altitude metres, true heading in
    **degrees** (not the aircraft-layer wire format's radians -- see
    `from_telemetry_dict`).

    `pitch_deg`/`bank_deg` (`plans/cockpit-visibility/plan.md`) are also
    degrees, same unit-conversion rule as `heading_true_deg` -- the wire
    format (`aircraft-layer/src/schema/__init__.py`'s `TelemetrySample.
    pitch_rad`/`bank_rad`) is radians, this dataclass is not. Unlike
    heading, neither is wrapped to `[0, 360)`: both are small, signed,
    physically-bounded angles (nose up/down, roll left/right), and wrapping
    would corrupt that sign. Both default to `0.0` (level, unbanked) so
    every existing `OwnshipState(...)` call site -- test fixtures included
    -- keeps compiling and behaving exactly as before; only
    `from_telemetry_dict` (a live/replay telemetry read) ever supplies a
    real, non-zero value.

    Sign convention: standard aviation -- positive `pitch_deg` = nose up,
    positive `bank_deg` = right bank (right wing down).

    **Both signs confirmed against DCS by the user, 2026-09-17** -- "right
    bank is positive, left bank negative" and "pitch down is negative, up
    positive". This closed the riskiest open assumption in
    `plans/cockpit-visibility/`: an inverted *bank* sign would have failed
    *dangerous* rather than fail-safe, silently swapping which side
    Petrovich gains visibility on during a turn. (Consistent with the one
    piece of independent evidence available beforehand: a parked,
    zero-airspeed telemetry sample reads `pitch_rad=+0.0482` (+2.76 deg),
    an airframe sitting slightly nose-up on its gear.)

    No unit test can verify this wire contract -- every test necessarily
    exercises the code's own convention against itself -- so it had to come
    from a real observation. What the tests *do* pin is that the code stays
    consistent with the confirmed convention: `test_geometry.py`'s
    `test_body_relative_direction_bank_rotates_elevation_into_azimuth` at
    the rotation level, and `test_visibility.py`'s
    `test_banking_right_lifts_a_right_side_contact_but_banking_left_does_not`
    at the gate level (the latter deliberately asymmetric, since a
    directly-below contact rotates the same way under either sign once
    `is_visible` folds azimuth through `abs()`).

    If a future DCS change ever inverts this, the fix is a single negation
    where the field is read from the wire, not a change to the geometry."""

    t_sim: float
    x: float
    z: float
    alt_m: float
    heading_true_deg: float
    pitch_deg: float = 0.0
    bank_deg: float = 0.0

    #: Height above the ground below, metres (`plans/binocular-optic/
    #: plan.md` Stage 3). Already on the wire (`TelemetrySample.
    #: altitude_agl_m`) and simply never carried across before, because
    #: nothing needed it: `alt_m` is MSL, which is the right frame for
    #: comparing ownship against a contact's own altitude.
    #:
    #: **The binocular search needs the other one.** How far below the
    #: horizon a patch of ground at range R sits is `atan(agl / R)`, and
    #: over high terrain MSL is not even close -- a sweep aimed with MSL
    #: over a 1500 m plateau would point at the sky. Defaults to `0.0` so
    #: every existing constructor (test fixtures included) is unchanged;
    #: only `from_telemetry_dict` supplies a real value.
    alt_agl_m: float = 0.0

    @staticmethod
    def from_telemetry_dict(data: dict[str, Any]) -> OwnshipState:
        """Convert one aircraft-layer `GET /telemetry/latest` JSON object
        (`aircraft-layer/src/schema/__init__.py`'s `TelemetrySample.to_dict`
        shape) into an `OwnshipState`. Mirrors `TelemetrySample.from_dict`'s
        own naming, on the consuming side of the seam.

        Raises `KeyError`/`TypeError` on a malformed dict -- callers that
        read straight from the network (`logger.py`) are expected to treat
        those as a dropped/skipped poll, the same way
        `collector.server._handle_line` drops a malformed telemetry line
        rather than crashing the export loop.
        """
        return OwnshipState(
            t_sim=float(data["dcs_model_time_s"]),
            x=float(data["position_x_m"]),
            z=float(data["position_z_m"]),
            alt_m=float(data["altitude_msl_m"]),
            heading_true_deg=math.degrees(float(data["heading_true_rad"])) % 360.0,
            pitch_deg=math.degrees(float(data["pitch_rad"])),
            bank_deg=math.degrees(float(data["bank_rad"])),
            alt_agl_m=float(data["altitude_agl_m"]),
        )


@dataclass(frozen=True, slots=True)
class PositionUncertainty:
    """One look's own honest statement of its position error, in metres, as
    an elongated ellipse oriented along that look's own line of sight
    (`plans/precise-position-belief/plan.md`'s "The model"). Perceived
    metadata -- a channel's own declared estimate of how wrong its own
    report might be -- identical footing to `count_bucket`/`apparent_
    motion`/`classification_level` on `Observation`, never a truth field: a
    concrete source computes both fields from its own honest error model
    (`perception.estimation`), never from anything DCS-truth-derived beyond
    what the perceived bearing/range already carry.

    `sigma_cross_m` -- 1-sigma error perpendicular to the line of sight
    (bearing error turned into metres at the observation's own true range).
    `sigma_down_m` -- 1-sigma error along the line of sight (range error).
    Both are declared at the observation's own true range; `belief.
    position_belief` is what turns this pair into a 2x2 covariance oriented
    along `Observation.bearing_deg`/`Percept.bearing_deg`."""

    sigma_cross_m: float
    sigma_down_m: float


@dataclass(frozen=True, slots=True)
class DerivedWorldPosition:
    """A target position derived from bearing/range rather than read
    directly off ground truth -- `plans/body-layer/plan.md` §5's
    `observation.derived_world_position`. `None` on an `Observation` until a
    concrete source's geometry step has actually computed one."""

    x: float
    z: float
    confidence: float
    method: str


#: `classification_raw`'s specificity, on `belief.classification.
#: SpecificityLevel`'s 0-3 scale -- stated here as a bare `int`, not that
#: enum, because `perception/` must not import `belief/` (production stays
#: upstream of consumption, per this project's module boundary). `2` is that
#: enum's `CLASS` value: every existing `Observation` construction site
#: predates this field and emits a class-level (`OP_*` bucket) claim, so
#: defaulting here keeps every one of them compiling and behaving exactly as
#: before (`plans/classification-refinement/plan.md` Stage 2).
_CLASSIFICATION_LEVEL_CLASS_DEFAULT = 2


@dataclass(frozen=True, slots=True)
class Observation:
    """One tier-independent perception observation -- the return type of
    `PerceptionSource.poll()`. See the module docstring for `contact_id` and
    `source`'s scope at this stage.

    `classification_level` is the producing channel's own statement of how
    specific `classification_raw` is (see `_CLASSIFICATION_LEVEL_CLASS_
    DEFAULT` above) -- belief code trusts this rather than re-deriving it by
    parsing `classification_raw`.

    `continues_observation_id` is `plans/contact-duplication-ambiguity-
    runaway/plan.md`'s object-permanence mechanism: when a concrete source
    resolves a DCS `object_id` this poll that it has *ever* previously
    resolved (however long ago, subject to `belief.decay.
    object_id_continuity_valid`'s expiry check on the consuming side), it
    sets this to that prior emission's `Observation.id`. May reference an
    observation from an arbitrary number of polls ago, not necessarily the
    immediately preceding one -- each source's own persistent per-object-id
    map is never cleared mid-session (see `naked_eye_source.py`/
    `hybrid_source.py`). Still not a DCS truth field crossing the
    `perception`/`belief` boundary in a new shape: it is exactly the kind of
    `observation_id`-shaped bookkeeping reference `belief.percept.Percept.
    observation_id` already legitimately carries -- `object_id` itself never
    leaves `perception/`. `None` when the source resolved no `object_id`
    this poll, or resolved one it has never seen before."""

    id: str
    contact_id: str | None
    t_sim: float
    t_wall: float
    source: str
    classification_raw: str
    bearing_deg: float
    range_m: float
    ownship_at_observation: OwnshipState
    derived_world_position: DerivedWorldPosition | None
    provenance: str
    classification_level: int = _CLASSIFICATION_LEVEL_CLASS_DEFAULT
    continues_observation_id: str | None = None
    #: `plans/group-contact-model/plan.md` Stage 2 -- the ED count-vocabulary
    #: bucket name (`perception.clustering.count_bucket_for`) this
    #: observation's own cluster resolved to, or `None` for any source that
    #: does not (yet) cluster and so carries no count evidence at all (the
    #: scope/hybrid channel; `belief.contacts.Contact.record` leaves
    #: `cardinality` untouched -- a hold, not a claim of exactly one -- when
    #: this is `None`). Perceived metadata, same footing as `classification_
    #: level`: a channel's own honest statement of how many real objects one
    #: report stands for, not a truth field.
    count_bucket: str | None = None
    #: `plans/movement-detection/plan.md` -- the movement gate's tri-state
    #: verdict (`perception.motion.is_apparently_moving`), the *only* thing
    #: allowed to cross the `perception`/`belief` boundary for movement; the
    #: velocity vector itself never does (that module's own docstring).
    #: `None` is the default and means "not evaluated" (a source that
    #: doesn't compute movement, or no velocity sample was available this
    #: poll) -- unknown, never "stopped", same tri-state discipline as
    #: `is_ownship`/`heading_true_deg` elsewhere in this package.
    apparent_motion: bool | None = None
    #: `plans/precise-position-belief/plan.md` Stage 1 -- the channel's own
    #: declared error ellipse for this look's `bearing_deg`/`range_m`. Both
    #: concrete sources populate this unconditionally as of that plan;
    #: `None` is the default only so a construction site that predates it
    #: (test fixtures included) keeps compiling. `belief.percept.percept_of`
    #: carries this straight through -- see that module's own field.
    position_uncertainty: PositionUncertainty | None = None
    #: `plans/dcs-driven-los/plan.md` (X-B29) -- the DCS-driven, true-to-true
    #: LOS verdict (`building_clear and terrain_clear`) joined onto this
    #: observation's own cluster, when every member agrees (including
    #: all-`None`), else `None` -- `apparent_motion`'s own "identical keeps,
    #: disagreement degrades" rule, generalised. `None` is the default and
    #: means "no live verdict" (unknown, never a guessed clear/masked) --
    #: set by `naked_eye_source.py` only for admitted candidates; the hybrid
    #: channel has no geometric gate to source it from and never sets this.
    live_los_clear: bool | None = None


@runtime_checkable
class PerceptionSource(Protocol):
    """A tier-independent producer of `Observation`s. See the module
    docstring for why `poll()`'s signature is this narrow."""

    def poll(self, now_sim: float, ownship_state: OwnshipState) -> list[Observation]:
        """Return zero or more new `Observation`s as of `now_sim`. Must not
        block indefinitely -- a live-tier implementation is responsible for
        its own network/IO timeouts."""
        ...
