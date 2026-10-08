# Definition of Done — `fix/los-hook-statics` (BL-11 Stage 4, statics enumeration)

**Verdict scoped to tip `6bbe3bb85f1525bf457e4122b0dd02e6006f23a9`.** If the branch moves past
this sha, this verdict is stale and must be re-run.

**Worktree base correction.** The worktree landed on `main` (`2ddceff`), the known AGENTS.md rule-4
mechanism (the branch is checked out in the main checkout). `main` and the named tip have diverged
(each carries commits the other lacks), so this is not a `--ff-only` case. The scaffolding branch
`worktree-agent-a91a9ad3fb34f6083` carried no commits of its own (a bare ref onto `main`'s tip), so
moving the ref directly was lossless: `git checkout -B worktree-agent-a91a9ad3fb34f6083 6bbe3bb...`.
Verified `git rev-parse HEAD` == `6bbe3bb...`, tree clean, before anything else below.

## Code Quality

Touched subprojects, from the diff against merge-base `7c16f16` (`git diff --stat`): aircraft-layer
(source + tests + research note) and body-layer (`ROADMAP.md`/`BACKLOG.md` only, no `src`/`tests`).
So only aircraft-layer's own commands were run.

| check (cwd `aircraft-layer/`) | result |
|---|---|
| `ruff format --check src tests` | 56 files already formatted |
| `ruff check src tests` | All checks passed! |
| `mypy src` (CWD-only config discovery) | Success: no issues found in 21 source files |
| `pytest tests -q` | **256 passed** in 39.36s — matches the dispatching prompt's claimed count |

Lua checks:

- `luac5.1 -p aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` — syntax OK.
- Outer-file GETGLOBAL sweep: `loadfile, log, math, net, os, package, pcall, require, string,
  tonumber, tostring, type` — all Lua stdlib / genuine Hook-state DCS APIs. No script-own helper
  name present (there are none declared as globals in this file in any case).
- **`LOS_CODE` bridged chunk, extracted separately** (the string-literal half `luac -p` on the
  outer file cannot see): reconstructed `local MAX_SIGHTLINES = 50\nlocal BUBBLE_RADIUS_M =
  10000.0\n` + the literal body between the `[[`/`]]` markers (lines 346-607), compiled standalone
  — syntax OK. GETGLOBAL sweep on that reconstruction: `coalition, env, ipairs, land, math,
  Object, pairs, PB_LOOK_FOV_DEG, PB_LOOK_HOUR, pcall, string, table, timer, tostring, type,
  world`. All of these are Lua stdlib, genuine DCS scripting-state APIs, or the two documented
  look-direction globals (`PB_LOOK_HOUR`/`PB_LOOK_FOV_DEG`) — `aircraft-layer/CLAUDE.md`'s "clean
  result" list. **No script-own helper name appears** (`considerCandidate`, `buildingClear`,
  `terrainClear`, `wrapSigned180`, `nameRejects` are all declared `local` and used only below their
  declaration — no hoisting bug).
  (First extraction attempt was wrong — I had included the `.. [[` / `]]` delimiter lines
  themselves as chunk *content*, which parsed but as a different, bogus program; corrected by
  taking only the literal body, lines 346-607, before the prefix lines.)

No unhandled errors/panics in data paths: every DCS API call in the hot path is `pcall`'d (unit
and static enumeration, `getName`, `getPoint`, `isExist`, `getID`); the `env.info` logging call is
itself wrapped in a `pcall` so a logging failure cannot take the poll with it (confirmed by
reading, matches `implementation.md`'s own account). No debug `print`/stray `env.info` outside the
one documented scan line. No TODO comments introduced by this feature (grepped the diff — none).

**Cross-subproject check — the "no body-layer change needed" claim, tested rather than
restated.** Grepped `body-layer/src` for the LOS join: `perception/naked_eye_source.py`'s
`_resolve_los_by_unit_name` joins `GET /world_objects/latest` objects to LOS entries purely by the
`unit_name` string field, with no branch on whether the object is a unit or a static — confirmed by
reading `naked_eye_source.py:1066-1130` and its docstrings. `GET /world_objects/latest`
(`LoGetWorldObjects`) already returns statics alongside units, unchanged by this diff. So the claim
holds: a static's LOS entry is structurally indistinguishable from a unit's on the wire, and the
join needs no change. Confirmed the diff touches no body-layer `src`/`tests` file.

## Scope & Correctness

- Matches `plans/los-hook-statics/implementation.md` and the two security required fixes
  (`plans/los-hook-statics/security-review.md`) exactly — confirmed against
  `plans/los-hook-statics/review-round-3.md`'s independent re-verification (full read, every claim
  re-derived: ran all four checks itself, reconstructed and compiled the `LOS_CODE` splice
  standalone, exercised the real Python parser both ways, grepped every write site into the wire
  format, and mutated `%.17g` → `%.17s` to watch the guard test go red before reverting).
