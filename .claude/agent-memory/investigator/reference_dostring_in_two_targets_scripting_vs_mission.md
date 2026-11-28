---
name: reference_dostring_in_two_targets_scripting_vs_mission
description: net.dostring_in has two distinct, both-proven-live bridge targets from a Hook script -- "scripting" (land.getHeight/isVisible, F10 commands) and "mission" (world.weather.getFogThickness/getFogVisibilityDistance) -- and Export.lua itself has neither terrain-point nor weather getters at all.
metadata:
  type: reference
---

Confirmed across two separate sessions/flights, both still true as of 2026-11-28's BL-16 M3 recon:

- **`Export.lua` has no point-terrain-height getter and no fog/weather/visibility getter of any
  kind** — confirmed by exhaustive grep of the shipped reference file (`fog|visib|cloud|precip|
  light` all negative). `Export.LoGetHeightWithObjects` is ownship-only (Hoggit: "Ownship"
  section, gated behind `LoIsOwnshipExportAllowed()`), not a point query.
- **`net.dostring_in("scripting", ...)`** from a Hook script reaches `land.getHeight`/
  `land.isVisible`/`land.profile` (Mission Scripting terrain API) — production since 2026-09-13
  (F10 commands), and the point-query shape (`probe_points`, BL-B111) flown live 2026-11-27.
- **`net.dostring_in("mission", ...)`** from a Hook script reaches `world.weather.
  getFogThickness()`/`getFogVisibilityDistance()` — a *different* dostring_in target from the
  above, confirmed live 2026-09-29 (`aircraft-layer/research/2026-09-29-bridge-terrain-probe-
  results.md`, Finding 17: thickness=320, visibility=2300 on a real flight). Both targets are
  reachable from the same or sibling Hook scripts in the same tick.
- **Net effect for any future "read terrain/weather state live" question**: if `Export.lua`
  itself doesn't have the getter (check the shipped `Scripts/Export.lua`'s own doc comments
  first — ED documents its API as comments in that file, already the project's citation source
  for `LoGetWorldObjects`), the Hook-bridge route works but answers to the **collector/body-layer**,
  not back into `Export.lua`'s own per-frame Lua state — there is no direct Hook→Export.lua
  channel (both talk to the collector over separate loopback UDP sockets). A law running inside
  `Export.lua` (e.g. `flight_control.lua`) that needs a Hook-bridge-sourced value must get it
  relayed down through body-layer's existing command channel (e.g. `flight_lease`'s `limits`),
  not read it directly — a real latency/ownership fork, not a detail, flagged for BL-16 M3.
- `land.profile(from, to)` (same "scripting" bridge) returns a whole terrain line in one call —
  1 km → 14 points at ~77 m spacing, 1 ms — but does not start exactly at `from` (first point was
  160 m in) and its spacing is mesh-resolution-driven, not request-driven. Worth knowing before
  reaching for N individual `getHeight` calls on a line.
- Both `forum.dcs.world` thread URLs (ED forums) returned HTTP 403 to automated `WebFetch` this
  session — consistent with [[feedback_forum_403_fallback]]-class blocking; WebSearch snippets of
  them were usable as forum-claim-unverified evidence, but nothing on that domain is re-fetchable
  by this session's tools. Ask the user to paste content manually rather than treating a 403 as
  "undocumented."
