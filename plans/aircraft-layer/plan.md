### Goal

Build the first working slice of the Aircraft Layer — a live, LAN-reachable, read-only telemetry pipeline that streams Mi-24P kinematic state (position, attitude, heading, speed, altitude) out of a running DCS mission on the Windows box to a standard-format, cached, query-able API, as the first concrete step of `docs/concept/division-or-responsibility.md`'s aircraft layer (switches, contacts, and commanding are explicitly out of scope for this plan — see "Follow-on Milestones").

**Architect note on model depth:** this plan involves a new cross-machine live-process protocol and (in follow-on milestones) a bidirectional command surface reachable over LAN — comparable in risk to the coordinate-system/spatial-schema class of decision this role is instructed to flag. I'm proceeding at default (sonnet) depth because the investigator's findings resolved the load-bearing unknowns cleanly and the MVP scope below is narrow and reversible, but if the follow-on command-channel milestone (Stage 4 in "Follow-on Milestones") turns out to need deeper protocol/security design, I'd recommend re-invoking Architect with an opus override for that milestone specifically.

### Prior Investigation

`aircraft-layer/research/2026-09-06-aircraft-layer-live-runtime-io.md` (investigator, 2026-09-06) established the feasible architecture. Key resolved facts this plan relies on:

- `Saved Games\DCS\Scripts\Export.lua` is a separate, unsanitized, per-install (not per-mission) Lua environment that ships with LuaSocket and unrestricted `io`/`lfs` by default — **no `MissionScripting.lua` edit needed**, unlike the World Model Builder's elevation probes.
- `LoGetSelfData`/`LoGetADIPitchBankYaw`/altitude/airspeed functions give ownship kinematic state, **not gated by anti-cheat/labels settings**, callable every sim frame or throttled via `LuaExportActivityNextEvent`.
- Community precedent (Tacview real-time export, DCS-BIOS) proves "Export.lua as a live LAN-reachable server/publisher" works in production at real-time rates.
- Switch/indicator state (DCS-BIOS) and sensor contacts (no real API, needs `LoGetWorldObjects` + external LOS filtering) are **separate, harder problems**, deliberately deferred out of this plan.
- Direct flight-control-axis injection has no known API — stays deferred, consistent with `division-or-responsibility.md`'s own deferral.

Unresolved items from that investigation that don't block this plan (Mi-24P DCS-BIOS coverage, `LoGetWorldObjects` visibility semantics, safe export polling rate, Export.lua behavior while paused/briefing) are listed under Risks below and will be resolved by follow-on investigation when their milestone comes up.

### Architectural Decisions

