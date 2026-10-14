"""Tests for `belief.attack_run` -- `plans/attack-run/plan.md` Stage 3's
pure alignment derivation (tier 1 only; tier 2 is Stage 6, not built here)
plus `belief.speech.render_alignment`'s word-table rendering, and the
grep fence that keeps `Percept.relative_direction` to its two sanctioned
readers."""

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
    AttackRunState,
    _tier1_alignment,
    decide,
)
from belief.contacts import Contact
from belief.percept import Percept
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


def test_decide_is_silent_when_the_contact_has_no_percept() -> None:
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

    assert speech is None
    assert new_state == state


def test_decide_is_silent_once_the_relative_observation_goes_stale() -> None:
    contact = _contact_with_relative_direction(
        ownship_at_observation=_ownship(t_sim=0.0),
        relative=RelativeDirection(forward_m=1000.0, right_m=0.0, up_m=0.0),
        t_sim=0.0,
    )
    state = AttackRunState()

    _state, speech = decide(
        state,
        now_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.01,
        ownship=_ownship(t_sim=ATTACK_RUN_RELATIVE_MAX_AGE_S + 0.01),
        contact=contact,
    )

    assert speech is None


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


def test_render_alignment_tier_2_is_not_built_yet() -> None:
    with pytest.raises(NotImplementedError):
        render_alignment(
            0.0,
            0.0,
            tier=2,
            azimuth_table=AZIMUTH_WORD_TABLE,
            elevation_table=ELEVATION_WORD_TABLE,
        )


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
