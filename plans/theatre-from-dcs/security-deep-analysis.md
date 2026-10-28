## Security Deep Analysis: theatre-from-dcs

Branch `feature/theatre-from-dcs`, tip `137906bb651e0ab9c1cff6aa47bcc9f30ba565cd` (one commit over
`main` `cedf604f`). Scope per root `CLAUDE.md`: single-user, LAN-only, single-player.

### Dependency Status

No dependency change.

### What changed

`body-layer/src/body.py`: `--world-model-dir` can now be given alone (no `--theatre`/
`--world-model-db`, no `--mission-understanding`). The theatre is then adopted from the aircraft-
layer's `GET /mission_start/latest` on the first poll of the process (`_check_for_new_mission`'s
`runner.last_mission_start_sequence is None` branch now calls `_maybe_switch_theatre` instead of
doing nothing), and on every subsequent mission (re)start as before. A new `ConsolePerceptionRunner.
world_model_store: tuple[str, Path] | None` field carries the `(theatre, store path)` pair so the
REPL thread (`_run_crew_text_repl`, now taking no `world_model_db`/`theatre` parameters at all)
can follow a store the poll thread switches live, instead of a path bound once at startup.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body.py:2567-2583` (`_check_for_new_mission`, first-poll branch) | Externally-sourced string (`event.get("theatre")`, from an untrusted-by-design UDP/HTTP channel) now also drives path/store resolution on the very first poll, not only on restart | Routes through the same `_maybe_switch_theatre` as every prior mission-(re)start call — no new validation path was written. `_maybe_switch_theatre` enforces `isinstance(event_theatre, str)`, then `event_theatre in THEATRE_PROJECTIONS` (a static, finite dict — `world-model/src/coordinates/projections.py`) **before** `world_model_dir / f"{event_theatre.lower()}-full.sqlite"` is built or opened. This is the exact ordering `security-plan-review.md` (multi-theatre-afghanistan) and the BL-15 Stage 1/3 deep analyses already required and verified — reused unchanged, not reimplemented. | None |
| `body.py:4066-4096` (`_run_crew_text_repl`) | REPL thread opens `sqlite3.Connection` from `store[1]` with no visible validation at the open site | `store` is read from `runner.world_model_store`, which is only ever written by (a) `_maybe_switch_theatre` after the membership/build/region checks above pass, (b) the CLI-startup branch in `_run_crew_text_poll_loop` using the already-`parser.error`-validated `--theatre`/`--world-model-db` pair, or (c) set to `None` by `_enter_refusal_mode`. No code path assigns it from a raw/unvalidated value. Confirmed by reading every assignment site in the diff and the surrounding file — there is exactly one producer of a non-`None` value (`_maybe_switch_theatre`) plus the one startup literal. The REPL thread cannot be reached with an unvalidated theatre/path. | None |
| `body.py:4798-4807` (`--world-model-dir` alone, `main()`) | New `if not args.world_model_dir.is_dir(): parser.error(...)` | Local CLI argument sanity check by the same user who starts the process; not a trust boundary. | None |
| `aircraft-layer/src/collector/mission_start_receiver.py` (pre-existing, not changed by this diff) | `MissionStartReceiver` binds `127.0.0.1:7799` only | Confirmed still loopback-only — the datagram carrying `theatre` cannot be forged by another LAN host, only by a process on the same box as aircraft-layer. This is the existing accepted risk from `project_bl15_mission_start_plan_review.md`/`project_bl15_mission_start_deep_analysis.md` (agent memory): "forged-datagram belief-wipe risk accepted under single-user/LAN-only scope." This feature does not widen that risk — it was already possible to force a theatre switch via a forged mission-start event before `--world-model-dir` could be given alone; now the same forged event can additionally supply the *initial* theatre on first poll, bounded by the same `THEATRE_PROJECTIONS` membership gate as every other call site. | None (pre-existing, not reachable-newly by this feature) |

### Mode-2-required checks performed

- Reasoned through every assignment/read of `runner.world_model_store` and `runner.theatre` in
  the diff and surrounding file — one validated producer, no bypass.
- Confirmed `THEATRE_PROJECTIONS` is a static dict (not built from external data), so membership
  in it cannot be satisfied by an attacker-chosen path-traversal or SQLite-URI-injection string —
  it must exactly equal one of a finite, code-defined set of theatre names.
- Searched agent memory (`memory-search.py theatre` / `mission`) for prior findings on this exact
  mechanism — found and cross-checked the multi-theatre-afghanistan path/sqlite-injection fix and
  the two prior BL-15 security passes; this diff's new call site reuses that fix's guard, not a
  reimplementation that could have dropped the ordering.
- Confirmed test coverage already exercises the security-relevant boundary conditions on the new
  first-poll call site specifically: `test_check_for_new_mission_first_poll_loads_the_store_dcs_
  names`, `test_check_for_new_mission_first_poll_stays_refused_without_a_theatre`,
  `test_check_for_new_mission_first_poll_corrects_a_wrong_initial_theatre`
  (`body-layer/tests/test_mission_start_reset.py`), plus the pre-existing
  `test_maybe_switch_theatre_enters_refusal_mode_for_unknown_theatre` which covers the shared
  validation function this new call site reuses.

### Verdict

APPROVED

No findings requiring a fix, a risk-matrix decision, or a backlog filing. The feature reuses an
already-reviewed validation chokepoint (`_maybe_switch_theatre`'s `THEATRE_PROJECTIONS` membership
check before any path/sqlite construction) at its one new call site rather than introducing a
second one, and the REPL thread's store-following change introduces no new way to reach
`open_world_model` with an unvalidated value. The pre-existing loopback-only binding on the
mission-start UDP channel and the already-accepted single-user/LAN-only risk model are unchanged
by this diff.
