## Security Deep Analysis: emitter-visibility — Stage B (AC-B8 / BL-B73)

Reviewed at tip `8303d3bdcbfd10d7f689abb5955c8a578c28de87` on `feature/emitter-events`
(fast-forwarded cleanly from this worktree's stale base `5015a66`, no divergence). Four commits
vs `main`: `f02ec43` implement, `031abd3` review (NEEDS REVISION), `1e6c697` fix, `8303d3b`
re-review APPROVED. This is the Stage B pass; Stage A's own pass
(`plans/emitter-visibility/security.md`, APPROVED) is not re-litigated here except where Stage B
touches what it covered.

### Dependency Status

No dependency change. `aircraft-layer/CLAUDE.md` confirms stdlib-only, and the new files
(`src/schema/firing.py`, `src/collector/firing_receiver.py`) import nothing beyond
`dataclasses`/`typing`/`json`/`logging`/`socket`/`time`. No new entry in `pyproject.toml` on
either touched subproject.

### The new transport surface

**`FiringEventsReceiver` binds `127.0.0.1` only** (`DEFAULT_HOST`, `firing_receiver.py:71`), the
same loopback-only posture as every other Hook→collector channel in this module (`unit_velocity`,
`line_of_sight`, `f10_command_receiver`). It is not reachable over the LAN at all — only a process
on the same Windows box can send to it. The LAN-reachable half is `GET /firing/latest` on the
existing `TelemetryAPIServer`, which carries the same no-auth posture every other read endpoint on
that server already has (an accepted, pre-existing project posture for a single-user LAN, not
something this stage changes or widens).

**Wire parsing (`schema/firing.py`) is strict and fails closed.** `ALLOWED_KINDS` is a fixed
allow-list; an unrecognized kind, a non-`0`/`1` ownship flag, a non-numeric `t`/`x`/`z`, or a
malformed envelope shape all raise `FiringParseError`, caught at `_handle_datagram` and logged at
`debug` — the whole datagram is dropped, nothing partial is ingested. No `eval`/`exec`, no
deserialization beyond `json.loads` on a dict-shaped envelope plus the hand-rolled delimited
`_parse_entry`. Confirmed by `test_firing_schema.py`'s twelve cases (unrecognized kind, empty
initiator, malformed ownship flag, malformed `x`, malformed envelope shape, non-numeric
count/model-time) and `test_firing_receiver.py`'s three datagram-level cases (malformed payload,
non-JSON, well-formed).

**One real but pre-existing-shape gap, not introduced by this stage: a literal `;` or `:` inside
a DCS unit name can corrupt entry splitting.** `entries_str.split(";")` happens in
`FiringEventBatch.from_wire` *before* `_parse_entry` ever sees an entry, so a mission-editor unit
name containing a literal semicolon would split mid-entry and very likely raise
`FiringParseError` on a garbled fragment — which drops the **entire batch** for that poll (the
whole envelope fails `from_wire`, caught once at `_handle_datagram`), not just the one bad event.
The colon case is explicitly defended (`_parse_entry`'s docstring comment on splitting from both
ends to reserve the initiator field for free text) but semicolon is not and cannot be with a
flat-delimited format. **Impact is availability (a lost poll's worth of events), not an
omniscience or injection vulnerability** — the data still originates from the trusted, loopback-
only Hook script, and the failure mode is fail-closed (dropped), not fail-open (fabricated or
misattributed data admitted). This is the same wire-format shape `unit_velocity.py`'s and
`line_of_sight.py`'s own `unit_name` joins already carry (free-text mission-editor names over a
delimited wire), so it is not a defect specific to this stage — noting it here because this is the
first time a semicolon-delimited *list* of entries (rather than one value per line) carries that
same free-text field.

**Finding — Probability: low** (requires an unusual mission-editor unit name) — **Impact: low**
(a dropped poll of firing events, self-correcting the next poll since the state the batch would
have produced is re-derivable from the next `S_EVENT_SHOOTING_START`/`_END` the same unit
generates, or from the watchdog already covering a silently-missing `END`). Not a blocker.

