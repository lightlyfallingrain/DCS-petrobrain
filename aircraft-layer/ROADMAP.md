# Aircraft Layer — Roadmap

Live, LAN-reachable DCS I/O pipeline: `Export.lua` → Windows collector → LAN API, plus one narrow
write-back channel (`POST /text/push`) for in-cockpit text display. See `CLAUDE.md` for stack/API
details and `WORKFLOW.md` for the cross-machine deploy/run workflow. Full design/stage history:
`plans/aircraft-layer/plan.md`, `plans/aircraft-layer/implementation.md`.

## Status

- [x] **Core telemetry pipeline — done, merged 2026-09-07** (`feature/aircraft-layer-telemetry`).
  `Export.lua` → collector → `/telemetry/latest`. Live-tested against cockpit instruments
  (bank/IAS/heading/alt all match). 5 Hz export-rate bug found and fixed. `altitude_radar_m` stays
  null (deprioritized — `altitude_agl_m` is equivalent). `/telemetry/since` dropped as unneeded
  scope — no delta/ring-buffer endpoint exists; a consumer needs a concrete gap-free-history need
  before that's reconsidered.
- [x] **`/world_objects/latest`** — `LoGetWorldObjects`'s raw, unfiltered ground truth, feeding
  body-layer's `HybridPerceptionSource`/`NakedEyePerceptionSource` association. Each object carries
  `is_ownship` (PB-2 Stage -1, 2026-09-09), replacing an earlier 50 m proximity heuristic that had
  a false-negative window during troop insertion/close formation.
- [x] **`/petrovich_indication/latest`** — `list_indication(HELPERAI_DEVICE_ID)`'s parsed
  classification text, the scope channel's detection-existence gate.
- [x] **Text-overlay write channel — done, merged as part of BL-2.5, 2026-09-09.**
  `POST /text/push` → collector → loopback UDP → a DCS Hook-state overlay
  (`Saved Games/DCS/Scripts/Hooks/`), modeled on SRS's overlay pattern. First write path in an
  otherwise read-only layer; reframed `CLAUDE.md` from "read-only" to "read-mostly with narrow
  write channels." See `body-layer/ROADMAP.md` BL-2.5 for the body-layer side.
- [x] **F10 command inbound channel — done, merged 2026-09-13 (`eacc45c`).** First Hook→collector
  direction: `petrobrain-f10-commands-hook.lua` registers F10 menu items through
  `net.dostring_in("scripting", ...)` and forwards selections over loopback UDP 7794 to
  `F10CommandReceiver` (three allowed tokens only), served once via `GET /f10_commands/poll`.
  Needs `autoexec.cfg` `net.allow_dostring_in = { "scripting" }`. Wall-clock provenance only.
  See `body-layer/ROADMAP.md` "F10 radio-menu command input" and `plans/f10-crew-commands/`.

## Backlog

- [ ] **Split the export throttle** so `LoGetWorldObjects`/HelperAI can poll slower than self-data.
  `Export.lua`'s `EXPORT_INTERVAL_S = 0.2` (5 Hz) is one shared throttle gating all three feeds
  together. Ground units don't need 5 Hz; self-data (and any future threat-reaction signal) may
  want to stay fast. Fix: two independent interval constants. Not urgent — no measured FPS cost yet
  to react to (see next item). BL-2's contact-decay timescales (30s/120s) are ~2 orders of
  magnitude slower than either 5 Hz or a candidate 2 Hz, so this is a pure export-cost/latency
  tradeoff, not a belief-quality one. Raised 2026-09-09.
- [ ] **Measure `LoGetWorldObjects` FPS cost live** before tuning its poll rate. No confirmed,
  quantified per-call cost exists at realistic unit counts (~50–200) — only qualitative
  forum/Tacview-wiki folklore. Fly with world-objects export on/off at 5/2/1 Hz and diff
  FPS/frame-time. Also worth checking whether "being fired at" is even served by this poll rate at
  all (nothing currently reads it for threat/launch detection) — the urgent-callout-latency case
  may want its own dedicated signal later (e.g. RWR export) instead. Raised 2026-09-09, kept
  separate from the throttle-split item above since this is measurement that should land first.
