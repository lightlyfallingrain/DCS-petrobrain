---
name: extract-lua-function-comment-false-positive
description: aircraft-layer's _extract_lua_function test helper (test_sight_servo_lua.py, duplicated in test_exponent_float_fix.py) counts bare function/if/end words anywhere in the text, including inside -- line comments, so it has always been over-extracting; only check it if a new function's placement shifts the coincidental rebalancing point.
type: feedback
---

`_extract_lua_function` (both `aircraft-layer/tests/test_sight_servo_lua.py` and
`test_exponent_float_fix.py` carry their own copy, deliberately not shared) slices
`local function NAME(...) ... end` out of `Export.lua` by regex-counting the bare words
`function`/`if`/`end` from the declaration onward until depth returns to 0. **It does not skip
`--` line comments**, so an English sentence containing the word "end" (e.g. a comment reading
"a mission end/restart is not an observed OBSERV falling edge") is counted exactly like a real
Lua `end` token.

**This was already wrong before my change, silently.** Extracting `run_sight_servo` from the
pre-change file returned 379 lines, not its real ~230 -- the depth counter overshot into
`push_sight_servo_state`/`push_watched_args_state`'s bodies and happened to hit a *coincidental*
rebalancing point (another stray comment-`end` landing at the right spot) that made the chunk
syntactically valid Lua again, so every existing test kept passing against an over-long but still
compilable extraction. Found 2026-10-30 only because adding a new function
(`sight_servo_tick`) between `run_sight_servo`'s real end and the next comment shifted that
coincidental rebalancing point past EOF, and the generated test script failed to parse at all
("'end' expected ... near '<eof>'") -- a loud failure, not a silent one, but it took isolating
which specific extraction was wrong (compare `len(extract("run_sight_servo").splitlines())`
before/after, and against `git show HEAD:...` for a pre-change baseline) to see that the *real*
bug was pre-existing, not introduced by my edit.

**How to apply:** if you add/move/rename a function in `Export.lua` near one of these
`_extract_lua_function` call sites and a harness that used to work starts failing with an "'end'
expected ... near '<eof>'" Lua parse error (not a Python assertion failure), suspect this
mechanism first -- check by extracting the function directly with a short Python snippet and
comparing line count/first-and-last-line against the function's real source span. The fix (made
in `test_sight_servo_lua.py`'s own copy only, not `test_exponent_float_fix.py`'s) is a regex that
also matches `--[^\n]*` and skips those matches without touching depth:
`token_re = re.compile(r"--[^\n]*|\b(function|if|end)\b")`, then `if keyword is None: continue`
before the depth logic. Lua's `--[[ ]]` block comments are not handled by this fix -- check
whether one exists between the function's start and its real end before relying on it; `Export.lua`
currently has exactly one, in the file header, well before any extracted function.

See also [[lua51-60-upvalue-ceiling]], the change that surfaced this.
