"""Tests for `run_log_paths` and `logger._per_run_log_paths` -- `BL-11`
Stage 5's per-run log filenames.

Both halves are tested: the pure stamping helper, and the wiring that
applies it to the three log paths at once. The wiring is the part with the
real decisions in it (one stamp for all three, `None` passing through, and
the parent directory created or that one log disabled), and a tested pure
function with an untested call site is how a correct helper still ships a
broken feature.

The wiring tests use `tmp_path` rather than relative paths because
`_per_run_log_paths` creates directories: a bare `logs/trace.jsonl` here
would leave an untracked `logs/` wherever pytest happened to be started.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

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


def test_all_three_logs_share_one_stamp(tmp_path: Path) -> None:
    """A sortie's three logs must be recognisable as one set. Taking the
    stamp per writer would produce three unrelated-looking names across a
    midnight boundary, or simply three different seconds.

    Rooted in `tmp_path` rather than a bare relative `logs/` because
    `_per_run_log_paths` now creates each parent directory: a relative path
    here would make the suite deposit an untracked `logs/` in whatever
    directory pytest was started from, and the repo root does not gitignore
    one."""
    logs = tmp_path / "logs"
    trace, truth, speech = logger_module._per_run_log_paths(
        detection_trace=logs / "trace.jsonl",
        belief_truth_log=logs / "truth.jsonl",
        speech_log=logs / "speech.jsonl",
        when=_WHEN,
    )

    assert trace == logs / f"trace-{_STAMP}.jsonl"
    assert truth == logs / f"truth-{_STAMP}.jsonl"
    assert speech == logs / f"speech-{_STAMP}.jsonl"


def test_unset_log_paths_stay_none() -> None:
    """All three logs are off by default, so `None` must survive the roll
    rather than becoming a path that then gets opened."""
    assert logger_module._per_run_log_paths(
        detection_trace=None,
        belief_truth_log=None,
        speech_log=None,
        when=_WHEN,
    ) == (None, None, None)


def test_a_single_configured_log_rolls_without_inventing_the_others(
    tmp_path: Path,
) -> None:
    trace, truth, speech = logger_module._per_run_log_paths(
        detection_trace=None,
        belief_truth_log=tmp_path / "truth.jsonl",
        speech_log=None,
        when=_WHEN,
    )

    assert trace is None
    assert speech is None
    assert truth == tmp_path / f"truth-{_STAMP}.jsonl"


def test_the_resolved_parent_directory_is_created(tmp_path: Path) -> None:
    """The run scripts pass `logs/dcs-*.jsonl`, and `logs/` is gitignored
    and so absent in a fresh clone. Nothing else creates it:
    `per_run_log_path` only renames, and both writers `open(path, "a")`
    unguarded -- so without this the crew dies at startup with a
    `FileNotFoundError` raised before either writer's own write-failure
    reporting can say anything."""
    logs = tmp_path / "logs" / "nested"
    assert not logs.exists()

    trace, truth, speech = logger_module._per_run_log_paths(
        detection_trace=logs / "trace.jsonl",
        belief_truth_log=logs / "truth.jsonl",
        speech_log=logs / "speech.jsonl",
        when=_WHEN,
    )

    assert logs.is_dir()
    # And the paths are genuinely openable in append mode, which is what
    # the writers do -- the directory existing is the means, not the claim.
    for path in (trace, truth, speech):
        assert path is not None
        with path.open("a"):
            pass


def test_an_uncreatable_directory_disables_only_that_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unwritable log costs the sortie its trace, not its crew -- the
    same degrade `_resolve_speech_log_path` already applies to the default
    speech log. Here the parent is blocked by an existing *file* of that
    name, which is the cheapest real `OSError` to arrange."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")

    trace, truth, speech = logger_module._per_run_log_paths(
        detection_trace=blocker / "trace.jsonl",
        belief_truth_log=tmp_path / "ok" / "truth.jsonl",
        speech_log=None,
        when=_WHEN,
    )

    assert trace is None
    assert truth == tmp_path / "ok" / f"truth-{_STAMP}.jsonl"
    assert speech is None
    assert "detection-trace: could not create log directory" in capsys.readouterr().err
