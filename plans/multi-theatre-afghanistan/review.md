### Review Summary

Reviewed `feature/multi-theatre-afghanistan` at tip `381f828` (confirmed via `git rev-parse HEAD`
after `git checkout --detach 381f828`) against `plans/multi-theatre-afghanistan/plan.md` Stages
1, 2, 3, 5 (Stage 4 is explicitly a pending user live-DCS task) and
`plans/multi-theatre-afghanistan/implementation.md`. Diff base `14ca593`.

Scope matches the plan closely. All five "Affected Modules / Files" entries for Stages 1/2/5 are
touched as described; the two extra files touched (`test_towns_lua.py`, `test_beacons_lua.py`)
are correctly flagged by the implementer as an omission in the plan's own "Affected Modules"
list, not scope creep — both call the real parsers directly and needed the same signature/
monkeypatch fix. Stage 3's real build is documented in a new dated research note and a new
`RUN.md` §7, both consistent with each other and with what the sqlite store (independently
queried below) actually contains. No code outside `world-model/` and `body-layer/` was touched;
no out-of-plan commits appear in the branch's history.

**Checks — reproduced independently, fresh venvs created per each subproject's own `RUN.md`/
`CLAUDE.md` setup instructions (none existed in this worktree beforehand):**

| subproject | ruff format --check | ruff check | mypy --strict | pytest |
|---|---|---|---|---|
| world-model | pass (116 files; `src`/`tests` only, per Commands) | pass | pass, 71 source files | 542 passed, 3 skipped |
| body-layer | pass (114 files) | pass | pass, 53 source files | 1402 passed, 4 xfailed |

All four numbers match the implementer's own report in `implementation.md` exactly. The two
"pre-existing unformatted" files the implementer names (`tools/m7_kola_square_distortion_probe.py`,
`tools/validate_m7_stage3.py`) are real but fall outside `ruff format`'s own `src`/`tests` scope
(confirmed by running `ruff format --check` on them directly — both fail) — correctly out of
scope, not a hidden gap.

Invariant checks specific to this plan:
- **Provenance/confidence**: `THEATRE_PROJECTIONS["Afghanistan"]` carries `confidence=
  "provisional"` with a `source` string stating exactly what would upgrade it (Stage 4's live
  probe) — matches the project's "preserve provenance/uncertainty" invariant. The new
  self-consistency test (`test_afghanistan_provisional_fit_self_consistency`) explicitly
  disclaims itself as *not* a live/real-world check, in both the test docstring and
  `region.py`'s comment and `RUN.md` §7.2 — the M1 circularity caveat is stated three times,
  consistently.
