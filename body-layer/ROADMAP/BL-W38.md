# BL-W38 — Rejected: persistent omniscient mission-memory store

- **Persistent omniscient mission-memory store, upstream of perception filtering — REJECTED
  2026-09-10.** A performance angle (avoid DCS LOS queries via a coarse world-model precheck) rested
  on a false premise: `line_of_sight_clear` already samples world-model's *local* elevation grid, not
  a live DCS call. Do not revive without a new concrete trigger. `plans/omniscient-mission-memory/plan.md`
  (never merged) has the proposed pipeline for the record.
