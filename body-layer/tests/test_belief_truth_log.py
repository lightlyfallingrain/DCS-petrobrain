"""Tests for `belief_truth_log` -- the ground-truth/belief consistency log
(`--belief-truth-log`, `todo/todo.md`'s 2026-09-26 follow-up to the
eyesight-view work). Covers `evaluate_pair`'s pure comparison logic and
`BeliefTruthLogWriter.write_poll`'s join/output behaviour end to end."""

from __future__ import annotations

import io
import json
from pathlib import Path

from belief.cardinality import OP_1UNIT, CardinalityBelief, new_cardinality_belief
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact, ContactStore
from belief.position_belief import Covariance2D, PositionEstimate
from belief_truth_log import (
    POSITION_ERROR_UNCERTAINTY_MULTIPLE,
    BeliefTruthLogWriter,
    _cardinality_discrepancy,
    _classification_discrepancy,
    evaluate_pair,
)
from perception.detection_trace import (
    DetectionTrace,
    DetectionTraceCollector,
    GateOutcome,
)
from perception.geometry import GeoPosition
from perception.source import OwnshipState
from perception.visibility import NAKED_EYE_RANGE_CAP_M

_ZERO_COV = Covariance2D(xx=0.0, zz=0.0, xz=0.0)


def _contact(
    *,
    contact_id: str = "CONTACT_1",
    x: float = 1000.0,
    z: float = 0.0,
    covariance: Covariance2D = _ZERO_COV,
    class_value: str | None = None,
    level: SpecificityLevel = SpecificityLevel.UNKNOWN,
    cardinality: CardinalityBelief | None = None,
    contributing_observation_ids: list[str] | None = None,
) -> Contact:
    return Contact(
        id=contact_id,
        position=PositionEstimate(
            x=x,
            z=z,
            covariance=covariance,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=covariance,
        ),
        last_alt_m=0.0,
        last_class_raw="t-72",
        classification=new_classification_belief(
            value=class_value if class_value is not None else "OP_GROUPSOMETHING",
            level=level,
            established_sim=0.0,
        ),
        cardinality=(
            cardinality
            if cardinality is not None
            else new_cardinality_belief(OP_1UNIT, 0.0)
        ),
        contributing_observation_ids=contributing_observation_ids or [],
    )


_OBSERVER = GeoPosition(x=0.0, z=0.0, alt_m=0.0)


# --- evaluate_pair: position ----------------------------------------------


def test_position_error_zero_when_believed_matches_truth() -> None:
    # project_from_bearing_range: bearing=90 (due east) from observer(0,0)
    # -> x=observer.x (0), z=observer.z+range (1000) -- a believed contact
    # placed exactly there should show zero error.
    contact = _contact(x=0.0, z=1000.0)
    row = evaluate_pair(
        t_sim=0.0,
        contact=contact,
        object_id=1,
        object_type="t-72",
        true_bearing_deg=90.0,
        true_range_m=1000.0,
        observer=_OBSERVER,
        ground_truth_count=None,
    )
    assert row.position_error_m < 1e-6


def test_range_cap_tripwire_fires_beyond_naked_eye_cap() -> None:
    # The 2026-09-24 defect's own shape: a believed range far past what
    # the channel could ever have detected.
    contact = _contact(x=NAKED_EYE_RANGE_CAP_M * 9, z=0.0)
    row = evaluate_pair(
        t_sim=0.0,
        contact=contact,
        object_id=1,
        object_type="t-72",
        true_bearing_deg=0.0,
        true_range_m=1000.0,
        observer=_OBSERVER,
        ground_truth_count=None,
    )
    assert row.range_cap_tripwire is True
    assert row.tripwire is True


def test_range_cap_tripwire_does_not_fire_within_cap() -> None:
    contact = _contact(x=1000.0, z=0.0)
    row = evaluate_pair(
        t_sim=0.0,
        contact=contact,
        object_id=1,
        object_type="t-72",
        true_bearing_deg=0.0,
        true_range_m=1000.0,
        observer=_OBSERVER,
        ground_truth_count=None,
    )
    assert row.range_cap_tripwire is False


