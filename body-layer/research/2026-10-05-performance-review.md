# Body-layer performance review

**Date:** 2026-10-05. Whole-subproject pass (53 files, ~25.8 k lines of `src`), not a feature diff.
Reviewed at `main` tip `19143fa` (verified with `git rev-parse HEAD` before any reading).

**Why this pass exists:** `aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`
§2 found body-layer's poll loop running at ~0.7 Hz and said *"a timing instrument around the poll
loop is the next step, not more log reading."* That instrument is the first thing this review
built. The headline finding is diagnosed, measured, and the dominant term has a fix whose speedup
is measured at 8× with output equality asserted.

**Everything numbered below is measured unless the finding says otherwise.** Measurements come from
a synthetic-sortie harness that drives the *real* `ConsolePerceptionRunner.run_once()` +
`DetectionTraceWriter` + `BeliefTruthLogWriter` + `CrewConsole.drain_events` against a fake
in-process aircraft client and the **real** `world-model/data/world-model/syria-full.sqlite`
(738 MB). The harness lives in the session scratchpad, not in `src/` or `tests/` — see
"Reproducing the measurements" at the end for what it did, so it can be rebuilt. Scale was taken
from the sortie: 440 objects, 10 km player bubble, 130–142 live contacts, 1 s sim steps.

The fake client removes LAN latency, so every CPU number below is a **floor** for the real thing,
and the HTTP cost is measured separately (finding 7).

---

## The headline correction: `BL-B30`'s premise is wrong, and the real number is smaller but the cause is worse

`BL-B30` reads *"specified at 5 Hz (0.2 s), observed at ~0.7 Hz — about seven times slower."*

**There is no 5 Hz anywhere in body-layer's configuration.** `logger.py:999` is
`_DEFAULT_POLL_INTERVAL_S = 1.0`, unchanged since it was introduced (`abf49cd`, 2026-09-08), and
its own neighbouring comment at `logger.py:986` calls it *"the default one-second poll interval."*
`body-layer/RUN.md`'s documented run command does not pass `--poll-interval-s` at all, so the
sortie ran at **1.0 s**. The project's other docs already say so in as many words —
`body-layer/ROADMAP.md:1288` ("the project's own 1.0 s default poll interval"),
`audio-adapter/ROADMAP.md:473` ("default 1.0 s"). The "5 Hz" claim survives only in three stale
*docstrings* (`logger.py:1446`, `belief/brain_client.py:12` and `:274`,
`perception/motion.py:91`) that no configuration backs.

So the miss is **1.43 s against 1.0 s, ~1.4×, not 7×.** That matters in two directions:

- **Good news the backlog does not have:** `BL-B30`'s worry that *"every decay half-life, dwell and
  cadence constant… were tuned against an assumed 5 Hz tick"* and are therefore mis-calibrated is
  **unfounded**. They were tuned in flight at 1 Hz, which is what the code has always done.
  `perception/motion.py:91`'s comment ("objects arrive at 5 Hz") is the one place that documents an
  assumption the runtime never met — worth a direct look, but that is a correctness question for a
  debugger, not a performance one.
- **Bad news the backlog also does not have:** the mechanism is not latency somewhere, it is that
  **the loop sleeps a fixed interval *after* the work instead of to a deadline**, and the work is
  far more expensive than anyone had measured.

`logger.py:1552` (and `:1192`, the `--console` twin) ends the poll body with:

```python
stop_event.wait(poll_interval_s)
```

so the realised period is `work + poll_interval_s`, never `poll_interval_s`. Measured work at
sortie scale is **median ~330 ms with peaks to 1,736 ms** (finding 1 + finding 2 below). That gives
a median period of **1.33 s** against the sortie's measured **1.43 s** — the mechanism is
quantitatively accounted for, with the residual explained by LAN latency the harness does not
model.

Of `BL-B30`'s four named suspects, the ranking turns out to be:

| suspect, as `BL-B30` ranks it | verdict |
|---|---|
| world-model LOS **fallback** (SQLite per candidate per poll) | **not the cause.** `check_visibility`'s whole gate chain, LOS included, is 2.4–21 ms/poll for 440 candidates — see finding 3 |
| `BL-B26` triple-gather in `CalloutScheduler.tick` | **confirmed, and far worse than its own estimate** — finding 2 |
| the detection-trace writer | **real but small**: a steady 4.4 ms/poll CPU. Its *volume* is the finding — finding 6 |
| network latency on the aircraft-layer poll | **not the median cause** (3.4 ms loopback floor for 5 GETs) but a credible tail cause via its 2.0 s timeouts — finding 7 |

And the actual largest term was not on the list at all: **`perception.group_salience.group_salient_ids`,
~300 ms every poll, unconditionally** (finding 1).