Options:
  (A) Ignore — document acceptance of risk
  (B) Add to todo.md — fix in a future session (e.g. percent-encode or reject names containing
      `;`/`:` Hook-side, or switch the wire shape to length-prefixed fields)
  (C) Fix now
  (D) Stop — do not proceed until resolved

Recommended: (A), consistent with the same accepted shape elsewhere in this codebase and the
project's single-user/LAN-only scoping.

### Resource bounds — `EmitterTracker._active` and the raised watchdog

**The map is bounded by real unit cardinality and the watchdog, not by an explicit cap — and that
is adequate here, not a gap.** `_active` is a plain `dict[str, ActiveEmitter]` keyed by
`initiator`; nothing caps its size directly. Growth is bounded by:

- **The trust boundary.** The only sender is the loopback-only Hook script running inside the same
  DCS process as the mission itself — reaching this receiver with a flood of synthetic
  `S_EVENT_SHOOTING_START` entries naming thousands of distinct fake initiators requires a process
  already running arbitrary code on the same Windows box, at which point the firing-events channel
  is not the interesting attack surface. This is the same trust boundary every other Hook→collector
  receiver in this module already accepts (none of them cap entry counts either); Stage B does not
  widen it.
- **Real mission cardinality.** In the actual threat model (a live DCS mission, not a hostile local
  process), the number of distinct unit names that can ever appear in a batch is bounded by the
  mission's own unit count — tens to low hundreds, not an adversarially-chosen number.
- **The watchdog**, raised `10.0 → 180.0` (the Stage B fix). An entry with no further event at all
  now lives up to 180 s instead of 10 s before `ingest()`'s own prune step removes it — read
  `_apply`/`ingest` directly (`firing_receiver.py:188-219`): every `ingest()` call prunes every
  entry whose `expires_at_sim` the batch's own `dcs_model_time_s` has passed, independent of
  whether any event named that unit this batch. **This prune runs on every ingest, not only when
  an event arrives for that specific unit** — so a chatty stream for unit A does not delay the
  prune of a stale entry for unit B. 180 s of a few hundred units' worth of entries is not a
  meaningful memory concern on a desktop collector process.
- **Death removal** (`_DEATH_KINDS`) removes an entry immediately and independently of the
  watchdog, further bounding how long any one entry actually survives in the realistic case (a
  unit that stops firing either sends `END`, dies, or is the rare dropped-`END`-while-alive case
  the watchdog now covers at 180 s).

**The raise to 180 s is the Stage A/B reviewer-verified fix for a real finding** (watchdog
conflated two failure modes — see `.claude/agent-memory/implementer/
feedback_watchdog_timeout_owns_only_the_cases_death_doesnt.md` and the matching reviewer memory),
re-verified here by reading the two new tests and the mutation-based re-review already on file
(`review-2.md`): reverting the constant to `10.0` makes both new tests fail for the stated reason.
I did not have a `.venv` in this fresh worktree to re-run that mutation myself (see Verification
note below), so I am relying on `review-2.md`'s own documented mutation run rather than asserting
a fresh one — flagged, not silently assumed.