def test_position_uncertainty_tripwire_fires_when_error_dwarfs_uncertainty() -> None:
    # Believed position far from true position, but a tiny stated
    # uncertainty -- belief claiming precision it does not have.
    contact = _contact(x=1000.0, z=5000.0, covariance=_ZERO_COV)
    row = evaluate_pair(
        t_sim=0.0,
        contact=contact,
        object_id=1,
        object_type="t-72",
        true_bearing_deg=0.0,
        true_range_m=1000.0,  # true position: x=1000, z=0
        observer=_OBSERVER,
        ground_truth_count=None,
    )
    assert row.position_uncertainty_m == 0.0
    assert row.position_error_m > POSITION_ERROR_UNCERTAINTY_MULTIPLE * 0.0
    assert row.position_uncertainty_tripwire is True


# --- evaluate_pair: cardinality --------------------------------------------


def test_cardinality_discrepancy_when_count_outside_interval() -> None:
    cardinality = CardinalityBelief(lo=1, hi=1, confidence=0.5, established_sim=0.0)
    assert _cardinality_discrepancy(cardinality, ground_truth_count=4) is True


def test_cardinality_no_discrepancy_when_wide_interval_contains_truth() -> None:
    # A wide, hedged interval that still contains the true count is
    # correct hedging, not an error.
    cardinality = CardinalityBelief(lo=1, hi=10, confidence=0.5, established_sim=0.0)
    assert _cardinality_discrepancy(cardinality, ground_truth_count=4) is False


def test_cardinality_no_discrepancy_when_ground_truth_unknown() -> None:
    cardinality = CardinalityBelief(lo=1, hi=1, confidence=0.5, established_sim=0.0)
    assert _cardinality_discrepancy(cardinality, ground_truth_count=None) is False


# --- evaluate_pair: classification -----------------------------------------


def test_classification_no_discrepancy_when_belief_is_vaguer_than_truth() -> None:
    # PRESENCE/UNKNOWN never counts as a discrepancy -- honest vagueness,
    # not error.
    assert (
        _classification_discrepancy(
            new_classification_belief(
                value="OP_GROUPSOMETHING",
                level=SpecificityLevel.PRESENCE,
                established_sim=0.0,
            ),
            true_op_class="OP_ARMORED",
        )
        is False
    )


def test_classification_discrepancy_when_class_disagrees() -> None:
    belief = new_classification_belief(
        value="OP_TRUCK", level=SpecificityLevel.CLASS, established_sim=0.0
    )
    assert _classification_discrepancy(belief, true_op_class="OP_ARMORED") is True


def test_classification_no_discrepancy_when_class_agrees() -> None:
    belief = new_classification_belief(
        value="OP_ARMORED", level=SpecificityLevel.CLASS, established_sim=0.0
    )
    assert _classification_discrepancy(belief, true_op_class="OP_ARMORED") is False


def test_classification_type_level_resolves_via_parent_class() -> None:
    belief = new_classification_belief(
        value="ural", level=SpecificityLevel.TYPE, established_sim=0.0
    )
    assert _classification_discrepancy(belief, true_op_class="OP_TRUCK") is False
    assert _classification_discrepancy(belief, true_op_class="OP_ARMORED") is True


# --- BeliefTruthLogWriter.write_poll: join + output ------------------------


def _trace_entry(
    *,
    object_id: int = 1,
    observation_id: str | None,
    outcome: GateOutcome = GateOutcome.ADMITTED,
    cluster_member_object_ids: tuple[int, ...] | None = None,
) -> DetectionTrace:
    return DetectionTrace(
        object_id=object_id,
        object_type="t-72",
        t_sim=10.0,
        true_bearing_deg=0.0,
        true_range_m=1000.0,
        range_threshold_m=5000.0,
        threshold_bound="size_curve",
        outcome=outcome,
        observation_id=observation_id,
        cluster_member_object_ids=cluster_member_object_ids,
    )


