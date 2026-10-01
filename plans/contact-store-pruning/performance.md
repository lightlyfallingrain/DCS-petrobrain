### Performance Review

Branch `fix/contact-store-pruning`, tip `2992d91`, scope `main..fix/contact-store-pruning`,
principally `90057c4` (`BL-B23`: filter `GroupStore.reconcile`'s input to not-`lost` contacts in
`ContactStore.tick`'s eighth block). This is the fix for a defect this role raised itself during the
`group-cohesion-redesign` performance pass (`plans/group-cohesion-redesign/performance.md`,
"`ContactStore` never prunes" finding). Sits on the live 5 Hz poll-loop hot path.

Checks (`body-layer/`, fresh `.venv`): `ruff format --check src tests` clean, `ruff check src tests`
clean, `mypy src` clean ("Success: no issues found in 53 source files"), `pytest tests -q` ->
**1384 passed, 4 xfailed** (matches expected).

Measurements are a standalone microbenchmark against this branch's actual
`belief.contacts`/`belief.groups` code (synthetic `Contact` fixtures, same construction pattern
`tests/test_groups.py` uses), run independently of the implementer's and Reviewer's own benchmarks.

### Findings

#### Q1 — "before" reproduces as the real pre-fix shape, not a differently-shaped benchmark
- **Location:** `GroupStore.reconcile` called directly with the full unfiltered contact set (the
  pre-fix `tick()` call shape).
- **Measured** (fresh `n`, `GroupStore.reconcile(contacts, now_sim)` direct):

  | n | this review | implementer | original (group-cohesion-redesign) |
  |---|---|---|---|
  | 22 | 0.15 ms | 0.15 ms | 0.17 ms |
  | 50 | 0.72 ms | 0.71 ms | 0.72 ms |
  | 100 | 2.86 ms | 2.75 ms | 2.96 ms |
  | 300 | 25.43 ms | 24.62 ms | 24.75 ms |
  | 500 | 69.50 ms | 69.15 ms | 70.1 ms |
  | 800 | 180.60 ms | 178.40 ms | 179.7 ms |
  | 1200 | 418.66 ms | 402.99 ms | 405.8 ms |

  All three runs land within ordinary measurement noise (single-digit-percent) of each other at
  every point, and the curve is cleanly quadratic from 100 upward in all three. This confirms the
  implementer's "before" column is a reproduction of the same mechanism this role originally
  measured, not a differently-shaped benchmark that happens to land nearby.
- **Action:** none — confirmation only.

#### Q2 — the live-count axis is exactly as quadratic as before, unchanged by this fix (by design)
- **Location:** `belief/groups.py::_cluster_contacts`, reached via `ContactStore.tick`'s eighth
  block, now fed only not-`lost` contacts.
- **Measured** (`ContactStore.tick()`, all `n` contacts simultaneously live/fresh — the
  target-rich-moment shape, not the long-sortie-tail shape the implementer's "after" column tests):

  | n live | time |
  |---|---|
  | 20 | 0.15 ms |
  | 50 | 0.77 ms |
  | 100 | 2.88 ms |
  | 200 | 11.19 ms |
  | 300 | 25.12 ms |
  | 500 | 69.80 ms |

  This is the same curve as Q1's "before" column (as it must be — with nothing filtered out, `tick`
  feeds `reconcile` the same full set either way). **The implementer's "after" column being flat
  (0.15-1.4 ms across a 55x range in total `n`) is true only along the axis it measured: total
  contacts ever seen, with live count fixed at 20.** It says nothing about what happens when the
  *live* count itself grows, and it was never meant to — `BL-B23`'s whole premise is that `_contacts`
  accumulates over sortie length while the live threat picture does not. Growing the live count
  reproduces the pre-existing O(live²) clustering cost untouched, because clustering's input size is
  exactly the live count after this fix.
- **Risk:** at 300 simultaneously-live contacts, 25 ms/tick is ~12% of a 200 ms (5 Hz) tick budget —
  noticeable but not alarming. At 500, 70 ms is 35% of budget, and would start to compete with the
  other work `tick` and the poll loop do in the same cycle. Whether a mission plausibly reaches
  300-500 *simultaneously live* contacts within the 10 km player bubble (`PLAYER_BUBBLE_RADIUS_M`,
  `perception/association.py`) is a scenario-design question, not a code one — a dense multi-column
  convoy-plus-escort engagement with every individual vehicle as its own `Contact` could approach the
  lower end of that band, but it is not this project's typical sortie shape today.
- **Action:** MONITOR, not a defect in this fix. This is the same risk the group-cohesion-redesign
  performance review already named and MONITORed independently of the total-ever-seen growth path
  (that review's "`_cluster_contacts`'s O(n²) pairing" finding) — `BL-B23` was scoped to the
  total-ever-seen axis only, and fixing it correctly left the live-count axis exactly as it was. No
  new backlog item needed; the existing one already covers this axis if it ever needs revisiting.

#### Q3 — residual O(n) per-contact work, confirmed linear and cheap at scale
- **Location:** `ContactStore.tick`'s first seven per-contact blocks
  (certainty/classification/cardinality/motion/attention/range/engagement), run over every contact
  in `_contacts` regardless of certainty, untouched by this fix.
- **Measured:** 1200 contacts, all past `LOST_THRESHOLD_S` (none reach `reconcile`, isolating this
  cost from clustering entirely): **1.23 ms**. Growth is visible but mild — this review did not sweep
  it, but the implementer's own "after" column (0.15 ms at 22 -> 1.37-1.4 ms at 1200, with only 20 of
  those live and the rest excluded from clustering) is effectively measuring this same residual cost
  plus a flat 20-contact clustering term, and it stays linear across the full 55x range.
- **Risk:** 1.23 ms at 1200 contacts is under 1% of a 200 ms tick budget. Not a problem at any scale
  this project has reason to expect over a single sortie (even an aggressive multi-hour one).
- **Action:** MONITOR, no backlog entry warranted now. Worth a second look only if `_contacts`
  itself ever needs pruning for memory reasons (unrelated to this fix's scope) or if a future
  per-contact block in `tick` becomes non-trivial (e.g. a per-contact DB/IO call) — linear cost with
  a cheap constant is not where this project's risk budget should go today.

#### Q4 — `certainty_of` call overhead is not worth tracking
- **Location:** `ContactStore.tick`'s eighth-block filter comprehension,
  `certainty_of(contact, now_sim) != "lost"`, called once per contact per tick in addition to the
  first block's own `certainty_of` call (so twice per contact per tick, not newly — the first block
  already called it before this fix).
- **Measured:** 1200 calls in isolation: **0.083 ms total, ~0.069 us/call**. At 5 Hz x 1200 contacts
  (6000 calls/s, doubled to ~12000/s counting both call sites), that is well under half a millisecond
  of CPU time per second of wall clock.
- **Risk:** none. `certainty_of` is a handful of float comparisons against `now_sim -
  contact.last_seen_sim` — exactly the kind of pure, allocation-free function that is cheap to call
  twice rather than cache.
- **Action:** none.

### Verdict
APPROVED — MONITOR

The fix does what it claims: it removes the total-ever-seen growth path from clustering, confirmed
by an independent reproduction of both the "before" (418.66 ms at 1200, matching the implementer's
402.99 ms and this role's own original 405.8 ms within noise) and "after" (1.37 ms at 1200) numbers.
The live-count quadratic clustering cost is unchanged — correctly so, since fixing it was never this
fix's scope — and remains covered by the pre-existing `group-cohesion-redesign` performance finding
as a MONITOR item, not a new backlog entry. The residual linear per-contact cost and the
`certainty_of` call overhead are both negligible at every scale measured.
