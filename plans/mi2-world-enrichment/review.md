### Review Summary

Reviewed MI-2 (world-model's first HTTP server + mission-interpreter's `world_enrich` client/
enrichment walk) on `feature/mi2-world-enrichment` against the locked plan
(`plans/mi2-world-enrichment/plan.md`, commit `a849e47`) and `implementation.md`. Read every
changed source file directly (`world-model/src/api/server.py`, `__main__.py`,
`tests/test_api.py`; `mission-interpreter/src/world_enrich/{world_model_client,schema,enrich}.py`,
both new test files), plus the doc/roadmap diffs. Ran both subprojects' full verification suites
myself with correct per-subproject cwd, and independently reproduced the CWD-sensitivity mypy claim
by temporarily reintroducing the `no-any-return` bug.

All eight callout items in the review brief check out. No required fixes.

**Item-by-item:**

1. **Single-threaded `HTTPServer` deviation** — sound. `sqlite3.Connection` objects are genuinely
   not thread-safe by default in CPython (this is documented stdlib behavior, not a workaround for
   an unrelated bug), and the module docstring in `server.py` states the deviation, the reasoning,
   and the residual caller obligation (`check_same_thread=False` needed only because
   `serve_forever()` may run on a different thread than the one that opened the connection) in
   full — not silently dropped. For an offline, pre-mission batch consumer at "dozens of calls, not
   thousands" volume (the plan's own estimate), single-threaded is the right tradeoff; no live-rate
   consumer exists yet that would need concurrency.
2. **Axis-swap test** — genuinely load-bearing. `test_route_waypoint_maps_y_to_z_not_x` uses the
   fixture's `x=10, y=20` waypoint and asserts `(10.0, 20.0) in calls` **and**
   `(20.0, 10.0) not in calls`. A swapped-axis bug (`z=point.x` instead of `z=point.y`) would
   produce exactly `(20.0, 10.0)`, which the second assertion explicitly rules out — this is not a
   symmetric fixture that could pass by coincidence either way.
3. **`WorldModelClient` never swallows to `None`** — confirmed by reading all three `get_*` methods
   plus `_get_json`: every failure path (network/OSError, non-2xx via `URLError` subclassing, bad
   JSON, wrong top-level shape, wrong element shape, wrong `{"clear": bool}` shape) raises
   `WorldModelClientError`. No method has a fallback return value.
4. **`theatre` mismatch validation** — present (`_require_theatre` in `server.py`, checked on both
   `/describe_position` and `/line_of_sight`) and tested on both sides:
   `test_describe_position_theatre_mismatch_returns_400` /
   `test_line_of_sight_theatre_mismatch_returns_400` (server) and
   `test_get_describe_position_raises_on_theatre_mismatch` (client).
