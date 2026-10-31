"""Tests for `progress.format_progress`/`ThrottledProgress`/`Heartbeat` --
the shared mechanism every build stage's progress logging is migrated onto
(see `plans/osm-landcover-optimization/progress-logging.md`).

`ThrottledProgress`'s throttling is tested with an injected clock (a small
mutable counter), never real `time.sleep`, so it is deterministic. `Heartbeat`
genuinely needs a background thread and real time, so its test uses a short
interval with a generous, loose assertion (">= 1 call", not an exact count)
rather than depending on precise timing.
"""

import logging
import threading
import time

import pytest

from progress import Heartbeat, ThrottledProgress, format_progress


class _FakeClock:
    """A monotonically-advancing fake clock a test can move forward on
    demand, so `ThrottledProgress`'s interval logic can be tested without
    any real sleeping."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestFormatProgress:
    def test_basic_line_with_total_and_counters(self) -> None:
        line = format_progress(
            "ingest_srtm", elapsed_s=12.0, done=50, total=200, sampled=48, void=2
        )
        # 12s for 50/200 => 36s remaining for the other 150.
        assert line == (
            "ingest_srtm: 50/200 (25.0%, sampled=48, void=2, "
            "12s elapsed, ~36s remaining)"
        )

    def test_unknown_total_renders_question_mark_and_no_percent(self) -> None:
        line = format_progress("osm.pbf", elapsed_s=5.0, done=1000)
        assert line == "osm.pbf: 1000/? (5s elapsed)"

    def test_no_done_renders_question_mark_for_done_too(self) -> None:
        line = format_progress("stage", elapsed_s=1.0)
        assert line == "stage: ?/? (1s elapsed)"

    def test_remaining_time_is_extrapolated_from_rate(self) -> None:
        line = format_progress("ingest_srtm", elapsed_s=10.0, done=25, total=100)
        # 10s for 25/100 => 30s remaining for the other 75.
        assert "~30s remaining" in line

    def test_estimated_marks_done_total_and_percent_with_tilde(self) -> None:
        line = format_progress(
            "osm.pbf", elapsed_s=15.0, done=15.0, total=30.0, estimated=True
        )
        assert line == "osm.pbf: ~15/30 (~50.0%, 15s elapsed, ~15s remaining)"

    def test_large_counts_never_use_scientific_notation(self) -> None:
        line = format_progress("osm.pbf", elapsed_s=1.0, done=8_600_000, total=None)
        assert "8600000" in line
        assert "e+" not in line


class TestThrottledProgress:
    def test_first_call_always_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        clock = _FakeClock()
        target = logging.getLogger("test.progress.throttle1")
        reporter = ThrottledProgress(target, "stage", interval_s=30.0, clock=clock)

        with caplog.at_level(logging.INFO, logger=target.name):
            logged = reporter.maybe_log(done=1)

        assert logged is True
        assert len(caplog.records) == 1

    def test_call_before_interval_elapses_is_suppressed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = _FakeClock()
        target = logging.getLogger("test.progress.throttle2")
        reporter = ThrottledProgress(target, "stage", interval_s=30.0, clock=clock)

        with caplog.at_level(logging.INFO, logger=target.name):
            reporter.maybe_log(done=1)
            clock.advance(10.0)
            logged_again = reporter.maybe_log(done=2)

        assert logged_again is False
        assert len(caplog.records) == 1

    def test_call_after_interval_elapses_logs_again(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = _FakeClock()
        target = logging.getLogger("test.progress.throttle3")
        reporter = ThrottledProgress(target, "stage", interval_s=30.0, clock=clock)

        with caplog.at_level(logging.INFO, logger=target.name):
            reporter.maybe_log(done=1)
            clock.advance(31.0)
            logged_again = reporter.maybe_log(done=2)

        assert logged_again is True
        assert len(caplog.records) == 2

    def test_zero_interval_logs_every_call(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = _FakeClock()
        target = logging.getLogger("test.progress.throttle4")
        reporter = ThrottledProgress(target, "stage", interval_s=0.0, clock=clock)

        with caplog.at_level(logging.INFO, logger=target.name):
            for i in range(5):
                reporter.maybe_log(done=i)

        assert len(caplog.records) == 5

    def test_log_bypasses_throttle_and_resets_window(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = _FakeClock()
        target = logging.getLogger("test.progress.throttle5")
        reporter = ThrottledProgress(target, "stage", interval_s=30.0, clock=clock)

        with caplog.at_level(logging.INFO, logger=target.name):
            reporter.maybe_log(done=1)  # logs (first call)
            reporter.log(done=2)  # forced, logs regardless of throttle
            suppressed = reporter.maybe_log(done=3)  # window just reset

        assert suppressed is False
        assert len(caplog.records) == 2

    def test_total_is_threaded_through_to_the_formatted_line(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = _FakeClock()
        target = logging.getLogger("test.progress.throttle6")
        reporter = ThrottledProgress(
            target, "ingest_srtm", total=100, interval_s=30.0, clock=clock
        )

        with caplog.at_level(logging.INFO, logger=target.name):
            reporter.maybe_log(done=25, sampled=20)

        assert "25/100" in caplog.records[0].getMessage()
        assert "sampled=20" in caplog.records[0].getMessage()


class TestHeartbeat:
    def test_report_fn_is_called_at_least_once_while_running(self) -> None:
        calls: list[int] = []
        hb = Heartbeat(lambda: calls.append(1), interval_s=0.02)

        with hb:
            time.sleep(0.15)

        assert len(calls) >= 1

    def test_report_fn_stops_being_called_after_exit(self) -> None:
        calls: list[int] = []
        hb = Heartbeat(lambda: calls.append(1), interval_s=0.02)

        with hb:
            time.sleep(0.1)
        count_at_exit = len(calls)
        time.sleep(0.1)

        assert len(calls) == count_at_exit

    def test_report_fn_runs_on_a_background_thread(self) -> None:
        seen_threads: list[int] = []
        main_thread_id = threading.get_ident()

        def _report() -> None:
            seen_threads.append(threading.get_ident())

        with Heartbeat(_report, interval_s=0.02):
            time.sleep(0.08)

        assert seen_threads  # at least one tick observed
        assert all(tid != main_thread_id for tid in seen_threads)

    def test_exception_inside_with_block_still_stops_the_thread(self) -> None:
        calls: list[int] = []
        hb = Heartbeat(lambda: calls.append(1), interval_s=0.02)

        with pytest.raises(ValueError), hb:
            time.sleep(0.05)
            raise ValueError("boom")

        assert not hb._thread.is_alive()
