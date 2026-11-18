### Review Summary

Reviewed BL-16 mode 1 M1+M2 perf/security change-request round, `4defba5e..307d6a81` (branch
`feature/bl16-raw-axes`). This round addresses three items from the batch's own perf/security
reports:

1. **Perf finding 1** (`perf-m1-m2.md`): `check_envelope`/`read_measured` each independently read
   `LoGetSelfData`/`LoGetIndicatedAirSpeed`/`LoGetADIPitchBankYaw` every active frame.
2. **Security Finding A** (`security-m1-m2.md`): `fc_last_cmd_seq` desyncs permanently against a
   fresh `wire_seq` across a body-layer restart (or a LAN probe), silently dropping every future
   `take`/`release`/`goal`/`arm`.
3. **Security Finding B** (`security-m1-m2.md`): `arm_lease_s` shared the generic 60 s sanity
   ceiling, letting any accepted message widen U10's 3 s escape-hatch margin by 20x.

**Worktree note**: this worktree's HEAD (`59192cfa`, an unrelated merge on
`worktree-agent-afa7fd3b0d275fd8b`) was not an ancestor of the task's stated tip `307d6a81` (nor
the reverse — separate histories). Tree was clean, so per the task's own fallback: `git branch
review-cr 307d6a81 && git checkout review-cr`. Confirmed `HEAD == 307d6a81` before reading
anything.

#### 1. Perf finding 1 — verified fixed, behaviour-preserving

`run_active_frame` now calls `read_measured()` first and passes the result into
`check_envelope(t, measured)`, which makes no `LoGet*` call of its own — the duplication is
eliminated entirely (not merely reduced to one redundant call, as the mitigation text allowed for;
`read_measured` already made the one `LoGetSelfData` call `check_envelope` needed). The
fail-soft-vs-release distinction is preserved correctly: `read_measured` now also returns
`self_data_ok`/`ias_valid`/`bank_valid`, captured **before** the fail-soft zeroing of
`ias_mps`/`bank_rad`, and `check_envelope` checks those flags rather than the (possibly-zeroed)
values directly — so a missing/NaN reading still releases with its original `"dead"`/`"nan"`
cause rather than being masked into a slow `"envelope"` release once a zeroed IAS crosses the
low-speed margin. `bank_valid` is correctly still needed even though NaN propagates through
`math.deg` unchanged, to distinguish a genuine NaN from `LoGetADIPitchBankYaw` returning nothing
at all (`type(bank_rad) ~= "number"`), which NaN-propagation alone cannot tell apart from a valid
zero. All 23 pre-existing `test_flight_control_lua.py` cases pass unchanged. Confirmed by reading
the diff directly, not by trusting the implementation note.

#### 2. Security Finding A — verified fixed for the reconciliation case; one residual noted (not blocking)

Chose option (b) (body-layer reconciles `wire_seq` up to Lua's echoed `fc_last_cmd_seq`) over
option (a) (bound how far a single message may advance the Lua-side counter). I agree with this
choice and with declining to reuse `ai_pilot_wheel.lua`'s `goal_seq ~= ai_pilot_goal.goal_seq`
("different", not "greater") shape: that check is a one-shot trigger dedup for a single field,
layered on top of an already-monotonic staleness gate — not a replacement for one. Switching
`flight_control`'s own gate from "greater than" to "different from" would accept a genuinely
stale, reordered duplicate as new, which is exactly the failure mode `test_a_stale_seq_is_ignored`
exists to prevent. Confirmed `handle_flight_control_command`'s `seq <= fc_last_cmd_seq` gate is
unchanged; only the echo and the body-layer-side reconciliation are new.

Reconciliation (`body._apply_flight_control`, `if state.lua_last_cmd_seq is not None and
state.lua_last_cmd_seq > state.wire_seq: ... wire_seq=state.lua_last_cmd_seq`) runs
unconditionally, first, every poll — before any send. Verified by mutation: deleting this block
makes `test_a_body_layer_restart_reconciles_wire_seq_above_lua_last_cmd_seq` fail for exactly the
stated reason (`seq == 1`, not `48`); restored and reran clean. It only ever raises `wire_seq`,
confirmed by `test_reconciliation_never_lowers_wire_seq_below_its_own_history` (seeds `wire_seq=10,
lua_last_cmd_seq=3`, asserts the send still lands at `11`).

**First poll after a body-layer restart, status not yet received**: `advance_flight_control_state`
runs immediately before `_apply_flight_control` every poll (`body.py:5070,5080`), so in the
ordinary restart-while-mode-1-active case, the very first poll's `GET /flight_control/latest`
already carries `fc_last_cmd_seq` (Lua keeps running through a body-layer restart), and
reconciliation happens before any send that same poll. The one narrow gap: if that first status
fetch returns `None` (sample not yet cached, or the fetch itself fails) on the exact poll a `take`
is also dispatched, `lua_last_cmd_seq` stays `None`, reconciliation is skipped, and the send goes
out at `wire_seq=1`, which Lua silently drops as stale. This is not silent to the player, though:
`FlightControlState.phase` is body-layer's own field (never derived from `lua_mode`) and defaults
to `"PILOT"` on a fresh process, so the dropped send is a `take`, which already has an ack-timeout
path (`decide_flight_control`, "Ack timeout while TAKING" → "Unable, not ready.", phase back to
`PILOT`) — the player gets a clear, spoken failure and can simply retry, by which point the mirror
has caught up. I did not find a `goal` sent in this same race window reachable from a fresh
restart (state starts at `PILOT`, not `ACTIVE`, so no bare unacked `goal` send is possible before a
take has succeeded). **Not a required fix** — flagging only because it was asked for directly;
the degradation is a single retry, not a silent or permanent failure.

**Residual not addressed by this round, and not addressable within its scope**: once
`fc_last_cmd_seq` reaches the HTTP bound's own max (`2**31-1`), reconciliation now *actively*
raises `wire_seq` to that same max (previously, a restarted process's own small `wire_seq` would
just keep being silently dropped at Lua forever without the HTTP layer ever objecting). The next
legitimate send after reconciliation is `wire_seq+1 = 2**31`, which `_FLIGHT_CONTROL_SEQ_MAX`
rejects at the aircraft-layer HTTP boundary itself — `write_flight_control` raises
`AircraftLayerError`, caught and logged as a warning, "continuing," with no further progress on
this channel for the rest of the DCS session. The failure mode is now an explicit logged error
instead of a silent accept-then-ignore, which is marginally better, but the "channel is dead for
the rest of the session" outcome Finding A's own report named is not reopened by reconciliation —
it is structurally unfixable by *this* option; only option (a) (bounding how far a single message
may jump `fc_last_cmd_seq`) would have prevented reaching the max in the first place, and that was
reasoned against for a stated, legitimate reason (a genuine restart after a long sortie could
need a large legitimate jump). **Not a required fix** — `security-m1-m2.md` already rated this
low-probability (single-user LAN, accepted baseline), and the physical park gesture remains the
independent escape hatch regardless. Worth a one-line backlog note if the user wants it tracked;
not blocking this round.

#### 3. Security Finding B — fixed, but the rendered `defaults.toml` is missing the new warning (required fix)

The numeric fix is correct and verified consistent across all three places that check
`arm_lease_s`/`ARM_LEASE_S`: `Export.lua`'s `FC_LIMIT_BOUNDS.arm_lease_s` = `{0.0, 10.0}`,
`aircraft-layer/src/api/server.py`'s `_FLIGHT_CONTROL_LIMITS_BOUNDS["arm_lease_s"]` = `(0.0,
10.0)`, and body-layer's `tuning.py`-backed `ARM_LEASE_S` `hi` = `10.0`. Confirmed by reading all
three, not just grepping for the number.

**However**: the new `#:` comment on `ARM_LEASE_S` adds its explanation (why `hi` is narrower,
the cross-layer coupling, "a user override above either would be silently rejected
whole-message") as a **second sentence**, after the pre-existing first-sentence paragraph (which
ends at "...keeps the *armed* escape open)."). `generate_defaults.py`'s own sentence-splitter
(`_SENTENCE_SPLIT`, splits on a non-digit-adjacent period) emits only the first sentence. I
regenerated and read the rendered `config/defaults.toml` directly — it reads:

