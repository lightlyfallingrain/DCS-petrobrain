"""Which services exist on this machine, and how a start command is built from toggled options.

The launcher drives the existing `run-scripts/run-*.sh` scripts and does not hold a second copy of
their command lines (X-B40 plan): a toggled option is appended, and reaches the service through the
script's own `"$@"`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from launcher.helpparse import HelpOption

# Flags that draw on the terminal (no place for them in a 10-line log pane), or that print and exit.
# User, 2026-11-19: "terminal draw debug option not available in launcher."
_BODY_HIDDEN = frozenset(
    {
        "--eyesight-view",
        "--eyesight-view-radius-m",
        "--pov-view",
        "--print-tuning",
        "--print-rules",
    }
)


@dataclass(frozen=True)
class Service:
    name: str
    script: str
    hidden: frozenset[str] = field(default_factory=frozenset)
    # Windows-side services only: a fragment of the `python.exe` command line, used to kill a
    # leftover Windows process if stopping the WSL side did not end it (X-B40, unverified).
    windows_marker: str | None = None


_MAC: tuple[Service, ...] = (
    Service("audio-adapter", "run-audio-adapter.sh"),
    Service("piper", "run-piper-mac.sh"),
    Service("brain", "run-brain.sh"),
    Service("body-layer", "run-body-layer.sh", _BODY_HIDDEN),
)

_WSL: tuple[Service, ...] = (
    Service("aircraft-layer", "run-aircraft-layer.sh", windows_marker="-m collector"),
    Service(
        "audio-capture", "run-audio-capture.sh", windows_marker="audio_adapter.capture"
    ),
    Service(
        "audio-adapter",
        "run-audio-adapter-windows.sh",
        windows_marker="-m audio_adapter --host",
    ),
    Service("piper", "run-piper-windows.sh", windows_marker="piper.http_server"),
    Service("brain", "run-brain.sh"),
    Service("body-layer", "run-body-layer.sh", _BODY_HIDDEN),
    Service(
        "chart-viewer", "run-chart-viewer.sh", windows_marker="-m raster_chart_viewer"
    ),
)


def detect_platform() -> str:
    """'wsl' or 'mac' -- the two shells the launcher supports (user, 2026-11-17)."""
    try:
        if "microsoft" in Path("/proc/version").read_text().lower():
            return "wsl"
    except OSError:
        pass
    return "mac"


def services_for(platform: str) -> tuple[Service, ...]:
    return _WSL if platform == "wsl" else _MAC


class OptionState(Enum):
    TOGGLEABLE = "toggleable"
    IN_SCRIPT = "in_script"  # already on the run script's own command line
    NO_VALUE = "no_value"  # value flag with no OPT_ key in petrobrain.env


def env_key(service: str, flag: str) -> str:
    """`OPT_<SERVICE>_<FLAG>`: where a value flag's value lives in petrobrain.env."""
    return (
        "OPT_" + re.sub(r"[^A-Za-z0-9]", "_", f"{service}_{flag.lstrip('-')}").upper()
    )


def script_flags(script_text: str) -> set[str]:
    """Every `--flag` the script's own command lines already pass (comments excluded)."""
    code = "\n".join(line.split("#", 1)[0] for line in script_text.splitlines())
    return set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", code))


def option_state(
    service: str, opt: HelpOption, in_script: set[str], env: dict[str, str]
) -> OptionState:
    if opt.flag in in_script:
        return OptionState.IN_SCRIPT
    if opt.takes_value and env_key(service, opt.flag) not in env:
        return OptionState.NO_VALUE
    return OptionState.TOGGLEABLE


def build_args(
    service: str, enabled: list[HelpOption], env: dict[str, str]
) -> list[str]:
    """Extra arguments for the run script, in option order."""
    args: list[str] = []
    for opt in enabled:
        args.append(opt.flag)
        if opt.takes_value:
            args.append(env[env_key(service, opt.flag)])
    return args
