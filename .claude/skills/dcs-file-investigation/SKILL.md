---
name: dcs-file-investigation
description: Locate and read files in the installed DCS World tree -- module Lua (Mi-24P/Petrovich cockpit scripts), the Export/scripting API, terrain data, Saved Games. Provides the path map, the text-vs-opaque file breakdown, and scoped grep recipes. Use when investigating how a DCS system actually works from its shipped files, instead of rediscovering the install layout each session.
---

# DCS File Investigation

Static reconnaissance of the **installed DCS tree**. Complements `dcs-log-recon`, which parses
*runtime* `Export.lua` output — this skill is about the files DCS ships on disk.

## In-repo reference: the real Mi-24P manual (RU)

`docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf` (167 pages) is the full Russian-language DCS
Mi-24P Quick Start manual — the actual cockpit/systems manual, more comprehensive than the English
quickstart guide. Unlike everything else in this skill, it needs no DCS machine: it's checked into
the repo and readable from any checkout. Use `Read` with `pages:"a-b"` (poppler/`pdftoppm` required
on the reading machine, max 20 pages/call — `brew install poppler` on Mac).

Useful for cross-checking live-probe conclusions about real systems (e.g. the 9K113 Raduga-Sh
guidance device/ПН, ASP-17 sight, PTUR designation procedure) against how the actual aircraft's
systems are meant to work, not just how DCS happens to expose them. **Check the relevant
`research/` directory for an existing RU-manual-sourced note before re-reading the PDF from
scratch** — earlier mining passes are written up there, and re-deriving one costs a lot of pages.

The `investigator` role otherwise re-derives "where does this live, is it readable" every session,
because so much of this project rests on unverified DCS internals. This skill is that answer, and
it was verified against one install — `2.9.29.27278`, 2026-09-09. Treat every layout claim below as
dated to that version: DCS updates move things, so re-check rather than trust it after an update.

## Precondition: are you on the DCS machine?

```bash
: "${DCS_INSTALL_PATH:?not on the DCS machine}" "${DCS_SAVED_GAMES_PATH:?not on the DCS machine}"
```

Both are set only on the machine with DCS installed. **If either is unset, stop** — you are on a
dev-only machine and cannot answer from the install tree. Say so rather than guessing paths or
answering from memory; route the question to the user or to synced artifacts under
`win-mac-sync/from-windows/`.

Never hardcode the paths this skill's examples resolve to. Always go through the variables — they
differ per machine and per mount.

## Read-only, always

`world-model/docs/CONVENTIONS.md`: **never modify the DCS installation.** Read, `grep`, `strings`,
and copy *out*. No writes, no `sed -i`, no scratch files inside `$DCS_INSTALL_PATH`. The one
directory this project does write is `$DCS_SAVED_GAMES_PATH/Scripts/` (Export.lua deployment) —
that is `aircraft-layer/WORKFLOW.md`'s job, not this skill's.

## The important finding: DCS ships plaintext Lua

**Do not run `strings` on `.lua` files.** Every `.lua` in the install sampled so far is readable
source, not `\x1bLua` bytecode — Mi-24P (170/170 text), plus Ka-50_3, M-2000C, SA342, Su-25T and
F-4E (0 bytecode across ~920 files). `grep` and `sed -n` work directly.

Re-check rather than assume after a module update or for a module not listed above:

```bash
find "$DCS_INSTALL_PATH/Mods/aircraft/<Module>" -name '*.lua' \
  -exec sh -c 'head -c4 "$1" | grep -q $'"'"'\x1bLua'"'"' && echo "BYTECODE $1"' _ {} \;
```

`strings` is for the genuinely opaque files only:

| What | Readable? | How |
|---|---|---|
| `*.lua` | yes, source | `grep` / `sed -n` |
| `*.dll` (e.g. `Mi-24P/bin/Mi24.dll`) | no | `strings -n 6 <f> \| grep -i <term>` |
| `*.edce` (`Scripts/Database.edce`, terrain `Sounds.edce`) | no, ED-encrypted | not extractable; find the answer elsewhere |
| `*.miz` | yes | zip archive — `unzip -p <f> mission` |
| `*.edm` / `*.EDM`, `*.dds`, `*.lods` | no | model/texture binaries; out of scope |
| `manifest.bin`, `*.cmp`, `*.adb` | no | opaque |

