### Goal

Build BL-4 (= PB-4 plus the runtime doc's event model section): real attention-state and
area-attention machinery on top of BL-2 Stage 4's bare `normal`/`watch` enum, plus event
detection for attention changes, cooldown/chatter suppression on the event log, and the
event-queue consumption mechanics BL-5's `poll_events`/`acknowledge_event` will later wrap —
still console-driven, no LLM, no new perception/geometry primitives.

**Explicitly out of scope** (per `todo/todo.md`'s "Attention direction and detection cones"
deferred entry): distinct optical modes (peripheral/naked-eye/binocular/APS-17), scan-loop
logic, attention *direction* as a perception-gating input. That entry names BL-4 as the
milestone whose machinery it will eventually sit on top of, not something BL-4 builds itself.
Also out of scope: threat/relevance scoring (BL-6), mission-phase-driven attention, and natural-
language place resolution (`find_place`, BL-5/BL-6) — see the `watch_area` gap noted below.

### Two scoping questions resolved from existing docs (not escalated)

**Q1 — attention state count.** `plans/body-layer/plan.md` §3.3 already fixes `set_attention`'s
signature as `level: "ignore" | "normal" | "watch" | "priority"` — four states, no `TRACK`. The
runtime doc's fuller `IGNORE/NORMAL/WATCH/TRACK/PRIORITY` list explicitly defers `TRACK` ("worth
keeping `TRACK`/`IGNORE` semantics free to be driven by a threat-priority lookup later instead of
only manual player commands" — i.e. `TRACK` is threat-priority-table territory, BL-6+). Since
BL-5's tool signature is the load-bearing contract and it already excludes `TRACK`, BL-4 builds
exactly four states: `ignore`, `normal`, `watch`, `priority`.

**Q4 — event queue ownership boundary.** BL-5's milestone brief says it wraps `poll_events`/
`acknowledge_event` around "the machinery BL-0..BL-4 actually built" — the same framing BL-5
uses for `set_attention`/`watch_area`. That places the queue's actual mechanism (unacknowledged
tracking, an acknowledge mutation, console-testable list/ack commands) inside BL-4, mirroring how
BL-2 built `watch_contact`/`unwatch_contact` in `tools.py` and a console command ahead of BL-4/
BL-5 wrapping them. BL-4 therefore builds the full mechanism and a console surface (`events`,
`ack <id>`); BL-5 only adds the transport, the `{facts, summary, phrasing_hints}` wrapping, and
(separately, not this milestone) the `bypass_gate` urgent-event fast path described in §2 of the
body-layer plan, which needs threat assessment this milestone does not have.

### Affected Modules / Files

