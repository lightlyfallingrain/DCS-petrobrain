# Review round 2 — `fix/los-hook-statics`

**Sha actually reviewed: `928a2c6`.** The brief named `5ec13eb`. The worktree could not check the
branch out (it is held by the main checkout), so the documented fallback was taken:
`git merge --ff-only fix/los-hook-statics` onto `worktree-agent-a1e9e6c9ae3a95a17`, landing on
`928a2c6`. The orchestrator has since reset the branch to `5ec13eb`, having moved that stray commit
to `main` as `5c954c9`.

**The delta is config-only and outside the change under review**, verified here rather than taken on
report: `git diff 5ec13eb 928a2c6 --stat` is exactly `.claude/scripts/agent-sha-gate.sh` and
`.obsidian/workspace.json`, and `git diff 5ec13eb 928a2c6 --name-only -- aircraft-layer plans
body-layer` is empty. So every judgement below is a judgement about `5ec13eb`'s tree. The stray
commit is not treated as scope creep in this feature.

**Live behaviour is not verified by this review and cannot be.** Nothing below asserts the Hook works
in the sim; this subproject has no automated test that executes a Hook script. The acceptance step is
a sortie by the pilot on branch **`fix/los-hook-statics`**.

---

### Review Summary

All three required fixes land, and the optional was taken in a better form than it was asked for.
There are no required fixes in this round.

**Fix 1 — `unitEnumFailures`.** Present, incremented in the `else` of the per-side
`pcall(coalition.getGroups, coa)`, emitted as `unit_enum_failures=` on the same `env.info` line with
the same `tostring()` shape as `static_enum_failures`.

**The granularity choice is correct — and for a stronger reason than the comment gives.** The brief
asked whether a silent `grp:getUnits()` failure can also distort the cap measurement. Reading the
three uncounted sites against the control flow:

