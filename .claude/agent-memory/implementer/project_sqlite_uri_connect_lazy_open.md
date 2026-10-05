---
name: sqlite-uri-connect-lazy-open
description: sqlite3.connect(uri=True, mode=ro) on a missing file doesn't raise until first execute(), not at connect()
metadata:
  type: project
---

`sqlite3.connect(f"file:{path}?mode=ro", uri=True)` against a nonexistent path does **not** raise
at `connect()` — it succeeds and returns a `Connection`. The `OperationalError` ("unable to open
database file") only fires on the first `execute()`/query against it.

**Why it matters:** a `try/except (sqlite3.Error, OSError)` meant to catch "store not built yet"
must wrap the query call too, not just the `open_world_model(...)` connect call — wrapping only
the connect looks correct and passes a quick read, but silently lets the real error escape
unguarded. Confirmed experimentally in `body-layer/.venv` (not assumed) while implementing the
multi-theatre-afghanistan plan's security deep-analysis required fix (`plans/
multi-theatre-afghanistan/security.md`'s optional item, `body-layer/src/logger.py`'s mismatch
guard).

**How to apply:** when wrapping a `sqlite3.connect(..., mode=ro)` call for a "clean error on
missing/corrupt store" guard, wrap the connect *and* the first subsequent query inside the same
`try` block.
