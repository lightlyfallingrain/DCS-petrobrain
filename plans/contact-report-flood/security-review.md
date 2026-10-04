## Security Deep Analysis: contact-report-flood

Branch `fix/contact-report-flood`, tip `3884840` (confirmed via `git rev-parse HEAD` before any
other action). Implementation commit: `c3bf79b`.

### Dependency Status
No dependency change. `pyproject.toml` untouched; the fix is pure Python against existing
in-tree modules (`belief.association_over_time`, `belief.callouts`, `belief.contacts`).

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `association_over_time.py:333-363` `contacts_plausibly_same` | New contact-vs-contact spatial/class gate | Conjunction, not disjunction: `class_compatibility(...) == "incompatible"` short-circuits to `False` first, then the Mahalanobis test on the summed, own-elapsed-inflated covariances must also pass. Reuses the unmodified `GATE_SIGMA_THRESHOLD = 3.0` and the already-production-trusted covariance model from `passes_gate` — no new constant invented for this purpose. | None |
| `association_over_time.py` / `classification.py:83-90` | `class_compatibility` returns `"unknown"` (not `"incompatible"`) whenever either side resolves to `None`, and `OP_GROUPSOMETHING` (`DEFAULT_OP_CLASS`) always resolves to `None` | Confirmed: for the ~99.7% of real belief rows classed `OP_GROUPSOMETHING` (per the task brief's cited sortie figure), the class gate never rejects — the spatial Mahalanobis test is the only operative guard for nearly every real suppression decision. This is **not new risk introduced by this feature**: the identical three-valued `class_compatibility` and the identical "unknown passes" posture already govern the production percept-vs-contact merge decision in `ContactStore.ingest` today (`passes_gate`, same function, same threshold). This feature does not loosen that gate; it reuses it for a second purpose. Measured against the real sortie-1004 snapshot (commit message), the result is not "suppress everything spatially close": 17 of 34 foundings still speak, and the four genuinely-simultaneous members of the plan's own six-vehicle cluster are *not* mutually suppressed (same-poll exclusion handles that case separately — see below). | None — see risk note below for the one residual concern worth a user decision |
| `callouts.py` `CONTACT_DETECTED` branch | `other.first_seen_sim < this_contact.first_seen_sim` (strict) | Correctly excludes same-poll peers, which is what prevents mutual suppression of genuinely-simultaneous distinct contacts (verified by the commit's own stated measurement and by the merged test suite). This is the mechanism that keeps the class-gate's permissiveness from being the only thing standing between "normal operation" and "silences a whole real cluster." | None |
| `callouts.py` `CONTACT_DETECTED` branch | `certainty_of(other, now_sim) != "lost"` | Confirmed `other` must still be live (not yet decayed to `lost`) to suppress — matches the merge-echo mechanism's own premise (the abandoned identity is still *technically* tracked, just about to decay). | None |
| `callouts.py` `_render_event` → `tick`'s `_consumed` set | One-shot, permanent suppression per event | Confirmed by reading `tick`'s loop: a suppressed `CONTACT_DETECTED` is added to `_consumed` and never re-scored. The underlying `Contact` record, its classification, and its cardinality belief are untouched — `report`/console tools (`belief/tools.py`) read live store state, not the event log, so a suppressed contact remains fully queryable for the rest of the sortie. This is the documented, accepted cost (plan's "honest cost" section) and matches the module docstring. | None required; see risk note below for the standing-decision framing |
| `association_over_time.py:355-363` | Reads only `Contact.last_class_raw`, `Contact.last_position`, `Contact.last_seen_sim` (both sides) | No ground-truth field, no DCS object id, no world-model query. Confirmed against `belief/percept.py`'s no-omniscience boundary — this function never crosses it; it operates entirely on two already-belief-layer `Contact` records. | None |
| `contacts.py:734-743` `ContactStore.contact()` | New named lookup, `dict.get` | Simple accessor, no new write path, no new externally-reachable input. | None |
| Cost per `CONTACT_DETECTED` event | `any(... for other in store.contacts)` | O(n) scan over the full contact store per founding event, not per tick and not per percept — `CONTACT_DETECTED` events are rare (new-contact foundings only; the real sortie produced 34 across a whole flight) and `n` is the same small, sortie-bounded contact count `BL-B23` already established is not a growth risk. Not quadratic in any meaningful sense for this workload; no separate performance pass is warranted for this change. | None |

### Risk Note (non-blocking, surfaced per standing practice)

**Finding:** Because the class gate passes freely for `OP_GROUPSOMETHING` contacts (the normal
case), suppression correctness for most real contacts rests entirely on the spatial Mahalanobis
test, whose covariance grows with each side's own elapsed time since last observation. A contact
that has sat in `tracked`/`estimated` state for a while (but not yet `lost`) before a new, truly
distinct contact founds nearby could in principle have an inflated-enough covariance to pass the
3-sigma test and suppress a genuine new sighting.

**Location:** `association_over_time.py` `contacts_plausibly_same`, `callouts.py` `CONTACT_DETECTED`
branch.

**Probability:** low — this is the same growth-with-elapsed-time mechanism and the same 3-sigma
threshold already trusted in production for the percept-vs-contact merge decision (`passes_gate`),
not a new or widened tolerance. The `certainty_of(...) != "lost"` condition also bounds how long
`other` can sit un-lost before the decay ladder removes it from consideration.

**Impact:** low-medium — if it fires wrongly, the cost is one missed first-sighting callout for a
real, distinct contact; the contact itself is still founded, tracked, and reachable via `report`,
per the one-shot-suppression finding above. It would not hide the contact from belief state, only
from one spoken line.

**Recommended action:** accept as-is. The mechanism is inherited, measured against real sortie
data in the implementation commit, and the plan already documents the accepted tradeoff (merge-echo
vs. genuine-split ambiguity) at the design level — this residual timing edge case is a further,
smaller instance of the same accepted tradeoff, not a new one.

Options:
  (A) Ignore — document acceptance of this risk (recommended)
  (B) Add to todo.md — fix in a future session
  (C) Fix now — I'll address it before continuing
  (D) Stop — do not proceed until this is resolved

### Verification run (from inside `body-layer/`, fresh venv built against `pyproject.toml`)
- `ruff format --check src tests` — 114 files already formatted
- `ruff check src tests` — all checks passed
- `mypy src` — no issues found, 53 source files
- `pytest tests -q` — **1399 passed, 4 xfailed** (matches this branch's own stated 1389/4 baseline
  plus this feature's own new tests)

### Verdict
APPROVED
