# Vendored DCS reference documents

Verbatim copies of documentation shipped inside the DCS World installation, kept here so the
repo (and any machine without DCS installed) can consult them without live access to
`$DCS_INSTALL_PATH`.

**Do not edit these files.** They are byte-for-byte vendor copies. Findings, interpretation and
anything Petrobrain-specific belong in a dated research note in the parent directory
(`aircraft-layer/research/`), not in here.

Re-copy after a DCS update and record the new version below — ED revises these between builds.

## Inventory

| File | Source | DCS version | Copied | MD5 |
|---|---|---|---|---|
| `Sim_ControlAPI.md` | `$DCS_INSTALL_PATH/API/Sim_ControlAPI.md` | 2.9.29.27278 | 2026-09-09 | `3303e0496cafed5a62da9bc9e103cec6` |

### `Sim_ControlAPI.md`

ED's official documentation for **user scripts loaded into the GUI/Hook Lua state** —
`$DCS_SAVED_GAMES_PATH/Scripts/Hooks/*.lua`. This is a third Lua state, distinct from both the
Export environment that `aircraft-layer/dcs-export/Export.lua` runs in and the sandboxed Mission
Scripting environment; it is loaded once at DCS startup rather than per-mission, and is not
sanitised (`io`/`os`/`lfs` available).

The closest thing to an authoritative reference for what DCS can be *commanded* to do from
outside a mission. Sections:

- `Sim.*` — simulation control (line 93)
- `log.*` — logging (line 226)
- `net.*` — networking, chat, and `net.dostring_in` cross-state execution (line 288)
- `Export.Lo*` — the LuaExport API, also reachable from Hook state (line 485)
- Simulation and GUI callbacks (lines 573, 682)

Found 2026-09-09 during the text-panel output-channel investigation; see
`../2026-09-09-dcs-text-panel-output-channel.md` for how it applies to Petrobrain.

Two siblings were left in the install and not copied: `Sim_ControlAPI.html` (same content,
HTML rendering) and `include/ed_object_access.h` (C header, separate concern).
