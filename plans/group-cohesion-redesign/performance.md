### Performance Review

Branch `fix/group-undermerging`, tip `676f12c`, scope `63916e1..676f12c` (re-trigger fix,
cohesion redesign, two speech fix rounds). Files: `belief/groups.py`, `speech.py`, `callouts.py`,
`contacts.py`, `crew_console.py`, `perception/object_model.py`. This sits on body-layer's live
5 Hz poll-loop hot path. One pass for the whole feature, per root `CLAUDE.md`'s cadence.

Checks: `ruff format --check`, `ruff check`, `mypy --strict src` all clean. `pytest`: 1367
passed, 4 xfailed (matches expected).

Measurements below are a standalone microbenchmark against this branch's actual
`belief.groups`/`belief.callouts`/`belief.contacts` code (synthetic `Contact` fixtures, the same
construction pattern `tests/test_groups.py` uses), not the 2026-10-01 sortie replay — the sortie
trace tops out at 22 objects / 17 live contacts, too small to show the scaling asked for.

### Findings

#### `_cluster_contacts`'s O(n^2) pairing, at realistic and stress scale
- **Location:** `belief/groups.py::_cluster_contacts` (nearest-neighbour pass + the pairwise
  backstop loop it feeds `_pair_backstop_m` into)
- **Measured** (scattered contacts, uniform over 20x20 km, `.venv/bin/python` microbench):

  | n contacts | time |
  |---|---|
  | 22 | 0.17 ms |
  | 50 | 0.72 ms |
  | 100 | 2.96 ms |
  | 300 | 24.75 ms |
  | 500 | 70.1 ms |
  | 800 | 179.7 ms |
  | 1200 | 405.8 ms |

  Scaling is cleanly quadratic from 100 upward (4x time for ~2x n is the signature). The
  `_pair_backstop_m` redesign (installation-cap check, per-class `EAGER`/`STRICT` dict lookup,
  the ordinary unit-widths multiply) adds a handful of dict lookups per pair on top of the old
  single multiply — same *complexity class* as before this diff, a slightly larger constant.
  `object_model.profile_for` (the one per-pair call that is a linear keyword scan, not O(1)) is
  memoized **once per contact** before the n^2 loop (`profiles = [...]`), not re-run per pair —
  correctly avoided.
- **Risk:** at the real sortie's scale (22 objects) this is noise (0.17 ms against a 200 ms 5 Hz
  tick budget). At a genuinely target-rich moment (100), still noise (3 ms). It only becomes a
  real cost at counts this project has never flown (300+), and the growth path to get there is
  not "many contacts visible at once" — see next finding.
- **Action:** MONITOR. No change needed for the diff's own correctness-driven cost increase; the
  complexity class is unchanged from the pre-existing mechanism.

#### `ContactStore` never prunes, and `reconcile` runs over every contact ever seen
- **Location:** `belief/contacts.py::ContactStore.tick` ("Eighth block": `self._groups.reconcile(list(self._contacts.values()), now_sim)`); `_contacts` has no removal path anywhere in the class (grepped — only `_observation_id_to_contact_id` is documented "never pruned," but `_contacts` itself has no delete path either).
- **Risk:** this is pre-existing (the `reconcile` call site and its unfiltered argument predate this diff — group-reporting Stage 2), not introduced by `fix/group-undermerging`. But it is the thing that actually turns the table above from reassuring into a real risk over a **90-minute sortie**: `_cluster_contacts` costs grow with the total number of distinct objects *ever* folded into a `Contact`, not the number currently live. A mission with substantial ground traffic over its length can plausibly accumulate several hundred `Contact` records (most of them long-LOST) well before the sortie ends, at which point the 500-800-contact rows above (70-180 ms per tick) stop being hypothetical. This diff's own change (a few extra dict lookups per pair) marginally raises that constant but did not create the growth path.
- **Action:** LATER — escalate to Architect as a `BL-B` backlog item: filter `reconcile`'s input to contacts still plausibly relevant (e.g. not `lost` past some certainty/age threshold) before clustering, rather than the full historical set. Out of scope for this fix (no line in `63916e1..676f12c` touches which contacts get passed to `reconcile`), but worth recording here since the review explicitly asked about long-sortie growth and this is where the real exposure lives, not in the per-tick contact count.

