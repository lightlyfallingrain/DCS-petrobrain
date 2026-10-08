### Implementation Summary

`BL-11` Stage 4. The DCS line-of-sight Hook walked `coalition.getGroups()` ->
`grp:getUnits()` only, so **static objects were absent from the enumeration entirely** and could
never receive a LOS verdict — **278 of 404 objects, 68.8 %**, in the measured sortie's own mission
(`aircraft-layer/research/2026-10-06-unit-id-join-results.md`; the same fact as the 323-of-425
objects that got no verdict on 2026-10-05). In that mission the statics were 112 infantry, 31 T-55,
34 T-72B/B3 and eight `ZSU-23-4 Shilka` — killable, and in the Shilka's case shooting. "Static" in
DCS means placed without AI or waypoints, not decorative.

`coalition.getStaticObjects(coa)` is now walked for the same three coalition sides, through the
**same filter implementation** as units, into the **same** `candidates` list and the **same** wire
entry shape. The join key stays `getName()` — `Unit:getObjectID()` matches the `LoGetWorldObjects`
key but does not exist on `StaticObject` (`<NONE>`, 94/94), so no integer key spans both
populations. Nothing on the wire branches on unit-vs-static, so body-layer needs no change.

**Live behaviour is unverified and unverifiable from here** — it needs Windows and a running DCS.
Nothing below is a claim that it works in the sim; only that it parses, has no hoisting bug, and
passes every mechanical check this environment can run.

### Files Changed

- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`
  - **Statics enumeration.** A second pass over the same three sides calling
    `coalition.getStaticObjects`, `pcall`'d per side, feeding `considerCandidate(st, true)`.
  - **One shared filter, not a copy.** The bubble/wedge/name/ownship logic was extracted from the
    unit loop into `considerCandidate(obj, isStatic)`, which both populations call. A copy-pasted
    second filter is the failure this avoids: "same filters as units" has to be structurally true,
    not re-typed. It is declared *below* every local it closes over.
  - **`isExist` is advisory for statics.** If the call itself fails on a `StaticObject` the object
    is still considered — dropping a live Shilka is worse than carrying a dead one, whose verdict
    is simply never joined on the body-layer side. For units the existing `isExist` gate is
    unchanged (and now `pcall`'d).
  - **Ownship exclusion hardened.** `player:getID()` was called unprotected inside the loop and
    was the only exclusion test; it is now resolved once under `pcall`, with `player:getName()` as
    a backstop so a failed `getID()` **alone** no longer lets ownship through as a candidate. It is
    a backstop, not a guarantee — if *both* resolutions fail, the unit loop's id test admits and the
    name test is a no-op (2026-10-06 review; the claim here originally said "cannot", which
    overstates it). That case is now reported as `ownship_unidentified=1` on the scan line.
  - **Cap literal de-duplicated.** `:322`'s hardcoded `128` now reads `MAX_SIGHTLINES`, spliced
    into the bridged chunk from `MAX_SIGHTLINES_PER_CALL` at module load time
    (`"local MAX_SIGHTLINES = " .. string.format("%d", …)`). The chunk lives in a string literal
    and cannot see this file's `local`s, which is why a splice rather than a reference.
  - **Cap instrumentation** (below).
  - Header and the `LOS_CODE` doc comment rewritten to state the statics enumeration, why the join
    key must stay `getName()`, that `units_in_*` now count objects, and that the nearest-first sort
    is load-bearing now that truncation is reachable.
- `aircraft-layer/src/schema/line_of_sight.py` — **docstring only**, no behaviour. Records that the
  population is units + statics, that a static is indistinguishable on this wire, that
  `units_in_bubble`/`units_in_wedge` are now object counts keeping their names for compatibility,
  and that `sightlines_computed < units_in_wedge` is the thing to watch.
- `aircraft-layer/CLAUDE.md` — added a `dcs-export/petrobrain-line-of-sight-hook.lua` bullet to the
  Structure list. It did **not** state the unit-only enumeration: it did not mention this Hook at
  all (nor does `WORKFLOW.md`). An absent description is worse than a stale one here, so one
  accurate bullet was added rather than leaving a shipped Hook script undocumented.

### The cap instrumentation, and what the sortie must answer

`MAX_SIGHTLINES_PER_CALL = 128` is **unchanged** — retuning it is a decision that needs the
measurement first. Pre-statics: median 43, max 71 units per result, `bridge_call_ms` ~1 ms. With
~278 more candidates in a 404-object mission the cap **may bind for the first time**, and that is
currently unmeasured. Three additions make one sortie answer it:

1. **Hook-side, `dcs.log`.** The result's leading counters are pulled out with a `string.match`
   (a pattern, not a splice) and logged as
   `objects_in_bubble= objects_in_wedge= sightlines_computed= cap=128 cap_hit=0|1`, replacing a
   truncated `result_head=`. On a pattern miss the counters read `?` and `cap_hit` reads `?` rather
   than a confident `0`.
2. **A dedicated `LOS cap bit:` line** naming how many candidates were dropped, so the question is
   one grep rather than an inference.
3. **`env.info` from inside the scripting state**, carrying what cannot cross the `dostring_in`
   boundary (one scalar return, fixed wire format): `statics_in_bubble`, `statics_in_wedge`,
   `candidates`, **`static_enum_failures`** and (added by the review fix) **`unit_enum_failures`**
   plus `ownship_unidentified`. The two failure counters are the point of the line — without the
   first, a `coalition.getStaticObjects` failing on every side would look *exactly* like the old
   unit-only behaviour; without the second, a `coalition.getGroups` failure is invisible in exactly
   the direction that makes `cap_hit=0` read as good news. Both are per side, so both top out at 3.

**What the sortie must answer:**

- Does `cap_hit=1` ever appear? If so, how often, and at what `bridge_call_ms`?
- `statics_in_bubble` > 0 on a mission known to contain statics — i.e. the enumeration is actually
  running. `static_enum_failures=0` **and `unit_enum_failures=0`** — a non-zero second counter
  invalidates the `cap_hit` reading for that poll rather than merely noting a hiccup, because it
  means the candidate population was undercounted.
- Does `bridge_call_ms` stay near ~1 ms with the tripled candidate population? The filter cost is
  per *candidate*; only the capped survivors pay the two engine calls.
- Do statics appear in body-layer's own join (contacts that previously had no LOS verdict now
  getting one)?

### Tests Added

None. The Python change is a docstring; the Lua change has no automated behavioural test by this
subproject's own standing policy (`aircraft-layer/CLAUDE.md` Testing: Hook scripts need a real DCS
process). The existing `tests/test_line_of_sight_hook_lua.py` static-text guards all still pass —
they target `SET_LOOK_TEMPLATE`, which was not touched; the new load-time splice is a separate
construct and deliberately does not live in that template.

Test-impact check: `grep -rln 'line_of_sight|LineOfSight|units_in_wedge|sightlines_computed'` over
`aircraft-layer/tests` found four files (`..._schema`, `..._api`, `..._cache`, `..._receiver`) plus
`test_line_of_sight_hook_lua.py`. None assert on the docstring prose or on the Lua text that
changed, so none needed editing. Full suite run unfiltered, not `-k`.

### Checks

aircraft-layer/ (the only subproject touched):
- `ruff format --check src tests`: **pass** (56 files already formatted)
- `ruff check src tests`: **pass**
- `mypy src` (run from inside `aircraft-layer/`): **pass**, 21 source files
- `pytest tests -q`: **pass**, 252 passed

No other subproject was touched, so no other suite applies.

Lua:
- `luac5.1 -p` on the **outer** file: pass.
- `luac5.1 -p` on the **bridged chunk extracted to its own file**, including the spliced
  `local MAX_SIGHTLINES = 128` prefix line: pass. (`luac -p` on the outer file proves nothing about
  the chunk — it lives inside a string literal.)
- `luac5.1 -p` over every file in `dcs-export/`: pass.
- **GETGLOBAL sweep, outer:** `loadfile, log, math, net, os, package, pcall, require, string,
  tonumber, tostring, type` — Lua stdlib plus genuine Hook-state DCS APIs.
- **GETGLOBAL sweep, chunk:** `coalition, env, ipairs, land, math, Object, pairs, PB_LOOK_FOV_DEG,
  PB_LOOK_HOUR, pcall, table, timer, tostring, type, world` — Lua stdlib, genuine scripting-state
  DCS APIs, and the two mission-scripting globals this channel reads on purpose.
- Neither list contains any of the script's own helpers (`considerCandidate`, `wrapSigned180`,
  `buildingClear`, `terrainClear`, `MAX_SIGHTLINES`), which is the mechanical ruling-out of the
  no-hoisting bug.

### Notable Discoveries

- **`aircraft-layer/CLAUDE.md` and `WORKFLOW.md` never documented this Hook script at all.** Every
  sibling Hook (overlay, F10 commands) has a Structure bullet; the LOS Hook had none, and neither
  did `WORKFLOW.md`'s deploy steps. The deploy gap is left as-is — out of scope here, but it means
  the deploy procedure for this script exists only in the file's own header.
- **The bubble radius was duplicated exactly the way the cap was** — `PLAYER_BUBBLE_RADIUS_M = 10000.0`
  in the outer file, `if rangeM > 10000.0` re-typed inside the chunk — and flagging it rather than
  fixing it **was the wrong call**: the review pointed out the local therefore had *zero* code
  readers, which is strictly worse than the cap's duplication (two live definitions that could
  drift) because it is one live definition plus one decoy that reads as governing the bubble.
  **Now spliced** (see the review-fix section). `HOUR_DEFAULT`/`FOV_DEFAULT_DEG` versus the chunk's
  `or 0`/`or 45` are a *different* case and are deliberately left duplicated: the file-level pair is
  live at `:565`/`:566` as `_safeClampInt` fallbacks for a **bad inbound value**, while the chunk's
  `or`-defaults cover **no command having arrived yet this mission**. They are equal by coincidence,
  not construction, so splicing them would couple two unrelated decisions — retuning the bad-input
  clamp would silently move the no-directive-yet wedge. Reviewer's explicit ruling; do not "tidy".
- **An unnamed object no longer counts toward `units_in_bubble`.** The name is now fetched before
  the bubble counter increments, so the counter equals the joinable population rather than the
  observed population. Previously a nil-named unit counted in bubble and wedge but produced no
  entry — and worse, a nil name would have hit a nil-concat error at the entry-building step, and
  an empty name would have produced an entry the Python parser rejects (`empty unit_name`), killing
  the whole snapshot. The probe measured names as non-null 50/50 units and 94/94 statics, so this
  is defensive rather than a fix for an observed failure.
- **`coalition.getGroups` was being called unprotected** (`ipairs(coalition.getGroups(coa) or {})`),
  as were `grp:getUnits()`, `unit:isExist()` and `unit:getID()`. All are now `pcall`'d. **The reason
  first written here — "an error inside `onSimulationFrame` takes the mission with it" — is false,
  and is corrected rather than defended** (2026-10-06 review). The chunk does not run in
  `onSimulationFrame`; it runs in the **mission-scripting state** via `net.dostring_in`, behind two
  independent layers of `pcall`: `dostring`'s own `pcall(net.dostring_in, …)` at `:567` and
  `pcall(pollAndSend)` at `:762`. A chunk error could never have taken the mission down — it
  produced a `poll failed:` log line. **The real reason, which is a good one:** a per-side
  enumeration failure should degrade to *fewer candidates* rather than losing the whole poll, and
  must then **say so in a counter**. That second clause is load-bearing and was the missing half —
  without it the `pcall` converts a loud failure into a silent one, which is what the wrong
  justification would have licensed next time. See the review-fix section below.
- **Statics cost is filter-only until they survive the wedge.** `getPoint` + arithmetic per
  candidate; only the capped survivors pay the two engine calls (`searchObjects` + `isVisible`).
  So the tripled population's cost is dominated by the cheap half unless the wedge is wide.

---

## Review fixes (2026-10-06, `plans/los-hook-statics/review.md`)

Three required fixes plus the one offered optional. The verdict was APPROVED WITH REQUIRED FIXES;
none was a correctness defect in the shipped Lua.

### Files Changed

- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` — mechanism, commit `f562cf4`.
- `plans/los-hook-statics/implementation.md` — the corrections above, in place, next to the claims
  they correct rather than only here. A wrong reason left standing where a reader will meet it is
  the thing being fixed; a correction appended 100 lines below it does not fix that.

