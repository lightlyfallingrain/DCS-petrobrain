# Rule files (`config/rules/*.lua`)

Every spoken command is a Lua rule: a fixed-wording pattern with typed slots, plus a handler
that calls exposed actions and writes its own readback. `plans/speech-rules/plan.md` has the
full design; this page is the one-page reference for writing/editing a rule.

## Reloading

Rule files reload at every **mission (re)start** — restart the DCS mission to pick up an edit,
not body-layer itself. Check an edit without flying: `--print-rules` (standalone) or
`--print-rules --audio-adapter-url http://127.0.0.1:7795` (also pushes and shows what the
adapter accepted/rejected).

## A rule

```lua
when.speech("turn_heading_relative", "turn <direction:left|right> <degrees:angle>",
  function(s)
    local r = flight.increment_heading(s.direction == "left" and -s.degrees or s.degrees)
    if not r.ok then
      say(unable(r.reason))
      return
    end
    say(s.degrees .. " " .. s.direction .. ".")
  end)
```

`when.speech(id, pattern, handler)`:

- `id` — the command token. Shown in `--speech-log`, the command-map, and (once ported) BR-2's
  brain allowlist.
- `pattern` — the grammar below. One pattern per rule; two rules that could both match the same
  wording are both disabled at load/push time (see "Failures" below).
- `handler(s)` — called with one table `s`, keyed by each slot's own name. Calls `say`/`unable`
  to speak, and whatever actions it needs.

## Pattern grammar

| element | meaning |
|---|---|
| a bare word | a literal the pilot must say |
| `[ ... ]` | an optional group — literals and/or slots |
| `<name:type>` | a typed slot (table below) |
| `<name:w1\|w2>` | a word-set slot — the value is the exact word heard (a string) |

## Slot types

| type | spoken | value | notes |
|---|---|---|---|
| `angle` | 1–3 digits, digit-by-digit or whole ("two zero", "20") | int 1–359 | no anchor word of its own |
| `heading` | the word "heading" + exactly 3 digits | int 0–359 (360 normalises to 0) | world compass degrees; no ×5 checksum |
| `oclock` | 1–12 + "o'clock" | int hour | |

`bearing` is **not built yet** — the bearing/heading rename is paused (see
`body-layer/ROADMAP/BL-17.md`); do not write a rule that assumes it exists.

A slot that fails to parse means the rule did not match on this utterance — not an error, just
a non-match (the same "say again" fallthrough any unmatched command gets).

## The Lua API every rule file sees

- `say(text)` — speaks one line. A handler may call it more than once; every call's text is
  spoken in order.
- `unable(reason)` — returns the fixed wording for a closed reason key (the same catalogue
  every other command in this codebase uses), e.g. `unable("NOT_READY")` → `"Unable, not
  ready."`. An unrecognised key degrades to a plain `"Unable."`, never an error.
- `digits(n)` — spells `n` digit by digit ("3 1 5" for 315), the aviation readback convention.

Nothing else from Lua's standard library is reachable — no `io`, `os`, `require`, `debug`,
`load`, `string.dump`, `collectgarbage`. `string`/`table`/`math` are available with their
ordinary (non-filesystem) members.

## Actions

Actions are namespaced Lua tables — what a rule may *do*, as opposed to what it may *say*.
Every argument is validated in Python before the underlying code runs; a bad call answers
`{ok = false, reason = nil}` rather than raising.

| call | params | effect |
|---|---|---|
| `flight.increment_heading(delta_deg)` | int, −359..359 | turns the AI-overlay heading hold by `delta_deg` relative to its current held value |

Every action returns a table: `r.ok` (bool), `r.reason` (a reason key for `unable`, or `nil` on
success).

## Failures

Any rule-file failure — a pattern clash with another rule or with an existing spoken command, a
Lua syntax error, a bad `when.speech` call, an unknown slot type, a Lua error while a handler
runs — is written to the standard error log (with the file and, where known, the rule id) and
Petrovich says exactly **"Action file error."** once per load that has one. There is no
per-cause spoken description; the log is where the detail lives.

- A Lua syntax error, or an error in a file's own top-level code, discards **that file's**
  rules only — other files are unaffected.
- A duplicate rule id — within one file or across two — disables **every** rule carrying it.
- Two rules that could both match the same wording, or a rule that collides with an existing
  spoken command, are **both** disabled.
