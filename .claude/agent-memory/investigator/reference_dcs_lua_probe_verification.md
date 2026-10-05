---
name: dcs-lua-probe-verification
description: Mechanically verify a DCS Lua probe without DCS — catch accidental globals (the no-hoisting bug) via luac5.1 -l, and syntax-check the bridged inner chunk separately.
metadata:
  type: reference
---

Two checks that make a `dostring_in`-based DCS probe verifiable with no DCS available. Both were
used on `aircraft-layer/dcs-export/petrobrain-unit-id-join-probe-hook.lua` (2026-10-06).

## 1. The no-hoisting bug class IS mechanically detectable — use `luac5.1 -l`

`aircraft-layer/CLAUDE.md` says `luac5.1 -p` cannot see the `push_ptt_state` failure (a function
referencing a `local` declared below it compiles the name as a *global*, `nil` at call time) and
that `luacheck` is not installed. Both true — but the bug has an exact bytecode signature:

```sh
luac5.1 -l -p <file.lua> | grep -o 'GETGLOBAL.*; .*' | sed 's/.*; //' | sort -u
```

This lists every global name the chunk actually reads. **If any of the script's own helper function
names appear in that list, that is the bug.** A clean result contains only Lua stdlib (`pcall`,
`string`, `table`, `math`, `type`, `tostring`, `ipairs`, `pairs`, `require`) and genuine DCS APIs
(`log`, `net`, `DCS`, `coalition`, `coord`, `world`, `timer`, `land`, `Unit`, `Object`,
`StaticObject`). It also catches typo'd API names for free.

Prefer this over eyeballing declaration order — eyeballing is what failed in 2026-09-23.

## 2. `luac -p` on the outer file proves nothing about the bridged chunk

The code that actually runs in the mission-scripting state lives inside a long-bracket string
literal, and `luac` does not look inside strings. **Extract it and check it separately**: find the
`[==[` / `]==]` line numbers with `grep -n`, `sed -n '<start+1>,<end-1>p'` into a scratch `.lua`,
then run both checks above on it. Use `[==[ ... ]==]` (not `[[ ]]`) for the literal so the inner
chunk can contain `]]`.

Must be **Lua 5.1** (`luac5.1`, present at `/opt/homebrew/bin/luac5.1` on the Mac) — DCS embeds 5.1
and a newer `luac` accepts syntax DCS rejects.

## 3. Correlating the two Lua states without names

Export.lua's state and the mission-scripting state share no globals, so a probe spanning them needs
a correlation key. Three that work, strongest first — see
[[dcs-cross-state-correlation-anchors]] if that gets written up separately:

- **Ownship is an exact, name-free anchor.** `Export.lua` flags one object `is_ownship: true` by
  comparing the `LoGetWorldObjects` key against `LoGetPlayerPlaneId()`, so that object's
  `object_id` is a known-good table key for a known unit. Log `world.getPlayer():getID()` /
  `:getObjectID()` from the scripting side and it is a single integer comparison.
- **`coord.LOtoLL` inside the scripting state** gives lat/lon in the same units
  `/world_objects/latest` reports, so objects pair positionally — the only route that covers
  nil-named and duplicate-named objects.
- Unique names, as a cross-check only.

Related: [[project_aircraft_layer_live_io]] (Export.lua vs Mission Scripting sandboxes).
