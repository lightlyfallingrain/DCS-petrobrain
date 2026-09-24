### Performance Review

Reviewed `feature/watch-reporting` at head `4051534` (branched from `main` at `3409b66`), against
`ContactStore.tick`'s new sixth (range-crossing) and seventh (engagement/LOS) blocks in
`body-layer/src/belief/contacts.py`, `belief/threat.py`, and `belief/callouts.py`'s watched-only
grouping change. This is the once-per-feature performance pass; no prior review assessed runtime
cost.

**Method.** The worktree is based on `main`, which doesn't contain this branch. Read the branch's
code via `git show`/`git diff main..feature/watch-reporting`. Built a timing/call-count harness
(`perf_watch.py`, not committed -- lived in the scratchpad) against the real feature-branch source,
extracted with `git archive feature/watch-reporting -- body-layer` into a scratch tree and run with
`body-layer/.venv/bin/python`, `PYTHONPATH=src:<world-model>/src`. **No world-model `.sqlite` was
available, so real `line_of_sight_clear` I/O was not timed** -- LOS was stubbed with a counting
callable to measure call *count* and the wall time of everything around it. Numbers below are
counts and non-LOS wall time, not real SQLite/DEM timings; the risk argument rests on call count
against a primitive independently known to be `belief/`'s most expensive one, per the task brief.

### Findings

#### LOS is called unconditionally, before the range/altitude gate that would rule it out
- **Location:** `ContactStore.tick`'s seventh block, `body-layer/src/belief/contacts.py` (the
  `if los_clear is None: ... else: raw_clear = _threat_has_los(...)` branch runs before
  `current_engaged = range_ok and alt_ok and los_ok` is assembled).
- **Risk:** `range_ok`/`alt_ok` are computed first but not used to short-circuit the LOS call --
  `_threat_has_los` runs for every watched contact with a resolvable threat envelope, *even when
  the contact is already far outside `envelope.range_max_m` or below the envelope's altitude
  floor*. Confirmed directly: harness case with a contact at 20 km against a 2,408 m max-range AAA
  envelope still produced one LOS call per watched contact (`los_calls=20` for `n_watched=20`,
  `los_calls=200` for `n_watched=200` -- see script output, "OUT-OF-RANGE" cases). Since LOS is the
  one primitive here that touches on-disk SQLite elevation sampling, this is pure waste: most
  watched contacts in a real sortie sit outside their own threat's engagement envelope most of the
  time (that's the point of standoff), so this call fires on nearly every tick for nearly every
  watched contact for no decision-relevant reason.
- **Action:** NOW
- **Mitigation:** Reorder so `los_ok` is only computed (and `_threat_has_los`/`los_clear` only
  called) when `range_ok and alt_ok` is already `True`; default `los_ok = True` otherwise (matches
  the existing fail-open posture -- LOS may only ever *suppress* a warning, never manufacture one,
  so skipping it when already outside range/altitude changes nothing about `current_engaged`, which
  is `False` either way). One-line reorder, no behaviour change, and it is the single highest-value
  fix found in this review -- it turns "every watched-with-envelope contact, every tick" into
  "watched-with-envelope contacts already inside their own envelope, every tick," which is the
  actual population LOS needs to discriminate.

#### The deadband/dwell gate the *event*, not the LOS call itself
- **Location:** `LOS_MASK_CONFIRM_S` (`belief/decay.py`) consumed in `ContactStore.tick`'s seventh
  block via `contact.los_masked_since_sim`.
- **Risk:** Per the plan's own framing (Decision 5a-ii), the dwell exists to stop the *engagement
  state* flapping on a noisy masked sample. It does that correctly. But it sits entirely
  **downstream** of the LOS call -- `_threat_has_los` still runs every tick for every qualifying
  watched contact regardless of dwell state; the dwell only changes whether a masked result is
  allowed to flip `current_engaged` to `False` this tick. So unlike the range-crossing block's own
  deadband (5a-i, which gates a cheap `range_m`/`range_uncertainty_m` computation -- not a concern),
  this dwell provides **no cost reduction at all** on the one call that actually matters for
  budget. This is exactly the distinction the task brief asked to check for, and it is real: dwell
  bounds event *noise*, not LOS *call volume*.
- **Action:** MONITOR (the NOW fix above addresses the actual cost; this finding is here so the
  distinction is on record and isn't mistaken for a mitigation it isn't)
- **Mitigation (if ever needed beyond the NOW fix):** if watched-with-envelope populations grow
  large in practice, LOS re-evaluation itself could be staggered (re-run only every Nth tick per
  contact, or round-robin across contacts within a tick) rather than every watched contact every
  200 ms. Not needed at the scale this project currently targets (see next finding).

#### LOS call volume scales with watched-contact count, and that count is not bounded in code
- **Location:** `ContactStore.tick` seventh block x `belief.attention.AttentionArea` /
  `effective_attention` (`body-layer/src/belief/attention.py`, pre-existing, not changed by this
  branch but newly relevant here).
- **Risk:** LOS calls per tick = (number of currently-watched contacts with a resolvable threat
  envelope) x (1, or 3 if `Contact.last_position_uncertainty_m > 0` -- `_threat_has_los`'s
  perpendicular uncertainty sweep). The harness's synthetic contacts carried zero position
  uncertainty (no `position_uncertainty` supplied), so its counts are the *best* case --
  1x/contact/tick. A real detection's `Observation.position_uncertainty` is populated by the
  perceiving channel's own error model (`perception.source.PositionUncertainty`'s own docstring:
  "a channel's own declared estimate of how wrong its own report might be"), so in practice most
  watched contacts will have `uncertainty_radius_m > 0` and trigger the full 3-sample sweep. Watch
  count itself is not capped anywhere in code -- besides the player's direct `watch`/`priority`
  mark, `belief.attention.effective_attention` also grants watch-equivalent attention to every
  contact inside a live `AttentionArea` (a "watch left"/"watch that treeline" command), which can
  cover an arbitrary number of contacts at once (an enemy column, a village cluster). At this
  project's stated realistic scale (single aircraft, a few hundred world objects, 5 Hz), a plausible
  worst case is a dozen-or-so contacts pulled into one area-watch, each with an AAA/SAM-resolvable
  classification and nonzero uncertainty: ~20-40 LOS calls/tick, ~100-200/sec, all against on-disk
  SQLite -- before the NOW fix above, unconditionally; after it, only for the subset already inside
  their own envelope, which is a much smaller and behaviourally-motivated set.
