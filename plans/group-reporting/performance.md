### Performance Review

Branch `feature/group-reporting` @ `b92c7a7`, verified against `main` @ `acc94db` via an isolated
snapshot (`git archive feature/group-reporting | tar -x`) — the worktree's own HEAD (`570dccc`) was
not an ancestor of the named tip, so all checks and measurements below ran against the snapshot's
`body-layer`, using the main checkout's `.venv` interpreter by absolute path.

Checks (snapshot, `body-layer/`): `ruff format --check` clean, `ruff check` clean, `mypy src`
(strict) clean (53 files), `pytest tests -q` → **1349 passed, 4 xfailed** — matches the dispatch's
expected numbers exactly.

Scope: `belief/groups.py` (new), plus the cross-contact reconciliation wired into
`ContactStore.tick`, the `CalloutScheduler.tick` group-candidate path, and
`render_group_disclosure`/`_group_member_facts` in `speech.py`. This is on the live 5 Hz poll loop
(`ContactStore.tick` runs every poll), not a per-transcript or offline path.

### Findings

#### `_cluster_contacts`'s O(n²) cohesion pass
- **Location:** `belief/groups.py::_cluster_contacts`, called once per `ContactStore.tick()` via
  `GroupStore.reconcile`.
- **Risk:** Two nested all-pairs loops (nearest-neighbour-gap computation, then the union-find
  pass), each O(n²) in tracked-contact count. Measured directly against this branch's own code
  (isolated `_cluster_contacts` calls, uniform random positions):

  | n (tracked contacts) | per-call cost |
  |---|---|
  | 16 | 0.06 ms |
  | 52 | 0.6 ms |
  | 200 | 8.4 ms |
  | 500 | 54 ms |
  | 2000 | 879 ms |

  The 2026-09-28 sortie's longest run held **52 contacts total, 16 concurrent per poll**
  (`plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md`) — 0.6 ms against a 200 ms
  poll budget, a non-issue. The curve is consistent with pure O(n²) scaling (4x n → ~14x time). It
  would need on the order of **300–400 simultaneously tracked contacts** before this alone starts
  costing a meaningfully large slice of a 200 ms poll tick, and only becomes a real problem (tens to
  hundreds of ms) in the 500–2000 range — roughly 10–40x today's observed peak. Nothing in the
  10 km player bubble or the current sortie shapes suggests that count is near.
- **Action:** MONITOR. The plan and the module's own docstring already flag this cost shape and
  attribute it correctly ("fine at today's contact counts, worth watching if a sortie produces
  materially more simultaneous contacts") — this review confirms that with real numbers rather than
  reasoning alone. No mitigation needed now; if a future denser-scene milestone (composition/Stage 5,
  a longer sortie, a wider admission radius) starts pushing tracked-contact counts toward the low
  hundreds, revisit with a spatial index (grid/k-d tree) for the nearest-neighbour pass, which turns
  both loops from O(n²) to roughly O(n log n).

#### Duplicate `describe_contact` calls per group, per tick
- **Location:** `belief/callouts.py::CalloutScheduler.tick` calls `_group_member_facts` once per
  live group to decide whether to score it as a candidate; `belief/speech.py::render_group_
  disclosure` (called right after, on the same group, to get the actual line to compare/score)
  calls `_group_member_facts` again internally, redoing a `describe_contact` per member. For the
  one group that ends up chosen to speak, `render_group_disclosure` is called a third time at the
  "re-render fresh at the instant of speaking" step.
- **Risk:** Real redundant work — `describe_contact` is not free (attention/enrichment/position
  facts per member) — but bounded by group count × member count, both small at realistic scale (a
  handful of groups, 2–5 members each per the plan's own floor of 2). At today's contact counts this
  is a few extra function calls per tick, not a measurable cost. It is exactly the "poor batching"
  shape the checklist asks about, and the fix is mechanical: thread the already-computed
  `member_facts` list through as an optional parameter to `render_group_disclosure` instead of
  having it re-gather via `_group_member_facts`.
- **Action:** LATER. Not worth blocking this feature on — it's a small, local, easy cleanup with no
  behavioural risk, but there's no credible scenario at current or near-term scale where the 2–3x
  multiplier on a handful of cheap calls threatens the poll budget. Worth doing opportunistically the
  next time `speech.py`/`callouts.py` is touched.

#### Accumulation across ticks
- **`GroupStore.reconcile`** replaces `self._groups` wholesale every call (`self._groups =
  new_groups`) — a group with no matching cluster is dropped, not retained. No unbounded growth.
- **`GroupStore._next_group_number`** increments forever and never reuses ids, same posture as
  `ContactStore`'s own id counters elsewhere in this codebase — cosmetic (longer id strings over a
  very long session), not a cost issue.
- **`_representative_size_m`** is computed once per contact per `reconcile()` call (hoisted into a
  `sizes` list before the pairwise loop), not recomputed per pair — already correctly batched, no
  finding here despite the plan's own prompt to check it.
- No per-tick allocation was found that scales with sortie history rather than with the current
  contact/group count.

### Verdict
APPROVED — MONITOR
