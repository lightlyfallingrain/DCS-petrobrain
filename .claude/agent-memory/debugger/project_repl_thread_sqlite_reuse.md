---
name: repl-thread-sqlite-reuse
description: body-layer's console REPL thread must never read a sqlite3.Connection or EnrichmentContext built by the poll thread, or any other worker thread.
metadata:
  type: project
---

`body-layer/src/logger.py`'s `--console` REPL splits work across two real OS threads: a
background poll thread (`_run_console_poll_loop`) and the foreground REPL thread reading stdin
(`_run_console_repl`). PB-2 Stage 6 fixed one instance of "a `sqlite3.Connection` opened on one
thread, queried from another raises `sqlite3.ProgrammingError`" (`ConsolePerceptionRunner.sources`
/ `NakedEyePerceptionSource`'s terrain LOS gate). BL-3 added a *second* thread-affine field
(`ConsolePerceptionRunner.enrichment`, holding `world_model_conn`) built on the poll thread, and
`_run_console_repl` copied it straight into `Console.enrichment` — same bug class, different
field, not caught until live acceptance testing found it via `situation`/`position`
(`plans/bl5-tool-api/debug.md`). It had been latent since BL-3 shipped; `show <id>` with
enrichment would have hit it too.

**Why:** every new field this file adds that wraps a `sqlite3.Connection` (directly, or inside
something like `EnrichmentContext`) needs its own thread-affinity check — the existing Stage 6
fix does not generalize automatically to new fields added later by unrelated work.

**How to apply:** when reviewing/debugging any future body-layer change that adds a field to
`ConsolePerceptionRunner` or threads a new value from the poll thread into the REPL thread (or
vice versa), check whether that value transitively holds a `sqlite3.Connection`. If it does, it
needs its own thread-local build (lazy, on the consuming thread) — plain attribute reads (e.g.
`last_t_sim`, `last_ownship_state`) are fine to share across threads; only the `sqlite3.Connection`
itself is not. `check_same_thread=False` was considered and rejected for this file: the poll
thread queries on its own fixed interval independent of REPL input, so genuine concurrent access
is possible, not just alternating single-threaded use — disabling the check risks silent wrong
results, not just a louder crash.
