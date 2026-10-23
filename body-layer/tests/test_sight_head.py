"""Tests for `belief.sight_head` -- `[[BL-B80]]`'s simulated 9K113 sight
head (`plans/9k113-sight-pointing/plan.md`, re-plan v2, Stages 3/3b).

Covers the mode transitions (`off`/`caged`/`free`), world-direction hold
through a turn, per-axis rate limits, gimbal clamping, the "Aim source"
selection rule (`select_sight_goal`), and the grep fences F2/F3."""

from __future__ import annotations

import inspect
import pathlib
import re

import pytest

from belief import sight_head as sight_head_module
from belief.attack_run import seen_world_direction
from belief.contacts import Contact
from belief.percept import Percept
from belief.sight_head import (
    SEEN_AIM_HOLD_S,
    SLEW_AZ_DPS,
    SightHead,
    advance_sight_head,
    select_sight_goal,
)
from perception.source import OwnshipState, RelativeDirection

_SEEN_WORLD_DIRECTION_PATTERN = re.compile(r"\bseen_world_direction\b")
_SIGHT_HEAD_IMPORT_PATTERN = re.compile(r"\bsight_head\b")
_SIGHT_HEAD_TYPE_PATTERN = re.compile(r"\bSightHead\b")


def _ownship(
    *,
    t_sim: float = 0.0,
    heading_true_deg: float = 0.0,
    pitch_deg: float = 0.0,
    bank_deg: float = 0.0,
) -> OwnshipState:
    return OwnshipState(
        t_sim=t_sim,
        x=0.0,
        z=0.0,
        alt_m=500.0,
        heading_true_deg=heading_true_deg,
        pitch_deg=pitch_deg,
        bank_deg=bank_deg,
    )


def _contact_seen(
    *,
    contact_id: str = "CONTACT_1",
    forward_m: float = 1000.0,
    right_m: float = 0.0,
    up_m: float = 0.0,
    t_sim: float = 0.0,
    ownship_heading_deg: float = 0.0,
) -> Contact:
    percept = Percept(
        t_sim=t_sim,
        source="naked_eye_visual_filtered",
        classification_raw="OP_ARMORED",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(
            t_sim=t_sim, heading_true_deg=ownship_heading_deg
        ),
        observation_id="OBS_1",
        relative_direction=RelativeDirection(
            forward_m=forward_m, right_m=right_m, up_m=up_m
        ),
    )
    return Contact.from_percept(contact_id, percept)


# -- fences F2/F3 ----------------------------------------------------------


def test_fence_f2_seen_world_direction_only_in_attack_run_and_sight_head() -> None:
    """`seen_world_direction` appears in `src/` only in `belief/attack_
    run.py` (its definition) and `belief/sight_head.py` (its one caller)."""
    src_dir = pathlib.Path(inspect.getfile(sight_head_module)).parent.parent
    assert src_dir.name == "src"

    checked_any = False
    for path in src_dir.rglob("*.py"):
        if path.name in ("attack_run.py", "sight_head.py"):
            continue
        checked_any = True
        text = path.read_text()
        assert not _SEEN_WORLD_DIRECTION_PATTERN.search(text), (
            f"{path} references seen_world_direction"
        )
    assert checked_any
    assert _SEEN_WORLD_DIRECTION_PATTERN.search(inspect.getsource(sight_head_module))


def test_fence_f3_sight_head_imported_only_by_logger_and_trace_writer() -> None:
    """`sight_head` is imported in `src/` only by `logger.py` and `sight_
    trace_writer.py`; nothing under `belief/`/`mission_memory/` imports it
    (other than `sight_head.py` itself, which does not import its own
    module by that name), and `belief.tools`/`tool_api`/`crew_console`/
    `speech` never mention `SightHead`."""
    src_dir = pathlib.Path(inspect.getfile(sight_head_module)).parent.parent

    allowed_importers = {"logger.py", "sight_trace_writer.py"}
    checked_any = False
    for path in src_dir.rglob("*.py"):
        if path.name == "sight_head.py":
            continue
        checked_any = True
        text = path.read_text()
        if "import sight_head" in text or "from belief import sight_head" in text:
            assert path.name in allowed_importers, (
                f"{path} imports sight_head but is not in {allowed_importers}"
            )
    assert checked_any

    for forbidden_name in ("tools.py", "tool_api.py", "crew_console.py", "speech.py"):
        for path in (src_dir / "belief").glob(forbidden_name):
            text = path.read_text()
            assert not _SIGHT_HEAD_TYPE_PATTERN.search(text), (
                f"{path} mentions SightHead"
            )


# -- advance_sight_head: mode transitions -----------------------------------


def test_off_when_observ_not_observed() -> None:
    head = advance_sight_head(
        SightHead(mode="free", world_az_true_deg=10.0, world_el_deg=5.0),
        ownship=_ownship(),
        dt_s=1.0,
        align_observed=True,
        observ_observed=False,
        look_contact=None,
        desired_body_az_deg=None,
        desired_body_el_deg=None,
    )
    assert head.mode == "off"
    assert head.world_az_true_deg is None
    assert head.world_el_deg is None


