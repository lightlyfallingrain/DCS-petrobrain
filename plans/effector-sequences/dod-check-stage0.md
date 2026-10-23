# Definition of Done check — BL-B90 Stage 0b (offline effector-registry generator)

**Branch:** `feature/effector-sequences`
**Verdict scoped to tip:** `40641c973ca010605cac2c324722a47ef3f156d9` — this worktree's original
HEAD (`f4e552c1`, a different line of work) was not an ancestor, so it was detached straight to
this sha (clean tree, confirmed before and after). **If the branch moves past this sha, re-run
before trusting this verdict.**

**Batch under check:** the plan revision for BL-B80 v2, Stage 0a recon write-up, Stage 0b
generator + fixtures + tests, review + required fixes + re-review (APPROVED), security deep
analysis (APPROVED, one low-severity finding filed as `BL-B91`) and performance review
(APPROVED). The BL-B91 fix itself (TOML control-character escaping) plus its own review
(APPROVED) are also in this batch. **Not in this batch**: Stage 0c (the real run on the Windows
DCS machine), Stage 0d, and Stage 1+. **BL-B90 stays `[~]` in progress — no merge.**

## Code Quality

- **Subprojects touched** (`git diff --name-only origin/main...HEAD`): `body-layer` (code +
  tests + fixtures) and `aircraft-layer` (one new research note only, no `src`/`tests` change).
- `body-layer`, run fresh in this worktree:
  - `ruff format --check src tests tools` — **pass** (172 files already formatted)
  - `ruff check src tests tools` — **pass**
  - `cd body-layer && .venv/bin/mypy src` — **pass** (71 source files)
  - `.venv/bin/mypy tools` — **pass** (8 source files)
  - `pytest -q` (whole suite) — **2505 passed, 4 xfailed**, matching `implementation.md`'s own
    reported count exactly; no regressions.
- `aircraft-layer` — no code changed (only `aircraft-layer/research/
  2026-10-23-mi24p-clickabledata-forms.md`, a dated research note), so its format/lint/type/test
  commands were not required and were not run.
- No unhandled errors/panics in data paths: the generator is designed fail-closed throughout
  (unhandled elements, duplicate names, unresolvable includes, malformed loops all raise/report
  rather than guessing), confirmed by Reviewer's and Security's independent reads plus my own
  spot-check of the CLI's exit-code paths (below).
- No debug output left in committed code: grepped `generate_effector_registry.py` and its test
  file for `print(`/`TODO`/`FIXME`/`XXX`/`pdb.set_trace`/`breakpoint()` — every `print(` is the
  CLI's own intentional stdout report (this tool's whole job is to print a report), no debug
  leftovers, no TODO/FIXME markers.
- All new files staged with `git add`: confirmed — every file `git diff --name-only
  origin/main...HEAD` lists is already committed on this branch; `git status --porcelain` was
  clean at both HEAD-check points.

## Scope & Correctness

- Implementation matches the plan (as now corrected — see "Plan corrections" below). Reviewer's
  re-review (APPROVED) independently verified all four Required Fixes closed by re-running the
  exact mutations that first demonstrated each gap.
- No unplanned scope added silently: every departure from the plan's original text (`shape`
  naming, `cmd2`/`seat_explicit` fields, three-way completeness, exit-code assignment,
  `autoupdate.cfg` read timing) is logged in `implementation.md`'s "Decisions made during
  implementation" and "Follow-up pass" sections, with reasoning — per this project's "departing
  is allowed, doing it silently is not."
- No invariants violated: never executes the parsed Lua (confirmed by Security and by reading
  the import block — stdlib only); writes only inside the project's own `config/` by a
  script-relative default path, never inside `$DCS_INSTALL_PATH`; no DCS-BIOS import/parse (only
  named in the module docstring as a by-hand labelling aid — grepped clean); no ED source
  committed (all nine fixture `.lua` files are synthetic, labelled as such in their own headers).
- All new files staged — see above.

## Plan corrections made this pass (`plans/effector-sequences/plan.md`)

The task brief named specific places where the implementer's own departures (logged in
`implementation.md`) left the plan's text wrong for a Stage-1 reader. Fixed, each with a note of
what changed and why:

