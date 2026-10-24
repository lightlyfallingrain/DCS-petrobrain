## Security Deep Analysis: BL-B90 Stage 4 — readback by need

Reviewed detached at `2b742cf3` (`feature/effector-sequences-stage4`). The worktree's own branch
(`worktree-agent-acd36b888e0e52215`, `1d02e5e1`) had diverged from this tip in both directions
(neither an ancestor of the other) — per the dispatch instructions, checked out the named tip
detached rather than fast-forwarding; tree was clean before and after.

Diff reviewed: `git diff c231efda..2b742cf3` (42 files, +5113/-1547 — collector `ArgReadBroker`,
`api/server.py`'s two new endpoints and removed `/cockpit_switch/latest`, `Export.lua`'s
`watch_args`/`read_args` ops, body-layer's `AircraftLayerClient.read_args`/`set_watch_args`,
`effector_registry.load_polled_config`, plus the superseding of `schema.cockpit_switch` by
`schema.watched_args`).

### Dependency Status

No dependency change. Stdlib only on both sides (`secrets`, `threading`, `re`, `math`,
`tomllib` — all already in use elsewhere in this codebase for the same purposes).

### Required change from plan review — verified fixed, both sides

`security-stage4-plan.md`'s one required change (finiteness/non-bool guard on the one-shot
`read_args` response, before it reaches `cursor.snapshot`) is implemented on **both** ends, not
just the one the plan named:

- **Collector side** (`aircraft-layer/src/collector/arg_read_broker.py:145`,
  `handle_reply_line`): validates `"values"` through `schema.watched_args.parse_arg_values` — the
  **same function** the continuous feed's `WatchedArgsState.from_dict` already used, now shared
  rather than duplicated (`aircraft-layer/src/schema/watched_args.py:61-98`). A malformed reply
  (NaN/Inf/bool/non-numeric/out-of-range/>64 keys) is dropped at `WARNING`; the waiting `read()`
  call times out to `ArgReadTimeout` rather than ever seeing a bad value.
- **Body-layer side** (`body-layer/src/aircraft_client.py:327-366`, `read_args`): re-validates the
  HTTP response independently — finite, non-bool, ≤64 keys, keys in `0..4095`, **and** (stricter
  than the plan asked) every returned key must be a member of the `args` actually requested,
  rejecting an unrequested/extra key rather than silently accepting it.
- **Mutation test present and specific**, `body-layer/tests/test_aircraft_client.py:371-391`
  (`test_read_args_rejects_a_malformed_response`, "security plan review, E9"): parametrized over
  `nan`, `inf`, `bool`, bad key, negative key, out-of-range key, and an unrequested key — each
  case asserts `AircraftLayerError`, i.e. the guard is tested to actually reject, not merely
  present. `test_read_args_returns_validated_values` covers the accept path.