def test_caged_when_observ_on_but_not_yet_aligned() -> None:
    head = advance_sight_head(
        SightHead(),
        ownship=_ownship(),
        dt_s=1.0,
        align_observed=False,
        observ_observed=True,
        look_contact=None,
        desired_body_az_deg=None,
        desired_body_el_deg=None,
    )
    assert head.mode == "caged"
    assert head.world_az_true_deg is None


def test_entering_free_seeds_boresight_at_current_attitude() -> None:
    head = advance_sight_head(
        SightHead(mode="caged"),
        ownship=_ownship(heading_true_deg=45.0),
        dt_s=0.0,
        align_observed=True,
        observ_observed=True,
        look_contact=None,
        desired_body_az_deg=None,
        desired_body_el_deg=None,
    )
    assert head.mode == "free"
    # Boresight (body 0, 0) at heading 45 is world-true azimuth 45.
    assert head.world_az_true_deg == pytest.approx(45.0)
    assert head.world_el_deg == pytest.approx(0.0)


def test_world_direction_holds_through_a_turn() -> None:
    """A world-held direction's *body* azimuth changes with heading, but
    its *world* azimuth does not -- the whole point of simulating the
    head in the world frame."""
    head = advance_sight_head(
        SightHead(mode="free", world_az_true_deg=30.0, world_el_deg=0.0),
        ownship=_ownship(heading_true_deg=0.0),
        dt_s=0.0,
        align_observed=True,
        observ_observed=True,
        look_contact=None,
        desired_body_az_deg=None,
        desired_body_el_deg=None,
    )
    assert head.world_az_true_deg == pytest.approx(30.0)

    # Ownship yaws 10 degrees right; with no new desire, the head holds
    # its own current (world) direction -- it must not have moved.
    head2 = advance_sight_head(
        head,
        ownship=_ownship(heading_true_deg=10.0),
        dt_s=0.5,
        align_observed=True,
        observ_observed=True,
        look_contact=None,
        desired_body_az_deg=None,
        desired_body_el_deg=None,
    )
    assert head2.world_az_true_deg == pytest.approx(30.0)


def test_slew_rate_limits_the_approach_to_a_new_belief_goal() -> None:
    head = SightHead(mode="free", world_az_true_deg=0.0, world_el_deg=0.0)
    dt_s = 1.0
    stepped = advance_sight_head(
        head,
        ownship=_ownship(),
        dt_s=dt_s,
        align_observed=True,
        observ_observed=True,
        look_contact=None,
        desired_body_az_deg=60.0,  # far beyond one second's reach
        desired_body_el_deg=0.0,
    )
    # SLEW_AZ_DPS deg/s for one second -- not the full 60.
    assert stepped.world_az_true_deg == pytest.approx(SLEW_AZ_DPS * dt_s, abs=1e-6)


def test_gimbal_clamp_drags_a_held_direction_at_the_stop() -> None:
    # Desire well past the +60 az gimbal stop; after enough time the head
    # must sit at the stop, not beyond it.
    head = SightHead(mode="free", world_az_true_deg=0.0, world_el_deg=0.0)
    for _ in range(20):
        head = advance_sight_head(
            head,
            ownship=_ownship(),
            dt_s=1.0,
            align_observed=True,
            observ_observed=True,
            look_contact=None,
            desired_body_az_deg=120.0,
            desired_body_el_deg=0.0,
        )
    assert head.world_az_true_deg is not None
    assert head.world_az_true_deg <= 60.0 + 1e-6


# -- select_sight_goal: the Aim source selection table -----------------------


def test_seen_row_selected_when_look_matches_last_sight_look() -> None:
    contact = _contact_seen(t_sim=5.0)
    source, az, el, _rate_az, _rate_el, contact_id, t_look = select_sight_goal(
        SightHead(),
        look_contact=contact,
        desired_world_az_deg=0.0,
        desired_world_rate_az_deg_s=0.0,
        desired_world_el_deg=0.0,
        desired_world_rate_el_deg_s=0.0,
        last_sight_look_sim=5.0,
        now_sim=5.0,
    )
    seen = seen_world_direction(contact)
    assert seen is not None
    assert source == "seen"
    assert az == pytest.approx(seen.az_true_deg)
    assert el == pytest.approx(seen.el_deg)
    assert contact_id == "CONTACT_1"
    assert t_look == pytest.approx(5.0)


def test_binocular_look_of_same_contact_does_not_steer_the_sight() -> None:
    """A binocular/unaided look also produces an exact `relative_
    direction`, but `last_sight_look_sim` only stamps a *sight-tier*
    poll -- a mismatch must fall through to `belief`, not `seen`."""
    contact = _contact_seen(t_sim=5.0)
    source, *_ = select_sight_goal(
        SightHead(),
        look_contact=contact,
        desired_world_az_deg=0.0,
        desired_world_rate_az_deg_s=0.0,
        desired_world_el_deg=0.0,
        desired_world_rate_el_deg_s=0.0,
        last_sight_look_sim=3.0,  # the sight's last look was a different poll
        now_sim=5.0,
    )
    assert source == "belief"


