# WM-B3 — Measured data-quality figures need to reach their consumers

- [ ] **WM-B3 — Measured data-quality figures need to reach their consumers, not just a research
  note.** #status/open Raised 2026-09-29, from `fix/los-elevation-tolerance`: M7's SRTM-vs-DCS accuracy figure
  (mean −7.19 m, stddev 11.52 m) sat correctly recorded in `world-model/ROADMAP.md`'s M7 entry for
  three weeks while `query.line_of_sight.line_of_sight_clear` consumed the elevation grid as if
  exact, causing a real missed-detection defect. The measurement wasn't wrong and the consumer
  code wasn't wrong in isolation — the gap was that nothing connected the two. No fix scoped yet;
  worth asking, next time a grid/store gains a measured error figure, whether every consumer that
  treats that data as exact has been checked against it, rather than trusting a docstring or
  roadmap entry to be read at the right moment.
