---
name: momentary-button-and-own-weapon-objects
description: A momentary cockpit button cannot go in polled.toml (body polls 1 Hz, feed is a level) -- use the PTT per-frame push + collector edge counter; and own rockets/missiles already arrive in LoGetWorldObjects' default list, so any weapon feature must also exclude them from perception
metadata:
  type: project
---
Two structural facts found while planning BL-B67 (`plans/bl-b67-atgm-run/plan.md`, 2026-10-29):

1. **A momentary button (e.g. fire button arg 741) is invisible to `polled.toml`.** The watched-args
   feed is change-gated at the 5 Hz export tick and `GET /watched_args/latest` returns the *latest
   level*; body-layer polls at 1 Hz (`body._DEFAULT_POLL_INTERVAL_S`), so a sub-second press is gone
   before body reads it. The existing precedent is `Export.lua push_ptt_state` (read every frame,
   send on change); add a collector-side monotonic `press_count`/`last_press_t` so body sees edges.
2. **`LoGetWorldObjects()` with the default `"units"` category already returns in-flight own rockets
   (`C_8`)** — 2026-09-25 probe. Production Export.lua calls it that way, so own weapons can reach
   naked-eye perception as candidates. Any feature that reads weapon objects should add a
   name-based exclusion in perception at the same time.

**Why:** both were one hop away from the obvious design (put the arg in `polled.toml`; read the
missile from the feed) and would have shipped as silent misses / phantom contacts.
**How to apply:** for any edge-shaped cockpit input, ask "will a 1 Hz reader of a level see it?"
before choosing a readback class ([[readback-classes-poll-vs-read-at-need]]). For any feature
touching weapon objects, check perception's candidate filter in the same plan.
