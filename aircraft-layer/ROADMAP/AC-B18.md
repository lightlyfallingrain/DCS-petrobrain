# AC-B18 — Per-frame `GetDevice(0)` lookups keep growing across `Export.lua` modules (18+ now)

- [ ] **Per-frame `GetDevice(0)` lookups keep growing across `Export.lua` modules (18+ now).** #status/open Filed 2026-11-18 at the BL-16 mode 1 M1+M2 merge. Perf MONITOR from `plans/flight-control/perf-m1-m2.md`: `update_live_seat_tracking` adds up to 6 uncached `GetDevice(0)` calls per frame regardless of `fc_mode`. Fix when next touched: one cached `GetDevice(0)` per frame threaded through every `push_*`/`read_axis` call, file-wide.