- `body-layer/src/belief/attention.py` *(new)* — `Attention` (4-state `Literal`, moved from
  `contacts.py`), attention rank ordering, `AttentionArea` (center `GeoPosition` + `radius_m` +
  optional cardinal `sector` + `level` + `id`/`source`), `area_contains`, `effective_attention`
  (combines a contact's direct mark with area membership).
- `body-layer/src/belief/events.py` — new `CONTACT_ATTENTION_CHANGED` `EventKind`, an
  `attention_event_kind` comparison function (mirrors `lifecycle_event_kind`/
  `classification_event`'s shape), `EVENT_COOLDOWN_S` constant, and the cooldown check.
- `body-layer/src/belief/contacts.py` — `Contact` gains `last_emitted_attention: Attention | None`
  and `last_event_emitted_sim: dict[EventKind, float]` (per-kind cooldown timestamps, same
  per-contact-state placement as the existing `last_emitted_*` fields). `ContactStore` gains an
  area registry (`add_area`/`remove_area`/`areas`) and an acknowledged-event set
  (`unacknowledged_events`/`acknowledge_event`). `tick()` extended to compute effective attention,
  emit `CONTACT_ATTENTION_CHANGED` through the same last-emitted-comparison pattern, and apply the
  cooldown check uniformly before appending any of the three event kinds. `Attention` import moves
  to `belief.attention`.
- `body-layer/src/belief/tools.py` — `set_attention` (replaces `watch_contact`/`unwatch_contact`
  with the general 4-level form BL-5's tool wraps directly), `watch_area`/`unwatch_area`,
  `get_attention_state`, `list_events`, `acknowledge_event`. `_contact_facts`' `attention` key now
  reports *effective* attention; a new `attention_source` distinguishes direct vs. area-derived.
- `body-layer/src/belief/console.py` — `attention <id> <level>` (general), `watch <id>`/
  `unwatch <id>` kept as aliases for backward compatibility, `watch-area <bearing_deg> <range_m>
  <radius_m> [sector]` (resolved from `enrichment.ownship` via `perception.geometry.
  project_from_bearing_range` — see the `watch_area` gap below), `unwatch-area <id>`, `areas`,
  `events`, `ack <id>`.
- `body-layer/tests/test_contacts.py`, `test_events.py`, `test_tools.py`, `test_console.py`, plus
  a new `test_attention.py` for the pure functions.

### Implementation Plan

1. **Attention core.** New `belief/attention.py`: 4-state `Attention` `Literal` + rank ordering
   dict. Move the type out of `contacts.py` (re-exported or imported there, no behavior change).
   `tools.set_attention(store, contact_id, level, source="console") -> bool` replaces
   `watch_contact`/`unwatch_contact`; update `console.py`'s `watch`/`unwatch` to call it with
   `level="watch"`/`"normal"` so existing console behavior and tests are unaffected, and add the
   general `attention <id> <level>` command. `get_contacts`' `"watched"` filter broadens to
   `attention in ("watch", "priority")`.
2. **Area attention.** `AttentionArea` (center + radius + optional cardinal `sector`, checked via
   `perception.geometry.bearing_deg` against the area's own center — not ownship-relative) +
   `area_contains`. `ContactStore` area registry. `effective_attention(contact, areas, now_sim)`:
   a direct `"ignore"` always wins (explicit suppression is intentional and must not be overridden
   by wandering into a watched area); otherwise the higher-ranked of direct-mark and best-matching
   area applies. Console `watch-area`/`unwatch-area`/`areas`.
3. **Attention-change events.** `Contact.last_emitted_attention` + `events.
   attention_event_kind(previous, current) -> EventKind | None`, wired into `tick()` after the
   existing lifecycle/classification comparisons (ordering: lifecycle, then classification, then
   attention — a contact's first tick still never emits an attention-changed event, same
   `previous is None` convention as the other two).
4. **Cooldown/chatter suppression.** `Contact.last_event_emitted_sim: dict[EventKind, float]` +
   `EVENT_COOLDOWN_S`. In `tick()`, gate *emission* (not the last-emitted-state snapshot update) on
   this per-contact-per-kind cooldown, applied uniformly to all three kinds. State snapshots
   (`last_emitted_certainty`/`last_emitted_classification`/`last_emitted_attention`) still update
   every tick regardless, so a suppressed transition is not silently lost — the next tick compares
   against the true current state, not a stale one.
5. **Event queue.** `ContactStore` tracks acknowledged event ids in a plain `set[str]` (not a
   mutable field on the frozen `Event` dataclass — keeps `Event` construction sites and existing
   tests untouched). `tools.list_events(store, unacknowledged_only=True)` /
   `tools.acknowledge_event(store, event_id) -> bool`. Console `events` / `ack <id>`.
6. **Tests.** Pure-function unit tests for `area_contains`/`effective_attention`/
   `attention_event_kind`/cooldown in `test_attention.py` and `test_events.py`; `ContactStore.tick`
   integration tests (attention-changed events fire, respect cooldown, ordering vs. the other two
   kinds); `tools.py`/`console.py` command tests for the new surface. `ruff format`/`ruff check`/
   `mypy --strict`/`pytest` per `body-layer/CLAUDE.md`.

### Risks & Unknowns

- **`EVENT_COOLDOWN_S` is an unverified guess**, same posture as `IDENTITY_HALF_LIFE_S`/
  `NAKED_EYE_RANGE_CAP_M` before live tuning — pick a conservative default, document it as
  provisional, revisit once a live sortie shows real flap rates.
- **`watch_area`'s place-name gap.** BL-4 builds bearing/range + radius area machinery, not
  natural-language place resolution — `find_place` (turning "the village" into a position) is
  BL-5/BL-6 work. The console command takes raw bearing/range from ownship; BL-5's `watch_area`
  tool will need `find_place`'s output to bridge to this same machinery. Flagged so it isn't
  mistaken for solved.
- **Two independent suppression mechanisms now coexist**: classification's existing 30 s
  contradiction lockout (suppresses re-*promotion* of a classification value) and this
  milestone's event cooldown (suppresses re-*emission* of the resulting event). They operate on
  different things and don't conflict, but a future reader could easily conflate them — worth a
  cross-reference note in `events.py`.
- **`effective_attention`'s ignore-always-wins rule** is a judgment call (explicit suppression
  should not be overridden by area membership) rather than an established requirement — local and
  reversible, not escalated, but noted here in case live use disagrees.
- No live-sortie acceptance is planned for this milestone specifically (console/replay-only, per
  BL-0's testability principle) — first live exposure will likely come bundled with BL-5's tool
  surface.

### Second-Order Effect

**Unblocks BL-5**: `set_attention`, `watch_area`, `get_attention_state`, `poll_events`, and
`acknowledge_event` can wrap real machinery instead of being stubbed, and BL-5's freeze-point tool
list has nothing left it depends on that isn't built by the end of this milestone. **Narrows BL-6**:
`effective_attention`'s rank ordering is a natural input to a future relevance/priority score,
so BL-6 can consume it rather than re-deriving attention state. Does not touch or unblock the
deferred optical-modes/scan-loop vision — that remains a future perception-layer milestone with
no dependency on this one either way.
