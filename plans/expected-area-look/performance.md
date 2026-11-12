### Performance Review

`BL-B111`, "expected-area look," `feature/expected-area-look` @ `27eaed47dbc4f8e273f321f8e9d831c2e0d3e81f`
(fast-forwarded cleanly from local `main` @ `b92d59c9`; tree clean before and after). Budget context:
no hard real-time budget applies yet (root `CLAUDE.md`) — the applicable bar is "no per-request
allocation on hot paths / prefer precomputation and batching," judged against body-layer's real
poll rate, `_DEFAULT_POLL_INTERVAL_S = 1.0` (1 Hz), not any Runtime-phase latency SLA.

**Measured directly** where cheap: recreated `body-layer/.venv` (none existed in this worktree;
`python3.12 -m venv .venv` + `pyproj>=3.6` + `numpy>=1.26,<2.5`, matching `pyproject.toml`'s pinned
deps) and timed the four functions this feature actually adds, against the real production code,
using `Contact`/`Observation` fixtures built the same way `test_expected_area.py`'s own `_contact`
helper does. Script kept at `plans/expected-area-look/perf_probe_b111.py`; its own can-this-fail
probe (a close contact with a huge cross-range sigma must not fit one look) passed before any
timing was trusted.

```
probe_points_for:      2.14 us/call
area_fits_one_look:    1.52 us/call
a_out_of_view:         0.07 us/call
area_visibility:       0.38 us/call
resolve_checks (1 check): 13.2 us/call
```

Everywhere else the composed primitives this feature calls (`look_target_for`, `profile_for`/
`apparent_extent_m`/`distinctiveness_of`/`tier_ranges`, `perception.cockpit_mask.is_visible`,
`ForestOcclusion.occluded`) are already measured elsewhere at this project's own scale — reused
here rather than re-measured, per `[[project_bl_b110_expected_area_check_sector_and_location_gain_cost]]`,
`[[project_cockpit_mask_gate_cost]]` and the forest-occlusion plan's own "Measured cost" section.

### Findings

#### `_resolve_expected_area_checks`'s per-check evidence assembly + `resolve_checks`

- **Location:** `body.py:_resolve_expected_area_checks`, called once per poll from `run_once`
  immediately after `store.tick()`; `belief.expected_area.resolve_checks`.
- **Risk:** none at realistic scale. `checks` is capped at `belief.expected_area.MAX_OPEN_CHECKS`
  (2) by `ContactStore.ingest`'s own cap check before a third check can open — this is not a
  per-contact or per-candidate loop, it is a loop over at most 2 items, the tightest possible
  bound this codebase uses anywhere. Measured: the four new pure functions sum to ~4.1 µs/check;
  `resolve_checks` itself is 13.2 µs for one check. At the worst case of 2 concurrent checks,
  evidence assembly + `resolve_checks` together cost **~35 µs/poll — 0.0035% of the 1.0 Hz
  (1,000,000 µs) poll budget.** Composing in the reused primitives from memory (`look_target_for`
  ~5.75 µs, cockpit-mask `is_visible` ~1.44 µs, `profile_for`/`tier_ranges` chain ~1.9 µs, each
  called once per check) adds at most another ~18 µs at 2 checks. Total composed cost is still
  three orders of magnitude under budget, consistent with every other per-contact-bounded cost
  finding in this codebase.
- **Action:** MONITOR (effectively a non-issue; recorded for completeness, not because it is
  close to a limit).

#### Forest/settlement occlusion lookup, called once per open check

