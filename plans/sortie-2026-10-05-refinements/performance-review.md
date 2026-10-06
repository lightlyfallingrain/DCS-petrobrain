# Performance review — sortie 2026-10-05 refinements, items 2/3/4

**Branch:** `feature/sortie-refinements` · **Tip reviewed:** `18da60e` (verified by
`git rev-parse HEAD` after `git checkout --detach 18da60e`; the worktree was created at
`19143fa`, a *sibling* of this tip and not an ancestor of it — `git merge-base --is-ancestor
18da60e 19143fa` returned false — so the first reading would have been of the wrong code. AGENTS.md
rule 4 caught this, again.)

**Baseline this pass is measured against:** `body-layer/research/2026-10-05-performance-review.md`
(at `02e98da`, not present at this tip — read via `git show`). The poll loop is **1.0 s, not 5 Hz**;
the realised period is `work + interval`, measured median work ~330 ms with 1,736 ms peaks; the two
dominant terms are `group_salient_ids` (~300 ms every poll) and `CalloutScheduler.tick`'s
`describe_position` calls (worst observed tick 47 calls / 1,579 ms).

**Knowledge graph:** not queryable — `graphify-out/` does not exist in this worktree
(`.claude/scripts/gq.sh` → *"No graph yet."*). Same condition the Architect hit on this feature.
Treat that silence as "not built", never as "nothing exists".

## Verdict

**NEEDS MITIGATION** — one finding, on Item 3. Items 2 and 4 are clear.

The mitigation is small, local, and follows a suppression rule this codebase already has. Per
AGENTS.md it re-enters the loop as **Implementer → Reviewer → DoD**; I am requesting it rather than
applying it.

---

## Findings

### 1. Item 3 turns one watched contact into N, and the watched-only callout kinds amplify that into a measured ~0.8–1.6 s tick — NOW

- **Location:** `body-layer/src/belief/crew_console.py:1232` (`_mark_watched_with_group`, the
  `for member_id in member_ids` loop) → `body-layer/src/belief/contacts.py:1223` (the sixth block's
  `is_watched` gate on `CONTACT_RANGE_CROSSED` emission) → `body-layer/src/belief/callouts.py:788`
  (the `_WATCHED_ONLY_KINDS` filter's `describe_contact`) and `:812` (the scoring
  `describe_contact`).
- **Mechanism, traced end to end.** `_mark_watched_with_group` is correct and cheap in itself. The
  cost is downstream, in two places the plan did not look at:
  1. **`CONTACT_RANGE_CROSSED` is watch-gated at *emission*** (`contacts.py:1223`: a non-watched
     contact clears `last_announced_range_km` and emits nothing). So for an 8-member group, watching
     one member used to produce **one** event stream; watching all eight produces **eight**. Group
     members are co-located *by definition* — that is what `_cluster_contacts` means — so they cross
     the same whole-kilometre mark in the same poll or the next one. The events arrive **co-timed, in
     one tick**.
  2. **`CONTACT_MOTION_CHANGED` is *not* watch-gated at emission** (`contacts.py:1172`) — it was
     always produced for every contact and discarded by the callout filter's not-watched `continue`.
     Now it survives the filter for every member. A convoy pulling away is N simultaneous
     `CONTACT_MOTION_CHANGED` events.
  - Each surviving event costs **two** `describe_contact` calls per tick — one at `callouts.py:789`
    in the filter, one at `:812` in scoring — and each resolves to a `describe_position`, because
    `WorldEnrichmentCache` **misses by construction** for a re-observed contact (keyed on exact
    `Contact.last_position` equality, `enrichment.py:645`) and the contacts being spoken about are
    precisely the re-observed ones. That was Finding 2 of the 2026-10-05 pass; it is unchanged here.
  - **`tick` speaks at most one candidate and does not consume the losers** (`callouts.py:932`
    returns on the first speakable line). The remaining N−1 events are re-described on every
    non-busy tick until spoken or until `CALLOUT_MAX_AGE_S` (10 s). `WATCH_REPORT_MIN_GAP_S` (8 s)
    is keyed on `contact_id` (`callouts.py:800`), so it does **not** damp across N *different*
    members. `busy_until_sim` is the only brake.
- **Measured, at this tip, against the real `world-model/data/world-model/syria-full.sqlite`:**

  | | |
  |---|---|
  | `describe_position`, 24 distinct positions within 9 km | median **77.9 ms**, mean 81.9, max 133.6 |
  | `describe_position`, 8 group members spread 300 m | median **51.4 ms**, **410 ms** for the eight |
  | same position repeated ×10 | median 50.8 ms — **no internal memo**, CPU-bound, as before |

  So: 8 members × 2 calls ≈ **820 ms added to one tick** from range crossings alone, against a
  330 ms median poll. A convoy that is newly watched *and* starts moving *and* crosses a kilometre
  mark produces ~16 events ≈ **32 `describe_position` calls ≈ 1.6 s in one tick** — which is
  numerically the 2026-10-05 pass's *worst observed tick* (47 calls / 1,579 ms). That tick was seen
  **once in 150 polls**; this one is reproducible from a single player command.