### Why the sortie logs could not have found this, and where the instrument goes

Both logs the sortie analysis used derive "poll gap" from *distinct `t_sim` values in
conditionally-written rows*. That measurement cannot distinguish three different things: "did not
poll", "polled and had nothing to write", and "polled but sim time did not advance". The proof it
is unreliable is in the note's own table — the detection trace reports 2,621 polls and the
belief-truth log 1,340 over the *same* span of the *same* loop. At least one of them is not
counting polls. In particular, the **193 s maximum gap is almost certainly a sim-time artifact**
(a pause, or a mission load), not a 193-second poll; nothing in this subsystem can block a single
poll for three minutes.

**The instrument that answers this is four lines in the poll body**, and it should record wall
clock, not sim time:

- Wrap each of the five phases already separated in `_run_crew_text_poll_loop`
  (`runner.run_once()`, `belief_truth_writer.write_poll`, `trace_writer.write_poll`,
  `crew_console.drain_events`, `_poll_f10_commands`/`_poll_transcripts`) with
  `time.perf_counter()` and accumulate per-phase totals.
- Emit **one** log line every N polls (not per poll) carrying: poll count, wall span, and the
  per-phase mean and max in ms. One line per 60 polls is a minute of flight per line.
- Inside `run_once`, the useful sub-split is `source.poll` vs `store.ingest` vs `store.tick`, since
  finding 1 and finding 3 both live under `source.poll` and need telling apart.
- **Count, don't just time, two things:** candidates handed to `group_salient_ids`, and
  `describe_position` calls per tick. Both are the multipliers, and both are invisible in a timing
  number alone.

That is `BL-B30`'s remaining work. The diagnosis below does not depend on it; it is what will
confirm the fix in flight and catch the next regression.

---

## Findings

Ranked by measured contribution to the poll period, then everything else.

### 1. `group_salient_ids` costs ~300 ms of every single poll, and ~90 % of that is recomputation inside an O(n²) loop — **the single largest cost in the subsystem**

- **Location:** `perception/group_salience.py:124` (`group_salient_ids`), its pair loop at
  `:154-157`, and `_cohesive` at `:104`. Called unconditionally once per poll from
  `perception/naked_eye_source.py:555`.
