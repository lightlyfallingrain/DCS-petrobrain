### Performance Review

**Scope: the whole of BL-12** (Stages 0, 0a, 0b, 1, 2a, 2b, 3, 3.5, 4 — Stage 5 skipped, Stage 6
deferred per amendment A10), on `feature/bl12-group-contact-identity` at `33da5b4`. Reviewed
against the budget established by `plans/bl11-tick-cost/performance-review.md`: **12.6 ms median
work per poll, 1.000 s realised period, 2.0 % of polls overrunning 1.0 s**, with every overrun a
single `describe_position` spike (84.6 ms/call in situ) unrelated to body-layer.

**Verification state**: 1697 passed / 4 xfailed, matching the stated baseline; no change made to
source. `ruff format`/`check` and `mypy --strict` not re-run since no code changed (read-only
review) — the suite result above is what the harness scripts below were measured against.

**Methodology.** A real-pipeline probe
(`plans/group-contact-identity/scratchpad/probe_bl12_perf.py`, run via
`body-layer/.venv/bin/python` with cwd `body-layer`) builds real `Contact`/`GroupStore` objects —
not a mock — and times `_cluster_contacts`, full `GroupStore.reconcile`, and
`GroupTraceLogWriter.write` directly. **Can-this-harness-fail check, run first**: the shipped
`_cluster_contacts` (full per-pair cost: profile resolution, backstop selection, admission-gate
lookup) was timed against a stripped-down double loop with no profile resolution at 300
contacts/30 clusters — 25.69 ms vs. 6.74 ms. The two are not doing the same work (this is a
sensitivity check that the harness resolves real cost differences, not an A/B of one change), but
it confirms the harness is not reporting a timer that reads the same number regardless of what
runs. All numbers below are measured, not reasoned.