```
# U10's lease: Lua takes at an unpark only if body-layer has re-sent `arm` within this many
# seconds -- about three missed ~1 Hz polls, closing the park-then-unpark escape route a
# same-frame unpark take would otherwise remove from a dead Petrobrain (Decision 2 stands for
# an *active* mode 1; this is what keeps the *armed* escape open).
# status: judgement | range: 0.5 .. 10.0
```

The new sentence — the entire explanation of *why* `hi` dropped from 30.0 to 10.0 and the
three-way coupling it must stay in step with — never reaches the file. This is exactly the defect
class this project's own review checklist names (`.claude/agents/reviewer.md`, "read the rendered
file, not the source comment"): the implementer's own check ("confirmed it now reads `range: 0.5
.. 10.0`") verified the *number* changed but not that the *new explanatory text* rendered — the
same gap three prior `X-T26` defects lived in. **Required fix**: merge the new explanation into
the first sentence (or otherwise ensure it survives the split) so a future reader of
`defaults.toml` alone — not the source — sees why this one constant's ceiling is tighter than
every sibling limit's, and that it is coupled to two other hard-coded values outside the tuning
system.

#### Cross-key coupling

Agree with the implementation note: `ARM_LEASE_S` is now coupled, outside `tuning.py`'s own
coupling-check mechanism, to two hard-coded Lua/HTTP ceilings that `generate_defaults.py` cannot
see. No automated check ties the three together; the implementer flagged this as backlog-worthy
rather than fixing it, which I agree is reasonable scope for this round — but it should carry an
ID rather than stay a prose note (see Required Fixes).

