### Review Summary

Reviewed M4 (`feature/m4-dcs-elevation`, 6 commits) against `plans/m4-dcs-elevation/plan.md`,
`world-model/CLAUDE.md`, `docs/CONVENTIONS.md`, and the M1-M3 structural precedent. Read every
changed source/test/tool file in full, ran the full verification sequence myself, and checked the
delta-report reasoning in the research note against the actual numbers.

**Verification (re-run, not trusted from the report):**
- `ruff format --check world-model/src world-model/tests` — 18 files, all formatted.
- `ruff check world-model/src world-model/tests` — all checks passed.
- `mypy world-model/src` (`--strict`) — success, no issues, 10 source files.
- `pytest world-model/tests -q` — 30 passed.

All four commands match the implementer's claims exactly.

**Structure/scope:** `src/elevation/` mirrors `coordinates/`/`osm/` (module docstring + `__all__`,
DCS-side parsing vs. external-source parsing split into two files). `tools/inspect_elevation.py`
mirrors `inspect_osm_overlay.py`'s CLI pattern. Coordinate math stays confined to
`coordinates.dcs_to_wgs84`, consumed as-is by `inspect_elevation.py` — no inline reimplementation
in the new module, as the plan required. No changes to `src/coordinates/`, `src/raster/`,
`src/osm/`, matching the plan's stated no-touch list. Scope matches the plan closely; the only
plan deviation (`net.log` → `io.open`, prompted by the user's in-session io/lfs authorization) is
recorded and justified in the plan's own edit history, not silently introduced.

**Tests:** both `test_dcs_grid.py` and `test_dem_srtm.py` verified to use real collected/downloaded
data, not fabricated fixtures — `test_dcs_grid.py`'s 8-point fixture is a literal copy of Stage 1's
real live-mission probe output (provenance comment points at the gitignored raw file), and
`test_dem_srtm.py`'s 5x5 grid is a literal crop of real int16 samples read from the actual
`N39E036.hgt` tile, with a derived (not fabricated) `span_deg` for that crop's true geographic
extent. The control-point test (`test_height_at_gemerek_control_point`, Gemerek's published
1,204m elevation, 50m tolerance) satisfies `world-model/CLAUDE.md`'s "every coordinate/spatial
function needs a control-point test" rule, reusing the same Gemerek point already validated in
`test_raster_registration.py`. Both null-height and void-sample failure modes are tested, not just
the happy path.

**Data hygiene:** `world-model/data/raw/dcs/2026-09-03/` and `world-model/data/raw/dem/` are both
covered by `world-model/.gitignore`'s `data/raw/` rule (confirmed via `git check-ignore -v`); `git
ls-files world-model/data` returns nothing. No raw/generated data staged for commit.

**Read-only/invariant check:** `elevation_probe.lua` and `collect_elevation_log.sh` only write to
`Saved Games/DCS/Logs/`, never to the DCS installation itself. The `MissionScripting.lua` io/lfs
edit is a separate, explicit, user-authorized manual step (not performed by any script in this
diff), consistent with the investigator recon and the plan's "Decisions Requiring User Input"
resolution — this was directly confirmed by the user in-session per the plan/task framing, not an
agent-relayed claim.

**Delta-report reasoning (research note, `2026-09-03-m4-dcs-elevation.md`):** the
terrain-mesh-resolution-mismatch conclusion is reasonably well-supported, not hand-waved. The note
correctly applies the plan's own pre-registered distinguishing test (systematic/uniform delta =
datum mismatch signature vs. spatially-localized/sign-varying = mesh-resolution noise) and shows
its work: walking the west-edge column row-by-row to demonstrate a smooth gradient rather than a
discontinuous jump, and noting the 9 largest-magnitude outliers cluster in two identifiable regions
rather than being scattered. It also correctly declines to over-claim — explicitly states the
vertical-datum question remains open, not resolved, and that this dataset merely "doesn't obviously
demand" a datum-offset explanation. One nuance the note doesn't fully unpack: the 76/24
positive/negative split and +13.89m mean is a real lean, not just noise around zero, and could
partly reflect a modest systematic component riding underneath the localized noise rather than
being purely mesh-resolution artifact — the note's own framing (mean "modest relative to the full
range") acknowledges this without fully resolving it. This is a fair reading of ambiguous data, not
a required fix — flagged as optional below.

### Required Fixes

- **Uncommitted files must be staged before this is done.** `git status` shows unstaged
  modifications to `.claude/agent-memory/architect/MEMORY.md`,
  `.claude/agent-memory/investigator/MEMORY.md`, `.claude/agent-memory/skill-candidates.md`,
  `plans/m4-dcs-elevation/plan.md`, and two new untracked files
  (`.claude/agent-memory/architect/feedback_agent_relayed_consent.md`,
  `.claude/agent-memory/investigator/project_m4_elevation_recon.md`). `CLAUDE.md`'s Definition of
  Done requires "all new/modified files staged and committed... confirm a clean working tree"
  before declaring the task complete. None of this is a code-quality problem — the content itself
  looks appropriate (plan.md's edit history, agent memory notes) — but it needs to be staged and
  committed (or explicitly reviewed for whether it belongs in this branch at all) before DoD.

### Optional Refinements

- The research note's positive/negative asymmetry (76/24 split, +13.89m mean) could be called out
  more explicitly as "a modest systematic lean layered under spatially-localized noise, not
  necessarily either pure noise or a pure datum offset" — the current framing is defensible but
  slightly understates how much of a lean +13.89/median +16.61 actually is relative to the
  point-to-point stddev of 28.02m. Worth a sentence if this region's data ever becomes load-bearing
  for M6 terrain semantics; not blocking for M4's stated goal (proving the extraction/comparison
  method).
- `tools/inspect_elevation.py`'s printed compare output doesn't inline the DEM source/version or
  DCS build version the way the research note does — all of that provenance exists in `research/`
  and the module docstrings, just not in the CLI's own stdout. Not required (this is a diagnostic
  tool, not a persisted artifact — unlike M3's PNG overlay, there's no saved output for provenance
  to travel with), but would make ad-hoc terminal runs a little more self-describing.

### Verdict

APPROVED WITH MINOR FIXES
