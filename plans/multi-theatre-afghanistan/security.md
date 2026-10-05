## Security Deep Analysis: multi-theatre-afghanistan

Analysed at `58fa966` (confirmed via `git rev-parse HEAD` after `git checkout --detach 58fa966`),
diff base `14ca593..58fa966`. Reviewer approved at this tip (`plans/multi-theatre-afghanistan/review.md`).

### Dependency Status

No dependency change. The diff is entirely within `world-model/` (registries, parsers, a new
one-off tool) and `body-layer/` (`logger.py`, `belief/mission_phase.py`); no new import of a
third-party package appears anywhere in the diff.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/logger.py` (Stage 5 derivation block, `elif mission_data is not None:`) | Untrusted-field-into-filesystem-path / SQLite URI injection | **Confirmed exploitable.** `theatre = mission_data.theatre.value` is used unsanitized in `world_model_db = args.world_model_dir / f"{theatre.lower()}-full.sqlite"`, then fed into the pre-existing `open_world_model()` (`perception/geometry.py:65`, `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`). See demonstration below. | **Must fix before DoD.** |
| `body-layer/src/logger.py` (same block) | Unhandled exception on guard failure | `guard_conn = open_world_model(world_model_db)` / `load_only_region(guard_conn)` has no `try/except` around the open+query; any `sqlite3.Error` (bad path, not-yet-built theatre store, corrupted file) propagates as a raw traceback instead of a clean `parser.error`. | Optional, present to user below — not a vulnerability on its own, but compounds the finding above and is a plain robustness gap either way. |
| `body-layer/src/belief/mission_phase.py` `_parse_theatre` | Missing content validation | Validates `value`/`epistemic_status` are `str` and `basis` is `list[str]`, but places **no constraint on the content** of `value` (the theatre name) beyond being a string. | Covered by the fix for the first row — see Required Fixes. |
| `mission-interpreter/src/miz/reader.py:123` | Untrusted source, confirmed | `theatre = str(mission.get("theatre", theatre_text)) or theatre_text` is the raw `.miz` Lua-table/zip-root string, carried through `world_enrich/enrich.py` → `schema/build.py` (`Tagged(value=enriched.theatre, epistemic_status="FACT", ...)`) with **zero validation anywhere in that chain** against a known theatre name or a safe charset. This confirms the field really is attacker-reachable, not a false alarm — out of this plan's file list, cited for context only, not a required fix here (mission-interpreter is a separate subproject/milestone). | Informational — fix belongs at the body-layer consumption point (see below), not mission-interpreter. |
| `world-model/src/dcs_data/towns.py`, `beacons.py`, `build/region.py`, `build/pipeline.py`, `coordinates/projections.py`, `tools/derive_afghanistan_full_region.py`, `tools/derive_m9_osm_clip_bbox.py` | n/a | All inputs here are operator-typed CLI args or hardcoded registry dict literals — no untrusted-input path. `pipeline.py`'s `Source(name=routes_path.name)` fix is a pure provenance-string correction, not a new input surface. | None — clean. |

### Demonstration (reproduced, not theoretical)

The fields and call chain are real and already merged in this diff:

- `mission["theatre"]` is attacker-editable: a `.miz` is a zip containing a Lua mission table; the
  `theatre` field is a plain string with **no validation anywhere in mission-interpreter**
  (`miz/reader.py:123` → `world_enrich/enrich.py:67` → `schema/build.py:50-51`). DCS missions are
  routinely downloaded from community sites in single-player, so this is externally-sourced
  content even though the project is otherwise single-user/LAN-only — the untrusted boundary is
  the mission file, not the network.
- That string reaches `body-layer/src/logger.py`'s new Stage 5 branch unmodified except for
  `.lower()`, and is used to build a path:

  ```python
  theatre = mission_data.theatre.value
  world_model_db = args.world_model_dir / f"{theatre.lower()}-full.sqlite"
  ```

  Reproduced directly against `pathlib` (this is standard, documented `Path.__truediv__`
  behaviour, not a bug in this plan's code — but this plan is the first place in the repo that
  feeds it an externally-sourced string):

  ```
  >>> PurePosixPath('/data/theatres') / '/etc/passwd-full.sqlite'
  PurePosixPath('/etc/passwd-full.sqlite')          # --world-model-dir silently discarded
  >>> PurePosixPath('/data/theatres') / '../../etc/cron.d/evil-full.sqlite'
  PurePosixPath('/data/theatres/../../etc/cron.d/evil-full.sqlite')   # traversal
  >>> PureWindowsPath('C:/data/theatres') / 'C:/Windows/System32/evil-full.sqlite'
  PureWindowsPath('C:/Windows/System32/evil-full.sqlite')             # drive override
  >>> PureWindowsPath('C:/data/theatres') / '//server/share/evil-full.sqlite'
  PureWindowsPath('//server/share/evil-full.sqlite')                  # UNC override
  ```

  So a `mission["theatre"]` value of `"/etc/passwd"` (or, on the Windows box this project actually
  deploys to per `AGENTS.md`/body-layer's cross-machine workflow, a UNC form like
  `"//attacker-host/share/x"`) makes `world_model_db` **ignore `--world-model-dir` entirely** and
  resolve to an attacker-chosen path (suffix forced to end in `-full.sqlite`, nothing else
  constrained). The UNC form is the more serious of the two in this project's actual deployment:
  an unsolicited outbound SMB connection to an attacker-controlled host, triggered purely by
  loading a mission file, is the standard "forced authentication" vector used to capture Windows
  NTLM credentials — this is not a theoretical escalation, it is one of the best-known classes of
  "attacker controls a file path that gets opened" bug on Windows.

- Separately, and more surprising: `open_world_model()` (pre-existing, `perception/geometry.py:65`,
  not touched by this diff but newly fed attacker-influenced input by it) builds a SQLite URI by
  plain string interpolation: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`. Reproduced
  directly, this session, in this worktree's `body-layer` venv:

  ```python
  >>> db_path = ".../does-not-exist?mode=rwc&dummy=-full.sqlite"
  >>> uri = f"file:{db_path}?mode=ro"
  >>> conn = sqlite3.connect(uri, uri=True)
  >>> conn.execute("select 1")   # succeeds
  ```

  Result: SQLite's URI parser stopped the **filename** at the attacker's injected `?`, treated
  `mode=rwc&dummy=-full.sqlite?mode=ro` as the **query string**, and took the attacker's `mode=rwc`
  over the code's own trailing `?mode=ro` — the file was opened in read-write-**create** mode, and
  a brand-new empty file appeared on disk at the truncated path (confirmed with `ls`). This means a
  theatre string containing a bare `?` doesn't even need `/`/`..`/drive-letter tricks to control
  *which path gets opened* (SQLite truncates there regardless of what follows), and a `?mode=rwc`
  (or `&vfs=...`) suffix defeats the `mode=ro` the code explicitly relies on as its read-only
  safety contract — this is the mechanism the project's own body-layer/world-model seam depends on
  for "read-only access to world-model data," and this plan is what first lets an attacker steer
  the argument that builds that URI.

