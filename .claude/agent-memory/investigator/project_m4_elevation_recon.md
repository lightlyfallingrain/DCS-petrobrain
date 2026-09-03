---
name: project_m4_elevation_recon
description: M4 elevation recon findings — land.getHeight scope, io/lfs sandbox, net.log bypass, SRTM vs Copernicus DEM choice
metadata:
  type: project
---

M4 (DCS elevation) recon, 2026-09-03, full details in `world-model/research/2026-09-03-m4-elevation-recon.md`.

- `land.getHeight` is Mission Scripting-only (Hoggit-documented), same environment as M1's `coord.LOtoLL`. No offline heightmap asset exists in `Mods/terrains/Syria/` — elevation is baked into proprietary encrypted/binary formats (`.surface5`, `.tile`, `.ng5`, `.sup4`, plus an encrypted `terrain.cfg.lua.pak.crypt`), none publicly specified. Live-mission probing is the only known route.
- io/os/lfs stripped by default in `MissionScripting.lua` — strongly convergent evidence (MOOSE docs, jboecker repo, ED forum thread titles all describe the identical `sanitizeModule` mechanism) but never directly confirmed by reading *this* install's actual file (cheap follow-up: `cat Scripts/MissionScripting.lua` via WSL, no mission needed).
- **Key finding: `net.log(string)` (Hoggit-documented, writes to `Logs/dcs.log`) is NOT touched by the io/os/lfs sandbox** — this is the scalable, read-only-compliant way to get bulk data (e.g. an elevation grid) out of a Mission Scripting probe without editing `MissionScripting.lua` and without `trigger.action.outText`'s manual-transcription limit. Prefer this over the io.open pattern `coord_probe.lua` used, going forward.
- DEM recommendation: **SRTM `.hgt`** (flat int16 binary, stdlib `struct`-parseable, no new dependency) over Copernicus GLO-30 (COG GeoTIFF, would force GDAL/rasterio or similar — real new dependency). SRTM needs a NASA Earthdata account for the official channel; viewfinderpanoramas.org is a no-login `.hgt` mirror fallback.
- User indicated willingness to hand-edit `MissionScripting.lua` to open io/lfs — this conflicts with the project's stated non-negotiable "never modify the DCS installation" invariant; flagged as an explicit Architect/user decision, not something to assume. `net.log` makes the tradeoff moot either way.
