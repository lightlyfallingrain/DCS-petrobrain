"""Tests for `belief.attack_run` -- `plans/attack-run/plan.md` Stages 3/6/7's
pure alignment derivation (tier 1, the live look; tier 2, the degraded
fallback with Decision 10's projection), `plans/attack-run-sortie-fixes/
plan.md` BL-B70's cause taxonomy and §1/§2/§4/§8/§9/§10/§11 fixes, plus
`belief.speech.render_alignment`'s word-table rendering, and the grep
fence that keeps `Percept.relative_direction` to its two sanctioned
readers."""

from __future__ import annotations

import inspect
import pathlib
import re

import pytest

from belief import attack_run as attack_run_module
from belief import percept as percept_module
from belief.attack_run import (
    ATTACK_RUN_ELEVATION_GATE_DEG,
    ATTACK_RUN_LINED_UP_AZIMUTH_DEG,
    ATTACK_RUN_RELATIVE_MAX_AGE_S,
    AZIMUTH_WORD_TABLE,
    ELEVATION_WORD_TABLE,
    TIER2_AZIMUTH_WORD_TABLE,
    AttackRunState,
    _no_look_cause,
    _tier1_alignment,
    _tier2_alignment,
    decide,
)
from belief.contacts import Contact
from belief.groups import Group
from belief.motion import MotionBelief, MotionState
from belief.percept import Percept
from belief.position_belief import Covariance2D, PositionEstimate
from belief.speech import render_alignment
from perception.naked_eye_source import ATTACK_TARGET_LOS_MAX_AGE_S
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC
from perception.source import OwnshipState, RelativeDirection

_RELATIVE_DIRECTION_PATTERN = re.compile(
    r"\brelative_direction\b|\bRelativeDirection\b"
)


def _ownship(
    *,
    x: float = 0.0,
    z: float = 0.0,
    alt_m: float = 500.0,
    heading_true_deg: float = 0.0,
    pitch_deg: float = 0.0,
    bank_deg: float = 0.0,
    t_sim: float = 0.0,
) -> OwnshipState:
    return OwnshipState(
        t_sim=t_sim,
        x=x,
        z=z,
        alt_m=alt_m,
        heading_true_deg=heading_true_deg,
        pitch_deg=pitch_deg,
        bank_deg=bank_deg,
    )


def _contact_with_relative_direction(
    *,
    ownship_at_observation: OwnshipState,
    relative: RelativeDirection,
    t_sim: float = 0.0,
) -> Contact:
    percept = Percept(
        t_sim=t_sim,
        source="naked_eye_visual_filtered",
        classification_raw="OP_ARMORED",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=ownship_at_observation,
        observation_id="OBS_1",
        relative_direction=relative,
    )
    return Contact.from_percept("CONTACT_1", percept)


def _group(
    *,
    movement_state: MotionState | None = None,
    heading_deg: float | None = None,
    contact_id: str = "CONTACT_1",
) -> Group:
    """A minimal `belief.groups.Group` fixture -- Stage 7/Decision 10's own
    inputs (`movement_state`/`heading_deg`), nothing else populated."""
    return Group(
        id="GROUP_1",
        member_contact_ids=frozenset({contact_id}),
        established_sim=0.0,
        last_reconciled_sim=0.0,
        movement_state=movement_state,
        heading_deg=heading_deg,
    )


# -- the grep fence (mirrors `test_contacts.
# test_belief_source_never_references_derived_world_position`) ----------


def test_belief_never_references_relative_direction_except_sanctioned_readers() -> None:
    """`plans/attack-run/plan.md` Decision 16 item 4: no file under
    `belief/` may mention `relative_direction`/`RelativeDirection` except
    `percept.py` (the projection) and `attack_run.py` (the one consumer).
    Word-boundary-aware so it does not false-positive on
    `body_relative_direction`/`alignment_direction`, which legitimately
    appear throughout `belief/contacts.py` and elsewhere."""
    belief_dir = pathlib.Path(inspect.getfile(attack_run_module)).parent
    assert belief_dir.name == "belief"

    checked_any = False
    for path in belief_dir.glob("*.py"):
        if path.name in ("percept.py", "attack_run.py"):
            continue
        checked_any = True
        text = path.read_text()
        assert not _RELATIVE_DIRECTION_PATTERN.search(text), (
            f"{path} references relative_direction"
        )
    assert checked_any

    # Sanity check both exempted modules actually use it -- the grep is
    # exercised, not a tautology.
    assert _RELATIVE_DIRECTION_PATTERN.search(inspect.getsource(percept_module))
    assert _RELATIVE_DIRECTION_PATTERN.search(inspect.getsource(attack_run_module))


# -- decide(): tier 1's re-rotation and the two-gate/cadence rules -------


def test_decide_falls_through_to_tier_2_when_the_contact_has_no_percept() -> None:
    """Stage 6: `Contact.position` always exists (founding requires it),
    so there is no longer a "nothing to guide on" silence once a target is
    selected -- `decide` falls straight to tier 2. Elevation is the one
    thing genuinely absent here (`contact.last_percept.relative_direction`
    is `None`, so no tier-1 look has ever supplied a remembered height,
    Decision 4 REVISED's fail-open case): the contact sits dead ahead at
    the founding bearing/range (0 deg, 1000 m), so tier 2's azimuth is
    "lined up" and the elevation axis never fires at all.

    **No qualifier** -- `BL-B70`'s cause taxonomy (`plans/
    attack-run-sortie-fixes/plan.md` §8): this contact carries no live LOS
    verdict at all (`live_los_clear` defaults `None`), which is the
    `"unknown"` cause, fail-open, no qualifier -- not `", obstructed"`,
    which now fires only on a fresh `live_los_clear is False`."""
    contact = Contact.from_percept(
        "CONTACT_1",
        Percept(
            t_sim=0.0,
            source="naked_eye_visual_filtered",
            classification_raw="OP_ARMORED",
            bearing_deg=0.0,
            range_m=1000.0,
            ownship_at_observation=_ownship(),
            observation_id="OBS_1",
            relative_direction=None,
        ),
    )
    state = AttackRunState()

    new_state, speech = decide(state, now_sim=0.0, ownship=_ownship(), contact=contact)

    assert speech is not None
    assert speech.text == "Lined up."
    assert new_state.last_spoken_tier == 2