#### Comment pruning

Reviewed both touched docstrings (`check_envelope`, `read_measured`) per "Prune the comment you
are standing next to." Nothing durable was deleted — both additions are pure additions, and both
existing "why" paragraphs remained accurate after the edit and were kept verbatim. No boundary
case moved into a test silently; the new behaviour (fail-soft flags) is covered by the unchanged
23 pre-existing `check_envelope`/`read_measured` tests plus the perf round's own reasoning in
`implementation.md`. No finding here.

#### Scope fit

Three fixes, each matching its own report's finding exactly, plus the one extra body-layer
`tuning.py` `hi` lowering Finding B's fix required for consistency. No scope drift. Responsibility
stayed in the right modules: the seq gate and its echo stay in `Export.lua`/the Lua-facing schema;
reconciliation policy lives in `body._apply_flight_control`, beside the other wire-send decisions
it already owns; `ARM_LEASE_S`'s tightened ceiling is a `tuning.py` declaration like every other
behaviour-affecting constant, not a bare literal.

#### Checks (all independently reproduced, this review)

- **aircraft-layer**: `ruff format --check` — 85 files already formatted; `ruff check` — all
  checks passed; `cd aircraft-layer && .venv/bin/mypy src` — success, 28 files; `luac5.1 -p` on
  `flight_control.lua` and `Export.lua` — both pass; full `pytest tests` — 953 passed (matches
  implementation.md's count); `fast-tests.sh aircraft-layer` (targeted on the three changed
  files) — 350 passed.
- **body-layer**: `ruff format --check` — 227 files already formatted; `ruff check` — all checks
  passed; `cd body-layer && .venv/bin/mypy src` — success, 92 files; `fast-tests.sh body-layer`
  (targeted on `belief/flight_control.py`, `body.py`) — smoke + 2454 passed, 6 deselected, 4
  xfailed (pre-existing). Both subprojects' `.venv` did not exist in this review worktree and were
  created fresh (`pip install -e .` for each, plus `pytest`/`mypy`/`ruff`); body-layer additionally
  needed `lupa` from its own `pip install -e .` (declared dependency, `BL-17`) before the smoke
  collect would pass — the implementer's own checks list did not call this out explicitly but its
  own `pip install -e .` step would have picked it up the same way.
- **Mutation**: reverted the `wire_seq` reconciliation block in `body.py` and reran
  `test_a_body_layer_restart_reconciles_wire_seq_above_lua_last_cmd_seq` — goes red for the exact
  stated reason (`seq == 1`, not `48`); restored, confirmed clean (`git diff --stat` empty on
  `body.py` after restore).

### Required Fixes

- **`ARM_LEASE_S`'s new cross-layer-coupling warning does not survive the `defaults.toml`
  generator's first-sentence split** — the rendered file still shows only the old "U10's lease..."
  paragraph; the new "why `hi` is narrower, must match two other hard-coded bounds" explanation is
  silently dropped. Fold it into the first sentence (or restructure the comment) so it reaches the
  file a future reader actually checks, per this project's own "the generator emits only the first
  sentence" caveat — exactly the defect class that caveat exists to prevent.

### Optional Refinements

- Mint a backlog ID (`AC-B<n>` or a body-layer-side equivalent) for the three-way `arm_lease_s`
  ceiling duplication (`Export.lua`, `aircraft-layer/src/api/server.py`, body-layer `tuning.py`)
  with no mechanical check tying them together — the implementation note already identifies this
  precisely; it just needs an ID so it does not live only as prose in `implementation.md` (optional
  — low probability of silent drift given all three are now commented with cross-references to
  each other, but `test_export_lua_constants_parity.py`'s existing pattern for a different constant
  pair shows this project already has the mechanism to extend).
- Consider noting, in `security-m1-m2.md` or a short follow-up line in `implementation.md`, that
  the max-seq (`2**31-1`) jam Finding A's report named is not reopened by the reconciliation fix —
  reconciliation changes the failure's *shape* (a logged `AircraftLayerError` instead of a silent
  accept-and-ignore) but not its *outcome* (channel dead for the rest of the session). Already
  rated low-probability and already has an independent escape hatch; this is purely so a future
  reader of the implementation note doesn't assume the reconciliation closed Finding A's full
  scope, when it closes only the restart-desync sub-case the implementer explicitly prioritized.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — all three fixes read against their source findings, all affected files diffed and
read in full, checks independently reproduced (not re-trusted from implementation.md), one new
test mutation-verified, and the rendered `defaults.toml` read directly per this role's own
standing instruction.
