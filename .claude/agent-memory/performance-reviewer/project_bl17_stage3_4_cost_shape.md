---
name: bl17-stage3-4-cost-shape
description: BL-17 Stages 3a/3b/3d/4 (fuzzy rule matching, category gates, effector-write rules, 19 flight-control rules) measured hot-path costs -- compile_rules' collision check regressed 66-107x from D13's perturbed-sample mechanism recomputing per rule-pair instead of once per rule; everything else (match_transcript, whisper prompt cache, Lua dispatch, per-poll drains) stays negligible. Supersedes stale claims in [[bl17-rule-engine-cost-shape]].
metadata:
  type: project
---

Measured 2026-11-17, `feature/speech-rules-matching` @ `1e5ddd5e`, fresh venvs
(`/opt/homebrew/bin/python3.14` -- audio-adapter stdlib-only; body-layer
`pip install pyproj numpy 'lupa==2.8'`, both installed cleanly, no issues). Full report:
`plans/speech-rules/performance-stage3-4.md`.

## The one real regression: `compile_rules`'s collision check, via per-pair perturbation recompute

D13 (Stage 3a) added one perturbed sample per rule to the rule×rule/rule×legacy collision passes
(`_samples_with_perturbation` -> `_perturbed_sample` -> `_best_probe_word`, an O(34)-sized
`difflib` scan over `_COLLISION_PROBE_WORDS` per fuzzable element position). The bug: `_rules_
collide(rule_a, rule_b)` (and `_collides_with_legacy`) call `_samples_with_perturbation(rule)`
**fresh on every call** instead of once per rule -- so across the rule×rule pass's `C(n,2)` pairs,
one rule's own perturbed-sample set gets rebuilt `~2·(n-1)` times instead of once.

**Measured** (real `compile_rules`, 18 real `flight.lua` rules + synthetic padding):

| rules | this batch | Stage 0-2 baseline (pre-D13, same n) | regression |
|---|---|---|---|
| 18 (today, real) | 49 ms | -- | -- |
| 50 | 791 ms | 16.84 ms | 47x |
| **100 (plan's own U6 target)** | **2.76-3.15 s** | **41.83 ms** | **66-75x** |
| 200 | 12.6 s | 118.05 ms | 107x |

`cProfile` at n=100 confirms the mechanism: `_rules_collide` called 4,950 times (`C(100,2)`),
`_samples_with_perturbation` 9,900+100=10,000 times, cascading to 20,000 `_best_probe_word` calls
and 735,300 `difflib.ratio()` calls -- essentially all of the wall time.

**Why this matters, concretely**: `compile_rules` runs synchronously inside audio-adapter's
`PUT /rules` handler, inside body-layer's `AudioAdapterClient.put_rules` call, which times out at
**5.0s** (`body-layer/src/belief/audio_client.py::_DEFAULT_TIMEOUT_S`) and is called on every
genuine mission (re)start *and* retried on every poll while `rules_version` mismatches. At U6's
own ~100-rule target this one CPU-bound call already eats 55-63% of that timeout before any
network/JSON overhead -- and a timed-out push retries at the *same* cost, with no backoff, so a
push that fails once at this scale is likely to keep failing, silently disabling every
flight-control rule for the rest of the sortie. This is the opposite of the plan's own stated
purpose (deterministic/fast fixed-wording path). Flagged NOW / Required Fix 1, not MONITOR --
unlike the Stage 0-2 pass's own (correct, at the time) "confirmed super-linear but bounded"
verdict on the *pre-D13* collision check.

**The fix is cheap and does not touch D9/D13 semantics**: precompute `_samples_with_perturbation`
once per accepted rule *before* the rule×rule/rule×legacy passes, thread the precomputed samples
into `_rules_collide`/`_collides_with_legacy` as parameters. Same memoization shape this project
already applied to `rule_anchor_words` (D15) and the whisper prompt (`CachedRulePromptProvider`)
for the identical reason -- a pure, deterministic per-rule computation recomputed far more often
than its input changes.

## Everything else measured in this batch: negligible, confirmed by direct test

- **Both Stage 0-2 MONITOR items are fixed**, verified by test (not by reading the docstring):
  `rule_anchor_words` computed once at `RuleRegistry.swap`, read via `server.py`'s
  `anchor_words=rule_state.anchor_words` on the real `/transcribe` path; `CachedRulePromptProvider`
  rebuilds only on a version change (3 same-version calls -> 1 build; a swap -> 1 more).
- **`match_transcript` no longer early-returns on a rule hit** (D13: both pipelines always run now,
  so the two can be compared) -- a rule hit now costs ~950-1740us at 18-100 rules, same order as a
  free-speech miss, not the 10-40us the pre-D13 code achieved. Still 3+ orders of magnitude below
  whisper-cli's own latency -- MONITOR, not NOW -- but the *old* "a hit stays cheap" framing is
  gone and should not be cited going forward.
- **Real Lua dispatch through the shipped `flight.lua`, end to end** (gate check + thread-local
  write buffer + lupa + speech line): PASS path 11.76 us/call, UNABLE 4.26 us/call,
  `drain_pending_rule_dispatch` idle 0.08 us/call, `current_crew_state()` 0.90 us/call. All
  negligible, confirms the category-gate mechanism (`rules.gates.check_gate`, a dict lookup) adds
  nothing beyond O(1).
- **`effector_engine.request_write`'s "already pending for this effector" check** is a linear scan
  over `state.ad_hoc_runs` plus a full dict copy per write -- bounded by concurrently in-flight ad
  hoc writes (stays tiny at human speech pace, "latest wins" keeps at most one per effector), same
  accepted cost class as `[[project_effector_engine_replace_only_baseline_cost]]`'s existing
  "rebuilds 4+ containers every poll" finding. MONITOR only if something later lets many ad hoc
  writes queue unresolved at once.

## Measurement technique notes

- Build a fresh `audio-adapter/.venv` with `/opt/homebrew/bin/python3.14 -m venv .venv` -- stdlib
  only, no pip install needed.
- `cd body-layer && /opt/homebrew/bin/python3.14 -m venv .venv && .venv/bin/pip install -q
  'pyproj>=3.6' 'numpy>=1.26,<2.5' 'lupa==2.8'` installs cleanly on this machine (cp314 macOS
  arm64) -- no need to fight wheel availability.
- The real dispatch path (`handle_command` through the real shipped `flight.lua`) is cheap to
  bench directly -- copy `test_rules_flight_actions.py`'s own `_dispatching_console` helper
  (`CrewConsole` + `RuleSandbox` + `RuleSet.load(DEFAULT_RULES_DIR, ...)`), no need to mock
  anything. `handle_command`'s signature is `(token, now_sim, slots=None, correlation_id=None)` --
  `now_sim` is positional before `slots`, easy to get backwards from memory.
- `cProfile` adds real overhead (observed ~4x on this workload) -- use it to find *where* a cost
  lives, then always re-measure the unprofiled wall time before reporting a number.