def test_decide_falls_through_to_tier_2_once_the_relative_observation_goes_stale() -> (
    None
):
    """Stage 6/Decision 4 REVISED's memory mechanism, pinned numerically:
    the first (tier-1) call sees the target 300 m *below* ownship
    (`up_m=-300.0`) and must remember that reconstructed altitude
    (`ownship_at_observation.alt_m + up_m` = 500 - 300 = 200) rather than
    falling back to `ownship.alt_m` once sight is lost. If tier 2 wrongly
    used `ownship.alt_m` as the target's altitude, the elevation axis
    would read 0 deg (level) instead of ~-16.7 deg, and the rendered text
    would silently lose the elevation word."""
    contact = _contact_with_relative_direction(
        ownship_at_observation=_ownship(t_sim=0.0),
        relative=RelativeDirection(forward_m=1000.0, right_m=0.0, up_m=-300.0),
        t_sim=0.0,
    )
    state = AttackRunState()

    state, speech1 = decide(state, now_sim=0.1, ownship=_ownship(), contact=contact)
    assert speech1 is not None
    assert speech1.text == "A little lower."
    assert state.last_known_target_alt_m == pytest.approx(200.0)

    # Tier 1's and tier 2's elevation axis render the identical "A little
    # lower." with no live LOS verdict at all (the `"unknown"` cause,
    # fail-open, no qualifier) -- so the tier transition is silent by
    # `_should_emit`'s own text-equality veto (the same accepted collapse
    # `test_decide_lined_up_tier2_unknown_cause_collapses_the_transition`
    # documents). A fresh, genuine DCS LOS block distinguishes the two
    # ticks' text so the memory this test actually cares about (tier 2's
    # elevation reading the *remembered* altitude, not `ownship.alt_m`)
    # is still visible in what is spoken.
    contact.live_los_clear = False
    contact.last_seen_sim = ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.01
    _state2, speech2 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.01,
        ownship=_ownship(t_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.01),
        contact=contact,
    )

    assert speech2 is not None
    assert speech2.text == "A little lower, obstructed."


def test_decide_dead_ahead_and_level_lines_up_and_speaks_once() -> None:
    contact = _contact_with_relative_direction(
        ownship_at_observation=_ownship(),
        relative=RelativeDirection(forward_m=1000.0, right_m=0.0, up_m=0.0),
    )
    state = AttackRunState()

    new_state, speech = decide(state, now_sim=0.1, ownship=_ownship(), contact=contact)

    assert speech is not None
    assert speech.text == "Lined up."

    # Design A: spoken once, then silence while nothing has changed.
    _state2, speech2 = decide(
        new_state, now_sim=0.2, ownship=_ownship(), contact=contact
    )
    assert speech2 is None


def test_decide_outside_the_sector_speaks_the_clock_hour() -> None:
    # A target 90 degrees off the nose (dead right) sits well outside the
    # 12 o'clock sector -- the o'clock register, not a word table.
    contact = _contact_with_relative_direction(
        ownship_at_observation=_ownship(),
        relative=RelativeDirection(forward_m=0.0, right_m=1000.0, up_m=0.0),
    )
    state = AttackRunState()

    _state, speech = decide(state, now_sim=0.1, ownship=_ownship(), contact=contact)

    assert speech is not None
    assert speech.text == "Three o'clock."


def test_decide_re_rotates_against_current_heading_not_the_observed_one() -> None:
    """Decision 16's own pinned case: the same `RelativeDirection` against
    two headings 9 degrees apart must yield azimuths 9 degrees apart --
    the carried offset is re-derived against *current* attitude, never
    frozen at the observing poll's own heading."""
    relative = RelativeDirection(forward_m=1000.0, right_m=50.0, up_m=0.0)
    observed_ownship = _ownship(heading_true_deg=0.0)
    contact = _contact_with_relative_direction(
        ownship_at_observation=observed_ownship, relative=relative
    )

    _s1, speech_a = decide(
        AttackRunState(),
        now_sim=0.1,
        ownship=_ownship(heading_true_deg=0.0),
        contact=contact,
    )
    _s2, speech_b = decide(
        AttackRunState(),
        now_sim=0.1,
        ownship=_ownship(heading_true_deg=9.0),
        contact=contact,
    )

    # Recover the azimuth each call actually rendered via `render_
    # alignment`'s own inputs is awkward from text alone (the word table
    # is coarse) -- so pin the underlying angle directly through the
    # private derivation instead of the rendered word.
    alignment_a = _tier1_alignment(_ownship(heading_true_deg=0.0), contact, now_sim=0.1)
    alignment_b = _tier1_alignment(_ownship(heading_true_deg=9.0), contact, now_sim=0.1)
    assert alignment_a is not None and alignment_b is not None
    az_a, _el_a = alignment_a
    az_b, _el_b = alignment_b
    assert abs(az_a - az_b) == pytest.approx(9.0, abs=1e-3)
    # Both renders must still have produced *something* (not silently
    # erroring) -- a loose sanity check on the public surface too.
    assert speech_a is not None
    assert speech_b is not None


def test_decide_oblique_heading_and_banked_ownship_does_not_mix_axes() -> None:
    """The bank-stabilisation claim is a trig no-regression claim and
    axis-aligned angles cannot prove it (plan Stage 3) -- a heavily banked
    *current* ownship attitude must not change the result, since `decide`
    goes through `geometry.alignment_direction`, which never reads bank."""
    relative = RelativeDirection(forward_m=1200.0, right_m=300.0, up_m=-150.0)
    contact = _contact_with_relative_direction(
        ownship_at_observation=_ownship(heading_true_deg=37.0, pitch_deg=-8.0),
        relative=relative,
        t_sim=0.0,
    )

    level = _tier1_alignment(
        _ownship(heading_true_deg=37.0, pitch_deg=-8.0, bank_deg=0.0),
        contact,
        now_sim=0.1,
    )
    banked = _tier1_alignment(
        _ownship(heading_true_deg=37.0, pitch_deg=-8.0, bank_deg=60.0),
        contact,
        now_sim=0.1,
    )

    assert level is not None and banked is not None
    assert level[0] == pytest.approx(banked[0], abs=1e-3)
    assert level[1] == pytest.approx(banked[1], abs=1e-3)


def test_decide_change_driven_cadence_resuppresses_unchanged_errors() -> None:
    """`plans/attack-run-sortie-fixes/plan.md` BL-B70 §1: emit if and only
    if the rendered text differs from the last *spoken* one -- text
    equality is a veto, the angular change-driven clause (`ATTACK_RUN_
    CHANGE_THRESHOLD_DEG`, since removed) is gone entirely."""
    # 20 degrees right -- outside the sector, "two" o'clock-ish register.
    contact = _contact_with_relative_direction(
        ownship_at_observation=_ownship(),
        relative=RelativeDirection(forward_m=1000.0, right_m=20.0, up_m=0.0),
    )
    state = AttackRunState()

    state, speech1 = decide(state, now_sim=0.1, ownship=_ownship(), contact=contact)
    assert speech1 is not None

    # An unchanged look the very next poll must stay silent.
    state, speech2 = decide(state, now_sim=1.1, ownship=_ownship(), contact=contact)
    assert speech2 is None


# -- decide(): tier 2, the degraded fallback, and tier transitions -------


