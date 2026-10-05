# Review: feature/multi-theatre-caucasus-kola

**Reviewed commit:** `45bac42eae264135b868afbeb9ef94185d694345` ("world-model: register Caucasus
and Kola theatres"), one commit on top of `main` (`906d0bd`). No `plans/multi-theatre-caucasus-kola/`
Architect plan exists — this commit is registry-entry work following
`plans/multi-theatre-afghanistan/plan.md`'s already-exercised pattern directly from
`world-model/research/2026-10-05-kola-caucasus-theatre-recon.md`'s "Possible Approaches" §1-2, the
same posture that note itself recommends ("Nothing here blocks starting the same five-stage plan
Afghanistan used... registry-entry work, not a new design pass").

**Verification method:** branch was checked out in the main checkout, so the worktree landed on
`main`. Verified via `git archive feature/multi-theatre-caucasus-kola | tar -x` into a scratch
directory and ran every check with `cwd` inside `<scratch>/world-model`, using
`/mnt/e/DCS-petrobrain/world-model/.venv/bin/<tool>` by absolute path. The installed DCS tree at
`/mnt/f/Games/DCS World/Mods/terrains/{Kola,Caucasus}/` and the staged raw data under
`world-model/data/raw/{dem,osm}/{kola,caucasus}-full/` (main checkout, read-only, untouched) were
both reachable from this worktree's environment.

## What was checked, and how

- **Diff scope**: `git diff main..feature/multi-theatre-caucasus-kola --stat` — 6 files, 171
  insertions, 0 deletions: `coordinates/projections.py`, `build/region.py`, `dcs_data/beacons.py`,
  `dcs_data/towns.py`, `tests/test_coordinates.py`, `RUN.md`. Matches the commit message's claim
  exactly — no scope drift, no unrelated files.
- **Path casing**, independently confirmed against the real installed tree (not just RUN.md's
  prose): Kola lowercase `map/towns.lua` + `beacons.lua`; Caucasus capitalized `Map/towns.lua` +
  `Beacons.lua`; `roads/Kola.routes`/`Kola.rn4` and `roads/Caucasus.routes`/`Caucasus.rn4` both
  present at the paths RUN.md's §8.2 build commands use.
- **Town/beacon counts**, independently reproduced by running the real parsers
  (`dcs_data.towns.parse_towns_lua`, `dcs_data.beacons.parse_beacons_lua`) against the real
  installed files, not by trusting the recon note: Kola 787 towns / 69 beacons, Caucasus 1759
  towns / 164 beacons — exact match to `EXPECTED_TOWN_COUNT`/`EXPECTED_BEACON_COUNT` and to the
  recon note.
- **Beacon self-consistency test's three hardcoded points** (Kola/Ivalo `airfield18_0`, Kola/Kemi
  `airfield3_0`, Caucasus/Tbilisi `airfield29_0`) — grepped each entry directly out of the real
  `beacons.lua`/`Beacons.lua` files and confirmed `position`/`positionGeo` match the test's
  literals exactly (x/z/lat/lon all verified byte-for-byte against the installed file).
- **Test is not vacuous**: perturbed `THEATRE_PROJECTIONS["Kola"].false_easting` by 102 m and
  reran `pytest -k Kola` — both Kola-parametrized cases failed with a 101.6 m residual (threshold
  is 0.2 m), confirming the test would actually catch a wrong projection parameter, not just
  pass by construction.
- **Projection residual claims, re-derived independently and more broadly than the test covers**:
  wrote a throwaway script using the registered `coordinates.dcs_to_wgs84` against *every* beacon
  in each theatre's real `beacons.lua` (not just the 1-3 sample points the committed test uses):
  Kola (n=69) rms=0.0363 m / max=0.0571 m; Caucasus (n=164) rms=0.0383 m / max=0.0649 m. These
  match the recon note's claimed rounded-value fit (Kola rms 0.0364/max 0.0573; Caucasus rms
  0.0385/max 0.0655) to the fourth decimal — the registered parameters are not just plausible,
  they reproduce the full beacon set, not only the three points the test samples.
- **Region rectangle arithmetic**, recomputed `centre_x/z` and `half_extent_x/z_m` by hand from
  the recon note's own stated padded raw-union bounds for both theatres — all four values for
  each theatre match the diff's `REGIONS["caucasus-full"]`/`REGIONS["kola-full"]` entries (to
  within 0.05, a harmless midpoint-rounding artifact, same pattern as the existing
  `afghanistan-full`/`syria-full` entries).
- **OSM clip bboxes**: ran `tools/derive_m9_osm_clip_bbox.py caucasus-full` and `kola-full` against
  the snapshot — both outputs match RUN.md §8.1's `osmium extract -b ...` commands exactly,
  character for character.
