# Definition of Done — `feature/theatre-from-dcs`

**Scoped to tip `4ba0bcf32340a56cdb392675f223cb6a8fc47e41`** ("BL-15: note the first-event
staleness risk (reviewer recommendation)"). If the branch moves after this check, this verdict
no longer covers it.

## Request

User (verbatim): *"We can now give body layer the directory where world model files are, but it
also requires mission understanding file. Change it so that mission understanding file is not
required, used theatre is read at mission start from DCS and then the correct world model file
is chosen automatically."*

Implemented: `--world-model-dir` alone now suffices to start body-layer. The theatre is read from
the aircraft-layer's `GET /mission_start/latest` on the first poll of the process (previously a
no-op there) and on every subsequent mission (re)start, via the pre-existing, already-reviewed
`_maybe_switch_theatre`. `--mission-understanding` is now fully optional (mission-phase input
only). Matches the request exactly — no unplanned scope added.

## Code Quality

Subprojects touched (derived from the diff, not memory): `body-layer` only (plus `.claude/`
agent-memory and `plans/`, neither a subproject). Commands run fresh, from inside
`body-layer`, against the worktree's own files, using `/Users/sg/Code/DCS-petrobrain/body-layer/.venv`:

| Check | Result |
|---|---|
| `ruff format --check src tests` | 178 files already formatted |
| `ruff check src tests` | All checks passed! |
| `cd body-layer && mypy src` | Success: no issues found in 77 source files |
| `pytest tests -q` | 2695 passed, 4 xfailed, **5 failed** |

The 5 failures (`test_load_effector_config_round_trips_the_real_committed_files`,
`test_round_trip_against_the_committed_registry`,
`test_load_registries_by_aircraft_discovers_the_real_mi24p_directory`,
`test_every_shipped_sequence_file_round_trips`,
`test_switch_reference_matches_the_generator`) are pre-existing. Verified by running the same
`-k` selection against `main` at `cedf604f` (the root checkout) directly: identical 5 failures,
same names, same assertions (stale `switch-reference.md` / an effector-registry round-trip
mismatch unrelated to this diff — `body.py` does not touch the effector-sequence machinery).
Not introduced by this branch.

No panics/unhandled errors in data paths (the new code path's one failure mode —
no-theatre-yet — degrades to the existing refusal mode, not an exception; verified by direct
dry run below). No debug prints or TODOs introduced by this diff (grepped the `body.py` diff for
`TODO`/`FIXME`/`print(`/`pdb`; the one `print(...)` found is the new startup status line to
stderr, `"theatre: not given -- waiting for DCS to report it at mission start"`, not debug
leftover).

## Scope & Correctness

- No `plans/theatre-from-dcs/plan.md` exists — Reviewer confirms this was **correctly scoped as a
  small, direct change per the dispatch brief**, consistent with this project's "Bug fix"/small
  direct-change role sequence (no separate Architect plan for this size of change).
- No unplanned scope added — `review.md` traces every write site of
  `world_model_conn`/`theatre`/`world_model_store` and confirms the change is exactly the
  requested behaviour plus the REPL-thread live-follow fix it necessarily implies (the REPL was
  previously bound to a startup path/theatre and could not have followed a `--world-model-dir`
  that initially has no store).
- No CLAUDE.md invariants violated: no-omniscience boundary untouched; the world-model seam
  stays in-process/same-box; `Percept` boundary untouched; additive-CLI-flag posture upheld
  (`--mission-understanding` degrades to fully optional rather than removed).