def test_decide_tier_transition_speaks_the_qualifier_without_flipping_direction() -> (
    None
):
    """Both tier transitions speak, and the direction word never flips
    just because the tier changed -- `_should_emit`'s own text-comparison
    re-fires on the qualifier appearing/disappearing (no tier-aware code
    needed, see `_should_emit`'s docstring), while the *sign* of the
    azimuth error is unaffected because tier 2's world-anchored position
    is set to agree with tier 1's relative observation here.

    **`plans/attack-run-sortie-fixes/plan.md` BL-B70 §8: the qualifier is
    cause-keyed, not tier-keyed.** `contact.live_los_clear` is set `False`
    with a fresh `last_seen_sim` (within `ATTACK_TARGET_LOS_MAX_AGE_S`)
    specifically so the tier-2 ticks below have the `"obstructed"` cause
    -- without that, the qualifier would not appear at all (a contact
    with no live LOS verdict is the `"unknown"` cause, fail-open, see
    `test_decide_falls_through_to_tier_2_when_the_contact_has_no_percept`)."""
    relative = RelativeDirection(forward_m=1000.0, right_m=100.0, up_m=0.0)
    contact = _contact_with_relative_direction(
        ownship_at_observation=_ownship(), relative=relative, t_sim=0.0
    )
    # Tier 2's world-anchored belief must agree with tier 1's relative
    # look for this test to isolate the qualifier from genuine geometry
    # drift between the two channels.
    contact.position = PositionEstimate(
        x=1000.0,
        z=100.0,
        covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
        as_of_sim=0.0,
        fused_at_sim=0.0,
        fused_covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
    )
    state = AttackRunState()

    # Tier 1, fresh: azimuth ~5.7 deg right -- "a bit right."
    state, speech1 = decide(state, now_sim=0.1, ownship=_ownship(), contact=contact)
    assert speech1 is not None
    assert speech1.text == "A bit right."
    assert state.last_spoken_tier == 1

    # Tier 1 goes stale -- falls to tier 2. Same geometry, so tier 2's
    # single-row table reads the same ~5.7 deg as "right" (not "a bit
    # right": that word is structurally unreachable in tier 2, see
    # `test_tier2_azimuth_never_speaks_tier_1s_fine_grained_words`), plus
    # a fresh, genuine DCS LOS block -- the `"obstructed"` cause.
    contact.live_los_clear = False
    contact.last_seen_sim = ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.1
    state, speech2 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.1,
        ownship=_ownship(),
        contact=contact,
    )
    assert speech2 is not None
    assert speech2.text == "Right, obstructed."
    assert state.last_spoken_tier == 2

    # Still stale, unchanged geometry, LOS verdict still fresh enough
    # (1.0 s < `ATTACK_TARGET_LOS_MAX_AGE_S`) -- silent (the steady-state
    # repeat suppression tier 1's own "Lined up."-then-silence has).
    state, speech3 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 1.1,
        ownship=_ownship(),
        contact=contact,
    )
    assert speech3 is None

    # Regain sight -- a fresh percept with the identical geometry.
    contact.last_percept = Percept(
        t_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 1.2,
        source="naked_eye_visual_filtered",
        classification_raw="OP_ARMORED",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        observation_id="OBS_2",
        relative_direction=relative,
    )
    state, speech4 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 1.3,
        ownship=_ownship(),
        contact=contact,
    )
    assert speech4 is not None
    assert speech4.text == "A bit right."
    assert state.last_spoken_tier == 1

    # Every utterance agreed on direction -- "right," never "left," across
    # the whole transition.
    for speech in (speech1, speech2, speech4):
        assert "right" in speech.text.lower()
        assert "left" not in speech.text.lower()


def test_decide_lined_up_tier_transition_speaks_once_each_way() -> None:
    """The user's own words (2026-10-14, second direction pass):
    `"lined up, obstructed"` composes exactly like the directional words,
    spoken once on entering it and once on leaving it -- `"lined up"` and
    `"lined up, obstructed"` are each spoken exactly once, never repeated
    while the state holds, mirroring tier 1's own `"Lined up."`-then-
    silence (§4).

    **`contact.live_los_clear = False` + fresh `last_seen_sim`, same
    reasoning as the directional test above** -- BL-B70 §8 makes the
    qualifier cause-keyed, so without a genuine fresh DCS LOS block the
    tier-2 tick below would be the `"unknown"` cause (no qualifier, and
    `"Lined up."` both tiers, which is `test_decide_lined_up_
    tier2_unknown_cause_collapses_the_transition`'s own, deliberately
    different, point)."""
    relative = RelativeDirection(forward_m=1000.0, right_m=0.0, up_m=0.0)
    contact = _contact_with_relative_direction(
        ownship_at_observation=_ownship(), relative=relative, t_sim=0.0
    )
    contact.position = PositionEstimate(
        x=1000.0,
        z=0.0,
        covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
        as_of_sim=0.0,
        fused_at_sim=0.0,
        fused_covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
    )
    state = AttackRunState()

    # Tier 1: lined up, spoken once.
    state, speech1 = decide(state, now_sim=0.1, ownship=_ownship(), contact=contact)
    assert speech1 is not None and speech1.text == "Lined up."

    state, speech2 = decide(state, now_sim=0.2, ownship=_ownship(), contact=contact)
    assert speech2 is None

    # Lose sight -- still lined up, but tier 2 with a fresh, genuine DCS
    # LOS block: spoken once.
    contact.live_los_clear = False
    contact.last_seen_sim = ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.1
    state, speech3 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.1,
        ownship=_ownship(),
        contact=contact,
    )
    assert speech3 is not None and speech3.text == "Lined up, obstructed."

    state, speech4 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 1.1,
        ownship=_ownship(),
        contact=contact,
    )
    assert speech4 is None

    # Regain sight -- still lined up, back to tier 1: spoken once, bare.
    contact.last_percept = Percept(
        t_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 1.2,
        source="naked_eye_visual_filtered",
        classification_raw="OP_ARMORED",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        observation_id="OBS_2",
        relative_direction=relative,
    )
    state, speech5 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 1.3,
        ownship=_ownship(),
        contact=contact,
    )
    assert speech5 is not None and speech5.text == "Lined up."

    state, speech6 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 1.4,
        ownship=_ownship(),
        contact=contact,
    )
    assert speech6 is None


def test_decide_lined_up_tier2_unknown_cause_collapses_the_transition() -> None:
    """The plan's own flagged Risk (`plans/attack-run-sortie-fixes/
    plan.md` BL-B70, "UNKNOWN speaks tier-2 guidance with no qualifier at
    all. Honest... but the pilot cannot distinguish it from a live
    look."), pinned as a structural property rather than left implicit:
    when tier 1 goes stale with **no** live LOS verdict at all (the
    `"unknown"` cause -- the ordinary case for a contact `BL-B71`'s optic
    ladder has not reached for yet), both tiers render the identical bare
    `"Lined up."`, so `_should_emit`'s text-equality veto suppresses the
    tier-1 -> tier-2 transition entirely. This is the accepted
    consequence of making the qualifier cause-keyed (§8) rather than
    tier-keyed -- contrast with `test_decide_lined_up_tier_transition_
    speaks_once_each_way` immediately above, where a genuine fresh
    `"obstructed"` cause *does* re-speak."""
    relative = RelativeDirection(forward_m=1000.0, right_m=0.0, up_m=0.0)
    contact = _contact_with_relative_direction(
        ownship_at_observation=_ownship(), relative=relative, t_sim=0.0
    )
    contact.position = PositionEstimate(
        x=1000.0,
        z=0.0,
        covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
        as_of_sim=0.0,
        fused_at_sim=0.0,
        fused_covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
    )
    state = AttackRunState()

    state, speech1 = decide(state, now_sim=0.1, ownship=_ownship(), contact=contact)
    assert speech1 is not None and speech1.text == "Lined up."
    assert state.last_spoken_tier == 1

    # Tier 1 goes stale, no live LOS verdict ever set -- cause is
    # "unknown", same text, no re-speak, but `last_spoken_tier` silently
    # keeps its old value (`1`) because nothing emitted to update it --
    # the one reachable case `test_last_spoken_tier_cannot_silently_
    # carry_a_wrong_value_across_a_retarget` names as "silently unspoken,"
    # not "silently wrong" (the stale `1` is also the one this function
    # actually computed internally, just never surfaced).
    state, speech2 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.1,
        ownship=_ownship(),
        contact=contact,
    )
    assert speech2 is None
    assert state.last_spoken_tier == 1
    assert state.last_spoken_text == "Lined up."


