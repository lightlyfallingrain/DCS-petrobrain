## Security Deep Analysis: configurable-constants (X-T26)

Reviewed at tip `2f196acdd77990d937e0eb4cdc072c96b10bf456` (`feature/configurable-constants`),
worktree created directly at that sha (no merge needed — base was already an ancestor-incompatible
sibling of local `main`, per dispatch instructions I did not touch the root). Read: the plan, both
review passes, the implementation writeup, `todo/todo/X-T26.md`, `body-layer/src/tuning.py` in
full, `body-layer/config/defaults.toml`, all five converted source files (`attack_run.py`,
`visibility.py`, `callouts.py`, `gaze.py`, `decay.py`, `estimation.py`), `logger.py`'s CLI wiring,
and `clustering.py`/`group_salience.py` for the cross-key question below. `.venv` was not present
in this worktree (gitignored, not copied), so I did not re-run the test suite myself — both review
passes already ran it, by name, against this exact tip, and I have no reason to doubt that; my own
verification here is by reading, not by re-executing, except where noted.

### Dependency Status

No dependency change. The only `pyproject.toml` diff is adding `"tuning"` to isort's
`known-first-party` list — confirmed by diffing against the pre-feature base. `tomllib` is stdlib
(3.11+), as the plan states. Nothing to search for CVEs against.

### The central question: do the declared bounds actually prevent an invariant-violating config?

**For the time-based keys, yes.** `IDENTITY_HALF_LIFE_S` (`lo=60, hi=1800`), `POSITION_HALF_LIFE_S`
(`lo=20, hi=120`), `LOST_THRESHOLD_S` (`lo=30, hi=600`) are all bounded on both ends — none can be
set to "never decays." `BEARING_SIGMA_DEG` (`lo=0.1, hi=14.0`) cannot be set to `0.0` (perfect
bearing), and `estimation.py`'s own comment states the `lo` bound is deliberately placed "above the
optical resolution floor, `perception.clustering.RESOLUTION_ANGULAR_RADIUS_RAD`" — I checked that
claim against the actual numbers (`RESOLUTION_ANGULAR_RADIUS_RAD = 0.00128 rad ≈ 0.073°`, well
below the declared `lo=0.1°`) and it holds. These four keys' bounds are principled, not just
"not obviously absurd."

**For the three visibility tier radii, no — and this is the finding I'd want you to see before
merge, even though I'm not blocking on it.**

