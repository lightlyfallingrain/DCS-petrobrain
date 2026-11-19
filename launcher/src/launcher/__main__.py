"""Entry point: `python -m launcher` from `launcher/src`, or `run-scripts/launcher.sh`."""

from __future__ import annotations

import curses
import subprocess
import sys
from pathlib import Path

from launcher.envfile import default_services, parse_env
from launcher.services import detect_platform, services_for
from launcher.ui import App

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "run-scripts"


def version() -> str:
    """Branch and `git describe` -- no project version exists, and the branch is what matters."""

    def git(*args: str) -> str:
        try:
            out = subprocess.run(
                ["git", "-C", str(REPO_ROOT), *args],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return out.stdout.decode().strip()

    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    return f"{branch} @ {git('describe', '--always', '--dirty') or '?'}"


def main() -> int:
    env_path = SCRIPTS_DIR / "petrobrain.env"
    try:
        env = parse_env(env_path.read_text())
    except OSError:
        env = {}
    platform = detect_platform()
    services = tuple(
        s for s in services_for(platform) if (SCRIPTS_DIR / s.script).exists()
    )
    names = {s.name for s in services}
    wanted = default_services(env)
    unknown = [n for n in wanted if n not in names]
    notice = f"unknown in DEFAULT_SERVICES: {', '.join(unknown)}" if unknown else ""
    app = App(services, SCRIPTS_DIR, env, version(), notice)
    curses.wrapper(app.run, [n for n in wanted if n in names])
    for s in services:
        tail = [ln for ln in app.procs[s.name].log if ln.startswith("[launcher]")][-1:]
        print(f"{s.name:<16} {tail[0] if tail else '(not started)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
