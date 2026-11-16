# Raster chart viewer, RC-1 Stage 7: acceptance card (2026-11-16)

**Artifact (cockpit/desk-readable card):** https://claude.ai/artifact/21AkKixYQcXaLDKfnbRSvN
**Card source:** `docs/acceptance/2026-11-16-raster-chart-viewer-rc1-stage7-sortie.md`
**Branch to fly:** `main` (after this DoD report's merge — Stages 1-6, tip `91e2296c`)

What is under test, verbatim from `plans/raster-chart-viewer/plan.md` Stage 7 and
`raster-chart-viewer/README.md`'s own "Stage 7" section: the live, Windows-box, real-DCS-data
check this plan's fixtures structurally cannot perform — whether every installed terrain's real
RasterCharts mosaic renders continuous (not scrambled) in a real browser via real OpenSeadragon,
and whether the background warm-up actually makes the first zoomed-out view feel fast on native
Windows I/O.

**What was verified for real before this card was written** (this session, WSL/Linux, no DCS
install, no browser): every setup/run command below was executed against this subproject's own
test suite and a real (fake-data) server instance — `ruff format/check`, `mypy --strict`,
`pytest` (55/55), and `python -m raster_chart_viewer --dcs-install <path> --port <port>
--host 127.0.0.1 --cache-dir <dir>` from inside `src/`, which bound the port and logged
"listening on 127.0.0.1:<port>" exactly as the README describes — confirming the module
invocation, the required `--dcs-install` flag, and the "stand in `src/`" instruction are all
correct, not merely plausible by reading. A live HTTP round-trip against that server is covered
by `test_server.py`'s own real-server urllib check (part of the 55 passing tests), not re-run
separately here (this environment has no outbound network tooling).

**What is UNVERIFIED and can only be confirmed on the Windows box**: the Windows-side venv
creation and `pip install pillow` (Windows `python.exe` + Pillow were confirmed absent/present
only during planning, not in this session), the firewall rule, whether the `/mnt/c` checkout
requirement actually matters in practice, and — the whole point of Stage 7 — whether the
sheet-mosaic convention (measured and edge-matched on Syria only) actually holds on Afghanistan,
Kola, Mariana Islands and Caucasus's zip-per-sheet layout, and whether OpenSeadragon's real
pan/zoom rendering handles the power-of-two-canvas edge-tile sidestep cleanly (`implementation.md`,
"Notable Discoveries" — this was sidestepped in design, not proven, and no browser exists in any
session that touched this feature so far).

Results go to `raster-chart-viewer/ROADMAP/RC-1.md` (clear `#needs-flight` there once flown,
naming the session that cleared it), not into the card.
