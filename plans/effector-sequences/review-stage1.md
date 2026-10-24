### Review Summary

BL-B90 Stage 1 (curated effector registry + sequence loader, branch `feature/effector-sequences`,
tip `6ab3d4aa`). Reviewed against `plans/effector-sequences/plan.md` ("File formats", D1-D10/R11),
`explore-notes.md`'s 2026-10-23 sections, `implementation.md`'s "Stage 1" entry, and
`body-layer/CLAUDE.md`.

Scope matches exactly: `belief/effector_registry.py` and `belief/effector_sequences.py` are pure
loaders, no engine, no `logger.py`/`crew_console.py`/`sight_effector.py` wiring (confirmed by grep
— neither module is imported anywhere outside itself and its own tests). Stdlib only. The five
shipped sequence files and the curated registry reproduce today's hard-coded `sight_effector.py`
behaviour exactly, including the one intended deviation (takeoff runs every takeoff, gated by
`!= on` row conditions rather than a one-shot latch).

**Checks (body-layer/, this worktree, tip `6ab3d4aa`):**
- `ruff format --check src tests tools` — pass (178 files)
- `ruff check src tests tools` — pass
- `cd body-layer && .venv/bin/mypy src` — pass (73 source files)
- `.venv/bin/mypy tools` — pass (9 source files)
- `pytest -q -p no:randomly` — 2532 passed, 4 xfailed, no regressions

### Parity (sight_effector.py / logger.py vs. the shipped sequence files)

- **Takeoff order and values**: `_POWER_UP_SWITCHES` = `(WEAP_SYS,3028)→(ASP_17V,3015)→
  (I9K113,3001)→(WEAP_SYS,3030)`, i.e. missile_power → cplr_distr → sight_power → scho_pwr_b1, all
  writes `1.0` ("on"). `mi-24p-copilot-takeoff.md` reproduces this row order exactly, and
  `test_takeoff_file_reproduces_todays_switch_order` asserts it directly against the real committed
  files (not a synthetic fixture) — a real regression test, not decorative.
- **Intended deviation (R4/D2)**: every row carries `<effector> != on`, evaluated against observed
  readback (Stage 2's job) — correctly makes a second takeoff, a hot start, or a warm air start a
  no-op per-row rather than skipping the whole sequence. This cannot change *first*-takeoff
  behaviour: on a cold start every effector reads "off"/unknown, so every `!= on` condition is true
  and all four rows fire, same as today's unconditional first run. (Stage 2 must still get the
  "unknown is never read as satisfying `!=`" rule right — D3 says so and is Stage 2's job, not
  this stage's; flagging it as the one thing to re-check once the engine lands, not a Stage-1 gap.)
- **OBSERV on/off, weapons arm/safe**: each a single unconditional row, matching
  `write_observ`/`write_weapon_safety`'s single-write-no-sequencing shape. Confirmed by
  `test_observ_and_weapons_files_are_single_unconditional_rows` against the real files.
- **No `petrovich-says` anywhere this cut** — correct; "Guidance unit ready" stays hard-coded on the
  960 edge per R3/D7, untouched by this stage.

### Registry

- **`source_element` names never stripped** — `_resolve_entry` reads `entry.get("source_element")`
  verbatim, no `.strip()`/normalization anywhere in the module. The one real leading-space element
  (`" CONTROL-COVER-PRIORITY-PTR"`) isn't used by any of this cut's six curated entries, but the
  mechanism that would preserve it if it were is present and the switch-reference generator
  explicitly renders a leading space visibly (`_element_name_cell`).
- **Device/cmd/arg collision drops both entries.** Matches the "neither silently wins" posture
  `effector_sequences.load_sequences` already applies to a duplicate `(aircraft, role, trigger)`
  key, and is defensible: there's no principled way for the loader to pick a winner between two
  curated names resolving to the same physical control, and picking one silently would be worse —
  a sequence file author gets a visible "unknown effector" error on the dropped name rather than a
  write happening under a name they didn't expect to be live. Not a required fix; flagging per the
  task brief's instruction to surface it, since "first wins" is the only plausible alternative and
  the plan's text ("drops that entry," singular) doesn't fully settle which was intended.
- **`cplr_distr`'s `unverified = true`.** Still correct to carry: Stage 0d confirmed the *element*
  `WEAP-DISTR-POWER-OP-PTR` exists under that name and resolves cleanly, but whether a write to it
  takes effect in flight is still open (flight question, not a registry-resolution question). The
  flag does nothing mechanical in Stage 1 (no consumer reads `EffectorDef.unverified` yet) — it's
  carried through for a later stage (presumably the Stage 2 startup banner or a sequence-file
  warning) to surface. Worth confirming Stage 2 actually reads it rather than letting it become a
  dead field; not a Stage 1 defect since Stage 1 correctly has no engine to consume it.

### D5 non-fatal posture

- Every content-level failure mode (unresolved `source_element`, missing/empty `values`, bad
  `index`, device/cmd/arg collision, unreadable/unparsable raw-dump or curated TOML) is collected as
  a `RegistryError`/`SequenceError`, never raised — confirmed both by reading `_resolve_entry`/
  `load_registry`/`_load_one_file`/`load_sequences` (no `raise` outside the documented
  `OSError`/`TOMLDecodeError` catch) and by the test suite exercising each case individually with
  real tmp-path fixtures (`test_effector_registry.py`, 11 cases; `test_effector_sequences.py`, 14
  cases plus 3 round-trip tests) — not merely asserting "no exception," each test asserts the
  *other* entries/files still load and the specific error shape.
- **Registry-cascade root-cause loss, as flagged in the task brief**: a catastrophically bad
  raw-dump/curated file collapses to one `RegistryError` naming the real cause, but every sequence
  file then independently reports "unknown effector X" against the empty registry rather than
  pointing back at that cause. `implementation.md` names this tradeoff explicitly and accepts it
  because the one `RegistryError` from `load_registry` itself still carries the real reason and
  both error lists reach the same console banner in Stage 2. This is acceptable **for Stage 1**,
  which has no banner yet to demonstrate the claim against — it is a Stage 2 commitment, not a
  Stage 1 fact, and Stage 2's review should check the banner actually surfaces the registry-level
  error prominently (e.g. first, or distinguished from the per-sequence noise) rather than burying
  it under five near-identical "unknown effector" lines. Not a Stage 1 required fix; flagging as
  the one thing Stage 2's reviewer must re-verify, since the cascade's acceptability was argued
  about a surface that doesn't exist yet.
- Every plan-listed validation rule has its own dedicated test (checked against the plan's "Stage
  1" bullet point by point): unknown effector, unknown value, unknown trigger, malformed row,
  say-only row (reserved), duplicate `(aircraft, role, trigger)` (both files rejected), unresolved
  `source_element`, duplicate triple collision, unreadable TOML (registry side and sequences side),
  plus the full round-trip of each shipped file. No gaps found.

### Switch reference

- Useful to a pilot/author writing a sequence file: grouped by device then seat, element name
  (leading space rendered visibly via `` `name`  _(leading space)_ ``), label, seat with
  explicit/defaulted qualifier, shape, cmds/args/arg-values, and a "Curated as" column that answers
  "can I already reference this" at a glance. The header's "To add a new effector" paragraph is a
  real how-to, not boilerplate.
- **Staleness test is real**, not decorative: `test_switch_reference_matches_the_generator` shells
  out to the actual tool in check mode against the real committed `effectors-raw.toml`/
  `effectors.toml`/`switch-reference.md` and asserts exit 0 — any one of the three files drifting
  from the other two fails CI, the same mechanism `test_tuning_defaults_toml.py` already uses for
  `generate_defaults.py`. Confirmed by inspection that the tool's output is deterministic (sorted by
  device, then seat, then element name) and self-consistent with the file on disk.
- Follows `generate_defaults.py`'s generator convention: static TOML read (no exec), check-mode
  default, `--write` to regenerate, GENERATED header naming source and a sha256 so the reference
  can never silently diverge from the dump it was rendered from.

### Trigger names

`effector_sequences.KNOWN_TRIGGERS = {"takeoff", "observ-on", "observ-off", "weapons-arm",
"weapons-safe"}` matches explore-notes decision 2's trigger set exactly (the plan's "BL-B66 first"
scope: takeoff, observ-on/off, weapons-arm/safe). The module docstring correctly flags itself as
the one place this list is spelled out, which Stage 2's `EffectorTrigger` enum must stay in sync
with — a real seam, not an assertion with nothing behind it (verified: no `EffectorTrigger` exists
yet in this diff, consistent with Stage 2 not having started).

