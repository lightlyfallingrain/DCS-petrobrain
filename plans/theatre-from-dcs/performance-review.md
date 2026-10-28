### Performance Review

Scope: `feature/theatre-from-dcs`, one commit (`137906bb`) over `main`
(`cedf604f`). `body-layer/src/body.py` -- startup without a store
(`--world-model-dir` alone), first-poll theatre adoption, REPL thread
following `runner.world_model_store` instead of a startup-bound path.

This is a one-off setup/transition path (process startup, and a rare
theatre-change event thereafter), not a per-tick hot path. Budget context:
no hard real-time budget applies in this phase (Petrobrain Runtime has not
started); the constraints that do apply here are "no blocking of work that
should be async" and "no per-request allocation on a path that runs every
poll."

### Findings

#### First-poll theatre adoption opens a full-theatre store on the poll thread

- **Location:** `_check_for_new_mission` (first-poll branch, `runner.
  last_mission_start_sequence is None`) calling `_maybe_switch_theatre` ->
  `open_world_model` (`sqlite3.connect(..., mode=ro)`) and `_build_sources`,
  in `_run_crew_text_poll_loop`.
- **Risk:** none credible. `open_world_model` is a bare
  `sqlite3.connect("file:...?mode=ro", uri=True)` -- it opens a file handle,
  it does not read the ~0.9 GB file into memory. `_build_sources` only
  constructs `HybridPerceptionSource`/`NakedEyePerceptionSource` objects
  (and optionally `ForestOcclusion`), no eager query against the store.
  Actual page-ins happen lazily, on the indexed point/grid queries each
  poll already issues (`describe_position`, `sample_grid`) -- this diff
  does not change what those queries cost, only when the connection that
  backs them is opened. The call is also gated to run at most once per
  mission (re)start, not every poll: `_check_for_new_mission` returns
  early on an unchanged sequence number before reaching this branch.
- **Mechanism is not new.** `_maybe_switch_theatre` itself is pre-existing
  (BL-15 Stage 3, already merged) and already runs this exact
  open+rebuild sequence whenever DCS reports a theatre change mid-run.
  This diff's only change is calling the existing function one poll
  earlier (on the first poll of a process, instead of only on a later
  change) -- it does not introduce a new cost shape.
- **Action:** MONITOR. If a live sortie ever shows a poll-loop stall at
  process start or at a mission restart, profile `sqlite3.connect` and the
  first `describe_position`/`sample_grid` call against a cold page cache
  (e.g. after a reboot, before the OS has cached the 0.9 GB file) -- that
  is the one scenario where first-touch page-in cost could be visible, and
  it is a one-time, one-poll cost even then, not a recurring one.

#### REPL thread's per-command tuple compare and conditional reconnect

- **Location:** `_run_crew_text_repl`, `store = runner.world_model_store;
  if store != repl_store: ...`.
- **Risk:** none. A 2-tuple `(str, Path)` equality check is two
  reference/string/hash comparisons, run once per typed REPL command (a
  human-paced input, not a poll-rate one) on a thread that already does
  far more per command (`EnrichmentContext` construction, belief queries).
  The reconnect (`open_world_model` + fresh `EnrichmentContext`) only runs
  on the tuple actually changing, i.e. on a theatre switch -- a rare event,
  not a steady-state cost. This is cheaper than the pattern it replaces
  (a startup-bound path that never followed a theatre switch at all, which
  was a correctness bug, not a performance concern).
- **Action:** NONE.

#### No per-request allocation introduced on the poll hot path

- Poll-loop steady state (`emit_mode="every_poll"`, every tick once a
  store is loaded) is unchanged by this diff -- the new code paths are all
  guarded by "store not yet loaded" or "sequence changed," both one-time
  or rare conditions. No new allocation, iteration, or query was added to
  the unconditional per-poll body.

### Verdict
APPROVED
