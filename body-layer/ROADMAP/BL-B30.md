# BL-B30 — The poll loop runs at ~0.7 Hz against a specified 5 Hz

- [x] **BL-B30 — RESOLVED 2026-10-06 by `feature/bl11-tick-cost` ([[BL-11]] Stages 1/2/3b), DoD
  PASSED on bench measurement; the flight is on the live-acceptance debt list.** #status/done The original
  title — "roughly 0.7 Hz against a specified 5 Hz" — was wrong in both halves, and the correction
  is recorded below under "DIAGNOSED 2026-10-05": there is **no 5 Hz specification anywhere in
  body-layer** (about 5× of the apparent gap was a constant nobody had read), and the real mechanism
  was `work + interval` rather than `interval`.

  **Measured at the fix** (`plans/bl11-tick-cost/performance-review.md`, real `syria-full.sqlite`,
  440 objects, 300 polls):

  | | pre-branch | at the fix |
  |---|---|---|
  | **realised poll period, median** | **1.33 s** | **1.000 s** (mean 1.008) |
  | poll work, median | ~330 ms | **12.6 ms** |
  | poll work, p90 / max | — / 1,736 ms | 98.6 / 1,642 ms |
  | `group_salient_ids` | ~300 ms every poll | **1.1 ms** |
  | enrichment-cache hits within a callout tick | **0 %** | **89.7 %** |
  | polls overrunning 1.0 s | — | **2.0 %** |

  `_wait_for_next_tick` realises `max(interval, work)` to within 0.1 ms. The entry's own
  prescription — *"a timing instrument around the loop is the next step, not more log reading"* —
  was **not** what resolved it: cProfile plus a bench harness at the sortie's scale did, and the
  in-flight instrument (the note's finding 0) is still unbuilt. Worth knowing, because the
  instrument would have cost a sortie and the harness cost none.

  **What this does NOT close.** The 2.0 % overrun tail is entirely `describe_position`'s unit cost
  (57–85 ms/call, identical cold or warm) and is `world-model`'s `M11`, not body-layer's. And the
  sortie's **4.98 s p90 remains unexplained** — nothing in the CPU measurements reaches it; the
  candidates are [[BL-B33]] and [[BL-B32]], both across a subproject seam. **The median is fixed and the
  tail is not**, so the "every decay half-life and cadence constant was tuned against the wrong
  rate" concern below is now answered for the typical tick and still open for the worst case.

  (Original filing, kept because the premise's correction is the instructive part:)

  **The poll loop runs at roughly 0.7 Hz against a specified 5 Hz. HIGH — the largest
  finding of the 2026-10-05 sortie, and it degrades everything downstream of the tick.**

  Measured from two independent logs of the same flight
  (`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md` §2):

  | source | polls | span | median gap |
  |---|---|---|---|
  | DCS Hook (producer, for reference) | 5,534 | 5,568 s wall | **1.00 s** |
  | detection trace | 2,621 | 4,235 s sim | **1.44 s** |
  | belief-truth log | 1,340 | 4,233 s sim | **1.43 s**, p90 **4.98 s**, **max 193 s** |

  Specified 5 Hz (0.2 s), observed ~0.7 Hz — **about seven times slower** — with a 193-second window
  in which body-layer did not poll at all.

  **Pre-existing, not caused by [[X-B29]].** The LOS work only made it visible, by adding a producer
  with a known, independently-logged 1 Hz cadence to compare the consumer against. There was no
  reference clock before.

  **Why it matters beyond latency**: every decay half-life, dwell and cadence constant, the
  movement-detection thresholds and the callout timing were tuned against an assumed 5 Hz tick. At a
  real 1.4 s tick they are being applied at a seventh of their intended rate — so any that "felt
  about right" in flight were calibrated against the wrong cadence.

  **Diagnose before fixing.** Candidates, none confirmed: the world-model LOS fallback (an SQLite
  query per candidate per poll, and that path carried 77 % of admissions — see [[BL-B31]]);
  [[BL-B26]]'s triple-gather in `CalloutScheduler.tick`; the detection-trace writer; LAN latency on
  the aircraft-layer poll. **A timing instrument around the loop is the next step, not more log
  reading** — the existing logs record what happened per poll, never how long the poll took.

  ---

  **DIAGNOSED 2026-10-05, and the premise above is wrong — scheduled as [[BL-11]] Stage 1/2.**
  Two whole-subproject passes (`body-layer/research/2026-10-05-performance-review.md`,
  `body-layer/research/2026-10-05-security-audit.md`) reached this independently, from different
  evidence.

  **There is no 5 Hz specification anywhere in body-layer.** `logger.py:999` is
  `_DEFAULT_POLL_INTERVAL_S = 1.0`, unchanged since `abf49cd` (2026-09-08); `body-layer/RUN.md`'s
  documented run command never passes `--poll-interval-s`; and this file's own `ROADMAP.md:1288`
  and `audio-adapter/ROADMAP.md:473` already call 1.0 s "the project's own default". The 5 Hz
  figure survives only in four stale **docstrings** (`logger.py:1446`,
  `belief/brain_client.py:12` and `:274`, `perception/motion.py:91`) and belongs to
  `Export.lua`'s producer rate, not the consumer. So the gap is **1.43 s against 1.0 s, ~1.4×,
  not 7×** — about 5× of it was a constant nobody had read.

  **The mechanism is `work + interval`, not `interval`.** Both poll loops end with
  `stop_event.wait(poll_interval_s)` *after* the work (`logger.py:1552`, `:1192`), so the period
  is the sum. Measured work at the sortie's own scale (440 objects, 142 contacts, against the real
  738 MB `syria-full.sqlite`): **median ~330 ms, peaks 1,736 ms** → 1.33 s period against the
  sortie's measured 1.43 s. Quantitatively accounted for.

  **The decay-constant corollary above is withdrawn.** Every half-life, dwell and cadence
  constant was tuned in flight at 1 Hz, which is what the code has always done — they were not
  calibrated against a rate the loop never had. (`perception/motion.py:91`'s *comment* does assert
  5 Hz arrival; that is a correctness question, filed separately as [[BL-B34]], not a cost one.)

  **The leading hypothesis is ruled out.** The whole gate chain including world-model terrain LOS
  is **2.4–21 ms/poll for all 440 candidates** — the cheap gates reject almost everything before
  the expensive one runs. Measured independently in `world-model/research/2026-10-05-performance-review.md`
  at 43.4 ms worst case for 71 candidates, ~4 % of the interval. [[BL-B31]]'s closing
  "one problem seen from both ends" is answered: they are two problems. [[BL-B31]] stands entirely
  on its own observability merits.

  **What the 330 ms actually is**, measured not reasoned:
  1. **`perception/group_salience.group_salient_ids` — ~300 ms of *every* poll, unconditionally**,
     58 % of a 300-poll cProfile, and it was not on the suspect list above at all. `_cohesive`
     recomputes two `profile_for` lookups and two `range_m` calls **per pair** of an O(n²) loop,
     all four depending on one candidate only. Hoisting them into the `_resolvable` pass plus
     `@lru_cache` on `profile_for` measures **8.1×** (215 → 27 ms at n=440) with the returned
     `frozenset` **asserted bit-identical at every n ∈ {55,128,250,440,800}**. Pure recomputation
     removal, not an approximation.
  2. **`CalloutScheduler.tick` — up to 47 `describe_position` calls in one tick, 1,579 ms
     measured.** That is [[BL-B26]], whose own estimate is two orders of magnitude out — see its
     entry.

  **The 193 s "gap" is probably not a 193-second poll.** Both logs derive poll gaps from distinct
  `t_sim` in *conditionally written* rows, so they cannot distinguish "did not poll" from "wrote
  nothing" from "sim paused". The note's own table is the proof: two consumers of the *same* loop
  report 2,621 and 1,340 polls over the same span.

  **The one open decision is the user's**: is the intended rate 1.0 s or 0.2 s? No optimisation
  closes a gap a constant opens, and at 0.2 s both findings above become mandatory rather than
  worthwhile. `gaze.FOCUS_DWELL_S = 2.0` currently sits at twice the poll period either way.

  **Where the instrument goes** (the sortie note's actual ask): wrap the five phases already
  separated in `_run_crew_text_poll_loop` with `perf_counter`, emit one line per 60 polls with
  per-phase mean/max in wall clock, and — more useful than any timing — count `len(candidates)` at
  `naked_eye_source.py:520` and `describe_position` calls per tick. Both are the multipliers and
  both are invisible in a timing number. **The one number that could re-rank the findings is the
  real per-poll in-bubble candidate count**: everything above assumes 440, and the sortie logged
  "444 distinct objects over 70 minutes" and "median 43 units in a LOS result", neither of which is
  that quantity. It is one `len()`.
