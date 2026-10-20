"""Post-flight reducer joining the voice chain's logs by correlation id
(`plans/voice-latency-instrumentation/plan.md` Stage 5) -- the actual
"locate the delay" deliverable this plan exists to produce, and the answer
to the 2026-10-20 sortie's "set target" finding: *"the real problem here is
the many second delay."*

Not a test -- a dev/pilot post-flight aid, mirroring
`summarize_detection_trace.py`'s own "reducer, not a test" posture. Raw
JSONL across three-to-five separate files (capture's own `--latency-log`,
audio-adapter's own `--latency-log`, body-layer's `--speech-log` and
`--belief-truth-log`) is not meant to be read directly; this joins them by
`correlation_id` into one ordered timeline per utterance.

**How to read one timeline.** Stages print in a *fixed pipeline order* --
`capture` (PTT release -> posted to audio-adapter) -> `transcribe`
(whisper + command match) -> `transcript` (body-layer's dispatch decision:
act/confirm/say-again/fallthrough) -> `spoken` (body-layer pushes the
chosen line to `/speak`) -> `speak` (audio-adapter synthesizes and
delivers) -- **never by comparing each row's own `t_wall`**, because this
chain crosses a Mac/Windows machine boundary with no shared clock (the
plan's own "What the investigation found": "a bare wall-clock subtraction
across two of these logs is not trustworthy"). `t_wall` only breaks ties
*within* one stage, where it is the same process's own clock.

**Which numbers to trust.** Every `*_duration_s` field was measured by one
process's own `time.monotonic()` bracketed around one call -- these are
the trustworthy numbers, and this tool never subtracts two different
processes' `t_wall` values to manufacture an end-to-end total (that would
quietly reintroduce the false-precision problem this project already
avoids elsewhere). What this tool prints instead, per timeline, is each
stage's own measured duration(s) and nothing stitched between them. The
dominant stretch this cannot measure at all, per the plan's own "Risks &
Unknowns", is how long a recognised transcript sits in audio-adapter's
queue before body-layer's poll drains it -- there is no field for it
anywhere in these logs, only the poll interval (~1s default) as a known
upper bound; if a timeline's `transcribe`-to-`transcript` stretch looks
large, that queue dwell is the first thing to suspect, not a number this
tool will ever show you directly.

**A stage that never arrives is flagged, not silently absent** -- a
`correlation_id` missing one of the five stages above prints a
"never reached: <stage>" line, since that is itself diagnostic (a clip
that was never posted, a transcript that never matched, a `/speak` call
that never happened because the channel stayed deferred).

Usage (run from `body-layer/`, no world-model/pyproj dependency):

    python tools/join_voice_latency.py \\
        --latency-log capture-latency.jsonl --latency-log adapter-latency.jsonl \\
        --speech-log dcs-speech-20261020-162158.jsonl \\
        --belief-truth-log belief_truth-20261020-162158.jsonl

Any of the three flags may be repeated (capture and audio-adapter server
each write their own `--latency-log` file; a sortie that restarted the
mission mid-process rolls `--speech-log`/`--belief-truth-log` to fresh
stamped filenames -- `RUN.md`) and any may be omitted (a timeline is built
from whichever logs are actually available, with the missing stages
flagged exactly as an unreached stage would be).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Lines `_iter_jsonl` could not parse as JSON this run, as `"path:line"`
#: strings -- `BL-B88` (security deep analysis, `plans/
#: voice-latency-instrumentation/security-review.md`, 2026-10-20). The
#: realistic trigger is a process killed mid-write (a DCS crash, a mission
#: reload, a power-cycle), which truncates exactly the last line of
#: whichever file was open -- this must cost that one line, not the whole
#: reducer run, since the tool is most likely to be reached for immediately
#: after the kind of event that produces one. Module-level rather than
#: threaded through every loader's return type, so `load_latency_log`/
#: `load_speech_log`/`load_belief_truth_log` keep their existing
#: `list[_Row]`-only signature (their own tests call them directly);
#: `main` resets this list before loading anything and reports its count
#: in its own closing summary line.
_malformed_lines: list[str] = []

#: Fixed pipeline order -- see module docstring for why this is not
#: inferred from `t_wall`. A row's own stage places it in this list;
#: ties within one stage (same file, same process, same clock) break by
#: `t_wall` ascending.
_STAGE_ORDER: tuple[str, ...] = (
    "capture",
    "transcribe",
    "transcript",
    "spoken",
    "speak",
)
_STAGE_INDEX: dict[str, int] = {name: i for i, name in enumerate(_STAGE_ORDER)}


@dataclass(frozen=True)
class _Row:
    """One stage's own row, tagged with which source file it came from --
    kept for provenance when a timeline pulls from several machines'
    worth of logs copied to one place after the flight."""

    stage: str
    source: str
    t_wall: float | None
    fields: dict[str, Any]


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    """One JSON object per non-blank line. A line that fails to parse (a
    process killed mid-write truncates exactly the last line of whichever
    file was open) is skipped, warned about on stderr with its file and
    line number, and recorded in `_malformed_lines` -- it must cost one
    row, not every row in every file this run (`BL-B88`)."""
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                location = f"{path}:{line_number}"
                _malformed_lines.append(location)
                print(
                    f"warning: skipping malformed JSON line at {location}: {exc}",
                    file=sys.stderr,
                )
    return records


def load_latency_log(path: Path) -> list[_Row]:
    """A `--latency-log` file (capture's own, or audio-adapter server's
    own) -- both write the same row shape (`stage`/`correlation_id`/
    `outcome`/`t_wall` plus whichever durations that stage measured), so
    one loader covers either source regardless of which process wrote it."""
    rows = []
    for raw in _iter_jsonl(path):
        stage = str(raw.get("stage", "?"))
        t_wall = raw.get("t_wall")
        rows.append(
            _Row(
                stage=stage,
                source=str(path),
                t_wall=float(t_wall) if isinstance(t_wall, (int, float)) else None,
                fields=raw,
            )
        )
    return rows


def load_speech_log(path: Path) -> list[_Row]:
    """A `--speech-log` file -- every recognised transcript and what
    body-layer decided to do about it (`act`/`confirm`/`say_again`/
    `fallthrough`). One row is this chain's "dispatch decision" stage."""
    rows = []
    for raw in _iter_jsonl(path):
        t_wall = raw.get("t_wall")
        rows.append(
            _Row(
                stage="transcript",
                source=str(path),
                t_wall=float(t_wall) if isinstance(t_wall, (int, float)) else None,
                fields=raw,
            )
        )
    return rows


