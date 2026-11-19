"""Turn a service's argparse `--help` output into the launcher's option list."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEAD_HELP_SPLIT = re.compile(r"\s{2,}")


@dataclass(frozen=True)
class HelpOption:
    flag: str  # the long form, e.g. "--eyesight-view"
    takes_value: bool
    help: str  # first line of the help text, "" if none


def parse_help(text: str) -> list[HelpOption]:
    """Options from argparse's option section: lines indented two spaces that start with `-`.

    Help that does not fit beside the flags starts on the next, deeper-indented line; only its
    first line is kept. `--x, --no-x` (BooleanOptionalAction) yields two on/off options.
    """
    options: list[HelpOption] = []
    pending: list[
        HelpOption
    ] = []  # options from the last head line still waiting for help text
    for line in text.splitlines():
        if line.startswith("  -") and not line.startswith("   "):
            parts = _HEAD_HELP_SPLIT.split(line.strip(), maxsplit=1)
            head = parts[0]
            help_text = parts[1].strip() if len(parts) > 1 else ""
            pending = []
            for alt in head.split(", "):
                tokens = alt.split()
                if not tokens or not tokens[0].startswith("--"):
                    continue
                pending.append(HelpOption(tokens[0], len(tokens) > 1, help_text))
            options.extend(pending)
            if help_text:
                pending = []
        elif pending and line.startswith("   ") and line.strip():
            first = line.strip()
            options = [
                HelpOption(o.flag, o.takes_value, first) if o in pending else o
                for o in options
            ]
            pending = []
        else:
            pending = []
    return [o for o in options if o.flag != "--help"]