- **The fix landing on `feature/bl11-tick-cost` does not cover this, and I measured that
  specifically.** The per-tick `describe_position` memo and the quantised `WorldEnrichmentCache`
  key were recommended at a 50–100 m grid. Group members are deliberately separated by more than
  that:

  | quantisation | distinct cells for 8 members spread 300 m |
  |---|---|
  | 50 m | **8 of 8** — no relief at all |
  | 100 m | 6 of 8 |
  | 200 m | 3 of 8 |

  The memo collapses the *3× double-gather* multiplier within a tick (which is real and valuable),
  but it does **not** collapse the N-members multiplier this item introduces, because those are N
  genuinely distinct positions. **My finding stands unchanged after `bl11-tick-cost` lands.**
- **Blast radius:** the poll thread, which is also the speech thread. This is the term the
  2026-10-05 pass identified as the spiky cause of the sortie's p90 of 4.98 s — i.e. the mechanism
  by which the pilot experiences Petrovich going quiet. And it fires on exactly the command item 3
  exists to serve (convoy tracking).
- **There is a speech-flood twin, same mechanism.** N members ⇒ up to N spoken range-crossing or
  motion lines about one group, one per tick-after-busy, over up to 10 s. The codebase **already
  has the policy that answers this**: `callouts.py:775-787` skips `CONTACT_DETECTED`/
  `CONTACT_REACQUIRED` for a contact that is in a group, because *"spoken for by the group's own
  disclosure line instead."* Item 3 newly makes three *other* kinds reachable in bulk for grouped
  contacts, and they bypass that rule.
- **Mitigation (smallest first; (1) alone is enough to clear this finding):**
  1. **Extend the existing grouped-contact suppression to `_WATCHED_ONLY_KINDS`.** In
     `callouts.py`'s filter, for an event whose `contact_id` is in a group with more than one
     member, keep **one** member's event (the group's leading contact, which
     `group_membership_state` already computes) and `self._consumed.add(event.id)` the rest. This is
     a ~6-line change in the loop that already does the identical thing one branch above, it drops
     the describe count from 2N back to 2, and it fixes the speech flood with it. It needs a product
     call on the wording — whether the line becomes "the group is moving" or stays one member's
     line — which is the Reviewer's/user's to make, not mine.
  2. Alternatively, cap `_mark_watched_with_group`'s member loop (e.g. nearest 4). Cheaper to write,
     but it makes `watch group` silently partial, which contradicts the user's own ask, so I do not
     recommend it.
  3. Not a fix, but worth knowing: making `WATCH_REPORT_MIN_GAP_S` group-scoped rather than
     contact-scoped would damp the speech flood without touching the describe cost. Half a fix.

### 2. Item 3's iterative-projection branch — the one the plan *did* flag — is genuinely free. The plan's conclusion was right; its reasoning was aimed at the wrong function — MONITOR (no action)

- **Location:** `body-layer/src/belief/enrichment.py:601` (`look_range_m <=
  PROJECTION_ITERATIVE_RANGE_M or contact.attention == "watch"`), reached from
  `_terrain_aware_world_position`. `plan.md:360-367` names this as the per-watched-contact cost
  item 3 "uses more aggressively", and dismisses it as the same pre-existing mechanism
  `plans/dcs-driven-los/performance.md` approved for `AttentionArea`.
- **Measured** (`project_terrain_aware`, 40 random bearings at 2.5–9 km on `syria-full`):

  | | |
  |---|---|
  | `max_iterations=1` (unwatched, beyond 2 km) | median **0.03 ms** |
  | `max_iterations=5` (watched) | median **0.15 ms** |

- So the watched branch costs **~0.12 ms per member per enrichment recompute** — 5× a number that is
  three orders of magnitude below the `describe_position` call sitting immediately after it in the
  same function. Even 50 watched contacts is 6 ms.
- **Action:** none. But the plan's "same mechanism already accepted" paragraph should not be read as
  having cleared item 3 on performance grounds: it cleared the 0.12 ms term and never reached the
  51 ms one. Finding 1 is what that paragraph was looking for.
- **Also MONITOR, not now:** `_mark_watched_with_group` creates one `watch_contact_task` per member
  when `self.tasks` is configured, so one command can mint N tasks where it used to mint one. Task
  creation is in-memory bookkeeping and the store is small; flagging only because the growth axis
  changed from per-command to per-command-×-group-size.

### 3. Item 4 raises `post_look_direction` from 1 % to 66 % of polls during a commanded `scan ahead` — cheap in the median, but it triples exposure to the 2.0 s HTTP timeout tail — MONITOR

