# Performance Review — `feature/bl11-tick-cost`

**Branch:** `feature/bl11-tick-cost`, tip `8fa2ad6` ("Document the widened degrade guard and the
`~` expansion").
**Verified at:** `8fa2ad6`. The worktree was created at `19143fa`, **42 commits behind the named
tip** — the sixteenth consecutive agent tonight to land behind it. `19143fa` was a strict
ancestor and the tree was clean, so per `AGENTS.md` rule 4 the worktree branch was fast-forwarded
(`git merge --ff-only feature/bl11-tick-cost`) and `git rev-parse HEAD` re-checked before a single
number was taken.
**Source of claims:** `body-layer/research/2026-10-05-performance-review.md` findings 1, 2, 6;
`plans/bl11-tick-cost/implementation.md`.

This is the once-per-feature pass before DoD, and the task framed it unusually: the branch *is*
performance work derived from a measured note, so the job was to check whether it delivered what
it claimed. **It did, and by more than it claimed in two places and less in one.**

**Everything below is measured on this tip.** Harnesses live in the session scratchpad, not in
`src/` or `tests/`. Each carries a **"can this harness fail" probe** asserted before any timing is
reported, because three tests on this branch passed for the wrong reason tonight and a benchmark
that cannot fail is the same defect wearing different clothes. One of those probes genuinely
tripped (the enrichment-cache counter, on a first smoke run), which is how we know the instrument
was live rather than silently measuring nothing.

---

## Verdict

**APPROVED — MONITOR.**

**`BL-11`'s own headline number is met: the realised poll period is 1.000 s median against the
1.33 s the note measured, at a 1.0 s setting.** Median poll work is **12.6 ms**, down from the
note's ~330 ms. `group_salient_ids`, the note's single largest cost at a flat ~300 ms every poll,
is now **1.1 ms median / 5.5 ms max** — it is no longer a term in the budget. 2.0 % of polls still
overrun 1.0 s, every one of them a `describe_position` spike, and that residual belongs to
`query.describe`'s unit cost rather than to anything on this branch.

Checks pass: `ruff format` 118 files unchanged, `ruff check` clean, `mypy src` clean on 54 files,
`pytest tests -q` → **1516 passed, 4 xfailed**, pytest `rootdir` confirmed as the worktree.

**One change is required and it is a docstring, not code.** `perception/group_salience.py:105`
asserts the hoist "is that finding's measured 8.1x"; it is **5.1×**, and the implementation log's
explanation for the gap is wrong. Finding 1 locates the missing factor exactly. The accompanying
code change is **not** worth making — the measured poll data settles that — so the request is one
line of prose.

---

## The headline question, answered

| | note, pre-branch | measured, this tip |
|---|---|---|
| poll work, median | ~330 ms | **12.6 ms** |
| poll work, p90 / max | — / 1,736 ms | 98.6 / 1,642 ms |
| **realised period, median** | **1.33 s** | **1.000 s** (mean 1.008, max 1.642) |
| polls overrunning 1.0 s | — | **2.0 %** (6 / 300) |
| `group_salient_ids` | ~300–318 ms **every poll** | **1.1 ms** median, 5.5 max |
| `describe_position` per callout tick | median 13 calls / ~440 ms, max 47 / 1,579 ms | **median 3 / 256 ms, max 20 / 1,615 ms** |
| enrichment-cache hit rate *within a callout tick* | **0 %** | **89.7 %** |

440 objects, 10 km bubble, 1 s steps, 300 polls, real `syria-full.sqlite` (738 MB), fake
in-process aircraft client — so every CPU figure is a **floor** for the real thing, exactly as the
note's were.

**The note's "single most valuable number" is now measured, and it was out by 2×.** Candidates
handed to `group_salient_ids` is **median 232, min 32, max 434** at 440 objects — not 440. The
player bubble sheds most of the field as the ownship tracks away from the clump centroid. The note
said this number was one `len()` away and that if it came back at 150 rather than 440 "finding 1's
median contribution is ~70 ms, not 300 — still the largest term, but the fix's urgency changes."
It came back at 232, and the urgency did change: it is what makes finding 1's residual not worth
chasing.

**Headroom at double the population** (800 objects, 200 polls): work median 35.5 ms, p90 449.3,
max 2,493; period median 1.000 s, mean 1.023, max 2.493; 3.0 % of polls overrun; candidates median
570; `group_salient_ids` median 8.1 ms. The quadratic term is comfortable at twice the sortie's
scale.

---

## The tests for the two load-bearing stages have teeth — checked by mutation, not by reading

Each stage's mechanism was reverted in `src` in place, the suite run, and the file restored from a
scratchpad copy (`git status --porcelain` afterwards shows only this review's own files; the suite
is back to 1516 passed, 4 xfailed):

| mutation | result |
|---|---|
| `enrichment.py` `get_or_compute`: grid key → the old exact `(x, z, alt_m)` tuple | **1 failed** — `test_cache_hits_after_a_one_metre_nudge`, the note's own reproduction |
| `logger.py` `_wait_for_next_tick`: back to `wait(poll_interval_s)` + queued deadline | **3 failed** — `..._sleeps_only_the_remainder_of_the_interval`, `..._does_not_sleep_when_the_work_overran`, `..._drops_missed_ticks_rather_than_queueing_them` |

Stage 2 is pinned differently — by output equality against a local reference copy rather than by
timing — and the round-2 review already made that non-tautological by replacing the imports with
copies. My own benchmark re-verified it the same way: tripling `GROUP_COHESION_GAP_UNIT_WIDTHS`
breaks the equality, asserted before any timing was reported.

---

## Findings

### 1. Stage 2's "8.1×" is 5.1×, the implementation log's explanation for the gap is wrong, and the missing 1.6× is one more per-candidate quantity left inside the pair loop — but the measured poll data says leave it there

- **Location:** `body-layer/src/perception/group_salience.py:181-191` (the hoisted pair loop) and
  `body-layer/src/perception/clustering.py:195-196` (`angular_separation_rad`'s observer-relative
  difference vectors). The false claim is at `group_salience.py:105` and in
  `plans/bl11-tick-cost/implementation.md`, "Notable Discoveries", second bullet.

- **What reproduces.** The implementer's 5.0× reproduces exactly. Against a verbatim pre-Stage-2
  reference (the test file's `_reference_group_salient_ids`, with `profile_for.__wrapped__`
  restoring the uncached baseline), output asserted bit-identical at every row:

  | n | range band | resolvable | pairs | pre-Stage-2 | +`@cache` only | shipped | speedup |
  |---|---|---|---|---|---|---|---|
  | 440 | 1–11 km | 145 | 10,440 | 24.5 ms | 17.8 | 5.0 | 4.9× |
  | 800 | 1–11 km | 229 | 26,106 | 61.4 ms | 44.2 | 12.2 | 5.1× |
  | **440** | **0.5–4 km** | **342** | **58,311** | **134.2 ms** | 98.5 | **26.4** | **5.1×** |
  | 800 | 0.5–4 km | 582 | 169,071 | 393.2 ms | 285.3 | 76.6 | 5.1× |

- **The O(resolvable²) half of the explanation is right, and I confirmed it.** The note's 215 ms at
  ~96 k pairs is **2.24 µs/pair**; my dense-band baseline is 134.2 ms at 58,311 pairs =
  **2.30 µs/pair**. Same unit cost, different pair count. The absolute numbers reconcile to within
  3 %, and the implementer was correct that its scene resolved 145 of 440.

- **The ratio half is wrong, and that is the finding.** The log says *"the ratio rises with pair
  count — so the sortie should see closer to the note's figure than to this one."* It does not. The
  ratio **saturates at 5.1× from ~2,500 pairs upward** and is still 5.1× at 169,071 pairs, nearly
  double the sortie's ~96 k. A flight will come back at 5×, not 8×, and the stated reason for
  expecting otherwise does not hold.

- **Mechanism, located.** Stage 2 hoisted four per-candidate quantities out of the pair loop and
  left the fifth in. `angular_separation_rad(observer, target_i, targets[j])` recomputes
  `a - observer` and `b - observer` on **every pair**, so candidate *i*'s observer-relative vector
  is rebuilt *n−1* times — exactly the recomputation shape Stage 2 exists to remove. Measured by
  carrying those vectors in the `_resolvable_terms` pass and keeping `atan2(|cross|, dot)` verbatim
  so the float result is bit-identical rather than merely close (equality asserted):

  | pairs | shipped | + difference vectors hoisted | further gain | total vs pre-Stage-2 |
  |---|---|---|---|---|
  | 58,311 | 26.5 ms | 16.7 ms | 1.59× | **8.0×** |
  | 169,071 | 76.9 ms | 47.9 ms | 1.61× | 8.2× |

  **8.0× at 58 k pairs is the note's 8.1×.** The note's prototype hoisted the difference vectors;
  the shipped code did not, and that single omission is the entire gap. For completeness, inlining
  `_cohesive_from_terms` instead buys only 1.1×, so the per-pair function call is *not* the problem.

- **Risk: none, and the poll measurement is what settles it.** `group_salient_ids` is **1.1 ms
  median / 5.5 ms max** in situ at real candidate counts (median 232, not 440). The further 1.6×
  would save about **0.4 ms of a 12.6 ms poll**, and 8.1 ms → 5 ms at 800 objects. That is a
  rounding error against a 1,000 ms period.

- **Action:** **NOW for the claim. The code change is explicitly NOT worth making.**
  - **Required:** correct `group_salience.py:105` and the implementation log. "Measured 8.1x" is
    false of the code it annotates, and this project spent two review rounds tonight deleting
    docstrings that claimed more than the code does — this one is the performance claim itself.
    Replace it with the measured 5.1×, and say what was left in the loop and why it is being left
    there. Otherwise the next person reconciling a flight measurement against the plan re-derives
    this from scratch, which is precisely what happened here.
  - **Declined, with the number:** hoisting the difference vectors. 1.6× of a term that is now
    1.1 ms. Recording it so it is not re-discovered as a surprise, not asking for it.
  - **Unchanged and still the Architect's:** the loop is O(n²) over the resolvable set. Spatial
    pruning is an algorithm change, and the note already escalated it.

### 2. Stage 1 delivers the configured period exactly, and the overrun policy cannot busy-spin

- **Location:** `body-layer/src/logger.py:1003-1048` (`_wait_for_next_tick`), called at `:1245` and
  `:1621`.
- **Measured against the pre-Stage-1 shape directly**, not inferred — `stop_event.wait(interval)`
  with a queued deadline, driven side by side with the shipped function (interval scaled to 200 ms
  for runtime; the shape is identical):

  | injected work | pre-Stage-1 period | Stage 1 period |
  |---|---|---|
  | 12.6 ms (the measured median) | 222.0 ms | **200.0** |
  | 100 ms | 310.1 ms | **200.0** |
  | 330 ms (the note's median, an overrun here) | 540.1 ms | **330.0** |

  Exactly `max(interval, work)` to within 0.1 ms. Independently confirmed at a 1.0 s setting with
  70 / 330 / 900 ms of work, all three realising 1.000 s median.
- **The overrun policy is sound and does not spin.** Started with a deadline five intervals in the
  past and zero work, five iterations took 4.010 s with four full-interval sleeps: the function
  re-bases **once** on the clock and then sleeps normally. Debt is not queued, and the queueing
  alternative is distinguishable by this measurement (asserted, +0.410 s apart), so the harness is
  not vacuous.
- **The one real cost is the one the docstring already owns**, and it owns it honestly: while work
  exceeds the interval, `stop_event.wait` is never called at all and the thread runs back-to-back
  with no voluntary yield, on a Mac that also hosts Ollama and the brain layer. The old
  `wait(poll_interval_s)` tail was an accidental 1.0 s floor that hid this. I agree with not
  flooring it — a floor would re-introduce a smaller `work + interval` in exactly the regime the
  stage exists to fix — and with naming `--poll-interval-s` as the knob. Measured frequency of that
  regime: **2.0 % of polls at 440 objects, 3.0 % at 800**, all of them single `describe_position`
  spikes rather than sustained load, so it is a tail behaviour and not an operating point. Shutdown
  stays prompt because `stop_event.is_set()` is checked at the top of every iteration.
- **Action:** **APPROVED, no change.**

### 3. Stage 3b works — 0 % → 89.7 % within-tick — and the note's own diagnostic signature still reads "true", which will mislead the next reader

- **Location:** `body-layer/src/belief/enrichment.py:689-706` (`get_or_compute`), `:654-665`
  (`_cache_position_key`), `:617-651` (the constant and its reasoning).
- **The fix is correct in shape and measured effective.** The key is
  `(floor(x/50), floor(z/50), floor(alt/50))` — integer cell indices, not rounded floats, so it
  cannot reintroduce the float-equality miss it exists to remove. Overall **8,161 hits / 189 misses
  = 97.7 %**; **within the 37 callout-bearing ticks, 1,651 hits / 189 misses = 89.7 %**, against the
  note's measured **0 %**. The miss-by-construction defect is gone.
- **The trap, and it is worth writing down.** `distinct_positions == describe_calls == cache_misses`
  — the exact equality the note used to *diagnose* the defect — **still holds in 37 / 37
  callout-bearing ticks.** It no longer means what it meant. Before, it held *with zero hits*, i.e.
  the cache did nothing; now it means each remaining miss is a genuinely distinct 50 m cell that
  genuinely needs a new call. **Anyone re-running the note's own diagnostic will see the same
  equality and may conclude Stage 3b failed.** The discriminator is the hit count beside it, never
  the equality alone.
- **Stage 3a is settled, and it is not worth building — I was wrong about the consequence.** My
  mechanical reading was that a per-contact key can never collapse two different contacts in the
  same cell, so 3a is not subsumed. That mechanism is right and the consequence I drew from it is
  wrong: measured, there are **189 describe calls against 187 distinct 50 m cells — 2 redundant,
  1.1 %** (at 800 objects: 325 calls, 320 cells, 1.5 %). Stage 3b, being per-`contact_id`, already
  absorbed `BL-B26`'s 3× same-contact multiplier; what remains is distinct positions, which no memo
  at this grid can merge. **The round-1 reviewer's call to omit 3a was correct**, and this
  quantifies it. It also meets the `sortie-refinements` reviewer's point from the other side:
  separated group members occupy distinct cells by construction, so neither 3b nor 3a collapses
  them — but there is nothing left there to collapse.
- **The remaining spike is `describe_position`'s unit cost, and it is not body-layer's.** 84.6 ms
  per call in situ. Independently, standalone on `syria-full.sqlite`: 57.4 ms median over 40
  distinct positions within 9 km, 57.7 ms for the same position ×20, 57.5 ms for positions 1 m
  apart, 58.3 ms within one 50 m cell. **Every shape costs the same** — no internal memo, no I/O
  warming — which confirms the note's CPU-bound diagnosis and means a cache hit saves the full unit
  cost while the grain only decides how often one is available. ~13 misses × ~85 ms is the whole of
  the 1.6 s worst poll. **Further work on this tail belongs in `query.describe`, not in
  body-layer's caching**, and that is a world-model question, not a `BL-11` one.
- **A staleness axis the constant's comment enumerates consumers for and then misses.** The comment
  carefully bounds the error at the cell diagonal (~70.7 m horizontal, ~86.6 m in 3D) and names
  `describe_position`, `relative_geometry` and `terrain_divide_qualifier`. But a hit also freezes
  the cached `world_position`, and `_terrain_aware_world_position` (`enrichment.py:553-614`) derives
  its **observer** — the fixed-point solve's starting vantage — from the most recent contributing
  `Percept`. Under the old exact-equality key a hit implied `last_position` was bit-identical, which
  in practice implied no new percept had been fused and therefore the same observer. Under a 50 m
  cell a hit can occur *after* new percepts have arrived from a different vantage, so the
  quantisation widens staleness along the observer axis too. **Unquantified**, and I will not guess:
  the instrument is one diff of the cached `world_position` against a freshly computed one on each
  hit, over a run. This is a consequence of a performance change rather than a performance risk, so
  it belongs to the Reviewer.
- **Action:** **APPROVED — MONITOR.** No change requested.

### 4. Stage 5 halves the real log — the note's own "2.2 KB/row" premise was wrong, and the larger half of the volume is still on the table

- **Location:** `body-layer/src/detection_trace_writer.py:163-186` (`_entry_to_dict`),
  `body-layer/src/run_log_paths.py`, wired once at `logger.py:2154`.
- **Measured against the real artifact**, which is on this machine:
  `/Users/sg/dcs-detection-trace.jsonl`, the 3.55 GB 2026-10-05 sortie, sampled 20,000 rows from
  the note's own byte offset 2,448,471,603 and re-serialised under the shipped omission rule.
  - **Real rows average 622 B, not the 2.2 KB/row the note claims.** The note divided 3.55 GB by an
    assumed 1.64 M rows; at 622 B the file holds ~5.7 M rows, so that per-row figure is wrong — and
    so is the premise it carried, that *"real rows have the `None` fields populated"*. Real rows
    carry a **mean 12.7 omittable null fields of 25 keys**, essentially the same as the synthetic
    case.
  - **So the None-omission saves 50.3 % on real rows** (622 → 309 B). That 3.55 GB sortie would
    have been **~1.76 GB**. Synthetic measurement agrees: 292 B/row and 125.3 KB/poll at 440
    objects, against the note's pre-change 659 B/row and 290 KB/poll. My own per-row check from the
    other direction: 638 → 271 B (58 %) on a sparse `PLAYER_BUBBLE` row, 0 % on a hypothetical
    fully-annotated one — and the real data says the fully-annotated row barely occurs.
  - **64.7 % of real rows are `player_bubble`** (gaze 31.9 %, range-or-size 3.4 %), confirming the
    note's 60–80 % estimate. That mitigation — drop them behind a flag — was **not** in Stage 5's
    scope. Taking it would move ~1.76 GB to **~0.6 GB**, so the larger half of the remaining volume
    is still available for the cost of one flag.
- **Per-run rolling is the item that mattered and it works** — one `_per_run_log_paths` call ahead
  of both the `--console` and `--crew-text` branches, one stamp across all three logs, `mkdir` plus
  per-log degrade on `OSError`/`ValueError`, and a `"<label>: writing <path>"` stderr line each. The
  byte-offset archaeology is gone. `run_log_paths.py` states the timestamped-vs-truncate trade and
  owns its cost in as many words (*"a new name per run costs disk the user can see and delete"*) —
  which is ~1.8 GB per sortie with no retention policy, a pruning decision someone makes by hand.
- **Second-order, noted not actioned:** `observation_id_to_contact_id` still rebuilds its whole
  mapping twice per poll (`detection_trace_writer.py:149-159`); measured trace-writer cost is
  3.6 ms/poll median, in line with the note's 4.4 ms. Unchanged by this branch and its own docstring
  accepts it.
- **Action:** **APPROVED — MONITOR.** Worth correcting the note's 2.2 KB/row figure where it is
  cited, since it understated this stage's benefit and misattributed the cause.

### 5. `@cache` on `profile_for` is unbounded, and that is fine — with one condition worth writing down

- **Location:** `body-layer/src/perception/object_model.py:557-558`.
- The note asked for `@lru_cache`; `@cache` is `lru_cache(maxsize=None)`, i.e. no eviction. The key
  is `object_type`, taken verbatim at `association.py:242` from the DCS payload's `object_type` — a
  *type* name from the DCS unit catalogue, bounded at a few hundred to a few thousand strings, each
  mapping to one `frozen=True, slots=True` dataclass. Its measured contribution is 1.36× of the
  pre-change pair-loop cost, and the hoist subsumes most of that inside `group_salience` — the
  note's point that ~40 k of the remaining per-poll calls come from `clustering.py` and
  `visibility.py` is why it still earns its place.
- **The condition:** this is bounded only while `object_type` carries a type name. If that field
  ever carried a per-unit string (a unit name, a DCS runtime id) the cache would grow one entry per
  unit per sortie, with no eviction and nothing to notice it. Not asking for a `maxsize` — the
  field's provenance is a single `str()` of a documented DCS type and changing it would be visible.
- **Action:** **NOTED, no change.**

---

## What could not be measured, and the instrument each needs

The note's own section is the model for this, and its most valuable line — that the real per-poll
in-bubble candidate count was one `len()` away — is now answered (median 232 at 440 objects, 2×
below what every finding-1 figure assumed). What is left:

1. **TTS blocking inside `push_speech`** (note finding 8). No TTS engine in the sandbox and the
   harness's `CrewConsole` had no speech client. **Needs** the in-flight instrument timing
   `push_speech` separately. Unchanged from the note, and still the one architectural violation of
   the project's own "never block the main thread" rule.
2. **LAN latency and the five 2.0 s timeouts** (note finding 7). The fake client is in-process, so
   every CPU number here is a floor. **Needs** per-endpoint wall time plus a timeout /
   `_is_connection_loss` count per N polls. This remains the only credible explanation for the
   sortie's 4.98 s p90, which nothing in the CPU measurements reaches — and the timeout change the
   note put in its "worth taking in the same pass" list was not taken, so **the median is fixed and
   the tail is not**.
3. **The within-tick cache hit rate under manoeuvring targets.** The harness's objects are static,
   so believed positions settle and cross 50 m cells rarely; **89.7 % is an upper bound**. The
   direction is robust — the pre-change exact-float key could never hit for a re-observed contact
   regardless of motion — but the magnitude needs a sortie. **Needs** a hit/miss counter on
   `get_or_compute`: two integers.
4. **The poll instrument itself** — the note's finding 0, still unbuilt, and now the thing that
   confirms all of the above in flight. Stage 1 made the configured period mean what it says;
   nothing yet reports what the loop realises with a real LAN and a real TTS engine in the path.
5. **The observer-axis staleness Stage 3b widened** (finding 3). One diff of cached against
   freshly-computed `world_position` on each hit.

## What this branch does not change, and should not be read as having changed

- `belief/callouts.py` — the 3× gather multiplier is intact at `:823`, `:833` →
  `speech.py:1480`/`:1681`, `:891` → `speech.py:1357` (Stage 3a, deliberately omitted, and finding
  3 now says correctly omitted).
- `ContactStore.ingest`'s non-short-circuiting gate scan and `tick`'s per-contact loop over every
  contact ever founded (note finding 4, **LATER**).
- `_is_merge_echo_of_earlier_contact`'s full contact-set scan per member per gather (note finding 5,
  **MONITOR**). The note's trigger was "re-measure immediately after finding 2 lands"; finding 2 has
  now landed and `drain_events` is 2.1 ms median, so the trigger has fired and come back clean at
  this scale.
- The aircraft-layer timeouts and the synchronous TTS push (note findings 7 and 8).
- `perception/motion.py:91` is the one surviving "5 Hz" claim in `src`, deliberately exempted as a
  behavioural claim for a debugger (`BL-B34`). Verified by grep: nothing else remains.

---

## Change request

**One, and it is a docstring.** `perception/group_salience.py:105` claims the hoist "is that
finding's measured 8.1x"; it is 5.1×, and the implementation log's explanation for the gap will
mislead the next person who reconciles a flight measurement against the plan. Per `AGENTS.md` this
re-enters the loop as Implementer → Reviewer → DoD, however small it looks — "reorder two lines" is
exactly the shape of change that gets applied without a second reading.

**No code change is requested.** The accompanying 1.6× hoist is declined on the measured data
(0.4 ms of a 12.6 ms poll), and it is recorded in finding 1 so that it is not later re-discovered
as a surprise.
