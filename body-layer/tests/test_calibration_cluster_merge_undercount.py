"""Synthetic reproduction of the live 2026-09-18 merge-undercount defect --
`plans/contact-merge-undercount/debug.md`.

A real sortie against a twelve-unit ground calibration complex (SA-3
launcher + SA-3 TR radar, ZU-23 on a Ural, ZSU-23-4, BMP-1, BTR-70, T-72B,
Ural, BM-21, and three AK infantry, all parked within a few hundred metres
of each other) produced roughly five `Contact`s instead of twelve. The
narrated log showed several distinct real objects collapsing into one
contact at first sighting and never separating even as the aircraft closed
to 500 m.

**Why this is a synthetic `ContactStore.ingest()` test, not a full
`tests/fixtures/*.json` replay fixture like `test_mock_flight_chain.py`'s**:
building a twelve-object version of that fixture would require running
every object's bearing/range through the real naked-eye quantisation and
visibility-tier formulas across many polls -- expensive to construct and,
more importantly, no more informative than driving `ContactStore` directly
with the *already-quantised* readings those formulas would produce for a
tight cluster at long range. At ~9 km, `NakedEyePerceptionSource`'s own
30 deg clock bucket and ~1000 m range bucket (`_CLOCK_BUCKET_DEG`,
`_RANGE_BUCKETS_M` in `perception.naked_eye_source`) collapse any two
objects within roughly a bucket-width of each other onto the *identical*
quantised `(bearing_deg, range_m)` pair -- which a twelve-unit complex
spanning a few hundred metres genuinely does at that range. This fixture
constructs exactly that: twelve distinct objects (distinct
`continues_observation_id` chains, mirroring how each real DCS `object_id`
gets its own persistent chain in `naked_eye_source.py`/`hybrid_source.py`),
each first sighted with an *identical* long-range, presence-tier reading
(`classification_raw=object_model.DEFAULT_OP_CLASS`,
`classification_level=SpecificityLevel.PRESENCE` -- naked-eye's honest
`lowres`-tier output, structurally class-blind, see `belief.classification`'s
`PRESENCE_CLASS` docstring), then refining to its own real class and a
well-separated position as range closes over two more polls -- exactly the
progression the log shows (a `SAM`/`armor`/`truck`/`BM-21`/`infantry`
narration replacing an initial run of undifferentiated `ground` callouts).

**This test asserts the CURRENT, still-defective behaviour** (a
characterisation test, not a regression test for a fix that landed) --
see this module's own docstring note and `plans/contact-merge-undercount/
debug.md`'s conclusion for why no fix was applied here: the root cause is
that a presence-tier founding percept carries no class evidence at all, so
`belief.association_over_time.passes_gate`'s spatial gate is the *only*
thing deciding whether two simultaneously-indistinguishable real objects
are "the same contact," and once the first two collapse, every further
same-cluster object's own founding percept sees only that one, single,
already-merged candidate -- the "two-or-more candidates never guess-merge"
safety net can only fire when 2+ *distinct* contacts already exist to be
ambiguous between, and the very first false merge permanently prevents
that from happening again for this cluster. Fixing this honestly requires
a belief shape this codebase does not have yet (group cardinality/
composition that refines over time, per the user's own stated target
progression) -- not a gate-tuning change. Once that model exists, this
test's assertions should be replaced with assertions on the *correct*
progressive-refinement behaviour, and this docstring updated accordingly."""

from __future__ import annotations

from belief.classification import SpecificityLevel
from belief.contacts import ContactStore
from perception import object_model
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    DerivedWorldPosition,
    Observation,
    OwnshipState,
)

_PRESENCE_RAW = object_model.DEFAULT_OP_CLASS  # "OP_GROUPSOMETHING"


def _ownship(t_sim: float, x: float) -> OwnshipState:
    return OwnshipState(t_sim=t_sim, x=x, z=0.0, alt_m=700.0, heading_true_deg=0.0)


def _obs(
    *,
    obs_id: str,
    t_sim: float,
    x: float,
    classification_raw: str,
    classification_level: int,
    bearing_deg: float,
    range_m: float,
    continues_observation_id: str | None,
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=range_m,
        ownship_at_observation=_ownship(t_sim, x),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.5, method="test_fixture"
        ),
        provenance="test_fixture",
        classification_level=classification_level,
        continues_observation_id=continues_observation_id,
    )