- **Action:** NOW fix above addresses the call-volume driver directly; the *unbounded watch count*
  itself is a MONITOR, not a NOW, for this branch -- it's an amplifier of an existing mechanism
  (`AttentionArea`), not something this branch introduced, and this project phase has no hard
  real-time budget yet.
- **Mitigation:** none needed now. If a future sortie profile shows area-watch regularly pulling in
  dozens of threat-classified contacts, revisit either a cap on `AttentionArea` membership or the
  LOS-staggering idea above -- flagging for the Architect rather than improvising here, since it
  would change area-watch semantics.

#### `ownship`-derived `GeoPosition` reconstructed per contact instead of once per tick
- **Location:** `ContactStore.tick`, sixth and seventh blocks -- `observer = GeoPosition(x=ownship.x,
  z=ownship.z, alt_m=ownship.alt_m)` appears three times (sixth block's seed and update branches,
  seventh block), each inside the per-contact loop, even though `ownship` is a single `tick`-wide
  argument and this value is identical for every contact evaluated in the same tick.
- **Risk:** A small `GeoPosition` dataclass construction is cheap (harness: ~0.012 ms/contact of
  non-LOS overhead at `n_watched=200`, which includes this alongside `range_m`/
  `range_uncertainty_m`/`envelope_for`; sub-microsecond per call in isolation). Not a credible
  budget risk at any watched-count this project will realistically see. It is, however, exactly the
  "recompute something constant for the tick" pattern the task asked to check for, and it is real.
- **Action:** LATER
- **Mitigation:** hoist a single `observer = GeoPosition(...) if ownship is not None else None`
  above the per-contact loop and reuse it in both blocks. Free correctness-preserving cleanup,
  worth folding into the next touch of this function rather than a dedicated change now.

#### `belief/threat.py`: module load is one-time; `envelope_for` is a dict lookup only at CLASS level
- **Location:** `belief/threat.py` -- `_LOADED`/`_HEADER`/`_ROWS`/`_CLASS_ENVELOPES` are all module
  level `Final` values computed once at import (`_load_header_and_rows()`,
  `_derive_class_envelopes()` both run at import time, not per call). Confirmed by reading the
  module: nothing in `envelope_for` re-parses the JSON or re-derives the rollup.
- **Risk:** none for the `CLASS` path (`_CLASS_ENVELOPES.get(...)`, true dict lookup, O(1)). The
  `TYPE` path (`_match_type_row`) is **not** a dict lookup -- it's a linear scan over `_ROWS` (28
  entries) doing a bidirectional case-insensitive substring test per row, called unconditionally
  once per watched contact per tick (the seventh block computes `envelope_for(contact.
  classification)` before checking anything else). At `n_watched=20` that's ~560 substring/`.lower()`
  operations per tick, ~2,800/sec at 5 Hz -- three orders of magnitude below anything that would
  show up against LOS or the SQLite path, and 28 rows is small enough that "scan" and "lookup" cost
  about the same in practice.
- **Action:** MONITOR (correcting the task brief's framing: it's a scan, not a dict lookup, for
  TYPE-level classifications specifically -- worth recording since a future reader might assume
  O(1) everywhere in this module. Not worth changing at 28 rows.)
- **Mitigation:** if the threat table grows an order of magnitude or `envelope_for` starts being
  called somewhere hotter than once-per-watched-contact-per-tick, memoize `_match_type_row` on
  `classification.value` (it's a pure function of that one string).

#### `callouts.py`'s watched-only kinds forced singleton -- no O(n²) introduced
- **Location:** `group_candidates` and `CalloutScheduler.tick`, `body-layer/src/belief/callouts.py`.
- **Risk:** none found. The three new watched-only kinds (`CONTACT_MOTION_CHANGED`,
  `CONTACT_RANGE_CROSSED`, `CONTACT_ENGAGEMENT_CHANGED`) are diverted to the singleton path
  (`singles.append(event); continue`) **before** `describe_contact` is called inside
  `group_candidates`, exactly the same early-exit shape `CONTACT_CLASSIFICATION_CHANGED` already
  used pre-branch. `CalloutScheduler.tick` does call `describe_contact` once per watched-only event
  itself (to check `attention` before grouping), so those events pay one extra `describe_contact`
  call each versus before this branch -- but that's O(events-this-tick), not O(contacts²), and
  event counts per tick are small (event-driven, not per-contact-per-tick). No quadratic behaviour
  introduced.
- **Action:** none (verified clean).

### Verdict
NEEDS MITIGATION — one item (LOS called before the range/altitude gate that would rule most calls
out) is a real, cheap-to-fix, high-value correction: applying it changes no test-visible behaviour
(the fail-open contract is preserved) while removing the dominant driver of LOS call volume this
branch introduces on the closest thing this project has to a hot path. Once that reorder lands,
this review's other findings are MONITOR/LATER only and the feature is performance-sound at this
project's stated realistic scale.
