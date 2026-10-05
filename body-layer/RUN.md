# Running the Body Layer

Petrovich's belief state: it polls the aircraft layer's API, runs perception
through its detection channels, and logs what Petrovich could plausibly have
noticed.

**Where this runs:** anywhere on the LAN — typically the Mac, pointed at the
Windows DCS box's aircraft-layer API. It does not need DCS itself.

For the design see `CLAUDE.md`; for milestone status see `todo/todo.md`.

---

## 1. One-time setup

Body layer imports world-model's `query`/`coordinates` packages in-process,
which pulls in `pyproj`. That is why it needs a real venv rather than stdlib
Python.

**macOS (zsh)**

```zsh
cd body-layer
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

**Windows (Command Prompt)**

```bat
cd body-layer
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

You also need a **built world-model `.sqlite`** for the terrain
line-of-sight gate — see `world-model/RUN.md`. Point `--world-model-db` at a
region whose coverage includes wherever you are flying.

## 2. Run the perception logger

**macOS (zsh)**

```zsh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://192.168.1.50:7791 \
  --theatre Syria \
  --world-model-db ../world-model/data/syria-full.sqlite
```

**Windows (Command Prompt)** — note the `;` path separator, not `:`.

```bat
cd body-layer
set PYTHONPATH=src;..\world-model\src
.venv\Scripts\python -m logger ^
  --aircraft-layer-url http://192.168.1.50:7791 ^
  --theatre Syria ^
  --world-model-db ..\world-model\data\syria-full.sqlite
```

Two things that will bite:

- **The venv interpreter is not optional.** Plain `python -m logger` fails with
  `ModuleNotFoundError: No module named 'pyproj'` once it reaches the
  world-model import chain. Either use the `.venv/bin/python` prefix or
  `source .venv/bin/activate` first (`.venv\Scripts\activate.bat` on Windows).
- **`PYTHONPATH` needs both entries.** Neither `src` directory is an installed
  package, and the world-model seam is a direct import.

### Arguments

| flag | required | meaning |
|---|---|---|
| `--aircraft-layer-url` | yes | base URL of the aircraft-layer LAN API |
| `--theatre` | yes | DCS theatre name, for lat/lon → DCS x/z conversion |
| `--world-model-db` | yes | path to a built region `.sqlite` |
| `--poll-interval-s` | no | seconds between poll ticks |

`--world-model-db` became required in PB-1.5: the naked-eye channel's terrain
LOS gate needs elevation data. Older notes showing a two-argument command are
out of date.

### The debug logs get a new filename every run

`--detection-trace`, `--belief-truth-log` and `--speech-log` all write JSONL,
and **the path you pass is not the path written.** Each run stamps its own
start time into the filename before the suffix, so

```
--detection-trace logs/dcs-detection-trace.jsonl
```

actually writes `logs/dcs-detection-trace-20261006-143500.jsonl`. Only the
filename is rewritten — the path's directory is used as given, never
relocated — and all three logs of one run share the same stamp so you can tell
at a glance which files belong to which sortie. The logger prints each
resolved path to stderr as it starts — that line is the authoritative answer
to "where did it go".

**The directory is created if it is missing**, which matters because `logs/`
is gitignored and so absent in a fresh clone. Without that, the writers'
`open(path, "a")` would raise `FileNotFoundError` during startup — before any
of the write-failure handling below could report it — and the crew would not
start at all. A directory that cannot be created disables that one log, with a
line on stderr, rather than taking the sortie down with it.

Where the run scripts put them: `run-scripts/run-crew-text.sh` and
`run-crew-text-debug-view.sh` both `pushd` into `body-layer/` first and pass
relative `logs/dcs-*.jsonl` paths, so the files land in `body-layer/logs/`.
They used to land loose in `$HOME` as `~/dcs-*.jsonl`.

This is `BL-11` Stage 5. Before it, all three opened with `"a"` and never
rolled, so one path accumulated every sortie ever flown: the detection trace
alone writes ~50 MB a minute, and the 2026-10-05 log analysis had to seek to
byte offset 2,448,471,603 to find that flight at all. Timestamping rather than
truncating is deliberate — truncating would also fix the seeking, and would
silently destroy the previous flight's log.

**Globs, not fixed names**, in anything that reads these afterwards:
`ls -t logs/dcs-detection-trace-*.jsonl | head -1` is the newest sortie.

If a write fails mid-flight (a full disk is the realistic case), that writer
says so once on stderr and then stops for the rest of the run. Perception,
belief and speech are unaffected — losing the trace is bad, losing the crew
member is worse.

## 3. Reading the output

One flat text line per observation, tagged by source:

```
source=petrovich_detection_associated observation_id=... bearing_deg=45.0 range_m=2100 classification_raw=OP_ARMORED ...
source=naked_eye_visual_filtered      observation_id=... bearing_deg=60.0 range_m=1800 classification_raw=OP_TRUCK ...
```

Two detection channels run side by side:

- **`petrovich_detection_associated`** — the scope channel. Gated on real
  HelperAI indication text, so it only fires when Petrovich's sight is on and
  has something listed.
- **`naked_eye_visual_filtered`** — our own channel. Gated on a synthetic
  FOV + angular-size + terrain-LOS filter over `LoGetWorldObjects`. Fires
  independently of the sight.

Bearings quantise to the 12 clock positions and ranges to ED's bucket ladder,
so values look coarse on purpose — that is the anti-omniscience design, not a
rounding bug.

## 4. Development checks

Run from the repository root.

**macOS (zsh)**

```zsh
ruff format body-layer/src body-layer/tests
ruff check body-layer/src body-layer/tests
mypy body-layer/src
pytest body-layer/tests
```

**Windows (Command Prompt)**

```bat
ruff format body-layer\src body-layer\tests
ruff check body-layer\src body-layer\tests
mypy body-layer\src
pytest body-layer\tests
```

`mypy` must be run **from `body-layer/`** if you hit path resolution problems —
its `mypy_path` includes `../world-model/src` relative to that directory.

## 5. Offline replay

`src/replay.py` is a **library, not a command**. It feeds recorded ownship
telemetry frames through any `PerceptionSource` with no live DCS connection,
and is what makes body-layer milestones testable offline. Use it from a test or
a short script; there is no CLI.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'pyproj'`** — you used system Python
instead of the venv interpreter. See step 2.

**`ModuleNotFoundError: No module named 'logger'` / `'perception'`** —
`PYTHONPATH` is unset or missing an entry. On Windows the separator is `;`.

**Connection refused / timeouts** — the aircraft-layer collector is not running
on the Windows box, or the firewall is blocking port 7791. See
`aircraft-layer/RUN.md` steps 3–4.

**Nothing is ever detected** — check the world-model region actually covers
where you are flying. A `.sqlite` built for one area gives the LOS gate no
elevation data elsewhere, which looks like a broken filter rather than missing
coverage.

**Only scope detections appear, never naked-eye** — expected when targets are
outside the ±60° cone, beyond their per-type range (truck ~3 km, T-72 ~3.5 km,
infantry ~900 m), or terrain-occluded.
