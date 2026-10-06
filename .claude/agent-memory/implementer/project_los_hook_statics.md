---
name: los-hook-statics
description: BL-11 Stage 4 — statics enumeration in the LOS Hook; how to syntax/GETGLOBAL-check a dostring_in-bridged chunk and splice a constant into it
metadata:
  type: project
---

`fix/los-hook-statics` (2026-10-06): `coalition.getStaticObjects` added alongside
`coalition.getGroups()`/`getUnits()` in `petrobrain-line-of-sight-hook.lua`.

**The bridged-chunk checks are mechanical and worth scripting once.** A `dostring_in` chunk lives
in a string literal, so `luac5.1 -p` on the outer file never sees it. Extract it to its own file —
**including any load-time-spliced prefix lines**, or the extracted chunk has undeclared locals and
the GETGLOBAL sweep reports a false positive. A ~12-line Python extractor (find
`local LOS_CODE = `, then the `[[` … `]]` span, prepend the spliced constants) is enough. The sweep
output to expect for a scripting-state chunk: Lua stdlib plus `coalition, env, land, Object, world,
timer` and any deliberate mission-scripting globals. Any of the script's *own* helper names in that
list is the no-hoisting bug.

**Splicing a constant into a bridged chunk is fine and is not the "runtime-value splice" the
Security argument is about.** The chunk cannot see the outer file's `local`s, so a duplicated
literal is otherwise unavoidable. `"local X = " .. string.format("%d", CONST) .. "\n" .. [[…]]` at
module load. Say so explicitly in the header next to the existing `SET_LOOK_TEMPLATE` argument, or
the next reader will conflate the two. The `%d` guard test only inspects `SET_LOOK_TEMPLATE`, so
this does not trip it.

**When a second population must get "the same filters" as an existing one, extract the filter.**
Re-typing it is how the two drift. Here the unit loop's bubble/wedge/name/ownship logic became one
`considerCandidate(obj, isStatic)` that both loops call — "same filters" is then structurally true
rather than a promise in a comment.

**`StaticObject` has `getName()`/`getPoint()` but NOT `getObjectID()`** (measured 94/94 in
`aircraft-layer/research/2026-10-06-unit-id-join-results.md`). So there is no integer key spanning
units and statics, and `getName()` is not a fallback — it is the only option. Do not "fix" it.

**A worktree has no `.venv`** (gitignored, not copied). `aircraft-layer/.venv/bin/<tool>` resolves
only in the main checkout; invoke those binaries by absolute path while `cd`'d into the *worktree's*
subproject dir, so mypy's CWD-only config discovery and pytest's `pythonpath` still resolve against
the worktree.

Related: [[feedback_verify_full_suite_not_just_new_files]],
[[project_dcs_driven_los_stage1_3]].