# -- decide(): the cause taxonomy (§2 masked, §8 obstructed/too_far/unknown) -


def _contact_at(
    *, bearing_deg: float, range_m: float, classification_raw: str = "OP_ARMORED"
) -> Contact:
    """A contact founded with no relative-direction percept at all, so
    `_tier1_alignment` always returns `None` and `decide` is forced to
    tier 2 regardless of `now_sim` -- these cause-taxonomy tests are about
    `_no_look_cause`, not tier selection."""
    return Contact.from_percept(
        "CONTACT_1",
        Percept(
            t_sim=0.0,
            source="naked_eye_visual_filtered",
            classification_raw=classification_raw,
            bearing_deg=bearing_deg,
            range_m=range_m,
            ownship_at_observation=_ownship(),
            observation_id="OBS_1",
            relative_direction=None,
        ),
    )


def _move_contact_to(contact: Contact, *, x: float, z: float, now_sim: float) -> None:
    """Re-points `contact.last_position` (a read-only property over
    `contact.position`) without going through `record()` -- the same
    direct-mutation pattern the pre-existing tier-transition tests above
    already use for `contact.position`."""
    contact.position = PositionEstimate(
        x=x,
        z=z,
        covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
        as_of_sim=now_sim,
        fused_at_sim=now_sim,
        fused_covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
    )


def test_no_look_cause_masked_behind_the_cockpit_mask() -> None:
    """§2: a target dead astern (`rear_cutoff_deg=130`) is `"masked"`
    regardless of range or LOS -- `cockpit_mask.is_visible` short-circuits
    before either of the other two gates is even consulted, matching
    `check_visibility`'s own gate order."""
    contact = _contact_at(bearing_deg=180.0, range_m=1000.0)
    assert _no_look_cause(_ownship(), contact, now_sim=0.0) == "masked"


def test_no_look_cause_obstructed_only_on_a_fresh_false_verdict() -> None:
    """§8/F2: `"obstructed"` fires only on `live_los_clear is False` with
    a verdict fresher than `ATTACK_TARGET_LOS_MAX_AGE_S` -- `None` (no
    verdict) and a stale `False` both fall through to `"unknown"`,
    fail-open."""
    contact = _contact_at(bearing_deg=0.0, range_m=1000.0)
    assert _no_look_cause(_ownship(), contact, now_sim=0.0) == "unknown"

    contact.live_los_clear = False
    contact.last_seen_sim = 0.0
    assert (
        _no_look_cause(_ownship(), contact, now_sim=ATTACK_TARGET_LOS_MAX_AGE_S - 0.1)
        == "obstructed"
    )
    assert (
        _no_look_cause(_ownship(), contact, now_sim=ATTACK_TARGET_LOS_MAX_AGE_S + 0.1)
        == "unknown"
    )

    contact.live_los_clear = True
    assert (
        _no_look_cause(_ownship(), contact, now_sim=ATTACK_TARGET_LOS_MAX_AGE_S - 0.1)
        == "unknown"
    )


def test_no_look_cause_too_far_beyond_naked_eye_presence_range() -> None:
    """§5/§6: beyond the naked eye's own presence threshold for this
    object's profile (`UNAIDED_OPTIC`, `BL-B71`'s ladder out of scope),
    the cause is `"too_far"` -- checked after masking but *before* LOS,
    matching `check_visibility`'s own gate order (range/size is gate 3,
    terrain LOS is gate 4)."""
    near = _contact_at(bearing_deg=0.0, range_m=1000.0)
    assert _no_look_cause(_ownship(), near, now_sim=0.0) == "unknown"

    far = _contact_at(bearing_deg=0.0, range_m=2000.0)
    assert _no_look_cause(_ownship(), far, now_sim=0.0) == "too_far"


def test_no_look_cause_too_far_wins_over_a_fresh_obstructed_verdict() -> None:
    """The reviewer's own mutation proof (`plans/attack-run-sortie-fixes/
    review.md`): a contact that is simultaneously (fresh
    `live_los_clear=False`, beyond the naked eye's presence range) must
    report `"too_far"`, not `"obstructed"` -- `check_visibility` itself
    would have rejected it on range (gate 3) before ever reaching terrain
    LOS (gate 4), so `"obstructed"` would be a misattribution. Before the
    fix this asserted `"obstructed"` and passed; swapping the two checks
    in `_no_look_cause` back to the wrong order makes this fail."""
    far = _contact_at(bearing_deg=0.0, range_m=2000.0)
    far.live_los_clear = False
    far.last_seen_sim = 0.0

    assert (
        _no_look_cause(_ownship(), far, now_sim=ATTACK_TARGET_LOS_MAX_AGE_S - 0.1)
        == "too_far"
    )


def test_decide_masked_tick_is_silent_and_run_stays_engaged() -> None:
    """§2: `speech` is `None`, and the run does not end -- `decide` simply
    returns a state, never a sentinel meaning "stop.\""""
    contact = _contact_at(bearing_deg=180.0, range_m=1000.0)
    state = AttackRunState()

    new_state, speech = decide(state, now_sim=0.0, ownship=_ownship(), contact=contact)

    assert speech is None
    assert new_state.last_spoken_text is None
    assert new_state.last_contact_id == "CONTACT_1"


def test_decide_masked_tick_never_moves_the_cadence_or_unresolved_baseline() -> None:
    """§2's own co-moving-fields rule: a suppressed-for-masking tick must
    not look like a spoken one to the next tick's comparison -- pinned by
    first speaking something, then masking, then confirming both
    `last_spoken_text` and `last_spoken_unresolved` are exactly what they
    were before the masked tick."""
    contact = _contact_at(bearing_deg=0.0, range_m=1000.0)
    state = AttackRunState()
    state, speech1 = decide(state, now_sim=0.0, ownship=_ownship(), contact=contact)
    assert speech1 is not None
    baseline_text = state.last_spoken_text
    baseline_unresolved = state.last_spoken_unresolved

    _move_contact_to(contact, x=-1000.0, z=0.0, now_sim=1.0)  # astern -- masked
    masked_state, speech2 = decide(
        state, now_sim=1.0, ownship=_ownship(), contact=contact
    )
    assert speech2 is None
    assert masked_state.last_spoken_text == baseline_text
    assert masked_state.last_spoken_unresolved == baseline_unresolved


