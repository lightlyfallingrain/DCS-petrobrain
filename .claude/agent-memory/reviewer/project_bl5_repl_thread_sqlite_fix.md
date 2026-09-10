---
name: bl5-repl-thread-sqlite-fix
description: BL-5 fix for REPL-thread reuse of poll-thread sqlite3.Connection via ConsolePerceptionRunner.enrichment; recurring bug class to re-check on new fields
metadata:
  type: project
---

Commit 1c55c6f (feature/bl5-tool-api) fixed a second instance of the PB-2 Stage 6 thread-affinity
bug: BL-3's `ConsolePerceptionRunner.enrichment` (built on the poll thread, holding that thread's
`sqlite3.Connection`) was being copied into `Console.enrichment` and queried from the REPL thread.
Stage 6 only fixed `.sources`; `.enrichment` shipped later and wasn't covered. Fix mirrors Stage
6's precedent exactly: `_run_console_repl` now builds its own thread-local connection +
`EnrichmentContext`, closed in `finally`. Verified sound: real two-thread regression test, no
required fixes, 356 tests pass. APPROVED, no fixes needed.

**Why:** `sqlite3.Connection` is thread-affine by default in this codebase (`open_world_model`
never overrides `check_same_thread`), and `logger.py` has two long-lived threads (poll + REPL)
sharing a `ConsolePerceptionRunner`. Any *new* field added to that runner which holds or derives
from a `sqlite3.Connection` — and is then read by the REPL thread — reintroduces this exact bug
class.

**How to apply:** When reviewing any future body-layer change that adds a field to
`ConsolePerceptionRunner` (or any object built on the poll thread and read by the REPL thread) and
that field is a `sqlite3.Connection` or holds one (directly or via something like
`EnrichmentContext`), explicitly check whether the REPL thread ever reads it. Grep
`_run_console_repl` and `belief/console.py`'s `Console` fields for the new attribute. Don't assume
Stage 6's fix covers all future fields — it only covered `.sources` at the time.