This closes the one gap the plan review found. Nothing else required by that review needed a
second look, but I re-verified the design claims directly against this stage's actual code rather
than taking the plan's account on trust (per the project's "verify state, not the account of it"
habit):

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/collector/arg_read_broker.py:84-124` | Broker slot lifecycle (`ArgReadBroker.read`) | Confirmed: `MAX_OUTSTANDING_READS=8` cap raises `ArgReadBrokerBusy` before a 9th slot is ever created; `secrets.token_hex(6)` `read_id`, never attacker-influenced (minted server-side); `threading.Event.wait(ARG_READ_TIMEOUT_S=0.25)` has exactly the two exit paths the plan review already verified, both of which pop the slot. Dedicated tests for all three (`test_arg_read_broker.py`'s `TestArgReadBrokerTimeout`, `TestArgReadBrokerBusyLimit`, `TestArgReadBrokerSendFailure`) including the late-reply-after-timeout race. | None |
| `aircraft-layer/dcs-export/Export.lua:818-845` (`parse_arg_list`) | Inbound Lua-side bound, shared by `watch_args`/`read_args` | Whole-op reject on any bad token (non-digit, >4 chars, >`MAX_WATCHED_ARG_NUMBER`), dedup, reject whole op if >`MAX_WATCHED_ARGS` after dedup. `extract_json_id_field` separately bounds `watch_id`/`read_id` to `[%w_]{1,16}`. Matches `aircraft-layer/src/api/server.py`'s `_validate_arg_list`/`_WATCH_ID_RE` and `schema.watched_args.parse_arg_values` exactly; held equal by `tests/test_export_lua_constants_parity.py`. Three independent enforcement points for one bound, as designed. | None |
| `aircraft-layer/dcs-export/Export.lua:1676-1710` (`poll_command_socket`) | Per-frame read cap | `MAX_READS_PER_FRAME=4` via `admit_read`, checked before each `read_args` op is handled; excess ops dropped at `debug_log`, loop continues draining the socket (never blocks on a flood). `watch_args` installs deliberately left uncapped per-frame (O(1) state write, no device read) — reasoned, matches `cockpit_switch`'s existing posture, not an oversight. | None |
| `aircraft-layer/src/api/server.py` `_handle_command_watch_args`/`_handle_query_read_args` | New LAN-facing POST endpoints | Both reject non-JSON/non-object bodies, validate `watch_id`/`args` via shared helpers before touching `command_sender`/`arg_read_broker`, and return `503` when unconfigured. `read_args` additionally surfaces the broker's own `503`(busy)/`504`(timeout) rather than hanging the HTTP thread past `ARG_READ_TIMEOUT_S`. Unbounded `Content-Length` read is the same pre-existing shape as every other POST handler on this server — already tracked (`AC-B11`, which explicitly names these two new handlers) and accepted low/low under this project's LAN-only threat model. Not a new risk introduced by this stage. | None (tracked via `AC-B11`) |
| `body-layer/src/belief/effector_registry.py:385-592` (`load_polled_config`) | `polled.toml` TOML parsing | Local, user-authored config file, not a network input. `tomllib` (stdlib, no known RCE class — it is a data parser, not a code loader). Missing file → required-only, not an error; unreadable/unparsable file → D5 `RegistryError`, still required-only, never a partial/corrupt config. Per-entry validation (name regex, arg range, dup/clash detection) before admission; total set capped at `_MAX_POLLED_ARGS=64` with required args always kept and config overflow dropped from the end with a logged error — matches S4.4a exactly. | None |
| `aircraft-layer/src/collector/command_sender.py:244-305` (`send_watch_args`/`send_read_args`) | UDP payload construction via f-string interpolation of `watch_id` | `watch_id` is regex-validated (`^[A-Za-z0-9_]{1,16}$`) by `api/server.py` before this method is ever called, and `read_id` is `secrets.token_hex`-minted (hex only) by the broker itself — neither can contain a `"` or any JSON-breaking character, so the hand-rolled interpolation cannot produce a malformed/injected payload. Same pattern as the already-reviewed `send_cockpit_switch`. | None |
| `/cockpit_switch/latest` removal | Dead-code/dead-route check | Grepped the full tree: no route registration, no handler, remains only in docstrings/comments explicitly noting its removal and in a test (`test_cockpit_switch_write.py`) asserting it is gone. Clean removal, nothing still references it as live. | None |

### Passed to Reviewer

None — nothing player-experience-correctness-shaped surfaced during this pass that Reviewer's
`review-stage4.md` had not already covered.

### Findings ledger

No new finding requires an ID. The one required change from plan review is now implemented and
tested (closed, not filed as backlog — it was a plan-stage blocker, now resolved in code). The one
pre-existing low/low finding touched by this stage (unbounded `Content-Length` on the two new POST
handlers) was already filed as `AC-B11` before this stage's code existed, and `AC-B11`'s own text
already names both new handlers explicitly — no new backlog entry needed for it.

### Verdict

APPROVED