#: The real complex's twelve units, each `(label, final class, final
#: bearing offset deg, final range m)` -- final positions spread the twelve
#: objects across ~300 m of cross-range and ~2.5 km of range, a plausible
#: real spread for a ground calibration complex approached head-on, per the
#: live log's clock/range progression (9-10 km down to 0.5 km).
_UNITS: tuple[tuple[str, str, float, float], ...] = (
    ("SA3_LAUNCHER", "OP_SAM", -1.0, 3000.0),
    ("SA3_TR_RADAR", "OP_SAM", -0.5, 3050.0),
    ("ZU23_URAL", "OP_AAA", 0.0, 2200.0),
    ("ZSU23_4", "OP_AAA", 0.5, 2150.0),
    ("BMP1", "OP_ARMOR", 1.0, 2000.0),
    ("BTR70", "OP_ARMOR", 1.5, 1950.0),
    ("T72B", "OP_ARMOR", -1.5, 2050.0),
    ("URAL_TRUCK", "OP_TRUCK", 2.0, 1000.0),
    ("BM21", "OP_MLRS", -2.0, 1000.0),
    ("INFANTRY_1", "OP_INFANTRY", 2.5, 500.0),
    ("INFANTRY_2", "OP_INFANTRY", 3.0, 520.0),
    ("INFANTRY_3", "OP_INFANTRY", -2.5, 480.0),
)


def test_twelve_unit_calibration_cluster_stays_twelve_contacts() -> None:
    """Reproduces the live defect: twelve distinct real objects, first seen
    together at long range where naked-eye's quantisation makes them
    positionally indistinguishable and presence-tier classification makes
    them class-indistinguishable, collapse into far fewer than twelve
    `Contact`s -- and stay collapsed once `continues_observation_id`
    continuity locks each object's own re-sightings onto whichever contact
    its founding percept happened to merge into."""
    store = ContactStore()

    # Poll 1 (t=0): every unit's founding sighting, all quantised to the
    # identical long-range presence-tier reading a real naked-eye channel
    # would emit for a cluster this tight at ~9 km -- see module docstring.
    founding_ids = {}
    founding_observations = []
    for label, _class, _bearing_offset, _range in _UNITS:
        obs_id = f"{label}_FOUND"
        founding_ids[label] = obs_id
        founding_observations.append(
            _obs(
                obs_id=obs_id,
                t_sim=0.0,
                x=0.0,
                classification_raw=_PRESENCE_RAW,
                classification_level=int(SpecificityLevel.PRESENCE),
                bearing_deg=0.0,
                range_m=9000.0,
                continues_observation_id=None,
            )
        )
    store.ingest(founding_observations, now_sim=0.0)

    # Poll 2 (t=30, ownship closed in): each unit's own continuity chain
    # reports its real, resolved class and a still-fairly-coarse
    # medium-range position -- still merges via continuity, not the gate,
    # regardless of what the gate would now say.
    mid_ids = {}
    mid_observations = []
    for label, op_class, bearing_offset, final_range in _UNITS:
        obs_id = f"{label}_MID"
        mid_ids[label] = obs_id
        mid_observations.append(
            _obs(
                obs_id=obs_id,
                t_sim=30.0,
                x=6000.0,
                classification_raw=op_class,
                classification_level=int(SpecificityLevel.CLASS),
                bearing_deg=bearing_offset,
                range_m=final_range * 1.5,
                continues_observation_id=founding_ids[label],
            )
        )
    store.ingest(mid_observations, now_sim=30.0)

    # Poll 3 (t=55, close range, ~500 m-2.5 km per the live log): each
    # unit's true, well-separated position and class -- still continuity,
    # still merges onto whatever poll 1 decided, exactly the live report
    # ("never separate even as the aircraft closes to 500 m").
    final_observations = []
    for label, op_class, bearing_offset, final_range in _UNITS:
        final_observations.append(
            _obs(
                obs_id=f"{label}_FINAL",
                t_sim=55.0,
                x=8500.0,
                classification_raw=op_class,
                classification_level=int(SpecificityLevel.CLASS),
                bearing_deg=bearing_offset,
                range_m=final_range,
                continues_observation_id=mid_ids[label],
            )
        )
    store.ingest(final_observations, now_sim=55.0)

    # The defect: twelve genuinely distinct real objects collapse to a
    # single digit number of contacts, never twelve. This count is not a
    # tuned target -- it is whatever this run of the real, unmodified
    # `ContactStore`/`association_over_time` code actually produces; if a
    # future change to the gate/ambiguity mechanism alters it, that is a
    # real behaviour change worth re-verifying by hand (see module
    # docstring), not a number to edit blindly to make this test pass again.
    # Twelve real units, twelve contacts. This asserted 6 when it was written
    # -- it was built as a reproduction of the false-merge defect, driving
    # twelve distinctly-identified objects through the real ContactStore and
    # watching them collapse, matching the roughly five seen in flight.
    #
    # The presence-tier merge veto fixed it. Kept, inverted, as the regression
    # test for that fix: the cluster is exactly the shape that broke, so it is
    # the right shape to guard.
    #
    # Note what this does NOT claim. Twelve contacts at 2-3 km is arguably too
    # *many* -- a crew member at that range sees "a group", not twelve
    # individually-tracked things, which is what the group contact model
    # (body-layer/ROADMAP.md) exists to represent properly. This test pins the
    # interim behaviour: no false merges. Expect it to change when that model
    # lands, deliberately and with its own reasoning.
    assert len(store.contacts) == len(_UNITS)
