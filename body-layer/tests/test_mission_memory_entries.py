"""`mission_memory.entries` -- JSON round-trip for every entry kind,
including an all-nullable entry."""

from __future__ import annotations

import json
import math

from mission_memory.entries import (
    AirDefencePayload,
    AttackRunPayload,
    CompositionItem,
    Entry,
    EntryPosition,
    FiredOnPayload,
    GroupPayload,
    MarkPayload,
    MotionInfo,
    PhaseInfo,
    SeenHow,
    ThreatInfo,
    decode_entry,
    encode_entry,
)


def _roundtrip(entry: Entry) -> Entry:
    """Encode, serialise through real `json.dumps`/`json.loads` (not just
    the in-memory dict), and decode -- so the round trip actually exercises
    the wire format a debrief tool would read, `math.inf` included."""
    text = json.dumps(encode_entry(entry))
    return decode_entry(json.loads(text))


def _base_kwargs() -> dict[str, object]:
    return {
        "schema": 1,
        "seq": 1,
        "provenance": "observed",
        "t_sim": 10.0,
        "t_wall": 1000.0,
        "phase": PhaseInfo(name="ingress", waypoint_index=2),
        "pos": EntryPosition(
            x=100.0,
            z=200.0,
            y=50.0,
            uncertainty_m=25.0,
            as_of_sim=9.5,
            lat=35.1,
            lon=36.2,
            landmark="the bridge",
        ),
        "seen": SeenHow(
            optic="naked_eye", range_m=1500.0, confidence=0.6, certainty="observed"
        ),
        "belief_ref": "CONTACT_17",
        "strikes": None,
        "iff": None,
    }


def test_group_entry_round_trips() -> None:
    kwargs = _base_kwargs()
    entry = Entry(
        **kwargs,  # type: ignore[arg-type]
        kind="group",
        payload=GroupPayload(
            composition=(
                CompositionItem(
                    op_class="OP_BTR", lo=4, hi=5, confidence=0.6, count_word="handful"
                ),
            ),
            motion=MotionInfo(state="moving", dir=None),
            ad_link=None,
        ),
    )
    result = _roundtrip(entry)
    assert result == entry


def test_air_defence_entry_round_trips() -> None:
    kwargs = _base_kwargs()
    entry = Entry(
        **kwargs,  # type: ignore[arg-type]
        kind="air_defence",
        payload=AirDefencePayload(
            composition=(
                CompositionItem(
                    op_class="OP_SRSAM",
                    lo=1,
                    hi=1,
                    confidence=0.7,
                    count_word=None,
                ),
            ),
            group_link=3,
            threat=ThreatInfo(envelope_m=8000.0, source="OP_SRSAM"),
        ),
    )
    result = _roundtrip(entry)
    assert result == entry


def test_attack_run_entry_round_trips() -> None:
    kwargs = _base_kwargs()
    entry = Entry(
        **kwargs,  # type: ignore[arg-type]
        kind="attack_run",
        payload=AttackRunPayload(
            target_seq=4, target_ref="CONTACT_9", weapon=None, outcome="unknown"
        ),
    )
    result = _roundtrip(entry)
    assert result == entry


def test_mark_entry_round_trips() -> None:
    kwargs = _base_kwargs()
    entry = Entry(
        **kwargs,  # type: ignore[arg-type]
        kind="mark",
        payload=MarkPayload(index=1, label="LZ", anchor="ownship"),
    )
    result = _roundtrip(entry)
    assert result == entry


def test_fired_on_entry_round_trips() -> None:
    kwargs = _base_kwargs()
    entry = Entry(
        **kwargs,  # type: ignore[arg-type]
        kind="fired_on",
        payload=FiredOnPayload(
            shooter_seq=2, shooter_ref="CONTACT_5", targets_ownship=True
        ),
    )
    result = _roundtrip(entry)
    assert result == entry


def test_all_nullable_fields_round_trip() -> None:
    """Every top-level nullable field at once -- `phase`/`pos`/`seen`/
    `belief_ref`/`strikes` all `None`, and a payload whose own nullable
    fields are all `None` too. A pilot-commanded mark with no selected
    target and no world-model connection would look exactly like this."""
    entry = Entry(
        schema=1,
        seq=1,
        kind="mark",
        provenance="commanded",
        t_sim=5.0,
        t_wall=500.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=None,
        strikes=None,
        iff=None,
        payload=MarkPayload(index=1, label=None, anchor="ownship"),
    )
    result = _roundtrip(entry)
    assert result == entry


def test_open_ended_cardinality_bucket_hi_is_infinite() -> None:
    """`CompositionItem.hi` can be `math.inf` (`OP_MORETHAN15UNITS`) --
    `json`'s non-standard `Infinity` token round-trips with no special
    casing (module docstring)."""
    kwargs = _base_kwargs()
    entry = Entry(
        **kwargs,  # type: ignore[arg-type]
        kind="group",
        payload=GroupPayload(
            composition=(
                CompositionItem(
                    op_class="OP_BTR",
                    lo=16,
                    hi=math.inf,
                    confidence=0.5,
                    count_word="many",
                ),
            ),
            motion=MotionInfo(state=None, dir=None),
            ad_link=None,
        ),
    )
    text = json.dumps(encode_entry(entry))
    assert "Infinity" in text
    result = decode_entry(json.loads(text))
    assert result == entry