- **Measured, at 440 in-bubble candidates (the sortie's own object count):**

  | poll | `group_salient_ids` ms | `profile_for` calls that poll | live contacts |
  |---|---|---|---|
  | 20 | 305.4 | 160,555 | 75 |
  | 120 | 298.5 | 160,709 | 142 |
  | 280 | 309.0 | 160,622 | 142 |
  | 480 | 308.4 | 160,622 | 142 |

  Flat at **~300–318 ms on every poll**, independent of contact count — it scales with *candidate*
  count. `cProfile` over 300 polls attributes **38.7 s of 66.7 s total (58 %)** to this one
  function, and `perception/object_model.py:556` (`profile_for`) is the largest single `tottime`
  entry in the whole profile at 12.5 s over 11.45 M calls.
- **Mechanism:** the union-find pass is O(n²) over the resolvable set — which is documented and
  deliberate. The cost is not the O(n²); it is that **`_cohesive` recomputes four per-*candidate*
  quantities per *pair*.** For each of the ~96,000 pairs at n=440 it performs two
  `object_model.profile_for` lookups and two `range_m` calls, all four of which depend on one
  candidate only and are identical across every pair that candidate appears in. `profile_for` is
  itself an uncached linear substring scan over two keyword tables with a `.lower()` allocation per
  call (hence 21.3 M `str.lower` calls in the profile).
- **Risk:** this *is* the budget violation. It is ~90 % of the median poll's CPU, it pays on every
  poll whether or not anything changed, and it grows quadratically with mission population — at 800
  candidates it is 722 ms, which on its own would push the realised period past 1.7 s.
- **Mitigation — measured, with output equality asserted:**

  | n | current | `+lru_cache` on `profile_for` | hoist per-candidate terms | both | speedup |
  |---|---|---|---|---|---|
  | 55 | 3.4 ms | 1.6 | 0.5 | 0.4 | 7.9× |
  | 128 | 17.8 ms | 8.8 | 2.3 | 2.2 | 8.0× |
  | 250 | 69.7 ms | 34.7 | 8.8 | 8.6 | 8.1× |
  | **440** | **215.1 ms** | 106.6 | **26.8** | 26.5 | **8.1×** |
  | 800 | 722.0 ms | 372.9 | 92.6 | 90.8 | 7.9× |

  (`assert r_current == r_lru == r_hoist == r_both` passed at every n — the returned
  `frozenset[int]` is bit-identical, so this is pure recomputation removal, not an approximation.)

  Two independent changes, both small and local:
  1. **Hoist.** Compute `(GeoPosition, theta_size)` once per candidate in the `_resolvable` pass
     that already walks the list, carry them in parallel lists, and make the pair loop pure
     arithmetic on `theta_sep <= GAP * 0.5 * (theta_i + theta_j)`. This is where the 8× is.
     `_cohesive` stays as a tested function for the two-candidate case; the loop stops calling it.
  2. **`@functools.lru_cache` on `profile_for`.** It is a pure function of one string with a key
     space of a few hundred DCS type names. Measured **0.93 µs → 0.04 µs per call (23×)**. Worth
     doing *as well as* the hoist, because ~40 k of the remaining per-poll `profile_for` calls come
     from `perception/clustering.py` and `perception/visibility.py`, which the hoist does not touch.
- **Action:** **NOW.** This is the fix that closes `BL-B30`. Taking the median poll from ~330 ms to
  ~70 ms puts the realised period at ~1.07 s against a 1.0 s target.
- **Not in scope for the NOW fix, flagged for Architect:** even after the hoist this is O(n²), and
  the plan's own reasoning (`group-detectability`, "a group is a property of the scene, not of
  what's currently gazed") deliberately runs it over the whole 10 km bubble *before* the gaze gate,
  so it cannot be scoped to the gaze cone without changing semantics. If 800+ candidate missions
  are expected, the next step is spatial pruning (sort by bearing, compare only within the cohesion
  angular window) — a semantics-preserving change, but a real algorithm change, not a hoist.

### 2. One `CalloutScheduler` tick makes up to 47 `describe_position` calls at ~34 ms each — a measured 1.58 s of blocking SQLite work on the poll thread

- **Location:** `belief/callouts.py` `tick`: `:789` (the `_WATCHED_ONLY_KINDS` filter),
  `:814` (scoring), `:823` (`_group_member_facts`), `:830`
  (`_already_reported_member_ids`), `:833` (`render_group_disclosure`, which calls
  `_group_member_facts` again at `belief/speech.py:1480`/`:1681`), `:891`
  (`group_membership_state`, which calls it a third time at `belief/speech.py:1357`). Each member
  fact resolves through `belief/enrichment.py:644` → `:650` `semantic_facts_for` →
  `query.describe.describe_position`.
- **This is `BL-B26`, and `BL-B26`'s own order-of-magnitude estimate is wrong by two orders.** That
  entry says *"~15 ms/tick for 5 groups × 10 members"* — i.e. ~0.3 ms per member gather — and notes
  it was "estimated rather than measured". Measured, the unit is a **`describe_position` call**, and
  on `syria-full.sqlite`:

  | | |
  |---|---|
  | `describe_position`, 60 distinct positions within 9 km | median **51.6 ms**, mean 67.8, max **228.4** |
  | same position repeated ×20 | median **41.4 ms** — it does **not** get cheaper, so it is CPU-bound Python, not cold I/O |
  | in-situ during a callout tick | **33.6 ms**/call |

- **Measured per-tick call counts** (150 polls, 440 objects, 132 contacts, 25 groups):

  | describe calls in one tick | 2 | 3–9 | 10–19 | 21–34 | **47** |
  |---|---|---|---|---|---|
  | ticks observed | 10 | 21 | 17 | 8 | **1** |

  Worst tick: **47 calls / 1,578.9 ms**. Median callout-bearing tick: 13 calls / ~440 ms. These show
  up directly in the poll series as `drain_ms` spikes of 388, 604, 639, 695, **1,387** ms against a
  `describe_ms` that accounts for essentially all of each spike.
- **`WorldEnrichmentCache` does not help inside a tick, and the reason is structural.** Overall hit
  rate across the run was healthy — 8,961 hits / 798 misses (92 %) — but in **every single
  callout-bearing tick, `distinct_positions == describe_calls == cache_misses`.** The cache
  (`belief/enrichment.py:632-651`) is keyed on `contact_id` plus **exact structural equality of
  `Contact.last_position`**, and a contact that was re-observed this poll has a freshly-updated
  believed position, so it misses by construction. The contacts that get spoken about are precisely
  the ones being re-observed. Confirmed directly: a **1 m nudge** to the query position costs the
  full 42 ms.
- **Risk:** this is the spiky term behind the sortie's p90 of 4.98 s. It is also the one that gets
  *worse* with exactly the thing the project is trying to improve — more groups, richer per-member
  enrichment. `BL-B26` already says "any future per-member enrichment pays 3× for nothing"; the
  measurement says the thing being paid 3× for costs 34 ms, not 0.3 ms.
- **Mitigation, cheapest first:**
  1. **Memoize `describe_position` per tick.** A tick-scoped dict keyed on quantised `(x, z)` —
     the function's own output is already coarse (nearest-feature names and distances), so a
     50–100 m quantisation changes no spoken line. This is the smallest change with the largest
     effect, because the 3× multiplier collapses to 1× without touching the scheduling loop at all.
  2. **Quantise `WorldEnrichmentCache`'s key** to the same grid instead of exact float equality.
     The cache's own docstring already accepts staleness in the confidence numbers; accepting it in
     position to a 50 m grid is the same trade, and it turns the 0 %-within-a-tick hit rate into a
     high one.
  3. Only then the scheduling-loop restructure `BL-B26` describes.
- **Action:** **NOW for (1) and (2)** — both are local, semantics-preserving at the spoken-line
  level, and each is independently testable. **Escalate the loop restructure to Architect**, which
  is what `BL-B26` already says and this review does not override. **Update `BL-B26`'s estimate**:
  its "not alarming on its own" assessment was based on a unit cost 100× too low.

### 3. The world-model LOS fallback is **not** the cause — ruled out, against `BL-B30`/`BL-B31`'s leading hypothesis

- **Location:** `perception/visibility.py:584` `check_visibility`, called once per candidate per
  poll from `perception/naked_eye_source.py:569`.
- **Measured:** the entire gate chain — cockpit mask, range/size, terrain LOS (the SRTM-grid
  fallback included), live-LOS join — costs **2.4 ms/poll** on polls with no callout and
  **16–25 ms/poll** on busy ones, for all 440 candidates. In the `cProfile` run,
  `check_visibility` is 0.30 s `tottime` of 66.7 s, and `sqlite3.Connection.execute` across the
  whole process is 1.10 s / 112,237 calls (~10 µs each).
- **Why the hypothesis was reasonable and still wrong:** the earlier gates reject almost everything
  before the LOS query is reached. `NAKED_EYE_RANGE_CAP_M` and the gaze gate are both cheaper and
  more selective, and the player bubble drops candidates before `check_visibility` is called at
  all. This is the same result as the `player-bubble` pass (measured ~1.4 % saving, not the ~77 %
  expected, for the same reason) — in this pipeline the cheap gates really are doing their job.
- **Action:** **NOTED, no change.** Record this in `BL-B30`/`BL-B31` so the hypothesis is not
  re-raised: `BL-B31`'s closing line ("if the loop is slow *because* the fallback is doing SQLite
  work per candidate, these are one problem seen from both ends") is now answered — **they are not
  one problem.** `BL-B31` remains worth doing entirely on its observability merits.

### 4. `ContactStore.ingest`'s gate scan and `ContactStore.tick`'s per-contact loop both iterate every contact ever founded — `_contacts` has no delete path

- **Location:** `belief/contacts.py:957-963` (the `passing = [...]` comprehension) and `:1088`
  (`for contact in self._contacts.values()`). `_contacts` is never deleted from — `BL-B23`
  deliberately fixed only *clustering*'s input (`:1422-1428` filters to not-`lost`), and that
  method's own docstring states the choice: *"The fix is **not** to prune `_contacts`."*
- **Measured at 142 live contacts / 440 candidates:** `ingest` 0.0–0.7 ms, `tick` 6.3–6.8 ms,
  `_cluster_contacts` 5.7–6.2 ms per poll. All small today.
- **Risk — real but second-order, and worth stating precisely because the churn finding makes it
  grow:** both of these scale with **total contacts ever founded**, which the sortie's §4 churn
  finding (`BL-B24`: 81 % of objects carried 2+ contact ids, worst 13) inflates well above the live
  count — 554 contacts for 444 real objects. Two specific costs:
  - `ingest`'s gate scan is O(observations × total_contacts) and **does not short-circuit**. The
    only distinction the code makes is `len(passing) == 1` versus not, so the scan can stop the
    moment it finds a second passing candidate, yet it evaluates `passes_gate` (a Mahalanobis test)
    against every remaining contact. Churn makes continuity fail more often, which routes more
    percepts into exactly this scan.
  - `tick`'s eight per-contact blocks run for every historical contact every poll, including ones
    `lost` an hour ago.
- **Mitigation:** short-circuit `ingest`'s comprehension at two passing candidates (a `for` loop
  with an early `break`, identical semantics); optionally prefilter by a coarse range bound before
  the Mahalanobis test. For `tick`, apply `BL-B23`'s own precedent — the per-contact blocks after
  the first need nothing from a `lost` contact that `certainty_of` has already settled.
