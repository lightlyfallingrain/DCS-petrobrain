# Handoff to the Windows-box session — build the raster chart viewer

**From:** the Mac session, 2026-11-16. **To:** `windows-session`, at the user's direction: the
user is putting the Windows session to work on this build.

**Branch:** `feature/raster-chart-viewer` (pushed to `origin`). Fetch it; do not branch from
`origin/main`. Everything below is committed on it.

## Status

**Planned and approved. Nothing implemented yet.** The plan's three user decisions are answered,
and the user approved one amendment to the cache design. Next is implementation, Stage 1 onward.

## Read, in this order

1. `mission-interpreter/ROADMAP/MI-B4.md` — the user's requests verbatim and the decision trail.
   MI-B4 is this service's **only** roadmap entry. The code is its own top-level service,
   `raster-chart-viewer/`, with no `ROADMAP/` directory (user: *"this should really be it's own
   small service, not under MI. I just did not want to create another roadmap folder for it."*).
2. `raster-chart-viewer/research/2026-11-16-rastercharts-all-terrains-recon.md` — your own recon,
   written up. The authority on file layout, naming, the sheet mosaic and timing.
3. `plans/raster-chart-viewer/plan.md` — the plan. Read in particular:
   - "Cache: served tiles plus small mips only — amended 2026-11-16" — **replaces** the plan's
     first cache design. Do not build the superseded version described at the top of that section.
   - "Mitigating the slow first fully-zoomed-out view" — warm-up starts per `(terrain, tier)` on
     first use, not for every terrain at server start.
   - "Decisions Requiring User Input — all answered 2026-11-16" — U1–U3 with the user's words.
4. `aircraft-layer/WORKFLOW.md` — the precedent for a LAN-facing Python server launched from WSL
   bash as Windows `python.exe`, and the firewall rule.

## Decided — do not reopen

- **U1:** Windows `python.exe` in a Windows-side venv with Pillow, launched from WSL bash.
  Windows `python.exe` is 3.14.7 and has no Pillow today.
- **U2:** Mariana's 62 tiles with no scale prefix become their own "unscaled" tier.
- **U3:** build all terrains first. The user checks each terrain by eye; a terrain that renders
  scrambled becomes a follow-up, not a blocker.
- **Cache:** composed-tile JPEGs plus small-mip PNGs (`N ≥ SMALL_MIP_MIN = 3`) only, 1 GB cap,
  middle zooms re-inflate.
- **Port 7800**, OpenSeadragon vendored at an exact version with its BSD-3 licence, Python stdlib
  server and `zipfile`, Pillow the only dependency.

## One thing to check before Stage 7 — where the checkout lives

`aircraft-layer/WORKFLOW.md` warns: *keep the Windows-side checkout on the Windows filesystem
(`/mnt/c/...`). A checkout on WSL's own ext4 is reachable from Windows only through a `\\wsl$\`
UNC path, and Windows tooling is unreliable about UNC working directories.* Your scratchpad path
suggests your checkout is on WSL ext4 (`/home/sg/Code/DCS-petrobrain`). Windows `python.exe`
running a module from there may fail or misbehave. Stages 1–6 can be built and tested with the
WSL venv's Python; for the Windows venv and Stage 7 either use a checkout under `/mnt/c` or show
the UNC path works. Say which in the run instructions.

## How the work runs here

The project's own sequence, per root `CLAUDE.md` and `AGENTS.md`: Implementer → Reviewer (loop
until approved) → one Performance pass and one Security pass for the batch → Definition of Done →
merge. Goal-aligner and plan-aligner do not apply: no Petrovich behaviour depends on this service.
Work in a worktree, never in the repo root. Run `raster-chart-viewer`'s own ruff format/check,
`mypy --strict` from inside the subproject, and pytest before every commit.

**Never commit chart images or anything decoded from them.** They belong to Eagle Dynamics. Every
test fixture is synthetic; the plan says how Pillow builds multi-mip DXT5 fixtures.

**The Mac session keeps merging to `main` meanwhile.** Before the final merge, bring `main` in and
re-run the checks.

## When done

Stage 7 is the user's live check: Syria in both tiers, Caucasus, and a look at the others, from a
phone or tablet on the LAN. Give the user the branch name, the one-time setup (venv, Pillow,
firewall rule) and the exact run command from WSL bash. Record the result on MI-B4.
