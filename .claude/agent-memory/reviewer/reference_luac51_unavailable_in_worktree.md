---
name: reference-luac51-unavailable-in-worktree
description: luac5.1 often missing in a reviewer's worktree; luac5.5's own-helper-leak scan uses GETTABUP/_ENV, not GETGLOBAL
metadata:
  type: reference
---

`aircraft-layer/CLAUDE.md`'s own-helper-leak check (a `local` referenced before its declaration
compiles to a global lookup, `nil` at call time — the `push_ptt_state` incident) is written against
`luac5.1 -l -p <file> | grep GETGLOBAL`. `lua5.1`/`luac5.1` is frequently **not installed** in an
agent worktree (only `luajit`/`lua5.5`/`lua` via Homebrew on this Mac). `luac5.5` is a different
bytecode format with **no `GETGLOBAL` opcode at all** — a global read compiles to `GETTABUP ... ;
_ENV "name"` instead. The recipe does not transfer byte-for-byte; the 5.5-equivalent scan is:

```sh
luac5.5 -l -p <file> | grep -E 'GETTABUP.*_ENV' | grep -oE '"[A-Za-z_0-9]+"$' | sort -u
```

**Why this doesn't block a review**: `luac5.1 -p` (syntax-only, no `-l`) still works fine on 5.5 for
the syntax check, and the implementer's own `debug.md`/verification notes typically report having
run the real `luac5.1` GETGLOBAL scan already — so cross-check with the 5.1-equivalent 5.5 scan
above rather than treating the missing binary as a gap. Install `lua5.1` properly (`apt`/`brew`) only
if a genuine Lua-5.1-vs-5.5 syntax divergence is suspected; the own-helper-leak scan does not need
that specific version, only an interpreter old/new enough to have *some* opcode encoding globals.

Seen on `plans/observ-off-axis-zero/review.md` (2026-10-24).
