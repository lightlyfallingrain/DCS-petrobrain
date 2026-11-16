---
name: ac-b12-export-lua-module-split-deep-analysis
description: AC-B12/AC-B13 (Export.lua split into dofile-loaded Petrobrain/ modules) Mode 2 deep security analysis -- APPROVED; the dofile loader has zero network-influenced path construction, bare-global publishing collides with no DCS API, and E-P6/AC-B13 both independently re-verified against the split rather than trusted from the review.
metadata:
  type: project
---

Reviewed `feature/ac-b12-export-modules` at `c304dcc5` (commits `6919c86d`/`0812e98f`/`c304dcc5`
against pre-split `fab32110`) after Reviewer's round-2 approval. Full account:
`plans/ac-b12-export-modules/security.md`. Verdict: APPROVED.

**What this split actually changes, security-wise, and what it does not.** The `dofile` loader
(`Export.lua:208-262`) is the one genuinely new mechanism a module-split review should check first:
`MOD_DIR` is a fixed base path, and the 7 module names passed to `load_module` are **source-code
string literals**, never anything from the network/wire/collector -- confirmed by reading the 7
call sites directly, not inferred from the plan's description. A malicious/replaced module file on
disk would still execute via `dofile`, same as the pre-split single file would with a malicious
`Export.lua` -- but that already requires local filesystem write access equivalent to code-exec on
the box, not a privilege this feature grants a LAN attacker. **General lesson for the next
`dofile`/`require`-based module split on this project: check whether any path component comes from
anywhere other than a literal in the loader's own source before concluding "no injection" --
it is fast to check and the one place a module split could introduce something genuinely new.**

**Bare-global publishing (new with this split) collides with no DCS API, and the real exposure is
self-inflicted, not attacker-reachable.** `core.lua` publishes ~14 generic names (`client`,
`safe_call`, `debug_log`, etc.) into `_G` so the 8 `dofile`'d chunks (which share no locals) can call
each other's helpers unqualified -- checked every name against the known DCS Export API surface
(`Lo*`, `GetDevice`, `list_indication`, `LuaExport*`, `net`/`log`/`lfs`/`io`/`os`/`socket`): no
collision. The only real collision scenario is the user manually chaining a *second* independent
Export-side add-on into the same Lua state (DCS loads exactly one `Scripts\Export.lua`) -- and that
add-on would already run with full `io`/`lfs`/socket privilege in that state, so a name collision
grants it nothing it couldn't already do by writing `_G` directly. Rated low/low and presented to
the user as a Risk Communication item (not filed as a backlog item) rather than fixed unilaterally,
since fixing it (prefixing every published global) is itself a non-trivial textual change across
every module body per
`.claude/agent-memory/implementer/project_export_lua_split_test_harness_dictates_global_local_boundary.md`'s
finding 1 (the Lua test harness's extraction regex depends on these exact bare names).

**Two project invariants independently re-verified against the split, not trusted from the plan or
review:** E-P6 (`HDG LOS`/short-right never pressed) -- `grep -rc AI_WHEEL_RIGHT` across every
production `dcs-export/*.lua` and `dcs-export/Petrobrain/*.lua` file (not just the files the plan
says changed) returns 0 everywhere; AC-B13's `ai_pilot_wheel.lua:on_stop` (`M.on_stop`, lines
687-708) releases unconditionally with a hardcoded `0` (release) value baked into the call site, so
the fix cannot itself press anything by construction, not merely by convention. Also ran
`luac5.1 -p` directly against every one of the 8 new module files plus `Export.lua` in this
worktree (all clean) rather than relying on the Reviewer's own account of having done so --
`aircraft-layer/CLAUDE.md`'s own warning that `luac -p` only proves syntax, not behaviour, still
applies, but it is one command and catches the `local`-declared-below-its-use class this project has
hit twice before.

See also `.claude/agent-memory/architect/project_export_lua_module_split_cross_file_sharing.md`,
`.claude/agent-memory/implementer/project_export_lua_split_test_harness_dictates_global_local_boundary.md`,
and `.claude/agent-memory/reviewer/project_ac_b12_export_lua_module_split_review.md` +
`project_ac_b12_export_lua_module_split_round2_approved.md` (architect/implementer/reviewer memories
on this same split).