1. **"Forms the parser must handle"** rewritten to state Stage 0a's confirmed forms as fact
   rather than as open questions for 0a — `devices.lua`'s bracket-only declaration (no dotted
   form), the reversed include direction (per-system files `dofile` *into* `command_defs.lua`,
   not the other way), the real 22-signature/18-called helper set (not 8), the raw-literal field
   names (`device`/`hint`/`action`/`arg`, not `cockpit_device_id`/`name`), the corrected seat rule
   (always one of `pilot`/`operator`/`both` plus `seat_explicit`, never a `"default"`
   placeholder), and the three-way completeness invariant (`heads == handled + unhandled +
   patches`, not two-way).
2. **Output TOML example** corrected to the shipped schema: `seat`/`seat_explicit` resolved
   values, `device_name` as its own field, list-shaped `cmds`/`args` throughout, `shape` as the
   bare helper name (including `"raw_table_literal"`), and a build placeholder instead of the
   stale hardcoded `2.9.29.27278`.
3. **`--dcs-build` resolution timing** clarified as lazy (resolved immediately before the write
   step, not unconditionally at startup) — the judgment call `implementation.md` flagged as not
   fully settled by the plan's own text either way.
4. **0d control points / build references** updated: both 2.9.29.27278 and 2.9.30.28738 are now
   confirmed-live builds (same 749-element count), so a mismatch on either is a parser bug, not a
   build drift to write up.
5. **R7 / Stage 4 reversed**, per `explore-notes.md`'s 2026-10-23 "Readback rate and scope"
   section, which the plan had not yet absorbed: the generic low-rate switch readback is **not**
   a deferred/backlog item and is **not** merely additive to BL-B80's per-frame push — it is
   BL-B90's own **last stage**, moving the six switch args off the per-frame feed onto a
   lower-rate (ideally on-demand, `Export.lua`-level) query, quoting the user's own words. Updated
   in three places: the R7 table row, the Stage 4 prose (both the "What moves, what stays"-
   adjacent summary line and the numbered "Implementation Plan" item), and "Decisions Requiring
   User Input" #1 (marked decided, no longer open).
6. **"Decisions Requiring User Input" #3** (the BL-B80 air-start "Guidance unit ready"
   divergence) marked resolved — `fix/guidance-ready-edge` is merged to `main` (verified:
   `git log --oneline origin/main` shows the merge commit and its DoD/review/security/performance
   chain), independently of this plan's own Stage 2. The "Finding outside this plan's scope"
   section near the top of the plan updated to match.

No design was invented beyond what `explore-notes.md`'s quoted user direction already states —
flagging, as the task brief asked, that the R7/Stage 4 reversal is plan-text-only; nothing about
*how* the on-demand `Export.lua` query should work beyond what the user's own words already say
was added, and if Stage 4's actual design needs more than that quote supplies, it is an Architect
question when Stage 4 is reached, not something this pass should invent.

## Testing

- Core logic (the Lua parser, the three structural-failure guards, the TOML renderer/escaper) is
  covered by 48 tests in `test_generate_effector_registry.py`, confirmed meaningful rather than
  decorative by Reviewer's own mutation testing (reran the exact mutations that first demonstrated
  each of the four Required Fixes against the fixed code, confirmed each fails a test) and by
  Security's own counterfactual re-run of the BL-B91 fix (10 of 14 relevant tests fail against the
  pre-fix code, verified directly rather than trusted from `implementation.md`).
- No existing tests broken: whole-suite `pytest -q` count (2505 passed, 4 xfailed) matches
  `implementation.md`'s own reported count exactly, confirmed by me running it fresh, not by
  trusting the report.

## Documentation

- Reviewer findings addressed: all four Required Fixes plus all three Optional Refinements,
  confirmed closed by the re-review (APPROVED) and independently spot-checked by me reading both
  review passes in full.
