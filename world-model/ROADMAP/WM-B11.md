# WM-B11 — `mode=ro` is bypassable two ways

- [ ] **WM-B11 — `f"file:{path}?mode=ro"` is bypassable two ways, five sites in-repo.** #status/open 2026-10-05
  security audit, **verified by execution**: a path containing `?mode=rwc&x=1` wins, and a path
  containing `#` makes SQLite discard the fragment *and* the appended mode. Both produced a
  read-write connection and created the file. Also recorded: `ATTACH DATABASE ?` is not
  URI-interpreted (no injection) but **opens read-write over a `mode=ro` main connection**. Fix is
  `urllib.parse.quote` on the path, or pass the URI through a builder rather than an f-string.
