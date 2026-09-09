# Running the Aircraft Layer

Live DCS I/O: `Export.lua` pushes ownship telemetry, world objects and
Petrovich's indication text into a local Python collector, which serves them
over a LAN HTTP API.

**Where this runs:** the Windows box running DCS. The collector must be on the
same machine as DCS — `Export.lua` connects to it over loopback. Only the HTTP
API faces the LAN.

For the design behind it see `CLAUDE.md`; for the cross-machine deploy story
see `WORKFLOW.md`.

---

## 1. One-time setup

No third-party dependencies — stdlib only. You still want a venv so the module
is importable and the dev tools are isolated.

**Windows (Command Prompt)**

```bat
cd aircraft-layer
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

**macOS (zsh)**

```zsh
cd aircraft-layer
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## 2. Deploy Export.lua (Windows, once per change)

Copy `aircraft-layer/dcs-export/Export.lua` to:

```
%USERPROFILE%\Saved Games\DCS\Scripts\Export.lua
```

```bat
copy dcs-export\Export.lua "%USERPROFILE%\Saved Games\DCS\Scripts\Export.lua"
```

The repo copy is canonical. **Never edit the deployed copy in place** — it is
not tracked, and the next deploy overwrites it.

Optional verbose logging: create an empty flag file, and Export.lua will write
to `Saved Games\DCS\Logs\aircraft_layer_debug.log`.

```bat
type nul > "%USERPROFILE%\Saved Games\DCS\Scripts\aircraft_layer_debug.flag"
```

Delete that file to turn logging off. It is read once at mission load, so
restart the mission after changing it.

## 3. Open the firewall (Windows, one-time)

Windows blocks inbound connections to a Python process by default. The API port
needs a rule; the Export.lua listener port (7790) does not, being loopback-only.

```bat
netsh advfirewall firewall add rule name="aircraft-layer-api" dir=in action=allow protocol=TCP localport=7791
```

Scope it to your private/LAN profile, not Public, if prompted.

## 4. Run the collector

**Windows (Command Prompt)**

```bat
cd aircraft-layer
set PYTHONPATH=src
.venv\Scripts\python -m collector
```

**macOS (zsh)** — for tests or a dry run; there is no DCS to feed it.

```zsh
cd aircraft-layer
PYTHONPATH=src .venv/bin/python -m collector
```

`PYTHONPATH` is **required**, not optional — `src` is not an installed package,
and plain `python -m collector` fails with `No module named collector`.

Leave it running, then start DCS and enter a mission. Export.lua connects on
mission start.

### Options

| flag | default | meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Export.lua listener host (keep on loopback) |
| `--port` | `7790` | Export.lua listener port |
| `--api-host` | `0.0.0.0` | LAN-facing API host |
| `--api-port` | `7791` | LAN-facing API port |
| `--dump-interval` | `1.0` | seconds between latest-sample prints to stdout |
| `--debug` | off | log every received line and parse result |

## 5. Check it is working

From the Windows box:

```bat
curl http://localhost:7791/telemetry/latest
```

From the Mac, replacing the IP with the Windows box's LAN address:

```zsh
curl http://192.168.1.50:7791/telemetry/latest
```

Endpoints:

| endpoint | returns |
|---|---|
| `/telemetry/latest` | most recent ownship kinematic sample |
| `/world_objects/latest` | most recent `LoGetWorldObjects` ground-truth snapshot |
| `/petrovich_indication/latest` | most recent HelperAI indication tree |

A JSON `null` means no sample has arrived yet. That is **not an error** — DCS
may not be running, or you may not be in a mission.

## 6. Development checks

Run from the repository root, not from `aircraft-layer/`.

**macOS (zsh)**

```zsh
ruff format aircraft-layer/src aircraft-layer/tests
ruff check aircraft-layer/src aircraft-layer/tests
mypy aircraft-layer/src
pytest aircraft-layer/tests
```

**Windows (Command Prompt)** — same commands, run from the repo root.

```bat
ruff format aircraft-layer\src aircraft-layer\tests
ruff check aircraft-layer\src aircraft-layer\tests
mypy aircraft-layer\src
pytest aircraft-layer\tests
```

---

## Troubleshooting

**`No module named collector`** — `PYTHONPATH` is unset. On Windows, `set
PYTHONPATH=src` applies only to the current Command Prompt window.

**API returns `null` forever** — Export.lua is not connecting. Check the
deployed file exists, that you are actually in a mission (not the briefing
screen), and turn on the debug flag from step 2 to see whether it is failing to
connect.

**The Mac cannot reach the API** — firewall rule missing (step 3), or the
collector is bound to loopback. `--api-host` must be `0.0.0.0`, which is the
default.

**Export.lua changes have no effect** — DCS loads it at mission start. Restart
the mission, not just the collector.
