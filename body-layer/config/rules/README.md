# Rule files (`config/rules/*.lua`)

Every spoken command is a Lua rule: a fixed-wording pattern with typed slots, plus a handler
that calls exposed actions and writes its own readback. `plans/speech-rules/plan.md` has the
full design; this page is the one-page reference for writing/editing a rule.

## Reloading

Rule files reload at every **mission (re)start** — restart the DCS mission to pick up an edit,
not body-layer itself. Check an edit without flying: `--print-rules` (standalone) or
`--print-rules --audio-adapter-url http://127.0.0.1:7795` (also pushes and shows what the
adapter accepted/rejected).

## Checking your rules

```sh
cd body-layer && .venv/bin/python tools/check_rules.py
```

Reports every problem as `file: rule 'id': message`, with the Lua line number where there is
one, and exits 1 if it found any:

- Lua syntax and load errors, and bad `when.speech` calls (duplicate id, unknown category);
- wording: an unparsable pattern, or one that clashes with another rule, an existing command
  or ordinary speech — the same check audio-adapter runs at load, offline (needs
  `audio-adapter/.venv`; without it this part is skipped with a warning);
- a **dry run** of every handler with sample slot values — each directive alternative, each
  slot form — while flying through the AI overlay, while hovering, while flying on the raw axes,
  and with every action failing. It
  catches a misspelt action, a wrong argument type or count, `nil` arithmetic, `digits()` of
  a word, and an `effector.write` naming a switch or value `effectors.toml` does not have.
  A branch none of the samples reach is not checked.

The same check runs as a **git pre-commit hook** whenever a commit touches
`config/rules/*.lua`, on the staged versions, and **blocks the commit** if it finds a problem
(`git commit --no-verify` overrides). Install the hooks once per clone with
`.claude/scripts/install-git-hooks.sh`.

## A rule

```lua
when.speech("turn_heading_relative", "turn <direction:left|right> [<degrees:angle>]",
  "flight_control_heading",
  function(s)
    flight.increment_heading(s.direction == "left" and -s.degrees or s.degrees)
    say(s.degrees .. " " .. s.direction .. ".")
  end)
```

`when.speech(id, pattern, category, handler)`:

- `id` — the command token. Shown in `--speech-log`, the command-map, and (once ported) BR-2's
  brain allowlist.
- `pattern` — the grammar below. One pattern per rule; two rules that could both match the same
  wording are both disabled at load/push time (see "Failures" below).
- `category` — **required**, one of the names in "Categories" below. Decides, before this
  handler ever runs, whether the rule may execute at all (e.g. "unable, not flying" when
  Petrovich has no controls). A missing or unrecognised category is a bad `when.speech` call —
  see "Failures" below.
- `handler(s)` — called with one table `s`, keyed by each slot's own name. Calls `say`/`unable`
  to speak, and whatever actions it needs.

## Categories

Every rule belongs to one category, and that category's gate runs **before** the rule's handler
— a rule whose gate says no never has its handler called at all, the same way the on-ground look
gate already works for scan/watch commands.

