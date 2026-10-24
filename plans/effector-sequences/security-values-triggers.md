## Security Deep Analysis: value-range generator, switch-reference Values column, triggers.md, mission-start triggers

Branch `feature/switch-reference-values`, reviewed at `8fd8fc38b8500b0ded9744c9708a6e163a95e5be`
(checked out detached in-worktree after confirming `git rev-parse HEAD` matched the dispatcher's
expected tip exactly; tree clean before and after).

Diff reviewed: `git diff 27c19054 8fd8fc38 -- body-layer aircraft-layer` (18 files, +4431/-741).

**Threat model applied (root `CLAUDE.md`, 2026-10-21): single-user, LAN-only. Realistic attackers
are (1) malicious code in a dependency and (2) an infected LAN machine port-scanning.** Nothing in
this batch is network-reachable or user-supplied over the wire: the generator reads ED's own
shipped Lua files from the local DCS install (a build-time, developer-invoked tool, not a runtime
service), and the two new triggers are driven by local ownship telemetry already inside the trusted
body-layer↔aircraft-layer LAN boundary accepted by `security-stage1-2.md`.

### Dependency Status

No dependency change. The one new import across the whole batch is stdlib `ast`
(`generate_effector_registry.py`), used only by the constant-arithmetic evaluator below. Confirmed
by reading every changed file's import block — no new third-party package, no new network client,
no new file-format library.

### Focus 1 — the `ast`-based constant-arithmetic evaluator (`generate_effector_registry.py`)

This is the one place in the batch that parses text into something evaluated, so it gets the
closest reading.

- **No `eval`/`exec`.** `_lua_arithmetic` calls `ast.parse(text, mode="eval")` to get a syntax
  tree, then walks it by hand in `_eval_constant_arithmetic` — nothing in this path calls Python's
  `eval`/`exec`/`compile`-and-run on the string; `ast.parse` alone does not execute anything, it
  only builds a tree.
- **Node whitelist is a strict allow-list, not a deny-list.** `_eval_constant_arithmetic` recognises
  exactly three node shapes and returns `None` (unresolved) for everything else: `ast.Constant`
  (restricted further to `int`/`float`, explicitly excluding `bool`, since `isinstance(True, int)`
  is true in Python and a stray `bool` constant is never meaningful arithmetic here), `ast.UnaryOp`
  with `ast.USub` only (no `ast.UAdd`/`ast.Not`/`ast.Invert`), and `ast.BinOp` restricted to
  `_ARITHMETIC_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)`. There is no `ast.Call`, no
  `ast.Name`, no `ast.Attribute`, no `ast.Subscript`, no comprehension, no `ast.Pow` anywhere in the
  whitelist — confirmed by reading the function body line by line, not just the module's own claim.
  A `Name` (e.g. `anim_speed_default`), a function call, a string, a comparison, or any node this
  function does not explicitly check falls through to the final `return None`, which
  `_lua_scalar` turns into the `_UNRESOLVED` sentinel rather than a guessed value — the caller is
  required to treat that as "unknown," never substitute a default silently (verified: every call
  site that receives `_UNRESOLVED` either returns an `unknown`-kind `ValueRange` with a reason
  string, or treats it as a hard failure for that element; none of them falls through to using the
  unresolved text as a number).
- **No `Pow`.** Explicitly checked — `_ARITHMETIC_BINOPS` has four members, `**` is not one of them,
  and there is no separate branch for `ast.Pow` anywhere in the function. An expression like `2**64`
  is syntactically valid Python/Lua-adjacent text but is not in the whitelist, so it returns `None`
  (unresolved), not evaluated. This matters because unbounded `Pow` is the classic way a
  "safe" arithmetic evaluator stops being safe (CPython has no depth/size cap on big-int
  exponentiation) — it is absent here, not merely unexercised.
- **Recursion depth.** `_eval_constant_arithmetic` recurses once per `UnaryOp`/`BinOp` node, bounded
  by the depth of the parsed expression tree, which in turn is bounded by the length of the input
  text (each level of nesting needs at least one more character). The input is a single Lua call
  argument's source text — in practice a few characters (`1/9`, `0.2 * 5 / 6`) — never a
  network-received or otherwise attacker-sized string. A pathologically long, deeply-parenthesised
  literal embedded in a compromised `clickabledata.lua` could in principle drive Python's own
  recursion limit (`ast.parse` itself, and this function's recursive walk, both recurse per nesting
  level) and raise `RecursionError`, which is **not** caught by `_lua_arithmetic`'s
  `except SyntaxError`/`except ZeroDivisionError` pair. Scoped per the threat model: this is a
  build-time, developer-invoked tool reading a local DCS install, not a service reachable by a LAN
  port scanner or network input — the realistic path to a hostile `clickabledata.lua` is a
  compromised/tampered DCS installation, which is a far larger compromise than this one function.
  A `RecursionError` here crashes the generator script with a traceback; it cannot write anything,
  corrupt anything, or execute attacker code — a `main()`-only failure that stops the tool before
  it writes the TOML, the same "even an unanticipated bug raising here would fail at startup, not
  mid-flight" posture `security-stage1-2.md` already accepted for the loaders. Not a required fix.