`LOWRES_ANGULAR_RADIUS_RAD` (`lo=0.0005, hi=0.01`, default `0.003`, measured), `MEDRES_ANGULAR_
RADIUS_RAD` (`lo=0.001, hi=0.05`, default `0.014`), `HIRES_ANGULAR_RADIUS_RAD` (`lo=0.002, hi=0.08`,
default `0.028`) are the detection/classification/type-ID thresholds. Detection range is **inverse**
to the threshold (`visibility.py`'s own formula: `presence = presence_size_m / LOWRES_ANGULAR_
RADIUS_RAD * optic.presence_range_mult`, same shape for the other two tiers) — a *smaller* angular
radius means the contact can be *farther away* and still cross the tier. So the dangerous direction
is the `lo` bound, not the `hi` bound, and the declared `lo`s permit a large move in exactly that
direction:

- `LOWRES`: `lo=0.0005` is **6x smaller** than the measured default `0.003`. The code's own
  calibration comment says the default puts the presence boundary at ~9333 m for a 7 m vehicle; at
  `lo`, that becomes ~56 km.
- `MEDRES`: `lo=0.001` is **14x smaller** than the measured default `0.014`. Default classification
  range ~1990 m (observed boundary) → ~27.9 km at `lo`.
- `HIRES`: `lo=0.002` is **14x smaller** than the measured default `0.028`. Default type-ID range
  ~1000 m (observed boundary) → ~14 km at `lo`.

All three are within their own declared bounds, so none of this is caught, warned about beyond the
ordinary "applied" line, or distinguishable in the startup block from any other legitimate tuning
change. A pilot setting any of these three keys to their permitted floor has, with a config edit
and no code change, rebuilt detection/classification/type-identification ranges that are an order of
magnitude past anything the project's own screenshot calibration measured — materially the
hawk-eyed-Petrovich defect this project exists to remove (root `CLAUDE.md`'s own framing, and
`project_ed_petrovich_failures` in agent memory).

**This is also a real, undefended cross-key coupling, structurally the same shape as the review's
Required Fix 1, just on the perception side rather than belief:**
`perception/clustering.py`'s own docstring states and relies on `RESOLUTION_ANGULAR_RADIUS_RAD <=
LOWRES_ANGULAR_RADIUS_RAD` as part of a stated correctness proof for its group-admission
self-consistency check (`_separable`'s `above_floor` term, "(A), checked against
RESOLUTION_ANGULAR_RADIUS_RAD, can never be the binding constraint... kept anyway as a one-line
self-consistency check"). `RESOLUTION_ANGULAR_RADIUS_RAD` is `0.00128`, fixed (correctly excluded
from tuning — it fails the plan's own inclusion test, a derived/rounded constant). `LOWRES`'s
declared `lo` (`0.0005`) and `MEDRES`'s declared `lo` (`0.001`) are both **below** that floor, so a
pilot setting either to anywhere in its declared `[lo, default)` range can violate the stated
invariant. Unlike the decay/gaze coupling, there is **no runtime guard at all** here — no `assert`,
no `_check_*_coupling`, nothing in `tuning.py`. I traced what actually happens when the invariant
breaks (`_separable` in `clustering.py`): it does not crash — `above_floor` is still just computed
and used in the real merge decision — it silently invalidates the "can never be the binding
constraint" premise the docstring's proof rests on, meaning (A) could now actually decide whether
two genuinely-separable contacts get merged into one cluster, in a way the module's own comments
say was never supposed to be reachable. I did not chase this through to a concrete wrong-output
example (that would be Debugger/Reviewer territory on the clustering module itself, not a
security defect), but the premise being silently false under a config this feature explicitly makes
reachable is exactly the class of thing the review's "parallel-treatment grep check" caught for
decay/gaze and did not catch here, because nobody asked clustering.py the same question.

**Why this is Recommended, not Required — the line I'm drawing and why:**
- It does not crash the process (unlike the decay/gaze case before the fix pass) — there is no
  disguised refuse-to-start here, so it does not contradict Decision 4 REVISED's forcing concern.
- The project is single-player, LAN-only, under active development; "the pilot can set his own
  detection range to 56 km" is, as root `CLAUDE.md`'s own framing says of deliberate cheating,
  his business.
- But the dispatch instructions were explicit about distinguishing *deliberate cheat* from *tunes a
  number without realising what it governs*, and this is squarely the second case: the generated
  description for each of these three keys is one sentence identifying the tier ("Presence tier
  (\"something is there\")...") plus `status: measured | range: 0.0005 .. 0.01`. Nothing in the
  rendered file says the relationship is inverse, nothing says how large a range change the bound
  permits, and nothing says a value below 0.00128 breaks a documented invariant elsewhere in the
  codebase. `BEARING_SIGMA_DEG`'s own bound is *safe by construction* regardless of description
  quality; these three are not — the description is the only thing standing between a pilot moving a
  number the "safe" direction (smaller usually reads as "tighter, more conservative" to an unfamiliar
  reader) and an order-of-magnitude range change.

**Finding:** `LOWRES_ANGULAR_RADIUS_RAD`/`MEDRES_ANGULAR_RADIUS_RAD`'s declared `lo` bounds permit
values below the fixed `RESOLUTION_ANGULAR_RADIUS_RAD` optical-resolution floor, and all three tier
radii's `lo` bounds permit detection/classification/type-ID ranges 6-14x past the measured
calibration, with the generated description giving no hint of either consequence.
**Location:** `body-layer/src/perception/visibility.py:300-326` (the three `tuning.real(...)` calls);
the undefended invariant is `body-layer/src/perception/clustering.py`'s module docstring and
`_separable`.
**Probability:** medium — these three keys are in the curated 15 specifically because they're the
set "a sortie actually revises" (plan, Stage 2), and the inverse relationship between threshold and
range is exactly the kind of thing someone tuning by feel gets backwards on a first attempt.
**Impact:** medium — within this project's own stated goal (not an attacker's), this directly
recreates the central defect root `CLAUDE.md` names as the reason the project exists; it is the
pilot's own sortie that degrades, not anyone else's.
**Recommended action:** tighten `LOWRES`/`MEDRES`'s `lo` to at least `RESOLUTION_ANGULAR_RADIUS_RAD`
(0.00128), add one sentence to each of the three tier radii's `#:` block stating the inverse
relationship and the rough range this bound implies (the same way `BEARING_SIGMA_DEG`'s own comment
already explains its `lo` bound), and consider narrowing the `lo` headroom generally (6-14x past a
*measured* value reads as a much looser "sanity" bound than the half-life keys get). Whether to add
a `_check_*_coupling`-style guard for the `RESOLUTION_ANGULAR_RADIUS_RAD` invariant, the same shape
as the review's Required Fix 1, is a judgment call on how likely a pilot is to actually hit the
narrow `clustering.py` behavior change versus just the (already-concerning) range expansion itself.

Options:
  (A) Ignore — document acceptance of risk (the pilot's own sortie, single-player)
  (B) Add to todo/backlog as a cross-cutting follow-up (tighten the three `lo` bounds + descriptions,
      maybe the clustering coupling guard) — cheap, narrow, doesn't block this merge
  (C) Fix now — re-enter Implementer → Reviewer loop before DoD
  (D) Stop — do not proceed until resolved

My own recommendation is (B): this is exactly the shape of thing Stage 3 will also need to get right
for the ~80 remaining keys, so it's worth fixing once, deliberately, rather than inside this fix
pass's momentum — and nothing here crashes or silently misreports, so there's no forcing reason to
block the merge that's otherwise ready.

### The grep-fence question

No new route around it. `tuning.py` resolves dotted keys into module-level float/int/sequence/table
constants from a pilot-authored local TOML file — it never reads or touches `Percept.
relative_direction` or any other truth-derived field, and nothing in this feature's diff adds a
module to the fenced set or widens who may import `attack_run.py`'s truth fields. The fence governs
*where truth-derived data may flow at runtime*; this feature only affects *which literal a `Final`
constant binds to at import*, a different and non-overlapping axis. Clean.

### The ordinary surface

- **`tomllib` parsing of a pilot-named local file**: `_build_state()` catches `OSError` (covers
  missing file, permission denied, a directory given instead of a file — `IsADirectoryError` is an
  `OSError` subclass) and `tomllib.TOMLDecodeError` separately, routing both to the already-reviewed
  non-fatal paths. No partially-applied configuration is possible: `_build_state()` either returns a
  fully-loaded `raw`/`flat` state or an empty one, there is no partial-parse branch.
- **One genuine, low-severity gap I did not see flagged elsewhere**: `_flatten()` recurses once per
  TOML table-nesting level with no depth limit, and `_build_state()`'s `except` clauses do not catch
  `RecursionError`. A pathologically deeply-nested TOML file (hundreds of nested `[a.b.c...]` tables)
  would raise an uncaught `RecursionError` instead of degrading per Decision 4 REVISED — a disguised
  refuse-to-start, the same category of thing Required Fix 1 fixed for the decay/gaze coupling.
  **This is informational, not a required fix**: the file is self-authored by the pilot (the env var
  he set points at a file he wrote), nesting a TOML file hundreds of levels deep by hand is not a
  realistic accident, and there is no untrusted-input path here — stated plainly per the scoping
  note, this would matter if the tuning file ever became something other than hand-authored
  (e.g. shared/downloaded configs), which is not this project's model today.
- **The env var naming something that is not a plain file**: a directory → `OSError` → `missing`,
  handled. A device node or FIFO → likely `OSError` or blocks on read depending on the device;
  blocking is a possible hang, but again self-inflicted and not a crash or security boundary issue —
  informational only, same reasoning as above.
- **`--print-tuning` output**: echoes the resolved values and the path the pilot himself put in his
  own environment variable, to his own terminal, before anything flies (`logger.py:2518-2525`).
  No file *contents* are echoed, only resolved scalar/sequence values and the path string. Nothing
  leaked that the pilot didn't already have.
- **Rejected value can never reach a constant**: confirmed by reading every rejection branch in
  `real`/`whole`/`sequence`/`table` — each returns `default`, never `value` or `raw_value`, on every
  rejection path (`wrong type`, `out of range`, `unrecognised table entry`, `invariant violation`,
  `unknown key`). No clamping anywhere. This matches both review passes' own verification by
  mutation; I verified it by reading rather than re-running, since the review already exercised this
  by mutation testing and I have no reason to doubt a result obtained that way.
- **No new dependency**: confirmed above.

### Verdict

**APPROVED**, with one Recommended finding (the visibility-tier `lo` bounds / undefended
`RESOLUTION_ANGULAR_RADIUS_RAD` coupling, above) and informational notes (the `RecursionError` gap,
device-node reads). Nothing here crashes, leaks, or opens a new path around the project's fences;
the one real design gap is a self-inflicted, single-player-scoped "the pilot can out-tune the
calibration" risk that the generated descriptions don't adequately warn against, which is a decision
for the user (options above), not a defect that should hold up this merge.

### Required Fixes

None.
