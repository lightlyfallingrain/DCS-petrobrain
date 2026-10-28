---
name: theatre-from-dcs-first-poll-reuses-guard
description: theatre-from-dcs (BL-15 follow-on) lets --world-model-dir run alone, adopting theatre from DCS mission-start on first poll -- reuses _maybe_switch_theatre's THEATRE_PROJECTIONS guard unchanged, approved clean
type: project
---

`feature/theatre-from-dcs` (2026-10-28, tip `137906bb651e0ab9c1cff6aa47bcc9f30ba565cd`) lets
body-layer start with `--world-model-dir` alone — no `--theatre`/`--world-model-db`, no
`--mission-understanding`. The theatre is adopted from the aircraft-layer's
`GET /mission_start/latest` on the *first* poll of the process via
`_check_for_new_mission`'s `last_mission_start_sequence is None` branch, which now calls the
existing `_maybe_switch_theatre` instead of doing nothing.

**Why this needed no new validation work**: the new call site reuses `_maybe_switch_theatre`
unchanged — the same function that already gates every mission-*restart* theatre switch with
`isinstance(event_theatre, str)` then `event_theatre in THEATRE_PROJECTIONS` (static dict,
`world-model/src/coordinates/projections.py`) *before* building `world_model_dir /
f"{theatre.lower()}-full.sqlite"` or opening it. This is the exact chokepoint
`project_mission_theatre_field_unsanitized_into_path_and_sqlite_uri.md` (the multi-theatre-
afghanistan finding: pathlib absolute/UNC override + sqlite URI `mode=ro` injection via an
unvalidated theatre string) forced into existence, and `project_bl15_mission_start_plan_review.md`/
`project_bl15_mission_start_deep_analysis.md` already verified it for the restart path. No new
guard was needed because no new path to `open_world_model` was created — only a new *caller* of
the existing, already-hardened one.

**New field, `ConsolePerceptionRunner.world_model_store: tuple[str, Path] | None`** — carries the
validated `(theatre, path)` pair so the REPL thread (separate `sqlite3.Connection`, thread-affine)
can follow a live theatre switch instead of a path bound once at startup. Checked every assignment
site: the only non-`None` producers are `_maybe_switch_theatre` (post-validation) and the CLI-
startup literal built from the already-`parser.error`-validated `--theatre`/`--world-model-db`
pair. The REPL thread's `open_world_model(store[1])` can never see an unvalidated value.

**Still-accepted pre-existing risk, unwidened by this feature**: `MissionStartReceiver`
(`aircraft-layer/src/collector/mission_start_receiver.py`) binds `127.0.0.1:7799` only — a forged
mission-start datagram requires code already running on the aircraft-layer box, not just LAN
access. That forged-event risk was already accepted (single-user/LAN-only scope) for the restart
path before this feature; this feature only lets the same already-accepted forgery also supply
the *initial* theatre, under the same `THEATRE_PROJECTIONS` bound.

**Verdict: APPROVED, no findings filed** — see `plans/theatre-from-dcs/security-deep-analysis.md`
for the full table. Nothing to add to the backlog.
