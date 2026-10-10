# WM-B15 — Multi-theatre support — Afghanistan, Caucasus, Kola

Promoted to an entry by the 2026-10-09 conversion of `world-model/ROADMAP.md`. In the source this
was a prose bullet in the Backlog section with no checkbox and no ID — but it is real outstanding
work rather than orientation prose (`docs/DOC_CONVENTIONS.md`, "Narrative orientation prose stays
in the index", on the one case that crosses over), so it takes an ID in the space that section's
own preamble declares, `WM-B<n>`. The `[~]` marker and its `#status/in-progress` tag are the only
text the conversion added to the source line, and they come from the entry's own *"Started
2026-10-04 with Afghanistan, then Caucasus, Kola last (user direction)"* — the bold lead's *"not
yet scoped"* predates that sentence rather than contradicting it. Nothing else was changed.

- [~] **Multi-theatre support (Afghanistan, Caucasus, Kola, others) — needed soonish, not yet scoped.** #status/in-progress
  Raised 2026-09-13. Architecture already generalizes (`THEATRE_PROJECTIONS`/`REGIONS` are
  per-theatre registries, not per-theatre code forks) — this is "add entries + verify," not a
  rewrite. Per-theatre work identified: (1) Transverse Mercator projection params — `pydcs` has
  fitted values for every theatre, but each needs live-DCS verification against real
  `coord.LOtoLL` output like WM-M1 did for Syria, not trusted blind; (2) a `RegionDefinition` entry
  (bbox/name) — cheap, mechanical; (3) raster chart registration (F10 paper map) — WM-M2's Syria fit
  was hand-derived from real-world control points on that specific raster, genuinely per-theatre
  manual work, not automatable from the pattern; (4) DCS source files (`towns.lua`/`beacons.lua`/
  `.routes`) — same parsers *should* work (same DCS-internal formats) but need an investigator
  pass per theatre, not assumed, since format has drifted across DCS versions before and no
  theatre besides Syria has been checked; (5) OSM/Geofabrik country-extract set differs per
  theatre, same `derive_m9_osm_clip_bbox.py`-style approach per theatre.
  **Kola is a genuinely harder case, not just "repeat the pattern":** SRTM only covers ±60°
  latitude, and Kola peninsula sits ~68-69°N, entirely outside SRTM's coverage — needs a
  different DEM source (ASTER GDEM to 83°N, or a Nordic national elevation dataset), unresolved
  and needs its own investigation before committing. **Update 2026-10-04: resolved in principle —
  viewfinderpanoramas.org DEM3 covers the Kola area (user-checked), same `.hgt` format the SRTM
  ingest already reads, so Kola needs no new elevation source.** Afghanistan and Caucasus are both within
  SRTM range, no elevation-source blocker. Needs an Architect + investigator pass before any
  theatre starts, per this project's standing convention for DCS-internals-uncertain work.
  **Started 2026-10-04 with Afghanistan, then Caucasus, Kola last (user direction).** Raw DEM and
  OSM extracts for both are staged under `world-model/data/raw/{dem,osm}/{afganistan,caucasus}-full/`
  (gitignored; `.hgt` tiles flattened to the folder top level, since `--srtm-dir` globs only `*.hgt`
  there). Caucasus DEM has 123 of 144 tiles — the missing ones are open Black Sea.
  **Update 2026-10-05: Caucasus and Kola registered** (`feature/multi-theatre-caucasus-kola`,
  Reviewer APPROVED, `plans/multi-theatre-caucasus-kola/review.md`), **merged 2026-10-10**. Recon
  (`research/2026-10-05-kola-caucasus-theatre-recon.md`) found nothing blocking: pydcs projections
  reproduced by beacon fits (~0.04 m RMS, both `provisional`), Kola's 64–71°N `.hgt` tiles parse
  unchanged, all parsers work on both theatres' files, staged OSM covers both envelopes. Regions
  `caucasus-full`/`kola-full`; run steps in `RUN.md` §8. **Remaining, user-run:** OSM clip/merge
  and the two builds; a live `coord_probe.lua` on each terrain to confirm the projections; optional
  Kola DEM tile `N71E023` (Tufjord, the one unstaged land tile).

  *This paragraph was written on the branch against the pre-split `world-model/ROADMAP.md` and
  re-landed here at merge time.* The branch's own edit conflicted with the four-line pointer that
  file became on 2026-10-09; resolving that conflict by keeping the branch's side would have put
  this text where nothing reads it, which is the exact failure the pointer's own gates were added
  to catch. Any other branch predating the split needs the same treatment.
