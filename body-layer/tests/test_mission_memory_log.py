"""`mission_memory.log.MissionMemoryLogWriter` -- round trip, and the
disable-once-and-report write-failure policy shared with `speech_log.
SpeechLogWriter`/`detection_trace_writer.DetectionTraceWriter`."""

from __future__ import annotations

import json
from pathlib import Path

from mission_memory.entries import FiredOnPayload, decode_entry
from mission_memory.log import MissionMemoryLogWriter
from mission_memory.store import MissionMemory


def test_write_appends_one_json_line(tmp_path: Path) -> None:
    path = tmp_path / "mission_memory.jsonl"
    writer = MissionMemoryLogWriter(path)
    store = MissionMemory()
    store.set_sink(writer.write)
    entry = store.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=FiredOnPayload(
            shooter_seq=None, shooter_ref="CONTACT_1", targets_ownship=True
        ),
    )
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    decoded = decode_entry(json.loads(lines[0]))
    assert decoded == entry


def test_a_write_failure_is_reported_once_then_abandoned(tmp_path: Path) -> None:
    """Pointing the writer at a directory makes every `open(..., "a")`
    raise `IsADirectoryError` (an `OSError` subclass) -- the real shape of
    a disk-full/unwritable-path failure, with no monkeypatching needed."""
    writer = MissionMemoryLogWriter(tmp_path)
    for i in range(3):
        writer.write(
            MissionMemory().append(
                kind="fired_on",
                provenance="observed",
                t_sim=float(i),
                phase=None,
                pos=None,
                seen=None,
                belief_ref="CONTACT_1",
                strikes=None,
                payload=FiredOnPayload(
                    shooter_seq=None, shooter_ref="CONTACT_1", targets_ownship=True
                ),
            )
        )
    assert writer._disabled is True


def test_disabled_writer_stops_opening_the_path(tmp_path: Path) -> None:
    """Once disabled, `write` must not even attempt a second `open` --
    checked by a writer whose path is a real file so a second attempt
    would otherwise succeed and mask the guard."""
    path = tmp_path / "mission_memory.jsonl"
    writer = MissionMemoryLogWriter(path)
    writer._disabled = True
    writer.write(
        MissionMemory().append(
            kind="fired_on",
            provenance="observed",
            t_sim=1.0,
            phase=None,
            pos=None,
            seen=None,
            belief_ref="CONTACT_1",
            strikes=None,
            payload=FiredOnPayload(
                shooter_seq=None, shooter_ref="CONTACT_1", targets_ownship=True
            ),
        )
    )
    assert not path.exists()
