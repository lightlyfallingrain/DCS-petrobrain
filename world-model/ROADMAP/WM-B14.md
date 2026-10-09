# WM-B14 — A region-row-less store slips past body-layer's startup guard

- [ ] **WM-B14 — A schema-valid but region-row-less store slips past body-layer's startup guard.** #status/open
  2026-10-05 security audit, after correcting a subagent's overstatement: the guard **does** catch an
  empty or foreign sqlite file (no `region` table → `sqlite3.Error` → `parser.error`). Only the
  narrow case passes — reachable from a full-theatre build interrupted between `create_schema` and
  `insert_region`, which [[M11]] Stage 5's `--srtm-grid-spacing-m` item can also produce. One row
  count at open.
