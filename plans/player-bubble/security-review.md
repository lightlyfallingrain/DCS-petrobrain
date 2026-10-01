## Security Deep Analysis: player-bubble

Branch `feature/player-bubble`, tip `5c5bde6` (verified via `git rev-parse HEAD` at
start of this review). Real change set is `6e3a2b7` (`824fea5` is Reviewer's
approval note, `5c5bde6` a doc-only correction to `implementation.md`'s own
reasoning). Branch cut from `53f8b0b`; `main..feature/player-bubble` is clean —
no unrelated `run-scripts/*` or `world-model/ROADMAP.md` drift once `git show
--stat 6e3a2b7` is read directly.

### Dependency Status

No dependency change. `body-layer/pyproject.toml` and `uv.lock`-equivalent are
untouched by this feature (confirmed via `git diff main..feature/player-bubble --
pyproject.toml`, empty). The only new imports (`filter_player_bubble`,
`PLAYER_BUBBLE_RADIUS_M`, `GateOutcome.PLAYER_BUBBLE`) are intra-module/intra-package.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `src/perception/association.py` `filter_player_bubble` | computation-scope filter on `WorldObjectCandidate.x/z/alt_m` (already-typed floats, parsed upstream by the pre-existing `from_dict`) | A malformed value that still parses as float (e.g. `nan`) propagates through `range_m`'s `sqrt`, producing `nan`. `nan <= PLAYER_BUBBLE_RADIUS_M` is `False` in Python, so the candidate is dropped — fails closed, not open. A value that doesn't parse as float at all (`None`, non-numeric string) raises in `from_dict` before this filter ever runs, which is pre-existing, unchanged behavior. | None — correct fail-closed behavior, by construction of IEEE 754 comparison semantics, not by an explicit guard. Confirmed, not assumed. |
| `src/perception/detection_trace.py` `GateOutcome.PLAYER_BUBBLE` / `DetectionTrace` row | new trace outcome records that a filtered-out unit existed at a given range/bearing | This is the one place in the diff that writes down a fact about something Petrovich deliberately did not look at. Traced all the way to `src/detection_trace_writer.py`: appends JSON lines to a local file only (`DEFAULT_FLUSH_EVERY_N_POLLS` buffered), its one read is a read-only join against `ContactStore.contacts` to resolve `object_id -> contact_id` for diagnostic purposes, and it writes nothing back into `ContactStore`, `Percept`, or any `Contact` field — the module's own docstring states this boundary explicitly and the diff doesn't touch it. No network path, no belief-state path. The omniscience invariant is about what Petrovich (the belief/dialogue layer) can act on or say; this artifact is for the user's own offline diagnosis, same footing as every other `GateOutcome` row already written for *admitted* candidates (which carry far more detail — tier, cluster membership). Confirmed, as asked, rather than skipped. | None |
| `src/perception/{naked_eye,hybrid}_source.py` | filter applied immediately after `filter_ownship`, before gaze/salience/visibility/clustering/`associate()` | Matches the plan and commit message exactly — a bubble-excluded candidate is never handed downstream. Neither file touches `belief/` or `ContactStore` at all (confirmed by `git show --stat 6e3a2b7`: only `perception/`, `tests/`, `tools/summarize_detection_trace.py`, plan/todo docs). An existing remembered contact that drifts past 10 km simply receives no new `Observation` this poll — the memory-retention/expiry logic (wherever it lives) is untouched code, not exercised differently by this change. No path in this diff can expire, delete, or downgrade a `Contact`. | None |
| `tools/summarize_detection_trace.py` | diagnostic-tool fix for the new outcome | Correctness fix on an offline reporting tool (would have mis-attributed a bubble-dropped candidate as having cleared the cockpit mask gate). No security implication — not reachable from any runtime path, tool is read-only against the trace file. | None |
| `association.py` `PLAYER_BUBBLE_RADIUS_M` vs `visibility.NAKED_EYE_RANGE_CAP_M` | two independent 10000.0 constants, deliberately not aliased | `tests/test_association.py::test_player_bubble_radius_is_not_imported_from_visibility` (and its pair) asserts the source-level independence by name, guarding the exact collapse the docstring warns against. This is a correctness/design-intent guard, not itself a vulnerability class, but it is the kind of regression that would matter later (the 9K113 sight's 20 km cone) — confirmed present and passing. | None |

### Untrusted-input handling (`GET /world_objects/latest`)

The filter's own two inputs, `candidate.{x,z,alt_m}` and `ownship.{x,z,alt_m}`,
are both already-validated floats by the time `filter_player_bubble` sees them —
`WorldObjectCandidate.from_dict` (pre-existing, unchanged by this diff) does the
`float(data["lat_deg"])`/`float(data["lon_deg"])` coercion and coordinate
conversion upstream, and raises on anything that doesn't coerce. This feature
introduces no new parsing of the wire payload — it consumes an already-typed
in-process dataclass. The one genuinely new arithmetic path (`range_m` inside
`filter_player_bubble`) is unconditional comparison against a float constant, and
Python's `<=` against `nan` is `False`, so an adversarial-but-float-parseable value
fails closed (dropped from consideration) rather than open (admitted into the
bubble). No exception path in the new code that could crash the poll loop.

### Verdict

APPROVED

No security-relevant change beyond what's analyzed above. This is a pure
computation-scope narrowing (fewer candidates reach perception logic, never
more), it introduces no new dependency, no new network/file surface beyond a
single new field on an existing local-disk debug trace, and the one new
arithmetic path fails closed on malformed numeric input. Single-user, LAN-only,
offline project; no attacker-with-local-code-execution scenario applies here.

### Verification run (worktree, `body-layer/`)

- `ruff format --check src tests` — pass (114 files)
- `ruff check src tests` — pass
- `mypy src` — pass, 53 source files
- `pytest tests -q` — 1379 passed, 4 xfailed (matches expected; one stderr
  traceback during the run is `brain_client`'s own connection-refused handling
  test, not a failure)
