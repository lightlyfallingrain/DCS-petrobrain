# raster-chart-viewer

Serve an installed DCS World terrain's `RasterCharts` as a pan/zoom tiled map, from a small LAN
service on the Windows DCS machine, with tiles made on demand (no bulk extraction). See
`CLAUDE.md` for the stack/structure and `plans/raster-chart-viewer/plan.md` for the design this
implements. **No Petrovich behaviour depends on this** -- it is a crew reference tool, not a
perception/belief/decision feature.

Stages 1-6 (discovery, mosaic math, DDS mip decode, the disk cache, the HTTP server, the viewer
page, background warm-up) are built and tested against synthetic fixtures -- no live DCS instance
is needed for any of that. **Stage 7, below, is the one live check this plan cannot close from a
fixture**, and it is the user's own task, not something to script or automate.

## Development (any machine with the repo checked out)

```sh
python3 -m venv raster-chart-viewer/.venv
raster-chart-viewer/.venv/bin/pip install "pillow>=9.1" "ruff==0.16.6" "mypy==2.3.1" "pytest==9.1.1"
pytest raster-chart-viewer/tests -q
```

No DCS install is needed for this -- every test builds its own synthetic DDS fixtures and fake
terrain trees (`tests/fixtures/`).

## Stage 7 -- the live check (Windows DCS machine, from WSL bash)

**Follows `aircraft-layer/WORKFLOW.md`'s own precedent exactly**: WSL bash launches **Windows**
`python.exe`, so the process binds the Windows network interface (reachable from the rest of the
LAN) and keeps zip reads on native Windows I/O rather than WSL's slower `/mnt/c`/`/mnt/f` 9P
bridge -- the one slow path (warm-up, first fully-zoomed-out view) this feature actually has.

### 0. One-time: a checkout under `/mnt/c`, not WSL's own ext4

**Windows `python.exe` cannot reliably run a module from a WSL-ext4 path.** A checkout at, say,
`/home/sg/Code/DCS-petrobrain` is reachable from Windows only through a `\\wsl$\` UNC path, and
Windows tooling (including `python.exe` itself) is unreliable about UNC working directories --
the same gotcha `aircraft-layer/WORKFLOW.md` already documents for its own collector. Stages 1-6
can be built and tested with the WSL venv's Python from anywhere; the Windows venv and this stage
need a checkout under `/mnt/c`. If one does not already exist:

```bash
git clone /home/sg/Code/DCS-petrobrain /mnt/c/Users/<you>/DCS-petrobrain
# or, if the WSL checkout already has the branch you want to run:
cd /mnt/c/Users/<you>/DCS-petrobrain && git fetch /home/sg/Code/DCS-petrobrain <branch> && git checkout <branch>
```

### 1. One-time: a Windows-side venv with Pillow

This project has never needed a third-party dependency on the Windows side before (`aircraft-layer`'s
collector is stdlib-only) -- there is no existing Windows venv to reuse. Windows `python.exe` ships
with DCS-adjacent tooling but **has no Pillow installed by default** (confirmed during planning:
3.14.7, no Pillow). From WSL bash, in the `/mnt/c` checkout:

```bash
cd /mnt/c/Users/<you>/DCS-petrobrain/raster-chart-viewer
python.exe -m venv .venv-win
.venv-win/Scripts/python.exe -m pip install pillow
```

### 2. One-time: firewall rule

Windows Firewall blocks inbound connections to a Python process by default. On the Windows
machine (PowerShell or `cmd`, as Administrator):

```
netsh advfirewall firewall add rule name="raster-chart-viewer" dir=in action=allow protocol=TCP localport=7801
```

Scope this to your LAN profile, not Public, if prompted.

### 3. Run (from WSL bash, in the `/mnt/c` checkout)

**Stand in `src/`** -- `src` is not installed as a package, so `python -m raster_chart_viewer`
needs it on `sys.path` somehow, and `python -m` putting the working directory there is one fewer
thing to get wrong than `PYTHONPATH` (same reasoning as `aircraft-layer/WORKFLOW.md`'s own note on
this exact point):

```bash
cd /mnt/c/Users/<you>/DCS-petrobrain/raster-chart-viewer/src
../.venv-win/Scripts/python.exe -m raster_chart_viewer --dcs-install "F:\Games\DCS World"
```

(Substitute your real DCS install path -- Windows-style, backslashes and all, since this runs as
a Windows process.) Add `-v` for DEBUG logging. `--cache-dir`/`--cache-cap-bytes`/`--host`/`--port`
override the defaults (`%TEMP%\raster-chart-viewer-cache`, 1GB, `0.0.0.0`, `7801`) -- see
`python -m raster_chart_viewer --help`.

### 4. Open it from any device on the LAN

```
http://<windows-box-lan-ip>:7801/
```

A phone, tablet, or second screen -- anything on the same LAN. Pick a terrain and tier from the
pickers; pinch/scroll to zoom, drag to pan.

### What to check

- **Syria, both tiers (32m and 64m)** and **Caucasus** (the special zip-per-sheet layout) -- pan
  and zoom each; the mosaic should look continuous (a coherent map), not scrambled. This is what
  settles U3 (the sheet-mosaic convention, measured on Syria only, applied everywhere).
- **Afghanistan, Kola, Mariana Islands** too, including Mariana's "unscaled" tier (U2) -- a quick
  look is enough; a terrain that renders scrambled is a follow-up to file, not a blocker for the
  rest (U3's own answer).
- **The first fully-zoomed-out view of a tier should be fast once warm-up has had a few seconds**
  -- the one slow path this plan's background warm-up (Stage 6) exists to hide. A *very* first
  look, right after starting the server, may still be a little slow for the largest tiers
  (Afghanistan's 32m, ~3000 entries) while warm-up is still running in the background; it should
  not be slow again on a second look at the same tier.
- **No DCS session is needed for any of this** -- the service reads only installed files, so
  pausing or closing the mission (or not having one running at all) makes no difference.

Record the result (which terrains/tiers looked right, which didn't, and the warm-up timing) on
`raster-chart-viewer/ROADMAP/RC-1.md`.
