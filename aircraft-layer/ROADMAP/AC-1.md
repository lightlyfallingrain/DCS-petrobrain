# AC-1 — Core telemetry pipeline

- [x] **Core telemetry pipeline — done, merged 2026-09-07** #status/done (`feature/aircraft-layer-telemetry`).
  `Export.lua` → collector → `/telemetry/latest`. Live-tested against cockpit instruments
  (bank/IAS/heading/alt all match). 5 Hz export-rate bug found and fixed. `altitude_radar_m` stays
  null (deprioritized — `altitude_agl_m` is equivalent). `/telemetry/since` dropped as unneeded
  scope — no delta/ring-buffer endpoint exists; a consumer needs a concrete gap-free-history need
  before that's reconsidered.
