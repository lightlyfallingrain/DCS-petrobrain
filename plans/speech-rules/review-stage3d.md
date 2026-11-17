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

---

## Re-review (Fix 4) — 2026-11-17

Branch `feature/speech-rules-matching`, fast-forwarded cleanly onto this worktree's prior tip
(`fc282270`) to `078e0b04` — no conflicts, no snapshot fallback needed. Scoped to Required Fix 4
only: the fix commit (`28baf690`) plus the same-day follow-up (`078e0b04`) that caught and closed
its own production gap. Stage 4 (flight-control port, `04217983`/`f67b332c`/`6a6ce8e7`) sits below
these on the branch and is out of scope here, per the task brief.

### Required Fix 4's own rollback (basic + concurrent-dispatch) — VERIFIED FIXED, not taken on faith

`28baf690` mints a fresh `object()` token per `_dispatch_rule` call, stores it on a new
`threading.local` (`_dispatch_token_local`) for the duration of the `rule_runner` call, stamps it
onto every `PendingEffectorWrite` queued during that call, and — on a Lua error — filters
`pending_effector_writes` by `is not token`, never by a length/count snapshot. This is exactly the
identity-based shape the prior round required, for exactly the stated reason (a shared,
lock-free, append-only list, appended to from either thread without a lock).

