---
name: bl15-mission-start-plan-review
description: BL-15 Stage 1 plan review (mission-start signal, belief reset, theatre switching) -- approved; theatre->path/sqlite risk correctly reuses the multi-theatre-afghanistan fix, forged-datagram belief-wipe risk accepted under single-user/LAN-only scope
type: project
---

Plan reviewed: `plans/bl15-mission-start/plan.md` (new Hook `onSimulationStart` → aircraft-layer
collector → body-layer poll signal; per-mission belief/mission-memory reset; Stage 3 live theatre
switching of the world-model store). Verdict: APPROVED, no required fixes before Implementer.
Full writeup: `plans/bl15-mission-start/security-plan-review.md`.

**Why this one needed the theatre/path memory lookup first**: this plan reintroduces exactly the
`theatre` string → `pathlib` join → `sqlite3` URI pattern already demonstrated exploitable in
`multi-theatre-afghanistan` (see [[mission-theatre-field-unsanitized-into-path-and-sqlite-uri]]),
just from a new source (a Hook/mission-scripting read instead of a `.miz`-derived
mission-understanding artifact) — equally untrusted either way. The plan explicitly commits to
reusing the already-fixed mitigation (`THEATRE_PROJECTIONS` membership check, strictly *before*
building the path or calling `open_world_model`) rather than inventing a second validation path.
**`open_world_model` (`body-layer/src/perception/geometry.py:56-65`) is still the unsafe
f-string-interpolated SQLite URI** as of 2026-10-19 — it is safe only because every caller
validates `theatre` membership first. If a future caller of `open_world_model` is ever added that
skips that check, this reopens immediately; worth a direct grep sweep for new callers whenever that
function's call sites change.

**New risk this plan does introduce, not carried from the earlier finding**: a forged/locally
spoofed UDP datagram on the new mission-start loopback port triggers a full belief/mission-memory
wipe (not just a command action, unlike the F10/audio/text channels this project already accepts as
locally-spoofable). Rated low-probability/self-healing and accepted under this project's
single-player/LAN-only scope — same local-attacker standard already applied to every other loopback
channel, not a new trust boundary. Presented to the user via the standard risk-communication
format rather than silently approved; not expected to need a different answer unless the project's
scope ever widens to multiplayer/shared-machine (root `CLAUDE.md`'s scope statement would need to
change first, which is itself a flagged condition elsewhere in this project's docs).

**Carried forward to Mode 2 (deep analysis, after Reviewer) for this feature**: (1) confirm Stage 3's
implemented runtime theatre-switch path keeps the membership-check-before-path-build order, since a
runtime code path is a second place the same ordering bug could be reintroduced independently of
`main()`'s already-correct one; (2) confirm the new `schema/mission_start.py` module actually
rejects malformed/wrongly-typed payloads (mirroring `F10CommandEvent.from_dict`/
`F10CommandParseError`), not just "same shape" by the plan's own description.
