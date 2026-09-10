### Review Summary

Reviewed commit `1c55c6f` ("Fix cross-thread sqlite connection reuse in console REPL") on
`feature/bl5-tool-api`, against `plans/bl5-tool-api/debug.md`. Bug-fix sequence
(Debugger -> Reviewer -> DoD per AGENTS.md).

Read `body-layer/src/logger.py` in full (current state), the diff for `test_logger.py`, and
`world-model/src/store/reader.py`'s `_load_grid_meta` to check the reproduction claim. Ran
body-layer's full verification suite myself.

**Fix is real and correctly scoped.** `_run_console_repl` (`body-layer/src/logger.py:354-425`)
now takes `world_model_db`/`theatre`, lazily builds its own REPL-thread-local `repl_conn`
(`sqlite3.Connection` via `open_world_model`) and `repl_enrichment` (`EnrichmentContext`) the
first time `runner.last_ownship_state` is available, refreshes `repl_enrichment.ownship` every
loop iteration thereafter, and assigns `console.enrichment = repl_enrichment` — never reading
`runner.enrichment` at all. `repl_conn` is closed in the `finally` block (line 423-425), which
wraps the entire `for line in sys.stdin` loop, so it fires on `KeyboardInterrupt` (caught) and on
any other exception (re-raised after close) alike — no leak on an exception path. `main()`'s call
site (line 517-519) passes `args.world_model_db`/`args.theatre` correctly.

**Poll thread untouched.** `_run_console_poll_loop` and `ConsolePerceptionRunner.run_once` are
unchanged by this diff (confirmed via `git show --stat` — only `logger.py`, `test_logger.py`, and
two docs/memory files touched). The fix is additive: a second connection/context, not a
modification of Stage 6's poll-thread behavior.

**Two `WorldEnrichmentCache`s — reasoning checked, sound.** Each `EnrichmentContext` (poll
thread's, REPL thread's) owns an independent connection and cache; `WorldEnrichmentCache` is
keyed by `contact_id` and recomputes only when `last_position` changed, with no shared mutable
state between the two instances. Worst case is duplicated recomputation work across the two
caches, never divergent/incorrect results, since both ultimately query the same underlying
`.sqlite` file via independent read connections. The debug report's "Considered and rejected"
section explicitly names this cost rather than glossing over it — verified, not just trusted.

**Regression test genuinely reproduces the live bug.**
`test_repl_thread_builds_its_own_enrichment_connection` (`test_logger.py`) drives real threads:
`_run_console_poll_loop` on a background `threading.Thread` against a real sqlite file
(`store.writer.open_for_build`-created schema), waits for `runner.last_ownship_state` to be set
(proof the poll thread completed a real poll), then calls `_run_console_repl` directly on the
test's own thread (pytest's test thread — a genuinely different OS thread than the poll thread)
with `sys.stdin` monkeypatched to `"situation\nposition\n"`. I traced
`_load_grid_meta` (`world-model/src/store/reader.py:279`) and confirmed it calls
`conn.execute(...)` unconditionally on entry, before any "grid has no data" short-circuit — so
the pre-fix code would hit `sqlite3.ProgrammingError` at that call regardless of the grid being
empty, exactly matching the live traceback (`sample_grid -> _load_grid_meta -> conn.execute`).
The test's final assertion (`"requires live ownship telemetry" not in line`) confirms the
enrichment path was actually exercised, not silently skipped. This is a real, non-mocked
reproduction, not a superficial regression test.

**`check_same_thread=False` rejection is sound.** The REPL thread blocks on `sys.stdin` iteration
between commands, but the poll thread runs on its own independent timer (`stop_event.wait
(poll_interval_s)`, default 1s) with no coordination with REPL command timing — so a poll-thread
query and a just-submitted REPL command's query can genuinely land inside the same wall-clock
window. Given that, sharing one `check_same_thread=False` connection between the two threads would
risk real concurrent access to the same `sqlite3.Connection` object (silent corruption risk per
SQLite's own threading caveats), not merely alternating single-threaded access. Building a second,
independent connection (this fix) avoids that risk entirely by construction. Sound, not overly
cautious.

**No other missed call sites.** Grepped for `runner.enrichment` / `console.enrichment =` across
`body-layer/src` and `body-layer/tests`: the only remaining live reference is the fix itself
(`logger.py:419`, `console.enrichment = repl_enrichment`); all other hits are docstring prose.
`belief/console.py`'s `_dispatch` reads `self.enrichment` (i.e. whatever `Console.enrichment` was
last set to) uniformly for every enrichment-aware command
(`situation`/`position`/`place`/`show`/`contacts`/`find`), so fixing the one assignment point in
`_run_console_repl` covers all of them — consistent with the debug report's claim.

**Verification (ran myself, `body-layer/.venv/bin`):**
- `ruff format --check src tests` — clean (48 files)
- `ruff check src tests` — all checks passed
- `mypy src --strict` (from `cd body-layer`) — no issues, 24 source files
- `pytest tests -q` — **356 passed**

`git status --short` on the branch is clean; no untracked/unstaged files.

### Required Fixes

None.

### Optional Refinements

- None worth flagging — the fix is minimal, mirrors an established precedent (Stage 6) exactly,
  and the debug report's own "Considered and rejected" section already documents the two
  alternatives (shared connection via `check_same_thread=False`, routing REPL reads through the
  poll thread) and why they were passed over. No further scope reduction or expansion applies.

### Verdict
APPROVED

### Next step (not a Reviewer/DoD substitute)

This fixes the reproduced crash and passes automated verification, but **BL-5 live acceptance
testing was interrupted by this bug and has not been completed**. The user still needs to re-run
the live console session (`--console --overlay`) to confirm `situation` no longer crashes, and
complete the remainder of the acceptance test script (`place`/`position`/`situation`/the full
tactical sequence) before BL-5 can be considered done end-to-end. Automated tests and this review
confirm the fix is correct in isolation; they cannot substitute for the live DCS acceptance pass.

### Review Confidence
Full read — read `logger.py` in full (current state), the complete diff (`git show 1c55c6f`),
traced `_load_grid_meta` in `world-model/src/store/reader.py` to verify the reproduction claim,
grepped for missed call sites across `body-layer/src` and `body-layer/tests`, and ran the full
verification suite myself rather than trusting the debug report's reported numbers.