**Scale used.** BL-11's own measured scale: 440 naked-eye candidate objects, in-bubble candidates
median 232. That is *before* clustering into `Contact`s — the belief-store `Contact` count
`GroupStore.reconcile` actually iterates is far smaller (BL-B49 measured 52 contacts as the
in-flight scale for a different path). The probe below uses 12/4, 30/8, and 60/15
(contacts/clusters) as typical/busy/2×-busy sortie ticks, plus 300/30 as a stress scale well past
anything a realistic DCS mission produces (DCS itself cannot host populations near that density,
per the plan's own "DCS just cannot handle so many units" premise) — included only to show the
O(n²) term does not become a problem even far past real scale.

---

### Findings

#### `_cluster_contacts`'s admission-gate addition (Stage 3.5)

- **Location:** `body-layer/src/belief/groups.py:673-843`, specifically the `roster_of` flattening
  (`:786-791`) and the per-edge lookup (`:827-831`).
- **Measured:** confirmed the plan's own performance note was honoured — `prior_rosters` is
  flattened into `dict[str, frozenset[str]]` **once**, before the O(n²) edge loop, not scanned
  with `any(...)` per pair. The per-edge admission test is one dict `.get()` plus one float add,
  exactly as specified.
- **Cost at scale:** full `reconcile()` (which includes `_cluster_contacts`) — 0.100 ms median at
  a typical 12-contact/4-cluster tick, 0.286 ms at 30/8, 1.337 ms at 60/15. `_cluster_contacts`
  alone is 25.69 ms only at the 300-contact/30-cluster stress scale, ~24× the realistic upper
  bound this project has measured anywhere in this module's domain.
- **Risk:** none at realistic scale. The O(n²) shape is pre-existing (noted in the function's own
  docstring before BL-12) and Stage 3.5 adds O(1) work per edge, which cannot change the growth
  curve's order.
- **Action:** NO CHANGE.

#### `reconcile`'s phase 1 (overlap match) and the remembered-group candidate set

- **Location:** `groups.py:1355-1377` (phase 1), `:1481-1521` (phase 4, expire).
- **Checked:** phase 1 and phase 2 iterate `persisted` (`remembered_groups`, i.e. matched-or-not),
  not only currently-observed groups — a real widening from pre-Stage-1 behaviour. The thing that
  bounds it is the expire phase: a group not reconciled this call is dropped once
  `now_sim - group.last_observed_sim > GROUP_REIDENTIFY_WINDOW_S` (`decay.py:263`,
  `2.0 * POSITION_HALF_LIFE_S` = **60 s**). So `remembered_groups`'s size is bounded by "groups
  formed or retained within the last 60 s," not by sortie length — confirmed by reading the expire
  branch, not assumed. **No unbounded-growth defect found.**
- **Cost:** phase 1/2 are O(clusters × remembered-groups), both counts small (single digits to low
  tens in any realistic scene) — folded into the full-`reconcile` numbers above, which stay sub-
  millisecond at realistic scale.
- **Action:** NO CHANGE. MONITOR only in the sense any O(n·m) term is: if a sortie's scene ever
  holds dozens of simultaneous groups, re-measure — nothing today suggests that will happen.

#### Per-reconcile aggregate recomputation (`composition`, `air_defence_composition`, `installation`, `extent_m`, `centroid_uncertainty_m`)

- **Location:** `_cluster_properties` (`groups.py:1049-1061`), called once per observed cluster per
  `reconcile` (`:1348-1351`), riding `_profile_for_contact` → `object_model.profile_for`'s
  `functools.cache`.
- **Measured:** folded into the full-`reconcile` timings above — 0.1-1.3 ms median across
  realistic-to-stress scale, for *all* per-cluster aggregates combined, not just one. `_extent_of`
  is the one O(members²) term inside this group (pairwise distance over a cluster's own members,
  not the whole contact set), and cluster sizes are small (a handful of members), so this is
  negligible in absolute terms even before the cache is counted.
- **Action:** NO CHANGE. As cheap in situ as in principle, confirmed rather than assumed.

#### Stage 4 heading smoothing (`_update_heading`)

- **Location:** `groups.py:980-1027`.
- **Checked by reading, not separately timed** (not worth a dedicated probe): at most
  `GROUP_HEADING_SMOOTHING_WINDOW` (5) trig calls (`sin`/`cos`/`atan2`) per group per reconcile,
  window-bounded by construction (`history[-GROUP_HEADING_SMOOTHING_WINDOW:]`), never a function of
  contact or group count beyond "once per group." This cannot be a hotspot at any scale this
  module will see — the bound is structural, not empirical.
- **Action:** NO CHANGE.

#### Stage 2's `plausible_speed_mps` on the gate path

- **Location:** `position_belief.py:193-233`; called from `association_over_time.py:350`
  (per-record gate check) and `groups.py:1081`/`:1157` (`group_matches` test 5).
- **Checked:** it is `_PLAUSIBLE_SPEED_MPS.get(op_class, default)` — a single dict lookup, no
  loop, no I/O. It replaced a flat constant (`GATE_GROWTH_RATE_MPS`) with a lookup of the same
  asymptotic cost. Being "now called on the gate path via `Contact.record`" is a correctness
  change (per-class speed instead of one flat figure), not a cost change — same call shape, same
  O(1).
- **Action:** NO CHANGE.

#### `group_trace_log.GroupTraceLogWriter` — the off-path is a true no-op; the on-path is not quite the "handful of rows" the module docstring claims

- **Location:** `body-layer/src/group_trace_log.py`; call site `groups.py:1468-1479` (every
  cluster, every `reconcile` call) and `:1510-1521` (expire only).
- **Default-off, confirmed a true no-op**: `reconcile(..., trace_sink=None)` vs. no `trace_sink`
  argument at all measured identically (0.100 ms median either way) — the `if trace_sink is not
  None:` guard at the very end of `reconcile` means no `GroupTraceLogWriter` is even constructed
  unless `--group-trace` is passed. Correct as documented.
- **On-path finding, worth recording precisely because the module's own docstring states the
  opposite:** `GroupTraceLogWriter`'s docstring says *"a phase-2 property match or an expiry is a
  handful of rows per sortie at most... not hundreds per poll"*, used to justify an **unbuffered**
  writer (open + write + close on every call, no batching). Reading `reconcile`'s trace-record
  loop (`:1468` onward) shows this is **not what happens**: the trace record is appended for
  **every cluster, every reconcile call**, tagged `overlap`/`property`/`found` — not filtered to
  the rare phase-2/expire cases the docstring's rationale describes. A tick with 4 ordinary,
  already-stable groups writes 4 trace rows every poll, not "a handful per sortie."
  - **Measured cost:** a single `GroupTraceLogWriter.write` call (open+write+close,
    `tempfile`-backed) is 0.034 ms median, 0.157 ms max. At 1 Hz with 4/8/15 active clusters —
    the same realistic-to-busy range used above — that is ~0.14/0.27/0.51 ms/poll of synchronous
    file I/O added to the poll thread. Measured directly on a full `reconcile` call too: 0.100 ms
    without a sink vs. 0.266 ms with one at 4 clusters — a 0.166 ms delta, consistent with the
    per-write figure times 4.
  - **Verdict on the number itself: not a budget risk.** Even the busy-tick estimate (~0.5 ms) is
    ~4% of the 12.6 ms baseline and nowhere near the 1.0 s budget — this is not what the "action"
    rows below are about.
  - **What is worth fixing is the docstring's premise, because it decided the design** (unbuffered,
    no batching) **on a frequency claim that is false for the common case.** The design is not
    wrong at today's group counts, but the stated reason for choosing it does not hold, and this is
    exactly the kind of mismatch that stops being free once group counts or poll rate change —
    the file is reopened from scratch on every single row rather than once per poll, which is the
    cheap fix available if it ever needs one.
