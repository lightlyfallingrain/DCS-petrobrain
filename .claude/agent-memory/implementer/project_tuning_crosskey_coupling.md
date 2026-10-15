---
name: tuning-crosskey-coupling
description: body-layer's import-time asserts between gaze/decay constants were a hazard when those same constants became independently tunable (X-T26) — closed in the review fix pass, 2026-10-15
metadata:
  type: project
---

**Update (2026-10-15 fix pass, `plans/configurable-constants/review.md` Required Fix 1): this gap
is closed, not just documented.** The original Stage 1-2 implementation left it as a documented
residual (below); the reviewer reproduced the crash with two individually in-bounds overrides
(`FOCUS_DWELL_S=5.0`, `POSITION_HALF_LIFE_S=20.0`) and required a real fix, which landed in
`tuning.py` itself as `_check_scan_decay_coupling` — not escalated to Architect, because "one
targeted check for this one known coupling" turned out to fit inside the loader without a general
cross-key framework.

**The fix cannot live where the invariant conceptually lives (`belief.decay`'s own assert) — it
has to live in `tuning.py`'s `real`/`sequence`, triggered for the specific coupled keys, before
`perception.gaze`'s own accessor calls return.** This is the load-bearing design fact, easy to miss
on a first pass: `perception.gaze` resolves *before* `belief.decay` is even imported (`belief.decay`
imports `FOCUS_DWELL_S`/`SCAN_CYCLE_PERIOD_S` from it), and other modules
(`belief.optic_policy`, `perception.naked_eye_source`, `logger.py`) import `SCAN_CYCLE_PERIOD_S`
directly from `perception.gaze`, not through `belief.decay`. A correction applied only inside
`belief.decay` (e.g. recomputing a local, corrected `OBSERVED_WINDOW_S`) would leave those other
modules holding the un-corrected, overridden value — silently reintroducing the exact bug the
lower-bound assert exists to prevent, just less loudly. The check must intervene at the point the
coupled key's own `Final` constant is about to be bound, which means peeking at the *other* coupled
keys' raw override values directly by dotted key (no import of the module that declares them
needed — the same technique `validate_against_defaults()` already uses against
`config/defaults.toml`), and using `config/defaults.toml`'s own committed values for each key's
code default rather than a second hardcoded copy (which could drift from the real defaults; the
registry can't, because its own staleness test already guards it).

**When a violation is found, reject every one of the coupled keys the override file actually sets,
not a chosen "culprit."** This is provably sufficient and doesn't need per-case reasoning about
which key is "the cause": any coupled key the file never mentions was already resolving to its own
code default, so rejecting every present key drives the whole triplet to exactly the code-default
combination, which the kept hard `assert` (now a code-defaults-only backstop, not a reachable
pilot-override path) already guarantees is safe.

**Original finding, preserved for context:** `body-layer/src/belief/decay.py` asserts
`OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` at **module import time** (`OBSERVED_WINDOW_S` =
`perception.gaze.SCAN_CYCLE_PERIOD_S` = `len(SCAN_PLAN) * FOCUS_DWELL_S`). Each accessor only
validates its own key against its own declared `lo`/`hi` bounds — nothing validates the
*combination* — so tuning more than one of `POSITION_HALF_LIFE_S`/`FOCUS_DWELL_S`/`SCAN_PLAN` at
once could trip the assertion and crash the process at import, a disguised "refuse to start" in a
feature whose whole point (Decision 4 REVISED) was never to do that.

**How to apply, going forward:** before converting a constant to `tuning.*`, grep its defining
module for `assert` statements that reference it (or a constant derived from it) at module scope —
not just inside functions. If found, and the coupling involves constants declared in *different*
modules with an import-order relationship between them (as here), the fix belongs in `tuning.py`
itself (a key-name-based pre-check, as above), not in whichever module's assert happens to state
the invariant — that module may not be the first of the coupled keys to resolve.

See also [[tuning-generator-comment-extraction]] for the sibling lesson from the same feature
about generating descriptions from hand-wrapped `#:` prose.
