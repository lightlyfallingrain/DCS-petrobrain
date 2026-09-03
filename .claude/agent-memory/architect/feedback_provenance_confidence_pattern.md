---
name: provenance-confidence-pattern
description: Pattern for handling third-party-derived (not ED-documented) facts in plans — provisional/confirmed confidence field, staged verification, don't block all progress on a Windows round-trip.
metadata:
  type: feedback
---

When a plan depends on a fact that's community/third-party-tool-derived rather
than ED-documented or verified against the actually-installed DCS copy (e.g.
pydcs's fitted Syria projection parameters), the right pattern — used in the M1
coordinate-transform plan — is:

1. Add an explicit `source` + `confidence` (`"provisional"` / `"confirmed"`)
   field on the data itself (e.g. in a per-theatre parameter registry), not just
   a comment.
2. Stage implementation into a "provisional" phase (can build and test now
   against the best current evidence) and a "confirmed" phase (blocking on
   whatever live-DCS probe closes the gap — usually a Windows-side run via
   `world-model/WORKFLOW.md`).
3. Do NOT flip roadmap/milestone status to done on the provisional phase alone —
   only after the confirming probe runs. This respects the root CLAUDE.md
   invariant ("do not encode unverified forum/community claims as fact")
   without blocking all coding on a manual cross-machine round-trip the user
   has to run themselves.

**Why:** This project's core invariant is that DCS is authoritative and
external/community claims must be verified, not silently trusted — but the
cross-machine (Mac dev / Windows DCS) workflow means "verify against the
installed copy" is often a slow, user-driven manual step, not something
investigator or architect can close in-session. Blocking all implementation on
every such gap would stall the project; silently trusting community numbers
would violate CLAUDE.md.

**How to apply:** Reuse this staged provisional/confirmed pattern whenever a
future milestone plan (raster registration, OSM reconciliation, DEM comparison)
depends on a claim that needs a live-DCS-install probe to fully confirm.