def test_decide_losing_and_regaining_sight_keys_on_resolvability_not_masking() -> None:
    """`docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` §10/§11
    (direction §11, the user's own words: *"losing sight is expected in a
    break after a gun/rocket run... the important question is whether
    Petrovich sees the target when we turn to see what is happening"*):
    a break that masks the target between two `"too_far"` ticks must not
    re-announce the loss, and must not announce "eyes on" just because
    the target came back from behind the mask -- only the resolvable ->
    unresolvable edge (and back) does that, never a masked tick in
    between."""
    contact = _contact_at(bearing_deg=0.0, range_m=2000.0)  # too far
    state = AttackRunState()

    # Losing sight: the full remembered-sighting claim, once.
    state, speech1 = decide(state, now_sim=0.0, ownship=_ownship(), contact=contact)
    assert speech1 is not None
    assert speech1.text.startswith("Lined up armor")
    assert "last seen" in speech1.text
    assert state.last_spoken_unresolved is True

    # A break: the pilot pulls off target, masking it -- not an
    # announcement, and `last_spoken_unresolved` is untouched.
    _move_contact_to(contact, x=-1000.0, z=0.0, now_sim=1.0)
    state, speech2 = decide(state, now_sim=1.0, ownship=_ownship(), contact=contact)
    assert speech2 is None
    assert state.last_spoken_unresolved is True

    # Turning back in, still too far (beyond acquisition range) -- no
    # re-announcement, bare guidance only.
    _move_contact_to(contact, x=2000.0, z=0.0, now_sim=2.0)
    state, speech3 = decide(state, now_sim=2.0, ownship=_ownship(), contact=contact)
    assert speech3 is not None
    assert speech3.text == "Lined up."
    assert "last seen" not in speech3.text
    assert state.last_spoken_unresolved is True

    # Turning back in, now within acquisition range -- "eyes on," once.
    _move_contact_to(contact, x=1000.0, z=0.0, now_sim=3.0)
    state, speech4 = decide(state, now_sim=3.0, ownship=_ownship(), contact=contact)
    assert speech4 is not None
    assert speech4.text == "Eyes on, lined up."
    assert state.last_spoken_unresolved is False


def test_decide_losing_sight_where_suppressed_when_it_restates_the_clock_hour() -> None:
    """Review's required fix 2 (`plans/attack-run-sortie-fixes/review.md`):
    outside the 12 o'clock sector, `phrase` is itself a worded clock-hour
    phrase (`"Three o'clock"`), so the `<where>` clause is suppressed
    rather than restating the same position as a bare digit (the old,
    defective `"Three o'clock armor 3 o'clock, last seen..."`)."""
    contact = _contact_at(bearing_deg=90.0, range_m=2000.0)  # 3 o'clock, too far
    state = AttackRunState()

    state, speech = decide(state, now_sim=0.0, ownship=_ownship(), contact=contact)

    assert speech is not None
    assert speech.text.startswith("Three o'clock armor, last seen")
    assert "3 o'clock" not in speech.text


def test_decide_losing_sight_where_phrase_kept_in_the_qualitative_register() -> None:
    """Inside the 12 o'clock sector, `phrase` is a qualitative word
    (`"lined up"`/`"come left"`) that carries no position at all, so the
    `<where>` clause still earns its place there -- `"ahead"` -- unlike
    the clock-hour case above, where it would be a pure repeat."""
    contact = _contact_at(bearing_deg=0.0, range_m=2000.0)  # 12 o'clock, too far
    state = AttackRunState()

    state, speech = decide(state, now_sim=0.0, ownship=_ownship(), contact=contact)

    assert speech is not None
    assert speech.text.startswith("Lined up armor ahead, last seen")


def test_decide_retarget_resets_last_spoken_unresolved() -> None:
    """§10's own co-moving-fields rule: a new target's first callout must
    never open with `"Eyes on, ..."` or inherit a last-seen clause from
    the previous target -- the re-point reset (security-fix review
    finding 5) already resets the whole state to fresh, and `last_spoken_
    unresolved` must be one of the fields that resets with it."""
    contact_a = _contact_at(bearing_deg=0.0, range_m=2000.0)  # too far
    state = AttackRunState()
    state, speech_a = decide(state, now_sim=0.0, ownship=_ownship(), contact=contact_a)
    assert speech_a is not None
    assert state.last_spoken_unresolved is True

    contact_b = _contact_at(bearing_deg=0.0, range_m=1000.0)  # within range
    contact_b.id = "CONTACT_2"
    new_state, speech_b = decide(
        state, now_sim=0.1, ownship=_ownship(), contact=contact_b
    )

    assert speech_b is not None
    assert "eyes on" not in speech_b.text.lower()
    assert "last seen" not in speech_b.text.lower()
    assert new_state.last_spoken_unresolved is False


# -- decide(): §4 the twelve o'clock marker ------------------------------


def test_decide_announces_twelve_oclock_entering_from_the_oclock_register() -> None:
    """§4: on the sector-entry transition the announcement prefixes the
    same utterance -- `"Twelve o'clock, come left."` -- rather than a
    second one, and it fires on *any* entry into the sector from the
    o'clock register, not only a literal 1->12/11->12 step (direction,
    resolved decision 1: a hard turn can skip the adjacent sector)."""
    contact = _contact_at(bearing_deg=40.0, range_m=1000.0)  # outside the sector
    state = AttackRunState()
    state, speech1 = decide(state, now_sim=0.0, ownship=_ownship(), contact=contact)
    assert speech1 is not None
    assert "o'clock" in speech1.text.lower()
    assert state.last_spoken_clock_hour is not None

    # Jump straight into the qualitative register -- still counts as
    # "entering the sector," even though it skipped the adjacent hour.
    # `_contact_at` forces tier 2 (no relative-direction percept), whose
    # one-row `TIER2_AZIMUTH_WORD_TABLE` has no "a bit"/"come" split --
    # bare "right" is the whole word at this gate.
    _move_contact_to(contact, x=1000.0, z=100.0, now_sim=0.1)  # ~5.7 deg right
    state, speech2 = decide(state, now_sim=0.1, ownship=_ownship(), contact=contact)
    assert speech2 is not None
    assert speech2.text == "Twelve o'clock, right."
    assert state.last_spoken_clock_hour is None


def test_decide_does_not_re_announce_twelve_oclock_while_steady_in_the_sector() -> None:
    """The marker is a transition, not a standing qualifier -- a second
    tick still inside the sector must not prefix again."""
    contact = _contact_at(bearing_deg=40.0, range_m=1000.0)  # outside the sector
    state = AttackRunState()
    state, speech1 = decide(state, now_sim=0.0, ownship=_ownship(), contact=contact)
    assert speech1 is not None
    assert "o'clock" in speech1.text.lower()
    assert state.last_spoken_clock_hour is not None

    _move_contact_to(contact, x=1000.0, z=100.0, now_sim=0.1)  # ~5.7 deg right
    state, speech2 = decide(state, now_sim=0.1, ownship=_ownship(), contact=contact)
    assert speech2 is not None
    assert speech2.text == "Twelve o'clock, right."
    assert state.last_spoken_clock_hour is None

    _move_contact_to(contact, x=1000.0, z=200.0, now_sim=0.2)  # still inside, ~11 deg
    state, speech3 = decide(state, now_sim=0.2, ownship=_ownship(), contact=contact)
    assert speech3 is not None
    assert speech3.text == "Right."


