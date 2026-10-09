# BL-7 — Mission phase and relevance (≈ PB-9's deterministic half)

- [x] **BL-7 — Mission phase and relevance (≈ PB-9's deterministic half; done, merged 2026-09-13,
  `feature/bl7-mission-phase-relevance`, merge commit `ec4cf12`).** #status/done `MissionPhaseTracker` consumes
  Mission Interpreter's MI-6 `--emit-compact` JSON output (file read, no cross-subproject import —
  mission-interpreter is not the body-layer ↔ world-model in-process exception). Sequences ownship
  monotonically through route waypoints via a capture-radius check (`WAYPOINT_CAPTURE_RADIUS_M`,
  uncalibrated placeholder, same debt class as `visibility.py`'s tier constants pending live
  calibration). Pure in-memory tracker (ints/tuples, no sqlite), written from poll thread
  (`.update()`), read-only from REPL thread (`.current_phase()`), deliberately mirrors
  `EnrichmentContext.ownship`'s cross-thread split to avoid this codebase's recurring
  sqlite thread-affinity defect class (BL-2 Stage 6, BL-5). **No new tool** — mission-phase
  proximity folds additively into `get_situation`'s facts payload as a tie-breaker *only* within
  attention tiers, never overriding cross-tier ranking (resolves the stale "adds `get_mission_phase`"
  flag — the tool-set freeze point was BL-6, not BL-7, and the decision here was to extend
  `get_situation`'s existing payload rather than a new tool, per `tool_api.py`'s module docstring).
  Tests: 475 passed (+24). Fixture-based acceptance testing only; live acceptance (real MI-6 output
  end-to-end against a real flight) deliberately deferred, same posture as BL-6's `scan_area` wiring
  gap. Full history: `plans/bl7-mission-phase-relevance/`.