- **Action:** **LATER.** 6 ms/poll is not the budget problem and these are not the fix for
  `BL-B30`. Do them when `BL-B24` is addressed, since that is when the total/live ratio stops
  growing. File under `BL-B23`'s lineage rather than as a new finding — this is the same shape, one
  consumer further along. **Supersedes** my own earlier memory note that read `BL-B23` as having
  fixed the total-ever-seen axis: it fixed it for clustering only.

### 5. `_is_merge_echo_of_earlier_contact` is a full contact-set scan per member per gather — so it multiplies by finding 2's 3×

- **Location:** `belief/callouts.py:566-572`, reached from `_already_reported_member_ids`
  (`:639`) and from `_render_event`.
- **Mechanism:** `any(... for other in store.contacts)` over the **whole** contact set (all ever
  founded — finding 4), calling `contacts_plausibly_same` (a Mahalanobis test against summed,
  time-inflated covariances) per pair. Per member, per gather, per tick. At 554 total contacts ×
  10 members × 3 gathers that is ~16,600 Mahalanobis evaluations in one tick.
- **Risk:** not measurable as a separate line in this harness (it sits inside the `drain_ms` that
  `describe_position` dominates at 34 ms/call, so it is noise next to that). It becomes the
  dominant term the moment finding 2 is fixed, which is the reason to record it now.