- **DCS-internals claims recorded in `research/`**: both the Stage 2 pre-check (`mission["theatre"]
  = "Afghanistan"`, confirmed against a real campaign `.miz`, not assumed) and the Stage 3 build
  results are written to a dated `world-model/research/2026-10-05-afghanistan-theatre-build.md`
  note before being relied on elsewhere (RUN.md, region.py's comment cite it).
- **Read-only DCS access**: every new/changed code path only reads `towns.lua`/`beacons.lua`/
  `.routes`/`AirfieldsTaxiways` paths; nothing writes under the DCS install tree. Confirmed by
  reading `build_world_model.py`'s CLI usage in the research note and `ingest_*` modules — no
  write calls into `/mnt/f/Games/DCS World/...` anywhere in the diff.
- **`world-model/data/` stays gitignored**: `git status --porcelain` is clean at `381f828`; the
  878 MB `afghanistan-full.sqlite` + caches are not staged (confirmed `git status` and a direct
  `git log`/`diff --stat` walk show no `data/` paths touched).
- **Coordinate math confined to the coordinate subsystem**: the new region-derivation tool
  (`derive_afghanistan_full_region.py`) calls `coordinates.wgs84_to_dcs` rather than
  reimplementing the projection — correct placement.
- **Mismatch guard (Stage 5) is real, not decorative**: traced `logger.py`'s `main()` directly —
  `open_world_model(world_model_db)` → `load_only_region(guard_conn)` → compares
  `built_region.theatre != theatre` → `parser.error`. The new test
  `test_main_rejects_world_model_db_theatre_mismatch` builds a real on-disk store with
  `theatre="Afghanistan"` and asserts `--theatre Syria` against it is rejected — not a trivial
  fixture, it exercises the actual comparison path end to end via `sys.argv` + `SystemExit`.

**Per this role's own standing check** ("grep for the new mechanism's own call site, not the file
list"): Stage 1's dict-ification of `EXPECTED_TOWN_COUNT`/`EXPECTED_BEACON_COUNT` and the
`theatre` parameter threading were verified by grepping every call site of `parse_towns_lua`/
`parse_beacons_lua` across both `src/` and `tests/`, not just the plan's named files — all six
call sites (two in `pipeline.py`, two test monkeypatch fixtures already named in the plan, plus
the two un-named `test_towns_lua.py`/`test_beacons_lua.py` direct-call sites) are updated
consistently. No site was missed.

### Required Fixes

None.

### Optional Refinements

- `body-layer/src/belief/mission_phase.py`'s `load_mission_understanding` now has a second,
  explicit `if not isinstance(raw, dict): raise ValueError(...)` at the top of the function,
  duplicating the identical check already inside `_require_list(raw, "phases")` (called a few
  lines later with the same message). Harmless — `_require_list` would already raise before
  `raw["theatre"]` is ever reached if `raw` were not a dict — but it is now stated twice. Not
  worth a fix commit on its own; worth collapsing next time this function is touched. (optional)
- The Afghanistan junction/airfield findings below are not required fixes (see "Findings"), but
  are worth a short pointer added to `world-model/research/2026-10-05-afghanistan-theatre-build.md`
  or the M10 backlog note the next time either file is touched, so a future reader of the
  Afghanistan build results isn't left to independently re-derive why `junction: 196` looks sparse
  next to Syria's `junction: 8732`. (optional, not blocking this branch)

### Findings (requested investigation)

**1. Junction sparsity: real, not a defect — a known, already-backlogged detector limitation that
happens to bite Afghanistan much harder than Syria, for a data-authoring reason, not a bug in this
plan's code.**

`src/roadnet/junctions.py`'s own docstring already states, as a pre-existing backlog item
(M10, not touched by this plan): endpoint-endpoint and endpoint-interior (T-junction) coincidences
are detected via grid-bucketed union-find; **interior-interior crossings (a road crossing another
mid-span, with neither having an endpoint there) are never unioned, "out of scope for this pass,"
flagged as backlog.** This plan ran that unchanged detector against Afghanistan's new road data —
it did not modify or need to modify it, correctly per the plan's own silence on junction detection.

Measured directly against the real built stores (not estimated):

- **10 km x 10 km window around Kabul** (`afghanistan-full.sqlite`): 13,366 road segments pass
  through the window; grid-bucketed segment-segment intersection testing finds 166 distinct
  road-ID pairs that geometrically cross, of which 28 cross exactly once (a clean, non-coincident
  crossing) and 138 cross many times (near-duplicate/coincident polylines — the same false-positive
  population the module's docstring already documents). **All 28 of the clean single crossings are
  >1 m from either road's own endpoint — i.e. 100% are pure interior-interior crossings, which this
  detector was never designed to catch.** Only 2 `junction` features exist in this same window.
- **10 km x 10 km window around Damascus** (`syria-full.sqlite`, same method): 113,651 segments,
  207 clean single-crossing pairs, **also 100% interior-interior** (0 within 1 m of an endpoint).
  167 `junction` features exist in this window.

So the detector's blind spot is identical in both theatres — it misses essentially all pure
crossings everywhere, not just in Afghanistan. The theatre-wide junction *density* gap
(1 per ~400 km of road in Afghanistan vs 1 per ~42 km in Syria) is not explained by the detector
behaving differently; it is explained by how differently the two theatres' `.routes` files are
segmented: Afghanistan averages ~51 km per `road` feature (1,590 roads / ~81,000 km) against
Syria's ~24.7 km (14,833 / ~366,000 km) — Afghanistan's road network is authored as roughly half
as many, much longer polylines relative to its road length, giving far fewer explicit route
splits (and therefore far fewer endpoint-based coincidences the detector *can* catch) per km of
road than Syria's more finely segmented network. This is a property of DCS's own Afghanistan
terrain-module authoring, not something `parse_towns_lua`/`.routes` parsing or this plan's code
introduced or could fix by itself.

Also checked, per the task's specific prompt: **`resync_events=1590` matching `routes_found_
whole_file=1590` exactly is expected, not a parsing defect.** `roadnet/routes.py`'s own
`RouteWalkStats.resync_events` docstring states it "counts every route boundary (normal and
expected — the trailer is always skipped by scan, never parsed)" — one resync event per route is
the designed behaviour of this container format's trailer-skipping, not a sign the parser
under-split anything. `sync_loss_events=22` (a small fraction of 1,590, same order as Syria's own
roadnet note documents as normal) is the actual health signal, and it is unremarkable.

**Net:** real, and worth a documentation pointer (see Optional Refinements) given the stated pilot
relevance (junctions as a navigation landmark), but not a defect this branch introduced, and not
something this plan's own scope committed to fixing — fixing the detector's interior-interior blind
spot is exactly the backlog item `junctions.py`'s docstring already names, unrelated to
multi-theatre support.

**2. Airfields: 7 of 26 is by-design (beacon-derived only), confirmed, with a concrete upgrade
path already available once Stage 4 runs.**

`src/build/ingest_beacons.py` derives an `airfield` feature only from a `beacons.lua`
`airfield<N>_<M>` group (`_parse_airfield_group`'s regex) — an airfield with zero navaids
(no TACAN/VOR/NDB/ILS at all) produces no `airfield_group` and is invisible to this layer. No
other source (towns.lua, OSM, `.routes`) ever contributes an `airfield` feature. Directly listed
`"/mnt/f/Games/DCS World/Mods/terrains/Afghanistan/AirfieldsTaxiways/"`: **26** distinct airfields
ship taxiway data (Bagram, Bamyan, Bost, Camp_Bastion, Camp_Bastion_Heli, Chaghcharan, Dwyer,
FOB_Salerno, Farah, Gardez, Ghazni_Heliport, Herat, Jalalabad, Kabul, Kandahar, Kandahar_Heli,
Khost_Dirt_Airfield, Maymana_Zahiraddin_Faryabi, Nimroz, Qala_i_Naw, and others cut off by the
listing), confirming the task's "~26" figure. The 7 beacon-derived ones (Bastion, Dwyer, Herat,
Kandahar, Shindand, Bagram, Kabul) are exactly the subset that happen to carry navaids.

**Consumer check**: grepped the whole repo for `nearest_airfield`/`AirfieldInfo` — the only
consumer is `query/describe.py`'s own `PositionDescription.nearest_airfield` field, read only by
the diagnostic CLI `tools/describe_position.py` (prints the whole dataclass as JSON). Neither
body-layer nor mission-interpreter references `nearest_airfield` anywhere. **This gap has the same
shape as the plan's own stated raster-registration exclusion** ("nothing in the serving path
consumes it, only diagnostic tools") — it currently costs a pilot nothing on a live sortie.

**Recommendation** (not built, per the task's instruction): the pending Stage 4 live probe
(`tools/dcs-mission-probe/coord_probe.lua`) already calls `world.getAirbases()` and records every
entry's `name`/`x`/`z`/`lat`/`lon` into `out.airbases` — `world.getAirbases()` enumerates DCS's
actual airbase registry (the same source that drives in-game ATC/parking, "includes airports,
FARPs, ships with decks" per the script's own comment), independent of beacons.lua, so it would
return all ~26 Afghanistan airfields regardless of navaid presence. When Stage 4 runs, its output
JSON is a ready-made, independently-sourced full airfield name+position list — a natural seed for
widening `ingest_beacons.py`'s airfield derivation (or adding a second airfield source) in a later
milestone, not this one. Flagging this as a found upgrade path, not asking for it to be built now.

### Verdict

**APPROVED**

Stages 1, 2, 3 and 5 match the plan, all checks reproduce cleanly and match the implementer's own
report exactly, and the two investigated open questions are both genuine data-authoring/scope
findings rather than defects in this branch's code. No required fixes. Stage 4 remains correctly
deferred to the user (Windows DCS box, live mission) — nothing in this branch depends on it having
run, and `confidence="provisional"` is preserved everywhere it should be until that happens.

### Review Confidence

Full read of the diff and both new/changed research/RUN.md documents. Checks (`ruff format
--check`, `ruff check`, `mypy --strict`, `pytest`) were re-run from scratch in fresh venvs in both
touched subprojects, not taken on the implementer's word. The two investigation questions were
answered by directly querying the real built `afghanistan-full.sqlite`/`syria-full.sqlite` stores
(geometric crossing counts, junction counts, airfield/beacon counts) and by listing the real
`AirfieldsTaxiways/` directory on the Windows-mounted DCS install — not inferred from documentation
alone.

### Fix review (f7f2827)

Reviewed the security fix chain `58fa966 → 5e30050` (security review) `→ 8a777c8` (performance
review, independent, no code touched) `→ f7f2827` (fix), checked out detached at `f7f2827`
(confirmed via `git rev-parse HEAD`). Diff scope `8a777c8..f7f2827`: `body-layer/src/logger.py`,
`body-layer/tests/test_logger.py`, `plans/multi-theatre-afghanistan/implementation.md`, plus an
implementer agent-memory file — against `plans/multi-theatre-afghanistan/security.md`'s one
required fix and one optional item.

**Required fix — validation placement.** `theatre = mission_data.theatre.value` is immediately
followed by `if theatre not in THEATRE_PROJECTIONS: parser.error(...)`, strictly before
`world_model_db = args.world_model_dir / f"{theatre.lower()}-full.sqlite"` is built — the one
route security.md identified as attacker-reachable (an externally-sourced `.miz`-derived string
flowing through `mission_data.theatre.value`). Re-read the whole derivation block: the sibling
explicit-flag route (`args.theatre is not None and args.world_model_db is not None`) takes
`theatre`/`world_model_db` straight from operator-typed CLI args, never from the mission artifact,
so it has no parallel issue — this matches security.md's own clean-bill finding for that branch,
and I confirm it on reread rather than taking it on trust. The registry check uses exact-case
membership against `coordinates.projections.THEATRE_PROJECTIONS`'s real keys (`"Syria"`,
`"Afghanistan"`, …), consistent with the pre-existing `.lower()` suffix convention — no bypass via
case folding.

**Optional item — exception handling.** `guard_conn = open_world_model(world_model_db)` and
`built_region = load_only_region(guard_conn)` are both now inside one `try: ... except
(sqlite3.Error, OSError): parser.error(...)`, with `guard_conn.close()` kept in its own nested
`finally`. Traced both failure points: if `open_world_model` itself raises, the nested block is
never entered (no `UnboundLocalError` risk); if `load_only_region` raises after a successful
connect, the `finally` closes the connection before the exception reaches the outer `except`. The
mismatch check (`built_region.theatre != theatre`) sits *outside* this `try/except`, unaffected,
so the catch cannot mask a real theatre/store mismatch — it only converts a missing/corrupt-store
`sqlite3`/`OSError` into a clean `parser.error`. Nothing that should propagate is swallowed.

**Regression-test gap (required fix, found by empirical disable-and-rerun, not by reading).**
Per this project's own standing check, I disabled only the required fix (removed the
`THEATRE_PROJECTIONS` membership check, left the optional `try/except` in place) and reran the 5
new tests: **all 5 still passed.** The reason: the optional fix's broad `except (sqlite3.Error,
OSError)` converts *any* downstream failure — an unknown theatre's well-formed-but-nonexistent
path, an absolute/UNC override that lands outside `tmp_path`, or a malformed URI — into the same
generic `SystemExit`, and the four parametrized tests assert only `pytest.raises(SystemExit)` plus
`not any(tmp_path.glob("*-full.sqlite"))`. That glob assertion passes in every case regardless of
the required fix: the absolute/UNC payloads resolve outside `tmp_path` entirely (so no match
there either way), and the unknown-theatre payload simply doesn't exist on disk yet. Reverting
*both* the required and optional fix together does make all 5 tests fail (confirmed), so the
suite does catch total regression — but it does not catch the required fix specifically being
removed while the optional item remains, which is exactly the scenario a future unrelated edit to
this block could produce silently.

A second, smaller problem in the same test: the `"Syria?mode=rwc"` ("query-string-injection")
parametrize case does not actually reproduce the SQLite URI-injection security.md itself
demonstrated — that demonstration needed a second, `&`-separated query parameter
(`...?mode=rwc&dummy=-full.sqlite`) for SQLite's URI parser to split the string the way the attack
depends on. Reproduced directly in this worktree's venv: `"Syria?mode=rwc"` alone makes
`sqlite3.connect` raise `OperationalError: no such access mode: rwc-full.sqlite?mode=ro` (a
malformed access-mode string, not a successful mode override), while the security.md-shaped
payload with `&dummy=...` does create a stray file on disk exactly as that document describes.
The test's intent (prove the injection vector is closed) is right; the specific payload doesn't
exercise the mechanism it's named after.

**Why this is a required fix, not optional:** this is a security control, and the whole point of
a regression test here is to fail loudly if the registry check is ever weakened or removed later.
As written, that specific regression — the one the security review's entire "Confirmed
exploitable" finding is about — would pass silently. Fix by asserting on the *reason* for
rejection, not just that *some* `SystemExit` occurred: either assert the captured stderr contains
the registry-check's own message (`"not a known theatre"`), or monkeypatch `open_world_model` to
raise if called at all for the four rejected-theatre cases, proving the rejection happens strictly
before that call rather than merely before it is observed to matter. Also swap the
`"Syria?mode=rwc"` payload for one that actually reproduces the demonstrated injection (an
`&`-separated second parameter), so that test case is exercising the vulnerability its own name
claims.

**Checks reproduced** (no `.venv` existed in this worktree; created fresh, `cd body-layer`):

| ruff format --check | ruff check | mypy --strict | pytest |
|---|---|---|---|
| pass (114 files already formatted) | pass (All checks passed!) | pass (53 source files, no issues) | 1407 passed, 4 xfailed |

Matches the implementer's own reported numbers exactly.

#### Fix Verdict

**NEEDS REVISION** — one required fix: tighten the new tests so they actually fail when the
required-fix registry check specifically is removed (currently they only fail when *both* fixes
are removed together), and correct the query-string-injection payload to match the mechanism it
claims to test. The security fix's production code itself (`logger.py`) is correct and complete —
this is a test-coverage gap on a security-relevant control, not a code defect in the fix.

#### Fix Review Confidence

Full read of the diff. Empirically verified both the required fix's placement (reproduced the
explicit-flag route has no parallel issue) and the test gap (disabled the required fix alone,
reran; disabled both, reran) rather than inferring from the code or the implementer's note. All
four verification commands re-run from a fresh venv in this worktree, not taken on report.

### Fix review 2 (91fd8a1)

Re-review of the test-only follow-up to the "Fix review (f7f2827)" finding above. Checked out
detached at `91fd8a1` (confirmed via `git rev-parse HEAD`). Diff scope `c3bf204..91fd8a1`:
`body-layer/tests/test_logger.py` and `plans/multi-theatre-afghanistan/implementation.md` only —
no production code touched, matching the implementer's own note.

**What changed, against the two gaps this review raised:**

1. **Regression-test gap (required).** The test now asserts, independently of the `SystemExit`
   check: (a) `open_world_model` is never called — via `monkeypatch.setattr(logger_module,
   "open_world_model", _fail_if_open_world_model_called)`, a local `-> NoReturn` helper that
   `pytest.fail`s if invoked at all; and (b) the specific rejection reason via
   `assert "not a known theatre" in capsys.readouterr().err`. Either assertion alone now catches
   "required registry check removed, optional `except` left in place" — the exact regression the
   old test let through — because that regression's only observable path is reaching
   `open_world_model` with an attacker-influenced path and failing later with a *different*
   message than the registry check's own.
2. **Payload-mechanism mismatch (required).** `"Syria?mode=rwc"` → `"Syria?mode=rwc&x="`, matching
   my own suggested shape: a second `&`-separated query parameter, which is what makes SQLite's
   URI parser split the filename at the injected `?` — the mechanism `security.md` actually
   demonstrated, not the bare-`?mode=rwc` malformed-access-mode failure the old payload exercised.

**Verified independently, not taken on the implementation note** (per the dispatching
instructions): disabled only the required `THEATRE_PROJECTIONS` membership check
(`if theatre not in THEATRE_PROJECTIONS:` → `if False and theatre not in THEATRE_PROJECTIONS:`,
`try/except` left in place), reran the 4 parametrized cases — **all 4 failed**, each on
`pytest.fail` inside `_fail_if_open_world_model_called`, with the traceback showing
`open_world_model` reached with the attacker-controlled path (e.g.
`.../syria?mode=rwc&x=-full.sqlite` for the injection case). Restored the line exactly
(`git diff --stat -- src/logger.py` empty after restore, confirming a clean revert) and reran —
**all 4 passed** again (`4 passed, 69 deselected`). This reproduces the exact result the
implementation note claims, independently rather than by reading it.

Read `logger.py`'s resolution block (lines ~1870-1924) end to end again while here: the registry
check still sits strictly before `world_model_db` is built, the explicit-`--theatre`/
`--world-model-db` route still bypasses it correctly (operator-typed, never mission-derived), and
the mismatch guard's `try/except (sqlite3.Error, OSError)` is unchanged and still sits after the
registry check, not around it. No new issue found in production code, consistent with this diff
touching none.

**Checks** (`cd body-layer`, fresh `.venv` built in this worktree — none existed on checkout):

| ruff format --check | ruff check | mypy --strict (src) | pytest (full) |
|---|---|---|---|
| pass (114 files already formatted) | pass (All checks passed!) | pass (53 source files, no issues) | 1407 passed, 4 xfailed |

Matches the implementer's own reported numbers exactly.

#### Fix Review 2 Verdict

**APPROVED.** Both gaps from "Fix review (f7f2827)" are closed, verified empirically rather than
by reading: the test now fails specifically when the required registry check is removed (not just
when both fixes are removed together), and the injection payload now reproduces the mechanism
`security.md` actually demonstrated. No production code changed; none needed to change. This
closes the required fix from the earlier review — no further action needed before DoD.

#### Fix Review 2 Confidence

Full read of the diff (small — one test file, one plan note). Empirically reproduced the
disable-required-fix-alone / restore cycle myself rather than trusting the implementation note's
account of it; same result both times. Ran all four body-layer checks from a fresh venv built in
this worktree.
