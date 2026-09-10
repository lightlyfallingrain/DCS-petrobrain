### Implementation Summary

BL-4 built as planned across three commits on `feature/bl4-attention-events`:

1. `26380b1` — new `belief/attention.py`: 4-state `Attention` (`ignore`/`normal`/`watch`/
   `priority`, replacing BL-2 Stage 4's 2-state enum), `Sector` (8 cardinal/intercardinal
   wedges), `AttentionArea` (center `GeoPosition` + radius + optional sector — no polygon or
   place-name type), `area_contains`, `effective_attention` (direct mark folded with area
   membership; explicit `"ignore"` always wins). Standalone module, not yet wired in.
2. `2ae3c06` — wires the above into `contacts.py`/`tools.py`/`console.py`: `Contact.attention`
   moves to the new 4-state type; `tools.set_attention` replaces `watch_contact`/
   `unwatch_contact`; `ContactStore` gains an `AttentionArea` registry (`add_area`/`remove_area`/
   `areas`); `facts.attention`/`get_contacts`'s `"watched"` filter both read *effective*
   attention now. `events.py` gains `CONTACT_ATTENTION_CHANGED` + `attention_event_kind` +
   `EVENT_COOLDOWN_S`; `Contact` gains `last_emitted_attention` + `last_event_emitted_sim`;
   `ContactStore.tick` applies a per-contact-per-kind emission cooldown uniformly across all
   three event kinds (lifecycle, classification, attention), gating emission only, never the
   underlying state-snapshot comparison. New console commands: `attention <id> [<level>]`
   (query/set), `watch-area`/`unwatch-area`/`areas`.
3. `422f375` — the event queue: `ContactStore.unacknowledged_events`/`acknowledge_event` (a
   plain `set[str]` of acknowledged ids, not a mutable field on the frozen `Event` dataclass),
   `tools.list_events`/`acknowledge_event`, console `events`/`ack <id>`.

### Files Changed
- `body-layer/src/belief/attention.py` — new: `Attention`, `Sector`, `AttentionArea`,
  `area_contains`, `effective_attention`.
- `body-layer/src/belief/contacts.py` — `Attention` import moved from a local definition;
  `Contact` gains `last_emitted_attention`/`last_event_emitted_sim`; `ContactStore` gains the
  area registry and the unacknowledged-event queue; `tick` extended with the attention-changed
  event kind and the cooldown gate applied to all three kinds.
- `body-layer/src/belief/events.py` — `CONTACT_ATTENTION_CHANGED`, `attention_event_kind`,
  `EVENT_COOLDOWN_S`, `Event.previous_attention`/`.attention` fields; module docstring
  cross-references `classification.py`'s `CLASSIFICATION_CONTRADICTION_LOCKOUT_S` to head off
  conflating the two suppression mechanisms.
- `body-layer/src/belief/tools.py` — `set_attention` (replaces `watch_contact`/
  `unwatch_contact`), `watch_area`/`unwatch_area`/`list_areas`, `get_attention_state`,
  `list_events`/`acknowledge_event`; `_contact_facts`/`_contact_summary`/`get_contacts`'s
  `"watched"` filter all read effective attention via `effective_attention` rather than the raw
  direct mark.
- `body-layer/src/belief/console.py` — `attention <id> [<level>]`, `watch-area`/`unwatch-area`/
  `areas`, `events`/`ack <id>`; `watch`/`unwatch` kept as aliases over `set_attention` with
  `level="watch"`/`"normal"`, byte-for-byte unchanged output.
- `body-layer/tests/test_attention.py` — new: pure-function tests for `area_contains`/
  `effective_attention` (sector boundary inclusivity, ignore-always-wins, tie-goes-to-direct,
  best-of-multiple-areas).
- `body-layer/tests/test_events.py` — `attention_event_kind` transition tests.
- `body-layer/tests/test_contacts.py` — `tick` integration tests: attention-changed events fire
  on a direct-mark change and on area-membership change (with no direct-mark change), explicit
  `"ignore"` wins over a priority area, cooldown suppresses rapid re-emission but not after it
  elapses, ordering (classification before attention within one tick), area registry round-trip,
  event-queue round-trip.
- `body-layer/tests/test_tools.py` — `set_attention`/`watch_area`/`unwatch_area`/`list_areas`/
  `get_attention_state`/`list_events`/`acknowledge_event` tests; `_contact_summary`'s call sites
  updated for its new `attention_level` parameter; `get_contacts`'s `"watched"` filter test for
  area-derived membership.
- `body-layer/tests/test_console.py` — `attention`/`watch-area`/`unwatch-area`/`areas`/`events`/
  `ack` command tests; the existing scripted-session acceptance test's event count updated from
  2 to 3 (a watch/unwatch round-trip now legitimately fires `CONTACT_ATTENTION_CHANGED`).

### Tests Added
42 new tests across `test_attention.py` (9), `test_events.py` (+3), `test_contacts.py` (+8),
`test_tools.py` (+11), `test_console.py` (+11, minus 2 net from folding two watch-command
assertions into one round-trip test) — see file list above for what each covers. Baseline 291 →
333 passing.

### Checks
- `ruff format --check body-layer/src body-layer/tests`: pass (every commit individually)
- `ruff check body-layer/src body-layer/tests`: pass (every commit individually)
- `cd body-layer && mypy src`: pass, strict, no errors (every commit individually)
- `pytest body-layer/tests -q`: pass — 300 after commit 1, 326 after commit 2, 333 after commit 3

### Notable Discoveries
- `effective_attention`'s signature could not literally match the plan's prose
  (`effective_attention(contact, areas, now_sim)`) — passing a `Contact` would make `belief.
  attention` (imported by `belief.contacts`) circularly import `belief.contacts`. Took plain
  values instead (`Attention`, `GeoPosition`, `Sequence[AttentionArea]`); `now_sim` was dropped
  entirely since nothing in this milestone's area model is time-dependent.
- `Contact.last_emitted_attention` stores the *effective* attention (direct mark folded with
  areas), not the raw direct mark — this is what makes a contact silently entering/leaving a
  watched area fire its own `CONTACT_ATTENTION_CHANGED` event with no direct-mark change at all.
  This is intended per the plan's area-attention design, not a bug, but it changed BL-2's
  existing scripted-console-session acceptance test's expected event count (2 → 3), since that
  test's watch/unwatch round-trip now genuinely produces an attention-changed event on the
  second `tick()` call.
- Splitting an already-fully-written diff into three independently-green commits was done via
  `git stash push --keep-index` (stage the target commit's files, stash the rest, verify, commit,
  pop) for commit 1, and via temporary `Edit`-based strip/restore of the cleanly-separable
  event-queue code for the commit 2/3 split — recorded as a reusable technique in agent memory.
- `console.py`'s structural test (`test_console_module_contains_no_belief_logic`, asserting every
  public `tools.py` function is referenced in `console.py`) forced `get_attention_state` to get
  a real console surface even though the plan didn't name one explicitly — resolved by
  overloading `attention <id>` (no level) as a query, `attention <id> <level>` as the existing
  set, rather than adding a separate command name.