- **Mitigation:** `store.contacts` already returns a fresh `list()` copy per call
  (`belief/contacts.py:674-677`) — hoist one list out of the member loop. Filter to
  `certainty_of(...) != "lost"` and `first_seen_sim < contact.first_seen_sim` *before* the
  Mahalanobis test, both of which are cheap scalar comparisons the predicate already performs
  after the expensive one in `any`'s short-circuit order (it does not — `other.id != contact.id`
  and the two cheap tests are first, so this one is already ordered correctly; the win is the
  hoisted list and the `lost` filter).
- **Action:** **MONITOR.** Re-measure immediately after finding 2 lands. Related to `BL-B25`, which
  is about the same function's correctness window, not its cost.

### 6. The detection trace writes ~290 KB per poll — 3.55 GB for one flight is the finding, not the 4.4 ms

- **Location:** `src/detection_trace_writer.py:68` `write_poll`, fed by every
  `DetectionTraceCollector.record` call including the `PLAYER_BUBBLE` rows
  `perception/naked_eye_source.py:529` emits for candidates that were never evaluated.
- **Measured:** **4.4 ms/poll** of CPU, steady and independent of everything else (`json.dumps` +
  `dataclasses.asdict`, 3.44 M `_asdict_inner` calls in the 300-poll profile). **440 rows per poll
  — one per candidate, every candidate, every poll, whatever the outcome — at 659 bytes/row = 290
  KB/poll.** At 1 Hz over 70 minutes that is ~1.2 GB; the real sortie's rows are fatter (3.55 GB /
  1.64 M rows = 2.2 KB/row) because real rows have the `None` fields populated.
- **Risk:** the CPU cost is fine. The **volume** is a real operational problem and the sortie proved
  it: a 3.55 GB file that is *appended to, not replaced*, so the analysis had to locate a
  byte offset (2,448,471,603) to find this sortie's region at all. A debug artifact that costs a
  gigabyte per flight and cannot be addressed by sortie is one that stops being read.
- **Mitigation, in order of value:**
  1. **Roll the file per run** (timestamped filename, or truncate on open rather than `"a"`). This
     alone removes the byte-offset archaeology.
  2. **Drop the `PLAYER_BUBBLE` rows by default**, behind a flag. They are 60–80 % of the volume at
     realistic spreads and carry one bit of information ("further than 10 km"), which the
     `true_range_m` on any other row already implies.
  3. Omit `None` fields from the JSON (`asdict` emits all 25). Cheap, roughly halves the bytes.
- **Action:** **LATER**, but (1) is nearly free and would have saved real analysis time on this very
  sortie. Not a `BL-B30` blocker.

### 7. The poll body makes five sequential HTTP round trips with no connection reuse, each with a 2.0 s timeout — the median is cheap, the worst case is ~20 s

- **Location:** `src/aircraft_client.py:79` (`_DEFAULT_TIMEOUT_S = 2.0`), `:241`/`:260`
  (`urllib.request.urlopen`, a fresh connection per call);
  `src/belief/audio_client.py:38` (`_DEFAULT_TIMEOUT_S = 5.0`).
- **Measured round trips per poll** (counted in the harness): `telemetry`, `world_objects`,
  `unit_velocity`, `line_of_sight`, `petrovich_indication` — **5 GETs every poll**, plus
  `post_look_direction` on gaze change (observed on 50 % of polls), plus `/f10_commands/poll` and
  `/transcripts/poll` when those flags are on, plus one `/text/push` per overlay event.
