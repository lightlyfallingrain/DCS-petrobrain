#!/usr/bin/env python3
"""Parse aircraft_layer_debug.log (or any Export.lua-style debug log) for a
named probe pattern's samples.

Each debug_log() line in Export.lua is prefixed "HH:MM:SS " followed by
free text; debug_dump() calls can span many following lines with no
timestamp-anchored terminator of their own. This script anchors on a probe
label (e.g. "list_indication(6)", "LoGetWorldObjects()") and extracts each
occurrence's payload up to the next timestamped line, then deduplicates
and counts distinct payload bodies -- the recurring manual task from PB-1's
live-spike sessions (diffing what a probe returned across hundreds of
samples to see whether/when its value actually changed).

Usage:
    parse_dcs_log.py <log_path> <probe_label> [--first N] [--show-samples N]

Examples:
    parse_dcs_log.py aircraft_layer_debug.log "list_indication(6)"
    parse_dcs_log.py aircraft_layer_debug.log "LoGetWorldObjects()" --show-samples 3
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict

TIMESTAMP_LINE = re.compile(r"^\d\d:\d\d:\d\d ")


def _normalize_anchor_line(line: str, probe_label: str) -> str:
    """Strip the "HH:MM:SS " timestamp and the "<probe_label> #<N>" sample
    counter from an anchor line, so identical payloads at different times
    and sample indices dedup together. Only touches the first occurrence of
    "<probe_label> #<N>" -- later "#N"-shaped text elsewhere in a payload
    (e.g. a literal page number in a DCS dump) is left untouched."""
    line = TIMESTAMP_LINE.sub("", line, count=1)
    counter_pattern = re.compile(re.escape(probe_label) + r" #\d+")
    return counter_pattern.sub(probe_label, line, count=1)


def extract_samples(log_text: str, probe_label: str) -> list[tuple[str, str]]:
    """Return each occurrence as (original_text, dedup_key) pairs. The
    dedup key strips the anchor line's timestamp and sample counter (see
    `_normalize_anchor_line`) so otherwise-identical payloads compare equal
    regardless of when or which sample number they were."""
    lines = log_text.splitlines()
    samples: list[tuple[str, str]] = []
    current: list[str] | None = None

    def flush() -> None:
        if current is None:
            return
        original = "\n".join(current)
        normalized_first = _normalize_anchor_line(current[0], probe_label)
        key = "\n".join([normalized_first, *current[1:]])
        samples.append((original, key))

    for line in lines:
        is_new_timestamped_line = TIMESTAMP_LINE.match(line) is not None
        if is_new_timestamped_line:
            flush()
            current = None
            if probe_label in line:
                current = [line]
        elif current is not None:
            current.append(line)

    flush()
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log_path", help="path to the debug log file")
    parser.add_argument("probe_label", help="substring identifying the probe, e.g. 'list_indication(6)'")
    parser.add_argument("--first", type=int, default=None, help="only consider the first N matches")
    parser.add_argument("--show-samples", type=int, default=1, help="print this many full example bodies per distinct value (default 1)")
    args = parser.parse_args()

    try:
        log_text = open(args.log_path, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        print(f"error reading {args.log_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    samples = extract_samples(log_text, args.probe_label)
    if args.first is not None:
        samples = samples[: args.first]

    if not samples:
        print(f"no samples found for probe label {args.probe_label!r} in {args.log_path}")
        return

    counts: Counter[str] = Counter(key for _, key in samples)
    examples: dict[str, list[str]] = defaultdict(list)
    for original, key in samples:
        if len(examples[key]) < args.show_samples:
            examples[key].append(original)

    print(f"probe: {args.probe_label!r}")
    print(f"total samples: {len(samples)}")
    print(f"distinct bodies: {len(counts)}")
    print()

    for key, count in counts.most_common():
        for example in examples[key]:
            preview = example if len(example) < 500 else example[:500] + " ...[truncated]"
            print(f"--- count={count} ---")
            print(preview)
            print()


if __name__ == "__main__":
    main()
