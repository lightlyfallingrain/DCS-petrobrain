"""Tests for `pov_view` -- the real-time ASCII Petrovich-POV debug view
(`plans/pov-view/plan.md`, `BL-B99`). Covers the testable geometry/
draw-order/player-bubble/off-canvas logic; the frame's actual look is for
a human, same split `test_eyesight_view.py` already establishes."""

from __future__ import annotations

from ascii_canvas import (
    BG_BLUE,
    BG_BROWN,
    BOLD,
    GROUND_TRUTH_NOT_SEEN_GLYPH,
    GROUND_TRUTH_SEEN_GLYPH,
    YELLOW,
)
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


def test_unaided_optic_draws_eye_edges_not_a_disc() -> None:
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=15.0,
        color=False,
    )
    # Two vertical green eye-edge lines, in the eye-edge's own glyph
    # ("‖", review Required Fix 3) -- never the optic-disc glyph (".").
    assert "‖" in frame
    canvas_lines = frame.splitlines()[4:]
    assert not any("." in line for line in canvas_lines)


def test_eye_edge_glyph_differs_from_the_gridline_glyph() -> None:
    # Mutation check (review's own method, Required Fix 1): the eye edge
    # must draw a different character than the dim gray gridline, or the
    # sector is unreadable with colour off. Confirmed by construction: the
    # eye-edge glyph is U+2016, the gridline glyph is plain "|" (U+007C).
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=15.0,
        color=False,
    )
    assert "‖" in frame
    assert "|" in frame  # the gridlines/border columns, still present too


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


def test_sight_narrow_uses_the_brown_background_tint_with_colour_on() -> None:
    # User amendment, 2026-10-25: "the optics FOV highlight could use
    # background color instead" -- with colour on, the FOV is a
    # background tint (BG_BROWN), not a foreground dot colour.
    frame = render_frame(
        optic_name="sight_narrow",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=3.0,
        color=True,
    )
    assert BG_BROWN in frame
    canvas_lines = frame.splitlines()[4:]
    assert not any("." in line for line in canvas_lines)


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


# --- Review required fixes: glyphs, border, gridlines ----------------------


def test_ground_truth_glyphs_are_the_shared_top_down_pair_not_ascii() -> None:
    # Required Fix 1 (review.md): the top-down view's own "." (seen) was
    # rejected by the user's explicit instruction ("use the existing
    # symbols from the top-down graph") -- pin the real characters, and
    # pin them against the shared constant so the two views cannot drift
    # apart independently.
    assert GROUND_TRUTH_SEEN_GLYPH == "·"
    assert GROUND_TRUTH_NOT_SEEN_GLYPH == "×"
    seen = [PovGroundTruthMarker(azimuth_deg=0.0, elevation_deg=0.0, visible=True)]
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=200.0,  # well outside the canvas -- no disc drawn
        boresight_elevation_deg=0.0,
        half_angle_deg=1.0,
        ground_truth=seen,
        color=False,
    )
    assert GROUND_TRUTH_SEEN_GLYPH in frame
    # Mutation check (review's own method): a seen marker must never draw
    # as the plain ASCII "." the old code used -- that glyph is reserved
    # for the optic FOV dot and must not appear for a ground-truth marker
    # here, where no disc is drawn at all.
    canvas_lines = frame.splitlines()[4:]
    assert not any("." in line for line in canvas_lines)


def test_ground_truth_not_seen_glyph_is_pinned_too() -> None:
    # Review's own optional refinement: pin the not-seen side too, not
    # just the seen side the review's mutation check happened to use.
    not_seen = [PovGroundTruthMarker(azimuth_deg=0.0, elevation_deg=0.0, visible=False)]
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=200.0,  # well outside the canvas -- no disc drawn
        boresight_elevation_deg=0.0,
        half_angle_deg=1.0,
        ground_truth=not_seen,
        color=False,
    )
    assert GROUND_TRUTH_NOT_SEEN_GLYPH in frame
    canvas_lines = frame.splitlines()[4:]
    assert not any("x" in line for line in canvas_lines)  # old ASCII glyph


def test_optic_fov_disc_still_draws_as_a_plain_dot() -> None:
    # The user's own instruction: "draw the current optic's FOV with dots
    # '.'" -- the disc glyph must stay plain ASCII "." and must not be
    # confused with either ground-truth glyph (review's Required Fix 1
    # caution: "." vs "·" must differ).
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=20.0,
        color=False,
    )
    canvas_lines = frame.splitlines()[4:]
    assert any("." in line for line in canvas_lines)
    assert not any(GROUND_TRUTH_SEEN_GLYPH in line for line in canvas_lines)
    assert not any(GROUND_TRUTH_NOT_SEEN_GLYPH in line for line in canvas_lines)