- **Measured cost:** against a real loopback `ThreadingHTTPServer` with a 51 KB world-objects
  payload, **0.67–0.73 ms per GET, 3.39 ms for all five.** aircraft-layer serves HTTP/1.0, so the
  connection closes per request and `urllib` re-handshakes each time; on a LAN that is ~2 RTT per
  call rather than ~0, so budget ~5–10 ms, not 3.4.
- **Risk:** **not the median cause** — 10 ms against a 330 ms poll. But the **timeouts are the tail
  cause.** Five sequential 2.0 s timeouts is 10 s of blocking in one poll body, and with
  `--speech-input` (5.0 s) and `--f10-commands` on, a fully-wired poll's worst case is past 20 s,
  all on the one thread. That is the right order of magnitude for the sortie's p90 of 4.98 s, which
  nothing in the CPU measurements reaches. It is not provable from the logs the sortie produced —
  see "What could not be measured".
- **Mitigation:** drop the per-call timeout for the `/latest`-style reads to ~0.3–0.5 s. These are
  cache reads from a local-ish service; a read that takes 2 s has already missed its poll and the
  correct behaviour is to skip the poll, which the loop's existing `except` already does
  gracefully. Reusing connections (one `http.client.HTTPConnection` per client, HTTP/1.1
  keep-alive) is a larger change for a smaller win — worth it only if a LAN measurement shows the
  handshakes mattering.
- **Action:** **NOW for the timeout values** (a constant change, and the tail is what the pilot
  actually experiences as Petrovich going quiet). **MONITOR** connection reuse.

### 8. Every spoken callout blocks the poll thread on TTS synthesis

- **Location:** `belief/crew_console.py:2247` `_print` → `AudioAdapterClient.push_speech`
  (`belief/audio_client.py:71`, 5.0 s timeout) → `audio-adapter/src/server.py:190`
  `audio = engine.synthesize(text)`.
- **Mechanism:** the adapter's `POST /speak` handler **synthesizes the whole line and delivers it
  before responding.** `_print` is called from `drain_events`, which runs inside the poll body. So
  the poll loop waits out speech synthesis, synchronously, for every line Petrovich says.
- **Risk:** credible and architecturally wrong — this is exactly the project's own
  "offload heavy work asynchronously, never block the main thread" rule, inverted. Magnitude is
  **not measured** (no TTS engine was exercised in this sandbox), but a sentence of local TTS is
  conventionally 0.3–2 s, and the 5 s timeout is the ceiling. The sortie spoke 63 lines in
  70 minutes, so this is not the median poll — it is a per-utterance stall, and the polls it stalls
  are the ones immediately after Petrovich has noticed something, which is the worst possible time
  to stop perceiving.
- **Mitigation:** make `/speak` enqueue-and-return on the adapter side (synthesize on the adapter's
  own worker), or push speech from a body-layer worker thread. The first is better — it keeps the
  seam's shape and fixes it for every future client. Either way `push_speech`'s raise-on-failure
  contract is preserved; only the *transport* becomes fire-and-forget.
- **Action:** **NOW to measure, then almost certainly NOW to fix.** The measurement is one line:
  time `push_speech` in the poll loop's new instrument (finding 0's instrument already has the
  hook point). This crosses into `audio-adapter`, so **escalate the fix's placement to Architect**
  rather than improvising it in body-layer.

### 9. Unbounded per-sortie growth — four structures with no prune path

All four are memory, not CPU, and none is a 70-minute problem. Recorded as one finding because they
are one pattern and the right time to deal with them is together.

| structure | location | growth |
|---|---|---|
| `ContactStore._observations` | `belief/contacts.py:647` | one entry per observation ever; measured **5,992 at poll 480** and rising linearly — extrapolates to ~50 k per sortie |
| `Contact.contributing_observation_ids` | `belief/contacts.py:391`, appended at `:557`/`:630` | unbounded per contact; sums to the same total |
| `ContactStore._observation_id_to_contact_id` | `belief/contacts.py:662` | documented as "never pruned or re-keyed", and correctly so — object permanence depends on it |
| `WorldEnrichmentCache._cache` | `belief/enrichment.py:632` | one entry per contact ever, each holding a `list[SemanticFact]` |
| `DetectionTraceCollector._last_by_object_id` | `perception/detection_trace.py:200` | never cleared when `records` is; bounded by distinct objects (444), so trivial |

- **Measured consequence:** `observation_id_to_contact_id(store)` (`detection_trace_writer.py:99`)
  rebuilds its whole mapping from scratch **twice per poll** (once for each writer) and is
  **0.03 ms at 538 observations**. Extrapolating to 50 k it is ~2–3 ms × 2. Real but small; the
  function's own docstring already accepts this ("an accepted cost for a single-sortie debug
  artifact, not a standing index").
