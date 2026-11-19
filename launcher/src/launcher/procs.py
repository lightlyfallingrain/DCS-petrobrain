"""Run one service's script as a child process group and keep the tail of its output."""

from __future__ import annotations

import collections
import os
import re
import signal
import subprocess
import threading
import time
from enum import Enum
from pathlib import Path

from launcher.services import Service

LOG_KEEP = 200
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# Grace periods before escalating a stop: SIGINT lets Python services run their KeyboardInterrupt
# cleanup, which is how they stop when Ctrl-C is pressed in their own terminal.
SIGINT_GRACE_S = 5.0
SIGTERM_GRACE_S = 2.0


class RunState(Enum):
    OFF = "OFF"
    ON = "ON"
    STOPPING = "STOPPING"


def child_env() -> dict[str, str]:
    """Unbuffered output, also for Windows `python.exe` started via WSL interop (needs WSLENV)."""
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    wslenv = [p for p in env.get("WSLENV", "").split(":") if p]
    if "PYTHONUNBUFFERED" not in wslenv:
        wslenv.append("PYTHONUNBUFFERED")
    env["WSLENV"] = ":".join(wslenv)
    return env


class ServiceProcess:
    def __init__(self, service: Service, scripts_dir: Path) -> None:
        self.service = service
        self.scripts_dir = scripts_dir
        self.log: collections.deque[str] = collections.deque(maxlen=LOG_KEEP)
        self._proc: subprocess.Popen[bytes] | None = None
        self._stopping = False
        self._lock = threading.Lock()

    @property
    def state(self) -> RunState:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                return RunState.OFF
            return RunState.STOPPING if self._stopping else RunState.ON

    def start(self, extra_args: list[str]) -> None:
        if self.state is not RunState.OFF:
            return
        argv = ["bash", self.service.script, *extra_args]
        self.log.append(f"[launcher] start: {' '.join(argv)}")
        try:
            proc = subprocess.Popen(
                argv,
                cwd=self.scripts_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=child_env(),
                start_new_session=True,  # own process group; the terminal's Ctrl-C stays ours
            )
        except OSError as exc:
            self.log.append(f"[launcher] could not start: {exc}")
            return
        with self._lock:
            self._proc = proc
            self._stopping = False
        threading.Thread(target=self._pump, args=(proc,), daemon=True).start()

    def _pump(self, proc: subprocess.Popen[bytes]) -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            text = _ANSI.sub("", raw.decode("utf-8", "replace")).rstrip("\r\n")
            self.log.append(text.split("\r")[-1])
        code = proc.wait()
        self.log.append(f"[launcher] exited, code {code}")

    def stop_async(self) -> None:
        with self._lock:
            proc = self._proc
            if proc is None or proc.poll() is not None or self._stopping:
                return
            self._stopping = True
        threading.Thread(target=self._stop, args=(proc,), daemon=True).start()

    def stop_and_wait(self) -> None:
        with self._lock:
            proc = self._proc
            if proc is None or proc.poll() is not None:
                return
            self._stopping = True
        self._stop(proc)

    def _stop(self, proc: subprocess.Popen[bytes]) -> None:
        for sig, grace in (
            (signal.SIGINT, SIGINT_GRACE_S),
            (signal.SIGTERM, SIGTERM_GRACE_S),
            (signal.SIGKILL, 0.0),
        ):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                break
            if sig is not signal.SIGINT:
                self.log.append(f"[launcher] sent {sig.name}")
            try:
                proc.wait(timeout=grace if grace else None)
                break
            except subprocess.TimeoutExpired:
                continue
        if self.service.windows_marker is not None:
            self._kill_windows_leftovers(self.service.windows_marker)
        with self._lock:
            self._stopping = False

    def _kill_windows_leftovers(self, marker: str) -> None:
        """Kill a Windows `python.exe` whose command line contains `marker` (WSL only).

        Insurance for X-B40's open question -- whether ending the WSL side ends the Windows process
        when it runs without a console. Logged when it fires, so a sortie says whether it is needed.
        """
        safe = marker.replace("'", "''")
        script = (
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{safe}*' }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }"
        )
        started = time.monotonic()
        try:
            out = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", script],
                capture_output=True,
                timeout=20,
                check=False,
            ).stdout.decode("utf-8", "replace")
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.log.append(f"[launcher] Windows leftover check failed: {exc}")
            return
        pids = out.split()
        if pids:
            self.log.append(
                f"[launcher] killed leftover Windows python.exe {', '.join(pids)} "
                f"({time.monotonic() - started:.1f} s)"
            )


def read_help(service: Service, scripts_dir: Path) -> str:
    """`run-<svc>.sh --help` output; argparse prints and exits whatever else is on the line."""
    try:
        result = subprocess.run(
            ["bash", service.script, "--help"],
            cwd=scripts_dir,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=child_env(),
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"[launcher] --help failed: {exc}"
    return (result.stdout + result.stderr).decode("utf-8", "replace")