- **Division by zero.** `_lua_arithmetic` wraps the walk in `except ZeroDivisionError: return None`,
  so `1/0` (or any expression that reduces to a zero divisor, e.g. `(1-1)/0` — actually caught one
  level up since `1-1` evaluates to `0.0` and then `x/0.0` raises `ZeroDivisionError` in Python
  float division too) collapses to the same "unresolved" outcome as every other non-numeric input,
  not an unhandled crash. Confirmed in code, not just by the docstring's claim: both `try` blocks in
  `_lua_arithmetic` are nested so that a `SyntaxError` from `ast.parse` and a `ZeroDivisionError`
  from the walk both reach a `return None`.
- **Huge literals.** A literal like `1e400` parses as `ast.Constant(value=float('inf'))` — Python's
  own float parser saturates to infinity rather than raising, so `_eval_constant_arithmetic` returns
  `float('inf')`, which then flows into `_round_value` (`round(inf, 6)` is `inf` in Python, no
  exception) and ultimately into a TOML float field. This cannot happen from a real `arg_lim_`/
  `delta_`/`gain_` literal in ED's shipped files (confirmed against the recon note: every real
  value is a small fraction or integer), so it is a theoretical-only path reachable only by a
  hand-edited or compromised Lua source — and its worst case is a bogus (`inf`) value range emitted
  to a generated reference document, not code execution or a write outside the intended output
  path. Not a required fix under this threat model; noted for completeness.

**Verdict on the evaluator: safe by construction for its actual input (ED's shipped Lua parameter
text), and the two edge cases above (unbounded recursion depth, `inf` from `1e400`-shaped literals)
are both DoS/correctness-only on an offline build tool, not exploitable for code execution or write
access.** No fix required.

### Focus 2 — do the new runtime triggers unlock writes that weren't possible before?

No. `EffectorTrigger.MISSION_START`/`MISSION_START_IN_AIR` (merged `effector_sequences.py`, fired
from `logger.py`'s `_run_crew_text_poll_loop`) only ever reach
`fire_effector_trigger(runner.effector_state, EffectorTrigger.MISSION_START, runner.last_t_sim)` —
the same `fire_effector_trigger`/`EffectorRunState.advance` path the five pre-existing triggers already
use, confirmed unchanged by this diff (`effector_engine.py`'s only change in this area is
re-exporting `EffectorTrigger` from its new home — the write path itself, `advance()`'s
`client.write_cockpit_switch(effector_def.device, effector_def.cmd, value)` call with both
`device`/`cmd`/`value` resolved from the curated, load-time-validated `EffectorDef` registry, is
untouched). `security-stage1-2.md` already established that a sequence file "has no way to name an
arbitrary device/cmd/arg/value; it can only select among the finitely many `(effector, value)` pairs
the curated `effectors.toml` already resolved to real DCS numbers" — a new trigger name widens
*which sequence runs*, never *what a sequence is allowed to write*. A trigger is an enum member
compared by identity against a sequence file's own `run-on-trigger` header (parsed and validated at
load time, same as the original five); there is no new parameter here that could be set from
external data to select a device/cmd pair outside that registry.

The two new triggers' *inputs* are entirely local: `runner.last_t_sim`/`runner.last_ownship_state`
(telemetry already inside the aircraft-layer↔body-layer trust boundary `security-stage1-2.md`
scoped — "An infected LAN machine able to spoof aircraft-layer's HTTP responses could already feed
body-layer false telemetry before this stage; this stage's worst case from that same attacker is a
wrong effector write... or a stalled sequence — not code execution, not an escape from the
registry's finite set") and `time.monotonic()` for the bounded fallback. Nothing here is new
attacker-reachable surface beyond what that prior pass already accepted; this stage adds two more
*consumers* of the same already-accepted feed, not a new trust relationship or a wider write
capability. The bounded fallback (`MISSION_START_RESOLVE_FALLBACK_S`, 30 s default, 5–120 s range
via `tuning.real`) only changes *when* the already-constrained trigger fires, never *what* it is
allowed to write.

### Focus 3 — triggers.md / switch-reference Values column (`render_triggers.py`,
`render_switch_reference.py`, rendered `triggers.md`/`switch-reference.md`)

Both renderers follow the exact pattern `security-stage1-2.md` already approved for
`render_switch_reference.py`'s predecessor: fixed, module-level `Path` constants
(`_OUTPUT_PATH`/`_RAW_DUMP_PATH`/`_CURATED_PATH`), no CLI flag to override the output or input path,
no path built from file *content*. `render_triggers.py`'s only input is the `TRIGGER_INFO` mapping
and `EffectorTrigger` enum — both Python source, not parsed file content — so there is no
content-derived string anywhere in its render path at all, a narrower surface than
`render_switch_reference.py`'s (which reads two local TOML files by fixed path and never executes
anything from them, same as before).

