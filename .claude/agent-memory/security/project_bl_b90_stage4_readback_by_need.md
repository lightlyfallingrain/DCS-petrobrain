---
name: project-bl-b90-stage4-readback-by-need
description: BL-B90 Stage 4 plan review (readback by need, option B) — the one real gap found was a missing isfinite/non-bool guard on the new one-shot read_args response, the same recurring unguarded-nonfinite-float category this codebase keeps hitting; everything else (shared 3-place bounds, server-minted read_id, broker slot lifecycle) was sound.
metadata:
  type: project
---

Plan reviewed: `plans/effector-sequences/plan.md` §"Stage 4 — readback by need (spec, revised
2026-10-24 — option B)", at `83e2835c`. New surface: `POST /query/read_args` (synchronous
`ArgReadBroker`, one-shot switch-position read at trigger fire / after a wait row),
`POST /command/watch_args` (fixed 3-arg continuous set, narrowed from the first spec's
union-of-sequence-args design), removal of `/cockpit_switch/latest`.

**The one required change**: `AircraftLayerClient.read_args(args) -> dict[str, float]` (S4.2) was
specified with no finiteness/non-bool/range guard before its values become `cursor.snapshot`,
compared directly in R12's self-check and D3's conditions. The plan already has exactly this guard
for the sibling continuous feed (`WatchedArgsState.from_dict`) — it just didn't carry it to the new
one-shot path. This is [[project_recurring_unguarded_nonfinite_float_before_conversion]]'s category
recurring a fourth time, this time at *plan* stage rather than code review — worth specifically
checking for on any future stage that adds a second reader/parser of a value class the first reader
already validates. **Why:** NaN-comparison semantics make a corrupted "unknown" value read as
"differs," which can trigger a write that shouldn't happen (bounded in impact here only because the
curated effector registry limits every write to a finite absolute-position set, per
`security-stage1-2.md`'s already-accepted posture).

**What was sound, worth not re-deriving next time on this same codebase:**
- The collector's TCP listener to Export.lua binds `127.0.0.1` and is `listen(1)`
  (`collector/server.py:130,200-201`) — confirmed directly, not assumed. Only the collector process
  itself can ever be Export.lua's peer, so a `read_id`/`watch_id` reply can never be spoofed by a
  LAN actor. `api/server.py` binds `0.0.0.0` (`DEFAULT_HOST`, line 273) — that split is where the
  real LAN boundary is, every time.
- A correlation id generated **server-side** (`secrets.token_hex(6)`, never taken from the LAN
  request body) eliminates request-id-spoofing analysis before it starts — worth checking first on
  any future broker-shaped design: who mints the id decides whether spoofing is even a question.
- `threading.Event.wait(timeout)` has exactly two exit paths (set, or timeout) and raises nothing —
  a slot-leak concern across an exception path doesn't apply unless something else in the critical
  section can raise while holding the slot. Don't over-rotate on this without checking what's
  actually inside the critical section.