- All new/modified files staged — confirmed via `git status --porcelain` below (clean after this
  report's own additions are added).

## Testing

New/changed tests (108 lines in `test_mission_start_reset.py`, 89 in `test_body.py`) specifically
exercise the new behaviour: `test_check_for_new_mission_first_poll_loads_the_store_dcs_names`,
`test_check_for_new_mission_first_poll_stays_refused_without_a_theatre`,
`test_check_for_new_mission_first_poll_corrects_a_wrong_initial_theatre`,
`test_enter_refusal_mode_clears_the_store_pair`. These are meaningful, not decorative — they
assert the specific co-moving-state property (`world_model_conn`/`theatre`/`world_model_store`
staying in sync) that is this change's one real correctness risk, matching the "recurring
co-moving state" defect class this project's reviewer memory already flags. No existing tests
were broken (`test_mock_flight_chain.py`'s one-line change updates a fixture call signature, not
an assertion).

## Documentation

- `body-layer/CLAUDE.md` and `body-layer/RUN.md` both updated to describe `--world-model-dir`
  alone as "the usual way," with the refusal-mode behaviour documented until DCS reports a
  theatre. Checked against the actual code (`main()`'s `--help` output and a live dry run, see
  below) — accurate.
- Reviewer's one optional refinement (note the staleness risk in `BL-15.md`) — **addressed**,
  already present in the merged tip's `BL-15.md`.
- `body-layer/ROADMAP/BL-15.md` DoD completion note and `#needs-flight` tag added by this pass
  (see "Live acceptance" below).

## Security

No `security-plan-review.md` — consistent with no separate plan file (nothing to review a plan
for). `security-deep-analysis.md`: **APPROVED**. Findings: the new first-poll call site routes
through the same `_maybe_switch_theatre`/`THEATRE_PROJECTIONS` membership gate as every other
theatre-switch call site, before any path/sqlite construction — reused, not reimplemented. No
new way to reach `open_world_model` with an unvalidated value (every producer of
`world_model_store` traced). Pre-existing loopback-only mission-start channel and
single-user/LAN-only accepted risk model unchanged.

## Performance

`performance-review.md`: **APPROVED**. First-poll theatre adoption opens a connection + builds
sources (bounded to at most once per mission (re)start, not per poll) — not a new cost shape,
just the existing `_maybe_switch_theatre` sequence running one poll earlier. REPL thread's
2-tuple compare per typed command is negligible. No change to the per-poll hot path.

## Acceptance boundary — what this pass's fixtures structurally cannot reach

The DoD check and the fixture-backed test suite verify the *logic*: theatre adoption from a
mission-start event, the refusal-mode gate, the REPL following a live store switch, and
(verified directly below, not just read) that the process genuinely starts and waits without a
crash when given `--world-model-dir` alone. **None of this exercises a real DCS session, a real
aircraft-layer collector, or a real theatre switch mid-flight** — the fixtures and the direct
dry run below use a fabricated `GET /mission_start/latest` response or no response at all, never
a live `onSimulationStart` from DCS. Two things a fixture cannot catch and this pass does not
claim to have ruled out:
- Whether the aircraft-layer collector's *actual* first-poll mission-start payload (timing,
  field names, staleness from a prior session) behaves the way the fabricated test events assume.
- Whether a live theatre switch (two different real missions, back to back, same process) feels
  right in the cockpit — e.g., any audible gap or stale-sounding report during the store swap.

### Commands run directly (not just read), to avoid shipping an unexecuted claim

```
$ cd body-layer && PYTHONPATH=src:../world-model/src <venv>/bin/python -m body \
    --aircraft-layer-url http://127.0.0.1:19999 --audio-adapter-url http://127.0.0.1:19998 \
    --world-model-dir .
theatre: not given -- waiting for DCS to report it at mission start
...
Petrovich crew session -- type naturally, e.g.:
  ...
```
(No crash. Waits as documented, with no live aircraft-layer/audio-adapter reachable.)

```
$ <same command>, stdin = "status\n"
...
system error, world model not loaded
```
(Matches `body-layer/CLAUDE.md`'s documented refusal-mode response exactly, verbatim.)

Both run from this worktree's own `body-layer/`, using the committed venv at
`/Users/sg/Code/DCS-petrobrain/body-layer/.venv` (no venv ships inside agent worktrees).

## Live acceptance — PENDING (live)

Per root `CLAUDE.md`'s auto-merge rule, live acceptance does not gate this merge. Tagged
`#needs-flight` on the `BL-15` entry (`body-layer/ROADMAP/BL-15.md`) — the prior Stage 1 sortie
(2026-10-20) did not exercise the first-poll store-resolution path this change adds, since
`--mission-understanding` was required at the time.

**Test card published**: `docs/acceptance/2026-10-28-theatre-from-dcs-card.md`
(https://claude.ai/artifact/81mVEm4waPeXuoWNan6gVK). Branch named on the card: `main`. Every
command on the card was run directly against this worktree (see above) — none is a confident
guess.

## Milestone-completion question

Does this change what the next milestone should be, or invalidate a downstream assumption? **No.**
BL-15 Stage 2 (the deferred Mission Interpreter briefing) still needs the mission file's
name/path from DCS, which this change does not touch, and `--mission-understanding` remains a
valid (now fully optional) mission-phase input whenever Stage 2 resumes.

## Verdict

**PASSED.**
