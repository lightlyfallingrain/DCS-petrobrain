---
name: readback-consumer-rate-audit
description: Before keeping any Export.lua per-frame read, audit who consumes it — body-layer polls at 1 Hz and caches are latest-of-one, so a per-frame push is usually consumed at 1 Hz; the slew servo reads its own args in Lua
metadata:
  type: project
---

When BL-B90 Stage 4 (2026-10-24) asked "which args can leave the per-frame push", the answer came
from tracing each arg to its reader, not from the arg's nature (switch vs lamp). Every reader of
`push_cockpit_switch_state`'s line was body-layer, at its **1 Hz poll**, through a latest-of-one
collector cache. So the per-frame push bought ≤1 frame of latency on a 1 s consumer. The only
genuinely per-frame needs (886 OBSERV, 898 align lamp, for the slew servo) were already met by
`run_sight_servo`'s **own** reads inside Lua. The whole line, lamps included, moved to the 5 Hz tick.

**Why:** the brief framed it as "switches move, axis stays". The real boundary is "read by Lua
per frame" vs "read by Python at poll rate". Lamps were in the brief's grey zone, and the audit
settled them in one table.

**How to apply:** for any future Export.lua feed, make a table with columns arg → Python reader →
the rate that reader actually samples at → any per-frame Lua reader. Only a per-frame *Lua* reader
justifies per-frame work. Also check reconnect behaviour: change-gated lines never resend after a
collector restart unless they are forced to, which was a pre-existing gap in the old feed. And a
cache must be cleared on a new Export session (the `export_version` line), or a stale line can
falsely "confirm" state. See [[export-lua-per-frame-push-functions]].
