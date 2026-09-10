### Debug Report

### Observed Issue
Live acceptance testing on `feature/bl5-tool-api` (`--console --overlay` REPL): typing
`situation` crashed with

```
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same
thread. The object was created in thread id 6181023744 and this is thread id 8451039616.
```

Traceback: `logger.py main() -> _run_console_repl -> console.handle_line -> belief/console.py
_dispatch -> _handle_situation -> tools.get_situation -> tools.describe_our_position ->
enrichment.py semantic_facts_for -> world-model/src/query/describe.py describe_position ->
world-model/src/store/reader.py sample_grid -> _load_grid_meta -> conn.execute(...)`.

### Hypothesis
Same bug class as the PB-2 Stage 6 live fix (`sqlite3.Connection` is thread-affine), but in a
field Stage 6 didn't cover. BL-3 added `ConsolePerceptionRunner.enrichment`
(`belief.enrichment.EnrichmentContext`), built and updated by `_run_console_poll_loop` on the
background poll thread, holding that thread's `world_model_conn`. `logger.py`'s
`_run_console_repl` (foreground/REPL thread, reads stdin) copied `runner.enrichment` straight
into `Console.enrichment` before every command. Any enrichment-aware console command
(`situation`, `position`, `place`, and `show`/`contacts`/`find` once BL-3 landed) then ran a
query against the poll thread's connection from the REPL thread — a different `threading.Thread`
than the one that created it — raising `sqlite3.ProgrammingError` on first use.

This is latent since BL-3 merged; BL-5's `situation`/`position` commands were simply the first
ones a live user happened to type that route through enrichment from the REPL thread. `show <id>`
with enrichment set would trigger the identical crash.

### Evidence
- Read `body-layer/src/logger.py` in full: confirmed `_run_console_repl` (`console.enrichment =
  runner.enrichment`) and `ConsolePerceptionRunner.run_once` (which builds/updates `self.enrichment`
  with `self.world_model_conn`, itself opened on the poll thread by `_run_console_poll_loop` per
  the Stage 6 fix).
- Read `body-layer/src/belief/enrichment.py`: `EnrichmentContext.conn: sqlite3.Connection` is
  used directly by `semantic_facts_for` -> `describe_position` -> (world-model) `sample_grid` ->
  `conn.execute`, with no thread-safety wrapping.
- Read `body-layer/src/belief/console.py`: `_handle_situation`/`_handle_position`/`_handle_place`
  (and `_handle_contacts`/`_handle_show`/`_handle_find`) all forward `self.enrichment` into
  `belief.tools` functions unchanged — every one of them would hit the same bug once enrichment
  is non-`None`.
- Reproduced directly: ran the *pre-fix* `_run_console_repl(runner, console)` against a real
  background poll thread and a real `store.writer.open_for_build`-created sqlite file, feeding
  `"situation\n"` via a monkeypatched `sys.stdin` on the calling (different) thread — this raised
  the exact `sqlite3.ProgrammingError` from the live traceback. Confirmed the same driver does
  not raise once the fix is in place.

### Fix Applied
`body-layer/src/logger.py`: `_run_console_repl` no longer reads `runner.enrichment`. It now takes
two additional parameters (`world_model_db: Path`, `theatre: str`) and lazily builds its own
REPL-thread-local `sqlite3.Connection` (`repl_conn`, via `open_world_model`) and
`belief.enrichment.EnrichmentContext` (`repl_enrichment`) the first time
`runner.last_ownship_state` is available — mirroring the Stage 6 fix's own precedent ("build the
thread-affine resource on the thread that uses it") rather than inventing a new pattern.
`repl_enrichment.ownship` is refreshed from `runner.last_ownship_state` before every command
(plain attribute read across the thread boundary — safe, same pattern `last_t_sim` already uses).
`repl_conn` is closed in `_run_console_repl`'s `finally` block. `main()`'s call site updated to
pass `args.world_model_db`/`args.theatre`.

Considered and rejected:
- `check_same_thread=False`: the poll thread queries its connection every `poll_interval_s`
  (default 1 s) independent of when the operator types a command, so the REPL thread's query and
  the poll thread's query can genuinely overlap — this is real concurrent access, not just
  alternating single-threaded use, so disabling the check risks silent wrong results/corruption
  instead of a loud crash. Rejected as unsafe here, not just a style preference.
- Routing REPL-thread enrichment reads through the poll thread (single shared connection/cache
  via a lock or queue): more "correct" in the sense of one shared `WorldEnrichmentCache`, but a
  materially bigger change (cross-thread call plumbing) for a single-user debug console. Rejected
  as disproportionate for this bug's severity.
- Accepted cost of the chosen fix: two independent `sqlite3.Connection`s and two independent
  `WorldEnrichmentCache`s (poll thread's, REPL thread's). Each recomputes on its own thread's
  first touch of a given contact; this can duplicate work across the two caches but never
  produces incorrect results, since each connection only ever serves reads on its own thread.

### Verification
- Added `test_repl_thread_builds_its_own_enrichment_connection` to
  `body-layer/tests/test_logger.py`: drives the real `_run_console_poll_loop` on a background
  thread against a real (empty-grid) world-model `.sqlite`, then drives the real
  `_run_console_repl` on the test's own thread (a genuinely different thread than the poll loop),
  feeding `"situation\n"` and `"position\n"` through a monkeypatched `sys.stdin`. Confirmed this
  test fails with the exact live `sqlite3.ProgrammingError` against the pre-fix code (temporarily
  reverted `logger.py` via `git stash`, re-ran, restored) and passes against the fix.
- Full suite: `ruff format --check body-layer/src body-layer/tests` (clean),
  `ruff check body-layer/src body-layer/tests` (clean), `cd body-layer && mypy src` (clean,
  strict), `pytest body-layer/tests -q` — 356 passed (355 pre-existing + 1 new), no regressions.
