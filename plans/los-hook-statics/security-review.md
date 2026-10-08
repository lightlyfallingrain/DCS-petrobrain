# Security Deep Analysis: los-hook-statics

**Branch:** `fix/los-hook-statics` · **target tip:** `1fc35c7` · **date:** 2026-10-08
**Threat model applied:** single-player, LAN-only, single-user, under active development, intended
to go public open-source. The realistic harms rated here are **invariant violations and silent
degradation**, not attackers.

## How this was verified, and the base-commit mismatch

The worktree's HEAD was `2ddceff` (`main`'s tip) — **diverged** from the named tip, not an ancestor,
with 8 unique commits of `main` bookkeeping. `git merge --ff-only` was therefore not available, and
the branch could not be checked out (it is in the main checkout, being flown). Took the documented
snapshot fallback: read the target's Lua and documents through `git show 1fc35c7:<path>`.

The source delta between my base and the target is **one Lua file plus a module docstring**:

| file | delta |
|---|---|
| `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` | +312 / −36 — the feature |
| `aircraft-layer/src/schema/line_of_sight.py` | +19 / −2, **entirely inside the module docstring** |

Every other `src` and `tests` file is byte-identical, so the Python checks below ran against
behaviourally identical code. Stated rather than assumed, because a stale base silently verifying
the wrong code is this project's own documented failure.

| check | result |
|---|---|
| `pytest tests -q` (aircraft-layer, borrowed venv, `cwd` in the worktree) | **252 passed** |
| import resolution | `schema.line_of_sight` resolves to the **worktree's own** `src` — confirmed by `__file__` |
| `luac5.1 -p` on the whole hook file | OK |
| `luac5.1 -p` on the bridged chunk, with the two spliced prefix lines prepended | OK |
| `GETGLOBAL` sweep over that chunk | reads `env`, `PB_LOOK_HOUR`, `PB_LOOK_FOV_DEG`, and otherwise only DCS API / Lua stdlib names (`world`, `coalition`, `land`, `timer`, `Object`, `math`, `table`, `pcall`, `pairs`, `ipairs`, `type`, `tostring`) |
| `SETGLOBAL` count in that chunk | **0** — the chunk writes no global at all |

Live behaviour is unverifiable from here. Nothing below claims anything works in the sim.

## Dependency Status

**No dependency change.** No manifest or requirements file is touched by the feature range
(`c322998^..1fc35c7`); the only non-document files are the Lua hook and the schema docstring. No CVE
search was owed.

---

## What is not a problem — said explicitly, so the findings stay credible

1. **Wire format, network surface, parsing path, Python behaviour: all clear.** The entry shape is
   unchanged, no port is added, no listener is added, the parser is untouched, and the only Python
   edit is docstring prose. Nothing was manufactured in these categories.

2. **The omniscience direction is *toward* the invariant, not away from it.** This is the central
   judgement asked for and it comes out favourable. Before this change a static's
   `live_los_clear` was always `None`, so `visibility.py:789` fell through to world-model's offline
   `line_of_sight_clear` — a **terrain-only, building-blind** primitive carrying a reviewed 12 m
   permissive tolerance. After this change those objects get `land.isVisible` **plus** a
   `world.searchObjects`/`SEGMENT` building test, both true-position-to-true-position from the
   engine. For the statics population the gate becomes **strictly harder to pass**, because buildings
   can now block where nothing could block before. Admitting statics to the gate is the gate working
   as intended; it is not an omniscience widening.

3. **A static cannot reach belief on a path a unit could not.** Verified at the layer above the wire.
   `_resolve_los_by_unit_name` (`body-layer/src/perception/naked_eye_source.py:1066`) branches on
   nothing but `unit_name`, `object_id` and the two booleans — no type, no category, no static flag
   anywhere in the join. Gate 4 (`visibility.py:785-791`) is likewise type-blind. Statics already
   flowed through the world-objects feed, association, clustering and the callout path before this
   change; what is new is only that they can now carry a verdict.

