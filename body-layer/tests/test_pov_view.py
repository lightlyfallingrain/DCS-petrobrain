"""Tests for `pov_view` -- the real-time ASCII Petrovich-POV debug view
(`plans/pov-view/plan.md`, `BL-B99`). Covers the testable geometry/
draw-order/player-bubble/off-canvas logic; the frame's actual look is for
a human, same split `test_eyesight_view.py` already establishes."""

from __future__ import annotations

from belief.cardinality import OP_1UNIT, new_cardinality_belief
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact
from belief.position_belief import Covariance2D, PositionEstimate
from perception.association import PLAYER_BUBBLE_RADIUS_M
from perception.detection_trace import DetectionTrace, GateOutcome
from perception.geometry import GeoPosition
from pov_view import (
    DEFAULT_MAX_LINES,
    PovBeliefMarker,
    PovGroundTruthMarker,
    pov_believed_markers_from_contacts,
    pov_ground_truth_markers_from_trace,
    render_frame,
)

_ZERO_COV = Covariance2D(xx=0.0, zz=0.0, xz=0.0)


def _contact(
    *,
    x: float = 0.0,
    z: float = 0.0,
    alt_m: float = 0.0,
    class_value: str = "OP_ARMORED",
    level: SpecificityLevel = SpecificityLevel.CLASS,
) -> Contact:
    classification = new_classification_belief(
        value=class_value, level=level, established_sim=0.0
    )
    return Contact(
        id="CONTACT_1",
        position=PositionEstimate(
            x=x,
            z=z,
            covariance=_ZERO_COV,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=_ZERO_COV,
        ),
        last_alt_m=alt_m,
        last_class_raw="t-72",
        classification=classification,
        cardinality=new_cardinality_belief(OP_1UNIT, 0.0),
    )


def _trace_entry(
    *,
    true_bearing_deg: float,
    true_range_m: float,
    true_elevation_deg: float | None,
    outcome: GateOutcome,
) -> DetectionTrace:
    return DetectionTrace(
        object_id=1,
        object_type="t-72",
        t_sim=0.0,
        true_bearing_deg=true_bearing_deg,
        true_range_m=true_range_m,
        true_elevation_deg=true_elevation_deg,
        range_threshold_m=5000.0,
        threshold_bound="size_curve",
        outcome=outcome,
    )


# --- pov_ground_truth_markers_from_trace -----------------------------------


def test_ground_truth_marker_carries_azimuth_and_elevation() -> None:
    entry = _trace_entry(
        true_bearing_deg=10.0,
        true_range_m=1000.0,
        true_elevation_deg=-5.0,
        outcome=GateOutcome.ADMITTED,
    )
    [marker] = pov_ground_truth_markers_from_trace([entry], heading_true_deg=0.0)
    assert marker.azimuth_deg == 10.0
    assert marker.elevation_deg == -5.0
    assert marker.visible is True


def test_ground_truth_marker_not_visible_for_rejected_gate() -> None:
    entry = _trace_entry(
        true_bearing_deg=0.0,
        true_range_m=1000.0,
        true_elevation_deg=0.0,
        outcome=GateOutcome.TERRAIN_LOS,
    )
    [marker] = pov_ground_truth_markers_from_trace([entry], heading_true_deg=0.0)
    assert marker.visible is False


def test_player_bubble_rows_are_dropped() -> None:
    # User, 2026-10-25: "Ignore all units outside player bubble" -- a
    # PLAYER_BUBBLE row never reached check_visibility at all, so it must
    # not appear on this canvas as a "not seen" marker either.
    entry = _trace_entry(
        true_bearing_deg=0.0,
        true_range_m=12000.0,
        true_elevation_deg=0.0,
        outcome=GateOutcome.PLAYER_BUBBLE,
    )
    markers = pov_ground_truth_markers_from_trace([entry], heading_true_deg=0.0)
    assert markers == []


def test_row_with_no_elevation_is_dropped_not_fabricated() -> None:
    entry = _trace_entry(
        true_bearing_deg=0.0,
        true_range_m=1000.0,
        true_elevation_deg=None,
        outcome=GateOutcome.ADMITTED,
    )
    markers = pov_ground_truth_markers_from_trace([entry], heading_true_deg=0.0)
    assert markers == []


# --- pov_believed_markers_from_contacts ------------------------------------


def test_believed_marker_geometry() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    # Target due east, 1000 m away, 1000 m above -- bearing +90, elevation 45.
    contact = _contact(x=0.0, z=1000.0, alt_m=1000.0, class_value="OP_TRUCK")
    [marker] = pov_believed_markers_from_contacts(
        [contact], observer, heading_true_deg=0.0
    )
    assert marker.label == "TR"
    assert marker.azimuth_deg == 90.0
    assert marker.elevation_deg == 45.0