- **Location:** `body.py:_resolve_expected_area_checks` → `runner.area_forest_occlusion.occluded`
  / `runner.area_settlement_occlusion.occluded` (`perception/forest.py`, the layer/class-set
  parameterised `ForestOcclusion`, reused — not duplicated — for the settlement mask per the
  plan's own "one class, two instances" design).
- **Risk:** `ForestOcclusion.occluded` is already measured at 0.075 ms median (cold,
  `containing_polygons` against the real `syria-full` store) with a per-cell memo cache
  (`forest-occlusion/plan.md`'s own "Measured cost" section). The new settlement instance adds a
  **second** such cache, but it is only ever queried for `A`'s believed point while a check is
  open — bounded to at most 2 distinct positions per poll, and in practice far fewer over a
  sortie (a check opens rarely; see the trigger-rate discussion in `plan.md`/`implementation.md`).
  Worst case, both caches miss on both checks: 2 × 0.075 ms × 2 occlusion kinds ≈ 0.3 ms/poll,
  and that is the absolute upper bound on a cold poll with two brand-new check positions — not a
  realistic steady state, since the hold's own area-fits-one-look constraint means `A` does not
  move far across the hold and the same cell is re-hit on every subsequent poll. Each instance's
  cache dict grows unbounded over a sortie's lifetime, same shape as the pre-existing
  `ForestOcclusion` instance already carries elsewhere — not a new growth pattern, and bounded in
  practice by the number of distinct 50 m cells any check's `A` has ever occupied (a handful per
  sortie, not per-object-per-poll).
- **Action:** MONITOR. Same posture as the forest-occlusion plan's own existing MONITOR item on
  this cache; nothing here raises its risk.

#### Synchronous `post_probe_points` push, "on change" only

- **Location:** `body.py:_resolve_expected_area_checks` → `aircraft_client.post_probe_points` →
  `AircraftLayerClient._post_json` (synchronous `urllib.request.urlopen`, `timeout_s` default,
  same client/timeout posture as every other `AircraftLayerClient` method).
- **Risk:** real but not new. This is the same shape as the already-reviewed `post_look_direction`
  call (`[[project_body_layer_poll_loop_serial_unpooled_gets]]`'s sibling finding: no connection
  pooling across any `AircraftLayerClient` method, a pre-existing architectural property of the
  whole client, not something this feature introduces). The feature's own mitigation — pushing
  "on change" only (`points_t != runner._last_probe_points`), mirroring `post_look_direction`'s
  own pattern exactly — means this fires at most once per state transition (a check opening,
  changing its probe points as `A`'s estimate moves, or every check closing and clearing to
  `N = 0`), not once per poll. Across a hold's lifetime (≤ 17 s worst case, typically 5–8 s per
  `plan.md`) this is a small, bounded number of extra round trips, not a per-poll cost added to
  the existing 6–8-GET poll loop baseline.
- **Action:** MONITOR, same cadence as the client's own pre-existing debt
  (`[[feedback_gated_http_call_before_the_gate]]`'s pattern does **not** apply here — the fetch
  is correctly placed after the emptiness/on-change gate, not before it, which is the defect that
  memory warns about).

#### `get_line_of_sight_latest()` re-fetched inside `_resolve_expected_area_checks`

- **Location:** `body.py:1602`, gated by `if not checks: return` immediately above — only called
  when at least one expected-area check is open.