- **Location:** `body-layer/src/perception/gaze.py:267` (`_SECTOR_LEGS["ahead"] = (11, 12, 1)`) →
  `body-layer/src/logger.py:511-519` (the `look_direction != self._last_look_direction` gate) →
  `body-layer/src/aircraft_client.py:172` (`post_look_direction`).
- **Measured** (`gaze_at` over a 120 s series at the 1.33 s realised period):

  | `scan ahead` legs | cone changes / polls | share of polls pushing `look_direction` | cone centres |
  |---|---|---|---|
  | old `(12,)` | 1 / 91 | **1 %** | `0°` |
  | new `(11, 12, 1)` | 60 / 91 | **66 %** | `-30°, 0°, +30°` |

  `gaze_at` itself is 0.83 µs — the function is free; what changed is how often its answer differs.
- **Per-poll CPU cost: unchanged.** `FOCUS_CONE_HALF_WIDTH_DEG` is still 15°, so each poll still runs
  the gaze gate against one 30°-wide cone. Only the *direction* cycles. The union of azimuths that
  pass the gate over a 6 s cycle widens from ±15° to ±45°, so up to 3× as many distinct contacts
  accumulate fresh percepts per cycle — which does feed Finding 2's cache-miss path.
- **Why this is nevertheless bounded, and the bound is a measured one.** Free scan's own table
  (`SCAN_PLAN`, 12/11/10/9/12/1/2/3) already sweeps ±105° and already pushes `look_direction` on
  ~50 % of polls — and the 2026-10-05 measurements (median 330 ms, worst tick 47 calls) were taken
  **under free scan**. Item 4 moves `scan ahead` from the narrowest gaze state the system has
  towards free scan's coverage; it cannot exceed the baseline those numbers were measured at. So
  there is no new performance class here, which is the same conclusion the plan reached — with a
  measurement behind it now.
- **The one real exposure is the tail, not the median.** Finding 7 of the 2026-10-05 pass:
  `aircraft_client._DEFAULT_TIMEOUT_S` is 2.0 s and serves HTTP/1.0 with no connection reuse, so one
  wedged push costs 2 s *on the poll thread*. Item 4 raises the number of polls carrying that extra
  round trip during a commanded `scan ahead` from ~1 % to ~66 %. Locally a push is 0.67–0.73 ms; on
  the LAN budget ~5–10 ms. Negligible in the median, a ~66× increase in how often the 2 s tail is
  reachable.
- **Action:** **MONITOR**, no change to this branch. It strengthens the case for Finding 7's own NOW
  item (drop the `/latest`-style read timeouts to ~0.3–0.5 s), which is already owned elsewhere.
  Nothing in item 4 should wait on it.

### 4. Item 2's two extra phrasings cost 0.8 ms on a path that runs per utterance, not per poll — no action

- **Location:** `audio-adapter/src/vocabulary.py:323-329` (`report_all` grows from 3 phrasings to 5;
  89 phrases across 52 tokens in total).
- **Measured** (`command_matcher.match_transcript`, 300 reps each):

  | transcript | median |
  |---|---|
  | `"describe contacts"` | 0.85 ms |
  | `"report contacts"` | 0.79 ms |
  | `"scan left three kilometres"` | 0.53 ms |
  | `"describe the mission to me and then tell me…"` | 0.41 ms |
  | `"quite a nice day for flying today"` | 0.095 ms |

- Two phrasings on 89 is ~2 % more matcher work, and the matcher runs once per *transcript* —
  a handful of times a minute at most, on the `/transcripts/poll` path, never per contact or per
  poll body. The adversarial sentence is the *cheapest* case, because the early reject fires first.
- **Action:** none.

## What could not be measured, and the instrument each needs

1. **The real in-flight distribution of watched group size.** Finding 1's cost is linear in it and
   I used 8 as a stated assumption, anchored on `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M`
   (500 m) and the convoy case item 3 was asked for. The instrument: a counter on
   `_mark_watched_with_group`'s `len(member_ids)` and on `describe` calls per
   `CalloutScheduler.tick`, logged to the existing sortie JSONL. Both are one line each, and both
   were already asked for by the 2026-10-05 pass's own "count, don't just time" note.
2. **Whether N co-timed range crossings actually land in one tick in flight**, rather than being
   spread by per-member belief jitter in `last_announced_range_km`'s deadband. The deadband is the
   belief's own down-range uncertainty (`contacts.py:1250`), which differs per member, so the burst
   may be smeared across 2–3 ticks — which lowers the per-tick peak but not the total, and the
   re-describe-until-spoken loop makes a smeared burst *more* expensive overall, not less. Needs a
   flown sortie with the counter from (1).
3. **LAN cost of the extra `post_look_direction`.** Measured only over loopback. Needs the Windows
   box with aircraft-layer live; the figure that matters is p99, not median.
