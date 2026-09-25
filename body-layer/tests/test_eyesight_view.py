"""Tests for `eyesight_view` -- the real-time ASCII eyesight view
(`todo/todo.md`'s "Added 2026-09-25 (user)" entry). Covers the testable
geometry/label/draw-order/off-edge logic; the frame's actual look is for a
human (`tools/eyesight_sample.py`), the same split `speak_samples.py`
already establishes for spoken phrasing."""

from __future__ import annotations

import math

from belief.cardinality import OP_1UNIT, CardinalityBelief, new_cardinality_belief
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact
from belief.position_belief import Covariance2D, PositionEstimate
from eyesight_view import (
    BeliefMarker,
    GroundTruthMarker,
    believed_markers_from_contacts,
    believed_markers_from_trace_rows,
    contact_label,
    ground_truth_markers_from_trace,
    relative_bearing_deg,
    render_frame,
)
from perception.detection_trace import DetectionTrace, GateOutcome
from perception.gaze import Gaze
from perception.geometry import GeoPosition

_ZERO_COV = Covariance2D(xx=0.0, zz=0.0, xz=0.0)


def _contact(
    *,
    x: float = 0.0,
    z: float = 0.0,
    alt_m: float = 0.0,
    class_value: str | None = None,
    level: SpecificityLevel = SpecificityLevel.UNKNOWN,
    cardinality: CardinalityBelief | None = None,
) -> Contact:
    classification = new_classification_belief(
        value=class_value if class_value is not None else "OP_GROUPSOMETHING",
        level=level,
        established_sim=0.0,
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
        cardinality=(
            cardinality
            if cardinality is not None
            else new_cardinality_belief(OP_1UNIT, 0.0)
        ),
    )


# --- relative_bearing_deg -----------------------------------------------


def test_relative_bearing_deg_dead_ahead() -> None:
    assert relative_bearing_deg(true_bearing_deg=45.0, heading_true_deg=45.0) == 0.0


def test_relative_bearing_deg_wraps_through_north() -> None:
    # True bearing 010, heading 350 -- the target is 20 deg clockwise of
    # the nose, not -340.
    result = relative_bearing_deg(true_bearing_deg=10.0, heading_true_deg=350.0)
    assert math.isclose(result, 20.0)


def test_relative_bearing_deg_behind() -> None:
    result = relative_bearing_deg(true_bearing_deg=180.0, heading_true_deg=0.0)
    assert math.isclose(abs(result), 180.0)


# --- contact_label --------------------------------------------------------


def test_label_unknown_for_no_classification() -> None:
    contact = _contact(level=SpecificityLevel.UNKNOWN)
    assert contact_label(contact) == "U"


def test_label_air_defence() -> None:
    contact = _contact(class_value="OP_SRSAM", level=SpecificityLevel.CLASS)
    assert contact_label(contact) == "AA"


def test_label_armour() -> None:
    contact = _contact(class_value="OP_ARMORED", level=SpecificityLevel.CLASS)
    assert contact_label(contact) == "AR"


def test_label_truck() -> None:
    contact = _contact(class_value="OP_TRUCK", level=SpecificityLevel.CLASS)
    assert contact_label(contact) == "TR"


def test_label_truck_type_level_resolves_via_parent_class() -> None:
    # TYPE-level value is a specific reporting name, not an OP_* bucket --
    # contact_label must resolve it through parent_class_of, same as a
    # CLASS-level contact.
    contact = _contact(class_value="ural", level=SpecificityLevel.TYPE)
    assert contact_label(contact) == "TR"


def test_label_out_of_vocabulary_class_falls_back_to_unknown() -> None:
    # OP_SHIP is real classification vocabulary but not one of the user's
    # four named kinds.
    contact = _contact(class_value="OP_SHIP", level=SpecificityLevel.CLASS)
    assert contact_label(contact) == "U"


