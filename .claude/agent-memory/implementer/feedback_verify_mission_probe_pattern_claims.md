---
name: feedback-verify-mission-probe-pattern-claims
description: Don't cite "mirrors an earlier proven M4 script" as justification without re-checking that earlier script actually does what's being claimed
metadata:
  type: feedback
---

When writing a new `tools/dcs-mission-probe/*.lua` script and describing it (in code comments or
`implementation.md`) as "mirroring" or "matching" an earlier script's "proven pattern," actually
re-read that earlier script's current content first — don't rely on a summary written from memory
of an earlier read.

**Why**: M5 Stage 3's `terrain_probe_{smoke,500,full}.lua` were described as mirroring
`elevation_probe.lua`'s (M4) "proven structure exactly: `pcall`-wrapped calls, append-mode
`io.write`". Both halves of that claim were checked against the file I'd read earlier in the same
session, but the *plan document's* own text (Finding E) — which does describe
`timer.scheduleFunction` chunking + append-mode `io.write` — got conflated with what
`elevation_probe.lua` actually contains, which is a single blocking loop with a one-time `"w"`
open. The scripts I wrote copied that same non-chunked shape, and the doc claim went uncaught
until Reviewer flagged it. See [[project_m5_stage3_handoff]].

**How to apply**: when a plan or checklist mandates a specific pattern (chunking, retries, a
particular API call shape) "per Finding X" or "matching the proven approach," verify the
*mandate's source text* and the *actual prior code* separately — a plan's prose description of a
pattern is not proof the referenced code implements it. This applies generally, not just to Lua
probes: any "matches what we did last time" claim in an implementation log is a testable
assertion, not a memory recall, and should be checked against the file on disk before being
written down.