def test_tier2_projects_a_moving_target_forward_but_holds_a_stopped_one() -> None:
    """Decision 10/Stage 7: projection is a tier-2-only concern, gated on
    `contact.motion.state == "moving"`, direction from `Group.heading_deg`.
    `contact.motion is None` ("never observed for movement") must be
    treated exactly like `"stopped"` -- held, never projected, never
    treated as moving by omission."""
    ownship = _ownship()

    def _contact_with_motion(motion_state: MotionState | None) -> Contact:
        contact = Contact.from_percept(
            "CONTACT_1",
            Percept(
                t_sim=0.0,
                source="naked_eye_visual_filtered",
                classification_raw="OP_ARMORED",
                bearing_deg=0.0,
                range_m=1000.0,
                ownship_at_observation=ownship,
                observation_id="OBS_1",
                relative_direction=None,
            ),
        )
        if motion_state is not None:
            contact.motion = MotionBelief(
                state=motion_state, confidence=0.9, established_sim=0.0
            )
        return contact

    group = _group(movement_state="moving", heading_deg=90.0)

    az_moving, _el_moving = _tier2_alignment(
        ownship, _contact_with_motion("moving"), 10.0, None, group
    )
    az_stopped, _el_stopped = _tier2_alignment(
        ownship, _contact_with_motion("stopped"), 10.0, None, group
    )
    az_none, _el_none = _tier2_alignment(
        ownship, _contact_with_motion(None), 10.0, None, group
    )

    assert az_stopped == pytest.approx(0.0, abs=1e-6)
    # `motion is None` is held exactly like "stopped" -- never projected.
    assert az_none == pytest.approx(az_stopped, abs=1e-9)
    # A moving target with a usable group heading is projected forward,
    # away from the stationary case.
    assert az_moving != pytest.approx(az_stopped, abs=1e-3)


def test_tier2_azimuth_never_speaks_tier_1s_fine_grained_words() -> None:
    """Decision 17 REVISED: `TIER2_AZIMUTH_WORD_TABLE` has one row, at the
    same gate tier 1's own last row uses, with bare direction words --
    `"come right"`/`"a bit right"` are structurally unreachable through
    it, not merely withheld by a rule."""
    for threshold_deg, positive, negative in TIER2_AZIMUTH_WORD_TABLE:
        assert threshold_deg == ATTACK_RUN_LINED_UP_AZIMUTH_DEG
        assert positive == "right"
        assert negative == "left"
    assert len(TIER2_AZIMUTH_WORD_TABLE) == 1

    # An error that would be "a bit right" in tier 1's table renders as
    # the bare word in tier 2.
    speech = render_alignment(
        6.0,
        0.0,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
        qualifier=", obstructed",
    )
    assert speech.text == "Right, obstructed."
    assert "come" not in speech.text.lower()
    assert "a bit" not in speech.text.lower()


# -- decide(): mid-run reselection resets the per-contact state --------
#
# BL-14 security-fix review, finding 5 (`plans/attack-run/review.md`): the
# security fix made mid-run reselection a sanctioned re-point (confirmed
# standing, user direction 2026-10-14) rather than a refusal, which means
# `decide` can be called with a state carried forward from the *previous*
# target. Every field on `AttackRunState` describes that previous target's
# last look -- these tests call `decide` directly, not through `drain_
# attack_run`, per the review's own note that the wrapper's occupancy gate
# can mask the exact tick a staleness bug would show.


def test_decide_does_not_derive_the_new_targets_elevation_from_the_old_targets_altitude() -> (
    None
):
    """The reviewer's own reproduction: engage contact A (tier 1 succeeds,
    remembered altitude = ownship alt + 500 m), re-point to contact B mid-
    run with no fresh relative observation for B at all. Before the fix,
    tier 2's elevation axis read B's altitude off A's remembered value and
    spoke a confidently wrong "Higher."/"A little lower." for a target
    whose own altitude has never been observed. After the fix, the contact
    id change resets `last_known_target_alt_m` to `None`, so B's elevation
    axis fails open (no elevation word) exactly as it would for a target
    that has never had a tier-1 look at all."""
    ownship = _ownship(alt_m=500.0)
    contact_a = _contact_with_relative_direction(
        ownship_at_observation=_ownship(alt_m=500.0),
        relative=RelativeDirection(forward_m=1000.0, right_m=0.0, up_m=500.0),
        t_sim=0.0,
    )
    state, speech_a = decide(
        AttackRunState(), now_sim=0.1, ownship=ownship, contact=contact_a
    )
    assert speech_a is not None
    # Tier 1 succeeded and remembered A's altitude as 500 + 500 = 1000.
    assert state.last_known_target_alt_m == pytest.approx(1000.0)
    assert state.last_contact_id == "CONTACT_1"

    contact_b = Contact.from_percept(
        "CONTACT_2",
        Percept(
            t_sim=0.1,
            source="naked_eye_visual_filtered",
            classification_raw="OP_ARMORED",
            bearing_deg=0.0,
            range_m=1000.0,
            ownship_at_observation=ownship,
            observation_id="OBS_2",
            relative_direction=None,
        ),
    )

    new_state, speech_b = decide(state, now_sim=0.2, ownship=ownship, contact=contact_b)

    assert new_state.last_contact_id == "CONTACT_2"
    # The bug: without the reset this would stay 1000.0, carried over from
    # A, and tier 2 would compute B's elevation from it.
    assert new_state.last_known_target_alt_m is None
    assert speech_b is not None
    assert "higher" not in speech_b.text.lower()
    assert "lower" not in speech_b.text.lower()


def test_decide_speaks_the_first_callout_about_a_retargeted_contact_even_if_the_old_cadence_baseline_matches() -> (
    None
):
    """The cadence-baseline half of the same finding: if `last_spoken_*`
    carried over from the old target, a new target whose geometry happens
    to render the same text/axes as the old target's last-spoken values
    would be wrongly suppressed as "unchanged" -- silent about a target
    the pilot just deliberately selected, which is exactly backwards (the
    first callout about a newly re-pointed target must speak)."""
    ownship = _ownship()
    relative = RelativeDirection(forward_m=1000.0, right_m=0.0, up_m=0.0)
    contact_a = _contact_with_relative_direction(
        ownship_at_observation=ownship, relative=relative, t_sim=0.0
    )
    state, speech_a = decide(
        AttackRunState(), now_sim=0.1, ownship=ownship, contact=contact_a
    )
    assert speech_a is not None
    assert speech_a.text == "Lined up."

    # Contact B: identical geometry to A's last-spoken state, so a carried-
    # over baseline would read "nothing has changed" and stay silent.
    contact_b = Contact.from_percept(
        "CONTACT_2",
        Percept(
            t_sim=0.1,
            source="naked_eye_visual_filtered",
            classification_raw="OP_ARMORED",
            bearing_deg=0.0,
            range_m=1000.0,
            ownship_at_observation=ownship,
            observation_id="OBS_2",
            relative_direction=relative,
        ),
    )

    new_state, speech_b = decide(state, now_sim=0.2, ownship=ownship, contact=contact_b)

    assert speech_b is not None
    assert speech_b.text == "Lined up."
    assert new_state.last_contact_id == "CONTACT_2"
    # The tier half of the same finding: the spoken utterance must carry
    # *this* tick's own tier (1, contact B's fresh look), never a tier
    # left over from A -- same call, same assertion point, since a wrong
    # carried-over tier and a wrongly-suppressed callout are the same
    # underlying defect here (see the next test for why they cannot be
    # separated further).
    assert new_state.last_spoken_tier == 1


