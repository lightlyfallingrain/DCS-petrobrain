### Review Summary

Reviewed BL-15 Stages 1-2 as implemented on `feature/bl15-mission-start`
(commits `77dcb5b2`, `bbd09fa8`, `a99bd5a9`, diff base `eab86662`; `b1a72d7c`
is docs only). Scope: aircraft-layer mission-start signal
(Hook `onSimulationStart` -> loopback UDP 7799 -> `MissionStartCache` ->
`GET /mission_start/latest`), body-layer `_check_for_new_mission` +
`reset_for_new_mission()` across `ContactStore`, `TaskStore`,
`MissionMemory`, both perception sources, `ConsolePerceptionRunner`,
`CrewConsole`. Stages 3-4 (theatre switching, live acceptance) are correctly
untouched, as instructed, and Decision 1's loud-refusal mode and Decision 5's
per-mission log files are correctly deferred to a later batch (stage1-decisions.md
says so explicitly) — their absence here is not a defect.

Read the full diff (not spot-checked), ran every check myself from inside
each subproject's own venv (using the main checkout's `.venv` binaries, since
the worktree has none of its own — see note at the end), and mutation-tested
the one completeness test the implementer's own notes flagged as load-bearing.

**Completeness against `BL-B68`'s table**: every item in that table is
covered. `attack_run_state`, `optic_state`, `scan_plan` (on
`ConsolePerceptionRunner`), `mission_phase_tracker`, `enrichment`/
`WorldEnrichmentCache`, `attitude_history`, `optic`/`_last_look_direction` all
reset via `ConsolePerceptionRunner.reset_for_new_mission`'s re-invoked
`__init__` (they are not in its preserve-set); both perception sources'
dedup maps (`_object_id_to_last_observation_id`, `_previously_seen_at`,
`_acquired_at`, `_last_emitted_texts`, `_observation_count`, `_dropped_count`)
are cleared explicitly since their constructors can't be wholesale
re-invoked. I checked the one thing the plan explicitly carves out as *not*
needing a reset — `NakedEyePerceptionSource.scan_plan`/`optic`/`sight_cone`/
`suppressed_until_sim` — by tracing `_apply_active_gaze` (`logger.py`
~L1059-1086): all four are unconditionally overwritten from
`runner.scan_plan`/`runner.optic` on every `run_once()` call, which always
runs immediately after `_check_for_new_mission` in both poll loops. The
claim holds; this is not a gap.

**Shared-object ordering (b)**: `runner.store is crew_console.store` and
`runner.tasks is crew_console.tasks` both before and after a reset, because
`ContactStore.reset_for_new_mission`/`TaskStore.reset_for_new_mission`
mutate the existing object in place (`self.__init__()`) rather than
replacing it, and `_reset_mission_state` resets those shared objects exactly
once, before `runner.reset_for_new_mission`/`crew_console.
reset_for_new_mission` pass the same (already-reset) references straight
through. `CrewConsole`'s own completeness test asserts this by identity, not
just equality. The real wiring test
(`test_crew_text_poll_loop_resets_belief_on_mission_restart`) drives the
actual poll loop and confirms both `runner.tasks` and
`crew_console.commands_handled` reset together.

**`init=False` trap (c)**: confirmed correctly handled for
`ConsolePerceptionRunner._last_look_direction` (the one field of this shape
on either `ConsolePerceptionRunner` or `CrewConsole` — I independently
re-checked every `field(...)` declaration on both classes and found no
second instance). I mutation-tested this directly: removing the explicit
`self._last_look_direction = None` line restores the trap, and
`test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest`
fails immediately with a clear message naming the exact field. Confirms the
completeness test is load-bearing, not decorative.