### Pure / no wiring / no new dependency

Confirmed by grep: `effector_registry`/`effector_sequences` are imported nowhere outside
`src/belief/effector_sequences.py` (which imports the registry module) and their own test files.
`logger.py`, `crew_console.py`, `sight_effector.py` are untouched by this diff (checked directly —
only `plan.md`/`explore-notes.md`/`implementation.md` and the new files/tests/memory notes are in
the Stage 1 commit). Both new modules import only `tomllib`, `collections`, `collections.abc`,
`dataclasses`, `pathlib`, `typing`, `re` — stdlib only, no new runtime dependency.

### Required Fixes

None.

### Optional Refinements

- **Device/cmd/arg collision: confirm "drop both" is the intended policy, not "first wins."**
  Defensible as implemented and already flagged in `implementation.md` as a judgment call; worth a
  one-line confirmation from the user before this becomes the precedent for later registries
  (BL-B67, a Mi-8 registry) that may have more collision-prone entries.
- **Stage 2's startup banner should be checked against the registry-cascade tradeoff** described
  above — not fixable now (no banner exists), but worth carrying into the Stage 2 review rather than
  re-discovering the tradeoff from scratch.
- **`EffectorDef.unverified`** has no consumer yet; confirm Stage 2 actually surfaces it somewhere
  (banner, log line, or a sequence-file comment convention) rather than letting it become dead
  data carried for no reader.

### Verdict

APPROVED

### Review Confidence

Full read — plan, explore-notes, implementation.md, both new source modules read in full, both new
test files read in full (test_effector_registry.py completely, test_effector_sequences.py's
definitions list plus its round-trip/parity tests), the curated registry, all five shipped sequence
files, the switch-reference generator and its staleness test, and `sight_effector.py` for parity
comparison. Ran ruff format/check, mypy (src and tools), and the full pytest suite myself in this
worktree against the actual tip commit rather than trusting the implementation report's stated
numbers. Did not re-read the 976-line generated `switch-reference.md` end to end — spot-checked its
header, generator logic, and the device-6/WEAP_SYS section that matters for this cut's six curated
effectors; the rest is machine-generated from already-reviewed (Stage 0) data and guarded by its
own staleness test.
