## Security Plan Review: bl-b67-atgm-run

Reviewed: `plans/bl-b67-atgm-run/plan.md`, `explore-notes.md`,
`aircraft-layer/research/2026-10-29-bl-b67-loadout-and-atgm-object-recon.md`, at tip
`858625061c9ee6cdac95b3f69152b8c320e6b872`. Scope per root `CLAUDE.md`/`.claude/agents/security.md`:
computer/network security only (code execution, access to the computer, what a LAN port scanner
reaches, prompt injection, dependencies/secrets) — single-user, LAN-only threat model, one
proportionate pass. Player-experience correctness (no-omniscience boundary, callout wording,
guidance accuracy) is Reviewer's, noted below without a verdict.

### Dependencies Checked

No new dependency. The plan has no dependency statement at all (`grep` over the plan file for
dependency-shaped language returns nothing) — checked this isn't a silent omission by reading
"Affected Modules" directly: every new file is Python stdlib (`src/schema/payload.py`,
`src/schema/fire_button.py`, `src/perception/own_weapons.py`, `src/belief/atgm_run.py`) or Lua
additions to the already-committed `Export.lua`/`Export.probe-weapons.lua`. Both subprojects
already declare stdlib-only. Nothing to escalate.

### Design Findings

**No new write-path category.** `select_station` and `radiation_reset` both resolve, through
`effector_engine.write_effector`/`advance`, to the existing `client.write_cockpit_switch(device,
cmd, value)` → `POST /command/cockpit_switch` — the one deliberate generic-write exception
already reviewed and user-overridden on BL-B66
(`.claude/agent-memory/security/project_cockpit_write_vocabulary_invariant.md`,
`project_bl_b66_9k113_effectors_deep_analysis.md`). The plan adds no new generic write primitive
and no new POST endpoint to aircraft-layer. Every value this plan writes is one of a finite named
set from `effectors.toml` (`missile_station`: `off=0.0, s1=0.1…s8=0.8`; `radiation_reset`:
`pressed=1.0, released=0.0`) resolved by name through `EffectorDef.values`, not a float threaded
in from network input — same bounded-registry shape as every other effector. `select_station(step)`
computes which *name* to write (next loaded station, an int 1–8) but still indexes into the fixed
table; it cannot cause an arbitrary `performClickableAction(device, cmd, value)` call.

**Correction to a standing memory item.** `.claude/agent-memory/security/` (`AC-B11`'s own text,
`aircraft-layer/ROADMAP/AC-B11.md`) assumed BL-B67 would add a sixth unbounded-`Content-Length`
POST handler to `TelemetryAPIServer` ("eventually six, once BL-B67 lands"). This plan does not —
the two new aircraft-layer endpoints are both `GET /payload/latest` / `GET /fire_button/latest`
(read-only, no request body), and the write side reuses the existing `/command/cockpit_switch`
handler already counted in AC-B11's five. AC-B11 updated with this correction (see memory below);
no new finding filed, because there is nothing new to file — the handler count stays five until
some other feature actually adds a sixth.

**New Export.lua feeds are read-only pushes, both stated pcall-guarded**, following the
already-established per-frame-closure pattern (`project_export_lua_per_frame_closures_are_established_pattern`)
and the PTT edge-detection shape (`push_ptt_state`) for the fire-button feed. Both sit in-process in
`Export.lua`, defined (per the plan's own note) below the locals they close over — the one
mechanical check this codebase has for the exact bug class that previously made `push_ptt_state`
silently publish nothing (`GETGLOBAL` bytecode scan, `aircraft-layer/CLAUDE.md`). Plan explicitly
schedules this check for Stage 4 ("Lua `GETGLOBAL` bytecode check… on the edited `Export.lua`").
Not a finding — the plan already carries the mitigation that matters here.

**Export.lua→collector channel stays loopback-only**, consistent with the existing telemetry/
world-objects channels (confirmed pattern, not re-derived: `collector/server.py` binds `127.0.0.1`
per `project_bl_b90_stage4_readback_by_need.md`). The new payload/fire-button feed does not change
who can be Export.lua's peer.

**Two new unauthenticated read-only GET endpoints extend an already-accepted exposure shape, not a
new one.** `aircraft-layer`'s API binds `0.0.0.0` (LAN-reachable by design, stated in
`aircraft-layer/CLAUDE.md`'s "What this is"); a LAN actor reaching `/payload/latest` or
`/fire_button/latest` learns ammo-station counts and a momentary button's last-press time — no
credential, no write capability, nothing beyond what `/world_objects/latest` or
`/petrovich_indication/latest` already expose about this aircraft. Consistent with this project's
stated single-user/LAN-only threat model; not escalated.

**Own-weapon object ids never cross the perception/belief boundary** (`perception/own_weapons.py`
holds ids, emits only `OwnWeaponEvents`; grep fence planned on `belief/` imports). This is a
no-omniscience/architecture invariant, not a computer-security boundary — noted under "Passed to
Reviewer" below, no verdict given here.

**No LLM involved and no prompt-injection surface.** `atgm_run.decide` is a pure deterministic
function over typed state; `belief/speech.py`'s new render functions build fixed-template strings
(`"<Family>, <N> seconds"`, `N` a rounded number) from a 3-valued `missile_family` enum and
arithmetic — not from arbitrary DCS object-name text interpolated unbounded. No brain-layer/LLM
call appears anywhere in this plan's affected-modules list.

**Probe script (Stage 0) extends an existing, already-reviewed pattern.** `Export.probe-weapons.lua`
(already committed, prior finding `C_8`) is disposable recon code per this project's standing
posture (`.claude/agent-memory`: DCS probe `io`/`lfs` access authorized for recon probes only,
never pipeline code). Grepped the existing file for `loadstring|dostring|os\.|require(` — the only
hit is `io.open` against the script's own fixed `LOG_PATH`, the same shape every other probe in
this directory uses. The proposed extensions (dump `pairs(obj)` keys, add `LoGetPayloadInfo()`)
add no new primitive.

### Verdict

APPROVED

### Required Fixes

None.

### Passed to Reviewer (no verdict given)

- Own-weapon object ids staying out of `belief/` (no-omniscience invariant) is enforced by a grep
  fence the plan proposes in Stage 5 — correctness of that fence, and of `aim_unit_direction`'s
  single-unit aim replacing the cluster centroid, is Reviewer's to verify against the diff.
- The deferred OBSERV-refused-by-cannon response and the "missile" singular not being in
  `WEAPON_WORDS` are both explicitly flagged in the plan's own Risks section as player-experience
  gaps, not security gaps.
