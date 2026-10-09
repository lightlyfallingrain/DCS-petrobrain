# WM-B13 — Two documented premises are stale by an order of magnitude

- [ ] **WM-B13 — Two documented premises are stale by an order of magnitude; documentation
  correction only.** #status/open 2026-10-05 performance pass. (a) `world-model/CLAUDE.md` and
  `plans/osm-classified-cache/plan.md` justify the OSM cache by a *"~25-30+ minute"* parse; post
  `osmium tags-filter` it measures **85.9 s**, so the cache protects a 1.5-minute stage while 90 % of
  the build is elsewhere. **No recommendation to remove the cache** — just stop citing a figure that
  would mis-size the next decision. (b) [[M7]]'s 449.3 s full-build baseline is quoted project-wide
  and is ~6× off the real ~82 minutes (see [[M11]] Stage 4); the `[x]` M7 entry keeps its historical
  number, but anything *planning* against it should cite the Afghanistan build note instead.