- No unplanned scope added. One optional item taken (the `;`-name regression test, `6bbe3bb`); the
  other optional (one docstring line in `schema/line_of_sight.py`) was left, correctly marked
  optional by round 3, not required.
- No CLAUDE.md invariants violated: no-omniscience is unaffected (this is a ground-truth
  enumeration feed, not a belief-layer change); DCS remains authoritative; read-only DCS access
  preserved (no write to the DCS installation); the `getName()` join key and provenance posture are
  unchanged from the existing `line_of_sight.py` schema.
- `git status --porcelain` at the end of this run is clean except the files I added (listed below)
  — no stray untracked files, and `audio-adapter/.obsidian/` (pre-existing untracked noise named in
  the dispatch prompt) was never staged.

## Testing

- Core logic (the `;`-name hazard / guard, the splice-constant tests, the schema parser) is covered
  by `aircraft-layer/tests/test_line_of_sight_hook_lua.py` and
  `aircraft-layer/tests/test_line_of_sight_schema.py` — round 3 confirmed these are meaningful by
  mutation testing (`%.17g`→`%.17s` goes red for the right reason) and by running the real parser
  against both a pre-fix-shaped and post-fix-shaped payload.
- The statics-enumeration mechanism itself (the Lua hook's live DCS behaviour) has **no automated
  test and cannot have one** — this codebase's standing, documented limitation
  (`aircraft-layer/CLAUDE.md` "Testing": "the live Export.lua↔collector↔API path have no automated
  test"). This is not a gap this feature introduces.
- No existing tests broken (256/256 passing, same count across rounds 2 and 3 plus this run modulo
  the two added this round).

## Documentation

- Reviewer findings addressed: round 1 and round 2 fixes applied and re-verified; round 3 approved
  with **no required fixes**, two optionals (one taken, one correctly left).
- Non-obvious behaviour is explained in-line in the Lua file's own comments (the `isExist`-advisory
  decision for statics, the ownership-exclusion backstop, the per-side failure counters' rationale)
  and in `plans/los-hook-statics/implementation.md`.

## Security

- `plans/los-hook-statics/security-plan-review.md` does **not** exist for this directory, and that
  is expected, not a gap: this is a Stage-4 continuation of BL-11 under the existing
  `plans/dcs-driven-los/plan.md`/`security-plan-review.md` (dated earlier), and the current cadence
  is one security pass per whole feature immediately before DoD, not a plan review re-run per
  stage/fix (`CLAUDE.md` "Agents"; prior agent-memory confirms this pattern for change-request-style
  branches).
- `plans/los-hook-statics/security-review.md` exists: **APPROVED WITH REQUIRED FIXES** (two). Both
  fixes are implemented (`3395b4a`) and independently re-verified by review round 3
  (`cd19add`, **APPROVED, no required fixes**).

## Reviewer memory-index restoration (`6440dd9`)

`.claude/agent-memory/reviewer/MEMORY.md`: 155 lines, **143 entries**, grepped for a truncated hook
(trailing `...`/`…`) — none found. Restoration looks structurally sound.

## Acceptance boundary — what this branch's fixtures structurally cannot reach

Fixtures/mechanical checks can prove: the Lua parses, has no hoisting bug, the schema parser
handles both payload shapes, and the `;`-name hazard is closed. **They cannot prove the statics
enumeration actually returns real DCS statics, binds the engine's own API correctly, or that a
static's verdict is ever consumed downstream by a real detection** — none of that is observable
without a live DCS process.

## Live acceptance — PARTIAL, and explicitly not complete

The user is flying this branch right now; the main checkout stays on `fix/los-hook-statics` and was
never touched by this worktree.

**Confirmed live** (`docs/acceptance/2026-10-08-los-statics-sortie-feedback.md`, item 1, open
terrain): both enumerations ran with zero failures on both counters (`static_enum_failures=0`,
`unit_enum_failures=0`, which is what makes the cap-hit reading trustworthy); candidates went from 7
to 49, 42 of 49 being statics — the core mechanism this Stage exists to deliver, confirmed in
flight, not just by the fixture suite above.

**Still open, honestly represented as open, not as done:**

1. **Over Damascus the 128 candidate cap binds** (`cap_hit=1`, ~200+ in the wedge). Whether that
   population is scenery buildings (which `coalition.getStaticObjects` should not return at all),
   mission-placed statics, or AI units is **unresolved** — filed as **`BL-B42`** in
   `body-layer/BACKLOG.md`, explicitly *not* a blocker on this fix (the fix under gate is the
   enumeration; the population question is a design question that needs `/explore`, per root
   `CLAUDE.md`'s flight-feedback-capture-then-explore rule).
2. **A ~5 s stutter**, leading hypothesis `Export.lua`'s blocking reconnect path — unconfirmed, and
   not this branch's code (the LOS Hook polls at 1 Hz, so would stutter at 1 s, not 5 s, if it were
   the cause).
3. **The downstream join is still unobserved in flight** — nobody has yet seen a static's LOS
   verdict actually reach a body-layer detection/contact.

An acceptance card for items 1 and 3 (the two this branch's own gate still owns) is published below
— item 2 is out of this branch's scope and is tracked only in the acceptance-feedback doc.

## Milestone-boundary question (root `CLAUDE.md` "Milestone Completion")

**Yes, this changes what BL-11 Stage 4's remaining work is.** Before this fix, Stage 4's roadmap
text (step 2b) already flagged "re-measure the sightline cap and bridge cost — now unmeasured" as a
consequence of adding ~278 candidate statics. The live flight answers that prediction directly: the
cap **does** bind, but only in a dense-city case, and the open question is no longer "will the cap
bind" but "what population is binding it and should it be filtered before the cap is raised."
That reframes Stage 4's remaining step 3 (fail-closed) and step 4 (coverage counter) — a coverage
counter is more clearly worth having now that a real cap-hit case exists, and the fail-closed step
should wait on `BL-B42`'s population question so it isn't built against a candidate mix nobody has
decided is correct.

## Merge recommendation — not performed here

`main` is at `2ddceff`; merge-base with this branch is `7c16f16`. Checked the three commits named
in the dispatch prompt as already on `main` under different shas, using `git patch-id` rather than
trusting the sha pairing alone:

| this branch | main | patch-id match |
|---|---|---|
| `e52a67b` | `ec59e67` | **no** |
| `a2a33b1` | `6f54756` | yes |
| `dcd3aee` | `fecb110` | **no** |

The two mismatches are not a contradiction of the dispatch prompt's claim, but it understated what
is going on: `e52a67b` and `dcd3aee` each carry the *same* real content as their `main` counterpart
(`git show --stat` on both pairs confirms identical commit messages and identical non-`.obsidian`
file diffs — `docs/acceptance/2026-10-05-sortie-feedback.md`'s 26 lines for the first pair,
`body-layer/BACKLOG.md`+`ROADMAP.md`+`plans/post-review-fixes/explore-notes.md`'s edits for the
second) **plus accidental `.obsidian/`/`.DS_Store` files that got swept in on this branch and were
cleaned up separately on `main`** (`de65d68`/`8a7a0eb`/`6333f0c`). So all three commit pairs really
are the same intended change landing twice — the patch-id mismatch is noise from the accidental
files, not evidence the content differs.

**This branch will look to carry duplicate work at merge.** Recommend `git rebase main` (dropping
the three already-landed commits, which will likely need `-i` since two of the three won't apply
cleanly as empty patches given the `.obsidian` noise) before merge, done by whoever performs the
merge — not performed here per this role's instructions.

## Verdict

**PASS.**

What remains unverified, for the user to judge before merging:

- `BL-B42`'s population question (buildings vs. statics vs. units over a dense city) — tracked, not
  blocking.
- The downstream join has not yet been observed carrying a real static verdict into a detection.
- The rebase-before-merge recommendation above has not been performed.
- The `.claude/agent-memory/reviewer/MEMORY.md` restoration (`6440dd9`) was checked structurally
  (entry count, no truncated hooks) but not read for *content* correctness against what it claims
  to index.
