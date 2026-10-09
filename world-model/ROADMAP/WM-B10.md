# WM-B10 — `features_in_bbox` embeds one bind parameter per candidate id

- [ ] **WM-B10 — `features_in_bbox` embeds one bind parameter per candidate id, against a limit that
  is build-dependent.** #status/open 2026-10-05 passes, found independently by both. 4,191 parameters at a 30 km
  bbox in an under-clustered synthetic store; `SQLITE_LIMIT_VARIABLE_NUMBER` is **32,766 on stock
  SQLite ≥ 3.32** but reports **250,000** on the dev Mac, so this is a cliff on a per-poll path that
  **cannot be ruled out by measuring here**. Exceeding it raises `OperationalError` from inside a
  live call. Needs `python -c "import sqlite3; print(sqlite3.connect(':memory:').getlimit(9))"` on
  the Windows Python, then either chunk the `IN` list or join against a temp table.
