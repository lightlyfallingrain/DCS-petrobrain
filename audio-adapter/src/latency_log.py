"""`--latency-log PATH` -- one JSONL row per timed stage of the voice
round trip this process participates in (`plans/
voice-latency-instrumentation/plan.md`): a capture clip posted
(`stage: "capture"`), a transcription attempt (`stage: "transcribe"`), a
synthesis+delivery attempt (`stage: "speak"`). Joined with body-layer's
`--speech-log`/`--belief-truth-log` by `correlation_id` via
`body-layer/tools/join_voice_latency.py` -- this file on its own is one
process's view of its own durations, never the whole chain.

Structurally copied from `body-layer/src/speech_log.py`'s `SpeechLogWriter`
(same unbuffered-write, auto-stamped-`t_wall`, disable-after-first-failure
shape) rather than inventing a second JSONL idiom in this subproject --
`audio-adapter` has no existing log writer of its own to reuse instead.
Stdlib only (`json`, `time`, `pathlib`), consistent with this subproject's
dependency policy."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


class LatencyLogWriter:
    """Appends one JSON line per timed stage. Unbuffered -- these rows are
    a handful per clip, not per poll, and the one most worth having is the
    one immediately before something went wrong."""

    def __init__(self, path: Path) -> None:
        self._path = path
        #: Set after the first write failure -- see `write`.
        self._disabled = False

    def write(self, row: dict[str, Any]) -> None:
        """Write one row, stamped with wall-clock time.

        `t_wall` is added here rather than taken from the caller, the same
        reason `SpeechLogWriter.write` does it: the file stays orderable
        even across stages run by different processes on different
        machines, each with their own (possibly skewed) clock -- the
        monotonic-derived duration fields in `row` are what the reducer
        trusts; `t_wall` is ordering/context only.

        **A write failure is reported once, then this writer gives up for
        the rest of the run**, the same policy `SpeechLogWriter`/
        `DetectionTraceWriter`/`belief_truth_log.BeliefTruthLogWriter`
        already share -- a logging failure must never be the reason a clip
        is not posted or a line is not spoken, so callers never see this
        raise."""
        if self._disabled:
            return
        stamped = {"t_wall": time.time(), **row}
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(stamped, default=str) + "\n")
        except OSError as exc:
            self._disabled = True
            print(
                f"latency-log: write to {self._path} failed ({exc}); "
                f"no further rows will be logged this run",
                file=sys.stderr,
            )