### Fix 1 — `unitEnumFailures`

The asymmetry was real and verified by count: `staticEnumFailures` appeared 3× in the file,
`unitEnumFailures` 0×. The statics counter was added for a good reason — a total statics failure
would otherwise be indistinguishable from the pre-Stage-4 unit-only behaviour — and the same commit
wrapped the unit side's four enumeration calls in `pcall` with no equivalent. Before those `pcall`s
such an error propagated out of the chunk and `pollAndSend` logged `poll failed:`; after them a
side's units silently vanish.

**Why it is the fix that could have cost a second flight:** fewer candidates *understates* cap
pressure. A silent unit-enumeration failure makes `cap_hit=0` — the exact number this sortie exists
to produce — read as good news.

Counted in the `else` of the per-side `pcall(coalition.getGroups, coa)`, emitted as
`unit_enum_failures=` on the same `env.info` line, same naming and `tostring()` formatting as the
statics counters. **The four `pcall`'d sites on the unit side are enumerated in a comment at the
counter's declaration** — `coalition.getGroups` (per side), `grp:getUnits()` (per group),
`unit:isExist()` and `unit:getID()` (per unit) — stating that only the first is counted, why (it is
the one whose failure loses a whole side, and the one granularity comparable to
`staticEnumFailures`, which is also per side and also caps at 3), and that a fifth call needs either
a bump or its own counter. The enumeration lives next to the guard so the next person adding a call
can see what is being promised; a reader who only greps call sites gets the wrong count.