- **Action:** MONITOR, with a documentation correction recommended now (cheap, no behaviour
  change) — see Change Requests below. Not a NOW code change: the measured cost at any realistic
  scale is immaterial, and the risk is to a future reader's assumption, not to this poll's budget.

#### Everything else named in the dispatch prompt, disposed of without a separate finding

- **Stage 1's displacement/property-match predicate (`group_matches`)**: six simple comparisons
  per candidate, no loop over contacts, folded into the phase-1/2 cost already measured above.
- **BL-B40 (the declined 1.6× remainder) and BL-B49 (the `describe_position`/enrichment cost)**:
  both pre-existing, both already triaged by the BL-11 pass and explicitly out of BL-12's own
  scope per amendment A5/A10 (BL-12 adds no new `describe_position` caller — Stage 5 was skipped
  in full, including the cheap anisotropic half). Nothing in this diff changes either number.

---

### Scaling behaviour summary

| term | shape | measured | realistic-scale verdict |
|---|---|---|---|
| `_cluster_contacts` (incl. Stage 3.5's admission gate) | O(n²) in tracked contacts, pre-existing shape | 0.05-1.15 ms, 12-60 contacts; 25.7 ms at a 300-contact stress scale ~24× realistic | fine, admission gate adds O(1)/edge |
| `reconcile` phases 1/2 | O(clusters × remembered-groups) | folded into full-reconcile: 0.1-1.3 ms | fine; group counts stay small, bounded by 60 s window |
| per-cluster aggregates (Stage 1/4 fields) | O(cluster size), cached profile lookups | folded into full-reconcile | fine |
| Stage 4 heading smoothing | O(1), window-bounded at 5 | not separately measured, structurally bounded | fine |
| `GroupTraceLogWriter` (on) | O(clusters), unbuffered I/O | ~0.03 ms/write, 0.14-0.51 ms/poll at 4-15 clusters | fine at today's scale; docstring's "rare" premise is false, worth correcting |

Nothing in BL-12 is worse than linear in any input that can realistically grow (contact count,
group count, cluster size). The 12.6 ms baseline is not meaningfully moved by this milestone —
the full-reconcile numbers above are two to three orders of magnitude below it at every scale
checked.

---

### Change Requests

One, documentation-only, no behaviour change, so it does not need the full
Implementer→Reviewer→DoD re-entry loop as a *code* change — but it is a correction to a shipped
docstring's factual claim, so it should still go through that loop per the project's own rule
("a change request... takes the implementation path," `AGENTS.md`) rather than being hand-applied
here:

- **File:** `body-layer/src/group_trace_log.py`, `GroupTraceLogWriter`'s class docstring.
- **Change:** correct *"a phase-2 property match or an expiry is a handful of rows per sortie at
  most... not hundreds per poll"* — reconcile logs one row per **active cluster every reconcile**,
  not only on phase-2/expiry. State the real frequency (groups-per-poll, roughly 1 Hz) and that the
  unbuffered design is still the right call at today's group counts, rather than resting on a rate
  claim that is false for the common case.
- **Acceptance measurement:** none needed beyond re-reading the corrected docstring against
  `reconcile`'s trace-record loop (`groups.py:1468-1479`) and confirming it now states "every
  cluster, every reconcile" rather than "a handful per sortie." No test changes — behaviour is
  unchanged.

No other change is requested. Nothing measured here moved the needle against the 1.000 s budget
or the 12.6 ms median, and no term scales worse than linear in a quantity this project's own
measurements say can realistically grow.

### Verdict

**APPROVED — MONITOR** (the group-trace docstring correction; no code/behaviour risk identified).