def test_held_row_within_window_after_seen_condition_fails() -> None:
    head = SightHead(
        aim_source="seen",
        seen_contact_id="CONTACT_1",
        last_seen_goal_az_deg=12.0,
        last_seen_goal_el_deg=2.0,
        last_seen_rate_az_deg_s=0.5,
        last_seen_rate_el_deg_s=0.0,
        last_seen_t_look=5.0,
    )
    source, az, el, rate_az, _rate_el, contact_id, t_look = select_sight_goal(
        head,
        look_contact=None,  # left the FOV
        desired_world_az_deg=0.0,
        desired_world_rate_az_deg_s=0.0,
        desired_world_el_deg=0.0,
        desired_world_rate_el_deg_s=0.0,
        last_sight_look_sim=5.0,
        now_sim=5.0 + SEEN_AIM_HOLD_S - 0.1,
    )
    assert source == "held"
    assert az == pytest.approx(12.0)
    assert el == pytest.approx(2.0)
    assert rate_az == pytest.approx(0.5)
    assert contact_id == "CONTACT_1"
    assert t_look == pytest.approx(5.0)


def test_belief_row_once_hold_expires() -> None:
    head = SightHead(
        aim_source="held",
        seen_contact_id="CONTACT_1",
        last_seen_goal_az_deg=12.0,
        last_seen_goal_el_deg=2.0,
        last_seen_t_look=5.0,
    )
    source, az, el, _rate_az, _rate_el, contact_id, t_look = select_sight_goal(
        head,
        look_contact=None,
        desired_world_az_deg=99.0,
        desired_world_rate_az_deg_s=0.0,
        desired_world_el_deg=3.0,
        desired_world_rate_el_deg_s=0.0,
        last_sight_look_sim=5.0,
        now_sim=5.0 + SEEN_AIM_HOLD_S + 0.1,
    )
    assert source == "belief"
    assert az == pytest.approx(99.0)
    assert el == pytest.approx(3.0)
    assert contact_id is None
    assert t_look is None


def test_belief_row_when_look_contact_changes() -> None:
    head = SightHead(
        aim_source="seen",
        seen_contact_id="CONTACT_1",
        last_seen_goal_az_deg=12.0,
        last_seen_goal_el_deg=2.0,
        last_seen_t_look=5.0,
    )
    other_contact = _contact_seen(contact_id="CONTACT_2", t_sim=5.0)
    source, *_ = select_sight_goal(
        head,
        look_contact=other_contact,
        desired_world_az_deg=0.0,
        desired_world_rate_az_deg_s=0.0,
        desired_world_el_deg=0.0,
        desired_world_rate_el_deg_s=0.0,
        last_sight_look_sim=3.0,  # not this contact's look this poll
        now_sim=5.1,
    )
    assert source == "belief"


def test_rate_never_differenced_across_a_seen_belief_pair() -> None:
    """A `held` -> `seen` transition for a *different* contact must not
    difference against the previous contact's last-seen goal."""
    head = SightHead(
        aim_source="held",
        seen_contact_id="CONTACT_2",
        last_seen_goal_az_deg=200.0,
        last_seen_t_look=1.0,
    )
    contact = _contact_seen(contact_id="CONTACT_1", t_sim=5.0)
    source, _az, _el, rate_az, _rate_el, contact_id, _t_look = select_sight_goal(
        head,
        look_contact=contact,
        desired_world_az_deg=0.0,
        desired_world_rate_az_deg_s=0.0,
        desired_world_el_deg=0.0,
        desired_world_rate_el_deg_s=0.0,
        last_sight_look_sim=5.0,
        now_sim=5.0,
    )
    assert source == "seen"
    assert contact_id == "CONTACT_1"
    # Different contact -- rate must be 0, never (az - 200.0) / dt.
    assert rate_az == pytest.approx(0.0)


# -- advance_sight_head wiring: the seen goal reaches the wire goal ----------


def test_advance_sight_head_seen_goal_feeds_through_to_world_goal() -> None:
    contact = _contact_seen(t_sim=5.0, forward_m=1000.0, right_m=100.0, up_m=0.0)
    head = advance_sight_head(
        SightHead(mode="free", world_az_true_deg=0.0, world_el_deg=0.0),
        ownship=_ownship(t_sim=5.0),
        dt_s=1.0,
        align_observed=True,
        observ_observed=True,
        look_contact=contact,
        desired_body_az_deg=0.0,
        desired_body_el_deg=0.0,
        last_sight_look_sim=5.0,
    )
    seen = seen_world_direction(contact)
    assert seen is not None
    assert head.aim_source == "seen"
    assert head.goal_world_az_deg == pytest.approx(seen.az_true_deg)
