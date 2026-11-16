## Security Deep Analysis: AC-B12 (Export.lua module split, AC-B13 folded in)

Scope: commits `6919c86d`, `0812e98f`, `c304dcc5` against `fab32110` (the pre-split `Export.lua`).
Batch covers AC-B12 (Stages 1-7) and AC-B13 (the AI-pilot-wheel stop-hook fix), the only stages
executed in this batch. Reviewer APPROVED (round 2), `plans/ac-b12-export-modules/review.md`.

### Dependency Status

No new dependency. Both new module files that call `require` (`core.lua`, `commands.lua`) require
`socket.core` — the same LuaSocket library the pre-split file already required; `require`'s own
module-name cache (`package.loaded`) means this is the same already-loaded table, not a second
load. No `pyproject.toml`/`requirements*.txt` changed in this diff.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/dcs-export/Export.lua:208-244` (`MOD_DIR`, `load_module`) | Dynamic `dofile` path construction | `MOD_DIR` is `lfs.writedir() .. "Scripts\\Petrobrain\\"`, a fixed base with no external input. `load_module(name)` is called 7 times (`Export.lua:246-262`) with 7 string **literals** (`"core"`, `"telemetry"`, `"petrovich"`, `"sight"`, `"ai_pilot_wheel"`, `"effectors"`, `"ptt_ics"`, `"commands"`) baked into the loader's own source — nothing from the network, the wire, or the collector ever reaches this call. A missing/erroring module file is caught by `pcall`, logged (by hand, before `core`/`debug_log` exists, straight to the log file — `Export.lua:230-239`), and the loader proceeds with that module as `nil`; every call site is `call_if`-guarded (`Export.lua:267-272`) or, inside `commands.lua`, guarded per dispatch-table entry (see next row). A *replaced* module file (malicious content substituted on disk) would execute via `dofile` exactly as before the split — but writing into `Saved Games\DCS\Scripts\Petrobrain\` already requires local filesystem write access equivalent to code-exec on the box, which is not a privilege this feature grants or that a LAN attacker (the stated threat model) can reach without a separate compromise. The split turns one file-to-protect into eight under the same folder and the same trust boundary — a larger surface *area* at identical trust *level*, not a new exploitable path. | None — holds. Informational only. |
| `aircraft-layer/dcs-export/Petrobrain/core.lua:338-352`, and every `_G[name] = result` in `Export.lua:242` | Bare globals published into the Export Lua environment | `core.lua` publishes 12 names as bare globals (`debug_log`, `debug_dump`, `fmt_num_or_null`, `safe_call`, `encode_json_line`, `json_escape_string`, `encode_scalar`, `extract_json_string_field`, `extract_json_number_field`, `extract_json_id_field`, `WHEEL_MENU_BUTTON`, `WHEEL_CENTER_BUTTON`), plus `client` (`core.lua:121`) and the 8 module identity tables (`core`/`telemetry`/`petrovich`/`sight`/`ai_pilot_wheel`/`effectors`/`ptt_ics`/`commands`, via the loader's `_G[name] = result`). Checked against every documented DCS Export API name (`Lo*`, `GetDevice`, `list_indication`, `LuaExport*`, `net`, `log`, `lfs`, `io`, `os`, `socket`) — no collision; this project's own names are distinct in every case. The real exposure is to a **second** Export-side script the user might separately `dofile` into the same Lua state (DCS loads exactly one `Scripts\Export.lua`, so this requires the user to have manually chained another add-on in); such a script already runs with the same privilege this one has (full `io`/`lfs`/network access in the Export state) — reading or clobbering a generic name like `client` gains it nothing it could not already do by writing `_G` directly. Not reachable by a LAN attacker or a malicious dependency: the Export Lua state has no network listener of its own (the command socket below is loopback-only) and nothing here parses or executes LAN-received bytes as Lua. | None required for the stated threat model; see Risk Communication below for the one genuine (self-inflicted) scenario, presented to the user rather than filed unilaterally. |
| `aircraft-layer/dcs-export/Petrobrain/commands.lua:75-127` | Command dispatch table built from cross-module globals | Matches the reviewer's required fix exactly: each handler entry is only added when its owning module (`petrovich`/`effectors`/`sight`) is non-`nil` (`commands.lua:76-86`), so one module failing to load no longer takes every other op down with it (the review's one finding, fixed in `c304dcc5`). `handlers[op]` on an unrecognized or absent op is `nil`, logged and ignored (`commands.lua:107-109`) — no unknown op reaches a handler. A missing module simply contributes no entries; it cannot widen what a *present* op does, since each handler is still the same function reference the owning module always exported. `read_args` additionally goes through its own per-frame cap (`effectors.admit_read`) before the handler runs. Verified against DCS's bytecode-level `local`-as-`GETGLOBAL` hazard (`test_dcs_export_lua_local_order.py`, widened to `dcs-export/**/*.lua`) and against the live counterfactual the reviewer already ran (pre-fix table construction crashes with `attempt to index global 'effectors' (a nil value)` under `luajit`) — independently re-confirmed here by running `luac5.1 -p` clean on every `Petrobrain/*.lua` file and `Export.lua` itself. | None — holds. |
| `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua:687-708` (`M.on_stop`, AC-B13) | Explicit failure path / state cleanup on stop | Release is unconditional on any open press: `if ai_wheel_pending_cmd ~= nil then ... performClickableAction(ai_wheel_pending_cmd, 0) end` — the `0` (release) value is hardcoded in the call, never a variable, so this code path cannot press anything; it can only release whatever button name is already recorded in `ai_wheel_pending_cmd` (itself only ever set to `AI_WHEEL_UP`/`AI_WHEEL_DOWN`/`WHEEL_CENTER_BUTTON` by this module's own logic, never from external input). Clears every takeover-sequence field (`stage`, `t`, `handover_altitude_m`, `menu_open`, …) in the same call, so a stale in-progress correction cannot resume on the next park. Confirmed this is additive — the module never had an `on_stop` before (BL-16 Batch A's one-shot nudge needed none); there is no prior behaviour to regress. | None — holds. |
| `aircraft-layer/dcs-export/Petrobrain/effectors.lua:249-273` (`handle_cockpit_switch_command`) | Deliberately unrestricted cockpit-control write (E-P6-adjacent, BL-B66) | Breadth unchanged by this split: still `device`/`cmd`/`value` extracted via `extract_json_number_field` (which already rejects non-finite/NaN/overflow values at `core.lua:235-246`, so the `BL-B104`-class NaN/Infinity-at-wire-boundary hazard does not apply here — this parser is hand-rolled regex + `tonumber`, not Python's `json.loads`, and already has its own finite check), then integer-floor-checked, then a `safe_call`-guarded `performClickableAction`. Confirmed no change in validation strictness or in which device/cmd pairs are reachable — this is the accepted, documented exception (user direction 2026-10-21) and the split moved its extraction into the handler body without touching its logic. | None — holds (pre-existing, accepted exception). |
| `aircraft-layer/dcs-export/Export.lua` and all 8 `Petrobrain/*.lua` files; grep for `AI_WHEEL_RIGHT`/`WHEEL_RIGHT`/`3002` | E-P6 invariant (`HDG LOS`/short-right never pressed) | `grep -rc AI_WHEEL_RIGHT` across every production `dcs-export/*.lua` and `dcs-export/Petrobrain/*.lua` file returns `0` everywhere. `3002` appears only in disposable probe scripts (`Export.probe-*.lua`, never deployed) and in an unrelated 9K113 device-arg comment. `ai_pilot_wheel.lua` declares only `AI_WHEEL_UP`/`AI_WHEEL_DOWN` (3004/3005) and explicitly comments that Left/Right (3003/3002) are not declared. No generic `press(direction, duration)` entry point exists anywhere in the split. | None — holds. |
| `aircraft-layer/dcs-export/Export.lua:206` / `aircraft-layer/src/collector/server.py` `EXPECTED_EXPORT_VERSION` | Deployment-staleness version check | `EXPORT_SCRIPT_VERSION = "2026-11-16b"` in `Export.lua`, `EXPECTED_EXPORT_VERSION = "2026-11-16b"` in `server.py` — both bumped in this diff, confirmed byte-identical. `tests/test_export_lua_constants_parity.py` already enforces the shared numeric bounds (`MAX_WATCHED_ARGS`/`MAX_WATCHED_ARG_NUMBER`) stay equal between the two sides; the version string itself has no automated parity test (it is a human-read mismatch warning, by design — the collector "compares the two and warns loudly on a mismatch", per `Export.lua`'s own header). The U1 rationale (this string is now the *whole* deployment-staleness check for the multi-file deploy) is sound and the bump is present. | None — holds. |

**Syntax/mechanical re-verification performed directly** (not taken on the Reviewer's word alone):
`luac5.1 -p` run against `Export.lua` and all 8 `Petrobrain/*.lua` files in this worktree — all pass
clean. `grep -rc AI_WHEEL_RIGHT`/`WHEEL_RIGHT`/`3002` run directly against the full `dcs-export/`
tree (production files and probes) rather than trusting the plan's or Reviewer's own account of the
result. Full `pytest` run was not performed in this worktree (no `.venv` provisioned here); Reviewer's
own record (`.claude/agent-memory/reviewer/project_ac_b12_export_lua_module_split_round2_approved.md`)
already reports the suite green on this same commit range, including a live `luajit`-run
counterfactual proving the dispatch-guard fix's own test is genuine rather than vacuous.

### Risk Communication

**Finding:** The generic helper names now published as bare Export-environment globals
(`client`, `safe_call`, `debug_log`, `fmt_num_or_null`, `encode_scalar`, etc. — `core.lua:338-352`,
`Export.lua:242`) were previously local to a single chunk and invisible outside it; they are now
live names in `_G` for the life of the Export Lua state.
**Location:** `aircraft-layer/dcs-export/Petrobrain/core.lua:338-352`, `Export.lua:242`.
**Probability:** low — requires the user to manually `dofile` a second, independent Export-side
add-on into the same Lua state (DCS itself loads exactly one `Scripts\Export.lua`); nothing in this
project's own deploy does that.
**Impact:** low — a colliding name could silently break either script's state (a stability/compat
bug), but grants no privilege a script already running in that same Lua state would not already
have (full `io`/`lfs`/socket access). Not reachable by a LAN attacker or a malicious dependency —
the Export Lua state has no network listener that executes received bytes.
**Recommended action:** no code change now; worth a one-line note in `aircraft-layer/CLAUDE.md` or
`WORKFLOW.md` if/when a second Export-chained add-on is ever installed alongside this one.

Options:
  (A) Ignore — document acceptance of this risk
  (B) Add to todo.md — fix in a future session (e.g. prefix these globals, `PB_client`/`PB_safe_call`)
  (C) Fix now — rename before merge
  (D) Stop — do not proceed until this is resolved

### Passed to Reviewer

None — no player-experience/correctness observation surfaced during this pass that Reviewer had not
already covered (the dispatch-guard fix, the ordering preservation, and the pruned-comment claim were
all Reviewer's own findings, re-confirmed here, not new ones).

### Verdict

APPROVED

### Closing — finding disposition

One finding this pass (the bare-global name-collision risk above): **not filed as a backlog item**,
intentionally — it is low/low, self-inflicted only (requires the user's own future action to become
reachable at all), and is presented above as a Risk Communication item for the user to decide among
(A)/(B)/(C)/(D) rather than filed unilaterally. If the user picks (B), it should be minted as an
`AC-B<n>` backlog item at that point, not before.