**Against a chatty-but-legitimate stream** (a sustained burst with frequent `START`/`END`
cycling): each `START` *replaces* the dict value for that initiator (`_apply`'s `S_EVENT_
SHOOTING_START` branch constructs a fresh `ActiveEmitter`, keyed by name) rather than appending, so
cycling does not grow the map — one entry per currently-or-recently-firing unit, always. No
unbounded accumulation under any stream shape I can construct within the realistic (or even
adversarial-but-loopback-bounded) threat model.

**Verdict on this point: no material exposure**, stated explicitly rather than waved through on
"it's LAN-only" — the relevant boundary here is narrower than LAN: this specific channel is
loopback-only, one further step removed from the LAN-reachable `GET /firing/latest` read side.

### The no-omniscience gate — Stage A's bypass, unwidened

**Confirmed by diff, not by the plan's claim about it**: `git diff main..8303d3b --
body-layer/src/perception/visibility.py` across all four Stage B commits is **empty**. The plan's
own Stage B bullet ("Nothing in `visibility.py` changes in Stage B") holds exactly — the file is
untouched at the byte level, not merely "untouched in the parts I looked at."

**Stage B only ever supplies a second kind to the same `Emitter` the Stage A gate already
consumes** (`body-layer/src/perception/emitters.py`'s `resolve_emitters`): `firing_emitters` reads
this poll's `GET /firing/latest` snapshot, joins by `unit_name` against this poll's
`raw_objects`, and returns `Emitter(kind=EmitterKind.FIRING, targets_ownship=...)` for matches —
structurally identical in shape and contract to Stage A's `burning_emitters` (same non-unique-
`unit_name`-drops-to-unresolved rule, same `.get(object_id)` returning `None` for every
unresolved case). Nothing new is added to `check_visibility`'s gate logic itself; the bypass
Stage A already built (range/size gate, forest gate, tier-clamp to `lowres`/presence, never
raising classification) is reused unmodified.

**`CONTACT_FIRING_SEEN` was checked directly against both exempt sets, not inferred from
comments** — per the Stage A security memory's own instruction to re-check this at every new
`EventKind`. Read `_OBSERVABILITY_EXEMPT_KINDS` (`callouts.py:398-400`, `frozenset({CONTACT_
ENGAGEMENT_CHANGED})`) and `_WATCHED_ONLY_KINDS` (`callouts.py:450-452`, `frozenset({CONTACT_
MOTION_CHANGED, CONTACT_RANGE_CROSSED, CONTACT_ENGAGEMENT_CHANGED})`) directly: neither
`CONTACT_FIRING_SEEN` nor `CONTACT_BURNING_SEEN` is in either set. Both callout kinds behave like
an ordinary, always-eligible-to-speak event, which is what the plan's design intends
("Informational, not a threat line" for burning; "taking fire"/"something firing" wording for
`FIRING`, gated on `targets_ownship` for priority only, not on observability exemption).

**`targets_ownship` crosses the wire as a single bit, not an identity.** Confirmed from
`schema/firing.py`'s own docstring and `_parse_bool01`: the Hook script compares `event.target`
against `world.getPlayer()` once, Lua-side, and only the resulting `0`/`1` crosses the wire — the
raw target identity (which could in principle have been some other named unit) never reaches the
collector or body-layer. This is the same "collapse to a bounded, perceivable signal before it
crosses the boundary" shape Stage A's `getLife()`/`getLife0()` → fire-band-predicate collapse
used, applied here to a different field. Grepped `aircraft-layer/src` and `body-layer/src` for
any wire field name that could carry a raw target unit name on this channel — none exists;
`entry.get("targets_ownship")` on the body-layer side is the only field read for this purpose
(`emitters.py`'s `firing_emitters`), and it is coerced to `bool`.

**The `MAX_SIGHTLINES_PER_CALL = 128` truncation risk the plan flagged is mitigated in this
stage, read from the diff rather than taken on the plan's word.** `petrobrain-line-of-sight-
hook.lua`'s sort key changed from `rangeM` alone to `(not firing, rangeM)` — every unit in
`PB_ACTIVE_FIRING_UNITS` (maintained by the firing-events Hook's own event handler, real-time, no
poll latency) now sorts ahead of every non-firing unit regardless of range, so a firing unit is
never truncated by the cap before it gets a sightline. The lookup (`firingUnits[a.name] ~= nil`)
reads a name set maintained by a trusted sibling Hook script in the same mission-scripting state —
not new untrusted input, and `PB_ACTIVE_FIRING_UNITS or {}` degrades to the pre-existing
range-only sort when that script is not loaded (a true no-op, confirmed by reading the comment and
the fallback expression together). This closes a real omniscience-adjacent risk (a feature meant
to admit distant emitters being silently neutered by an unrelated cap) rather than opening one.

### Other checks

- **Mission-restart / replay.** `dcs_model_time_s` regressing by more than `_RESTART_TOLERANCE_S`
  (0.5 s) clears the whole `_active` map (`ingest`, lines 197-209) — covers both a real mission
  restart and a bridge reconnect replaying old state, matching the plan's "no entry survives a
  mission boundary" row. Tested (`test_a_mission_restart_clears_every_tracked_entry`,
  `test_harmless_jitter_within_tolerance_does_not_clear_state`).
- **Duplicated/out-of-order events within a batch.** `ingest` applies events in the order the Hook
  drained them (arrival order), so a `START` immediately followed by its own `END` in the same
  batch applies the latch formula correctly (tested,
  `test_a_sub_poll_burst_start_and_end_in_the_same_batch_survives_one_poll`). A duplicate `START`
  for an already-active unit simply replaces the `ActiveEmitter` with an equivalent fresh one —
  idempotent, no state corruption.
- **Thread safety.** `EmitterTracker.ingest()`/`snapshot()` run on different threads (receiver
  thread vs. API server request thread) with no lock, the same GIL-level "effectively atomic
  enough" posture the codebase already accepts for `F10CommandQueue.drain_all` — not a new
  posture, stated explicitly in the module's own docstring rather than silently assumed.
- **`S_EVENT_SHOT`'s `x`/`z` seam** (`BL-B74`, not built this stage) is parsed but never acted on
  by `EmitterTracker._apply` (explicit no-op comment, line 244-247) — confirmed by reading the
  method, not inferred from the docstring's claim about it.

### Verification note

`aircraft-layer/.venv` and `body-layer/.venv` do not exist in this fresh worktree (git worktrees
do not carry a subproject's `.venv`), so I could not run `ruff`/`mypy`/`pytest` myself, including
re-running the watchdog mutation test independently. The dispatch states checks were green at
`1e6c697` (everything after is docs) and `review-2.md` documents its own mutation run against the
same two tests with the result pasted above. I am relying on that documented run, not asserting a
fresh one.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/schema/firing.py` (`from_wire`) | free-text field (`initiator`) inside a delimited wire format | A literal `;`/`:` in a unit name can corrupt entry splitting, dropping the whole batch (fail-closed) | None — low probability/low impact, same pre-existing shape as other feeds; optionally hardened later |
| `aircraft-layer/src/collector/firing_receiver.py` (`EmitterTracker._active`) | unbounded dict, no explicit size cap | Bounded by loopback trust boundary + real mission cardinality + 180 s watchdog + immediate death-removal; no unbounded growth under any realistic or loopback-bounded adversarial stream | None |
| `body-layer/src/perception/visibility.py` | emitter bypass (Stage A) | Unwidened — zero-diff across all four Stage B commits, confirmed by `git diff` | None |
| `body-layer/src/belief/callouts.py` (`_OBSERVABILITY_EXEMPT_KINDS`, `_WATCHED_ONLY_KINDS`) | frozenset membership for new `EventKind` | `CONTACT_FIRING_SEEN` correctly absent from both, checked directly | None |
| `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` (sort key splice) | reads a trusted sibling-script global, not new untrusted input | Mitigates the plan's own named truncation risk; degrades to pre-existing behaviour when absent | None |

### Verdict

**APPROVED**

No exploitable vulnerability, no new dependency, no widened omniscience bypass, no unbounded
resource growth within this feature's actual trust boundary (loopback-only Hook→collector,
no-auth LAN read endpoint consistent with every other endpoint on this server). One low/low
finding (semicolon/colon in a unit name corrupting entry splitting) is noted above with the
standard risk-communication options; recommended disposition is (A) Ignore, consistent with the
same accepted wire-format shape elsewhere in this codebase.

### Required Fixes (if any)

None.