def load_belief_truth_log(path: Path) -> list[_Row]:
    """A `--belief-truth-log` file -- only its `kind: "speech"` rows are
    relevant here (every other row is a ground-truth/belief comparison,
    not part of the voice chain). This is the "body-layer pushed a line to
    `/speak`" stage, carrying the `push_speech` call's own measured
    round-trip duration."""
    rows = []
    for raw in _iter_jsonl(path):
        if raw.get("kind", "belief_truth") != "speech":
            continue
        rows.append(_Row(stage="spoken", source=str(path), t_wall=None, fields=raw))
    return rows


def group_by_correlation_id(rows: list[_Row]) -> dict[str, list[_Row]]:
    """Rows with no `correlation_id` (an older process, a direct `curl`, or
    a push-lane line with no voice origin -- callouts, attack-run guidance)
    cannot be joined to anything and are silently excluded here; `main`
    reports their count separately so they are not simply lost from view."""
    groups: dict[str, list[_Row]] = defaultdict(list)
    for row in rows:
        correlation_id = row.fields.get("correlation_id")
        if isinstance(correlation_id, str) and correlation_id:
            groups[correlation_id].append(row)
    return dict(groups)


def _sort_key(row: _Row) -> tuple[int, float]:
    return _STAGE_INDEX.get(row.stage, len(_STAGE_ORDER)), row.t_wall or 0.0