### Fix 2 — the false justification, corrected in place

Verified before correcting: `dostring` wraps `net.dostring_in` in `pcall` at `:567`, and
`onSimulationFrame` wraps `pollAndSend` in `pcall` at `:762`. Two layers. The chunk runs in the
mission-scripting state, not in `onSimulationFrame`, and a chunk error produced a log line, never a
mission crash. The `pcall`s are **kept** — the real reason (degrade to fewer candidates rather than
losing the poll, *and say so in a counter*) is good. Only the stated reason changed.

### Fix 3 — the bubble radius, spliced

`PLAYER_BUBBLE_RADIUS_M` had its declaration and two comment mentions and **zero code readers**; the
live bound was the re-typed `10000.0` in `considerCandidate`. Spliced, the same shape as the cap
three lines above, as `local BUBBLE_RADIUS_M = <value>` prepended to the chunk at module load.

**`%d` is wrong for it and that is not a nitpick.** The cap is an integer count, so `%d` is exact.
The radius is a float: `%d` would silently truncate the moment anyone writes a non-integral radius,
turning a deliberate edit into a quiet rounding. `%.17g` is the shortest width that round-trips an
IEEE-754 double exactly, verified rather than assumed:

| value | `%.17g` | `tonumber(…)` equals original |
|---|---|---|
| `10000.0` | `10000` | yes |
| `10000.05` | `10000.049999999999` | yes |
| `1/3` | `0.33333333333333331` | yes |

`tostring`/`%.14g` would have been enough for `10000.0` and not in general, which is the class of
"works today" the splice exists to remove. The boundary test stayed `>` (inclusive at the boundary),
unchanged.

The declaration comment now states that this is the only definition of the bubble and that editing
it really does move the bubble — the property that was false until now.

### Optional taken — the ownship claim softened

The Lua comment and the log both claimed a failed `getID()` "cannot silently let ownship through".
It can, if `getID()` **and** `getName()` both fail. Claim softened in both places to what the code
guarantees, and the condition made observable as `ownship_unidentified=0|1` on the scan line.

**Why a field on the existing line rather than its own log call:** the chunk is rebuilt and
re-executed every poll, so it holds no state across polls and cannot log "once" without introducing
a new mission-state global — which would add a fourth deliberate global to the `GETGLOBAL` sweep's
allowlist, for a near-impossible condition. At 1 Hz a dedicated warning line would be noise for a
whole flight. Returning `ERR|` was rejected by the review and is worse: it drops the whole poll for
every object.

