# Review: BL-17 Stage 3d — effector-write action surface (D20)

Branch `feature/speech-rules-matching`, commit `68387d90` (fast-forwarded cleanly onto this
worktree's prior tip `fc282270`; no conflicts, no snapshot fallback needed). Reviewed against
`plans/speech-rules/plan.md` Revision 2's D20/Stage 3d section, U24, `body-layer/ROADMAP/BL-17.md`'s
"Rules can write effectors, from the start" decision, and `body-layer/CLAUDE.md`'s effector
paragraph. `implementation.md`'s own "Notable Discoveries" for this stage is accurate and was
checked against the code, not taken on faith.

### Review Summary

The extraction (`_execute_switch_row`) is behaviour-preserving — the full pre-existing
`test_effector_engine.py` suite (regression pin) passes unchanged, and a line-by-line diff of the
extracted block against the pre-extraction inline code shows no logic change, only the condition
check moving from `row.condition`/`registry.get` (caller-resolved) into explicit parameters. The
new ad-hoc-write pass correctly shares `assumed_writes`/`commanded_values`/`failed_effectors`/
`spoken` with the trigger-run pass within one `advance()` call (confirmed in code: all four are
built once at the top of `advance` and passed by reference into both passes), so D9's same-poll
collision rule holds across both kinds of run — and is explicitly tested
(`test_advance_ad_hoc_and_sequence_row_same_poll_collision_shares_failed_effectors`). Category
gates need no new mechanism and get none — `_handle_rule`'s gate check runs before any rule's Lua
handler, including one that calls `effector.write`, so this falls out of Stage 3b's existing
mechanism for free. `effector.write`'s validation (name/value against the live registry) happens
before the engine is ever touched, and no bare Python exception reaches D6's rollback path for any
input shape tested (unknown effector, illegal value, missing optional arg) — confirmed by tracing
`_make_action_wrapper`'s type checks, which run ahead of `_write_effector`'s own `assert`s.

Two things in this stage are **real, not latent-and-safe-to-ignore**, despite "no shipped rule
calls this yet": `config/rules/README.md` already documents `effector.write` as a live Lua call,
and nothing in the loader gates it behind a stage number — any `.lua` file dropped into
`config/rules/` from this commit onward can reach it. That changes how I weighed the two items
below against "defer to Stage 5."

**Checks:** `.venv` built fresh from `/opt/homebrew/bin/python3.14` (none existed); `ruff format
--check`, `ruff check`, `mypy --strict src` all clean (91 source files). `fast-tests.sh body-layer`:
2653 passed, 1 failed (`test_shipped_effector_config_loads_without_errors` — the named
pre-existing, unrelated `seat-copilot.md` empty-row failure), 4 xfailed. Matches the task brief's
stated known failure exactly.

### Required Fixes

1. **Cross-thread race on `crew_runner.effector_state` — fix now, not at Stage 5.**
   `body.py`'s `_request_effector_write` closure mutates `crew_runner.effector_state` directly,
   synchronously, at rule-dispatch time. `handle_command` — and therefore any rule's handler,
   including one that calls `effector.write` — is reachable from **two threads**: the poll thread
   (`handle_transcript`, voice) and the REPL thread (`_run_crew_text_repl` → `handle_line` →
   `handle_command`, typed input), confirmed by reading both call chains and
   `CrewConsole.handle_command`'s own `elif token in self.enabled_rule_ids` branch (line ~3455).
   The poll thread also assigns `runner.effector_state = advance_effectors(...)` (and seven
   `fire_effector_trigger` calls) unguarded, every poll. A REPL-thread dispatch racing one of
   those is a genuine lost-update: whichever assignment lands second silently discards the other's
   state (a completed write disappearing from `assumed_writes`, a spoken line disappearing from
   `spoken`, or an `ad_hoc_runs` entry reverting).

   This is a real design decision the plan's own D20 text explicitly chose ("against `body.py`'s
   own runner-owned `EffectorRunState`"), and the implementer caught it, documented it precisely in
   both `implementation.md`'s "Notable Discoveries" and a persistent memory note, and proposed the
   right fix — but deferred it to Stage 5 on the reasoning that "no shipped rule calls
   `effector.write` ... the race is latent and unreachable in practice." That reasoning holds only
   if reachability requires a *shipped* rule. It does not: `effector.write` is already a
   documented, callable Lua action the moment this merges, and Stage 4 (flight-control port, being
   built in parallel) touches none of `effector_state`/`ad_hoc_runs`, so nothing about Stage 4's
   own schedule bounds this window — a stray test rule, a quick hand-written `.lua` file during
   Stage 4 work, or anything added before Stage 5 is formally scheduled, reaches it today.

   **Required**: route the ad hoc write request through a one-shot field the poll loop itself
   drains once per poll — the same shape `observ_transition`/`weapon_safety_transition` already
   use, and the shape every *other* cross-thread effector path in this codebase is held to. This
   is applying an existing, established mechanism, not inventing a second one: the implementer's
   own proposed fix is correct and specific enough to build now rather than wait for Stage 5 to
   need it under schedule pressure — the same justification D20 itself used for building the write
   surface ahead of its first caller.

2. **`request_write`'s dedup drops a differing-value second request with no replacement, no
   error, and a misleading eventual confirmation.** The dedup check (`any(ad_hoc.effector == name
   ...)`) matches on effector name only, not value — so a second `effector.write` call naming the
   same effector as an already-pending ad hoc run is a silent no-op **even when its target value
   differs from the first's**. Concretely: if a future rule calls `effector.write("weapons",
   "safe", "Weapons safe.")` and, before that resolves, a second rule calls `effector.write
   ("weapons", "armed", "Weapons armed.")`, the second call is dropped — the switch ends up (or
   stays pending) at `"safe"`, and if the first write later completes, Petrovich says "Weapons
   safe," directly contradicting what the pilot most recently asked for. The plan's own test-list
   wording ("a second request for the same effector while one is pending is a no-op") only ever
   considered the same-value case (mirroring `fire_trigger`'s D1 shape, where re-firing a trigger
   is idempotent because a trigger always resolves to the same fixed sequence) — a differing-value
   case has no equivalent at the trigger level, since `fire_trigger` carries no value of its own,
   and nowhere in the plan is the differing-value case named or deferred the way U24 explicitly
   names and defers the failing-write tension. This is also not what this project does elsewhere
   for a structurally equivalent arbitration question: `AiPilotWheelGoal`'s own rule is "latest
   wins, nothing lost" (`body-layer/CLAUDE.md`, flight-control), and losing the pilot's most recent
   instruction silently is exactly the "co-moving fields" and "no omniscience" class of defect this
   role's checklist calls out — a callout that fires with the wrong content is worse than one that
   doesn't fire.

   **Required, in one of two forms**: either make the dedup value-aware (a differing-value request
   replaces the pending entry's target rather than being dropped, consistent with this project's
   existing latest-wins convention), or — if first-wins is actually the intended behaviour for some
   reason not yet stated — write that decision down explicitly (a new `U`-numbered entry, the same
   way U24 names and defers the failing-write tension) and add one line to
   `config/rules/README.md`'s `effector.write` row saying so, so a future rule author is not
   surprised by it. Leaving it unstated and untested is the one outcome that must not stand,
   because nothing else in this stage's test list would ever catch it.

3. **`says` has no length cap on the ad hoc path, unlike `say()`'s own `_MAX_SAY_LEN`.** The plan's
   D20 text states explicitly: `says` is "a free-text, length-capped string (the same cap `say()`
   already enforces)". Nothing enforces it — `_make_action_wrapper` only type-checks a `kind="str"`
   parameter, `_write_effector` passes `says` through unexamined, and `_speak_text`/
   `_execute_switch_row` apply no cap before appending to `EffectorRunState.spoken`, which
   eventually reaches the audio adapter over HTTP. Low practical severity today (rule files are
   hand-authored by the project's sole developer, not adversarial input, and `_MAX_SAY_LEN`'s own
   comment says it "bounds a pathological rule, not real wording") — but it is an explicit, stated
   requirement of this stage that was not built, and the gap is the same shape `_MAX_SAY_LEN` was
   introduced to close for `say()` itself. Cap it the same way, either in `_write_effector` or
   alongside `_speak_text`, before this path's first real caller.

### Optional Refinements

- **Add a test for `effector.write("x", "on", nil)`** — an explicit Lua `nil` as the third
  argument, distinct from omitting it entirely (`test_effector_write_says_is_optional` covers only
  the omitted case). The implementer's own persistent memory note on this exact pattern
  (`feedback_lua_native_function_optional_trailing_arg.md`) says to write both; "Notable
  Discoveries" claims the nil case is "covered implicitly," but no test in this diff actually
  passes a literal third `nil` argument to `effector.write`. I traced `_make_action_wrapper`'s
  logic by hand for this exact case and it is correct (an explicit `None` on a declared-optional
  parameter is accepted the same as an omission), so this is a coverage gap, not a known defect —
  optional because the behaviour is already right, just unproven by a test that exercises it
  specifically.
- Once Required Fix 2 is settled, add the resulting dedup/replace behaviour to
  `config/rules/README.md`'s `effector.write` row — the current row says only that the action
  "queues a cockpit switch write," with nothing about what happens to a second call naming the same
  effector.

### Verdict

CHANGES REQUIRED

### Review Confidence

Full read of the diff (`effector_engine.py`, `body.py`, `rules/actions.py`, `rules/engine.py`,
`config/rules/README.md`, and every new/changed test file), the plan's D20/Stage 3d/U24 text, the
roadmap decision, the implementer's own account and memory notes, and the thread-reachability
claim (traced `handle_command`'s dispatch branch and both its callers — the poll thread's
`handle_transcript` and the REPL thread's `handle_line` — by reading the actual call chains rather
than taking the implementer's note on faith). Ran the full subproject check suite myself
(`ruff format --check`, `ruff check`, `mypy --strict`, `fast-tests.sh body-layer`) after building a
fresh `.venv`, rather than trusting the reported numbers. Did not independently re-derive the
Stage 3a/3b content that arrived via the fast-forward (out of this review's scope per the task
brief) or re-review audio-adapter (untouched by commit `68387d90`).

---

## Re-review — 2026-11-17

Branch `feature/speech-rules-matching`, fast-forwarded cleanly onto this worktree's prior tip
`fc282270` to `eba9cb5c` ("BL-17: Stage 3d review fixes") — no conflicts, no snapshot fallback
needed. Reviewed `eba9cb5c`'s diff directly against the three Required Fixes above, `U21`/
`AiPilotWheelGoal`'s "latest wins, nothing lost" convention, and the implementer's own account in
`implementation.md`'s "Stage 3d review fixes" section.

### Required Fix 1 (cross-thread race) — VERIFIED FIXED

`body.py`'s `_request_effector_write` closure (around line 6558) no longer touches
`crew_runner.effector_state` at all — it validates and appends a new frozen
`belief.crew_console.PendingEffectorWrite(request_id, effector, value, says)` to
`CrewConsole.pending_effector_writes: list[PendingEffectorWrite]`. The poll loop (`body.py`
~line 5073) drains it with a swap-to-fresh-list (`pending_writes, crew_console.
pending_effector_writes = crew_console.pending_effector_writes, []`), immediately before
`advance_effectors`, calling `request_effector_write` once per queued entry against
`runner.effector_state` — exactly the place `observ_transition`/`weapon_safety_transition` are
already applied, as promised. The new field's own docstring correctly states why it is a list and
not a one-shot slot (several different effectors may be queued before one drain), why `list.append`
from either thread is safe (GIL-atomic), and why it is deliberately absent from
`_reset_one_shot_command_state`'s field list (an earlier dispatch's undrained entry must survive
an unrelated later command) — all three claims checked against the code, not taken on faith.
`test_effector_write_queued_from_background_thread_is_applied_on_next_poll_drain` dispatches from
a real `threading.Thread`, asserts nothing reaches any `EffectorRunState` from that thread, then
drives the simulated poll-thread drain itself and asserts the request only lands there — the right
boundary to test given `body.py`'s own `main()` wiring is untested by design.

### Required Fix 2 (differing-value dedup) — VERIFIED FIXED

`effector_engine.request_write` now looks up the pending entry by effector name first (unchanged
from before), then branches on `.value`: same value → logs and no-ops exactly as before (D1's
shape, unchanged); different value → deletes the old `request_id` entry and inserts a fresh one
under the *new* `request_id` with the new `value`/`says` — a true replace, not a merge-in-place,
so a stale `request_id` can never be found in `ad_hoc_runs` afterward. Matches the specified
semantics exactly (latest wins, same value stays a no-op).
`test_request_write_with_a_differing_value_replaces_the_pending_request` asserts
`set(state.ad_hoc_runs) == {"req-2"}` (old id gone) and the new cursor's `value`/`says` — this is
the right assertion shape; a weaker one (just checking the final value) would have passed even if
the implementation had left the stale `req-1` entry sitting alongside, which `advance`'s
`_execute_switch_row` pass would then have tried to execute concurrently against the same switch.
`config/rules/README.md`'s `effector.write` row states both halves of the rule in the prose a rule
author would read, not just in a docstring.

### Required Fix 3 (`says` length cap) — VERIFIED FIXED

`MAX_SAY_LEN` moved from `rules/engine.py` (`_MAX_SAY_LEN`) to `rules/actions.py` (public,
`Final[int] = 500`) to avoid the cyclic import, and `engine.py` now imports and uses the shared
constant for `say()`'s own cap — confirmed `_SinkHolder.say`'s behaviour is unchanged (same cap
value, same silent-truncate, not a rejection). `_write_effector` now truncates `says` to
`MAX_SAY_LEN` *before* calling `ctx.request_effector_write`, so neither the closure, the queue,
the engine, nor the eventual spoken line ever sees an uncapped value.
`test_write_effector_caps_says_at_the_same_length_say_enforces` asserts both the truncation point
and that the untruncated case (`test_write_effector_says_within_the_cap_is_untouched`) is
unaffected — good coverage of both sides of the boundary.

### Optional refinement (explicit Lua `nil`) — DONE

`test_effector_write_says_explicit_nil_is_also_optional` passes a literal third `nil` argument
(distinct from omitting it) and asserts the same `(name, value, None)` outcome as the
omitted-argument test beside it. `implementation.md`'s "Notable Discoveries" entry is corrected
to no longer claim this was "covered implicitly."

### Checks — all pass except the named pre-existing failure

`.venv` built fresh from `/opt/homebrew/bin/python3.14` (none existed in this worktree);
`ruff format --check`, `ruff check`, `mypy --strict src` (91 source files) all clean.
`fast-tests.sh body-layer`: 2658 passed, 1 failed
(`test_shipped_effector_config_loads_without_errors` — the named pre-existing, unrelated
`seat-copilot.md` empty-row failure), 4 xfailed — matches the task brief's stated known failure
exactly. Also re-ran the four touched-module test files directly (75 tests) in isolation: all
pass.

### Required Fix 4 (new) — the D6 rollback gap the implementer flagged must be closed, but not
### with the fix shape its own write-up suggests

**This is required, not optional, and for the same reason Required Fix 1 above was required over
"no shipped rule reaches this yet": `effector.write` is a documented, callable Lua action from the
moment this merges, and D6's own contract is unconditional —** *"A Lua error at dispatch time →
... every one-shot transition field set during this dispatch is cleared, so the action does not
happen without the pilot hearing about it."* **This is a different case from the one D20 already
decided to leave alone.** D20's own text says *"D6 rollback does not apply here, and should
not... an ad hoc effector write that **later fails** is not a dispatch-time error (dispatch
already returned 'queued' cleanly)"* — that is about the engine's own multi-poll execution failing
on a *later* poll, after a clean dispatch. The gap here is narrower and squarely inside D6's own
scope: a rule handler calls `effector.write` (which queues cleanly), and *then*, still inside the
**same** Lua dispatch, something else in the handler raises `RuleRuntimeError`/
`RuleBudgetExceeded`. `_dispatch_rule` catches that, calls `_reset_one_shot_command_state()`, and
returns `ACTION_FILE_ERROR_LINE` — but `pending_effector_writes` is not in that reset's field
list (correctly, for the reason its own docstring gives: an *earlier* dispatch's undrained entry
must survive), so the entry *this* dispatch just queued survives too. Concretely: a rule writes
`effector.write("weapons", "armed", "Weapons armed.")` and then hits a bug three lines later;
Petrovich says "Action file error," and the switch still moves (and, if `says` was given, he later
says the confirmation line for an action he just told the pilot didn't happen) — the exact
"callout fires with the wrong content" failure this role's checklist names, and worse than D20's
own already-accepted tension (silence on a late failure) because this one speaks a confirmed
contradiction.

**Why "snapshot the queue length at dispatch start, truncate on error" (the shape suggested in the
dispatching brief) is not safe to build as stated, and the reviewer flagging it here is required,
not optional, before it ships:** `pending_effector_writes` is shared and appended to from
*either* thread without a lock (that is the entire point of Required Fix 1 — GIL-atomic
`list.append`, no lock needed for an append-only field drained wholesale on one thread). A
length-based truncate is not append-only-safe: if the REPL thread's dispatch snapshots
`before = len(pending_effector_writes)`, then while its own Lua handler is still running the poll
thread's voice dispatch appends its *own*, unrelated, legitimately-queued entry, and then the
REPL dispatch's handler errors — `del pending_effector_writes[before:]` deletes both entries,
silently discarding the poll thread's write along with the REPL dispatch's own. That is precisely
the class of bug Required Fix 1 exists to prevent, reintroduced by the fix for a different bug.
This is a low-probability window (two concurrent dispatches, each queuing a write, with one
erroring, inside one dispatch's instruction budget), but this project does not get to apply a
lower correctness bar to a low-probability cross-thread race than Required Fix 1 was just held to
one review cycle ago — consistency requires the same standard here.

**What is required**: a rollback that identifies *which* queued entries belong to *this specific
dispatch*, not a position- or count-based snapshot of a shared list. The natural shape, consistent
with how this field already avoids a lock: give `_dispatch_rule` a way to mark "entries queued
during this call" by identity, not by range —
for example, a dispatch-scoped token (minted fresh by `_dispatch_rule`, e.g. an incrementing
counter or `object()`, stored so the calling thread's own closure invocation can read it — thread-
local is the natural mechanism, since a thread never runs two dispatches at once but the two
threads run independently) attached to each `PendingEffectorWrite` at append time (a new field,
defaulting to `None` so the existing direct-construction tests are unaffected), and on error,
filtering `pending_effector_writes` to drop exactly the entries carrying *this* dispatch's token —
never a `[:n]`/`[n:]` slice of the shared list. This correctly rolls back every `effector.write`
call the errored handler made (a handler can call it more than once before erroring), and
correctly leaves any other thread's concurrently-queued, unrelated entry alone.

**Required test coverage**: (1) the basic case — a rule that calls `effector.write` then raises,
dispatched through the real `_dispatch_rule`/`handle_command` path (not `run_rule` directly, the
way the Required-Fix-1 test necessarily bypasses `_dispatch_rule`), asserting
`pending_effector_writes` is empty afterward and the line spoken is `ACTION_FILE_ERROR_LINE`; and
(2) the concurrency-safety case, mirroring Required Fix 1's own test shape — a second, real
background thread's unrelated `effector.write` call queued *during* the erroring dispatch's
window must still be present in `pending_effector_writes` after the rollback. Test (2) is the one
that actually exercises the reason a length-based truncate is wrong, and should fail against the
naive implementation before it is fixed, not just against no implementation at all.

### Verdict

CHANGES REQUIRED — Required Fixes 1–3 and the optional nil test are all correctly built and
tested; one new Required Fix (4, above) must be closed before this stage merges.

### Review Confidence

Full read of `eba9cb5c`'s diff (`body.py`, `crew_console.py`, `effector_engine.py`,
`rules/actions.py`, `rules/engine.py`, `config/rules/README.md`, every changed test file, and the
implementer's `implementation.md` account), cross-checked against the three Required Fixes'
original text and `U21`'s convention. Built a fresh `.venv` and ran `ruff format --check`,
`ruff check`, `mypy --strict`, and `fast-tests.sh body-layer` myself, plus the four touched test
files directly in isolation, rather than trusting the reported numbers. Required Fix 4 was reached
by tracing `_dispatch_rule`/`_reset_one_shot_command_state`'s actual field list and D20's own
"D6 rollback does not apply here" paragraph side by side, not by taking either account at face
value — the two are about different failure windows, and the text of D20's carve-out does not
cover the gap the implementer flagged. Did not independently re-derive Stage 3a/3b (out of scope,
unchanged by this commit) or re-review audio-adapter (untouched).
