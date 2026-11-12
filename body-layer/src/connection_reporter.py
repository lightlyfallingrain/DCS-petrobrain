"""`ConnectionReporter`: one line when a dependency goes away, one when it
comes back, and nothing in between.

Originally `body.py`'s own `_ConnectionReporter`, private to that module,
for the aircraft-layer disconnect case (the poll loop retries every
`poll_interval_s`, so an unreachable collector used to print a fresh
traceback every second for as long as it stayed down -- thousands of
identical stack traces burying anything real; the pilot needs to know the
state changed, not to be told the same fact once a second, user direction
2026-10-02). Promoted to this shared, top-level module by `plans/
default-crew-pipeline/plan.md` (BL-B96 Stage 4) so `belief.crew_console.
CrewConsole`'s speech-push path and `body.py`'s own transcript-poll path
can share one instance -- and therefore one `_connected` state -- for the
audio-adapter-unreachable case, without `body.py` and `belief.crew_console`
importing each other (the former already imports the latter; a reverse
import would be circular).

**`logger` is a required constructor argument, not `logging.getLogger(
__name__)` resolved inside this module**, specifically so every
`ConnectionReporter` logs through whichever module's logger
`_configure_logger_for_main()` actually configured -- `body.py`'s own
`logger`, for both the aircraft-layer and the audio-adapter reporter.
A reporter built in `belief.crew_console` using *that* module's own
logger would fall back to `logging.lastResort` (`WARNING` threshold)
for its `report_success()`'s `INFO` line, the exact silently-dropped-log
defect `plans/bl11-stage4-fail-closed/dod-check.md` fixed for the
aircraft-layer case -- reintroducing it for audio-adapter would be the
same bug under a different name.

**`[[BL-B106]]` (`plans/async-speech/plan.md`'s "Refresh" section)
gives this a second caller on a second thread**: the audio-adapter
reporter is now also read/written by `belief.speech_worker.SpeechWorker`'s
background worker thread (the former `CrewConsole._print`-side
`report_failure`/`report_success` calls moved there), alongside
`body._poll_transcripts`'s existing poll-thread calls. The race this
opens (interleaved `_connected` reads/writes from two threads) is benign
either way -- at worst one duplicated transition line -- but the lock
below is three lines and removes the question rather than leaving two
threads mutating `_connected` with no synchronisation at all.
"""

from __future__ import annotations

import logging
import threading


class ConnectionReporter:
    """One line when the dependency goes away, one when it comes back,
    and nothing in between.

    State is tri-valued on purpose: `None` means nothing has been reported
    yet, so the first successful call announces "connected" rather than
    staying silent on the grounds that nothing broke.
    """

    def __init__(self, logger: logging.Logger, label: str = "aircraft layer") -> None:
        self._logger = logger
        self._label = label
        self._connected: bool | None = None
        self._lock = threading.Lock()

    def report_failure(self, exc: BaseException) -> None:
        """Log `disconnected` on the transition only; later failures are
        silent until a success resets the state."""
        with self._lock:
            if self._connected is False:
                return
            self._connected = False
        self._logger.warning("%s disconnected (%s)", self._label, exc)

    def report_success(self) -> None:
        """Log `connected` on the transition, including the first one."""
        with self._lock:
            if self._connected is True:
                return
            self._connected = True
        self._logger.info("%s connected", self._label)