### Not done, deliberately

- **`HOUR_DEFAULT`/`FOV_DEFAULT_DEG`** — explicitly out of scope; the review ruled they *should*
  stay duplicated (reason recorded in Notable Discoveries above). Not touched.
- **The farthest-surviving-candidate range** when the cap binds (optional refinement). The dropped
  count already answers "is 128 binding" well enough to retune, so this does not cost a flight.
- **The `CLAUDE.md` bullet's arrow ordering** and the `WORKFLOW.md` deploy gap — not in this task's
  brief; the deploy gap is being filed as an `AC-B<n>` backlog item by the orchestrator.

### Checks

aircraft-layer/ (the only subproject touched; **`src/` and `tests/` unchanged by these fixes** —
the diff is one `.lua` file plus one plan document, so ruff/mypy have nothing new to see, but the
suite was run anyway because a test parses the edited Lua file):

- `luac5.1 -p` on the **outer** file: **pass**.
- `luac5.1 -p` on the **bridged chunk extracted to its own file**, with **both** spliced prefix
  lines prepended (`local MAX_SIGHTLINES = 128`, `local BUBBLE_RADIUS_M = 10000`, the latter
  generated by running the file's own `string.format("%.17g", …)` rather than typed by hand):
  **pass**.
- `luac5.1 -p` over all **25** files in `dcs-export/`: **pass**.
- **GETGLOBAL sweep, outer:** `loadfile, log, math, net, os, package, pcall, require, string,
  tonumber, tostring, type` — Lua stdlib plus `log`/`net`, genuine Hook-state DCS APIs. `DCS` is
  absent because it is a `local` from `require("DCS")` at `:218`, checked rather than assumed.
- **GETGLOBAL sweep, chunk:** `coalition, env, ipairs, land, math, Object, pairs, PB_LOOK_FOV_DEG,
  PB_LOOK_HOUR, pcall, table, timer, tostring, type, world` — Lua stdlib, genuine scripting-state
  DCS APIs, and the three deliberate globals (`env`, `PB_LOOK_HOUR`, `PB_LOOK_FOV_DEG`). **No own
  helper appears**: not `considerCandidate`, `wrapSigned180`, `buildingClear`, `terrainClear`,
  `MAX_SIGHTLINES` or the new `BUBBLE_RADIUS_M`. Unchanged from the pre-fix sweep, i.e. the new
  local added no global.
- **The chunk sweep's sensitivity was proved, not assumed.** Run against the chunk body *without*
  the spliced prefix, the same sweep reports `BUBBLE_RADIUS_M` **and** `MAX_SIGHTLINES` as globals.
  So the clean list above is evidence that the splice lands, not a vacuous pass — which matters
  because a missing splice is exactly the no-hoisting bug this sweep exists to catch.
- `pytest tests -q` (unfiltered, from inside `aircraft-layer/`, borrowed venv): **pass**, **252
  passed** — identical to the baseline, as expected for a Lua-only diff.
- `tests/test_line_of_sight_hook_lua.py -v`: all **5 named tests** pass, confirmed by name. Relevant
  because the new `string.format("%.17g", …)` is a second `string.format` call site near
  `SET_LOOK_TEMPLATE`, whose guard regex could in principle have been loosened by it; pytest's
  `rootdir` resolved to the worktree, so the tests read the edited file.

**Live behaviour remains unverified and unverifiable from here, and nothing in these fixes weakens
that posture** — it is still stated in the file header, the schema docstring, the `CLAUDE.md` bullet
and this log. Acceptance is a sortie by the pilot on branch `fix/los-hook-statics`.

---

## Security deep analysis fixes (2026-10-08, `plans/los-hook-statics/security-review.md`)

Two required fixes plus one fix-before-public item taken while here. Verdict was
**APPROVED WITH REQUIRED FIXES**; no exploitable vulnerability, no dependency exposure. Base-commit
correction: the worktree landed on `main` (`2ddceff`), diverged from the named tip `60e5b07` with no
`--ff-only` path available since `worktree-agent-<id>` carried no unique commits — moved the branch
ref directly (`git checkout -B <branch> 60e5b07...`), per AGENTS.md rule 4's documented mechanism.

### Required fix 1 — a `;` in an object's name no longer drops the whole poll

Demonstrated mechanism (security review): `LineOfSightSnapshot.from_wire` splits `entries` on `;`,
and a fragment that does not `rsplit` into three `:`-separated fields raises
`LineOfSightParseError` — logged at `debug` in `line_of_sight_receiver.py:134` and the exception
propagates out of `from_wire`, discarding **every** verdict in that poll, not just the offending
object's. `:` and `|` are already safe by construction (`rsplit(":", 2)`, `maxsplit=6`) and were
deliberately left alone.

Fixed on the Hook side, in the shared `considerCandidate` filter, immediately after the existing
name-validity check: a name containing `;` (`string.find(name, ";", 1, true)` — plain find, not a
pattern) now drops that one object rather than the whole poll. Counted in a new `nameRejects` local,
declared above `considerCandidate` per the no-hoisting rule, reported as `name_rejects=` on the
existing `env.info` scan line — appended after `unit_enum_failures=` and before
`ownship_unidentified=`, so every existing field keeps its name and position. Counting it follows
this same branch's own `pcall-without-a-counter` lesson (commit `5ec13eb`): a drop with no counter
reads as "nothing to report."

### Required fix 2 — `LOS_CODE`'s splice gets the mechanical guard its sibling has

`tests/test_line_of_sight_hook_lua.py` already guarded `SET_LOOK_TEMPLATE` (exactly two `%d`, no
other specifier); the `LOS_CODE` prefix — `MAX_SIGHTLINES` via `%d`, `BUBBLE_RADIUS_M` via `%.17g` —
had no equivalent, so a later edit reaching for `%s` on either would land silently. Extended the
same test module (no new file), following `_extract_template`'s extraction approach:

- `_extract_los_code_prefix()` pulls both `string.format` calls' format-spec strings out of the
  `LOS_CODE` concatenation via regex, mirroring `_extract_template`.
- `test_los_code_prefix_has_exactly_one_percent_d_and_one_percent_17g` asserts the conversion sets
  are exactly `["%d"]` and `["%.17g"]`.
- `test_los_code_prefix_sets_both_globals_the_bridged_chunk_reads` asserts the splice actually
  assigns `MAX_SIGHTLINES`/`BUBBLE_RADIUS_M` — load-bearing, not decoration, since the bridged chunk
  cannot see the outer file's `local`s and a typo here would leave it reading a `nil` global.

**Non-obvious choice:** the existing `_FORMAT_DIRECTIVE_RE = re.compile(r"%[^%]")` only spans
single-character conversions and misparses `%.17g` as a bare `%.` (verified by running it red
first — it failed with `['%.'] == ['%.17g']`). Rather than widen that regex and risk changing
`SET_LOOK_TEMPLATE`'s existing guard behaviour, added a second regex, `_PRINTF_DIRECTIVE_RE`, that
spans a full printf-style directive (flags/width/`.precision`/conversion letter), used only by the
two new tests.

**Counterfactual run, not just reasoned:** temporarily changed the real `%.17g` call site to
`%.17s` (an edit to the actual splice, not to a copy or to the test), confirmed
`test_los_code_prefix_has_exactly_one_percent_d_and_one_percent_17g` goes red for exactly that
reason, then reverted via `Edit` back to `%.17g` and re-ran the full suite to confirm the restore
(254 passed, matching the post-fix baseline).

### Fix-before-public, taken while here — the `%.17g` "any value" comment

The header comment's "numerically identical to the constant for *any* value assigned to it" is
false for `math.huge`/`-math.huge`/NaN, which `%.17g` renders as `inf`/`-inf`/`nan` — not valid Lua
numeral syntax, so the chunk would fail to compile and every poll would error. Harmless today (the
constant is a literal `10000.0`, never reassigned — grep-confirmed by the earlier review round).
Narrowed the comment to "any *finite* value" and pointed at the existing NaN/infinity guards
(`_safeClampInt`, `test_lua_file_contains_the_nan_and_infinity_guards`) as the pattern that would
need to extend here if this constant ever stopped being a fixed literal. **No new runtime guard
added** — the value is not reachable today, so one would be ceremony against nothing live; said so
rather than papering over it, per the task's own instruction.

Finding 4 (the "neither test runs there" comment) was **not** touched — out of this round's named
scope (only the `%.17g` comment was named as in-scope-while-here); flagging that it remains open
for whoever next does a fix-before-public pass.

### Files Changed

- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` — the `;`-reject guard + `nameRejects`
  counter + `name_rejects=` field; the `%.17g` comment correction.
- `aircraft-layer/tests/test_line_of_sight_hook_lua.py` — `_extract_los_code_prefix`,
  `_PRINTF_DIRECTIVE_RE`, and the two new guard tests.
- `plans/los-hook-statics/implementation.md` — this section.

### Tests Added

- `test_los_code_prefix_has_exactly_one_percent_d_and_one_percent_17g` — `LOS_CODE`'s two
  `string.format` calls carry exactly `%d` and `%.17g` respectively, nothing else.
- `test_los_code_prefix_sets_both_globals_the_bridged_chunk_reads` — the splice assigns the two
  names (`MAX_SIGHTLINES`, `BUBBLE_RADIUS_M`) the bridged chunk actually reads.

No new parser-side test was added for Finding 1 (a `;`-rejected name): the parser itself was not
changed (deliberately — review's own ruling, strictness stays on the Lua/wire side), so there is no
new Python behaviour to assert on; the fix is Lua text, covered by reading and the bytecode checks
below, not by a Python test.

### Checks

aircraft-layer/ (only subproject touched; borrowed `.venv` from the main checkout at
`/Users/sg/Code/DCS-petrobrain/aircraft-layer/.venv`, source resolution confirmed unaffected since
only this worktree's own `src`/`tests`/Lua files changed):

- `ruff format --check src tests`: **pass** (56 files already formatted)
- `ruff check src tests`: **pass**
- `mypy src` (run from inside `aircraft-layer/`): **pass**, 21 source files
- `pytest tests -q` (unfiltered): **pass**, **254 passed** (252 baseline + 2 new)
- `pytest tests/test_line_of_sight_hook_lua.py -v`: all **7 named tests** pass, confirmed by name —
  including both new ones, not just a `-k` filter.
- `luac5.1 -p` on the outer file: **pass**.
- `luac5.1 -p` on the bridged `LOS_CODE` chunk, extracted to its own file with both spliced prefix
  lines prepended (`local MAX_SIGHTLINES = 128`, `local BUBBLE_RADIUS_M = 10000.0`): **pass**.
- **GETGLOBAL sweep, outer file:** `loadfile, log, math, net, os, package, pcall, require, string,
  tonumber, tostring, type` — unchanged from the pre-fix baseline, Lua stdlib plus genuine
  Hook-state DCS APIs only.
- **GETGLOBAL sweep, bridged chunk:** `coalition, env, ipairs, land, math, Object, pairs,
  PB_LOOK_FOV_DEG, PB_LOOK_HOUR, pcall, string, table, timer, tostring, type, world` — unchanged
  from the pre-fix baseline. No script-own helper (`considerCandidate`, `wrapSigned180`,
  `buildingClear`, `terrainClear`, `nameRejects`) appears as a global; the `;`-guard reads only the
  already-in-scope `name` local and increments the already-closed-over `nameRejects` local, so it
  introduces no new global by construction, confirmed by the sweep rather than assumed.

### Notable Discoveries

- **`_FORMAT_DIRECTIVE_RE` (single-char-conversion regex) silently misparses `%.17g`** — a precision
  digit between `%` and the conversion letter reads as `%.` plus stray literal text under that
  regex. It was adequate for `SET_LOOK_TEMPLATE` (`%d` only) by coincidence of that template's own
  simplicity, not because the regex is general. Left unchanged for the existing test; a second,
  more general regex was added for the new one rather than risk altering `SET_LOOK_TEMPLATE`'s
  established guard behaviour on an unrelated fix.
