---
name: ed-detection-gap-analysis
description: ED's native detection/identification model vs our BL perception+classification model — what's confirmed, what's a live lead, what's ruled out.
metadata:
  type: project
---

Full findings: `aircraft-layer/research/2026-09-19-ed-native-detection-identification-gap-analysis.md`.

Key facts worth not re-deriving:

- **`Scripts/AI/Detection.lua`** — a generic, engine-wide (not Mi-24P-specific) AI detection script,
  found via grep of `DCS-files.txt` but never fetched/read. Most plausible location for the actual
  consumer of `HelperAI.lua`'s `min_contrast_f`/`min_fog_transparency`/`extra_eyesight_ratio` —
  `HelperAI.lua` itself is confirmed (three separate exhaustive-grep sessions) to only *define*
  these constants with zero Lua consumers anywhere in the Mi-24P tree. Highest-value next fetch for
  any future ED-detection-formula question.
- **`world.weather.getFogThickness()` / `getFogVisibilityDistance()` are real, documented, live
  getters** (Hoggit-confirmed, added DCS 2.9.10) — but live in the **Mission Scripting** sandbox,
  not `Export.lua`. This reverses the prior working assumption that weather was `.miz`-only/write-
  only. Reachable only via the same Hook→`net.dostring_in`→loopback-UDP pattern already proven live
  for F10 commands (`project_f10_radio_menu_command.md`) — **but the `"mission"` target string for
  `net.dostring_in` (vs. F10's `"scripting"` target) has never itself been tested.** That's the one
  remaining checkpoint before a weather channel is buildable.
- **ED's own richest crew-facing channels never expose a raw numeric range** — the ambient callout
  buckets it into 1 of 24 fragments, the scope channel (`list_indication`) omits it entirely (no
  numeric field at all, confirmed across ~4000 live samples). Strong corroborating evidence (not
  new scope) for this project's own decision to treat ground-truth range in belief as an
  omniscience leak.
- **No movement/velocity term was found anywhere in ED's Lua-visible detection constants** —
  contradicts the intuitive assumption that "ED obviously models movement and we don't." The
  honest framing: neither model has a verified movement term; adding one to our own model is an
  independent design choice, not catching up to ED.
- **No dwell/time-integration term either** (exhaustive negative, prior session's Q4) — detection
  reads as a per-frame/instantaneous geometric test (angular size vs. per-tier threshold), not
  time-accumulated, as far as any Lua-visible constant shows.
