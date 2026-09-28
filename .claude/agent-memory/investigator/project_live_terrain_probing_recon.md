---
name: live-terrain-probing-recon
description: Feasibility of live in-mission land.getHeight probing via the existing mission-scripting bridge, for world-model densification
metadata:
  type: project
---

Full note: `aircraft-layer/research/2026-09-28-live-terrain-probing-feasibility.md`.

- **`PETROBRAIN_RUNTIME.md`'s "no live data path" blocker (written 2026-09-08) is stale as of
  2026-09-13** — `net.dostring_in("scripting", ...)` bridge (Hook state → mission-scripting state
  → loopback UDP → collector → LAN) has shipped and flown since then (F10 commands, then unit
  velocity 2026-09-22). Correct the concept doc's sentence rather than trusting it — see
  [[mission-bridge-already-shipping]] pattern in aircraft-layer's own research dir.
- **`land.getHeight`/`land.getSurfaceType` are Mission Scripting API** (same env the bridge already
  runs code in) — never actually called through `dostring_in` in any prior session; only called via
  offline mission-editor trigger scripts (M4/M5, `net.log`/`io.open`, before the bridge existed).
  High-confidence inference it'll work the same way `Object.getVelocity()` does, not yet watched.
- **Per-call cost of an O(N) `dostring_in` payload is the single most load-bearing unmeasured
  number in this project's aircraft-layer** — the velocity hook self-measures `bridge_call_ms`/
  `unit_count` to `dcs.log` every poll (deployed since 2026-09-22) but **nobody has ever read that
  log from a sortie with a realistic (50-200) unit count** — only sortie flown had 12 units. Same
  gap flagged independently by the 2026-09-26 performance review. Don't design a probe batch size
  or throttle rate until this exists.
- **M8 probe_store write side is cheap and ready**: `add_probe_chunk` ~23ms/2601-point chunk,
  `describe_position` w/ probe attached ~0.4ms (measured, Apple Silicon, local disk). Tri-state
  coverage `(kind, chunk_ix, chunk_iz)` is the exact "don't rescan" mechanism already built — the
  bottleneck for live densification is entirely DCS-side call cost, not the Mac-side store.
- **No collector/API endpoint exists yet for elevation-probe samples** — nearest patterns are
  `F10CommandQueue` (drain-all) and the velocity hook's packed-string-over-UDP wire format; either
  could be adapted. Architect decision, not resolved here.
