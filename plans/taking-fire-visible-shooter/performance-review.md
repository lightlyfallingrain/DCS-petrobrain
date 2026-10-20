### Performance Review

Batch reviewed: whole branch `fix/taking-fire-visible-shooter`, `git diff 431b5598..59eea085`
(tip `59eea0854589bd0a340a2f8a07a2bf9cfde83e3b`), covering both halves of F6
(`plans/taking-fire-visible-shooter/{debug,implementation}.md`): `perception/naked_eye_source.py`'s
new bypass-independent `targets_ownship_by_object_id`/`firing_by_object_id` per-candidate maps and
the cluster-fold priority reorder, plus the `belief/{percept,contacts,events,speech}.py` additions
carrying `firing_visible` across the no-omniscience boundary into `Contact`/`Event`/speech text.

This runs inside the 1 s body-layer poll tick (`NakedEyePerceptionSource.poll`, once per poll, once
per `check_visibility`-admitted candidate / per cluster), so the budget context is the one-second
poll period documented in `body-layer/research/2026-10-05-performance-review.md` (median poll ~330
ms before that review's fix, ~70 ms after it is applied — not yet confirmed landed on this branch).

### Findings

#### New per-candidate maps in `NakedEyePerceptionSource.poll`
- **Location:** `naked_eye_source.py` `poll()` — `targets_ownship_by_object_id` (un-gated from
  `result.emitter_kind is not None`, same shape as before) and the new `firing_by_object_id`, both
  built with one `for candidate, _result in visible:` pass each, dict lookups + attribute reads only.
- **Risk:** none credible. Both are single O(n) passes over `visible` (n = gate-admitted candidates,
  capped well under the 440-candidate sortie scale `body-layer/research/
  2026-10-05-performance-review.md` measured against), doing only a dict `.get()` and a boolean
  expression per candidate — no new allocation heavier than the dict entries themselves, no I/O, no
  recomputation of anything already resolved by `check_visibility`/the emitter collector.
- **Measured** (isolated micro-benchmark reproducing the exact loop shape, same field-access pattern,
  `/mnt/e/DCS-petrobrain/body-layer/.venv/bin/python3 -I`, `timeit`, 2000 iterations): **0.09 ms** at
  n=440 (the sortie's own measured candidate count) for both dicts combined. A 10x scale-up (n=4400)
  measured **1.06 ms**, an 11.7x increase for a 10x input — confirms linear (not quadratic) scaling;
  harness sanity-checked by asserting that ratio falls in `(5, 20)`, which would fail and flag a
  regression if this were accidentally O(n²) (ratio would land near 100x instead).
- **Action:** MONITOR (no mitigation needed; recorded so a future change to this loop has a baseline
  to compare against).

#### Per-cluster fold: two new unanimity sets in `_build_observation`
- **Location:** `naked_eye_source.py` `_build_observation` — `member_targets_ownship` and
  `member_firing_visible`, each a set comprehension over `cluster.members`, mirroring the
  pre-existing `member_emitter_kinds` set built the same way one line above.
- **Risk:** none credible. Bounded by cluster size (a handful of members in practice — clusters are
  angular-resolution groupings, not the whole candidate population), not by total candidate count.
  Worst-case measured with a single synthetic 440-member cluster (far larger than any real cluster
  would ever be): **0.05 ms**. Real clusters are tiny fractions of that.
- **Action:** MONITOR, same reasoning as above.

#### `_build_observation`'s provenance fold reordered, not added to
- **Location:** `naked_eye_source.py` `_build_observation`, the three-step priority check
  (`member_targets_ownship == {True}` → `member_firing_visible == {True}` → the pre-existing
  `member_emitter_kinds` branch).
- **Risk:** none. This replaces one `if`/`elif` chain with a slightly longer one over the same
  already-computed, cluster-bounded sets — no new iteration, no new per-poll work beyond the two
  findings above that feed it.
- **Action:** APPROVED, no mitigation needed.

#### `belief/{percept,contacts,events}.py`: new boolean fields threaded through
- **Location:** `Percept.firing_visible`, `Contact.firing_visible`, `Event.firing_visible` — each a
  single `bool` field, written by a closed-mapping membership test
  (`observation.provenance in _VISIBLE_FIRING_PROVENANCE`, a 1-element `frozenset`) or copied
  straight across (`Contact.from_percept`/`record`, `ContactStore.tick`'s event construction).
- **Risk:** none. Same cost shape as the pre-existing `targets_ownship` field these additions
  deliberately mirror — O(1) per contact per tick, no new query, no new allocation beyond one more
  `bool` per dataclass instance.
- **Action:** APPROVED, no mitigation needed.

#### `belief/speech.py`: new `_contact_report_text(..., event_clause="firing")` call for `firing_visible`
- **Location:** `_render_lifecycle_text`, the new `if event.firing_visible:` branch for
  `CONTACT_FIRING_SEEN`.
- **The dispatch's specific question — does this add enrichment cost per firing event (`BL-B49`,
  ~63 ms/contact `semantic_facts_for` + ~6.8 ms/contact terrain-divide)?** Traced the call path:
  `route_event` (unchanged by this diff, `speech.py:3274`) calls
  `describe_contact(store, event.contact_id, now_sim, enrichment=enrichment)` **unconditionally, for
  every lifecycle event kind, before dispatching to `_render_lifecycle_text`** — this was already
  true before this branch existed. The pre-existing `CONTACT_FIRING_SEEN` handling (the bypass-needed
  "Something firing... far" line) already paid the full `describe_contact` enrichment cost and simply
  discarded `result["facts"]` for the parts it didn't use (no classification, no range, no semantic
  fragment, by design — see `debug.md`'s "do not overclaim a `PRESENCE`-tier admission" reasoning).
  **This change does not add a new enrichment call** — it changes how an already-computed,
  already-paid-for `result["facts"]` dict is rendered into text for the specific case where the unit
  was admitted without the bypass (i.e. already carries a real classification tier). `_contact_report_text`
  itself (read in full) is pure string formatting over the `facts` dict with no enrichment/query calls
  inside it — confirmed by reading its body, not assumed.
- **Pre-existing, out of this diff's scope, noted for context:** `route_event` paying the full
  `describe_contact` cost for *every* `CONTACT_FIRING_SEEN` event — including the bypass-needed case
  that only ever speaks "far" and a clock position, never touching classification/semantic/range — is
  itself a standing inefficiency (paying ~63+6.8 ms/contact for a result partially discarded). This
  predates this branch, is unchanged by it, and `CONTACT_FIRING_SEEN` is cooldown-gated
  (`ContactStore._cooldown_elapsed`, `EVENT_COOLDOWN_S`) rather than fired every poll per contact, so
  it is not a per-poll multiplier. Not this review's finding to raise as NOW (not introduced or
  worsened by this batch) — recorded here only so it isn't mistaken for something this diff added, and
  so the next performance pass that looks at `route_event`/`describe_contact` has it in context.
- **Action:** APPROVED for this diff. The pre-existing `describe_contact`-for-every-firing-event cost
  is MONITOR/out-of-scope, unchanged by this batch.

#### Emission frequency: `CONTACT_FIRING_SEEN` is edge/cooldown-gated, not per-poll
- **Location:** `ContactStore.tick`, `firing_event_kind(...)` gated by
  `self._cooldown_elapsed(contact, CONTACT_FIRING_SEEN, now_sim)` — unchanged by this diff.
- **Risk:** none. Confirms the new `firing_visible` field and its speech branch fire only on
  transition + cooldown, not once per poll per firing contact — the hot-path cost analyzed above is
  the true steady-state cost, not a worst case that undercounts frequency.
- **Action:** APPROVED, no mitigation needed.

### Verdict
APPROVED
