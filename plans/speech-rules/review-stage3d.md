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