def test_label_group_wins_over_classification() -> None:

    contact = _contact(
        class_value="OP_ARMORED",
        level=SpecificityLevel.CLASS,
        cardinality=CardinalityBelief(lo=3, hi=5, confidence=0.5, established_sim=0.0),
    )
    assert contact_label(contact) == "G"


def test_label_singular_cardinality_does_not_force_group() -> None:

    contact = _contact(
        class_value="OP_TRUCK",
        level=SpecificityLevel.CLASS,
        cardinality=CardinalityBelief(lo=1, hi=1, confidence=0.5, established_sim=0.0),
    )
    assert contact_label(contact) == "TR"


# --- believed_markers_from_contacts ---------------------------------------


def test_believed_markers_from_contacts_geometry() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    # Target due east (bearing 090) of observer, ownship heading 000 --
    # relative bearing should read +90.
    contact = _contact(
        x=0.0, z=1000.0, class_value="OP_TRUCK", level=SpecificityLevel.CLASS
    )
    markers = believed_markers_from_contacts([contact], observer, heading_true_deg=0.0)
    assert len(markers) == 1
    assert markers[0].label == "TR"
    assert math.isclose(markers[0].bearing_deg, 90.0, abs_tol=1e-6)
    assert math.isclose(markers[0].range_m, 1000.0, abs_tol=1e-6)


# --- ground_truth_markers_from_trace --------------------------------------


def _trace_entry(
    *, true_bearing_deg: float, true_range_m: float, outcome: GateOutcome
) -> DetectionTrace:
    return DetectionTrace(
        object_id=1,
        object_type="t-72",
        t_sim=0.0,
        true_bearing_deg=true_bearing_deg,
        true_range_m=true_range_m,
        range_threshold_m=5000.0,
        threshold_bound="size_curve",
        outcome=outcome,
    )


def test_ground_truth_marker_visible_for_admitted() -> None:
    entry = _trace_entry(
        true_bearing_deg=0.0, true_range_m=1000.0, outcome=GateOutcome.ADMITTED
    )
    [marker] = ground_truth_markers_from_trace([entry], heading_true_deg=0.0)
    assert marker.visible is True


def test_ground_truth_marker_not_visible_for_rejected_gate() -> None:
    entry = _trace_entry(
        true_bearing_deg=0.0, true_range_m=1000.0, outcome=GateOutcome.TERRAIN_LOS
    )
    [marker] = ground_truth_markers_from_trace([entry], heading_true_deg=0.0)
    assert marker.visible is False


# --- believed_markers_from_trace_rows (offline replay) --------------------


def test_believed_markers_from_trace_rows_dedupes_by_contact_id() -> None:
    rows = [
        {
            "object_id": 1,
            "object_type": "ural",
            "true_bearing_deg": 10.0,
            "true_range_m": 2000.0,
            "outcome": "admitted",
            "contact_id": "CONTACT_1",
        },
        {
            "object_id": 2,
            "object_type": "ural",
            "true_bearing_deg": 11.0,
            "true_range_m": 2010.0,
            "outcome": "admitted",
            "contact_id": "CONTACT_1",
        },
        {
            "object_id": 3,
            "object_type": "t-72",
            "true_bearing_deg": -40.0,
            "true_range_m": 500.0,
            "outcome": "cockpit_mask",
            "contact_id": None,
        },
    ]
    markers = believed_markers_from_trace_rows(rows, heading_true_deg=0.0)
    assert len(markers) == 1
    assert markers[0].label == "TR"


# --- render_frame: draw order, cockpit-mask clipping, off-edge -----------


def _full_gaze() -> Gaze:
    return Gaze(center_azimuth_deg=0.0, half_width_deg=90.0, label="full")


