### Performance Review

Scope: BL-B90 Stages 1-2 (one batch), `feature/effector-sequences`, diff `8f2dc3f3..f452db83`
(`body-layer`, `aircraft-layer`). Target: per-poll runtime path, default 1 Hz crew poll loop
(`_run_crew_text_poll_loop` in `body-layer/src/logger.py`) — no hard real-time budget in this
phase (Petrobrain Runtime has not started), but no redundant per-poll I/O and no per-request
allocation on the hot path either, per root `CLAUDE.md`.

### Findings

#### Unconditional per-poll `GET /spu8/state` call

- **Location:** `body-layer/src/logger.py` ~3574 (`_run_crew_text_poll_loop`): `spu8_latest =
  aircraft_client.get_spu8_state_latest()` runs every poll, unconditionally, to compute
  `intercom_open` and feed `CrewConsole.drain_config_error`. `drain_config_error` itself
  (`crew_console.py:1583`) early-returns on `not self.config_error_pending` — but the HTTP GET
  has already fired by the time that check runs.
- **Risk:** `config_error_pending` is `True` only when a sequence/registry file failed to load at
  startup — the rare case. In the overwhelmingly common case (no bad file), this adds one
  synchronous blocking HTTP round trip to the aircraft-layer collector, every poll, for the entire
  length of every sortie, to serve a flag that is already known `False` and will stay `False`
  until the next mission (re)start. At the default 1 Hz poll rate this is a small but wholly
  avoidable addition over `get_cockpit_switch_state_latest` (which the poll already needs, for
  the engine's own readback) — exactly the "redundant queries" / "work at the wrong frequency"
  shape root `CLAUDE.md` calls out. `_get_json` carries a timeout (`timeout_s`), so this cannot
  stall the loop indefinitely, which is why this is a mitigation case and not a blocker.
- **Action:** NOW (trivial one-line fix, real and cheap to remove).
- **Mitigation:** Guard the call behind the flag that actually needs it:

  ```python
  intercom_open = False
  if crew_console.config_error_pending:
      spu8_latest = aircraft_client.get_spu8_state_latest()
      intercom_open = (
          spu8_latest is not None and spu8_latest.get("gate_open") is True
      )
  crew_console.drain_config_error(runner.last_t_sim, intercom_open=intercom_open)
  ```

  Once `drain_config_error` clears the flag (one-shot), the GET never fires again for that
  process's lifetime — matching the cost of the feature it serves (a one-time startup-error
  announcement) rather than the cost of every poll forever.

#### `EffectorRunState` bookkeeping per poll

- **Location:** `belief/effector_engine.py` `advance()` — copies `state.runs`/`.pending`/
  `.commanded_values` into plain dicts each call, iterates `state.fire_order` (bounded by the
  5-member `EffectorTrigger` enum).
- **Risk:** None credible. All three mappings are bounded by the fixed trigger count (≤5 entries)
  for the lifetime of this cut; no per-request allocation scales with anything unbounded.
- **Action:** MONITOR (only relevant if a future milestone adds many more triggers or per-aircraft
  trigger sets at once — not this cut's shape).

#### `_half_gap` recomputed per row evaluation

- **Location:** `belief/effector_engine.py` `_half_gap`/`_matches`, called once per row reached
  per poll (explicit condition check and/or the R12 implicit self-check).
- **Risk:** None credible at this scale — every shipped effector has 2-3 named values, and at
  most one row per running trigger is evaluated this way per poll. `sorted(set(...))` over 2-3
  floats is immaterial next to the HTTP round trip the same poll already pays for readback.
- **Action:** MONITOR only if `EffectorDef.values` ever grows to many entries (not the case for
  any cockpit switch).

#### `cockpit_switch` readback via the per-frame `args` map (R7, Stage 2 as built)

- **Location:** `aircraft-layer/src/schema/cockpit_switch.py` `to_api_dict`'s `"args"` key;
  `effector_engine._raw_value_for` looks the needed arg up by string key from the dict `GET
  /cockpit_switch/latest` returns.
- **Risk:** None for this batch. `to_api_dict` runs per HTTP request (once per body-layer poll,
  ~1 Hz), not per DCS frame — the six-entry dict it builds is trivial. The underlying BL-B80
  per-frame push into the collector's cache (storing the `CockpitSwitchState` object, not the
  dict) is pre-existing behaviour, unchanged by this diff.
- **Note for the planned Stage 4 move** (switch readback off the per-frame push onto a low-rate/
  on-demand query): this batch's design is favourable, not a complication. The engine reads
  readback only through the `Mapping[str, float] | None` args map keyed by arg number
  (`_raw_value_for`) — it has no idea whether that map came from a per-frame push or an on-demand
  low-rate query. Swapping the source in Stage 4 should not require touching `effector_engine.py`
  at all, only what `logger.py` passes in as `effector_readback`. Nothing in this batch adds a
  second place that would need the same change.

#### Startup-only loaders

- **Location:** `belief.effector_registry.load_registry`/`load_registries_by_aircraft`,
  `belief.effector_sequences.load_sequences` — called once in `logger.py`'s startup sequence
  (~line 3073-3107), before `_run_crew_text_poll_loop` starts, not inside the per-poll block.
- **Risk:** None. Confirmed startup-only; no re-parsing of TOML/markdown on any hot path.
- **Action:** none needed — confirmed as designed, no finding.

#### Stage 0 generator (`generate_effector_registry.py`)

- **Location:** `body-layer/tools/generate_effector_registry.py`.
- **Risk:** None. Offline dev tool, run by hand on the Windows DCS machine against one aircraft's
  cockpit script files (hundreds of elements, not theatre-scale data) — not part of the
  whole-theatre build pipeline (Milestones 5/7) and not a runtime path. Out of scope for this
  review's hot-path focus; no action.

### Verdict

APPROVED — MONITOR, with one change request: guard the per-poll `GET /spu8/state` call behind
`config_error_pending` so the added HTTP round trip only fires in the rare case it actually serves,
not on every poll of every sortie.
