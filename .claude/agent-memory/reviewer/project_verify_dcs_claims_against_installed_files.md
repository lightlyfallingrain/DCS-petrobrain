---
name: verify-dcs-claims-against-installed-files
description: When a diff's comment claims a DCS cockpit/geometry fact (eye points, arg semantics, API shape), read the actual installed DCS file instead of trusting the comment's arithmetic or citation
metadata:
  type: project
---

On `fix/ai-wheel-pilot-seat-gate` (2026-11-16), the implementer's comment claimed "Views.lua: pilot
eye x = 3.15 m, operator x = 4.65 m" and derived a seat-detection boundary from it. Rather than
trust the comment, I read `/mnt/f/Games/DCS World/Mods/aircraft/Mi-24P/Views.lua` and `entry.lua`
directly (both readable read-only from the WSL mount per `aircraft-layer/CLAUDE.md`/
`dcs-file-investigation` skill). This caught nothing wrong this time, but it's cheap (two file
reads) and it is the only way to actually rule out a transposed seat index or a stale comment —
`Cockpit[1]`/`Cockpit[2]`'s slot order isn't self-evidently "pilot then operator" from the Lua
alone; it only resolves by cross-referencing `entry.lua`'s `Mi-24P_pilot`/`Mi-24P_operator` input
profile order against the `Cockpit` table's own `player(...)` call order.

**Why:** root `CLAUDE.md`'s "verify against the installed DCS version" invariant is usually read as
the Investigator's/Implementer's job before a plan is written. It is equally the Reviewer's job
*after* — a confident-sounding comment with specific numbers is exactly the kind of claim that goes
unchecked because it looks like someone already checked it. The file is one `Read` call away and a
wrong eye-point or slot-order assumption here would have shipped a seat gate that silently reversed
pilot/operator, i.e. the exact class of bug this fix exists to prevent.

**How to apply:** whenever a diff's comment cites a specific DCS-internal number (arg ids, eye
points, API return shapes, thresholds attributed to "measured live"), and the claim is checkable
from files on this machine (`/mnt/f/Games/DCS World/...` per `dcs-file-investigation`), read the
file before accepting the comment. Don't stop at the one file named in the comment — check whether
a second file (here, `entry.lua`) is needed to resolve an ordering/identity question the first file
alone doesn't answer. Grep the project's own `research/*.md` first too: a claim like "LoGetCameraPosition
returns `{p=…, x=…, y=…, z=…}`" is often already primary-sourced there (quoted from DCS's own shipped
`Scripts/Export.lua` doc comments) rather than something to re-derive from scratch.