def test_believed_contact_wins_its_cell_over_the_gaze_cone() -> None:
    # A believed contact placed dead ahead, well inside the wide gaze
    # cone's own footprint -- its label must survive the cone's draw pass.
    believed = [BeliefMarker(label="AR", bearing_deg=0.0, range_m=2000.0)]
    frame = render_frame(
        gaze=_full_gaze(),
        optic_name="unaided",
        rear_cutoff_deg=130.0,
        believed=believed,
        radius_m=5000.0,
        width=41,
        color=False,
    )
    # Bearing 0, range 2000m at radius=5000m/width=41 lands at canvas
    # row=6 (ownship_row=10, 2000/500m-per-row=4 rows forward), col=20
    # (dead centre) -- computed directly from render_frame's own formula
    # rather than searching the whole frame, so this cannot be satisfied
    # by the legend text (which also contains the substring "AR").
    canvas_lines = frame.splitlines()[2:]
    assert canvas_lines[6][20:22] == "AR"


def test_ground_truth_marker_does_not_survive_under_a_believed_marker() -> None:
    # Same cell, ground truth first then a believed contact -- the
    # ground-truth glyph must not remain visible once the believed marker
    # is drawn on top of it (module docstring's draw-order rule).
    ground_truth = [GroundTruthMarker(bearing_deg=0.0, range_m=2000.0, visible=True)]
    believed = [BeliefMarker(label="TR", bearing_deg=0.0, range_m=2000.0)]
    frame = render_frame(
        gaze=_full_gaze(),
        optic_name="unaided",
        rear_cutoff_deg=130.0,
        ground_truth=ground_truth,
        believed=believed,
        radius_m=5000.0,
        width=41,
        color=False,
    )
    # Same cell math as test_believed_contact_wins_its_cell_over_the_gaze_
    # cone above: row=6, col=20 for bearing=0/range=2000m at this
    # radius/width -- the exact cell must read the believed label, not the
    # ground-truth glyph ("." for visible) it was drawn over.
    canvas_lines = frame.splitlines()[2:]
    assert canvas_lines[6][20:22] == "TR"


def test_marker_beyond_rear_cutoff_is_not_drawn() -> None:
    # A contact behind the cockpit-mask's own rear cutoff cannot be seen
    # at all -- it must not appear on the canvas.
    believed = [BeliefMarker(label="AR", bearing_deg=170.0, range_m=1000.0)]
    frame = render_frame(
        gaze=_full_gaze(),
        optic_name="unaided",
        rear_cutoff_deg=130.0,
        believed=believed,
        radius_m=5000.0,
        width=41,
        color=False,
    )
    canvas_lines = frame.splitlines()[2:]
    assert not any("AR" in line for line in canvas_lines)


def test_contact_beyond_radius_appears_in_legend_not_silently_dropped() -> None:
    believed = [BeliefMarker(label="AA", bearing_deg=20.0, range_m=8890.0)]
    frame = render_frame(
        gaze=_full_gaze(),
        optic_name="unaided",
        rear_cutoff_deg=130.0,
        believed=believed,
        radius_m=5000.0,
        width=41,
        color=False,
    )
    assert "beyond 5.0km radius:" in frame
    beyond_section = frame.split("beyond 5.0km radius:", 1)[1]
    assert "AA" in beyond_section
    assert "8.9km" in beyond_section


def test_ownship_marker_is_always_visible() -> None:
    # Regression test: the gaze centreline and the rear-cutoff boundary
    # rays both start their trace at range 0 (ownship's own cell), and an
    # earlier draft used set_if_blank for the ownship glyph -- which left
    # it permanently hidden under whichever ray happened to draw first.
    frame = render_frame(
        gaze=_full_gaze(),
        optic_name="unaided",
        rear_cutoff_deg=130.0,
        radius_m=5000.0,
        width=41,
        color=False,
    )
    canvas_lines = frame.splitlines()[2:]
    assert any("^" in line for line in canvas_lines)


def test_default_radius_is_5km() -> None:
    from eyesight_view import DEFAULT_RADIUS_M

    assert DEFAULT_RADIUS_M == 5000.0


def test_render_frame_color_disabled_has_no_escape_codes() -> None:
    frame = render_frame(
        gaze=_full_gaze(),
        optic_name="unaided",
        rear_cutoff_deg=130.0,
        believed=[BeliefMarker(label="TR", bearing_deg=0.0, range_m=1000.0)],
        radius_m=5000.0,
        width=41,
        color=False,
    )
    assert "\x1b[" not in frame