def _format_row(row: _Row) -> str:
    fields = row.fields
    if row.stage == "capture":
        return (
            f"  capture    outcome={fields.get('outcome')!r} "
            f"clip_duration_s={fields.get('clip_duration_s')} "
            f"post_duration_s={fields.get('post_duration_s')} "
            f"t_ptt_release_wall={fields.get('t_ptt_release_wall')}"
        )
    if row.stage == "transcribe":
        return (
            f"  transcribe outcome={fields.get('outcome')!r} "
            f"transcribe_duration_s={fields.get('transcribe_duration_s')} "
            f"match_duration_s={fields.get('match_duration_s')}"
        )
    if row.stage == "transcript":
        return (
            f"  transcript heard={fields.get('transcript')!r} "
            f"disposition={fields.get('disposition')!r} "
            f"acted_token={fields.get('acted_token')!r} "
            f"now_sim={fields.get('now_sim')}"
        )
    if row.stage == "spoken":
        return (
            f"  spoken     text={fields.get('text')!r} "
            f"push_duration_s={fields.get('push_duration_s')} "
            f"t_sim={fields.get('t_sim')}"
        )
    if row.stage == "speak":
        return (
            f"  speak      outcome={fields.get('outcome')!r} "
            f"synth_duration_s={fields.get('synth_duration_s')} "
            f"deliver_duration_s={fields.get('deliver_duration_s')}"
        )
    return f"  {row.stage}  {fields!r}"  # pragma: no cover -- unrecognised stage name


def format_timeline(correlation_id: str, rows: list[_Row]) -> str:
    ordered = sorted(rows, key=_sort_key)
    lines = [f"=== {correlation_id} ==="]
    for row in ordered:
        lines.append(_format_row(row))
    seen_stages = {row.stage for row in rows}
    missing = [stage for stage in _STAGE_ORDER if stage not in seen_stages]
    if missing:
        lines.append(f"  never reached: {', '.join(missing)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--latency-log",
        type=Path,
        action="append",
        default=[],
        help="a capture or audio-adapter --latency-log file; repeatable",
    )
    parser.add_argument(
        "--speech-log",
        type=Path,
        action="append",
        default=[],
        help="a body-layer --speech-log file; repeatable",
    )
    parser.add_argument(
        "--belief-truth-log",
        type=Path,
        action="append",
        default=[],
        help="a body-layer --belief-truth-log file; repeatable",
    )
    args = parser.parse_args(argv)

    _malformed_lines.clear()  # a fresh count for this run, not carried over
    # from an earlier `main()` call in the same process (e.g. the test suite).

    rows: list[_Row] = []
    for path in args.latency_log:
        rows.extend(load_latency_log(path))
    for path in args.speech_log:
        rows.extend(load_speech_log(path))
    for path in args.belief_truth_log:
        rows.extend(load_belief_truth_log(path))

    groups = group_by_correlation_id(rows)
    unattributed = sum(
        1
        for row in rows
        if not isinstance(row.fields.get("correlation_id"), str)
        or not row.fields.get("correlation_id")
    )

    if not groups:
        print("No correlated rows found.")
    else:
        # Utterances print earliest-first, by the earliest `t_wall` any of
        # their rows carries -- ordering *between* utterances, not within
        # one (which `format_timeline` itself orders by pipeline stage).
        # An utterance with no timed row at all (every row's `t_wall` is
        # `None`) sorts last rather than first, so it cannot masquerade as
        # the earliest.
        def _earliest_wall(correlation_id: str) -> float:
            walls = [
                row.t_wall for row in groups[correlation_id] if row.t_wall is not None
            ]
            return min(walls) if walls else float("inf")

        for correlation_id in sorted(groups, key=_earliest_wall):
            print(format_timeline(correlation_id, groups[correlation_id]))
            print()

    print(
        f"{len(groups)} correlated utterance(s); {unattributed} row(s) with no id. "
        f"{len(_malformed_lines)} malformed line(s) skipped."
    )


if __name__ == "__main__":
    main()
