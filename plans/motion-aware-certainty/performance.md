### Performance Review

Scope: body-layer only, diff `e6a43148..9228a080` (BL-B112, motion-aware contact certainty).
Body tick budget: poll loop runs at a few Hz, small/fast-model brain waiting on it; no hard
real-time budget yet (that starts with Petrobrain Runtime), but no per-request allocation or
full-dataset iteration on the hot path should be introduced regardless.

### Findings

#### `certainty_of` growth-based tracked/estimated boundary (`belief/decay.py`)
- **Location:** `certainty_of` → `distance_since_last_seen_m` → `association_over_time.
  contact_growth_rate_mps(contact)`, replacing a bare elapsed-time comparison against
  `POSITION_HALF_LIFE_S`.
- **Risk:** none credible. The added work is `object_model.profile_for(contact.last_class_raw)`
  (a `functools.cache`d lookup — O(1) after the first call for any given `object_type` string,
  the keyword-tuple scan only runs on a cache miss) plus two attribute checks and one multiply.
  This replaces one float comparison with one cached dict lookup + arithmetic — still O(1) per
  call, no allocation, no I/O. Call sites: `belief/contacts.py` (per-contact per tick, inside
  `ContactStore.tick`), `belief/callouts.py` (per candidate in a callout check), `belief/tools.py`
  (several list/sum comprehensions over `store.contacts`, driven by brain tool-API requests, not
  the poll loop itself), `mission_memory/admission.py` (per contact per poll, gated). All of these
  operate over the live contact set, which the project's own operating envelope keeps to tens of
  contacts (50–800 m AGL normal envelope; dozens of simultaneous contacts, not thousands). `speech.
  py`'s `_needs_hedge` and `crew_console.py` do **not** call `certainty_of` at all — they read the
  already-computed `facts["certainty"]` string that was set once upstream, confirming the function
  runs once per contact per tick rather than being re-invoked per consumer.
- **Action:** MONITOR. Cost is the same O(1)-per-contact class as before; nothing here is a
  budget-violation risk at this scale. Worth re-checking only if `profile_for`'s keyword-tuple scan
  ever grows large enough to matter on a cache miss, which it is nowhere close to today (~a few
  dozen entries).

#### `LostContactTracker` / `mission_memory/admission.py` lost-write path
- **Location:** `LostContactTracker` (`admission.py`), `_write_lost_entries`, `step`.
- **Risk:** the backlog concern this review was asked to check (BL-B38: "walks every contact ever
  founded") **does not apply here**. `LostContactTracker` is `FiredOnTracker`'s direct sibling: it
  keeps `_scanned_event_count` and only looks at `contacts.events[tracker._scanned_event_count:]`
  — the slice since the last `step` call — never the full event history or the full contact set.
  `_write_lost_entries` then filters that slice to `CONTACT_LOST` events only. The per-poll cost is
  O(new events since last poll), not O(all contacts ever founded) and not O(all events ever
  logged).
- **Action:** NOW (no code change needed) — verified correct; recorded here as a decision log
  entry so the BL-B38 question is answered rather than left open against this feature.

#### Mission-memory file I/O for lost entries
- **Location:** `MissionMemoryLogWriter.write` (`mission_memory/log.py`), reached via
  `_write_lost_entry` → `memory.append`.
- **Risk:** file I/O per lost event, not per tick, confirmed. `_write_lost_entries` only calls
  `_write_lost_entry` once per `CONTACT_LOST` event found in the new-events slice — a rare
  belief-state transition, not a per-poll occurrence. `MissionMemoryLogWriter` already documents
  its own volume assumption ("a handful to a few dozen per sortie... ~3600 in a worst-case two-hour
  sortie") and its unbuffered `open(..., "a")`-per-write design is a deliberate crash-safety choice
  at that volume, predating this feature. The lost-write path reuses this unchanged; it does not
  add a new write pattern, only a new reason (`CONTACT_LOST`) to use the existing one.
- **Action:** MONITOR (no change; this was already an accepted tradeoff for `group`/`air_defence`/
  `fired_on` entries, and lost-entries inherit the same bound).

#### `belief/motion.py` `fold_motion` watch-window changes
- **Location:** `fold_motion`, called once per contact per percept match from `Contact.record`/
  `Contact.from_percept`.
- **Risk:** none. Pure O(1) function, no allocation beyond one small frozen dataclass per call
  (same shape as the pre-existing classification/cardinality fold functions it mirrors). The new
  founding-watch branch adds one more `if`/comparison, not a loop or lookup.
- **Action:** MONITOR.

#### Object-type profile table growth (`perception/object_model.py`)
- **Location:** `_KEYWORD_PROFILES` additions (SA-2 components, SA-10 immobile flags, SA-6
  override).
- **Risk:** none. Static data only; `profile_for` stays `@cache`d, so repeated calls for the same
  `object_type` string are O(1) regardless of table size, and the table is still a few dozen rows.
- **Action:** MONITOR.

#### Pre-existing full-iteration block noted but out of scope
- **Location:** `belief/contacts.py`, the `certainty_of_a_is_lost = {candidate.id: certainty_of(
  candidate, now_sim) == "lost" for candidate in self._contacts.values() ...}` dict comprehension
  inside the fresh-founding branch (gated by `self._expected_area_checks and len(self._checks) <
  MAX_OPEN_CHECKS`).
- **Risk:** this *is* a full iteration over all live contacts, and it now does marginally more
  work per candidate (the `certainty_of` growth check). It is **not** part of this diff** — `git
  log e6a43148..9228a080 -- src/belief/contacts.py` shows the only change to this file in scope is
  the unrelated `fold_motion` call hoisting (Contact.from_percept). This block predates BL-B112
  (expected-area-check feature) and was presumably already assessed there. Flagging only because
  it is the one real full-iteration pattern adjacent to the reviewed code, gated to "a new contact
  founds while expected-area checks are enabled and under the open-check cap" — not a per-tick
  event, and bounded by the same tens-of-contacts envelope.
- **Action:** MONITOR. No change requested; out of this feature's scope.

### Verdict
APPROVED