- **Action:** **MONITOR.** No action at 70 minutes. If sortie length grows materially, the cheapest
  fix is to maintain `observation_id_to_contact_id` incrementally in `ingest` (it already writes
  `_observation_id_to_contact_id` on the same line) rather than rebuilding it, and to cap
  `contributing_observation_ids` to the most recent N — `belief/enrichment.py:545` already reads it
  `reversed`, i.e. recent-first, so a cap is behaviour-preserving for its one real consumer.

### 10. Small, cheap cleanups — correct to note, wrong to prioritise

- **`ContactStore.events` copies the whole event list to take its length.**
  `logger.py:540`'s `events_before = len(self.store.events)` goes through the property at
  `belief/contacts.py:686-690`, which returns `list(self._events)`. A second full copy follows at
  `:543` when `overlay_client` is set. Microseconds at realistic event counts. Fix by exposing a
  count, or by slicing `_events` directly — but this is a readability fix, not a performance one.
- **`ContactStore.observations` returns `dict(self._observations)`** — a full copy of the unbounded
  observation log, taken at `logger.py:570` purely for a `len()`. **Not on the live path**:
  `--crew-text` constructs the runner with `output=None` (`logger.py:2012`), so the `print` is
  skipped. It *is* on the `belief/tools.py:710` path (`get_situation`), which the REPL thread
  calls, not the poll thread. **NOTED**, no action.
- **`_look_targets` builds a `LookTarget` for every contact ever seen, every poll**
  (`logger.py:676`, called unconditionally from `run_once` via `decide_optic`), each calling
  `effective_attention(..., store.areas)`. Consistent with my earlier measurement of
  `optic_policy.decide` (0.08 / 0.45 / 1.46 ms at 55 / 300 / 1000 contacts). **MONITOR**, same
  trigger as finding 4.
- **`WorldObjectCandidate.from_dict` calls `wgs84_to_dcs` per object per poll**
  (`perception/association.py:228`) — 440 scalar `pyproj` transforms where
  `coordinates.dcs_to_wgs84_array` exists. Measured at 0.48 ms/poll total across all 440 in the
  profile (`from_dict` 0.186 s `tottime` over 132,000 calls), because the `Transformer` is already
  cached per theatre (`world-model/src/coordinates/__init__.py:32-47`). **NOTED, no action** — the
  vectorised form would save well under a millisecond and would couple this call site to numpy
  array plumbing for nothing.

---

## What could not be measured, and the instrument each needs

1. **LAN latency and timeout frequency on the aircraft-layer seam** (finding 7). The harness is
   in-process; loopback is a floor. **Needs:** the poll-loop instrument recording per-endpoint wall
   time and a count of `_is_connection_loss` / timeout events per N polls. Without it, "5 × 2.0 s
   timeouts explain the 4.98 s p90" stays a well-shaped hypothesis, not a finding.
2. **TTS synthesis time inside `push_speech`** (finding 8). No TTS engine in this sandbox.
   **Needs:** the same instrument, timing `push_speech` separately. One sortie answers it.
3. **The real distribution of in-bubble candidate count.** Finding 1's cost is quadratic in it, and
   every number above assumes 440. The sortie logged 444 *distinct objects over 70 minutes* and
   "median 43 units in a LOS result", which are different quantities from "candidates inside the
   10 km bubble this poll" — the one that drives the cost. **Needs:** a per-poll count of
   `len(candidates)` at `naked_eye_source.py:520`. If the real median is 150 rather than 440,
   finding 1's median contribution is ~70 ms, not 300 — still the largest term, but the fix's
   urgency changes. **This is the single most valuable number the instrument can return**, and it
   is one `len()`.
4. **Whether the 193 s gap was a pause.** Not diagnosable from body-layer at all; it needs the
   instrument's wall-clock span against sim-time span in the same line. Stated above as "almost
   certainly a sim-time artifact" — that is reasoning from the fact that no mechanism here can
   block for three minutes, not a measurement.
5. **`perception/motion.py:91`'s "objects arrive at 5 Hz" assumption.** A correctness question, not
   a cost one, surfaced by this review's headline correction. **Belongs to a debugger**, not here.

## What was ruled out

- **The world-model LOS fallback** — finding 3, measured, explicitly against `BL-B30`'s leading
  hypothesis.
- **`_cluster_contacts` / `GroupStore.reconcile`** — 5.7–6.2 ms/poll at 142 contacts, consistent
  with the earlier group-cohesion measurements (0.6 ms @ 52, 8.4 ms @ 200). `BL-B23`'s fix is
  holding. Not a contributor at this scale.
