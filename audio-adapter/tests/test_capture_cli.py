"""`audio_adapter.capture`'s poll-rate resolution.

`main()` itself is a live-process entrypoint (untested by design, same
posture as `__main__.py` -- see `audio-adapter/CLAUDE.md`'s "Testing"
section), but the per-source default poll rate is ordinary decision logic
factored into `_resolve_poll_hz`, which is exactly the kind of thing that
belongs in a test rather than behind an entrypoint's exemption.

The regression this guards against: `--ptt dcs` polls a collector sharing a
box with DCS over HTTP, and `ptt_source.DEFAULT_DCS_POLL_HZ` documents 30 Hz
as the deliberate tradeoff for that hop. `key`/`joystick` are local reads
with no network cost, so they keep the faster flat default. An explicit
`--poll-hz` must win for every source -- the easy way to reintroduce this
bug is to resolve the default by mutating the parser per `--ptt` value
instead of resolving it once after parsing.
"""

from __future__ import annotations

from audio_adapter.capture import (
    DEFAULT_LOCAL_POLL_HZ,
    _build_parser,
    _resolve_poll_hz,
)
from ptt_source import DEFAULT_DCS_POLL_HZ


def test_dcs_default_is_the_slow_documented_rate() -> None:
    assert _resolve_poll_hz("dcs", None) == DEFAULT_DCS_POLL_HZ


def test_key_default_is_the_fast_local_rate() -> None:
    assert _resolve_poll_hz("key", None) == DEFAULT_LOCAL_POLL_HZ


def test_joystick_default_is_the_fast_local_rate() -> None:
    assert _resolve_poll_hz("joystick", None) == DEFAULT_LOCAL_POLL_HZ


def test_explicit_poll_hz_overrides_dcs_default() -> None:
    assert _resolve_poll_hz("dcs", 5.0) == 5.0


def test_explicit_poll_hz_overrides_local_default() -> None:
    assert _resolve_poll_hz("key", 5.0) == 5.0


def test_parser_default_poll_hz_is_none() -> None:
    """`--poll-hz` must default to `None` on the parser itself -- the
    per-source default is resolved after parsing, not by mutating the
    parser's default per `--ptt` value."""
    args = _build_parser().parse_args(["--ptt", "dcs"])
    assert args.poll_hz is None


def test_explicit_poll_hz_flag_is_parsed() -> None:
    args = _build_parser().parse_args(["--ptt", "dcs", "--poll-hz", "12.5"])
    assert args.poll_hz == 12.5
