"""The probe-tier store: a second, persistent SQLite file per region
(`<region>-probe.sqlite`, see `paths.probe_store_path`) holding chunk-by-
chunk accumulated probe data -- fine elevation, `surface_type`, ridge/
valley -- that a live DCS mission produced and that the base store's
delete-and-recreate rebuild contract must never touch.

See `plans/m8-incremental-store/plan.md` and
`world-model/docs/M8_PROBE_STORE.md` for the full two-store rationale. In
one sentence: the base store (`store/`) is always rebuilt from `data/raw/`
and is disposable; the probe store is not rebuildable from anything on disk
and is the more precious of the two files.

Module layout mirrors `store/`'s: `schema.py` (DDL + its own
`SCHEMA_VERSION`), `models.py` (`Chunk`/`ChunkStatus`; `Source`/
`StoredFeature` are reused from `store.models` rather than duplicated),
`writer.py` (write-only, direct connection to the probe store, never the
base store), `reader.py` (read-only; every function takes an optional
`schema` parameter so the same code works against a bare probe-store
connection or one where the probe store has been `ATTACH`ed under an alias
by a caller such as `query.describe.describe_position`), `paths.py` (the
one place mapping a base-store path to its probe sibling).
"""