- **Risk:** this is a **second** `GET /line_of_sight/latest` call within the same poll whenever a
  check is open — `perception/naked_eye_source.py:740` already fetches the same endpoint once per
  poll for `NakedEyePerceptionSource.poll`. The gate on `checks` means the extra round trip only
  fires during the rare window a check is actually open (the trigger is narrow: `A` out of view,
  area-fits-one-look, a gate-path fold/echo/beside-lost match — `plan.md`'s own "measured trigger
  rate" risk, still open pre-flight), so this is not a per-poll cost at this project's scale. It
  is a real, avoidable redundant network call during that window, not a correctness or scale risk
  — the two fetches could share one sample by threading the snapshot `naked_eye_source` already
  pulled through to `body.py`, saving one loopback round trip per poll while a check is open.
- **Action:** LATER (not NOW). The fix is a small plumbing change (pass the already-fetched
  `LineOfSightSnapshot` through rather than re-fetching), worth doing opportunistically next time
  this code path is touched, but the cost today — one extra loopback GET, only while ≤ 2 checks
  are open, bounded by the same `timeout_s` every other `AircraftLayerClient` call already
  tolerates — does not justify a standalone change-request cycle (Implementer → Reviewer → DoD)
  on its own.
- **Mitigation (when picked up):** have `body.py`'s poll loop fetch the LOS snapshot once per
  poll and pass it to both `NakedEyePerceptionSource.poll` and
  `_resolve_expected_area_checks`, rather than each fetching it independently.

#### `ExpectedAreaLogWriter` — per-poll JSONL rows while a check is open (`--expected-area-log`)

- **Location:** `body.py:_resolve_expected_area_checks` → `expected_area_log.py`'s
  `ExpectedAreaLogWriter.write` — open-append-close per row, unbuffered, disable-after-first-failure
  (the same shape `SpeechLogWriter`/`GroupTraceLogWriter` already use).
- **Risk:** `[[project_speech_log_writer_is_the_reusable_low_frequency_jsonl_pattern]]` pre-approves
  this file-reopen-per-write shape **at per-utterance/per-clip frequency**, explicitly flagging that
  a per-poll or per-tick call site would need buffering instead. This writer is called once per
  *open* check per poll (one "open" row per check per poll it stays open) plus one "verdict" row
  when a check resolves — a genuinely higher frequency than any prior instance of this pattern, but
  tightly bounded on both axes that matter: at most `MAX_OPEN_CHECKS` (2) rows per poll, and only
  for the duration one check stays open (≤ 17 s worst case, `plan.md`'s own figure). Defaults off
  (`--expected-area-log` absent is a true no-op, same posture as every other per-run debug log), so
  there is no cost at all in the default configuration. When enabled, worst case is 2 file
  open/write/close cycles per poll for a bounded handful of seconds per check — nowhere near
  `DetectionTraceWriter`'s per-candidate-per-poll volume this pattern was built to avoid.
- **Action:** MONITOR. Flagging the frequency drift from the established "per-utterance" precedent
  explicitly (see Persistent Agent Memory below) so a *future* writer copying this shape at an
  actually unbounded per-poll frequency is not waved through on this file's precedent alone.

#### Non-continuity re-detection opening a second held check against the same `A`

- **Location:** `ContactStore.ingest`'s gate-fold branch (`contacts.py:1548`/`1612`), the path the
  Reviewer already named in `review.md` ("Review Summary", the dispatch's own named question).
- **Risk:** cost-wise, a non-issue — it does not add a new cost class, only a second instance of
  the already-negligible per-check cost measured above, and it is structurally bounded by the same
  `MAX_OPEN_CHECKS` cap already covering the ordinary case (the cap is checked with
  `len(self._checks) < MAX_OPEN_CHECKS` before opening either check, an O(1) dict-length read, not
  a scan). The `copy.deepcopy(fold_target)` taken for `a_snapshot` on check-open only runs when the
  rare trigger actually fires (bounded by the same 2-check cap), not per poll. Reviewer's own
  framing stands from a performance angle too: bounded latency/slot cost, no wrong-result loop, no
  unbounded growth.
- **Action:** MONITOR (no performance action needed; this finding is purely a cross-reference
  confirming the Reviewer's correctness-framed note has no hidden cost tail).

#### `GroupStore.reconcile` / `mission_memory.admission.step` skipping held contacts

- **Location:** `contacts.py:2253` (`not self.has_open_check(contact.id)` inside the existing
  per-contact list comprehension feeding `reconcile`), `admission.py:534`
  (`if contacts.has_open_check(contact.id): continue` inside the existing per-contact loop).
- **Risk:** none. `has_open_check` is `contact_id in self._checks`, an O(1) dict-membership test
  added inside loops that already iterate every contact once per poll (pre-existing O(n), not
  introduced by this feature). This adds a constant per-contact cost on the order of the dict
  lookups these loops already perform elsewhere, not a new complexity class.
- **Action:** MONITOR (effectively a non-issue).

#### `choose_glass_look`'s new `area_check` bucket (`-1`, ranked first)

- **Location:** `optic_policy.py:1787` (`choose_glass_look`), `_area_or_glass_can_improve`
  (`optic_policy.py:1624`).
- **Risk:** none. This changes which bucket a target sorts into, not the loop's complexity —
  `choose_glass_look` still runs `choose_look` over whichever single bucket is selected
  (`min(by_bucket)`), and an `area_check` target's own bucket is capped at `MAX_OPEN_CHECKS` (2)
  members, strictly smaller than any other bucket's realistic size. `[[project_bl_b110_expected_area_check_sector_and_location_gain_cost]]`
  already covers `choose_look`'s own O(k²) cost at realistic `k`; this feature narrows `k` for the
  bucket it adds rather than widening it.
- **Action:** MONITOR (non-issue).

#### Lua probe evaluation (`land.getHeight`/`land.isVisible`, up to 6 points)

- **Location:** `petrobrain-line-of-sight-hook.lua`'s new probe chunk, evaluated inside the
  existing LOS chunk after the per-unit sightline loop, at the collector's own poll rate (not per
  DCS render frame — the file's own comments and the plan's "Stage 1" section both place this in
  "the LOS chunk," the same cadence the unit sightlines already run at).
- **Risk:** low. Bounded to `MAX_PROBE_POINTS` = 6 points, each one `pcall(land.getHeight, ...)` +
  `pcall(land.isVisible, ...)` — the same two calls the per-unit sightline path already makes at
  1 Hz for every tracked unit, measured in `aircraft-layer/research/2026-09-29-bridge-terrain-
  probe-results.md` at ~25 µs peak per sightline. 6 probes at that rate is ~150 µs peak, added once
  per poll only while probes are non-empty (N = 0 clears when no check is open). This has not been
  re-measured live (no DCS available in this sandbox) — the plan's own Stage 1 Windows card
  (confirm `bridge_call_ms` does not move) is the right verification step and is still owed,
  exactly as `review.md` already notes for the DCS-side mechanism generally.
- **Action:** MONITOR until the Windows card runs; no reason from the existing cost model to expect
  a different outcome, since this reuses an already-measured primitive at a tightly bounded count.

### Verdict

APPROVED — MONITOR