| category | gate |
|---|---|
| `always` | always runs — queries, describe, recall |
| `flight_handover` | always runs — the two handover commands ("you/i have controls"). What each means depends on state (flying through the AI overlay, already flying on the axes, nobody flying), so the action itself reads that state rather than a category precondition |
| `flight_control` | runs once Petrovich has the aircraft's controls, with no further precondition — the absolute-set flight commands and HVRT (whose own hover-mode check stays inside the action) |
| `flight_control_heading` | `flight_control`'s own has-controls check, **plus** holds (then retries) during the takeover-settle window until a held heading is known |
| `flight_control_speed` | same shape, for a held speed |
| `flight_control_altitude` | same shape, for a held altitude |
| `flight_control_any` | same shape, but passes once **any one** of held heading/altitude/speed is known (`level_flight`'s own "partial knowledge still freezes what is known" rule) |

Every `flight_control*` category answers "unable, not flying" immediately if Petrovich has no
controls at all; the four finer ones additionally hold briefly (never refuse) during the
takeover-settle window (the moment right after "Request Aircraft Control") until their own
needed value arrives. **Split into per-parameter categories, not one shared `flight_control`
gate re-deriving a single proxy** (`[[BL-17]]` Stage 4) — a single "settling" boolean checking
only the held heading was correct for exactly one rule (`turn_heading_relative`) and wrong for
most of the others, each of which needs a *different* held value before it may run.

Declaring a category does not add a second check inside the handler — a rule's own action may
still validate its *arguments* (D5), but the category already owns the seat/flight-state
precondition, so an action extracted from a ported handler should not re-check it. A genuinely
*finer*, rule-specific precondition that is not a property of the whole category (HVRT's own
"is the AI actually in hover" check) stays inside that rule's own action instead.

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
| `angle` | 1–3 digits, digit-by-digit, or a composed number word ("two zero", "20", "thirty") | int 1–359 | no anchor word of its own |
| `heading` | the word "heading" + exactly 3 digits | int 0–359 (360 normalises to 0) | world compass degrees; no ×5 checksum; no compass-word form |
| `oclock` | 1–12 + "o'clock" | int hour | |
| `quantity` | a digit run (1–4 digits) or a composed number word/phrase ("three two zero", "three hundred twenty") | int | no range check of its own — the using rule applies whatever range makes sense; paired forms ("three fifteen") do not parse as one number |
| `speed_target` | `quantity`'s own grammar, or the literal word "max" | `{kind="number", value=N}` or `{kind="max"}` (a Lua table) | a union slot — the rule's own handler branches on `s.<name>.kind` |

`bearing` is **not built yet** — the bearing/heading rename is paused (see
`body-layer/ROADMAP/BL-17.md`); do not write a rule that assumes it exists.

A slot that fails to parse means the rule did not match on this utterance — not an error, just
a non-match (the same "say again" fallthrough any unmatched command gets).

## The Lua API every rule file sees

- `say(text)` — speaks one line. A handler may call it more than once; every call's text is
  spoken in order. **For a `flight_control*`-category rule, this does not mean "now."** BL-16
  (`plans/flight-desired-state/plan.md`, section 3a) waits for `Export.lua`'s own accept/refuse
  before any of these lines are actually spoken — a rule still just calls `say(...)` with the
  text it wants read back, and the console (not the rule) decides when that is heard: on accept
  verbatim, swapped for `unable(...)` on a refusal, or "Unable, not ready." on a timeout. A rule
  author never has to know this; it only matters if you are reading a dispatch's returned lines
  and expecting them to already have been spoken.
- `unable(reason)` — returns the fixed wording for a closed reason key (the same catalogue
  every other command in this codebase uses), e.g. `unable("NOT_READY")` → `"Unable, not
  ready."`. An unrecognised key degrades to a plain `"Unable."`, never an error.
- `digits(n)` — spells `n` digit by digit ("3 1 5" for 315), the aviation readback convention.

Nothing else from Lua's standard library is reachable — no `io`, `os`, `require`, `debug`,
`load`, `string.dump`, `collectgarbage`. `string`/`table`/`math` are available with their
ordinary (non-filesystem) members.

## Actions

Actions are namespaced Lua tables — what a rule may *do*, as opposed to what it may *say*.
Every argument is validated in Python before the underlying code runs. A bad call (wrong
argument count, type or range) is a bug in the rule: it is logged and Petrovich says "Action
file error."

**Every `flight.*` action in the table below except `turn_continuous`/`take_controls`/
`release_controls` dispatches by *mode*** (BL-16 mode 1, `plans/flight-control/plan.md`,
"Revised 2026-11-18"): Petrovich flies through ED's own AI-pilot wheel (parked, mode 2) or on
the raw cyclic/collective/pedal axes (unparked, mode 1). The wording and readback below is the
same in either mode; which underlying body actually runs is decided once, in code
(`CrewConsole.flight_mode()`), never by the rule. `turn_continuous` has no mode-2 counterpart at
all (there is no "continuous turn" concept on the AI-pilot wheel) and answers `unable("AI_
OVERLAY")` there; the HVRT actions have no mode-1 counterpart (mode 1 is forward flight only)
and answer `unable("NOT_READY")` there.

**A rule never checks whether an action worked.** When one fails, the handler stops there and
Petrovich says `unable(reason)`, e.g. "Unable, not flying." Anything the handler already said
before the failing call is still spoken, and nothing it did is undone. The failure is logged.
Rules cannot catch the failure themselves.

| call | params | effect |
|---|---|---|
| `flight.increment_heading(delta_deg)` | int, −359..359 | turns the AI-overlay heading hold by `delta_deg` relative to its current held value |
| `flight.set_heading(deg)` | int, 0..359 | sets the absolute heading hold |
| `flight.level_flight()` | — | freezes heading, altitude and speed at their current held values |
| `flight.set_speed(value)` | int, 0..9999 | sets the speed hold to the nearest wheel step; `r.is_max`/`r.speed_kmh` name what was actually set |
| `flight.set_speed_max()` | — | sets the speed hold to max |
| `flight.step_speed(sign)` | int, −1..1 | one step up (`1`) or down (`-1`) from the held speed |
| `flight.set_altitude(m, reference_code)` | ints, `m` 0..9999, `reference_code` 0 (none)/1 (radar)/2 (barometric) | sets the altitude hold; `r.altitude_m`/`r.barometric` name the achieved value and reference |
| `flight.step_altitude(delta_m)` | int, −9999..9999 (already signed — positive climbs, negative descends) | one step from the held altitude |
| `flight.hold_altitude()` | — | freezes the altitude hold at its current held value |
| `flight.level_off()` | — | stops a turn and holds the current heading |
| `flight.hvrt_translate_left/right/forward/back()` | — | cycles the AI wheel into HVRT (from hover) and presses the named direction |
| `flight.hvrt_hold()` | — | clears an outstanding HVRT translate press |
| `flight.hvrt_step_up/down()` | — | the 2 m HVRT altitude tap |
| `flight.turn_continuous(sign)` | int, −1..1 | "turn left/right" with no degrees heard — mode 1: starts a continuous turn at the fixed bank angle, in the named direction; mode 2: `unable("AI_OVERLAY")` |
| `flight.take_controls(says)` | string | "you have controls" — refuses `unable("ON_GROUND"\|"ATTACK_RUN_ENGAGED")`; while flying through the AI overlay, a silent no-op (`r.acted == false`); otherwise takes the raw axes at any airspeed (BL-16 lift-vector law, Stage LV-1: no `"TOO_SLOW"` any more), and `says` is spoken once the aircraft layer confirms the take, not when this call returns |
| `flight.release_controls()` | — | "i have controls" — while flying through the AI overlay, `unable("AI_OVERLAY")` (U9: not remembered — the player gets the stick back by unparking, then saying it again); while flying on the axes, hands back at once (`r.acted == true`); otherwise a silent no-op (`r.acted == false`, the player already has the controls) |
| `effector.write(name, value, says)` | `name`/`value`: strings, checked against the loaded aircraft's own effector registry; `says` optional, free-text (silently capped at the same length `say()` enforces) | queues a cockpit switch write; **says nothing when it returns** — returning only means the write was accepted, not that it happened yet (it may take several polls). If `says` was given, that text is spoken once the write actually lands, through the same path a sequence file's own `petrovich-says` cell uses. No shipped rule calls this yet — it exists so a later rule group can write effectors without a second mechanism. A second `effector.write` naming the same effector while the first is still pending is a no-op if it names the *same* value (the pilot repeating themselves), or **replaces** the pending request if it names a *different* one — latest wins, nothing lost. |

An action that works returns a table with whatever fields its row above names (e.g.
`r.altitude_m`) for the handler's readback. `effector.write`'s own failure reason is always
`"UNKNOWN_EFFECTOR"`: an unknown `name`, or a `value` that effector does not know.

## Failures

Any rule-file failure — a pattern clash with another rule or with an existing spoken command, a
Lua syntax error, a bad `when.speech` call (including a missing or unrecognised `category`), an
unknown slot type, a Lua error while a handler runs — is written to the standard error log (with
the file and, where known, the rule id) and
Petrovich says exactly **"Action file error."** once per load that has one. There is no
per-cause spoken description; the log is where the detail lives.

- A Lua syntax error, or an error in a file's own top-level code, discards **that file's**
  rules only — other files are unaffected.
- A duplicate rule id — within one file or across two — disables **every** rule carrying it.
- Two rules that could both match the same wording, or a rule that collides with an existing
  spoken command, are **both** disabled.