**Would the completeness tests catch a newly-added, unreset field (d)?**
Yes for the five classes using the re-invoked-`__init__` pattern
(`ContactStore`, `TaskStore`, `MissionMemory`'s state minus the sink,
`ConsolePerceptionRunner`, `CrewConsole`) — `dataclasses.fields()`/`vars()`
enumeration at test time means a new field is automatically poisoned and
checked, with no hand-maintained list to fall out of sync. **No** for
`NakedEyePerceptionSource`/`HybridPerceptionSource` — their reset tests
(`test_reset_for_new_mission_clears_dedup_and_counter_state`) assert a fixed,
hand-written list of attribute names; a new dedup/counter field added to
either class later would silently leak across a mission restart with no
test failure. This is explicitly acknowledged in the plan ("no cheap 'fresh
instance' to diff against" — the constructors require live collaborators
that can't be re-synthesized for a throwaway comparison instance) and is not
a scope deviation, but it is the one place this plan's own safety property
("a newly added field resets by default") does not actually hold. See
Optional Refinements.

**Thread safety (e)**: no new hazard. The `--console` REPL
(`belief.console.Console`) and the `--crew-text` crew console
(`belief.crew_console.CrewConsole`) both hold `store`/`tasks` by reference
from before any reset; since reset mutates those objects in place rather
than replacing them, no stale reference is created. Concurrent read/write
between the poll thread and the REPL thread on `ContactStore`'s internal
dicts is a pre-existing property of this codebase (not introduced or
worsened by this change) — `ContactStore.ingest`/`tick` were never
synchronized against the REPL thread before this feature either.

**First-poll no-op (f)**: correct and tested four ways
(`test_check_for_new_mission_does_nothing_on_first_poll_even_with_sequence_present`,
plus the sequence-change/unchanged/empty-cache cases). `None` is used as the
"never checked" sentinel, distinct from "sequence 0 seen," matching Decision
2 ("yes" to "no reset on first poll").

**Schema rejection (g)**: `MissionStartEvent.from_dict` rejects missing
`sequence`, non-int `sequence`, `bool`-as-`int`, and non-string `theatre`,
mirroring `F10CommandEvent.from_dict` exactly as the security plan review's
carried-forward requirement asked. `MissionStartReceiver._handle_datagram`
drops non-JSON, non-dict, and schema-rejected payloads at debug level without
crashing the receive loop. Verified by reading `test_mission_start_schema.py`
(8 cases) and `test_mission_start_receiver.py`.

**Decisions 1 and 5 (next batch)**: confirmed absent from this diff, as
instructed — no loud-refusal-mode code, no per-mission log file rolling.
Correctly out of scope here.

**Checks** (run myself, from inside each subproject, using the main
checkout's `.venv` since the worktree has none of its own — see note below):
- aircraft-layer: `ruff format --check src tests` / `ruff check src tests` —
  pass. `mypy --strict src` (run via `cd aircraft-layer && mypy src`) —
  pass, 25 source files. `pytest tests -q` — 374 passed.
  `luac5.1 -p` on the new Hook script — pass.
- body-layer: `ruff format --check src tests` / `ruff check src tests` —
  pass. `mypy --strict src` — pass, 68 source files. `pytest tests -q` —
  2179 passed, 4 xfailed (pre-existing, unrelated to this change — confirmed
  by name, all concern unrelated modules).
- A whole-subproject `ruff format --check .`/`ruff check .` on both
  subprojects (not scoped to `src`/`tests`) fails, but only on two
  pre-existing, untouched `research/*.py`/`research/*.md` files (one each in
  aircraft-layer and body-layer) — confirmed by diffing the touched-file
  list against the failures; neither file is in this feature's diff. Not
  this feature's problem, not flagged as a required fix.

### Required Fixes

None.

### Optional Refinements

- **`NakedEyePerceptionSource.reset_for_new_mission`/
  `HybridPerceptionSource.reset_for_new_mission` have no completeness
  guarantee against a future added field** (see "(d)" above) — their tests
  assert a fixed list of attribute names rather than enumerating the
  dataclass's actual fields. A cheaper partial fix than "diff against a
  fresh instance" (which the plan correctly rules out, since the
  constructors require live collaborators): a test that enumerates
  `dataclasses.fields()` on each class and asserts every field name is
  accounted for by one of three buckets — the constructor-required/preserved
  set, the explicit per-poll-overwritten set (`scan_plan`/`optic`/
  `sight_cone`/`suppressed_until_sim`/`live_los_coverage`), or the
  explicit dedup/counter set `reset_for_new_mission` clears. A field
  matching none of the three fails the test by construction, without
  needing a throwaway "fresh" instance. Worth doing before this becomes the
  next `BL-B68`-shaped gap, but not blocking — the plan already named this
  tradeoff and it is symmetric with the costs it was traded against.
- **`LiveLosCoverage` (`NakedEyePerceptionSource.live_los_coverage`) is not
  reset and not mentioned anywhere in the plan or `BL-B68`'s table.** On
  inspection this looks like a deliberate omission rather than a gap — its
  own docstring describes it as "an always-on regression guard... for the
  lifetime of the source," summed and logged once at end-of-run
  (`_log_live_los_coverage_summary`), not pilot-facing belief state — so
  carrying it across a mission restart is arguably correct (it is a coverage
  metric about the terrain model, not about the current mission). Flagging
  only because it is the one piece of `NakedEyePerceptionSource` state the
  diff is silent on; if it is meant to be per-mission (e.g. a debrief tool
  wants per-sortie coverage numbers once Stage 3's theatre switching can
  change the underlying model mid-run), it will need the same treatment that
  dedup/counter state got.

### Verdict

APPROVED

### Review Confidence

Full read — read every changed file in the diff, including all touched
tests across both subprojects, both `ROADMAP/` entries, the security plan
review, and the user's own decisions. Ran format/lint/type/test myself in
both subprojects (not trusting the implementer's own report) and
mutation-tested the one load-bearing completeness test to confirm it
actually fails when the mechanism it guards is removed.

**One environment note, not a scope gap**: this worktree was created with no
`.venv` in either subproject (git worktrees don't carry gitignored
directories). I ran every check using the main checkout's
`<subproject>/.venv/bin/<tool>` binaries invoked from inside this worktree's
subproject directories (`cd <worktree>/aircraft-layer && /Users/sg/Code/
DCS-petrobrain/aircraft-layer/.venv/bin/mypy src`, same pattern for
body-layer) — `mypy`'s CWD-only config discovery still resolves correctly
this way since the config file is read from the CWD, not from the
interpreter's own location. Results matched the implementer's own reported
counts exactly.