#### Infantry `EAGER` chain-merge — no degenerate blow-up found
- **Location:** `belief/groups.py::_pair_backstop_m` (EAGER returns `math.inf`, no backstop) / `_cluster_contacts`'s single-link union-find.
- **Measured:** infantry packed into a 50x50 m box (worst case for chaining): 10 -> one 10-member
  cluster, 0.05 ms; 30 -> one 29-member cluster, 0.27 ms; 60 -> 51+9, 0.98 ms; 120 -> 117+2,
  3.73 ms. `tick()` (reconcile + `CalloutScheduler.tick`) over the same scenarios adds only
  ~0.3-0.6 ms on top — rendering one 117-member group's disclosure line is not materially more
  expensive than rendering several small ones, because `_group_member_facts`/
  `_member_contacts_for` are linear in group size, not quadratic.
- **Risk:** none at measured scale. The union-find does collapse into one giant cluster exactly as
  the EAGER policy intends (that is a correctness/speech-content question the Reviewer already
  covered, not a performance one) — it does not cost more than an equivalent-sized ordinary
  cluster, and reconciliation does not re-trigger extra `GroupStore` churn per tick (same group id
  persists once majority-overlap is established).
- **Action:** MONITOR (no action needed; recorded because the task asked explicitly).

#### Per-tick re-render of every group's disclosure line, even when silent
- **Location:** `belief/callouts.py::CalloutScheduler.tick` (calls `_group_member_facts` once per
  group, then `render_group_disclosure` again internally for `content_signature`, every tick,
  for every group — up to 4 total `_group_member_facts`/`_member_contacts_for` passes for the one
  group actually selected to speak this tick).
- **Measured:** many small, well-separated groups (worst case for the per-group multiplier, since
  clustering itself is near-free when clusters are spatially separated): 5 groups/20 contacts,
  0.032 ms; 10/40, 0.053 ms; 21/80, 0.113 ms; 41/160, 0.275 ms; 23 groups of 8/160, 0.243 ms. All
  negligible, and over two orders of magnitude below the clustering cost at equivalent n.
- **Why it's not a real risk at this scale:** `_member_contacts_for` rebuilds a full
  `{contact.id: contact for contact in store.contacts}` dict every call (one per
  `_group_member_facts`/render pass, so 2-4x per group per tick) — an O(total contacts) allocation
  that is a legitimate "needless per-tick allocation" by the letter of the focus areas, but it is
  dwarfed by `_cluster_contacts`'s O(n^2) by roughly two orders of magnitude at every n measured
  (160 contacts: 0.275 ms for the whole tick vs. ~7 ms `_cluster_contacts` alone would cost at
  that n). Fixing `_cluster_contacts`'s growth-over-time problem above would make this worth a
  second look (an O(groups x total_contacts) dict rebuild stops being free once clustering itself
  is cheap), but it is not where the budget risk is today.
- **Action:** MONITOR. Not required now; revisit if the `ContactStore` pruning fix above ships and
  total contacts stays large by design rather than by accident.

#### `last_spoken_member_contact_ids` and friends — bounded, not accumulating
- **Location:** `belief/groups.py::Group` (`last_spoken_member_contact_ids`,
  `last_spoken_leading_contact_id`, `last_spoken_differentiated`); written only by
  `GroupStore.mark_spoken`.
- **Reasoned (not measured — the mechanism makes measurement unnecessary):** `mark_spoken`
  **replaces** these fields outright (`group.last_spoken_member_contact_ids = member_contact_ids`,
  etc.), it never appends. Each is a snapshot of the group's membership at the instant it last
  spoke, bounded by that group's own current member count — a handful of contact ids, not a
  log. A `Group` that stops matching any current cluster is dropped outright by `reconcile`
  (module docstring: "a persisted group with no matching cluster ... is simply dropped"), so
  there is no path for a stale `Group` to sit around accumulating state either.
- **Action:** none needed — no unbounded growth found in the state this feature actually added.
  (The real long-sortie growth risk is `ContactStore._contacts` itself, covered above, which this
  feature did not create.)

### Verdict
APPROVED — MONITOR

No regression in this diff's own complexity class; the one real growth-over-time risk
(`ContactStore` never pruning, which this diff did not introduce) is recorded above as a backlog
item for the Architect rather than a blocker, since fixing it means changing what `reconcile`'s
caller passes in, outside `63916e1..676f12c`'s own lines.