### Focus 4 — `petrovich_says` / LLM-visible text (carried-forward check)

`security-stage1-2.md` flagged `SwitchRow.petrovich_says` as "not yet a live surface" and asked to
re-check "the moment a future stage wires `petrovich_says`... into `CrewConsole._print`." This batch
does not touch that field or any reader of it — grepped the full diff for `petrovich_says` and
`_print`: zero hits outside files already reviewed as unchanged in that area. The two new triggers
fire fixed, hard-coded log lines (`logger.warning(...)` with a format string, never user-/file-
derived text reaching speech or brain-facing output) and otherwise only select which registry-
resolved sequence runs. Still correctly unflagged; the re-check condition has not yet been met.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `generate_effector_registry.py` `_eval_constant_arithmetic`/`_lua_arithmetic` | `ast`-based constant-arithmetic evaluator | No `eval`/`exec`; strict node whitelist (`Constant` int/float only, `UnaryOp`/`USub`, `BinOp` restricted to Add/Sub/Mult/Div — no `Pow`, no `Call`, no `Name`); `ZeroDivisionError` and `SyntaxError` both caught and collapsed to "unresolved." Recursion depth and huge-literal (`1e400`→`inf`) edges are theoretical-only on this offline, developer-invoked, non-network tool reading ED's own shipped Lua text — worst case is a tool crash or a bogus `inf` in a generated doc, never code execution or an out-of-lane write. | None. |
| `logger.py` mission-start poll block, `effector_sequences.py` `EffectorTrigger` | Two new trigger names reaching `fire_effector_trigger`/`advance()` | Same write path as the original five triggers (`security-stage1-2.md`'s finding, unchanged by this diff): only registry-resolved `(device, cmd, value)` can ever be written; a trigger only selects which already-validated sequence runs. New trigger inputs (`last_t_sim`, ownship sample, `time.monotonic()`) are local/already-trusted-LAN telemetry, not new attacker surface. | None. |
| `render_triggers.py`, `render_switch_reference.py` | New dev tools, fixed-path reads, `--write` to fixed path | Same posture `security-stage1-2.md` approved for the registry generator: hard-coded path constants, no CLI path override, no content-derived path, nothing executed from what is read. | None. |
| `body-layer/config/sequences/triggers.md`, `switch-reference.md`, `mi-24p.toml` (generated artifacts) | Generated documentation/config, committed | Plain data, no executable content, no secrets (checked: no API keys, tokens, credentials patterns in the diff). | None. |
| New tests (`test_generate_effector_registry.py`, `test_render_switch_reference_values.py`, `test_render_triggers.py`, `test_logger.py` additions) | Test-only code | No production surface; not in scope beyond confirming they don't introduce e.g. a subprocess call or network fixture. Confirmed clean by the same grep used on production files. | None. |

### Secrets/Credentials

None. Grepped the full diff for key/token/secret/password/credential patterns — zero hits beyond
variable names like `_RAW_HINT_RE` that are not secrets.

### Verdict

**APPROVED.** No findings requiring a fix. The two noted theoretical edges in the arithmetic
evaluator (unbounded recursion depth on a pathological literal, `inf` from an exponent-notation
literal) are both DoS/correctness-only on an offline, non-network, developer-invoked build tool
whose only realistic trigger is a compromised DCS installation — out of proportion to fix given this
project's single-user/LAN-only scope, and not worth a backlog item: fixing them buys no real
exposure reduction, since a compromised DCS install is already a strictly larger compromise than
anything this function could do. Nothing else in this batch needed a risk-matrix presentation, so
there is nothing to file an ID for.

### Passed to Reviewer

None — no player-facing correctness issue was observed in this pass; this batch's correctness
findings (the `default_1_position_tumb` fallback grouping, the never-called-helper dormant case,
the takeoff-trigger documentation wording) were already caught and closed by Reviewer in
`review-switch-values.md`/`review-mission-start.md` before this pass started.

### Memory and graph queries run

`python3 .claude/scripts/memory-search.py` for `ast arithmetic evaluator effector`,
`mission start trigger`, `eval exec arithmetic`: all "not indexed yet." No prior Security-role memory
on this generator's evaluator or the mission-start triggers. No new memory file written: the one
reusable shape here (an `ast`-whitelist evaluator over a vendor's shipped config text, safe because
the whitelist excludes `Pow`/`Call`/`Name` and both failure modes collapse to "unresolved" rather
than a guess) does not yet recur elsewhere in this codebase, so it is not promoted to a general
`security` memory on a single occurrence — if a second `ast`-whitelist evaluator appears in this
project, that is the point to write it down.
