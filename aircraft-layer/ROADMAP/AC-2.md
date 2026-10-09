# AC-2 — `/world_objects/latest`

- [x] **`/world_objects/latest`** #status/done — `LoGetWorldObjects`'s raw, unfiltered ground truth, feeding
  body-layer's `HybridPerceptionSource`/`NakedEyePerceptionSource` association. Each object carries
  `is_ownship` (PB-2 Stage -1, 2026-09-09), replacing an earlier 50 m proximity heuristic that had
  a false-negative window during troop insertion/close formation.