def _ownship() -> OwnshipState:
    return OwnshipState(
        t_sim=10.0,
        x=0.0,
        z=0.0,
        alt_m=0.0,
        heading_true_deg=0.0,
        pitch_deg=0.0,
        bank_deg=0.0,
    )


def test_write_poll_joins_admitted_entry_to_its_contact(tmp_path: Path) -> None:
    path = Path(str(tmp_path)) / "belief_truth.jsonl"
    contact = _contact(
        contact_id="CONTACT_1", x=1000.0, z=0.0, contributing_observation_ids=["OBS_1"]
    )
    store = ContactStore()
    store._contacts["CONTACT_1"] = contact  # type: ignore[attr-defined]

    collector = DetectionTraceCollector()
    collector.records.append(
        _trace_entry(observation_id="OBS_1", cluster_member_object_ids=(1,))
    )

    stderr = io.StringIO()
    writer = BeliefTruthLogWriter(path, flush_every_n_polls=1, stderr=stderr)
    writer.write_poll(collector, store, _ownship())
    writer.close()

    # write_poll must not clear the collector -- the poll loop owns that.
    assert len(collector.records) == 1

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["contact_id"] == "CONTACT_1"
    assert row["object_id"] == 1
    assert row["ground_truth_count"] == 1


def test_write_poll_skips_unadmitted_and_unresolved_entries(tmp_path: Path) -> None:
    path = Path(str(tmp_path)) / "belief_truth.jsonl"
    store = ContactStore()
    collector = DetectionTraceCollector()
    collector.records.append(
        _trace_entry(observation_id=None, outcome=GateOutcome.COCKPIT_MASK)
    )
    collector.records.append(_trace_entry(observation_id="OBS_UNRESOLVED"))

    writer = BeliefTruthLogWriter(path, flush_every_n_polls=1, stderr=io.StringIO())
    writer.write_poll(collector, store, _ownship())
    writer.close()

    assert path.read_text(encoding="utf-8") == ""


def test_write_poll_prints_tripwire_to_stderr(tmp_path: Path) -> None:
    path = Path(str(tmp_path)) / "belief_truth.jsonl"
    contact = _contact(
        contact_id="CONTACT_1",
        x=NAKED_EYE_RANGE_CAP_M * 9,
        z=0.0,
        contributing_observation_ids=["OBS_1"],
    )
    store = ContactStore()
    store._contacts["CONTACT_1"] = contact  # type: ignore[attr-defined]

    collector = DetectionTraceCollector()
    collector.records.append(_trace_entry(observation_id="OBS_1"))

    stderr = io.StringIO()
    writer = BeliefTruthLogWriter(path, flush_every_n_polls=1, stderr=stderr)
    writer.write_poll(collector, store, _ownship())
    writer.close()

    assert "BELIEF-TRUTH TRIPWIRE" in stderr.getvalue()
    assert "CONTACT_1" in stderr.getvalue()


def test_write_poll_no_tripwire_line_for_ordinary_row(tmp_path: Path) -> None:
    path = Path(str(tmp_path)) / "belief_truth.jsonl"
    contact = _contact(
        contact_id="CONTACT_1", x=1000.0, z=0.0, contributing_observation_ids=["OBS_1"]
    )
    store = ContactStore()
    store._contacts["CONTACT_1"] = contact  # type: ignore[attr-defined]

    collector = DetectionTraceCollector()
    collector.records.append(_trace_entry(observation_id="OBS_1"))

    stderr = io.StringIO()
    writer = BeliefTruthLogWriter(path, flush_every_n_polls=1, stderr=stderr)
    writer.write_poll(collector, store, _ownship())
    writer.close()

    assert stderr.getvalue() == ""
