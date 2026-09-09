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
