---
name: feedback_lua_pairs_order_check_a_change_gate_signature
description: When an Export.lua change-gate signature is built by concatenating a pairs() loop over a DCS-returned table, probe pairs() ordering directly with an interpreter rather than assuming it — don't just flag it as a theoretical risk.
metadata:
  type: feedback
---

On BL-B67 Stage 4 (`push_payload_state` in `Export.lua`), the new change-gate signature string is
built by `for i, st in pairs(payload.Stations or {}) do ... sig_parts[...] = ...`. `pairs()`
iteration order is unspecified by the Lua language spec in general, and `LoGetPayloadInfo()`
returns a fresh table every call — so a naive read says "this could spuriously resend every poll
even when nothing changed, if two calls order the same content differently."

**Don't stop at flagging that as a risk in the review — probe it.** Ran a 5-trial check with the
interpreter actually installed in this environment (`luajit`, via Homebrew; `lua5.1` itself isn't
on this Mac, only `luac5.1`): build a dense 1..8 array table fresh each trial, iterate with
`pairs()`, record the key order. Result: `1,2,3,4,5,6,7,8` every time — matches the Lua 5.1
reference-implementation behaviour of walking a table's array part (dense sequential integer keys)
in order before the hash part, which this same `Export.lua` file already relies on in four other
`pairs()` loops elsewhere in the file (so it's an established pattern here, not a new risk this
stage introduces).

**Why this matters as a review technique, not just a one-off finding**: the alternative to probing
was writing "this could be an issue" as a flagged risk with no resolution, which either becomes a
required fix nobody can act on (there's no code change that "fixes" relying on dense-array
iteration order in Lua — it's already the only reasonable way to write this) or gets waved through
on a hunch that it's probably fine. One `luajit` one-liner settles it either way. Cost: under a
minute. Use this whenever a reviewed change's correctness depends on iteration order over a table
that isn't provably array-only by construction (e.g. built from sparse/externally-sourced indices,
unlike a dense DCS `Stations[1..8]` array).

See also [[feedback_emitter_visibility_fix_pass_confirmed_by_mutation]] and the project's standing
"verify by mutation, per entry, not per set" rule (`reviewer.md`) — this is the same instinct
(don't trust a read, run it) applied to a language-semantics question instead of a test mutation.