- Non-obvious behaviour explained: `implementation.md`'s decision logs cover every departure from
  the plan's literal text; the research note (`aircraft-layer/research/
  2026-10-23-mi24p-clickabledata-forms.md`) is a thorough, dated, sourced write-up of the real Lua
  forms, distinguishing what it corrects from what it confirms.
- One generalisable insight harvested to `notes/planning-and-process-lessons.md` (see below).

## Security

- `plans/effector-sequences/security-stage0.md` — **APPROVED**. One low-severity finding
  (TOML control-character escaping gap in `label`/element `name`) filed as `BL-B91`, then fixed in
  this same batch and separately reviewed — **APPROVED** (`review-stage0.md`'s "2026-10-23 — BL-B91
  fix review" section).
- No plan-stage security-plan-review file exists for this Stage-0-only batch (`plans/
  effector-sequences/security-stage0.md` is the deep-analysis document; the plan-review-after-
  Architect step predates this specific Stage 0 spec and is not required per root `CLAUDE.md`'s
  "once per batch of stages actually executed together" cadence — this batch's deep analysis is
  the one pass the cadence calls for, and it ran and approved).

## Milestone status

`body-layer/ROADMAP/BL-B90.md` updated: Stage 0b marked done (2026-10-23) with what it corrected
and why; Stage 0c named as next, pointing at `plans/effector-sequences/stage0c-run.md`; the
milestone-completion question answered in one line (Stage 1's curated registry can now be filled
directly from the real dump's confirmed field names, no further format negotiation). **BL-B90
itself stays `[~]` in progress** — Stage 0c (Windows run), 0d (control-point check + commit) and
Stage 1+ remain.

## Notes harvest

Ran `/notes-harvest effector-sequences` (manually, the skill's embedded script run from a
scratchpad copy since the skill description itself is only a usage string). All candidates from
`implementation.md`'s "Notable Discoveries" and both review passes' "Required Fixes" came back
"no duplicate," but on inspection are Stage-0-specific corrections already fully recorded in the
research note / updated plan.md / implementation.md — not independently generalisable, and
already findable there (`memory-search.py`/`gq.sh`), so per CLAUDE.md's "do not add notes/ entries
that are obvious from the code or already documented," skipped.

**One genuinely generalisable, non-obvious lesson added** to
`notes/planning-and-process-lessons.md`: a completeness/parity invariant drafted against an
*inferred* external file structure can undercount by a whole term once the real structure is read
— this plan's two-way `heads == handled + unhandled` check needed a third term (`+ patches`) once
Stage 0a's recon found 235 of 749 heads were field patches, not new definitions, a category the
plan's own prior inference never considered.

Two new **reviewer**-role agent-memory files were created on this branch during the review passes
(`feedback_static_lookup_table_entries_need_per_entry_mutation.md`,
`feedback_independent_transcription_claim_needs_source_math_not_diff.md`) — both are first
occurrences, not yet recurring, and correctly scoped as reviewer-process memory rather than
project-domain notes. No action needed from this pass beyond noting them.

## Recurring-fix pattern check (dod memory)

Searched `.claude/agent-memory/dod/` for a category this feature's required fixes might bump to
"recurring." The closest existing entry, `project_recurring_approved_plan_wrong_on_real_data.md`
("a reviewed, approved design that only broke against real sortie/tile data, never a fixture"),
does **not** match this feature's shape closely enough to bump its count: in that pattern, a
*plan already approved* breaks silently against real data; here, the plan's original guesses
about ED's Lua forms were caught by `Stage 0a`'s own live recon *before* Stage 0b was built against
them — exactly the mitigation this project adopted (an investigator-style recon pass before
committing to unverified-internals assumptions) working as intended, not a new instance of the
failure slipping through. None of Stage 0's four Required Fixes (duplicate-name guard,
statements-ignored implementation, helper-signature coverage, CLI flag naming) matched any other
existing dod-memory category on a `memory-search.py` pass either. No pattern-memory update made
this pass.

## Verdict

**DoD: PASSED** for this batch (Stage 0a + Stage 0b + their review/security/performance passes +
the BL-B91 fix and its review). **Milestone BL-B90 remains `[~]` in progress — no merge.** The
branch carries on to Stage 0c (Windows DCS machine) next.

---

## Acceptance boundary — what Stage 0b's fixtures structurally cannot reach

Named explicitly, per this role's standing instruction: a DoD pass against synthetic fixtures is
not a flight pass, and this one is further removed than most, since this stage never touches a
running aircraft at all.

- **No fixture, however faithful, proves the parser handles the *actual* installed
  `clickabledata.lua`/`command_defs.lua`/`devices.lua`.** Stage 0a's recon (one read of the real
  files, one build) and the nine synthetic fixtures built from it are the best available
  substitute, but they are still a transcription, not the file. Stage 0c — the real run against
  the live Windows install — is the only thing that actually proves this, and it has not run yet.
  A clean 0c report is still not proof against every real form: the 749-head completeness count
  and the 0d control points are the fail-closed backstop for exactly this gap, not a replacement
  for running it.
- **A later DCS patch can silently change the real file's shape in a way neither this review nor
  0c's current run would catch retroactively** — the generator's own "regenerate after any DCS
  update" header line exists because device/command numbers are positional, but nothing re-runs
  Stage 0c automatically; it is a manual step tied to a DCS patch, not a CI gate.
- **Nothing in this batch touches a cockpit, a switch, or a spoken line** — Stage 0 is an offline
  text-to-text transform with no runtime dependency at all (confirmed by Performance Review's
  "offline, dev-time, rare invocation" framing). The acceptance-testing-plan-with-live-flight
  pattern this role normally runs does not apply to this batch; there is nothing in DCS to fly
  against yet. The first point any of this reaches the cockpit is Stage 2's wiring and Stage 3's
  re-flight card, both still ahead.

## Acceptance Testing Plan — adapted: no live DCS step for this batch

**Goal:** confirm the generator and its CLI behave as documented, without a live DCS install.

**Prerequisites**
- [x] `cd body-layer && .venv/bin/mypy src` and `.venv/bin/mypy tools` — both pass (done above).

**Test cases — all run, output pasted, nothing left as a guess**

1. `DCS_INSTALL_PATH` unset, no `--scripts-dir` →
   `python3 tools/generate_effector_registry.py` — **ran it**:
   ```
   DCS_INSTALL_PATH is not set -- not on the DCS machine; pass --scripts-dir to point elsewhere.
   ```
   exit 1. Matches the plan's documented startup-refusal message and exit code exactly.
2. Report mode against the `clean` synthetic fixture (`--scripts-dir tests/fixtures/
   effector_registry/clean --dcs-build test-build`) — **ran it**:
   ```
   10 elements[ heads: 9 emitted, 0 unhandled, 1 field patches, 1 statements ignored
   statements ignored (neither an elements[...] definition nor a patch):
     line 4: elements = {}
   (report only -- pass --write to write the registry)
   ```
   exit 0.
3. `--write --output <scratch path>` against the same fixture — **ran it**: wrote the file, printed
   `wrote <path> (9 elements)`, exit 0. Header content (source line, per-input sha256, the
   three-way elements count, the regenerate-after-patch line) matches `plan.md`'s corrected
   "Output" example shape exactly.

**Edge cases to probe** — covered by the 48-test suite, independently re-verified by Reviewer via
mutation (duplicate table/device name now raises; an untested helper-signature entry now fails a
test; a control character in `label` now escapes instead of breaking `tomllib`) rather than taken
on faith.

**Pass criteria** — all three ran commands above produced exactly the documented output; the
48-test suite plus the full 2505-test body-layer suite pass with no regressions. **Met.**

**Not run, and explicitly out of reach from this machine:** the real Stage 0c command
(`plans/effector-sequences/stage0c-run.md`) against the actual installed Mi-24P module — there is
no DCS install on this Mac. That card is written, its mechanics (the unset-variable refusal and
the write/report flow) are verified against the fixture above, but the real run is UNVERIFIED by
construction until the user runs it on Windows.

---

## Stage 0c command, verbatim (for the user)

```sh
cd body-layer

# 1. Report only
python3 tools/generate_effector_registry.py

# 2. If step 1 exits 0 (no unhandled elements), write the real dump:
python3 tools/generate_effector_registry.py --write
```

Full card with prerequisites and what to send back: `plans/effector-sequences/stage0c-run.md`.
