---
name: lupa-single-runtime-lock-blocks-genuine-concurrency-tests
description: A test that wants two threads genuinely overlapping inside Lua execution (via rules.sandbox.RuleSandbox/lupa) must use two separate RuleSandbox instances, not one shared one -- lupa's own per-runtime lock serializes every call into one LuaRuntime, so two threads sharing a sandbox never truly overlap.
metadata:
  type: feedback
---

When a test needs two dispatches to genuinely interleave at the thread level (e.g. to prove a
rollback correctly distinguishes "this dispatch's own queued item" from "another thread's
legitimately queued item," BL-17 Stage 3d re-review Required Fix 4), do not share one
`rules.sandbox.RuleSandbox` between the two dispatching threads.

**Why:** `research/2026-11-17-lupa-sandbox.md`'s R4 measured that lupa's `LuaRuntime` has its own
global per-runtime lock — confirmed empirically (8 threads, 16,000 concurrent calls, zero lost
increments, consistent with serialization). That lock is held for the *entire* top-level Lua call,
including any Python callback invoked from inside it (e.g. an action wrapper like
`effector.write`'s `request_effector_write` closure) — so if thread A is paused inside its own
closure call (even via a plain `threading.Event.wait()`, pure Python), thread B's attempt to make
its *own* call into the *same* `RuleSandbox`/`LuaRuntime` blocks until A's entire dispatch returns.
Two dispatches sharing one sandbox therefore never actually overlap in Lua execution — only in the
brief plain-Python window between one dispatch's `rule_runner()` return and whatever runs right
after it (e.g. a rollback filter), which is real but far narrower and not reliably reproducible by
pausing *inside* a Lua-held callback.

**How to apply:** when a test needs genuine, deterministic thread overlap through the rule-dispatch
path, give each thread its own `RuleSandbox` (its own `LuaRuntime`) and its own `RuleSet` loaded
from its own rule file/directory, both still constructed with `ActionContext`s that point at the
*same* shared state under test (e.g. the same `CrewConsole`, so both dispatches mutate the same
`pending_effector_writes`). Wire a single `rule_runner` closure that dispatches to whichever
`(RuleSet, RuleSandbox)` pair matches the incoming rule id. This sidesteps lupa's lock entirely
(each thread's own runtime has its own lock) while still faithfully exercising the Python-level
mechanism actually under test. Confirmed this test fails for the expected reason against a
length-based counterfactual (`del pending_effector_writes[before:]`) and passes against the real
token-based filter — see `plans/speech-rules/review-stage3d.md` Required Fix 4 and
`body-layer/tests/test_rules_effector_action.py::test_rollback_leaves_a_concurrent_dispatchs_own_queued_write_alone`.
