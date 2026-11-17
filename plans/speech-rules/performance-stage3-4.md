### Performance Review

**Scope:** BL-17 batch built together on `feature/speech-rules-matching` (fast-forwarded to tip
`1e5ddd5e`, clean): Stage 3a (fuzzy rule matching incl. phrase-level directive fuzz, number words,
D13's literal/word-set fuzz, D15's two caching fixes), Stage 3b (category gates,
hold-and-retry drained per poll), Stage 3d (effector writes from rules via the existing engine, ad
hoc runs), Stage 4 (19 flight-control rules ported; 18 load in this tree — `README.md`/Stage 4
follow-ups note two were later disabled by the adapter's own collision check, matching the
`test_shipped_rule_files_load_with_zero_failures` fixture's own count), plus follow-up fixes.

**Target** (task + `CLAUDE.md`): no hard real-time budget yet, but the user's own reason for fixed
wording — *"to get the deterministic (=fast) path, I use fixed wording"* — means PTT-release-to-
action latency must not grow noticeably as rule count grows toward the plan's own stated scale
(U6: ~80-100 rules total). Separately, Milestone 5/7's "practical, roughly linear" pipeline budget
does not apply here (BL-17 is a runtime matcher/sandbox, not an offline world-model build) but the
same "measure, don't estimate" discipline does.

**Method:** built fresh venvs (`/opt/homebrew/bin/python3.14`) for both subprojects (audio-adapter:
stdlib only; body-layer: `pip install pyproj numpy 'lupa==2.8'`, both installed cleanly). Measured
every hot path named in the task directly against the real shipped code — no estimation — at
today's real rule count (18, the shipped `flight.lua`) and the plan's own projected ~100, with a
few extra points (1/10/50/150/200) where the shape of the growth mattered. Every bench script
asserts a can-this-fail probe (a real hit, a real miss, a real HOLD) before any timing is printed.

### Findings

#### `compile_rules`'s collision check recomputes each rule's perturbed samples on every pair it appears in, turning D13's O(n²) check into something far worse than O(n²)

- **Location:** `audio-adapter/src/rule_patterns.py::_rules_collide` (rule×rule pass) and
  `_collides_with_legacy` (rule×legacy pass), both calling `_samples_with_perturbation(rule)` ->
  `_perturbed_sample` -> `_best_probe_word` (an O(34), `_COLLISION_PROBE_WORDS`-sized,
  `difflib.SequenceMatcher` scan per fuzzable element position) **fresh, every single call**,
  rather than once per rule. `_rules_collide(rule_a, rule_b)` calls this for *both* `rule_a` and
  `rule_b` on every one of the `compile_rules` rule×rule loop's `C(n,2)` pairs, and
  `_collides_with_legacy` calls it once per rule (that part alone is fine, O(n)) — but combined,
  one rule's own perturbed-sample set gets rebuilt roughly `2·(n-1)` times instead of once.
- **Measured** (real `compile_rules`, the `_legacy_probe`-shaped injection, a realistic mix of the
  18 real shipped `flight.lua` rules plus distinct synthetic rules padding to each `n`):

  | rules | wall time | vs. Stage 0-2's pre-D13 baseline at the same `n` |
  |---|---|---|
  | 1 | 0.63 ms | (not measured then) |
  | 10 | 33.4 ms | 2.67 ms (12.5×) |
  | 18 (today's real count) | 49.2 ms | — |
  | 50 | 791 ms | 16.84 ms (47×) |
  | **100 (plan's own U6 target)** | **2.76-3.15 s** | **41.83 ms (66-75×)** |
  | 150 | 7.05 s | (not measured then) |
  | 200 | 12.6 s | 118.05 ms (107×) |

  `cProfile` on the n=100 case (47.3M calls, confirms the mechanism rather than the magnitude,
  since the profiler itself adds ~4× overhead here) attributes essentially all of the cost to
  exactly this path: `_rules_collide` called 4,950 times (= `C(100,2)`), each invoking
  `_samples_with_perturbation` twice (9,900 calls) plus 100 more from `_collides_with_legacy` —
  10,000 calls total, cascading into 20,000 `_best_probe_word` calls and 735,300 `difflib.ratio()`
  calls. The genuinely-necessary O(n²) work (the pairwise `match_pattern_with_ratio` comparisons
  themselves) is unaffected and stays the ~42 ms/100-rules the Stage 0-2 pass already measured and
  accepted — this finding is specifically the **avoidable** multiplier on top of that, not the
  algorithm's own inherent cost.
- **Risk:** this runs synchronously inside `server.py`'s `PUT /rules` HTTP handler, inside
  body-layer's `AudioAdapterClient.put_rules` call, which times out at **5.0 s**
  (`audio_client.py::_DEFAULT_TIMEOUT_S`) — the same client call `_push_rules` makes on every
  genuine mission (re)start *and* retries on every poll where `rules_version` mismatches (`body.py`
  `_check_for_new_mission`/poll-loop re-push, `[[BL-17]]` D2). At the plan's own already-reached-for
  scale (U6's ~80-100 rules, not a hypothetical future one — Stage 4 alone shipped 18-19 and the
  plan explicitly names "the remaining ~80 commands" as the next ports), this single CPU-bound call
  already consumes **55-63% of the entire client timeout budget before a single byte of network
  latency, JSON parsing, or machine-load variance is counted.** `[[BL-B95]]`'s later
  "mission-stacked rules added to the common set" was already named by the plan as a case that
  could push `n` higher — at 150-200 rules this blows the 5 s timeout outright (7.0 s / 12.6 s
  measured). A timed-out push is caught cleanly (`_push_rules`'s own `except AudioAdapterError`
  logs and returns, "will retry next poll") — but the *same* 2.8-3.1 s CPU cost repeats on every
  retry, so a push that fails once at this scale is likely to keep failing, leaving every rule
  (every flight-control command, the entire "fixed wording = fast path" mechanism this plan
  exists to build) silently unavailable for the rest of the sortie, with no escalating backoff
  visible in `_push_rules` to even slow the retries down. This is a real, measured, scale-triggered
  risk to the project's own stated goal, not a theoretical one — it sits at exactly the rule count
  the plan already commits to reaching.
- **Action: NOW.**
- **Mitigation (concrete, cheap, no architectural change):** compute
  `_samples_with_perturbation(rule)` once per accepted rule *before* `compile_rules`'s rule×rule
  loop and rule×legacy pass (e.g. `samples_by_id = {rid: _samples_with_perturbation(r) for rid, r
  in accepted.items()}` right after the parse loop, around `rule_patterns.py:1168`), then change
  `_rules_collide`/`_collides_with_legacy`'s signatures to take the precomputed sample list(s) for
  each rule instead of calling `_samples_with_perturbation` themselves. This drops the call count
  from ~`2·C(n,2) + n` to exactly `n`, which the measurements above show removes essentially all of
  the regression (the remaining genuine O(n²) `match_pattern_with_ratio` cost stays the already-
  accepted ~42 ms/100 rules). No change to D9's collision semantics, D13's fuzz behaviour, or any
  test's expected outcome — this is a pure memoization of an already-pure, already-deterministic
  per-rule computation, the same shape this project already applied to `rule_anchor_words`
  (D15) and the whisper prompt (`CachedRulePromptProvider`) for exactly the same reason.

#### `match_transcript`'s per-transcript cost: both MONITOR items from the Stage 0-2 pass are confirmed fixed — but D13 changed what "a rule hit" costs, and the Stage 0-2 memory's own numbers for that case are now stale

- **Location:** `audio-adapter/src/command_matcher.py::match_transcript`.
- **Confirmed fixed** (read, then verified by direct test against the real code, not re-asserted
  on faith):
  - `rule_anchor_words(rules)` (moved to `rule_patterns.py`, D15) is computed exactly once, inside
    `RuleRegistry.swap` — at the `PUT /rules` swap point, never per transcript. `server.py`'s real
    `/transcribe` handler (line ~426-430) passes `anchor_words=rule_state.anchor_words` on every
    call; the only `match_transcript` call site that omits it (`server.py`'s `_legacy_probe`, used
    solely by `compile_rules`'s own collision check, never by `/transcribe`) is load-time-only by
    its own docstring.
  - `CachedRulePromptProvider` only rebuilds the whisper prompt when `registry.version` changes —
    verified directly: 3 calls at an unchanged version produced exactly 1 `build_prompt` call; a
    `registry.swap` to a new version triggered exactly 1 more.
- **New in this batch (D13, Stage 3a):** `match_transcript` **no longer returns early on a rule
  hit** — `_match_rules` and `_match_legacy` both run on every call now (so the higher-ratio result
  can be compared against the other, D13's own widened tie-break), and `_match_rules`/
  `match_pattern_with_ratio` do real per-element fuzzy scoring (`_resolve_word_set`'s `sorted()`
  over each word-set's alternatives, `_literal_ratio`'s `difflib` call per literal) rather than
  exact-only matching.
- **Measured** (real `match_transcript`, real 18-rule + synthetic-padded mix, `anchor_words`
  precomputed as the hot path does):

  | active rules | free-speech (no match), µs | rule hit, µs | legacy hit, µs |
  |---|---|---|---|
  | 18 (today) | ~1095 | ~953 | ~1068 |
  | 100 (U6 target) | ~1986 | ~1738 | ~1516 |

  Compare the Stage 0-2 pass's own numbers for "a transcript that *does* match a rule": **10-40 µs
  even at 200 rules** — that figure is now **stale**, because it measured the pre-D13 early-return
  behaviour. A rule hit now costs roughly the same as a free-speech miss or a legacy hit (~1-2 ms
  at this batch's scale), because the legacy pipeline always runs alongside it.
- **Risk:** **not credible as a budget violation**, same reasoning as Stage 0-2's own verdict —
  `/transcribe` runs once per PTT release (human-paced), and the very next step is a `whisper-cli`
  subprocess call costing hundreds of ms to low seconds; ~1-2 ms is three-plus orders of magnitude
  below that regardless of which branch resolves. The *shape* changed (no more "a hit is nearly
  free") but the *conclusion* (negligible against whisper) did not.
- **Action: MONITOR** — no change required. **House-keeping action taken as part of this
  review:** the stale "10-40 µs, a rule hit stays cheap" claim in this project's own
  `.claude/agent-memory/performance-reviewer/project_bl17_rule_engine_cost_shape.md` is corrected
  below (memory update), rather than left to mislead whoever next reads it, per this role's own
  "a per-file correction is not a correction" lesson — checked for siblings: `grep -rn "10-40"
  .claude/agent-memory/` and `plans/speech-rules/performance-stage0-2.md` find the number only in
  that one memory file and the original (historically accurate, dated) report; the report is not
  rewritten (it is a decision log of what was true at the time), only the memory file that would
  otherwise keep asserting it as current.

#### Lua dispatch through the real shipped `flight.lua`, end to end — measured, negligible

- **Location:** `belief/crew_console.py::handle_command` -> `_handle_rule` (category gate via
  `rules.gates.check_gate`) -> `_dispatch_rule` (thread-local write-buffer open/commit, Stage 3d
  Fix 4 round 2) -> `rules.engine.run_rule` -> lupa.
- **Measured** (real `RuleSet.load` against the shipped `config/rules/flight.lua`, real
  `RuleSandbox`, real dispatch through `handle_command`, 7×2000-call medians):

  | path | µs/call |
  |---|---|
  | PASS (gate passes + Lua handler runs + speech line produced) | 11.76 |
  | UNABLE (gate rejects, handler never called) | 4.26 |
  | `drain_pending_rule_dispatch`, nothing pending (steady-state per-poll cost) | 0.08 |
  | `current_crew_state()` construction alone | 0.90 |

- **Risk:** none. Confirms the Stage 0-2 pass's isolated-lupa measurement (3.39 µs/call for the
  bare handler+hook) holds once the real gate check, thread-local buffer, and speech path are
  wired around it — the category gate (`rules.gates.check_gate`, a dict lookup + a handful of
  attribute comparisons, no loop over rules or categories) and `current_crew_state()` (one frozen
  dataclass construction from already-held fields) are exactly the O(1) shape the task brief
  expected, confirmed by direct measurement rather than architecture-only reasoning.
- **Action:** none.

#### Per-poll additions in `body.py`/`crew_console.py`/`effector_engine.py` — all bounded, nothing new added to the hot path's growth class

- **Location:** `drain_pending_rule_dispatch` (above, 0.08 µs idle), `queue_effector_write`
  (appends to a thread-local buffer during a dispatch, or the shared list outside one — O(1) per
  write), the `pending_effector_writes` swap-with-fresh-list drain in `body.py` (`~5089`, O(writes
  since last poll), realistically 0-1 per poll), and `effector_engine.request_write` (D20's ad hoc
  write path) — the one sub-finding worth naming: `request_write`'s "already-pending for this
  effector" check (`next(... for id, ad_hoc in state.ad_hoc_runs.items() if ad_hoc.effector ==
  name)`) is a **linear scan over `ad_hoc_runs`**, not a dict lookup, same as `dict(state.
  ad_hoc_runs)`'s full-copy-per-write. Both are bounded by the number of *currently in-flight* ad
  hoc writes, which stays tiny (a pilot speaks commands at human pace, and each resolves within a
  handful of polls) — this is the same "rebuilds 4+ containers every poll" pattern this project's
  own `[[project_effector_engine_replace_only_baseline_cost]]` memory already reviewed and accepted
  for `effector_engine.advance`'s existing baseline; BL-17's ad hoc writes are a marginal addition
  to an already-accepted cost class, not a new one.
- **Risk:** none at any realistic concurrent-write count. Would only become worth a second look if
  a future change let many ad hoc writes queue up unresolved simultaneously (not something this
  batch does — `request_write`'s own "latest wins" rule keeps at most one in-flight request per
  effector).
- **Action:** none.

### Verdict

**CHANGES REQUIRED**

**Required fixes, numbered:**

1. `audio-adapter/src/rule_patterns.py::compile_rules` — precompute each accepted rule's
   `_samples_with_perturbation` once, before the rule×rule and rule×legacy passes, and pass the
   precomputed samples into `_rules_collide`/`_collides_with_legacy` instead of having them
   recompute it per pair. Measured effect: removes a confirmed 66-107× regression (49 ms → 2.8 s
   between today's 18 real rules and the plan's own U6-stated ~100-rule target; 12.6 s at 200),
   which at 100 rules already consumes over half of `PUT /rules`'s 5 s client timeout on pure CPU
   time before any network/JSON overhead, and risks an indefinite retry-and-fail loop that would
   leave every flight-control rule silently unreachable for a sortie — the opposite of this plan's
   own stated purpose ("to get the deterministic (=fast) path, I use fixed wording"). This re-enters
   the loop as ordinary implementation work (Implementer -> Reviewer -> DoD), per `AGENTS.md`'s
   "A change request from Security or Performance Reviewer re-enters the loop."

**MONITOR (no action required now):**

- `match_transcript`'s now-unconditional dual-pipeline cost (~1-2 ms at 100 rules, every call, not
  only free speech/legacy hits as before) — negligible against whisper-cli's own latency, but worth
  re-measuring if rule count approaches U6's own stated ceiling with a *less* synthetic rule mix
  (more real word-sets, more literal fuzz surface) than this bench used.
- `effector_engine.request_write`'s linear scan + full-dict-copy over `ad_hoc_runs` — bounded by
  concurrently in-flight ad hoc writes today; revisit only if a future change lets that count grow
  unbounded.

Everything else named in the task brief — the whisper prompt cache, the rule-anchor-word cache, Lua
dispatch with the gate check, and every per-poll addition in `body.py` — was measured directly
against the real shipped code and found negligible, with both Stage 0-2 MONITOR items confirmed
fixed by direct test rather than by re-reading the docstring that claims it.