5. **Dropped `test_api_integration.py`** — the stated reason (mission-interpreter's venv lacks
   `pyproj`/`osmium`/`pillow`, and `api.server`'s import chain pulls in `coordinates`→`pyproj`) is
   real — confirmed by the module import chain in `server.py`. On the residual-gap question: the
   client is deliberately opaque (`dict[str, Any]` pass-through, no re-declared schema), so the
   *only* wire-format assumptions it actually encodes are "describe_position returns a JSON
   object," "find_place_by_name returns a JSON list of JSON objects," and "line_of_sight returns
   `{"clear": bool}}`" — and all three of those exact shape assumptions are independently exercised
   against the real server in `world-model/tests/test_api.py` (`isinstance(body, dict)`,
   `isinstance(body, list)`, `body["clear"] is True`). So the coverage gap is real but narrow: a
   field *rename* inside `PositionDescription` (e.g. `nearest_settlement` → something else) would
   not be caught by any test on either side, since `enrich.py` never inspects fields of the
   `position` dict it passes through. Worth a mention, not a blocker — see Optional Refinements.
6. **Parallel `Enriched*` tree** — confirmed directly in `schema.py`: every `Enriched*` dataclass
   wraps the original MI-1/MI-1.5 dataclass by reference (`group: Group`, `point: RoutePoint`,
   `zone: TriggerZone`) plus a `WorldRef`/`WorldRef | None`; none of `RoutePoint`/`Unit`/`Group`/
   `TriggerZone`/`CrewAvailableMission` gained new fields.
7. **Scope boundary held** — `_enrich_group` only ever reads `group.units[0]`, never iterates
   per-unit; `group.units` is carried through untouched on `EnrichedGroup`. `briefing`/
   `kneeboard_images` are passed through byte-for-byte with no parsing. No `find_place_by_name`
   call is made against briefing text anywhere in `enrich.py`.
8. **mypy CWD-sensitivity claim** — verified by direct reproduction, not just trusted. I
   temporarily reintroduced the exact class of bug described (`return result.get("clear")` with no
   `isinstance` narrowing, `_get_json` returning `Any`): `mypy mission-interpreter/src` invoked
   from the repo root reported **no error**, while `mypy src` invoked with `cwd=mission-interpreter/`
   correctly raised `no-any-return`. This reconfirms the existing memory item — mypy's
   `no-any-return` check is silently skipped when invoked with a subproject-relative path from the
   wrong cwd. File was restored to its original (bug-free) state after the test; `git status`
   confirms no diff remains.

**Verification run myself (not trusted from the report):**
- `world-model/`: `ruff format --check` / `ruff check` — pass; `mypy src` (cwd=`world-model/`) —
  clean, 55 files; `pytest tests -q` — 302 passed.
- `mission-interpreter/`: `ruff format --check` / `ruff check` — pass; `mypy src`
  (cwd=`mission-interpreter/`) — clean, 15 files; `pytest tests -q` — 31 passed.
- Numbers match the implementation report exactly.

**Other checks:**
- No writes to the DCS install; no new claims about DCS internals encoded (MI-2 only wires already-
  verified `query` functions and typed MI-1/MI-1.5 fields — no new `research/` entry needed, matches
  the plan's own assessment).
- `world-model/data/` stays gitignored; nothing under it is tracked.
- Coordinate math stays confined to world-model's existing coordinate subsystem — `enrich.py` does
  no math of its own beyond the `y`→`z` axis relabeling (already-typed field access, not a
  transform) and the polygon-centroid mean, which mirrors `find_place_by_name`'s own established
  convention rather than inventing a new one.
- `world-model/CLAUDE.md`, `mission-interpreter/CLAUDE.md`, `mission-interpreter/ROADMAP.md` diffs
  all read accurately against the actual code — no stale or aspirational claims.
- No TODO/FIXME/debug prints in any new file.
- No new dependency introduced on either side.

### Required Fixes

None.

### Optional Refinements

- **No explicit shared-contract test for the wire format** (item 5 above) — the two sides' shape
  assumptions (object/list/`{"clear": bool}`) are each verified independently against the real
  server or a hand-rolled double, but nothing would catch a field *rename* inside
  `PositionDescription`/`PlaceMatch` silently drifting out of sync with what mission-interpreter
  expects, since the client stays deliberately opaque about field names. A cheap future option:
  a small `world-model/tests/test_api.py` assertion that snapshots the full key set of one
  `describe_position` response (not just checking two ad hoc field names), so an accidental field
  rename fails loudly on world-model's own side even without a cross-venv integration test.
  Low priority given the deliberately opaque `dict[str, Any]` client design already minimizes this
  risk's blast radius.
- **Stray uncommitted agent-memory files** (`.claude/agent-memory/implementer/MEMORY.md` modified,
  `.claude/agent-memory/implementer/project_mi2_world_enrichment.md` untracked) — unrelated to the
  MI-2 diff itself (Implementer's own memory bookkeeping), but the working tree isn't fully clean.
  Not a required fix on the feature's own merits, but should be committed (or reverted) before DoD
  signs off on "clean working tree."

### Verdict

APPROVED

### Review Confidence

Full read — all changed source files read directly (not diff-only), both subprojects' full
verification suites run myself with correct per-subproject cwd, and the mypy CWD-sensitivity claim
independently reproduced rather than trusted from the report.
