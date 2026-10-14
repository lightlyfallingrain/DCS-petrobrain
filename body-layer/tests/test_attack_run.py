"""Tests for `belief.attack_run` -- `plans/attack-run/plan.md` Stages 3/6/7's
pure alignment derivation (tier 1, the live look; tier 2, the degraded
fallback with Decision 10's projection) plus `belief.speech.
render_alignment`'s word-table rendering, and the grep fence that keeps
`Percept.relative_direction` to its two sanctioned readers."""

from __future__ import annotations

import inspect
import pathlib
import re

import pytest

from belief import attack_run as attack_run_module
from belief import percept as percept_module
from belief.attack_run import (
    ATTACK_RUN_CHANGE_THRESHOLD_DEG,
    ATTACK_RUN_ELEVATION_GATE_DEG,
    ATTACK_RUN_LINED_UP_AZIMUTH_DEG,
    ATTACK_RUN_RELATIVE_MAX_AGE_S,
    AZIMUTH_WORD_TABLE,
    ELEVATION_WORD_TABLE,
    TIER2_AZIMUTH_WORD_TABLE,
    AttackRunState,
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
    "lined up" and the elevation axis never fires at all."""
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
    assert speech.text == "Lined up, obstructed."
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
    """Decision 7: emit when the rendered text differs from the last
    *spoken* one, or either axis has moved by more than `ATTACK_RUN_
    CHANGE_THRESHOLD_DEG` since that same last-spoken baseline -- not the
    previous sample."""
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
    is set to agree with tier 1's relative observation here."""
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
    # the qualifier.
    state, speech2 = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.1,
        ownship=_ownship(),
        contact=contact,
    )
    assert speech2 is not None
    assert speech2.text == "Right, obstructed."
    assert state.last_spoken_tier == 2

    # Still stale, unchanged geometry -- silent (the steady-state repeat
    # suppression tier 1's own "Lined up."-then-silence has).
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
    silence (§4)."""
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

    # Lose sight -- still lined up, but tier 2: spoken once.
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
        tier=2,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Right, obstructed."
    assert "come" not in speech.text.lower()
    assert "a bit" not in speech.text.lower()


# -- render_alignment: the register switch and the two-gate evaluation ---


def test_render_alignment_outside_sector_speaks_o_clock() -> None:
    speech = render_alignment(
        90.0,
        0.0,
        tier=1,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Three o'clock."


def test_render_alignment_large_azimuth_error_says_come() -> None:
    speech = render_alignment(
        10.0,
        0.0,
        tier=1,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Come right."


def test_render_alignment_small_azimuth_error_says_a_bit() -> None:
    speech = render_alignment(
        6.0,
        0.0,
        tier=1,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "A bit right."


def test_render_alignment_left_is_the_negative_phrase() -> None:
    speech = render_alignment(
        -10.0,
        0.0,
        tier=1,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Come left."


def test_render_alignment_elevation_combines_with_azimuth_when_both_fire() -> None:
    speech = render_alignment(
        10.0,
        15.0,
        tier=1,
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
        tier=1,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "A little lower."


def test_render_alignment_both_gates_satisfied_is_lined_up() -> None:
    speech = render_alignment(
        1.0,
        1.0,
        tier=1,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Lined up."


def test_render_alignment_tier_2_appends_the_qualifier_outside_the_sector() -> None:
    speech = render_alignment(
        90.0,
        0.0,
        tier=2,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Three o'clock, obstructed."


def test_render_alignment_tier_2_appends_the_qualifier_to_the_direction_word() -> None:
    speech = render_alignment(
        10.0,
        0.0,
        tier=2,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Right, obstructed."

    speech_left = render_alignment(
        -10.0,
        0.0,
        tier=2,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech_left.text == "Left, obstructed."


def test_render_alignment_tier_2_elevation_word_is_unchanged_from_tier_1() -> None:
    """`"higher"`/`"a little lower"` either way -- `ELEVATION_WORD_TABLE`
    is shared, not re-declared for tier 2 (its one row carries no
    large/small split in either tier)."""
    speech = render_alignment(
        0.0,
        -15.0,
        tier=2,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "A little lower, obstructed."


def test_render_alignment_tier_2_combines_both_axes_then_the_qualifier() -> None:
    speech = render_alignment(
        10.0,
        15.0,
        tier=2,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Right, higher, obstructed."


def test_render_alignment_tier_2_lined_up_speaks_the_qualifier_too() -> None:
    """The user's own words (2026-10-14, second direction pass):
    `"lined up, obstructed"` composes exactly like the directional words
    -- no silence, no alternative phrasing."""
    speech = render_alignment(
        1.0,
        1.0,
        tier=2,
        azimuth_table=TIER2_AZIMUTH_WORD_TABLE,
        elevation_table=ELEVATION_WORD_TABLE,
    )
    assert speech.text == "Lined up, obstructed."


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
        tier=1,
        azimuth_table=AZIMUTH_WORD_TABLE,
        elevation_table=finer_elevation_table,
    )
    assert speech.text == "A touch higher."


# -- constants, stated as assumptions, not tuned here --------------------


def test_the_three_constants_are_unchanged_assumptions() -> None:
    assert ATTACK_RUN_LINED_UP_AZIMUTH_DEG == 5.0
    assert ATTACK_RUN_ELEVATION_GATE_DEG == 10.0
    assert ATTACK_RUN_CHANGE_THRESHOLD_DEG == 3.0
