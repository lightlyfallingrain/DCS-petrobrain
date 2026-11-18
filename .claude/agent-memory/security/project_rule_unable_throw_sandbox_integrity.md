---
name: project_rule_unable_throw_sandbox_integrity
description: BL-17's "a failed action throws RuleUnable" refactor (2026-11-18) verified sandbox-safe -- extends [[project_lupa_sandbox_quirks_bl17_stage0]]'s unwrapped-exception finding to a nested Lua call frame, and confirms the instruction-count hook's finally survives it.
metadata:
  type: project
---

Mode 2 deep analysis of `refactor/rule-action-unable-throw` (merged as `09218679`,
`body-layer/ROADMAP/BL-17.md` "A failed action throws 'unable'", user 2026-11-18): a failed rule
action now raises `RuleUnable(reason)`/`RuleRuntimeError` from inside the `_make_action_wrapper`
Python callback (`body-layer/src/rules/engine.py`) instead of returning `{ok=false}`, and
`run_rule` catches it in one place instead of 17 duplicated `if not r.ok then ...` blocks in
`config/rules/flight.lua`. APPROVED, no fixes required. Two things worth keeping beyond what
`plans/speech-rules/security-unable-throw.md` already records:

1. **The unwrapped-Python-exception-through-lupa finding
   ([[project_lupa_sandbox_quirks_bl17_stage0]] point 6) extends to a *nested* Lua call frame.**
   The Stage 0 research and the shipped `flight.lua` only ever exercise one Lua frame calling the
   Python-backed action directly. I wrote a throwaway probe with `local function helper() return
   probe.one(3) end` calling the action one level deeper and confirmed `RuleUnable` still
   propagates cleanly out to `run_rule`'s own `except RuleUnable` clause, with lines already
   `say()`-ed before the failing call preserved and nothing after it spoken. Nothing in the
   codebase currently calls an action through an intermediate Lua function, but if a future rule
   file ever does, this is already proven safe — no need to re-probe it.
2. **`run_with_budget`'s `finally: self._debug_sethook(None)` survives an exception type its own
   `except` clauses don't name.** `RuleUnable`/`RuleRuntimeError` raised inside the callback are
   neither `_InstructionBudgetExceeded` nor `lua54.LuaError`, so they fall through
   `run_with_budget`'s two `except` clauses unmatched — but Python's `try/finally` still runs the
   `finally` during that propagation, so the instruction-count hook is disarmed regardless. Ran 5
   consecutive `RuleUnable`-raising dispatches on one `RuleSandbox` followed by a clean dispatch
   of an unrelated rule to confirm no leaked arm state / corrupted budget counter. This is the kind
   of thing that *looks* like it should need the exception type explicitly handled and doesn't —
   worth remembering so a future reviewer doesn't assume an unmatched `except` means the cleanup
   was skipped.

**Why a rule cannot forge or abuse the exception**: the sandbox's `_SAFE_GLOBAL_NAMES`
(`body-layer/src/rules/sandbox.py`) excludes `pcall`/`xpcall`/`error`/`debug` entirely, so there is
no Lua-side mechanism to catch, inspect, or construct either exception type, and `RuleUnable.
reason` is always a fixed, code-chosen string from the action's own Python `invoke` (never
built from a rule-supplied argument, in every action shipped as of this commit) — and even if it
were, `render_unable`'s `_UNABLE_TEMPLATES.get(reason, "Unable.")` is a closed dict lookup, not
string interpolation, so a forged reason degrades to a plain "Unable." rather than leaking
arbitrary text into speech.

Check for this again if a future action ever builds its `reason` from a rule-supplied value
(none do today) — that would be the first case where `reason` carries anything other than a
closed, code-chosen token.