1. **Aircraft layer is a new sibling subproject, `aircraft-layer/`**, parallel to `world-model/`, not a submodule of it. It shares the repo's provenance/CLAUDE.md conventions but has its own stack notes (this is a live-process/networked service, not an offline batch pipeline — different testing shape).
2. **Three-hop pipeline, not two:** DCS process → `Export.lua` (in-process, Windows) → local collector process (Windows, same box) → LAN API (Windows→Mac). Export.lua is kept deliberately dumb: it only *pushes* its own ownship state to a local collector over loopback; it never listens for or answers arbitrary requests from the Mac. Rationale:
   - Keeps the code running inside DCS's sim thread minimal — reduces risk of a slow/misbehaving LAN client stalling frame time (Export.lua callbacks run on DCS's own thread).
   - The stated output requirements (standard-format sanitized data, most-recent-data cache, delta-since-last-query) are much easier to implement correctly in Python than hand-rolled Lua, and the collector process is where they naturally live.
   - Only the trusted local collector can inject data into Export.lua's socket; the LAN-facing surface is a conventional, independently testable Python service, not an extension of DCS's own script sandbox.
   - Matches existing community precedent (DCS-BIOS is Export.lua-as-publisher + a separate protocol consumers read; it doesn't try to be a full application server itself).
3. **World Model query interface belongs to the body layer, not the aircraft layer.** `division-or-responsibility.md` flags this as open ("world model query, data from world model (or maybe body layer, consider)"). Decision: aircraft layer's contract stays "DCS I/O only" per its own one-line definition in that doc ("aircraft = DCS I/O + API for exposing DCS data and possible commands to DCS"). World Model queries are static reference data, not DCS I/O, and the body layer's own worked examples in that doc already show it fusing aircraft position with world-model lookups (e.g. "2 o'clock, 5km → DCS coordinate → query world model"). Keeping the aircraft layer narrowly scoped keeps it independently testable against a live DCS instance without a World Model dependency, and avoids the same coupling existing in two layers.
4. **Wire protocols: plain newline-delimited JSON everywhere, no new dependency**, consistent with the World Model Builder's stdlib-first pattern (`sqlite3`, `array`, no GDAL). Export.lua→collector: a minimal hand-rolled Lua JSON encoder (the schema is flat, ~10 fields) over a local TCP push connection. Collector→Mac: a stdlib `http.server`-based JSON polling API (`GET /telemetry/latest`, `GET /telemetry/since/{timestamp}`). A push/WebSocket transport is a possible later refinement, not MVP — polling is simpler to debug and sufficient for crew-cognition-rate consumption (not a flight-control loop).
5. **Every telemetry sample carries both DCS model-time and wall-clock receipt timestamp.** This satisfies the project's "preserve timestamps" invariant and is required for the delta-since-last-query API and for later staleness/confidence reasoning in Petrobrain's episodic memory.

### Affected Modules / Files

- `aircraft-layer/` (new) — new sibling subproject to `world-model/`.
  - `aircraft-layer/dcs-export/Export.lua` — canonical, version-controlled Windows Export.lua script (kinematic state only). Deployed by copying to `Saved Games\DCS\Scripts\Export.lua` on the Windows box — same "canonical script in git, deployed copy is gitignored/untracked" pattern as `world-model/tools/wsl/` → `win-mac-sync/run-wsl/`.
  - `aircraft-layer/src/collector/` — local TCP listener receiving the Export.lua feed, maintains most-recent-state cache + a short ring buffer for delta-since-last-query.
  - `aircraft-layer/src/schema/` — the standard telemetry data shape (dataclass/typed dict): position (DCS x/y/z), pitch/bank/yaw, heading (state which — true; magnetic deferred per `division-or-responsibility.md`'s own "need to use either true or magnetic consistently, defer decision"), speed (IAS/TAS), altitude (MSL/AGL/radar where available), DCS model-time, wall-clock receipt time.
  - `aircraft-layer/src/api/` — the Mac-facing LAN API server (stdlib `http.server`, JSON).
  - `aircraft-layer/tests/` — unit tests for schema parsing/validation and the delta-cache logic against fixture JSON (no live DCS needed for these); a separate manual/live test procedure for the actual Export.lua↔collector↔API path (documented, not automated — mirrors how M4's elevation probe needed a live mission).
  - `aircraft-layer/WORKFLOW.md` — new cross-machine doc: how to deploy Export.lua, run the collector on the Windows box, what port/firewall rule is needed, how the Mac reaches it. Explicitly *not* the same as `world-model/WORKFLOW.md`'s Dropbox-symlink manual-copy flow — that workflow is for asynchronous offline file transfer and is confirmed unsuitable for live telemetry (investigator finding #7 / "Process boundary").
  - `aircraft-layer/CLAUDE.md` — subproject conventions (stack, commands, testing shape), written once Stage 1 proves the pipeline out, mirroring `world-model/CLAUDE.md`'s role.
- `CLAUDE.md` (root) — "Module Responsibilities" reference section needs a new `aircraft-layer/` bullet once this lands; not edited by this plan, flagged for the Implementer/DoD step.
- `aircraft-layer/research/2026-09-06-aircraft-layer-live-runtime-io.md` — already written by investigator, no change needed, referenced above.

### Invariant Check

- DCS authoritative, never overridden: satisfied — this pipeline only reads ownship state, never fabricates it.
- Code owns facts, models interpret: satisfied — the collector and API layer are deterministic Python, no model involved at this stage.
- Read-only against DCS install: the Export.lua deployment writes into the user's own `Saved Games\DCS\Scripts\Export.lua`, which is user-writable game-config, not the DCS installation tree — consistent with the existing project convention that `MissionScripting.lua` edits (also user/local-install config, not DCS's own install-tree logic) were acceptable for the same reason.
- Provenance/timestamps preserved: satisfied by decision 5 above.
- `world-model/data/` gitignore boundary: unaffected, this plan doesn't touch `world-model/`. `aircraft-layer/` will need its own `.gitignore` entries for anything analogous (none expected at MVP — no persistent store, just an in-memory cache).

### Implementation Plan

1. **Scaffold `aircraft-layer/`** — directory structure per "Affected Modules" above, `pyproject.toml` matching `world-model/`'s tooling (ruff, mypy --strict, pytest) unless the user wants a shared root config instead (flagged below).
2. **Minimal working version — one-way kinematic push:**
   - Write `Export.lua` calling `LoGetSelfData`/`LoGetADIPitchBankYaw`/altitude/airspeed on `LuaExportAfterNextFrame`, throttled via `LuaExportActivityNextEvent` to a conservative starting rate (proposed: 5 Hz — well under frame rate, easy to verify has no measurable frame-time cost, can be raised later once measured).
   - Serialize to a small hand-rolled JSON line, push over a local TCP socket to the collector.
   - Write the collector: accept the local connection, parse each line into the schema type, hold as most-recent-state.
   - **This stage has no Mac-facing API yet** — verify end-to-end via a local script on the Windows box reading the collector's in-memory state (or a debug stdout dump) before adding the network hop to the Mac.
3. **Validate correctness — live DCS test:** run an actual Mi-24P mission (training mission is fine) with the deployed Export.lua, confirm the collector receives real-time-rate updates with correct-looking values (compare a few instrument readings visually against the cockpit — e.g. does reported altitude/heading match the ADI/altimeter). This is the live-mission validation step analogous to M4/M5's real-fixture testing — no meaningful automated test without a running DCS instance, document the manual procedure in `aircraft-layer/WORKFLOW.md`.
4. **Add the Mac-facing API:** implement `GET /telemetry/latest` and `GET /telemetry/since/{timestamp}` in the collector process, open the necessary firewall port on the Windows box, confirm reachability from the Mac over LAN with a plain `curl`. Document the exact port/firewall steps in `aircraft-layer/WORKFLOW.md`.
5. **Validate performance:** measure DCS frame-time impact at the chosen export rate (compare frame time with Export.lua active/inactive), and confirm the delta-since-last-query endpoint behaves correctly across a few consecutive polls including the "nothing changed" case. If frame-time impact is negligible at 5 Hz, consider whether crew-cognition consumers actually need a higher rate before raising it — don't raise the rate speculatively.
6. **Refine:** write `aircraft-layer/CLAUDE.md`, fixture-based unit tests for schema/cache logic, and the root `CLAUDE.md` Module Responsibilities addition.

### Follow-on Milestones (not this plan — listed for roadmap visibility only)

Mirroring how `world-model/ROADMAP.md` sequenced M0→M9 rather than planning the whole pipeline at once:

- **Switch/indicator state** — needs a hands-on Windows-box check of Mi-24P's DCS-BIOS module completeness (`control-reference.html` with Mi-24P loaded, or reading the module's `.lua` source) before deciding "adopt DCS-BIOS" vs. "hand-roll arg-export in the same Export.lua." Needs its own Architect pass once that check is done.
- **Command channel (switch actuation)** — the first genuinely bidirectional, LAN-reachable command surface in this project. **Flag explicitly per the current-phase Security exemption's own carve-out: this is a bigger untrusted-input-adjacent surface than the World Model Builder ever had (a live command channel into a running DCS session, even if LAN-only/single-user), and should get a Security plan-review pass before implementation, not the blanket skip.** Route commands through cockpit-control actuation (DCS-BIOS-style "move this arg") per the investigator's finding — no raw flight-control-axis injection API exists.
- **Sensor pointing commands** — needs further investigation into how Mi-24P's optical/thermal sight is represented in the cockpit-arg model; not investigated yet.
- **Contacts/detection approximation** — `LoGetWorldObjects` ground truth + an external LOS/range/terrain-masking filter. The filter logic is body-layer work per decision 3 above; the aircraft layer's job here is only to expose the raw `LoGetWorldObjects` read, not to do any filtering itself.
- **Direct flight-control-axis (pitch/bank/yaw) injection** — stays deferred; no known API, matches the project's own existing deferral.
- **Weapon systems** — stays deferred per `division-or-responsibility.md`.

### Risks & Unknowns

- **LAN reachability/firewall** between the collector (Windows) and whatever box the body process runs on (Windows or Mac — see topology note below) for a new live TCP/HTTP port is unverified — the existing Dropbox-symlink workflow deliberately avoids needing this, so this plan introduces a genuinely new piece of network plumbing.
- **Export.lua sampling-rate ceiling is undocumented** (investigator finding) — Stage 5's frame-time measurement is the real answer, not a documented spec.
- **Export.lua behavior during pause/briefing/mission-editor screens is unverified** — relevant to the project's "model-swap only at briefing/on-ground" compute note for later milestones, not blocking for this one but worth resolving before the brain layer relies on knowing "we're at briefing."
- **`LoGetWorldObjects` visibility/anti-cheat filtering semantics unresolved** — doesn't block this plan (kinematics only), but blocks the contacts follow-on milestone; the one ED forum thread that would likely answer it 403'd investigator's fetch — ask the user to paste it when that milestone starts.
- **New subproject tooling duplication** — `aircraft-layer/pyproject.toml` mirroring `world-model/`'s risks drifting out of sync with it over time; acceptable for now (subprojects are already established as independently configured), flagged so it isn't silently assumed identical forever.

### Decisions Requiring User Input

- ~~Windows-box Python availability~~ — resolved 2026-09-06: **native Windows Python**, not WSL2. Collector runs directly on Windows alongside DCS.
- **Export rate starting point**: this plan proposes 5 Hz as a conservative default pending frame-time measurement — confirm that's an acceptable starting point rather than a specific rate the user already has in mind.
- **New subproject config**: confirm `aircraft-layer/` should get its own independent `pyproject.toml`/lint/type/test config (mirroring `world-model/`) rather than a shared root config — this plan assumes independence, matching the existing per-subproject pattern, but wasn't explicitly asked.

### Compute Topology (updated 2026-09-06)

User clarified the deployment topology is looser than the aircraft-layer↔brain split implied earlier: the **aircraft-layer process must run on Windows** (it needs the DCS install) and exposes its API over LAN. The **body process may run on either Windows or Mac** — it's a LAN client of the aircraft-layer API either way, so this plan's Mac-facing API design (stdlib HTTP/JSON) already supports both without change. The **brain process may also run on either box**, but the *local LLM itself* (Ollama) can only run on the Mac (no local-LLM runtime on Windows) — a cloud-model brain could run anywhere, a local-model brain must run on/reach the Mac. This doesn't change this plan's design (aircraft-layer's API is host-agnostic on the client side), but supersedes the earlier fixed "Mac=brain, Windows=DCS/aircraft" mental model — worth carrying into body-layer planning.
