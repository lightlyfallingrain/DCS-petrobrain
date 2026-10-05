"""Tests for `run_log_paths` and `logger._per_run_log_paths` -- `BL-11`
Stage 5's per-run log filenames.

Both halves are tested: the pure stamping helper, and the wiring that
applies it to the three log paths at once. The wiring is the part with a
real decision in it (one stamp for all three, `None` passing through), and
a tested pure function with an untested call site is how a correct helper
still ships a broken feature.
"""

from __future__ import annotations

import time
from pathlib import Path

import logger as logger_module
from run_log_paths import RUN_STAMP_FORMAT, per_run_log_path, run_stamp

#: 2026-10-06 14:35:00 local time, as epoch seconds -- built through
#: `mktime` rather than hardcoded so the test is timezone-independent.
_WHEN = time.mktime((2026, 10, 6, 14, 35, 0, 0, 0, -1))
_STAMP = "20261006-143500"


def test_run_stamp_renders_the_documented_format() -> None:
    assert run_stamp(_WHEN) == _STAMP
    assert time.strftime(RUN_STAMP_FORMAT, time.localtime(_WHEN)) == _STAMP


def test_per_run_log_path_inserts_the_stamp_before_the_suffix() -> None:
    assert per_run_log_path(Path("logs/trace.jsonl"), _WHEN) == Path(
        f"logs/trace-{_STAMP}.jsonl"
    )


def test_per_run_log_path_keeps_the_directory_exactly_as_given() -> None:
    """It renames the file, never relocates it -- a user who pointed an
    explicit flag at a big disk still writes to that disk."""
    rolled = per_run_log_path(Path("/big/disk/dcs-detection-trace.jsonl"), _WHEN)

    assert rolled.parent == Path("/big/disk")
    assert rolled.name == f"dcs-detection-trace-{_STAMP}.jsonl"


def test_per_run_log_path_handles_a_suffixless_path() -> None:
    assert per_run_log_path(Path("trace"), _WHEN) == Path(f"trace-{_STAMP}")


def test_per_run_log_path_does_not_collide_with_the_original() -> None:
    """The point of the stamp: two runs against one configured path write
    two files, and neither is the path as configured."""
    original = Path("logs/trace.jsonl")

    assert per_run_log_path(original, _WHEN) != original
    assert per_run_log_path(original, _WHEN) != per_run_log_path(
        original, _WHEN + 3600.0
    )


def test_all_three_logs_share_one_stamp() -> None:
    """A sortie's three logs must be recognisable as one set. Taking the
    stamp per writer would produce three unrelated-looking names across a
    midnight boundary, or simply three different seconds."""
    trace, truth, speech = logger_module._per_run_log_paths(
        detection_trace=Path("logs/trace.jsonl"),
        belief_truth_log=Path("logs/truth.jsonl"),
        speech_log=Path("logs/speech.jsonl"),
        when=_WHEN,
    )

    assert trace == Path(f"logs/trace-{_STAMP}.jsonl")
    assert truth == Path(f"logs/truth-{_STAMP}.jsonl")
    assert speech == Path(f"logs/speech-{_STAMP}.jsonl")


def test_unset_log_paths_stay_none() -> None:
    """All three logs are off by default, so `None` must survive the roll
    rather than becoming a path that then gets opened."""
    assert logger_module._per_run_log_paths(
        detection_trace=None,
        belief_truth_log=None,
        speech_log=None,
        when=_WHEN,
    ) == (None, None, None)


def test_a_single_configured_log_rolls_without_inventing_the_others() -> None:
    trace, truth, speech = logger_module._per_run_log_paths(
        detection_trace=None,
        belief_truth_log=Path("truth.jsonl"),
        speech_log=None,
        when=_WHEN,
    )

    assert trace is None
    assert speech is None
    assert truth == Path(f"truth-{_STAMP}.jsonl")