## Path map

```
$DCS_INSTALL_PATH/
  Scripts/                    Export.lua, MissionScripting.lua, JSON.lua, Database.edce
                              -- the shipped scripting/export API surface
  API/                        Sim_ControlAPI.md + .html, include/ed_object_access.h
                              -- the closest thing to official export API docs
  Doc/                        PDFs (user manual, beacon lists), Charts/
  Mods/aircraft/<Module>/     per-module tree, see below
  Mods/terrains/<Theatre>/    one directory per installed theatre -- `ls` it, or read the module
                              list out of autoupdate.cfg, rather than assuming which are present
                              RasterCharts/ clipmaps/ map/ beacons.lua entry.lua
  CoreMods/                   aircraft/ tech/ services/ characters/ 'WWII Units'
  autoupdate.cfg              install version + installed module list (JSON)

$DCS_SAVED_GAMES_PATH/
  Scripts/                    Export.lua (deployed), Hooks/, aircraft_layer_debug.flag
  Logs/                       dcs.log, aircraft_layer_debug.log -- feed to `dcs-log-recon`
  Missions/  Tracks/  Config/
```

### Mi-24P module tree (the one that matters here)

```
$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/
  entry.lua comm.lua Views.lua
  bin/                              CockpitMi24.dll, Mi24.dll  (strings only)
  Cockpit/Scripts/
    HelperAI/                       <- Petrovich. HelperAI.lua, _page*.lua,
                                       _reporting_names.lua, _sound.lua,
                                       _lengths_ng.lua, AI_Wheel/
    CrewIndicator/                  crew_indicator_init.lua, _page.lua
    AI/                             AI_Gunners.lua, AI_Side_Gunner.lua, AI_utility.lua
    PKV/ ASP17V/ 9K113_CAM/ ADI/ HSI/ MapDisplay/ C061K/ ASO_2V/
    Devices_commands/ Devices_specs/ ControlsIndicator/ TRIGGERSYSTEM/
  Cockpit/IndicationTextures/Petrovich/
  Input/ Options/ Missions/ l10n/ FM/
```

`HelperAI_reporting_names.lua` and `HelperAI_sound.lua` are the usual starting points for what
Petrovich can name and say; `AI/` is the gunner behaviour.

## Recipes

**Always scope with `--include`.** The install holds ~7.5k `.dds` and ~2.2k `.edm`; an unscoped
`grep -r` drags every one across the mount. Scoped, a whole-module search is ~0.2s and all of
`Mods/aircraft` is ~3s.

```bash
# what a term looks like across one module
grep -rn --include='*.lua' 'Petrovich' "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P"

# which files define/call a symbol, across every aircraft module
grep -rln --include='*.lua' 'LoGetWorldObjects' "$DCS_INSTALL_PATH/Mods/aircraft"

# is an export function shipped at all, and where
grep -rn --include='*.lua' 'LoGetWorldObjects' "$DCS_INSTALL_PATH/Scripts"

# read a known region without dumping the file
sed -n '120,180p' "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts/HelperAI/HelperAI_reporting_names.lua"

# installed version + module list
head -30 "$DCS_INSTALL_PATH/autoupdate.cfg"

# mission table out of a .miz, without unpacking to disk
unzip -p "$DCS_SAVED_GAMES_PATH/Missions/<name>.miz" mission | head -50

# last resort, binaries only -- the DLLs carry mangled C++ symbols, so a device
# name reveals its class path (avPKV -> cockpit::Mi24::avPKV)
strings -n 6 "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/bin/CockpitMi24.dll" | grep 'PKV'
```

Search the DLLs for *device/class* names (`PKV`, `ASP17`, `avSomething`), not for gameplay
concepts — `Petrovich` and `HelperAI` return nothing there, because that layer is Lua-side.

## Writing up what you find

Per `CLAUDE.md`, the `investigator` role writes dated findings to the `research/` directory of the
module the finding is about (`world-model/research/`, `aircraft-layer/research/`, …) in the format
from `docs/concept/WORLD_MODEL_BUILDER.md`. Record the install version from `autoupdate.cfg`
alongside any claim about file layout — DCS updates move things.
