"""Every recognised transcript, and what Petrovich did about it.

`--speech-log PATH`, answering the question the inbound-speech chain could
not answer at all before: **what did he hear, and why did nothing happen?**

Until this existed, an utterance that matched no command fell through to
escalation, and the default brain client does nothing — so the single most
useful case for debugging recognition left no trace anywhere. With
`--brain-client debug` the payload reached stderr, scrolled past, and was
gone. Matched utterances were no better off: a false fire (something
executing that the pilot did not say) was only visible as the readback
itself, with no record of the transcript that caused it.

Deliberately **not** part of `--detection-trace`. That file answers "why
did he not see that" and is joined against ground truth per poll per
object; this one answers "why did he not hear that" and is one row per
utterance. Merging them would make both harder to read and neither easier
to write.

Sits beside `logger.py` rather than inside `belief/`, the same placement
and for the same reason as `detection_trace_writer.py`: no package gains an
import because a debug artifact exists.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class SpeechLogWriter:
    """Appends one JSON line per recognised transcript.

    Unbuffered, unlike `DetectionTraceWriter`'s five-poll buffer: speech is
    a handful of rows per sortie rather than hundreds per poll, and the
    thing most worth logging is the utterance immediately before something
    went wrong — which a buffer would still be holding when the process was
    killed to investigate.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, row: dict[str, Any]) -> None:
        """Write one row, stamped with wall-clock time.

        `t_wall` is added here rather than taken from the caller so the
        file is orderable even when `now_sim` stalls — a paused mission
        keeps its sim clock still, and two utterances a minute apart would
        otherwise be indistinguishable.
        """
        stamped = {"t_wall": time.time(), **row}
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(stamped, default=str) + "\n")