### Silent-wrong-position angle (the thing Stage 5's guard was built to prevent)

The mismatch guard compares `built_region.theatre != theatre` where `theatre` is the *same*
attacker-controlled string used to build the path. An attacker who can also place or predict
content at the resolved path (e.g. via a traversal string pointing at a real, stale, or
differently-built store elsewhere on disk with a `region.theatre` column that happens to match
their own crafted string) makes the guard pass trivially, because it only checks string equality
between two values the attacker influences jointly — it does not check that the resolved path
stays inside `--world-model-dir`. In the pure "edit one mission file, nothing else" threat model
this is a secondary concern (the attacker doesn't control filesystem content elsewhere without
separate access), but it means the guard is not the safety boundary the plan's own narrative
("stands between Petrovich's world knowledge being right and being silently, confidently wrong")
describes it as — the real boundary needs to be the input validation below, applied before any of
this is reachable.

### Verdict

**NEEDS FIXES**

Everything the Reviewer checked (Stages 1, 2, 3, the mismatch-guard's logic for the two explicit-
flag and one artifact-derived happy/reject paths already under test) is correct and the checks
reproduce. The gap is specific and narrow: the new theatre-from-mission-understanding derivation
in `logger.py` passes an externally-sourced string into a path join and (transitively) a SQLite URI
with no validation at all, and this project's own existing read-only-DCS-access / no-silent-wrong-
output invariants are both directly implicated.

### Required Fixes

1. **Validate `theatre` immediately after derivation, before it is used to build any path** —
   `body-layer/src/logger.py`, the `elif mission_data is not None:` branch (currently around where
   `theatre = mission_data.theatre.value` is assigned). Reject with `parser.error(...)` naming the
   offending value if it is not a known theatre name. The cheapest correct check is membership in
   world-model's own `coordinates.projections.THEATRE_PROJECTIONS` registry — body-layer already
   imports world-model's `coordinates` package in-process elsewhere
   (`perception/association.py:62`), so this is the existing coupling, not a new one, and it is
   also the *correct* functional check: a theatre with no projection entry can't do anything useful
   downstream anyway. A defense-in-depth charset check (e.g. `^[A-Za-z][A-Za-z0-9]*$`) alongside the
   registry check is cheap insurance against a future registry entry ever containing a stray
   special character, but the registry check alone closes every path/URI vector demonstrated above
   (none of `Syria`/`Afghanistan`/`Caucasus` contain `/`, `\`, `?`, `#`, `&`, or `..`).
2. **File:Line** — `body-layer/src/logger.py`, Stage 5 derivation block (the `elif mission_data is
   not None:` branch, immediately after `theatre = mission_data.theatre.value`).

### Optional (not blocking, raise if touching this code again)

- Wrap the mismatch guard's `open_world_model(world_model_db)` / `load_only_region(guard_conn)` in
  a `try/except (sqlite3.Error, OSError)` that turns a failure into a clean `parser.error` naming
  the path. Right now even a *legitimate*, validated theatre with no store built yet for it crashes
  with a raw traceback instead of a readable message — a usability gap, not a vulnerability, but
  worth folding into the same fix pass since it touches the same four lines.