def test_render_frame_color_enabled_has_escape_codes() -> None:
    frame = render_frame(
        gaze=_full_gaze(),
        optic_name="unaided",
        rear_cutoff_deg=130.0,
        believed=[BeliefMarker(label="TR", bearing_deg=0.0, range_m=1000.0)],
        radius_m=5000.0,
        width=41,
        color=True,
    )
    assert "\x1b[" in frame


def test_binocular_optic_selects_blue_gaze_cone() -> None:
    frame = render_frame(
        gaze=Gaze(center_azimuth_deg=0.0, half_width_deg=4.25, label="fixed_look"),
        optic_name="binocular",
        rear_cutoff_deg=130.0,
        radius_m=5000.0,
        width=41,
        color=True,
    )
    assert "\x1b[34m" in frame  # _BLUE


def _many_distant_markers(count: int) -> list[BeliefMarker]:
    """`count` believed contacts, all beyond a 5 km radius, spread in
    bearing and increasing in range."""
    return [
        BeliefMarker(
            label="AR",
            bearing_deg=float(-120 + index * 6),
            range_m=5200.0 + index * 180.0,
        )
        for index in range(count)
    ]


def _frame(markers: list[BeliefMarker], max_lines: int | None) -> list[str]:
    return render_frame(
        gaze=Gaze(center_azimuth_deg=-60.0, half_width_deg=15.0, label="11_oclock"),
        optic_name="unaided",
        rear_cutoff_deg=130.0,
        believed=markers,
        radius_m=5000.0,
        color=False,
        max_lines=max_lines,
    ).splitlines()


def test_frame_never_exceeds_its_line_budget() -> None:
    """Found in use, not in testing (user, 2026-09-25): a long
    beyond-radius list pushed the frame past the console's ~60 lines and
    scrolled the canvas off the top — so the picture this tool exists to
    show was the part that got lost. His workaround was raising the radius
    to 10 km, which is backwards: it shrinks the list by making the view
    coarser.

    The list is capped rather than the canvas, because the canvas is the
    instrument and the list is an overflow note about what it could not
    draw."""
    markers = _many_distant_markers(40)

    assert len(_frame(markers, None)) > 60, "fixture must actually overflow"

    for budget in (60, 40, 30):
        lines = _frame(markers, budget)
        assert len(lines) <= budget, f"budget {budget} exceeded: {len(lines)}"


def test_a_truncated_list_says_so_and_keeps_the_nearest() -> None:
    """Truncation must be visible and must keep the *nearest* entries — a
    silently shortened list is the one way this could mislead, and the
    near ones are the ones most likely to matter."""
    lines = _frame(_many_distant_markers(40), 40)

    assert lines[-1].strip().startswith("... and "), lines[-1]
    assert "more" in lines[-1]

    listed = [line for line in lines if line.startswith("  believed")]
    ranges = [float(line.rsplit(" ", 1)[-1].removesuffix("km")) for line in listed]
    assert ranges == sorted(ranges), "beyond-radius list is not nearest-first"
    assert abs(ranges[0] - 5.2) < 0.05, ranges[:3]


def test_beyond_radius_list_is_ordered_by_range_not_by_rendered_text() -> None:
    """The original ordering sorted the rendered line alphabetically, so
    'believed' sorted before 'truth' and then by label — a 9 km contact
    could outrank a 5.1 km one. Nearest-first is what survives
    truncation, so the ordering is load-bearing rather than cosmetic."""
    markers = [
        BeliefMarker(label="U", bearing_deg=10.0, range_m=9000.0),
        BeliefMarker(label="AA", bearing_deg=-10.0, range_m=5100.0),
    ]
    listed = [line for line in _frame(markers, None) if line.startswith("  believed")]

    assert "5.1km" in listed[0], listed
    assert "9.0km" in listed[1], listed