def test_believed_marker_beyond_player_bubble_is_dropped() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    contact = _contact(x=0.0, z=PLAYER_BUBBLE_RADIUS_M + 1.0, alt_m=0.0)
    markers = pov_believed_markers_from_contacts(
        [contact], observer, heading_true_deg=0.0
    )
    assert markers == []


def test_believed_marker_at_exactly_the_bubble_radius_is_kept() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    contact = _contact(x=0.0, z=PLAYER_BUBBLE_RADIUS_M, alt_m=0.0)
    markers = pov_believed_markers_from_contacts(
        [contact], observer, heading_true_deg=0.0
    )
    assert len(markers) == 1


# --- render_frame: draw order, azimuth cutoff, elevation clipping ---------


def test_believed_contact_wins_its_cell_over_the_optic_disc() -> None:
    believed = [PovBeliefMarker(label="AR", azimuth_deg=0.0, elevation_deg=0.0)]
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=90.0,
        believed=believed,
        color=False,
    )
    assert any("AR" in line for line in frame.splitlines())


def test_ground_truth_marker_does_not_survive_under_a_believed_marker() -> None:
    ground_truth = [
        PovGroundTruthMarker(azimuth_deg=0.0, elevation_deg=0.0, visible=True)
    ]
    believed = [PovBeliefMarker(label="TR", azimuth_deg=0.0, elevation_deg=0.0)]
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=15.0,
        ground_truth=ground_truth,
        believed=believed,
        color=False,
    )
    lines = frame.splitlines()
    assert any("TR" in line for line in lines)


def test_marker_beyond_azimuth_cutoff_is_not_drawn() -> None:
    believed = [PovBeliefMarker(label="AR", azimuth_deg=95.0, elevation_deg=0.0)]
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=90.0,
        believed=believed,
        azimuth_half_deg=90.0,
        color=False,
    )
    assert "AR" not in frame.split("\n", 2)[-1]


def test_marker_beyond_elevation_range_is_clipped_not_dropped() -> None:
    # Elevation beyond the canvas's extent is a display choice, not a
    # perceptual one (module docstring) -- it must still appear, clipped
    # to the canvas edge, not vanish.
    believed = [PovBeliefMarker(label="AR", azimuth_deg=0.0, elevation_deg=-500.0)]
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=90.0,
        believed=believed,
        color=False,
    )
    assert any("AR" in line for line in frame.splitlines())


def test_unaided_optic_draws_a_border_not_a_disc() -> None:
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=15.0,
        color=False,
    )
    # Two vertical border lines ("|"), not the disc glyph (".").
    assert "|" in frame
    canvas_lines = frame.splitlines()[4:]
    assert not any("." in line for line in canvas_lines)


def test_binocular_optic_draws_a_filled_disc() -> None:
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=20.0,
        color=False,
    )
    canvas_lines = frame.splitlines()[4:]
    assert any("." in line for line in canvas_lines)


def test_sight_narrow_uses_the_brown_colour_code() -> None:
    frame = render_frame(
        optic_name="sight_narrow",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=3.0,
        color=True,
    )
    assert "\x1b[38;5;130m" in frame  # BROWN


def test_render_frame_color_disabled_has_no_escape_codes() -> None:
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=15.0,
        believed=[PovBeliefMarker(label="TR", azimuth_deg=0.0, elevation_deg=0.0)],
        color=False,
    )
    assert "\x1b[" not in frame


def test_render_frame_color_enabled_has_escape_codes() -> None:
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=15.0,
        believed=[PovBeliefMarker(label="TR", azimuth_deg=0.0, elevation_deg=0.0)],
        color=True,
    )
    assert "\x1b[" in frame


def test_watched_contacts_draw_orange_and_unwatched_yellow() -> None:
    markers = [
        PovBeliefMarker(label="AR", azimuth_deg=-30.0, elevation_deg=0.0, watched=True),
        PovBeliefMarker(label="TR", azimuth_deg=30.0, elevation_deg=0.0, watched=False),
    ]
    out = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=90.0,
        believed=markers,
        color=True,
    )
    assert "\x1b[38;5;208m" in out, "watched marker is not orange"
    assert "\x1b[33m" in out, "unwatched marker is not yellow"


def test_elevation_axis_labels_present() -> None:
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=90.0,
        color=False,
    )
    assert "+10" in frame
    assert "-10" in frame
    assert "-20" in frame


def test_azimuth_axis_labels_present() -> None:
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=90.0,
        color=False,
    )
    assert "-90" in frame
    assert "+90" in frame
    assert "+30" in frame
    assert "+60" in frame


def test_default_max_lines_is_a_module_constant() -> None:
    assert DEFAULT_MAX_LINES == 60


def test_frame_respects_a_tight_max_lines_budget() -> None:
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=90.0,
        color=False,
        max_lines=5,
    )
    assert len(frame.splitlines()) <= 5
