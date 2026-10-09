# WM-B2 — Power lines from DCS data

- [>] **WM-B2 — Power lines from DCS data — deferred 2026-09-13 (user: not important now).** #status/deferred Wanted as a
  low-level wire hazard and navigation landmark, but only with exact in-DCS positions (OSM's ~1 km
  offset rules it out as a source). Recon done: `research/2026-09-13-dcs-power-lines-recon.md`.
  Syria's model catalogs include `power_trans_line_big`/`power_pole_wooden`; placements live in
  `Scenes/Syria.scn5` (5.5 GB scenery placement database; header and 15,289-entry model-name table
  decoded, per-object record layout not). Recommended route when picked up: a live
  `world.searchObjects(SCENERY)` probe, `tools/dcs-mission-probe/power_line_scenery_probe.lua`
  (written, never run; run steps in its header). Alternative: decode `Syria.scn5` records, a large,
  uncertain reverse-engineering job.