4. **`isExist` being advisory for statics is safe, re-derived independently.** Two separate reasons,
   either sufficient:
   - **The join is driven by the live feed, not by the verdict set.** The resolution loop iterates
     `objects` (this poll's `GET /world_objects/latest`) and looks each name up in `verdicts`. A
     verdict for an object absent from that feed is never read — there is no iteration over
     `verdicts` anywhere. A stale verdict cannot attach to anything.
   - **A verdict makes no aliveness claim.** Even if a destroyed static still appears in the Export
     feed as a wreck, the verdict says only "this sightline is clear", and the wreck is where the
     wreck is. Aliveness comes from the feed, never from LOS.

   Note also that the advisory path is narrower than its own comment implies: the test is
   `(not okE) or exists`, so an `isExist` that *works and returns false* still drops the object.
   Only a **failing** call admits.

5. **The ownship hole costs one wasted sightline and cannot reach belief.** Three independent
   barriers, each of which alone is sufficient, and the first was not in the reported analysis:
   - For ownship to be admitted, `player:getName()` must fail **while** `obj:getName()` on the same
     unit succeeds inside `considerCandidate` — the name check at line 446 drops any candidate whose
     own `getName()` fails. Same method, same unit; a failure of one is near-certainly a failure of
     both.
   - If it were admitted, the verdict is keyed by the **mission-scripting** name
     (`01-A-Mi-24P011`), while the Export feed reports ownship's `unit_name` as the player's
     **callsign** (`sg`) — the research note's own falsified-comment finding. The names differ, so
     the join finds nothing.
   - `association.py:286` drops any candidate whose `is_ownship is True` before the gate runs.

   Exposing it as `ownship_unidentified=0|1` rather than failing the poll is the right call: an
   `ERR|` would drop every object's verdict for one unresolvable self-reference.

6. **The code-generation splice is safe as written — confirmed, not taken on trust.**
   `MAX_SIGHTLINES_PER_CALL` (line 256) and `PLAYER_BUBBLE_RADIUS_M` (line 249) are module-level
   `local`s assigned once from numeric literals and **never reassigned** anywhere in the file
   (grep-confirmed over all 16 mentions; the other 14 are comments and `tostring` log reads). Nothing
   inbound can reach either: the chunk is built at module load, before any socket exists, and the
   `GETGLOBAL` sweep confirms the chunk reads no name the splice could have introduced. `%d` on an
   integer and `%.17g` on a float can each emit only `[-+0-9.eE]` and so cannot close the long
   bracket or open a statement. The `SET_LOOK_TEMPLATE` runtime splice and its `_safeClampInt` guard
   are unchanged by this feature and remain as the earlier plan review left them.

7. **Cross-population name collision fails closed where it can bite.** Statics are enumerated
   second, so `verdicts[name]` is last-write-wins in favour of the static. But if a unit and a static
   share a name and both appear in the Export feed, `name_counts[name] > 1` drops **both** to
   unresolved — the SRTM fallback, not a wrong verdict. The research note measured **zero** duplicate
   `unit_name` across all 404 objects of the mission concerned. Residual: a collision where only one
   of the two is in the Export feed would mis-assign one verdict. Low probability, one object, and
   either direction of error is a sightline call, not an existence claim. **Not a finding** — recorded
   so the next pass does not re-derive it.

---

## Code Findings

| # | File:Line | Pattern | Severity | Assessment |
|---|---|---|---|---|
| 1 | `petrobrain-line-of-sight-hook.lua:446` / `schema/line_of_sight.py:_parse_entry` | delimiter injection from mission-author free text | **LOW, fix now** | A `;` in any object name drops the **entire poll's** verdicts. Feature-amplified. |
| 2 | `petrobrain-line-of-sight-hook.lua:332-336` | code-generation site with no mechanical guard | **LOW, fix now** | The sibling splice has a guard test for exactly this reason; this one has none. |
| 3 | `petrobrain-line-of-sight-hook.lua:328-331` | overclaimed safety property in a header comment | **LOW, fix before public release** | The "any value" claim is false for `math.huge`/NaN. |
| 4 | `petrobrain-line-of-sight-hook.lua:378` | comment contradicts the code it describes | **LOW, fix before public release** | "neither test runs there" — one of the two does. |
| 5 | `petrobrain-line-of-sight-hook.lua:512-531` | fail-open with no counter | **pre-existing, note only** | Untouched lines, but the feature changes their consequence. |

### Finding 1 — a semicolon in one object's name silently drops every verdict in that poll

**Location:** the shared filter, `considerCandidate`, hook line 446 (the name check) — and
`schema/line_of_sight.py`'s `_parse_entry`, which raises on the malformed fragment.

**Demonstrated by execution, not reasoned.** Feeding crafted payloads through the real parser:

| name contains | outcome |
|---|---|
| nothing special | OK, both verdicts parsed |
| `:` | OK — `rsplit(":", 2)` handles it by design |
| `\|` | OK — `split("\|", 6)` leaves the entries field intact |
| **`;`** | **`LineOfSightParseError` — the whole poll is dropped** |

**Failure scenario.** A mission author names one static `Checkpoint; north`. The Hook emits it; the
receiver raises `LineOfSightParseError` at `line_of_sight_receiver.py:134`, logs at **`debug`**, and
returns. Every object in that poll loses its live verdict, so every one of them falls back to
world-model's **building-blind** SRTM primitive — the exact permissive path this feature exists to
replace. It persists for as long as that object is in the wedge, and at `debug` level nobody sees it.
A sortie would read as "the statics fix did nothing".

**Why this is this feature's finding and not a pre-existing one.** The hazard existed for units, but
the feature triples the candidate population and adds the population whose names are *most* likely to
be decorative author prose rather than a terse `Tank-1`. More to the point, the feature created the
single shared filter that is the natural place for the guard — the fix is one line there and did not
previously have a home.

**Fix:** in `considerCandidate`, immediately after the existing name validation, drop a name that
cannot survive the wire — `if string.find(name, ";", 1, true) then return end`. One object is lost
instead of the whole poll, which is the right failure direction and matches the
nearest-first/drop-the-far reasoning already in this file. Leave the parser strict.

**Risk rating, honestly:** Probability **low** — it needs one author to use a semicolon.
Impact **medium** — total, silent loss of the gate the feature was built to supply, reverting to the
permissive primitive. Cost of the fix: one line plus a parser test.

### Finding 2 — the new splice has no mechanical guard, unlike its sibling

**Location:** hook lines 332-336 (`LOS_CODE`'s load-time prefix).

The file's own header argues that the `SET_LOOK_TEMPLATE` splice needs
`tests/test_line_of_sight_hook_lua.py` to assert "exactly two `%d` and no other specifier" as a
mechanical guard "against exactly that edit". This feature adds a **second** code-generation site
and no equivalent assertion: `grep` over `aircraft-layer/tests/` finds **no** reference to
`MAX_SIGHTLINES`, `BUBBLE_RADIUS`, `%.17g`, `getStaticObjects` or `considerCandidate`.

**Failure scenario.** A later change wants a theatre name or a string flag in the chunk and reaches
for the existing prefix pattern with `%s`. Nothing fails. The project has already decided this
category deserves a guard; the guard simply was not extended to the new site.

**Fix:** extend `test_line_of_sight_hook_lua.py` to assert the `LOS_CODE` prefix contains exactly the
conversions `["%d", "%.17g"]` and no other `%` specifier, with the same comment the sibling test
carries. The test is currently safe to write — verified above.

### Finding 3 — the `%.17g` claim is stated more broadly than it holds

**Location:** hook lines 328-331: *"`%.17g` is the shortest width that always does, so the spliced
text is numerically identical to the constant for **any** value assigned to it"*.

Not true for `math.huge` or NaN: `%.17g` renders `inf` / `nan`, neither of which is a Lua numeral, so
the chunk fails to compile and **every poll** returns an error — a total feed outage from one
constant edit. Harmless today (the constant is `10000.0`), but the sentence is the kind of
over-broad safety claim that licenses the edit it was meant to prevent, and this role has already
been burned by a documented claim outliving its premise.

**Fix:** narrow the claim to "for any finite value", or assert finiteness at module load.

### Finding 4 — a comment says a filter does not run where it does

**Location:** hook line 378: *"Statics cannot be ownship, so neither test runs there."*

The **id** test is unit-loop-only (lines 474-477). The **name** test is at line 447, inside
`considerCandidate`, which statics pass through — so it does run on statics. Consequence is
negligible (a static named identically to the player's mission-scripting name would be silently
dropped from LOS, one object), but the comment misdescribes the shared filter that is this feature's
central structural claim. The last commit on this branch was itself about stopping a wrong tidy-up;
this is the same class of hazard.

**Fix:** correct to "the id test does not run on statics; the name test is in the shared filter and
is a harmless no-op there."

### Finding 5 — pre-existing fail-open in the sightline primitives, newly consequential

**Location:** hook lines 512-531. **Confirmed untouched by this feature** (`git diff` over the
feature range shows no change to `buildingClear`/`terrainClear`). **Not a blocker and not this
feature's finding** — recorded because the feature changes what the fail-open means.

Both primitives return `true` ("clear") when their `pcall` fails, with no counter. Previously a
failing `world.searchObjects` affected only units, which had a verdict either way. Now a fail-open
verdict for a **static** actively *overrides* the SRTM fallback that would otherwise have been
consulted — so a silent, systematic `searchObjects` fault becomes a maximally permissive verdict for
~69 % of objects, in the omniscience direction, with nothing on the log to say so. This is precisely
the argument the file's own `unitEnumFailures`/`staticEnumFailures` comments make for the
enumeration sites ("a failure that is not counted reads as good news"); the reasoning applies here
and the counter is absent.

**Suggested (not required):** two counters on the existing `env.info` scan line —
`building_test_failures` / `terrain_test_failures`. It rides a line that already exists, costs no
wire change, and closes the one remaining silent fail-open in the chain.

---

## Verdict

**APPROVED WITH REQUIRED FIXES**

The feature's core security property is sound and its direction is correct: it makes Petrovich's
sightline gate *stricter* for the population it admits, the shared filter genuinely makes a static
indistinguishable from a unit at every layer checked, and the three paths flagged for scrutiny
(advisory `isExist`, the ownship hole, the splice) each hold up under independent derivation. No
exploitable vulnerability, no probable risk, no dependency exposure.

### Required Fixes

1. **Guard the entry delimiter in the shared filter** — `considerCandidate`,
   `petrobrain-line-of-sight-hook.lua:446`. Drop a name containing `;`. Add a parser test asserting
   one bad name costs one object, not the poll. (Finding 1)
2. **Extend the splice guard test to the new code-generation site** —
   `aircraft-layer/tests/test_line_of_sight_hook_lua.py`. (Finding 2)

Both are mechanical and total roughly fifteen lines. Per `AGENTS.md` they re-enter
Implementer → Reviewer → DoD rather than going straight to DoD.

### Fix before public release (not blocking)

3. Narrow the `%.17g` "any value" claim, or assert finiteness at load. (Finding 3)
4. Correct the ownship-filter comment at line 378. (Finding 4)
5. Consider counters for the two fail-open sightline primitives. (Finding 5 — pre-existing)

### Outside security's remit, flagged once

The cap (`MAX_SIGHTLINES_PER_CALL = 128`) under a tripled candidate population remains **unmeasured**,
as the implementation says plainly. That is a coverage question, not a security one, and the
instrumentation to answer it in one sortie is in place. Worth saying only because the failure
direction if it binds is silent under-coverage, which is the same shape as the findings above.
