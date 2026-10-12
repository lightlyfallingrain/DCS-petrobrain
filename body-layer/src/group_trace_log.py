"""`--group-trace PATH`, the sortie-observable half of `BL-12`'s amendment
A4: one JSONL row per `belief.groups.GroupStore.reconcile` resolution
outcome (`phase` in `overlap`/`property`/`found`), plus one per group that
actually expires that call (`phase = "expired"`).

Until this existed, a live sortie produced zero evidence of a phase-2
property match ever having happened — the trace fields
(`GroupStore.reconcile`'s `trace_sink` keyword, built in Stage 1) were real
and tested, but nothing on the CLI side called them. That left D5's rarity
claim ("it's the unusual occurrence") and `BL-B50`'s lapse condition
("blocking-priority if a sortie log shows membership flipping on
consecutive ticks") both unevaluable from an actual flight — the only
available evidence was a wrong spoken line in the cockpit, which is exactly
the failure class this project tries to catch from a log instead
(`plans/group-contact-identity/plan.md` amendment A4, reasons 1/3/4).

Sits beside `logger.py` rather than inside `belief/`, the same placement
and for the same reason as `speech_log.py`/`detection_trace_writer.py`: no
package gains an import because a debug artifact exists.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Mapping
from pathlib import Path


class GroupTraceLogWriter:
    """Appends one JSON line per group-identity trace record.

    Unbuffered, mirroring `SpeechLogWriter` rather than
    `DetectionTraceWriter`'s five-poll buffer. The unbuffered choice is for
    the usual reason -- the row most worth having is the one immediately
    before a wrong spoken line, which a buffer would still be holding when
    the process was killed to investigate -- but the frequency it is
    weighed against is not rare: `GroupStore.reconcile`'s `trace_sink`
    fires once per active cluster on **every** reconcile call when
    `--group-trace` is on, not only on the occasional phase-2 property
    match or expiry (see `reconcile`'s own docstring: "once per cluster-
    resolution outcome... and once per group that expires this call").
    Measured at realistic scale (4-15 tracked clusters, ~1 Hz polling):
    ~0.03 ms per write, ~0.14-0.51 ms per poll, against a 12.6 ms median
    poll and a 1.0 s budget -- immaterial, so unbuffered is still the
    right call, but on "every cluster, every poll," not "a handful per
    sortie." With no `--group-trace` (the default), nothing here runs at
    all -- a true no-op.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        #: Set after the first write failure -- see `write`.
        self._disabled = False

    def write(self, row: Mapping[str, object]) -> None:
        """Write one row, stamped with wall-clock time.

        `t_wall` is added here rather than taken from the caller, the same
        choice `SpeechLogWriter.write` makes and for the same reason: the
        file stays orderable even when `now_sim` stalls (a paused mission
        keeps its sim clock still).

        **A write failure is reported once, then this writer gives up for
        the rest of the run** (`BL-11` Stage 5's policy, applied here to a
        fourth writer). `ContactStore.tick`'s `group_trace_sink` call is
        not wrapped in a caller-side try/except the way `CrewConsole.
        _log_transcript` wraps `SpeechLogWriter`, so this writer must not
        let a failed write propagate into the poll loop -- a logging
        failure must never cost the sortie its belief tick.
        """
        if self._disabled:
            return
        stamped = {"t_wall": time.time(), **row}
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(stamped, default=str) + "\n")
        except OSError as exc:
            self._disabled = True
            print(
                f"group-trace: write to {self._path} failed ({exc}); "
                f"no further group-trace records will be logged this run",
                file=sys.stderr,
            )