- **`store.ingest` / `store.tick`** as *present* costs — 0.7 ms and 6.5 ms respectively. The
  algorithmic shape is a future risk (finding 4), not a current one.
- **The trace writer's CPU** — 4.4 ms/poll. Its volume is the finding, not its time.
- **Per-poll coordinate transforms** — under 0.5 ms/poll, the transformer is cached.
- **Lock contention** — there is none to find. The poll loop is one thread owning a thread-affine
  `sqlite3.Connection`, the REPL builds its own, and `brain_client`'s poll runs on a third thread
  with its own queue. The thread-affinity discipline (`logger.py`'s module docstring, BL-2 Stage 6
  and BL-5) is doing what it was built for.

## Verdict

**NEEDS MITIGATION.**

`BL-B30` is diagnosed. Two changes account for essentially the whole miss, and both are measured:

1. **Hoist the per-candidate terms out of `group_salient_ids`' pair loop** and add
   `@lru_cache` to `profile_for` — **8.1× measured, output asserted identical**, taking the median
   poll from ~330 ms to ~70 ms (finding 1). **NOW.**
2. **Memoize `describe_position` per callout tick and quantise `WorldEnrichmentCache`'s position
   key** — removes a measured 1.58 s worst-case stall and collapses `BL-B26`'s 3× multiplier
   without restructuring the scheduling loop (finding 2). **NOW.**

Alongside them, two one-line changes worth taking in the same pass: **drop the aircraft-layer
`/latest` timeouts to ~0.3–0.5 s** (finding 7) and **roll the detection trace per run** (finding 6).

**Also required, and not an optimisation:** fix `BL-B30`'s stated premise. There is no 5 Hz
configuration; the three docstrings claiming one should be corrected, the backlog entry's
"seven times slower" and its decay-constant worry should be withdrawn, and
`perception/motion.py:91`'s 5 Hz assumption should go to a debugger.

**Escalated to Architect, not improvised here:** `BL-B26`'s scheduling-loop restructure (after the
memoization makes it optional rather than urgent), the O(n²) spatial pruning in
`group_salient_ids` if 800+ candidate missions are expected, and where the async TTS push belongs
across the body-layer/audio-adapter seam (finding 8).

**The instrument still has to be built.** Everything above is a synthetic-scale measurement; the
one number that could change the ranking is the real per-poll in-bubble candidate count, and it is
a single `len()` away.

---

## Reproducing the measurements

Four scripts, written to the session scratchpad rather than the repo (this review adds no code to
`src/` or `tests/`). All were run with
`PYTHONPATH=src:../world-model/src` from `body-layer/`, against
`world-model/data/world-model/syria-full.sqlite`.

1. **`harness.py`** — a `FakeAircraftClient` duck-typed against `AircraftLayerClient` (zero
   network) serving a static field of N objects placed uniformly in a disc of a given radius around
   a Latakia-area ownship, plus a real `ConsolePerceptionRunner` built through `logger._build_sources`,
   a real `CrewConsole` with `NullBrainClient`, and both real writers. Times `run_once` /
   `truth_write` / `trace_write` / `drain_events` per poll, optionally under `cProfile`.
2. **`series.py`** — wraps `group_salient_ids`, `check_visibility`, `ContactStore.ingest`/`tick`,
   `_cluster_contacts`, `describe_position`, `nearest_feature` and `profile_for` at their
   importing call sites and emits a per-poll CSV. This is what separated the 300 ms flat term from
   the spiky one. Its `--static-ownship` mode holds position so contacts accumulate.
3. **`bench_salience.py`** — the finding-1 fix comparison. Builds candidate sets at
   n ∈ {55, 128, 250, 440, 800}, times the shipped `group_salient_ids` against an `lru_cache`'d
   `profile_for`, against a hoisted reimplementation, and against both, and **asserts all four
   return the same `frozenset`** at every n.
4. **`bench_wm.py`** / **`bench_callout.py`** / **`bench_http.py`** — `describe_position` and
   `nearest_feature` unit costs on `syria-full` (cold-distinct, warm-repeat, 1 m-nudge);
   `describe_position` calls per `CalloutScheduler` tick with `WorldEnrichmentCache` hit/miss
   counts; and the five-GET poll round trip against a real loopback `ThreadingHTTPServer`.

The one thing to rebuild carefully if these are re-run: **`series.py` patches module-level names at
the importing module** (`naked_eye_source.group_salient_ids`, not
`group_salience.group_salient_ids`), because `from x import y` binds a separate reference. Patching
the defining module measures nothing and reports zeros, which looks exactly like "this is cheap".
