## Security Deep Analysis: bl-b67-atgm-run (batch A — Stages 1-4 + Stage 0 probes)

Branch `feature/bl-b67-atgm-run`, tip `f2c8c25cd2932d794c9aa6d008e691df20a21e0c`. This worktree's
HEAD (`30a663b5`) was a strict ancestor of the tip and the tree was clean, so `git merge --ff-only`
was used — no cherry-pick, no divergence.

Scope per the dispatch: Stages 1-4 plus the Stage 0 probe files (`Export.probe-weapons.lua`,
`petrobrain-damage-events-probe-hook.lua`). **Stage 5 (the own-weapon `S_EVENT_SHOT` parser-side
bound on `schema/firing.py`) is explicitly out of this batch** — it is tracked by the plan
re-review's "Required Plan Changes" item 1 (`.claude/agent-memory/security/
project_bl_b67_own_weapon_wire_rereview.md`) and is not reachable from this diff: `perception/
own_weapons.py` does not exist yet (`belief/atgm_run.py`'s own docstring confirms it, "Stage 5 real
shape ... not built"), so nothing in this batch touches the firing-events wire at all.

### Dependency Status

No dependency change. `git diff main...f2c8c25c -- '*/pyproject.toml'` is empty; every new file
(`aircraft-layer/src/schema/payload.py`, `body-layer/src/belief/atgm_run.py`, the Lua additions) is
stdlib/no-import, matching both subprojects' existing stdlib-only declarations. Consistent with the
Mode 1 plan review's finding.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/api/server.py` (`_handle_payload_latest`, `_PAYLOAD_LATEST_PATH`) | new `GET /payload/latest` endpoint | Read-only, no request body, no new POST handler added — `AC-B11`'s unbounded-`Content-Length` category (5 POST handlers) is unchanged by this batch, confirming the plan review's correction. Discloses ammo-station counts/names, same sensitivity class as `/world_objects/latest`/`/firing/latest` already exposed on this LAN-bound (`0.0.0.0` by design) API. | None |
| `aircraft-layer/src/schema/payload.py` (`PayloadStation.from_dict`, `PayloadSample.from_dict`) | JSON parsing of a DCS-derived wire line | Every field type-checked (`isinstance`, explicit bool-exclusion on numeric fields) before use; malformed input raises `PayloadParseError`, which `collector/server.py`'s `_handle_line` catches and logs at WARNING, dropping the line rather than crashing the poll loop (confirmed: `if "stations" in data: try: ... except PayloadParseError: logger.warning(...); return`). `name` is passed through unvalidated against a known-name set — documented, deliberate (module docstring), and inert: it reaches only `GET /payload/latest`'s JSON response and `atgm_run.family_of`'s lowercase-substring match against a fixed 4-entry hint table, never a file path, a shell, or unescaped text concatenation. | None |
| `aircraft-layer/dcs-export/Export.lua` (`push_payload_state`) | new per-frame Lua push, reads `LoGetPayloadInfo()`/`LoGetNameByType()` | Every DCS call `pcall`-guarded; a failed/non-table read is a silent no-send, not a malformed line. `name` is run through the existing `json_escape_string` helper before being embedded in the hand-rolled JSON line — correct escaping for the wire format, matching every other string field this script already sends. Function is defined below `safe_call`/`json_escape_string`/`client` (confirmed by reading file order), so the no-hoisting class of bug (`push_ptt_state`, `aircraft-layer/CLAUDE.md`) does not apply here — also confirmed mechanically: `luac5.1 -l -p Export.lua \| grep GETGLOBAL` lists only genuine DCS APIs (`LoGetPayloadInfo`, `LoGetNameByType`, …) and Lua stdlib, no own-helper name. | None |
| `aircraft-layer/src/collector/server.py`/`cache.py`/`__main__.py` (`PayloadCache`, `"stations"` line dispatch) | new wire-key dispatch branch | Collector stays bound to `127.0.0.1` (`DEFAULT_HOST`, unchanged); `PayloadCache` is "latest of one," same bounded shape as every sibling cache (`PttCache`, `SightServoCache`) — no growth, no new socket. | None |
| `aircraft-layer/dcs-export/Export.probe-weapons.lua` (Stage 0 extension: knob sweep/park/reset state machine, first-seen key dump) | cockpit writes via `GetDevice(7):performClickableAction(cmd, value)`; disposable recon probe | Writes are all to fixed `(device, cmd)` pairs (`DEV_I9K113=7`/`CMD_KNOB=3038`, `CMD_RAD_RESET=3029`) driven by a hardcoded, autonomous state machine — no network or player input selects the cmd/device/value, so this is not a new generic-write surface, just a probe exercising the same cockpit-write primitive BL-B66 already reviewed and the user already overrode the allow-list requirement for. `clickable()`/`read_arg()` are `pcall`-wrapped. File stays disposable-recon posture per this project's standing "`io`/`lfs` probe access authorized for recon only" rule; its own header still says "delete this file once the question is settled." `luac5.1 -p` clean; `GETGLOBAL` scan clean (only DCS APIs + stdlib). | None |
| `aircraft-layer/dcs-export/petrobrain-damage-events-probe-hook.lua` (Stage 0 extension: `S_EVENT_SHOT`/`S_EVENT_HIT` weapon introspection, `WEAPON_EXIST_POLL_CODE` via `net.dostring_in`) | DCS mission-scripting bridge, pre-existing file extended | `net.dostring_in("scripting", WEAPON_EXIST_POLL_CODE)` sends a **fixed compile-time string literal**, never built from external/player input — the expected, already-reviewed shape of this bridge (per `aircraft-layer/CLAUDE.md`'s own documented posture and this role's prior `project_bl_b66_...`/plan-review findings on the same mechanism). Extracted `EVENT_REGISTER_CODE`'s new branch and `WEAPON_EXIST_POLL_CODE` separately with `luac5.1 -l -p` per the no-hoisting procedure (outer-file `luac -p` cannot see inside the string literals): both clean — the only non-stdlib/non-DCS-API globals are `PB_PROBE_KEPT_WEAPON`/`PB_PROBE_EVENT_QUEUE`/`PB_PROBE_EVENT_NAMES`/`PB_PROBE_HANDLER_REGISTERED`, all deliberately-global cross-dostring-call state persistence (same pattern `PB_ACTIVE_FIRING_UNITS` already uses, per this file's own comment), not an accidental undeclared-local bug. | None |
| `body-layer/src/belief/atgm_run.py` (`family_of`) | string handling of a DCS-derived type/store name | Lowercases and substring-matches against a fixed 4-entry dict (`_FAMILY_NAME_HINTS`); returns only `"shturm"`/`"ataka"`/`None`, confirmed by grep — no other return path exists. No regex, no eval, no file/path use of the string. | None |
| `body-layer/src/belief/speech.py` (`render_atgm_launch`) | speech rendering from `family: str \| None` | `family` is always one of the two literals above or `None` by construction (`_render_launch_line`'s only producer is `family_of`); the `_ATGM_FAMILY_DISPLAY.get(family, family.capitalize())` fallback branch is defensive and not reachable with a raw unbounded DCS string in this batch's wiring. No LLM/brain-layer call anywhere in the diff; confirmed by grep (no `brain_client`/`BrainClient` reference added by this batch's files) — no prompt-injection surface. | None |
| `body-layer/src/aircraft_client.py` (`get_payload_latest`) | ordinary typed HTTP GET client | Mirrors every other `get_*_latest` method's shape (type-checks the JSON result, raises `AircraftLayerError` on the wrong shape). No new surface. | None |
| Security-grep sweep (full run, both subprojects + all 57 Lua files) | pattern categories 1-9 | Zero hits in `eval`/`exec`/`pickle.loads`/`yaml.load`/`loadstring`/`dofile` anywhere. `net.dostring_in` hits are all the already-expected `aircraft-layer/dcs-export/` bridge files. `subprocess`/`os.system`/`shell=True` hits are all pre-existing `audio-adapter` process-spawn code, untouched by this batch. `Content-Length`/`rfile.read`/`recv(` hits are the pre-existing, already-`AC-B11`-filed shape on `aircraft-layer/src/api/server.py`'s five POST handlers and `collector/server.py`'s fixed `4096`-byte `recv` — none of this batch's files add a new instance. | None (all pre-existing, none newly reachable from this batch) |

### Verdict

**APPROVED**

### Required Fixes (if any)

None for this batch. The one carried-forward item — `schema/firing.py`'s own-weapon `<type>` field
needing an independent parser-side length/charset bound — belongs to Stage 5, is not implemented in
this batch's diff (`perception/own_weapons.py` does not exist yet), and is already tracked in the
plan's own re-review (`plans/bl-b67-atgm-run/security-plan-review.md`, "Required Plan Changes" item
1) rather than needing a fresh backlog ID here. **Do not implement Stage 5 without that parser
bound landing in the same commit** — flag for whichever role runs this batch's Security deep
analysis next.

### Passed to Reviewer (no verdict given)

- `Percept.aim_unit_direction` / single-unit aim replacing the cluster centroid on the sight-goal
  path, and the `belief/` grep fence keeping own-weapon object ids (once Stage 5 lands) out of
  `Contact`/`PositionBelief` — no-omniscience/architecture correctness, not computer security.
- Whether the knob-step ↔ `Stations` array index correspondence the Stage 0 probe's auto-advance
  logic assumes (Q3) actually holds, and whether `S_EVENT_SHOT` reliably carries `event.weapon` for
  the 9M114/9M120 (Q6) — both are the plan's own open empirical questions, player-experience/
  correctness in nature.
- Everything the Mode 1 plan review and its re-review already passed to Reviewer without a verdict
  (unchanged by this batch's actual diff).
