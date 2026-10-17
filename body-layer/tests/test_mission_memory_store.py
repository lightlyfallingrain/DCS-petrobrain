"""`mission_memory.store` -- the strike chain, the Co-moving Fields table,
and the single-construction-site obligation the plan transfers to the
Implementer."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mission_memory.entries import FiredOnPayload, MarkPayload, decode_entry
from mission_memory.log import MissionMemoryLogWriter
from mission_memory.store import MissionMemory, rebuild_struck_by

_SRC = Path(__file__).resolve().parent.parent / "src" / "mission_memory"


def _fired_on_payload() -> FiredOnPayload:
    return FiredOnPayload(
        shooter_seq=None, shooter_ref="CONTACT_1", targets_ownship=True
    )


def test_append_mints_monotonic_seq_starting_at_one() -> None:
    store = MissionMemory()
    first = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    second = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    assert first.seq == 1
    assert second.seq == 2


def test_strike_is_recorded_and_derived_struck_by_reflects_it() -> None:
    """append -> strike -> derived `struck_by` -- the plan's Decision 4
    chain, exercised end to end."""
    store = MissionMemory()
    original = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    replacement = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=original.seq,
        payload=_fired_on_payload(),
    )
    assert store.struck_by == {original.seq: replacement.seq}
    assert store.is_struck(original.seq)
    assert not store.is_struck(replacement.seq)


def test_replay_rebuilds_struck_by_from_entries_alone() -> None:
    """A debrief tool only ever has the JSONL file, never a live store --
    `rebuild_struck_by` must agree with the live `struck_by` index when
    replayed over the same entries in order."""
    store = MissionMemory()
    a = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    b = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=a.seq,
        payload=_fired_on_payload(),
    )
    store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=3.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=b.seq,
        payload=_fired_on_payload(),
    )
    assert rebuild_struck_by(store.entries) == store.struck_by


def test_replay_rebuilds_struck_by_from_an_actual_jsonl_file(tmp_path: Path) -> None:
    """The same chain, but genuinely written to disk through `log.
    MissionMemoryLogWriter` and read back with `entries.decode_entry` --
    "from the file alone" taken literally, not merely from the in-memory
    `Entry` objects `MissionMemory` itself still held."""
    path = tmp_path / "mission_memory.jsonl"
    writer = MissionMemoryLogWriter(path)
    store = MissionMemory()
    store.set_sink(writer.write)

    a = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=a.seq,
        payload=_fired_on_payload(),
    )

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    replayed_entries = [decode_entry(json.loads(line)) for line in lines]
    assert rebuild_struck_by(replayed_entries) == store.struck_by


def test_striking_an_already_struck_entry_is_rejected() -> None:
    """A second strike of one entry is a bug in the caller, not a chain
    (Co-moving Fields table's `_struck_by` row) -- rejected, never
    silently layered."""
    store = MissionMemory()
    original = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=original.seq,
        payload=_fired_on_payload(),
    )
    with pytest.raises(ValueError):
        store.append(
            kind="fired_on",
            provenance="observed",
            t_sim=3.0,
            phase=None,
            pos=None,
            seen=None,
            belief_ref="CONTACT_1",
            strikes=original.seq,
            payload=_fired_on_payload(),
        )


def test_striking_an_unknown_seq_is_rejected() -> None:
    store = MissionMemory()
    with pytest.raises(ValueError):
        store.append(
            kind="fired_on",
            provenance="observed",
            t_sim=1.0,
            phase=None,
            pos=None,
            seen=None,
            belief_ref="CONTACT_1",
            strikes=999,
            payload=_fired_on_payload(),
        )


def test_latest_live_seq_tracks_the_newest_entry_per_contact() -> None:
    store = MissionMemory()
    store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    second = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    assert store.latest_live_seq("CONTACT_1") == second.seq
    assert store.latest_live_seq("CONTACT_999") is None


def test_mark_index_is_minted_by_append_regardless_of_caller_value() -> None:
    """`append` overwrites `payload.index`, never trusting the caller's
    placeholder (`entries.MarkPayload`'s own docstring)."""
    store = MissionMemory()
    first = store.append(
        kind="mark",
        provenance="commanded",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=None,
        strikes=None,
        payload=MarkPayload(index=999, label=None, anchor="ownship"),
    )
    second = store.append(
        kind="mark",
        provenance="commanded",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=None,
        strikes=None,
        payload=MarkPayload(index=999, label=None, anchor="ownship"),
    )
    assert isinstance(first.payload, MarkPayload)
    assert isinstance(second.payload, MarkPayload)
    assert first.payload.index == 1
    assert second.payload.index == 2


def test_mark_index_is_not_incremented_by_non_mark_appends() -> None:
    store = MissionMemory()
    store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    mark = store.append(
        kind="mark",
        provenance="commanded",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=None,
        strikes=None,
        payload=MarkPayload(index=0, label=None, anchor="ownship"),
    )
    assert isinstance(mark.payload, MarkPayload)
    assert mark.payload.index == 1


def test_mark_index_never_reused_across_a_struck_mark() -> None:
    """A struck mark's number is retired with it, never reissued to the
    entry that replaces it."""
    store = MissionMemory()
    first_mark = store.append(
        kind="mark",
        provenance="commanded",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=None,
        strikes=None,
        payload=MarkPayload(index=0, label=None, anchor="ownship"),
    )
    replacement = store.append(
        kind="mark",
        provenance="commanded",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=None,
        strikes=first_mark.seq,
        payload=MarkPayload(index=0, label=None, anchor="ownship"),
    )
    assert isinstance(first_mark.payload, MarkPayload)
    assert isinstance(replacement.payload, MarkPayload)
    assert first_mark.payload.index == 1
    assert replacement.payload.index == 2


def test_sink_is_called_with_the_appended_entry() -> None:
    store = MissionMemory()
    seen: list[object] = []
    store.set_sink(seen.append)
    entry = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=_fired_on_payload(),
    )
    assert seen == [entry]


# --- single construction site -------------------------------------------


def test_entry_is_constructed_in_exactly_one_place_in_store_py() -> None:
    """`append()` is the plan's named single construction site for a
    *live* `Entry` -- grepped, not counted by eye, per the `BL-B71` lesson
    the plan explicitly transfers here."""
    text = (_SRC / "store.py").read_text()
    hits = re.findall(r"\bEntry\(", text)
    assert len(hits) == 1, (
        f"expected exactly one `Entry(` construction in store.py (inside "
        f"append()), found {len(hits)}"
    )


def test_admission_and_marks_never_construct_entry_directly() -> None:
    """`admission.py`/`marks.py` must go through `store.append`, never
    build an `Entry` themselves -- the same obligation, checked at the two
    call sites that will exist once Stage 2/3 land, so a future author
    bypassing `append` fails a test rather than a review."""
    for name in ("admission.py", "marks.py"):
        path = _SRC / name
        if not path.exists():
            continue
        text = path.read_text()
        assert "Entry(" not in text, f"{name} constructs Entry() directly"