- **Staged raw data**, checked against the main checkout (read-only, nothing written there):
  194 Kola `.hgt` files, 123 Caucasus `.hgt` files (both match the recon note and RUN.md's
  implicit expectations); Kola OSM extracts present (`finland`, `northwestern-fed-district`,
  `norway`, `sweden`); Caucasus OSM extracts present (`armenia`, `azerbaijan`, `georgia`,
  `north-caucasus-fed-district`, `south-fed-district`, `turkey-260911` reused from the Syria
  build as RUN.md's comment states).
- **Other theatre-enumeration sites**: grepped `body-layer/src`, `mission-interpreter/src`,
  `aircraft-layer/src` for `"Syria"`/`"Afghanistan"` literals — the only live code reference is
  `body-layer/src/logger.py`'s `THEATRE_PROJECTIONS`-keyed mismatch guard (theatre-generic, reads
  the registry rather than enumerating theatres; confirmed by reading the actual code around line
  1949, not just the commit message's claim). `raster/registration.py`'s
  `THEATRE_RASTER_REGISTRATIONS` still has only `"Syria"` — correctly left alone, as the recon
  note's Q6 explicitly scoped out (no serving-path consumer, only two diagnostic tools, same
  reasoning the Afghanistan plan already applied). No missed enumeration site found.
- **Invariants**: no DCS installation writes (read-only investigation only); no coordinate math
  outside `coordinates/`; provenance/confidence present on both new `TmercParams` entries
  (`confidence="provisional"`, with a `source` string naming the pydcs cross-check, the beacon-fit
  method, and the exact residuals); no unverified DCS-internals claim encoded without a
  `research/` citation — both new registry entries' docstrings/comments cite
  `world-model/research/2026-10-05-kola-caucasus-theatre-recon.md` directly; `git status
  --porcelain` after the reviewed commit is clean, no raw/generated data staged.
- **Verification commands** (world-model's own, per its `CLAUDE.md` "Commands"), run against the
  isolated snapshot:
  - `ruff format --check src tests` — 118 files already formatted.
  - `ruff check src tests` — all checks passed.
  - `mypy src` (run from inside `world-model/`, per the CWD-only config-discovery trap) — success,
    no issues in 72 source files.
  - `pytest tests -q` — 568 passed, 3 skipped (pre-existing skips, unrelated to this change). The
    three new parametrized cases (`Kola-Ivalo`, `Kola-Kemi`, `Caucasus-Tbilisi`) all pass.

## Required Fixes

None.

## Optional Refinements

- `world-model/ROADMAP.md`'s "Multi-theatre support" backlog entry still reads "Caucasus/Kola
  themselves remain backlog" as of `main` — this commit doesn't update it, so the roadmap will lag
  behind the registry landing until a follow-up commit touches it. Low-cost, same pattern flagged
  as optional in prior reviews of incremental theatre work (not a blocker — this commit is
  explicitly scoped as "registry entries only," one stage of what will likely be a longer build
  sequence, not a milestone-completion claim that `CLAUDE.md`'s "Milestone Completion" rule would
  apply to). (Optional.)
- No `plans/multi-theatre-caucasus-kola/plan.md` exists — the work was derived directly from the
  research note's own "Possible Approaches" recommendation rather than going through a fresh
  Architect pass. Given the pattern is already fully exercised end-to-end by the merged Afghanistan
  work, and every number in this diff traces cleanly to the dated research note, this is a
  reasonable judgment call under the Escalation Rules (local, reversible, no new architectural
  ambiguity) rather than a process gap — noting it only so a reader doesn't go looking for a plan
  file that was never written. (Optional / informational.)
- `world-model/data/afganistan-full-build.log` and `world-model/afghanistan-full-build.log` sit
  untracked in the **main checkout** (not this branch, not this commit — confirmed by `git show
  --stat` on `45bac42` showing only the 6 declared files). Out of scope for this review since
  they're not part of the reviewed commit, but worth a mention since one is misspelled
  ("afganistan") — likely leftover from an ad hoc build run, harmless if never staged. (Optional /
  housekeeping, not this branch's responsibility.)

## Verdict

**APPROVED**

Every number in the diff was independently reverified against either the real installed DCS files,
the real parser code, or hand-recomputed arithmetic from the recon note's own stated bounds — none
of it required trusting the note or the commit message at face value. The beacon self-consistency
test was empirically confirmed to be non-vacuous. No invariant violations, no scope drift (the diff
is exactly what the commit message claims, nothing more), no misplaced coordinate math, no stray
raw data staged. Format/lint/type/test all pass clean on the isolated snapshot.

This lands the registry entries only — no `.sqlite` build, no live `coord.LOtoLL` probe. Both
projections stay `confidence="provisional"` until that live check, per the recon note's own
upgrade path (same posture Afghanistan held pre-Stage-4). There is nothing here for a pilot to fly
yet — the acceptance step is the eventual theatre build + live projection probe on the Windows box,
not this commit.

## Review Confidence

Full read. All six changed files read in full; every claimed number (projection parameters,
residuals, region rectangle corners, town/beacon counts, DEM/OSM staged-file counts, clip bboxes,
beacon test literals) was independently reproduced or hand-verified rather than spot-checked.
