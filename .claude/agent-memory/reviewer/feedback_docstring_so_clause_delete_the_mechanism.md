---
name: docstring-so-clause-delete-the-mechanism
description: A docstring "X, so Y" is two claims — delete X and ask whether Y still holds; a true conclusion with a false reason is this project's most recurrent docstring defect.
metadata:
  type: feedback
---

**A docstring sentence of the form "X, so Y" is two claims. Mentally (or actually) delete
mechanism X and ask whether consequence Y still holds. If Y holds anyway, X is not the reason for
it — and the sentence is a defect even though its conclusion is correct.**

**Why:** on `feature/bl11-tick-cost` this class of defect recurred in **three consecutive review
rounds**, each instance written while fixing the previous one. Round 1: a test docstring claiming
coverage it did not have. Round 2: "only the tuning constants are shared" (four behaviour functions
were) and a function stating a policy a later commit had overridden. Round 3, both found by this
check:

- `_resolve_speech_log_path` justified keeping a redundant local `mkdir` with *"it degrades before
  the default path is ever returned, **so** the `"writing <path>"` startup line is never printed for
  a location that cannot hold a file."* Calling `_per_run_log_paths` alone against an uncreatable
  parent returned `(None, None, None)` — the announcement loop prints only for non-`None`, and
  `per_run_log_path` uses `Path.with_name` so the parent is identical. Y held without X.
- An equivalence test's module docstring argued four shared leaf primitives were safe because
  "Stage 2 did not touch them" — but Stage 2's own commit subject was *"hoist …, **cache
  profile_for**"*. The conclusion survived (memoising a pure function cannot make an equality
  tautological); the stated premise was simply false.

**How to apply:** on any file whose docstrings carry the architecture's reasoning (this project's
do, deliberately and at length), read every causal connective — "so", "therefore", "which is why",
"kept deliberately: " — as a separate assertion from the claim it supports. Two cheap probes:
`git log --oneline main..HEAD` subject lines often falsify a "commit N did not touch X" premise
outright; and for a "this guard prevents Y" claim, call the *downstream* code in isolation and see
whether Y is prevented anyway. Long load-bearing docstrings are a strength here, which is exactly
why a wrong "so" survives several readings.

Related: [[feedback_rendered_english_assertions_too_weak]],
[[feedback_estimate_flags_must_reach_code]], [[project_bl11_round3_deletion_review]].
