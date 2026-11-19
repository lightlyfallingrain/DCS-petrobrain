# launcher/CLAUDE.md

Subproject instructions for the Petrobrain launcher. Augments the root `CLAUDE.md`.

**Tracked as `todo/backlog/X-B40.md`**, not under a roadmap of its own (user, 2026-11-19: *"keep
filed in todo/backlog"*). That entry has the user's spec verbatim, the decisions and the plan.

## What this is

A curses text UI that starts, stops and watches the services on **one machine** (Mac or WSL bash
on the Windows box). A helper tool: **no Petrovich behaviour depends on it**, it imports nothing
from any other subproject, and it changes nothing a service does.

**It drives the existing `run-scripts/run-*.sh` scripts** and holds no copy of their command
lines. A toggled option is appended to the script's arguments and reaches the service through the
script's own `"$@"` -- so every script in `services.py`'s table must forward `"$@"`
(`tests/test_services.py` checks this). Options come from `run-<svc>.sh --help`; a value flag's
value from `OPT_<SERVICE>_<FLAG>` in `run-scripts/petrobrain.env`; autostart from
`DEFAULT_SERVICES` there.

Not "fancy or very robust at this stage" (user, 2026-11-19) -- toggles reset each launch, values
are not editable in the UI, and a service that draws on the terminal, or that you want to type
into, is started by hand instead. Services get a stdin pipe that stays open and is never written
(an EOF ended body-layer's stdin REPL, and so body-layer, at start -- 2026-11-19).

## Tech stack

- Python 3.11+, **stdlib only at runtime** (`curses`, `subprocess`, `threading`) -- run by
  `run-scripts/launcher.sh` with `launcher/.venv` if present, else `python3`.
- `mypy --strict`, `ruff format` / `ruff check`, `pytest`.

## Commands

```sh
ruff format launcher/src launcher/tests   # format
ruff check launcher/src launcher/tests    # lint
cd launcher && .venv/bin/mypy src         # type check (strict) -- CWD-only config discovery
pytest launcher/tests -q                  # test
```

Reinstall the venv (dev tools only):

```sh
python3 -m venv launcher/.venv
launcher/.venv/bin/pip install "ruff==0.16.6" "mypy==2.3.1" "pytest==9.1.1" pytest-xdist
```

## Testing

Unit tests cover the pure parts: `envfile.py`, `helpparse.py`, `services.py`. `procs.py` and
`ui.py` are checked by running the launcher (a pty-driven run on the Mac at build time; the
Windows side by the user, see X-B40).

## Structure

`src/launcher/` -- `envfile.py` (parse `petrobrain.env`), `helpparse.py` (argparse `--help` ->
options), `services.py` (per-platform service table, option state, argument build), `procs.py`
(child process group, output tail, stop: SIGINT -> SIGTERM -> SIGKILL, plus a Windows
`python.exe` leftover kill via `powershell.exe` for WSL-interop services), `ui.py` (curses),
`__main__.py`.
