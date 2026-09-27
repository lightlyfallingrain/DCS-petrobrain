### Performance Review

Reviewed `fix/sortie-2026-09-26` (`f4a4991`, code commit `195085f` + docstring fix `63684c4`),
run after DoD (which had already PASSED) to close the gap left by skipping this pass mid-feature —
per root `CLAUDE.md`'s "performance-reviewer and security run once per whole feature, immediately
before DoD." Read `plan.md`, `implementation.md`, `review.md`, `decisions.md`, and `body-layer/
CLAUDE.md`. Diffed `git diff main...f4a4991 -- body-layer/src`.

Scope: `body-layer`'s per-poll belief path, the closest thing this project has to a hot path —
default poll cadence is **1 Hz** (`logger.py`'s `_DEFAULT_POLL_INTERVAL_S = 1.0`), not the tighter
budget Petrobrain Runtime will eventually need. Root `CLAUDE.md` is explicit that no hard
real-time budget applies in this phase. That context matters for every finding below: at this
cadence, sub-millisecond additions are not credible risks.

### What changed on the hot path

1. `ContactStore.tick`'s fifth (`CONTACT_MOTION_CHANGED`) and sixth (`CONTACT_RANGE_CROSSED`)
   blocks now gate emission on `_callout_may_speak(contact, ownship, now_sim)`, computed once per
   contact per tick whenever `ownship is not None` — unconditionally, not gated on watch/attention.
2. `Contact.last_observable_sim` is written every tick for every contact the gate runs against
   (confirmed by reading `tick()`, matching `review.md`'s own finding).
3. `optic_policy.decide()`'s `SCANNING` branch runs `is_worth_a_look` over `targets` (a list
   comprehension) and, on committing or starting a look, copies `attempted_at_range_m`,
   `attempted_at_time_sim`, and (new) `pending_attempted_at_range_m` via `dict(...)` — one more
   copy than before this change, all unconditional per `decide()` call.
4. Both `OpticState`'s three per-contact dict fields and `Contact`'s fields (this and prior work)
   are never pruned — contacts accumulate for the life of the process, confirmed by Security's
   prior review and unchanged here.

### Measurements

I did not rely on reading the code alone — two isolated microbenchmarks, run from
`body-layer/.venv` against this branch's actual source (`PYTHONPATH=src:../world-model/src`):

**`_callout_may_speak`'s actual primitive cost** (`body_relative_direction` + `cockpit_mask.
is_visible`, the two calls the gate makes per contact): 20,000 simulated ticks × 55 contacts —

- **1.44 us per contact-call**
- **0.079 ms per tick at 55 contacts** (i.e. all of Fix A's added work, for a full sortie's worth
  of contacts, in one tick) — **0.008% of the 1000 ms poll budget**.

**`optic_policy.decide()`'s SCANNING branch** (`is_worth_a_look` comprehension + the `dict(...)`
copies), at three contact-set sizes to see how the never-pruned maps degrade:

| contacts | ms/call |
|---|---|
| 55 (this sortie's actual max) | 0.084 |
| 300 (a long multi-sortie session) | 0.447 |
| 1000 (well beyond anything a real sortie or session produces) | 1.460 |

Linear in contact count, as expected from the dict-copy shape, and even at 1000 unpruned contacts
it is 0.15% of the 1 Hz budget. `body-layer/CLAUDE.md`'s own belief-truth log shows the largest
recorded run at 52 contacts; the bridge log shows ~55 units/tick — this sortie is nowhere near the
scale where this would register.

I also ran `ruff format --check`, `ruff check`, `mypy src`, and `pytest` directly rather than
trusting the implementer's/reviewer's reported numbers — see Verification below.

**Not measured, and flagged rather than estimated:** `ContactStore.ingest`'s per-observation
association/continuity matching, run ahead of `tick()` on the same poll. A full-pipeline benchmark
(`ingest` + `tick`, 55 contacts, 500 simulated ticks) did not complete in several minutes and was
killed rather than left to finish — that cost lives entirely in `ingest`'s pre-existing association
logic, which this diff does not touch, so I did not chase it further under this review's scope. It
is worth a dedicated look in a future performance pass (see OBSERVATIONS), since it is the actual
expensive neighbour of the code this diff adds to, not a finding against this branch.

### Findings

#### Fix A's observability gate runs unconditionally per contact per tick
- **Location:** `belief/contacts.py::_callout_may_speak`, called from `ContactStore.tick`'s fifth
  and sixth blocks, gated only on `ownship is not None` (every production call site), not on watch
  or attention state.
- **Risk:** none credible at this scale. Measured at 1.44 us/contact; 55 contacts costs 0.08 ms
  against a 1000 ms poll budget. The concern shape (recompute cockpit-mask geometry for every
  contact, every tick, forever) is the right thing to check — it is just cheap here because the
  primitive is a vector rotation plus a lookup over a handful of table breakpoints (`is_visible`
  does one `abs()`, one loop over `OcclusionMask.breakpoints` — a handful of entries per station —
  and a comparison; no allocation beyond the returned `BodyRelativeDirection` dataclass instance).
- **Action:** MONITOR. If a future higher-frequency runtime phase (Petrobrain Runtime, once its own
  hard budget exists) inherits this same unconditional-per-tick shape, re-measure then — 1 Hz makes
  it a non-issue, a 20+ Hz loop would not automatically, though even then 55×1.44us ≈ 0.08ms stays
  trivial against any plausible per-tick budget. No mitigation needed now.

#### `optic_policy.decide()`'s per-call dict copies (`attempted_at_range_m`,
`attempted_at_time_sim`, `pending_attempted_at_range_m`)
- **Location:** `decide()`'s `GLASSING`-commit branch and `SCANNING`-chosen branch; `OpticState`'s
  three maps are never pruned (Security's prior finding, unchanged by this work).
- **Risk:** none credible at realistic scale. Measured 0.084 ms/call at 55 contacts, growing
  linearly to 1.46 ms/call at a synthetic 1000-contact set — the latter is roughly 20x the largest
  contact count this project has actually recorded in a sortie. Even at that exaggerated size, it
  is 0.15% of the 1 Hz poll budget.
- **Action:** MONITOR. The unbounded-growth pattern is real and already accepted for memory reasons
  elsewhere in the codebase; it is not, on its own, a performance problem until contact counts are
  an order of magnitude beyond anything single-player DCS sorties produce. Revisit only if session
  length or contact-count assumptions change materially (e.g. a very long campaign-style session
  that never restarts the process), not as part of this feature.

#### `logger.py`'s `already_on_target` check and `crew_console.py`'s reset
- **Location:** `_run_crew_text_poll_loop`'s "any command lowers binoculars" glue block;
  `CrewConsole.handle_command`'s reset of `last_command_target_contact_id`.
- **Risk:** none. Both are O(1) attribute reads/comparisons inside an already-per-poll block that
  previously did an unconditional `lower_binoculars` call — this is strictly less work on the
  common path (nothing to lower) and adds three attribute comparisons on the command-dispatch path.
- **Action:** none needed.

### Not part of this diff, flagged for a future pass

`ContactStore.ingest`'s association/continuity matching (unrelated to Fixes A/B/C) is the one place
in this poll's pipeline I could not rule out as expensive at scale within this review's time budget
— my attempt to microbenchmark the full `ingest`+`tick` pipeline at 55 contacts over 500 simulated
ticks did not finish in several minutes, which is itself a data point worth taking seriously even
though I did not isolate the cause. This is pre-existing code this branch does not touch, so it is
out of scope for a performance review of *this* feature, but it is a stronger candidate for the
project's next dedicated performance pass than anything in this diff. Recommend the next
performance-reviewer invocation (or a debugger pass, if it turns out to be a correctness-adjacent
stall rather than pure asymptotic cost) start there rather than re-checking this branch's own
additions.

### Verdict
APPROVED

Nothing in this diff registers against the stated non-negotiables (whole-theatre pipeline scale
does not apply here; no new per-request allocation of consequence; no new blocking I/O; no new
redundant querying) at the 1 Hz cadence and 52-55 contact scale this sortie and this project's
current phase actually produce. Both dict-copy and gate-computation costs were measured, not
estimated, and both round to noise against the poll budget. Nothing here blocks merge.