- **`unit:getID()` cannot lose a candidate at all.** It fails *open*:
  `if (not okI) or playerId == nil or uid ~= playerId then considerCandidate(unit, false)`. A failed
  `getID()` over-admits (the ownship hole this round's optional documents), it never drops.
- **`grp:getUnits()` and `unit:isExist()` can only lose objects that are already not live, in the
  normal case.** The chunk runs synchronously inside one `net.dostring_in` call with no yield
  anywhere between `coalition.getGroups(coa)` returning and the per-group/per-unit calls, so the
  simulation cannot advance in that window and no group or unit can die inside the loop. A group that
  errors on `getUnits()` was therefore already invalid when `getGroups` handed it over — and a dead
  group contributes no *live* units whether it errors or returns an empty table, so counting it would
  recover nothing. The loss that would matter is `getUnits()` erroring on a group holding live units,
  which needs an engine fault, not a mission condition.
- **A systematic unit-side fault is already visible on the same log line.** If `getUnits()` failed
  across the board, `objects_in_bubble` would collapse to the statics population, i.e.
  `statics_in_bubble == objects_in_bubble` and `statics_in_wedge == objects_in_wedge` — a free
  cross-check from fields that are already printed. The undetectable residual is a *group-selective*
  `getUnits` fault on groups with live units, which has no plausible mechanism.
- **`coalition.getGroups` is genuinely different, which is why counting only it is right.** It has a
  real mechanism (an API erroring or absent for a side — literally what motivated
  `staticEnumFailures` for `getStaticObjects`), it loses a whole side, and it is *not* inferable from
  the other fields, because a side with no units is a legitimate mission configuration.

So the answer to the brief's question is: yes in the abstract, no in any way this sortie can be
misled by. Many small groups cannot silently bleed live candidates without an engine bug, and the
one failure that can is counted. Round 1 explicitly licensed folding *or* skipping the per-group and
per-unit sites; skipping is the option taken, and it is the better one.

**Fix 2 — the false justification.** Corrected at the claim rather than appended, and the replacement
reason is true of the code: `pcall(net.dostring_in, state, code)` at `:567` and `pcall(pollAndSend)`
at `:762`, with `onSimulationFrame` at `:749`. Two independent layers, so a chunk error produced a
log line and never took the mission down. The kept-but-re-reasoned `pcall`s now carry the clause that
was the missing half — degrade to fewer candidates *and say so in a counter*.

**Fix 3 — the bubble-radius splice.** Verified single-definition and verified boundary-preserving:

- `PLAYER_BUBBLE_RADIUS_M` now has a real code reader (`:326`,
  `string.format("%.17g", PLAYER_BUBBLE_RADIUS_M)` prepended as `local BUBBLE_RADIUS_M = …`), and the
  only remaining `10000` occurrences in the file are the declaration at `:249` and three comments.
  No re-typed literal survives. Same for the cap: `128` appears once, at `:256`.
- **The boundary did not shift.** The test is `if rangeM > BUBBLE_RADIUS_M then return end` — `>`, as
  before, so inclusive at the boundary. Run under a Lua interpreter rather than argued: with the
  spliced text `10000`, a range of exactly `10000.0` is admitted, `9999.9999` admitted,
  `10000.0001` rejected, and `10000 == 10000.0` is true. The `%.17g` output is numerically identical
  to the constant.
- The `%.17g`-vs-`%d` reasoning is sound and the right conversion for a float constant.

**Optional — `ownship_unidentified`, and the departure from the brief.** The trade is good; I would
have made the same call. The emitted condition is `playerId == nil and playerName == nil`, which is
*exactly* the hole: the unit loop admits when `playerId == nil`, and `considerCandidate`'s
`playerName ~= nil and name == playerName` test is a no-op when `playerName == nil`. It also covers
the `okPid`-true-but-`pid`-nil case. A once-only log really would need cross-poll state, and the
chunk is rebuilt and re-executed every poll, so it would mean a fourth deliberate mission-state
global in the `GETGLOBAL` allowlist for a near-impossible condition. A field that is `0` on every
line costs ~22 bytes per second of `dcs.log` and is greppable for the one flight where it is not `0`.
Softening the claim in both the Lua comment and the implementation log is the part that mattered, and
it was done.

**`HOUR_DEFAULT`/`FOV_DEFAULT_DEG` were not tidied.** Confirmed: `:272`/`:273` and the chunk's
`or 0`/`or 45` at `:329`/`:330` are unchanged, and the live `_safeClampInt` readers are still at
`:618`/`:619`. See the first optional below for where the *reason* is, and is not, recorded.

**The sortie criterion is correctly interpreted.** "A non-zero `unit_enum_failures` invalidates that
poll's `cap_hit` reading rather than merely noting a hiccup" follows from the code: a per-side
`getGroups` failure removes that side's entire unit population from `candidates`, so `#candidates`
undercounts and `cap_hit = (sightlinesComputed < #candidates)` can read `0` where it would have read
`1`. The claim is directional and the log does not claim the converse. Combined with the
`statics_in_bubble == objects_in_bubble` cross-check above, one sortie is decisive for the question
the branch exists to answer: does 128 bind.

---

### Required Fixes

None.

---

### Optional Refinements

- **Record the `HOUR_DEFAULT`/`FOV_DEFAULT_DEG` ruling in the Lua, not only in the plan** (optional,
  but the one I would actually do before merge). The reason they stay duplicated is recorded well in
  `implementation.md`, which is not where the next reader meets them. The declaration comment at
  `:265`–`:273` instead says the pair "mirrors `PB_LOOK_HOUR or <default>` … inside LOS_CODE below" —
  which now reads as an *invitation* to splice, because this round put two worked splices three lines
  below it. One sentence at the declaration ("equal by coincidence, not construction: this pair is
  the bad-inbound-value clamp fallback, the chunk's `or`-defaults are no-command-yet; do not splice
  them together") closes the loop this branch opened.
- **Nothing automated defends either splice** (optional; a reasonable `AC-B<n>`). The two constants
  having exactly one definition each, and the chunk not re-typing a literal, are currently held by a
  reviewer noticing and by a hand-run `GETGLOBAL` sweep. `tests/test_line_of_sight_hook_lua.py`
  already establishes the idiom for exactly this class of thing — five text assertions over the Lua
  source, including one guarding the sibling `SET_LOOK_TEMPLATE` splice — so two more assertions (the
  prefix lines exist; the chunk body contains no bare `10000`/`128`) would cost ~15 lines and make the
  de-duplication a contract instead of a convention. **I considered making this required and did
  not**: a re-typed literal is a maintenance regression, not a runtime defect, and round 1 shipped the
  cap splice the same way, so requiring it now would be a round trip for a durability improvement
  that does not affect the flight.
- **The round-2 log cites pre-fix line numbers.** `implementation.md` says the two `pcall` layers are
  at `:513` and `:709`; in the committed file they are `:567` and `:762` (the fix added ~54 lines, and
  the offsets match). The claim is true, the addresses are not, and the next reader checking the
  citation will find `pcall(net.dostring_in, …)` nowhere near `:513`. Cheap to correct; the same
  applies to a few round-1 citations the log inherits.
- **The comment's stated reason for the counter's granularity is weaker than the real one.** "It is
  the one whose failure loses a whole side, and the one granularity comparable to
  `staticEnumFailures`" is true but not load-bearing — comparability is aesthetic. The load-bearing
  facts are that `getID()` fails *open* so it cannot lose a candidate, that the chunk cannot yield so
  the other two can only drop already-dead objects, and that a systematic unit-side fault shows up as
  `statics_in_bubble == objects_in_bubble`. Putting one of those in the comment would stop a future
  reader "fixing" the asymmetry by adding three counters nobody can interpret. (Flagged because this
  is the "X, so Y" pattern: Y is right, X is not what makes it right.)

---

### Verdict

**APPROVED.** The three required fixes from round 1 are all genuinely closed, the optional was taken
in a defensible stronger-than-asked form, and the one judgement call the brief singled out — counting
only the per-side `getGroups` failure — is correct for reasons the code supports.

### Ready for DoD

**Yes.** No required fixes outstanding; nothing found needs a code change, a re-run, or a re-flight.
DoD's own gate should note two things rather than discover them:

1. **The acceptance step is a live sortie by the pilot on branch `fix/los-hook-statics`** — a Windows
   box with DCS running, since no agent can execute a Hook script. The flight is scored against
   `implementation.md`'s "What the sortie must answer", whose criteria this review confirms follow
   from the code.
2. **Live behaviour remains entirely unverified**, as the file header, the schema docstring, the
   `CLAUDE.md` bullet and the implementation log all state. No claim on this branch overreaches into
   "it works in the sim" — checked, including the new `CLAUDE.md` bullet, which closes with
   "Unverified against a live DCS session as of the statics change".

### Review Confidence

Full read of the round-2 diff (`f9aaeea..928a2c6`) line by line, both enumeration loops and the
shared filter in the committed file, the `env.info` line, the cap-bit line, the schema docstring and
the `CLAUDE.md` bullet. Verified mechanically here rather than taken on report: the `5ec13eb..928a2c6`
delta is config-only; `PLAYER_BUBBLE_RADIUS_M`/`BUBBLE_RADIUS_M`/`10000`/`128`/`MAX_SIGHTLINES`
occurrence inventories; the boundary's inclusivity **executed** under a Lua interpreter with the
spliced text; the two `pcall` layers' real line numbers; the `HOUR_DEFAULT` pair still duplicated with
live readers; and that nothing in `aircraft-layer/src`, `aircraft-layer/tests` or `body-layer/src`
parses the `env.info` scan line, so the two new fields cannot break a consumer. **Not re-run** (per
the orchestrator's stated verification): `luac5.1 -p`, the `GETGLOBAL` sweeps including the
without-prefix sensitivity check, the `%.17g` round-trip probes, and `pytest tests -q` (252 passed).
**Not verifiable from here at all:** every live DCS behaviour — `getStaticObjects` availability, the
statics enumeration returning objects, the heading convention, whether `grp:getUnits()` ever errors
on a live group, and whether the cap binds.
