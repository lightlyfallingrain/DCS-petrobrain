---
name: ac-b12-export-lua-module-split-review
description: AC-B12 (Export.lua split into dofile-loaded Petrobrain/ modules, AC-B13 folded in) reviewed APPROVED WITH MINOR FIXES -- behaviour preservation verified line-by-line against the pre-split file; the one real gap was a load-time coupling the loader's own per-call call_if guards don't cover.
metadata:
  type: project
---

Reviewed `feature/ac-b12-export-modules` at `6d064b52` against `plans/ac-b12-export-modules/plan.md`.
Verdict: APPROVED WITH MINOR FIXES. Full account in `plans/ac-b12-export-modules/review.md`.

**What held up well, and how it was actually checked (not just read):** traced the original
`LuaExportStart`/`Stop`/`ActivityNextEvent`/`AfterNextFrame` bodies at the pre-split commit
line-by-line against the new loader's composed callbacks, confirming every state reset lands where
the plan's relocation map says and the per-frame/5 Hz call order is byte-for-byte identical (the
implementer correctly deviated from the plan's own illustrative composition snippet, which would
have changed failure semantics around a failed world-objects send). Diffed one normalized handler
(`handle_sight_target_command`) in full against the original and found zero logic drift beyond the
field-extraction relocation the plan called for -- used that as the representative case rather than
diffing all three normalized handlers verbatim, since the extraction shape is mechanically
identical across all three.

**The one real finding: a module-split's stated failure-isolation goal needs checking at *every*
cross-module read site, not just the loader's own `call_if` guards.** The plan's design goal was "one
feature module failing does not take down telemetry or any other module." The loader's `call_if`
wrapper delivers that for every per-tick push call. But `commands.lua`'s dispatch table is built
*once*, at that module's own top level, by indexing `petrovich`/`effectors`/`sight` as bare globals
directly (`handlers = { cockpit_switch = effectors.handle_cockpit_switch_command, ... }`) -- if any
one of those three fails to load, that table construction throws, `commands.lua` itself fails to
load (caught by the same `pcall` as any other module), and **all five** command ops go dark,
including the ones owned by modules that loaded fine. This is a narrower regression than the
pre-split baseline (a syntax error anywhere used to kill the whole single file), but it is still a
real gap against what the plan says the split achieves. Caught by reading the dispatch-table
construction site directly and asking "what happens if one of these three names is nil," not by
reading the loader's own guards (which are correct) and assuming the pattern was applied everywhere
symmetrically. **General lesson: when a plan states a failure-isolation property for a module split,
grep every cross-module reference for whether it is `call_if`-style guarded, not just the call sites
the loader itself owns** -- a dispatch table, a cached reference, or any other one-time
cross-module wiring built outside the loader's own composed callbacks is a second place the same
property has to be re-earned.

**Also useful for a future Lua-module-split review:** the implementation log's own "Notable
Discoveries" claimed a pruned ordering comment kept "the rest of each comment... relative to
genuinely still-local same-file constants." Tracing the actual 4 occurrences against the original
file showed the claim was imprecise -- one occurrence was in a different file than stated
(`telemetry.lua`, not `sight.lua`), and in the two `sight.lua` occurrences checked, the *entire*
ordering note was removed, not a partial prune. The actual ordering was still correct (confirmed by
grepping declaration line numbers), and `test_dcs_export_lua_local_order.py` mechanically re-proves
it on every run, so this cost nothing in practice -- but it is a reminder that an implementation
log's self-description of what it pruned is a claim to verify against the diff, not a fact to carry
into the review as-is. See `.claude/agents/reviewer.md`'s "Checking a pruned comment block" section
-- this is exactly the kind of claim that section exists to make the Reviewer check rather than
trust.

See also `.claude/agent-memory/architect/project_export_lua_module_split_cross_file_sharing.md` and
`.claude/agent-memory/implementer/project_export_lua_split_test_harness_dictates_global_local_boundary.md`
(the architect's and implementer's own memories on this same split).
