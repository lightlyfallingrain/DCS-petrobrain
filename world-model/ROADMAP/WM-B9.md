# WM-B9 — `find_place_by_name` scans ~49k rows

- [ ] **WM-B9 — `find_place_by_name` scans ~49k rows with four `json.loads` each: 507 ms vs 26.9 ms
  with a SQL-side `name LIKE` prefilter.** #status/open 2026-10-05 performance pass. This is crew-command latency
  the pilot actually hears, not a build-time cost. `all_features`-scans to substring-match a name.