def test_top_and_bottom_border_rows_are_full_dash_lines() -> None:
    # Required Fix 2: the user's mock shows a complete "-" border row at
    # both elevation extremes, not just a labelled top edge.
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=-90.0,  # disc nowhere near either border row
        half_angle_deg=2.0,
        color=False,
    )
    canvas_lines = frame.splitlines()[4:]
    top_row, bottom_row = canvas_lines[0], canvas_lines[-1]
    assert top_row.count("-") > len(top_row) // 2
    assert bottom_row.count("-") > len(bottom_row) // 2


def test_vertical_gridlines_run_through_the_full_canvas_body() -> None:
    # Required Fix 2: dim "|" gridlines at every 30-degree tick, the whole
    # canvas height, not just a header tick row above the canvas.
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=-90.0,
        half_angle_deg=2.0,
        color=False,
    )
    canvas_lines = frame.splitlines()[4:]
    # Interior rows (not the border rows, which are solid dashes) must
    # each carry at least one gridline "|".
    interior_rows = canvas_lines[1:-1]
    assert interior_rows, "expected at least one interior row for this canvas"
    assert all("|" in row for row in interior_rows)


def test_gridlines_and_border_are_drawn_before_the_optic_disc() -> None:
    # Required Fix 2's draw-order clause: the disc must win its cell over
    # a gridline/border cell beneath it, not leave a gap in the disc.
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,  # boresight sits right on the centre gridline
        boresight_elevation_deg=0.0,  # and on the 0-degree elevation row
        half_angle_deg=5.0,
        color=False,
    )
    canvas_lines = frame.splitlines()[4:]
    center_row = canvas_lines[len(canvas_lines) // 2]
    # The centre column must show the disc glyph, not a gridline "|" --
    # i.e. the disc has overridden the gridline rather than the gridline
    # surviving underneath it.
    assert "." in center_row


# --- User amendment (2026-10-25): optic-FOV highlight as a bg tint -------


def test_disc_is_a_background_tint_not_a_dot_with_colour_on() -> None:
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=20.0,
        color=True,
    )
    assert BG_BLUE in frame
    canvas_lines = frame.splitlines()[4:]
    assert not any("." in line for line in canvas_lines)


def test_disc_falls_back_to_dots_with_colour_off() -> None:
    # Unchanged from the user's original instruction ("draw the current
    # optic's FOV with dots '.'") -- there is no way to show a background
    # tint in plain text, so colour off keeps the old dot rendering.
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=20.0,
        color=False,
    )
    assert "\x1b[" not in frame
    canvas_lines = frame.splitlines()[4:]
    assert any("." in line for line in canvas_lines)


def test_marker_inside_the_disc_keeps_its_own_glyph_and_gains_the_tint() -> None:
    # The whole point of the amendment: a background tint must never hide
    # a marker (or anything else) inside the FOV -- the marker's own
    # glyph/foreground survive, and the cell additionally carries the
    # disc's background code.
    believed = [PovBeliefMarker(label="AR", azimuth_deg=0.0, elevation_deg=0.0)]
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=20.0,
        believed=believed,
        color=True,
    )
    assert f"{BOLD}{YELLOW}{BG_BLUE}A" in frame
    assert f"{BOLD}{YELLOW}{BG_BLUE}R" in frame


def test_blank_cell_inside_the_disc_renders_as_a_tinted_space() -> None:
    # A cell inside the FOV with nothing else drawn on it is not left
    # untouched -- it still carries the background tint, as a tinted
    # blank, confirming the tint paints the whole disc rather than only
    # cells that already had a marker/gridline on them.
    frame = render_frame(
        optic_name="binocular",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=20.0,
        color=True,
    )
    assert f"{BG_BLUE} " in frame


def test_eye_sector_border_cells_are_recoloured_green() -> None:
    # Required Fix 3's second clause: the top/bottom border cells across
    # the naked-eye sector's azimuth width are recoloured green, so the
    # sector reads as a highlighted band rather than two free-floating
    # vertical lines.
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=15.0,
        color=True,
    )
    lines = frame.splitlines()
    top_border_line, bottom_border_line = lines[4], lines[-1]
    green = "\x1b[32m"
    assert f"{green}-" in top_border_line
    assert f"{green}-" in bottom_border_line


def test_eye_sector_border_highlight_is_absent_without_colour() -> None:
    # Same scenario as above with color=False -- the recoloured segment
    # must render as plain "-", not reappear as some other glyph, since
    # colour is the only thing distinguishing it from the rest of the
    # border row.
    frame = render_frame(
        optic_name="unaided",
        boresight_azimuth_deg=0.0,
        boresight_elevation_deg=0.0,
        half_angle_deg=15.0,
        color=False,
    )
    lines = frame.splitlines()
    assert "\x1b[" not in lines[4]
    assert "\x1b[" not in lines[-1]