# The pre-BL-B70 version of this module had a mechanical test here
# (`test_last_spoken_tier_cannot_silently_carry_a_wrong_value_across_a_
# retarget`) asserting that a tier-1 render and a tier-2 render of the
# same angle can never collide as strings -- true when `render_alignment`
# unconditionally appended tier 2's `", obstructed"` qualifier. BL-B70 §8
# makes the qualifier cause-keyed instead, so the two registers *can* now
# collide (the `"unknown"`-cause, no-qualifier case) -- the property is
# gone, not merely re-pinned, and `test_decide_lined_up_tier2_unknown_
# cause_collapses_the_transition` above documents the replacement fact:
# `last_spoken_tier` can go stale in that case, harmlessly, because
# nothing emits when it does.


# -- render_alignment: the register switch and the two-gate evaluation ---


def test_render_alignment_outside_sector_speaks_o_clock() -> None:
    speech = render_alignment(
        90.0,
        0.0,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Three o'clock."


def test_render_alignment_large_azimuth_error_says_come() -> None:
    speech = render_alignment(
        10.0,
        0.0,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Come right."


def test_render_alignment_small_azimuth_error_says_a_bit() -> None:
    speech = render_alignment(
        6.0,
        0.0,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "A bit right."


def test_render_alignment_left_is_the_negative_phrase() -> None:
    speech = render_alignment(
        -10.0,
        0.0,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Come left."


def test_render_alignment_elevation_combines_with_azimuth_when_both_fire() -> None:
    speech = render_alignment(
        10.0,
        15.0,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Come right, higher."


def test_render_alignment_elevation_only_fires_without_azimuth_word() -> None:
    # Inside the azimuth band but outside the elevation gate -- the
    # conjunction (Decision 9) means this is not yet "lined up".
    speech = render_alignment(
        0.0,
        -15.0,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "A little lower."


def test_render_alignment_both_gates_satisfied_is_lined_up() -> None:
    speech = render_alignment(
        1.0,
        1.0,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Lined up."


def test_render_alignment_qualifier_appends_outside_the_sector() -> None:
    """`plans/attack-run-sortie-fixes/plan.md` BL-B70 §8: `qualifier` is
    caller-supplied, not tier-driven -- `render_alignment` itself no
    longer knows about tiers at all."""
    speech = render_alignment(
        90.0,
        0.0,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
        qualifier=", obstructed",
    )
    assert speech.text == "Three o'clock, obstructed."


def test_render_alignment_qualifier_appends_to_the_direction_word() -> None:
    speech = render_alignment(
        10.0,
        0.0,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
        qualifier=", obstructed",
    )
    assert speech.text == "Right, obstructed."

    speech_left = render_alignment(
        -10.0,
        0.0,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
        qualifier=", obstructed",
    )
    assert speech_left.text == "Left, obstructed."


def test_render_alignment_tier_2_elevation_word_is_unchanged_from_tier_1() -> None:
    """`"higher"`/`"a little lower"` either way -- `ELEVATION_WORD_TABLE`
    is shared, not re-declared for tier 2 (its one row carries no
    large/small split in either tier)."""
    speech = render_alignment(
        0.0,
        -15.0,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
        qualifier=", obstructed",
    )
    assert speech.text == "A little lower, obstructed."


def test_render_alignment_qualifier_combines_with_both_axes() -> None:
    speech = render_alignment(
        10.0,
        15.0,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
        qualifier=", obstructed",
    )
    assert speech.text == "Right, higher, obstructed."


def test_render_alignment_lined_up_speaks_the_qualifier_too() -> None:
    """The user's own words (2026-10-14, second direction pass):
    `"lined up, obstructed"` composes exactly like the directional words
    -- no silence, no alternative phrasing."""
    speech = render_alignment(
        1.0,
        1.0,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
        qualifier=", obstructed",
    )
    assert speech.text == "Lined up, obstructed."


def test_render_alignment_announce_twelve_prefixes_without_capitalizing_the_rest() -> (
    None
):
    """`plans/attack-run-sortie-fixes/plan.md` BL-B70 §4: `"Twelve
    o'clock, come left."`, not two sentences, and the guidance clause
    stays lowercase after the prefix's own comma."""
    speech = render_alignment(
        -10.0,
        0.0,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
        announce_twelve=True,
    )
    assert speech.text == "Twelve o'clock, come left."


def test_both_axes_share_one_table_lookup_helper() -> None:
    """Decision 11 REVISED, rule 3's own test: nothing in the renderer may
    branch on "the vertical axis is coarse" -- both axes must go through
    the same helper. Checked by constructing a one-row elevation table
    with the same shape as the azimuth table and confirming it is read
    the same way (a smaller threshold fires a different phrase, exactly
    like azimuth's second row does)."""
    finer_elevation_table = (
        (ATTACK_RUN_ELEVATION_GATE_DEG, "higher", "a little lower"),
        (2.0, "a touch higher", "a touch lower"),
    )
    speech = render_alignment(
        0.0,
        3.0,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=finer_elevation_table,
    )
    assert speech.text == "A touch higher."


# -- constants, stated as assumptions, not tuned here --------------------


def test_the_two_constants_are_unchanged_assumptions() -> None:
    """`ATTACK_RUN_CHANGE_THRESHOLD_DEG` is removed entirely by BL-B70 §1
    (F1: no threshold could fix a comparison finer-grained than the
    vocabulary it guards) -- the other two assumptions stand."""
    assert ATTACK_RUN_LINED_UP_AZIMUTH_DEG == 5.0
    assert ATTACK_RUN_ELEVATION_GATE_DEG == 10.0


# -- `BL-B71`: `AttackRunState.requested_optic` --------------------------

# Presence thresholds for "OP_ARMORED" (`_contact_at`'s own default
# classification), from the same `tier_ranges` formula the module itself
# uses: UNAIDED ~1667 m, BINOCULAR ~4033 m.
_ARMORED_UNAIDED_M = 1666.6666666666667
_ARMORED_BINOCULAR_M = 4033.3333333333335


class TestRequestedOptic:
    def test_starts_none_before_the_first_tick(self) -> None:
        assert AttackRunState().requested_optic is None

    def test_within_naked_eye_range_requests_the_naked_eye(self) -> None:
        contact = _contact_at(bearing_deg=0.0, range_m=1000.0)
        state, _speech = decide(
            AttackRunState(), now_sim=0.0, ownship=_ownship(), contact=contact
        )
        assert state.requested_optic is UNAIDED_OPTIC

    def test_beyond_naked_eye_requests_binoculars(self) -> None:
        contact = _contact_at(bearing_deg=0.0, range_m=_ARMORED_UNAIDED_M + 1.0)
        state, _speech = decide(
            AttackRunState(), now_sim=0.0, ownship=_ownship(), contact=contact
        )
        assert state.requested_optic is BINOCULAR_OPTIC

    def test_a_masked_tick_freezes_the_request_guard_1(self) -> None:
        """§7 guard 1: `requested_optic` must not re-evaluate while
        `cause == "masked"`, even though the range changed underneath it
        -- this is what "falls out of §2" means (`AttackRunState.
        requested_optic`'s own docstring): the field is only ever updated
        after the `cause == "masked"` early return, so a masked tick
        leaves it exactly as it was."""
        near = _contact_at(bearing_deg=0.0, range_m=1000.0)
        state, _speech = decide(
            AttackRunState(), now_sim=0.0, ownship=_ownship(), contact=near
        )
        assert state.requested_optic is UNAIDED_OPTIC

        # Move the same contact astern (masked) *and* far beyond the
        # naked eye's own range -- if the field re-evaluated here it
        # would jump to `BINOCULAR_OPTIC`.
        far_and_astern = _contact_at(
            bearing_deg=180.0, range_m=_ARMORED_UNAIDED_M + 1.0
        )
        masked_state, speech = decide(
            state, now_sim=1.0, ownship=_ownship(), contact=far_and_astern
        )
        assert speech is None  # confirms this tick really was masked
        assert masked_state.requested_optic is UNAIDED_OPTIC

    def test_de_escalation_is_withheld_until_the_margin_is_crossed(self) -> None:
        """Guard 2, exercised through the full `decide()` path rather
        than `guidance_request_for` directly -- a target still just
        inside `BINOCULAR_OPTIC`'s own threshold does not yet give up the
        request; one comfortably inside it does."""
        far = _contact_at(bearing_deg=0.0, range_m=_ARMORED_UNAIDED_M + 1.0)
        state, _speech = decide(
            AttackRunState(), now_sim=0.0, ownship=_ownship(), contact=far
        )
        assert state.requested_optic is BINOCULAR_OPTIC

        just_inside = _contact_at(bearing_deg=0.0, range_m=_ARMORED_UNAIDED_M - 1.0)
        held_state, _speech = decide(
            state, now_sim=1.0, ownship=_ownship(), contact=just_inside
        )
        assert held_state.requested_optic is BINOCULAR_OPTIC

        comfortably_inside = _contact_at(
            bearing_deg=0.0, range_m=_ARMORED_UNAIDED_M * 0.5
        )
        de_escalated_state, _speech = decide(
            held_state, now_sim=2.0, ownship=_ownship(), contact=comfortably_inside
        )
        assert de_escalated_state.requested_optic is UNAIDED_OPTIC

    def test_a_re_point_resets_the_request(self) -> None:
        """The reset-on-re-point path (`decide`'s own docstring) must
        clear `requested_optic` too -- a new target starts its own ladder
        evaluation from the floor, never inheriting the old target's
        standing request."""
        far = _contact_at(bearing_deg=0.0, range_m=_ARMORED_UNAIDED_M + 1.0)
        state, _speech = decide(
            AttackRunState(), now_sim=0.0, ownship=_ownship(), contact=far
        )
        assert state.requested_optic is BINOCULAR_OPTIC

        other_contact = Contact.from_percept(
            "CONTACT_2",
            Percept(
                t_sim=1.0,
                source="naked_eye_visual_filtered",
                classification_raw="OP_ARMORED",
                bearing_deg=0.0,
                range_m=1000.0,
                ownship_at_observation=_ownship(),
                observation_id="OBS_2",
                relative_direction=None,
            ),
        )
        new_state, _speech = decide(
            state, now_sim=1.0, ownship=_ownship(), contact=other_contact
        )
        assert new_state.last_contact_id == "CONTACT_2"
        assert new_state.requested_optic is UNAIDED_OPTIC


# -- `BL-B71` review's required fix: `_no_look_cause` must test range   -
# -- against the optic that actually resolved the look, not a fixed    -
# -- `UNAIDED_OPTIC` --------------------------------------------------- -


def test_no_look_cause_optic_param_lowers_the_too_far_threshold() -> None:
    """Direct unit proof that `optic` moves the range gate: a contact
    just beyond the naked eye's own presence threshold is `"too_far"`
    against the default (`UNAIDED_OPTIC`), but `"unknown"` (resolvable,
    no live LOS verdict either way) against a granted `BINOCULAR_OPTIC`
    -- the two thresholds `_ARMORED_UNAIDED_M`/`_ARMORED_BINOCULAR_M`
    above, exercised through the parameter itself rather than through
    `decide`."""
    contact = _contact_at(bearing_deg=0.0, range_m=_ARMORED_UNAIDED_M + 1.0)
    assert _no_look_cause(_ownship(), contact, now_sim=0.0) == "too_far"
    assert (
        _no_look_cause(_ownship(), contact, now_sim=0.0, optic=BINOCULAR_OPTIC)
        == "unknown"
    )


def test_decide_with_granted_binoculars_resolves_tier_1_instead_of_losing_sight() -> (
    None
):
    """The review's required fix, exercised through the full `decide()`
    path with a contact `_contact_at` cannot build (it is deliberately
    tier-2-only): a **fresh tier-1 percept** -- `relative_direction` set,
    so `_tier1_alignment` resolves -- at a range beyond the naked eye's
    own presence threshold but within the granted binoculars'. This is
    the steady-state case `BL-B71`'s optic ladder exists to cover: once
    the ladder grants binoculars, a live look through them must speak
    the ordinary alignment, not misattribute `"too_far"` (tested against
    the wrong, narrower optic) and announce "last I saw ..." about a
    target Petrovich is actively tracking.

    Confirmed to fail for the stated reason before the fix (manual
    counterfactual, not asserted here): reverting `_no_look_cause`'s
    `optic` parameter to a hardcoded `UNAIDED_OPTIC` makes this test fail
    with `speech.text` carrying the `render_attack_run_lost_sight`
    "last I saw ..." phrasing instead of "Lined up.", because `cause`
    reads `"too_far"` against the naked eye's own (narrower) threshold
    even though tier 1 has a fresh, live look."""
    range_m_value = _ARMORED_UNAIDED_M + 1.0  # beyond naked eye, inside binoculars
    assert range_m_value < _ARMORED_BINOCULAR_M
    contact = Contact.from_percept(
        "CONTACT_1",
        Percept(
            t_sim=0.0,
            source="naked_eye_visual_filtered",
            classification_raw="OP_ARMORED",
            bearing_deg=0.0,
            range_m=range_m_value,
            ownship_at_observation=_ownship(),
            observation_id="OBS_1",
            relative_direction=RelativeDirection(
                forward_m=range_m_value, right_m=0.0, up_m=0.0
            ),
        ),
    )
    state = AttackRunState()

    new_state, speech = decide(
        state,
        now_sim=0.1,
        ownship=_ownship(),
        contact=contact,
        resolving_optic=BINOCULAR_OPTIC,
    )

    assert speech is not None
    assert speech.text == "Lined up."
    assert new_state.last_spoken_tier == 1
    # The edge this fix exists for: a resolvable tier-1 look must not be
    # recorded as "unresolved," which would wrongly prime the next tick
    # for a "regained sight" announcement that never lost anything.
    assert new_state.last_spoken_unresolved is False
