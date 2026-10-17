"""The JSONL sink -- `--mission-memory PATH`. Same posture as `speech_log.
SpeechLogWriter`: unbuffered (one `open(..., "a")` per write), and a write
failure is reported once, then this writer gives up for the rest of the
run -- mission-memory entries are a handful to a few dozen per sortie
(plan's "Risks & Unknowns": ~3600 in a worst-case two-hour sortie at the
tightest `RESIGHT_MIN_INTERVAL_S`), nowhere near detection-trace volumes,
so there is no buffering cost to amortise and every row is worth not
losing to a crash mid-write."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mission_memory.entries import Entry, encode_entry


class MissionMemoryLogWriter:
    """Appends one JSON line per mission-memory entry."""

    def __init__(self, path: Path) -> None:
        self._path = path
        #: Set after the first write failure -- see `write`.
        self._disabled = False

    def write(self, entry: Entry) -> None:
        """Write one row. A write failure is reported once on `stderr`,
        then this writer silently no-ops for the rest of the run -- a
        logging failure must never propagate back into `store.
        MissionMemory.append`, which has already fully decided and
        recorded the entry in memory by the time this is called."""
        if self._disabled:
            return
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(encode_entry(entry), default=str) + "\n")
        except OSError as exc:
            self._disabled = True
            print(
                f"mission-memory: write to {self._path} failed ({exc}); "
                f"no further entries will be logged this run",
                file=sys.stderr,
            )