I did not take the implementer's own counterfactual claim on faith — I reproduced it myself: with
the real `.venv`, I temporarily replaced the token-filter with the rejected
`del self.pending_effector_writes[_before_len:]` shape (a `len()` snapshot before `rule_runner`,
a truncate after) and reran the two new tests. `test_rollback_leaves_a_concurrent_dispatchs_own_
queued_write_alone` failed exactly as claimed (`assert [] == [('weapons', 'safe')]`, rule B's
unrelated entry discarded alongside rule A's) and `test_a_write_then_a_later_error_in_the_same_
dispatch_is_rolled_back` still passed (the single-dispatch case does not distinguish the two
shapes) — confirming the second test, not the first, is the one actually exercising the reason a
length-based truncate is wrong, same conclusion the implementer's own write-up draws. Restored the
real filter afterward; `git status --porcelain` and `git diff --stat` both confirmed a clean
revert, and the full `pending_effector_writes`-touching test file (12 tests) passed again
afterward.

### Follow-up (`body.py`'s closure never stamped the token) — VERIFIED FIXED, grep fences mutation-tested

`078e0b04` adds `CrewConsole.queue_effector_write` as the one appender (stamps `dispatch_token=
self.current_dispatch_token()` itself) and routes `body.py`'s real `_request_effector_write`
closure and every test closure through it instead of constructing `PendingEffectorWrite` by hand.
This closes a real production gap the first commit left open: before this follow-up, the
*rollback* was correct but the one caller that matters in flight never stamped a token, so it had
nothing to find.

I mutation-tested both new grep-fence tests rather than reading them and trusting they'd fire:

- Reintroduced a hand-built, bare `PendingEffectorWrite(...)` append inside `body.py`'s closure
  (via an aliased import, `from belief.crew_console import PendingEffectorWrite as _PEW`, to rule
  out the fence matching only the literal unaliased name) — `test_body_py_never_constructs_
  pending_effector_write_directly` failed for the stated reason, catching the alias too (it
  asserts the bare substring `"PendingEffectorWrite"` is absent, not just the call form).
- Added a second, harmless `PendingEffectorWrite(...)` construction elsewhere in
  `crew_console.py` — `test_pending_effector_write_is_constructed_in_exactly_one_place_in_crew_
  console_py` failed for the stated reason (`2 == 1`).

Both mutations reverted; `git status --porcelain` clean afterward, both tests pass again.

### New finding — Required Fix 4's own guarantee is still defeatable, by a different interleaving than either test covers

**Required**, for the same reason Required Fix 1 and Required Fix 4 itself were each required
over "low probability" — this project's own stated bar, set twice already in this review, does
not get relaxed a third time.

Required Fix 4's stated guarantee is unconditional: *"a switch must not move, and no confirmation
must be spoken, for an action whose own dispatch just reported 'Action file error.'"* That holds
against the two interleavings already tested (a single dispatch; two concurrent *dispatches* each
queuing their own write). It does **not** hold against a third interleaving neither test
exercises: **Required Fix 1's own poll-thread drain step racing against an in-flight REPL-thread
dispatch's still-open rollback window.**

`handle_line` → `handle_command` → `_handle_rule` → `_dispatch_rule` runs **entirely on the REPL
thread** when the command is typed (`_run_crew_text_repl`, confirmed by reading the call chain —
this is the *same* foreground REPL `_run_crew_text_repl`'s own docstring describes as "every
player-issued report command," not a dev-only shell; `--crew-text` is unconditional, `BL-B96`).
Nothing in `_dispatch_rule` prevents the **poll thread** — running independently, on its own
1 Hz-default cycle (`_DEFAULT_POLL_INTERVAL_S`), with no lock anywhere in `body.py` or
`crew_console.py` — from executing its own unconditional per-poll drain
(`pending_writes, crew_console.pending_effector_writes = crew_console.pending_effector_writes,
[]`, `body.py` ~line 5089, Required Fix 1's own mechanism) **while** a REPL-thread dispatch is
still open: past its own `effector.write` call (which has already appended to the shared list),
not yet at the later statement in the same handler that raises. If the poll thread's drain lands
in that window, it removes the entry from `pending_effector_writes` and feeds it into
`effector_state` (where it starts actually executing) **before** the REPL dispatch's own
token-filter rollback ever runs. The filter then finds nothing carrying that token — not because
nothing was queued, but because it was already drained by an unrelated step — and the write
proceeds to completion: the switch moves, and if `says` was given, the confirmation is eventually
spoken, despite "Action file error." having already been returned for that exact dispatch.

This is a different bug than the one either new test targets. Test (2)
(`test_rollback_leaves_a_concurrent_dispatchs_own_queued_write_alone`) proves the token filter
correctly leaves a *second dispatch's* concurrently-queued entry alone — it never drives the
*poll thread's own drain* during the window, because neither of its two threads ever calls the
drain code (both just append via `request_effector_write`/`queue_effector_write`). Nothing in this
round's diff, and nothing in the implementer's "Lua-level concurrency note," addresses this
interleaving — that note is about two *dispatches'* Lua execution never truly overlapping
(lupa's per-runtime lock), which is a fact about the window's *shape*, not about whether something
*else* (the poll thread, not bound by that lock at all, since it never touches a `RuleSandbox`)
can act inside it.

**Demonstrated, not just argued.** I wrote a standalone probe (reproducing the exact
`test_rollback_leaves_a_concurrent_dispatchs_own_queued_write_alone`-style rule, but simulating
the poll thread's own drain — `pending_writes, console.pending_effector_writes = console.
pending_effector_writes, []`, body.py's exact line — from the test harness itself, during the
dispatch's open window instead of a second dispatch) against the real, unmodified code:

```
drained by 'poll thread' while dispatch still open: [PendingEffectorWrite(request_id='req-1',
  effector='observ', value='on', says='Observ on.', dispatch_token=<object object at ...>)]
dispatch result: [['Action file error.']]
pending_effector_writes after rollback: []
```

The entry is drained away intact — carrying the correct token, correctly stamped — and the
rollback's own filter (now running against an empty list) has nothing left to remove. `effector_
state` would receive it on the very next `request_effector_write` call inside that same drain,
and the switch would proceed exactly as if the dispatch had never errored.

**Why this is in scope for Fix 4, not a pre-existing Fix-1-only gap.** Required Fix 1's drain is
correct *in isolation* — it is what makes "the write progresses even when queued from the REPL
thread" possible at all, and that's the point of the field being a plain list rather than a
one-shot slot (`feedback_cross_thread_one_shot_queue_vs_single_slot.md`: "an entry queued by an
earlier dispatch this poll has not yet drained must survive"). The gap is specifically in Fix 4's
own added guarantee: a rollback that identifies entries by a token stamped *after* they are
already visible on the shared list can always lose a race to anything else that reads that same
shared list before the rollback runs — and the poll thread's drain is exactly such a reader,
already in this codebase, already required to run unconditionally and without a lock (Fix 1's own
constraint). Fix 4 added a second consumer of the same list (a rollback) without reconciling it
against the first consumer (the drain) that was already reading from it independently.

**What the right fix shape looks like** (for the Implementer to build, not prescribed in detail
here): the queuing side needs to make an entry invisible to the poll thread's drain until the
dispatch that queued it has already decided whether to keep or discard it — i.e., buffer-then-
commit rather than append-then-maybe-roll-back. Concretely, `_dispatch_rule` could collect writes
requested during its own call in a **thread-local** buffer (not the shared `pending_effector_
writes` list) — `queue_effector_write` would append there instead, only visible to the calling
thread — and `_dispatch_rule` itself extends the shared list with that buffer's contents on
success, or discards the buffer entirely on error, after `rule_runner` returns. Nothing partial is
ever visible to the poll thread, so there is nothing for its drain to race against, and the
`dispatch_token` field/filter machinery built in `28baf690` is no longer needed at all (this would
be a simplification, not an addition). A lock around the drain is **not** the right fix — it would
reintroduce exactly the kind of cross-thread blocking Required Fix 1 was built to avoid, and would
also defeat D20's own "a voice-dispatched write starts progressing this same poll" requirement for
the one thread (poll) where same-poll progression is actually wanted.

**Required test coverage for whatever shape is built**: a test that opens a REPL-style dispatch
(blocked mid-handler, after its own `effector.write` call, before its own error), runs the poll
thread's real drain code against the shared list *during* that window, then lets the dispatch
error — and asserts `effector_state`/`ad_hoc_runs` received **nothing** from that dispatch (not
just that `pending_effector_writes` ends up empty, which is true either way and would pass even
against the current, still-racy code once the entry has already been drained).

### Verdict

CHANGES REQUIRED — Required Fix 4's own rollback and its same-day follow-up are both correctly
built and tested for the interleavings they target (verified above by independent mutation, not
taken on faith). One new required fix remains: the rollback can still be defeated by Required Fix
1's own poll-thread drain racing a REPL-thread dispatch's open window, demonstrated above with an
unmodified-code probe. This must close before this stage merges, on the same "no shipped rule
reaches it yet does not bound the window" reasoning this review has already applied twice in this
same stage (Required Fix 1's original race, and Required Fix 4 itself).

### Review Confidence

Full read of `28baf690` and `078e0b04`'s diffs against their own commit messages and
`implementation.md`'s account. Built a fresh `.venv` (none existed in this worktree), ran
`ruff format --check`, `ruff check`, `mypy --strict src` (all clean, 91 source files) and
`fast-tests.sh body-layer` myself (2671 passed, 1 failed — the same named pre-existing
`test_shipped_effector_config_loads_without_errors`, 4 xfailed — matching the task brief's stated
known failure exactly), plus the touched test file directly (12/12 pass). Independently mutated
and reverted, rather than trusting either account: the rollback filter itself (swapped for the
rejected length-based truncate, confirmed the concurrency test is the one that tells the
difference), and both new grep-fence tests (reintroduced a direct construction via an aliased
import in `body.py`, and a second construction site in `crew_console.py`; both fences fired for
the stated reason). The new finding was reached by asking, for each of Required Fix 4's two
threads, "what else reads or mutates `pending_effector_writes` independently of this call stack,"
not by re-reading the diff alone — `body.py`'s own per-poll drain block (Required Fix 1's
mechanism, unchanged by this round) is the answer, and I demonstrated the resulting race with a
standalone probe against the real, unmodified code rather than arguing it from the call graph
alone. Did not re-review Stage 4 (flight-control port, out of scope per the task brief) or
audio-adapter (untouched by either commit).
