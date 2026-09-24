## Security Deep Analysis: position-belief-runaway

Branch `fix/position-belief-runaway`, head `cd768af`, branched from `main` at `a04eec8`.
Scope: once-per-feature pass, single-user/LAN-only project per `CLAUDE.md` — this is a
robustness/correctness read of the belief-integrity surface this fix touches, not a hardening
audit. No externally-untrusted input exists anywhere on this branch (all inputs are DCS
engine/world-object state); "adversarial" below means pathological/ordinary-operation
input sequences, not attacker-controlled ones.

### CVE Status

No new or changed dependency. `git diff main..fix/position-belief-runaway -- body-layer/pyproject.toml
world-model/pyproject.toml aircraft-layer/pyproject.toml` is empty. Both touched subprojects stay
stdlib-only, confirmed rather than assumed.

| Package | Version | Advisory | Severity | Affected in This Project |
|---|---|---|---|---|
| — | — | — | — | n/a — no dependency change |

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `position_belief.py`, `Covariance2D.inverse`/`fold_position` guard hold branch | Elapsed-time process-noise inflation composes **quadratically-in-dt across repeated holds** rather than linearly-in-elapsed-time | **Probable risk, confirmed by direct execution — see below.** The review's "~20s recovery" claim does not hold for continuous polling; recovery time scales roughly as `1/poll_interval_s` and grows without bound as poll rate increases. | Recommend fixing before merge (see suggested fix below); not a blocker if the user accepts the risk with a todo instead |
| `Covariance2D.inverse()`, `_MIN_DETERMINANT_RATIO`/`_MIN_DETERMINANT_ABSOLUTE` | Overflow/NaN propagation in `trace**2` under unbounded elapsed-time inflation | **False positive.** Verified directly: `trace` only overflows to `inf` (producing `NaN` downstream) at `elapsed_s ~ 1e154` seconds — physically unreachable (a DCS sortie runs for hours, ~1e4–1e5 s; the age of the universe is ~4e17 s). No realistic path to `inf`/`NaN`. | None |
| `speech.py` `_identification_lead` regex | Regex built from speech-recognition-derived text | **False positive.** `spoken` is passed through `re.escape()` before being embedded in the pattern, so it is always a literal (no metacharacter injection), and the pattern shape (`\bliteral\b`) has no repetition/alternation to backtrack on — length-linear regardless of input length or content. | None |
| `belief/contacts.py` `_max_detection_range_m` fallback | Unrecognised `percept.source` falls back to the *larger* of the two known caps | Correct-direction fail-open (never spuriously rejects a fusion this module can't judge) — consistent with the module's own stated intent, not a gap that admits an unbounded range. | None |
| `belief/contacts.py`, `position_belief.py` call sites | Envelope/guard applied at both `record` and `from_percept`, no bypass path | Confirmed by reading both call sites in the diff — no third path constructs a `Contact.position` without going through `clamp_to_detection_envelope`. | None |

### The load-bearing finding, in detail

**Claim under test** (from the task and from `review.md`'s own re-review): "empirically the
guards recover within tens of seconds under normal reacquisition... ~20s... at
`GATE_GROWTH_RATE_MPS = 20`." I reproduced this claim directly rather than trusting it, using
isolated `git archive` scratch trees (the `pytest`/`PYTHONPATH` trap noted in
`.claude/agent-memory/reviewer/feedback_worktree_main_based_pytest_pythonpath_trap.md` applies to
ad hoc scripts too, not just pytest, so I ran everything with `cwd` inside a clean archived copy
of `body-layer/`, no ambient `PYTHONPATH`).

The reviewer's own "~20s" number is real, but it was measured for a **single re-acquisition after
a gap** (a target goes unobserved, then is seen once more 20s later — `clamp_to_detection_envelope`'s
own test fixture and the review's own check both use this shape). That is not the shape of a
continuously-tracked contact whose looks keep disagreeing enough to re-trip
`FUSION_SANITY_SIGMA` on *every poll*, which is the operationally realistic case this branch's own
guard newly creates (pre-fix, there was no repeated-hold path at all — the runaway bug it fixes was
exactly "fuse regardless, no hold").

I reproduced the near-parallel disagreeing-looks case from
`test_fold_position_near_parallel_disagreeing_looks_holds_prior_not_runaway` (the debug report's own
live-defect reproduction numbers) and repeated it every `dt` seconds, chaining each hold's own
output as the next poll's prior — exactly what `Contact.record` does when a poll keeps producing a
percept that re-trips the guard:

```
dt=20.0s : recovers at t=20.0s   (1 poll  -- the review's own scenario)
dt=5.0s  : recovers at t=10.0s
dt=1.0s  : recovers at t=47.0s   (47 polls -- body-layer's own default --poll-interval-s)
dt=0.2s  : recovers at t=233.6s  (1168 polls)
dt=0.05s : recovers at t=933.9s  (~15.5 minutes, 18678 polls)
dt=0.01s : still held after 2000s / 200,000 polls
```

The mechanism: `Covariance2D.inflated` adds `growth_var = (GATE_GROWTH_RATE_MPS * elapsed_s)**2` to
the covariance, and each hold resets `as_of_sim` to the current poll's `t_sim`, so `elapsed_s` on
the *next* poll is only the inter-poll interval, not the time since the belief was last genuinely
fused. Summing `n` steps of `(rate*dt)**2` over a fixed wall-clock budget `T` (`dt = T/n`) gives
`rate**2 * T**2 / n` — inversely proportional to poll rate — instead of the `rate**2 * T**2` a single
`T`-second gap gives. Recovery time is therefore not a fixed ~20s constant; it is
`O(1/poll_interval_s)`, and at `body-layer/src/logger.py`'s own `_DEFAULT_POLL_INTERVAL_S = 1.0`
it is already ~47s (>2x the cited figure) for this reproduction, worsening further at any tighter
poll interval a future session might use.

This is not "stuck forever" in the strict sense (it is monotonic and always eventually recovers,
confirmed out to 200,000 polls with no numerical breakdown), and it is not attacker-reachable — DCS
world-object positions are not adversarial input in this project's threat model. But it does mean:
a contact that has genuinely relocated, while remaining continuously observed with looks that keep
disagreeing at a near-parallel bearing (an ordinary geometry, not a corner case — this is exactly
the geometry two consecutive looks from a slowly-turning helicopter produce), can be reported at a
stale position for **minutes**, not the "tens of seconds" the review's approval rested on, while
`last_seen_sim` keeps advancing every poll (the review's own "Optional Refinements" item, confirmed
still true) — so it reads as fresh and current the whole time. That combination — stale position,
fresh-reading timestamp, for materially longer than believed — is the same class of problem this
branch exists to fix, reintroduced in a milder, bounded form by the fix itself.

**Suggested fix** (not prescriptive, per role scope): compute elapsed-time inflation against the
`t_sim` of the last estimate that was actually *fused* (or the contact's founding look), not
against the `as_of_sim` of the last *held* estimate — i.e. carry a separate "last real update" time
alongside the held mean/covariance, so repeated holds accumulate inflation linearly in true elapsed
time regardless of poll granularity, the way the review's "~20s" scenario assumed.

**Finding:** Guarded-hold recovery time is `O(1/poll_interval_s)`, not the fixed ~20s the review's
approval relied on; a continuously-tracked, continuously-disagreeing contact can read fresh at a
stale position for minutes at the project's own default poll interval.
**Location:** `body-layer/src/belief/position_belief.py` — `Covariance2D.inflated`, the
`FUSION_SANITY_SIGMA` hold branch in `fold_position`, and `clamp_to_detection_envelope`'s identical
hold pattern (same mechanism, not separately re-derived here since the math is identical).
**Probability:** high that this triggers in ordinary flight (near-parallel disagreeing looks from a
turning aircraft are common geometry, not a corner case) — low that a user would ever notice within
this project's current single-user acceptance-testing regime, since it requires a specific sustained
disagreement pattern to keep re-tripping the guard across many consecutive polls rather than
resolving in one or two.
**Impact:** medium — a materially stale position callout, presented with undiminished apparent
confidence, for longer than the fix's own design intent. No crash, no data corruption, no
attacker path.
**Recommended action:** fix now (small, localized change — track last-real-fuse time separately from
last-held time) or defer to `todo/todo.md` with this report linked, if the user judges the current
behavior (bounded, monotonic, eventually-correct, and still strictly better than pre-fix's unbounded
runaway) acceptable for this project phase.

Options:
  (A) Ignore — document acceptance of this risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — address before this branch reaches DoD
  (D) Stop — do not proceed until resolved

### SBOM

Not regenerated — no dependency manifest changed on this branch (see CVE Status above), so there
is nothing to change in `sbom.json` relative to its `main` baseline. `body-layer/pyproject.toml`,
`world-model/pyproject.toml`, `aircraft-layer/pyproject.toml` all diff empty against `main`.

### Verdict

**NEEDS FIXES** — one item, the recovery-time finding above. This is a correctness/robustness
finding, not an exploitable vulnerability (no untrusted input, no attacker path, bounded and
monotonic) — flagged here because it directly undermines the specific claim
(`review.md`'s "~20s recovery") the merge approval rests on, verified false for the continuous-poll
case the task asked me to check. Left to the user's judgment via the options above rather than a
hard block; everything else on this branch (determinant-floor overflow/NaN reachability, regex
injection/backtracking, envelope-clamp bypass, dependency manifest) checked clean.

### Required Fixes (if any)

1. (Recommended, not mandatory per the scoping above) Decouple elapsed-time inflation from the
   last-*held* estimate's timestamp — accumulate against the last-*fused* time instead — so
   guarded-hold recovery time stops depending on poll granularity.
   `body-layer/src/belief/position_belief.py`: `Covariance2D.inflated` call sites inside
   `fold_position`'s guard branch and `clamp_to_detection_envelope`.
