---
name: m8-probe-store-read-path-drift-gap
description: M8 probe store — write-path drift detection (open_probe_store) is solid and tested, but describe_position's ATTACH-based read path only checks schema_version, not theatre/chunk lattice — reproduced silent cross-theatre answer.
metadata:
  type: project
---

M8 (incremental probe store, `plans/m8-incremental-store/`) split identity-drift protection
across two code paths that look equivalent in the docs but aren't:

- **Write path** (`probe_store.writer.open_probe_store`, used by `build.pipeline.add_probe_chunk`):
  compares `theatre`, `chunk_size_m`, `probe_spacing_m`, `base_schema_version` against stored
  meta on every reopen, raises `ValueError` on any mismatch. Genuinely tested
  (`test_open_probe_store_raises_on_*` in `tests/test_probe_store.py`).
- **Read path** (`query.describe.describe_position`'s `ATTACH DATABASE ... AS probe`): only
  calls `check_probe_schema_version` — never compares theatre/chunk lattice meta against the
  base store actually being queried.

Reproduced concretely (not theoretical): built a base store for `theatre="Syria"`, attached a
probe store created with `theatre="Kola"` (matching schema version) via `probe_db_path`,
`describe_position(conn, "Syria", ...)` silently returned the Kola probe store's value labeled
`source="probe"`, `coverage="queried_with_data"` — no error, no signal.

`docs/M8_PROBE_STORE.md`'s "Drift protection" section states the check runs on "every
subsequent `open_probe_store` call" — true, but `describe_position` never calls
`open_probe_store` at all (it ATTACHes directly), so the doc overclaims read-path coverage.

**Why this matters:** the plan explicitly named this exact scenario ("probe store built against
one region's geometry, then paired with a base store rebuilt at a different extent") as "the
main new risk the split introduces" needing "an explicit test" — the test exists for the write
path only. Filed as a Required Fix in `plans/m8-incremental-store/review.md`, verdict NEEDS
REVISION on that single issue (everything else in the plan was genuinely and correctly
implemented with real tests, not prose assertions).

**Pattern worth watching for in future milestones**: when a design has two independent entry
points into the same identity/versioning contract (a "creator/writer" path and a "consumer/
reader" path), verify *both* enforce the contract — a check implemented once and assumed to
"just apply" via shared meta storage does not actually apply unless every entry point calls it.
[[project_m8_probe_store]] is the implementer's own memory on this milestone — cross-reference
if resuming this thread.
