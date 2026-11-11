"""`--expected-area-log PATH`, `plans/expected-area-look/plan.md` Pass 3 --
one JSONL row per `belief.expected_area` check *opened* and one per
*verdict* `resolve_checks` actually reaches, read by `body._resolve_
expected_area_checks`'s own call site.

**Why this exists, rather than the `logging` module calls Pass 2 already
added staying the only record.** Pass 2 built `logger.debug`/`logger.info`
lines for check-open/verdict (`implementation.md`, "Not built as
specified"), explicitly flagging that neither fits `perception.
detection_trace.DetectionTrace` (ground-truth-only by construction, no
`belief/` import at all, per that module's own docstring) nor `belief_
truth_log.BeliefTruthRow` (every row requires a *matched ground-truth
object* -- `object_id`, true bearing/range -- which an expected-area check
never has; it is a belief-only state transition over a remembered place,
not a detection). Neither of the other two sortie logs (`dcs-belief-truth`,
`dcs-speech`) fits for the same reason: this project's own "no omniscience"
boundary (`body-layer/CLAUDE.md`'s Invariants) keeps ground-truth-joined
and belief-only data in separate files by construction, and a voice-
transcript log has nothing to do with a binocular check at all. Standard
`logging` output is real but goes to stderr/stdout, not a file
`sortie-log-triage` can resolve and reduce -- so the plan's own "the
trigger rate in flight is unmeasured" risk (its top-listed one) stayed
genuinely unobservable from a flown sortie's artifacts.

**The closest existing pattern, not a new one**: this is the *seventh*
per-run JSONL log (`run_log_paths`'s three, plus `--group-trace`/
`--mission-memory`/`--slew-trace`, each its own sibling `_resolve_*_log_
path` function and `_reroll_run_logs` branch) -- same unbuffered,
self-disabling-on-write-failure shape as `GroupTraceLogWriter`, which this
module is a near-literal copy of rather than a redesign. Defaults off
(`--expected-area-log` absent is a true no-op), same posture as every
other per-run debug log.

Unbuffered for the same reason `GroupTraceLogWriter`/`SpeechLogWriter` are:
the row most worth having is the one immediately before a wrong verdict,
which a buffer would still be holding when the process was killed to
investigate. Volume is tiny by construction -- at most `belief.
expected_area.MAX_OPEN_CHECKS` (2) checks open at once, one open-row per
open check per poll plus one verdict-row per check that resolves that
poll -- nowhere near `DetectionTraceWriter`'s per-candidate-per-poll
volume, so buffering would save nothing worth the risk.

Sits beside `body.py` rather than inside `belief/`, the same placement and
for the same reason as `group_trace_log.py`/`speech_log.py`: no package
gains an import because a debug artifact exists."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Mapping
from pathlib import Path


class ExpectedAreaLogWriter:
    """Appends one JSON line per expected-area check open/verdict record.

    See the module docstring for why this exists and why it is unbuffered.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        #: Set after the first write failure -- see `write`.
        self._disabled = False

    def write(self, row: Mapping[str, object]) -> None:
        """Write one row, stamped with wall-clock time -- `t_wall` added
        here rather than taken from the caller, the same choice `Group
        TraceLogWriter.write`/`SpeechLogWriter.write` make and for the
        same reason: the file stays orderable even when `now_sim` stalls
        (a paused mission keeps its sim clock still).

        **A write failure is reported once, then this writer gives up for
        the rest of the run** (`BL-11` Stage 5's policy, applied here to
        the seventh writer) -- the caller (`body._resolve_expected_area_
        checks`) must not let a failed write propagate into the poll loop,
        the same posture every other per-run log writer already takes."""
        if self._disabled:
            return
        stamped = {"t_wall": time.time(), **row}
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(stamped, default=str) + "\n")
        except OSError as exc:
            self._disabled = True
            print(
                f"expected-area-log: write to {self._path} failed ({exc}); "
                f"no further expected-area-log records will be logged this run",
                file=sys.stderr,
            )
