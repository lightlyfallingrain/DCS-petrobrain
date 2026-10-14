# X-T26 — Make behaviour-affecting constants configurable

Architect pass, 2026-10-14. Brief: `todo/todo/X-T26.md`. Base: `main` @ `6301ec7`.

### Goal

Give every behaviour-affecting constant a declared default in code, a fully-qualified key, and a
generated, self-describing TOML file the pilot can override from — without moving any constant's
value, and without moving its provenance out of the code comment that holds it.

---

## Effort/Value check — read this before Stage 2 is scoped

**The count, measured, not reasoned** (AST over each `src/`, module-level `UPPER_CASE` with a
numeric or table literal; see "How the count was taken" below):

| subproject | module-level consts | public numeric/table | **survives the inclusion test** |
|---|---|---|---|
| body-layer | 313 | 100 | **~95** |
| audio-adapter | 88 | 32 | **~10** |
| world-model | 145 | 33 | **~6** (query path only) |
| aircraft-layer | 59 | 3 | **0** |
| mission-interpreter | 34 | 2 | **0** |
| brain-layer | — | — | 0 (no runtime yet) |

**~111 keys, 85% of them in body-layer.** That is the figure the brief asked for, and it is nearer
150 than 30.

**The value is real but extremely concentrated.** Of those ~111, the set the user would plausibly
touch in a sortie-tuning loop is about **fifteen**: the four `attack_run` gates, the three
`visibility` tier radii, `SPEECH_RATE_WPS`, `INTER_UTTERANCE_GAP_S`, `FOCUS_DWELL_S`,
`IDENTITY_HALF_LIFE_S`, `POSITION_HALF_LIFE_S`, `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS`,
`BEARING_SIGMA_DEG`, `LOST_THRESHOLD_S`. The remaining ~95 are keys nobody will open the file to
change, and each one is a line he has to read past to find the one he wants. A 111-key file is
measurably worse at the stated purpose — *"so that I can change them easily"* — than a 15-key one.

**Recommendation: build the mechanism universally, expose the set incrementally.** Stages 1–2 ship
the loader, the generator and a curated ~15-key set; Stage 3 adds the rest module by module *if he
wants it*, and is cheap and mechanical once the mechanism exists. Marking one more constant tunable
is a one-line edit forever after, so nothing is foreclosed by starting small. This is the difference
between one feature and three.

**This is advice.** If he wants all ~111 exposed, Stage 3 does it; the plan carries it as a stage
rather than refusing it. See Decision 1.

---

### The inclusion test

A constant is **tunable** iff **all five** hold. Stated as a test rather than a sentiment so two
people classify the same constant the same way.

1. **Free parameter.** Moving it to a nearby value leaves the code *correct* — no other constant,
   formula, derivation or data structure must change to stay consistent.
2. **Crew-perceivable.** Its value changes what Petrovich detects, identifies, reports, says, or
   when — something the pilot could notice from the cockpit. Not log format, not a cache grid, not
   an overlay's width.
3. **Not an interface contract.** Not a timeout, port, poll interval, buffer size, sample rate,
   schema version, or any value another process or a Win32 API agrees on.
4. **Has provenance that could change.** It came from a measurement, a judgement or a guess —
   something a sortie could revise. If it is forced by arithmetic or by an external spec, it is not
   a knob.
5. **Public.** No leading underscore. The author's own underscore says "not this module's
   interface"; making it a config key contradicts that marking. A private constant that really is a
   knob gets *renamed public* in the same commit that exposes it — a visible, reviewable promotion,
   not a quiet exception.

**Derived constants are never keys.** Anything whose RHS is an expression over another constant
(`decay.OBSERVED_WINDOW_S = SCAN_CYCLE_PERIOD_S`, `gaze.SCAN_CYCLE_PERIOD_S`,
`optic_policy.OPTIC_RETRY_INTERVAL_S`, `attack_run._SECTOR_HALF_DEG` — 6 in body-layer) stays
derived. Expose the inputs; the derivation is mechanism. This is also what makes `SCAN_PLAN` safe
(below): its coupling to `decay.OBSERVED_WINDOW_S` is already structural, not hand-maintained.

#### The test run against the hard cases

| constant | verdict | why |
|---|---|---|
| `perception/gaze.py:SCAN_PLAN` `(12,11,10,9,12,1,2,3)` | **IN**, array-valued | Passes all five. Its own comment says revisiting the alternative is "a one-table edit"; the apparently-coupled `decay.OBSERVED_WINDOW_S` is *derived from* `SCAN_CYCLE_PERIOD_S`, which is derived from this tuple, so test 1 holds. Arrays replace wholesale, never merge. |
| `belief/position_belief.py` plausible-speed table | **IN**, table-valued, **after promotion** | The canonical behaviour table (BL-12 Stage 2's calibration commit). Fails test 5 today as `_DEFAULT_PLAUSIBLE_SPEED_MPS` + a private per-class map; promoted to public names in the exposing commit. Merges **per entry**; an unrecognised entry key is a startup refusal, so a mistyped class name cannot be silently ignored. |
| `perception/visibility.py:RESOLUTION_ANGULAR_RADIUS_RAD` `0.00128` | **OUT** | Fails test 1 and test 4. It is `7/5440` *rounded down on purpose*, and its comment states the rounding direction is load-bearing: "a threshold derived from an observation must admit that observation, or the derivation is not reproducible from the data it cites." A pilot moving this breaks a derivation rather than expressing a preference. |
| `perception/visibility.py:LOWRES/MEDRES/HIRES_ANGULAR_RADIUS_RAD` | **IN** | Same family, different character: each is a *calibration output* from a photographed tier boundary, and `LOWRES`'s own comment says "the real presence limit is further out than anything tested — a longer ladder would push this down again." Exactly a value a sortie revises. |
| `perception/visibility.py:IFF_ANGULAR_RADIUS_RAD` | **OUT** | Fails test 2 — its comment says "Not used by this module", named only so the table reads complete. A key nothing reads is the precise failure the brief warns about. |
| `belief/callouts.py:SPEECH_RATE_WPS` `2.5` | **IN**, with a lapse note | The paradigm case: "Uncalibrated — needs a live sortie." Gets `status="uncalibrated"` and a sentence in its `#:` block saying it is **retired** when `AC-B6`'s real playback-stopped signal lands. A key with a stated end is better than a key that outlives its premise. |
| `belief/attack_run.py` — `ATTACK_RUN_LINED_UP_AZIMUTH_DEG`, `_ELEVATION_GATE_DEG`, `_CHANGE_THRESHOLD_DEG` | **IN**, highest priority | Declared agreed guesses a sortie is meant to set; today setting one means editing `attack_run.py`. These are why the item exists. `status="agreed-guess"`. |

Three further rulings the test produces, each removing work:

- **aircraft-layer is out of scope entirely.** Its 3 public numeric constants are a line-length
  cap, a Win32 joystick decode floor and a device switch threshold — transport and device decoding,
  nothing that changes what Petrovich does or says (test 2/3). It also runs on the Windows box,
  where a config file is one more thing to deploy. **No stage.**
- **world-model's build pipeline is out of scope; its query path is in.** The 22 build constants
  change the *built artefact*, not runtime behaviour, most are already `DEFAULT_*` CLI arguments,
  and acting on one means a multi-hour theatre rebuild — a tuning loop the pilot cannot run. The
  handful read at runtime through the body↔world-model in-process seam are in:
  `query/line_of_sight.py:TERRAIN_TOLERANCE_M` (12.0 — directly decides whether Petrovich sees a
  contact; promoted from `_`), `query/divides.py:DIVIDE_MERGE_M`, and `query/describe.py`'s two
  radii. ~6 keys, not 22.
- **mission-interpreter and brain-layer: no stage.** Nothing runs yet.

---

### Where provenance lives — the authority question

**The code comment is the authority. Nothing moves, nothing is duplicated.**

Those `#:` blocks are not decoration: `SYSTEMATIC_BIAS_FRACTION`'s "keeps a heavily-observed contact
converging on a wrong, confidently-held position", `BEARING_SIGMA_DEG`'s "models the crewman's own
pointing precision, not anything DCS reports … the load-bearing claim is the *ratio*", the
`LOWRES` derivation chain. They are 10–18 lines each and cannot survive as a config one-liner.
body-layer already carries 2554 `#:` lines; the convention exists and is good.

**So the config file is generated from the code, never hand-written.** Drift is then impossible by
construction rather than by discipline:

- **Each tunable constant's declaration carries its own machine-readable facts** — key, default,
  sanity bounds, calibration status — as arguments to the loader call. One source of truth per
  fact, readable at runtime by `--print-tuning` and by the generator alike.
- **The short description is the first sentence of the constant's `#:` block**, lifted by the
  generator from the source. Verified against the real comments: it yields usable one-liners for
  `RANGE_FRACTIONAL_SIGMA`, `BEARING_SIGMA_DEG`, `SYSTEMATIC_BIAS_FRACTION` and `FOCUS_DWELL_S`
  unchanged.
- **Every generated entry carries a `source:` pointer** (`perception/estimation.py:BEARING_SIGMA_DEG`)
  so the full reasoning is one grep away. The file's own header says the code comment is
  authoritative and that the file is generated.
- **A test fails if the generated file is stale.** `test_defaults_toml_matches_code` regenerates in
  memory and compares. A calibration commit that forgets to regenerate fails CI; it cannot drift
  silently.

**Three constants in scope have no `#:` block of their own** — `MEDRES`/`HIRES_ANGULAR_RADIUS_RAD`
share `LOWRES`'s block. The implementer writes one each. That is a real readability fix, not scope
creep, and it is the only place the generator's rule needs manual help.

**Calibration status is the field the pilot most needs**, and it is what tells him whether a number
is worth fiddling with. One of `measured` / `derived` / `judgement` / `agreed-guess` /
`uncalibrated`, rendered as a comment on every key.

---

### Mechanism

**Format: TOML, read with `tomllib`.** Stdlib since 3.11 and every subproject is `>=3.11`, so the
stdlib-only policy in `body-layer/`, `aircraft-layer/` and `world-model/CLAUDE.md` is satisfied with
**zero new dependencies**. JSON is disqualified outright — it has no comments, and the descriptions
*must* live in the file. YAML would be a dependency. We only ever read, never write, so `tomllib`'s
read-only nature costs nothing.

**Two files per subproject, one generated, one the pilot's:**

| path | written by | committed |
|---|---|---|
| `<subproject>/config/defaults.toml` | the generator | yes — this is the documented default file the user asked for |
| `<subproject>/config/tuning.toml` | the pilot, by hand | **no**, gitignored, absent by default; sparse — only keys he changed |

**Defaults live in code, at the constant.** The generated file is a *rendering*, never the
authority. Three reasons: existing pinning tests (`test_groups.py::test_constants_are_the_stated_
assumptions`) assert module-level values and must keep working; every subproject must run with no
config file at all (module independence, and the Windows box); and a generated file that were also
the source would make the generator circular. Keeping the literal at the constant is also what
preserves "mechanism and calibration never share a commit" unchanged — see below.

**Declaration shape** (one line per constant, the `#:` block above it untouched):

```python
#: Cross-range (perpendicular to line-of-sight) 1-sigma bearing error,
#: degrees. **Not measured, cannot be** -- it is the crewman's own pointing
#: ... (18 existing lines, unchanged) ...
BEARING_SIGMA_DEG: Final[float] = tuning.real(
    "perception.estimation.BEARING_SIGMA_DEG", 3.0, lo=0.1, hi=30.0, status="judgement"
)
```

Key is the **fully-qualified module path plus the constant's own name**, so the TOML maps 1:1 onto
the code and the pilot can find any key by grep. TOML tables fall out naturally:

```toml
[perception.estimation]
# Cross-range (perpendicular to line-of-sight) 1-sigma bearing error, degrees.
# status: judgement | range: 0.1 .. 30.0
# source: perception/estimation.py:BEARING_SIGMA_DEG
BEARING_SIGMA_DEG = 3.0
```

**Composition.** Scalars: the override replaces the default. Tables: merge **per entry**, unknown
entry keys refused. Arrays: replace wholesale.

**Why the value is resolved at import, and why that is the only workable choice.** The alternative —
load config, then `setattr` the module globals — **is broken here**, not merely inelegant.
body-layer binds constants by value at import time (`from belief.decay import OBSERVED_WINDOW_S` in
`contacts.py`; `from eyesight_view import DEFAULT_MAX_LINES as …` in `logger.py`), so a later
`setattr` on the defining module never reaches the importer. Resolving at the declaration makes
import order irrelevant: whichever tunable module imports first triggers the single file read, every
later module sees the same cached mapping, `from X import CONST` keeps working, the constants stay
`Final` module-level scalars, and the pinning tests are untouched.

**The file path comes from an environment variable, `PETROBRAIN_TUNING`, not a CLI flag.** This is
forced by the same fact: constants resolve during *import*, and `argparse` in `main()` runs after
every import has completed, so a `--tuning PATH` flag would be parsed too late to have any effect —
and would fail *silently*, which is the exact defect this feature exists to prevent. The env var is
read at the loader's first use, i.e. during import, and is trivially scriptable into the run command
documented in `aircraft-layer/WORKFLOW.md`. **No implicit path**: with the variable unset nothing is
read, so tests, CI and a fresh clone cannot be perturbed by a file someone left in `config/`.
See Decision 2.

---

### Failure behaviour

A silently-ignored bad value is worse than no feature, so **every bad input refuses to start**, and
the one non-error case is the one that is genuinely normal.

| case | behaviour | why |
|---|---|---|
| `PETROBRAIN_TUNING` unset | run on code defaults, one INFO line: `tuning: no override file (PETROBRAIN_TUNING unset)` | The normal case — tests, CI, Windows, fresh clone. |
| file named but missing/unreadable | **refuse to start**, naming the path | He named a file. If it is not there, he is tuning nothing. |
| key absent from the file | code default, silently | The file is *sparse by design* — he copies out the handful of lines he wants. This is not an error and must not warn, or the normal case is drowned in noise. |
| **key not in `defaults.toml`** (misspelled, renamed, stale) | **refuse to start**: unknown key, the file and line, and the nearest known key by edit distance | The central case. Validated against the committed `defaults.toml`, which is the complete registry — *not* against whatever happens to have been imported, so there is no import-order dependency. |
| wrong type | **refuse to start**: key, expected, got | TOML is typed. An `int` is accepted where a float is wanted (`30` for `30.0`); a float is **rejected** for an int key rather than truncated. |
| out of declared `lo`/`hi` | **refuse to start**: key, value, bounds | Bounds are *sanity* bounds (an angle in 0–180, a half-life > 0), declared at the constant where the author's knowledge is. They are not taste bounds and must not be used to express a preferred range. |
| table entry key unrecognised | **refuse to start**, naming the entry and the valid set | A mistyped op-class in the plausible-speed table would otherwise be a no-op. |

**Where the refusal is visible.** It is not a warning and it is not mid-flight. Each affected
process is launched from a terminal *before* the sortie — body-layer's `logger.py` and
audio-adapter's server, both on the Mac. The process exits non-zero with one line on stderr, in
front of the person who just typed the command. There is no case where a config error surfaces in
the cockpit, because the file is read once, at import, before anything flies. This is also the
argument for the next decision.

A deliberate non-goal: **no warning channel into the cockpit.** `--overlay` and Petrovich's voice
exist, but routing a config complaint through them would make the crew layer report on its own
plumbing, and the pilot cannot act on it while flying anyway.

### Load timing — startup only

Three reasons, not just "probably right":

1. **A mid-sortie reload would be a lie.** Every constant resolves at module import. Re-reading the
   file without re-importing would change the mapping and nothing else; the pilot would see the new
   value in `--print-tuning` and the old behaviour in the cockpit.
2. **Belief state is temporally integrated.** Half-lives, decay ladders, confirm windows and
   hysteresis accumulate history. Change `POSITION_HALF_LIFE_S` at minute twelve and every live
   contact carries decay computed under the old value — the observed behaviour is neither setting's.
   An A/B comparison across a reload would be uninterpretable, which defeats the point of tuning.
3. **The restart loop is already seconds.** Restarting body-layer between sorties is the existing
   workflow; mid-sortie reload buys a convenience that costs interpretability.

---

### Verifying a changed value took effect

This is the feature's whole purpose and the easiest thing to ship broken, so it gets its own
mechanism rather than being inferred from behaviour.

- **Startup logs every override applied**, one line per key: `tuning: perception.estimation.
  BEARING_SIGMA_DEG 3.0 -> 5.0 (judgement)`, then a count. An empty list where he expected changes
  is visible in the first second, not inferred from a sortie.
- **`--print-tuning`** on each entrypoint dumps every registered key's **resolved** value, default,
  status and source, then exits 0. This is the mechanical answer to "did it take effect": resolved
  values, not file contents. The flag is safe as a flag (unlike the path) because it only reads the
  already-resolved registry.
- **Keep two questions apart.** *Was it applied?* is answered by the two mechanisms above and by
  tests — never by a sortie. *Is the new value better?* is the only question a sortie answers.
  Conflating them is how this ships broken: a sortie that shows no change proves nothing unless the
  value is known to have been read.

**Tests decide**: that an override reaches the constant (a subprocess with `PETROBRAIN_TUNING` set
to a temp file, asserting the module attribute); each refusal case above; that `defaults.toml` is
not stale; that no in-scope constant changed value during conversion (see Stage constraint).
**A sortie decides only**: whether the exposed set is the right ~15, and the three `attack_run`
gates' real values — which this feature does not touch.

---

### Affected Modules / Files

- `body-layer/src/tuning.py` — **new.** Loader, registry, `real`/`whole`/`fraction`/`table`/
  `sequence` accessors with `lo`/`hi`/`status`, `PETROBRAIN_TUNING` read-once, override log,
  `print_tuning()`.
- `body-layer/tools/generate_defaults.py` — **new.** AST + source scan: registry facts from the
  `tuning.*` call, description from the first sentence of the `#:` block, writes
  `config/defaults.toml`.
- `body-layer/config/defaults.toml` — **new, generated, committed.**
- `body-layer/src/logger.py` — `--print-tuning`; `tuning.validate_against_defaults()` at the top of
  `main()`.
- `body-layer/src/belief/attack_run.py`, `perception/visibility.py`, `belief/callouts.py`,
  `perception/gaze.py`, `belief/decay.py` — Stage 2's curated set, one literal → one `tuning.*` call
  each, `#:` blocks untouched except the three missing ones.
- Stage 3 (if taken): `belief/{groups,contacts,crew_console,optic_policy,voice_commands,enrichment,
  events,position_belief,mission_phase,cardinality,classification,association_over_time,speech,
  tools}.py`, `perception/{estimation,association,motion,group_salience,naked_eye_source,
  object_model,hybrid_source}.py`.
- `audio-adapter/src/tuning.py`, `tools/generate_defaults.py`, `config/defaults.toml` — Stage 4,
  **a copy, deliberately.** No cross-subproject import: `CLAUDE.md` names body↔world-model as the
  sole exception and says not to add another. ~70 duplicated lines is the stated price.
- `world-model/src/tuning.py` + the 4 query-path constants — Stage 5.
- `.gitignore` — `*/config/tuning.toml`.
- `body-layer/CLAUDE.md`, `audio-adapter/CLAUDE.md`, `world-model/CLAUDE.md` — how to tune, and the
  `PETROBRAIN_TUNING` variable in the run command.
- `todo/todo/X-T26.md` — mark `[~]`, then `[x]`.

### Implementation Plan

1. **Stage 1 — mechanism only, body-layer. No constant converted, no observable at all.**
   `tuning.py` + `--print-tuning` + `validate_against_defaults()`, an empty `config/defaults.toml`,
   the generator, `.gitignore`. Every failure case above covered by a test. Behaviour bit-identical
   by construction: nothing calls the loader yet.
2. **Stage 2 — the curated set, and the first thing the pilot can actually do.** ~15 keys: the four
   `attack_run` gates, the three tier radii, `SPEECH_RATE_WPS`, `INTER_UTTERANCE_GAP_S`,
   `FOCUS_DWELL_S`, `SCAN_PLAN`, `IDENTITY_HALF_LIFE_S`, `POSITION_HALF_LIFE_S`,
   `LOST_THRESHOLD_S`, `BEARING_SIGMA_DEG`. Write the three missing `#:` blocks. Generate and commit
   `defaults.toml`; add the staleness test. **Observable: an attack-run gate changes without a code
   edit.** This stage alone satisfies the item's motivating case and is a sensible stopping point.
3. **Stage 3 — the remaining ~80 body-layer keys, one commit per module.** Purely mechanical;
   reviewable in chunks; promotes the plausible-speed table to public names. Gated on Decision 1.
4. **Stage 4 — audio-adapter's ~10.** **Sequenced after `AA-B5`** (see below).
5. **Stage 5 — world-model's 4 query-path keys**, with the build-pipeline exclusion written into
   `world-model/CLAUDE.md` so it is a decision on record rather than an omission.
6. **Docs + roadmap.** `CLAUDE.md` tuning sections; `X-T26` closed with the inclusion test quoted so
   the next constant added has a rule to apply.

**Stage constraint, every stage:** *no constant's value changes.* Converting a literal to a
`tuning.*` call with the same default is a **mechanism** commit. A full `pytest` run must pass
unchanged after each one — and per `implementer/project_bl12_stage2_growth_rate.md`, run the *whole*
suite, not the touched module's, because a test can move from a value change without ever naming the
constant. If a suite goes red after a conversion, the conversion changed a value; fix the
conversion, never the test.

### How "mechanism and calibration never share a commit" gets easier

The rule survives unchanged, and the feature sharpens it three ways:

- The default stays a literal at the constant, so a calibration commit is still exactly one literal
  in one file — plus one regenerated line in `defaults.toml`, which makes the calibration *more*
  visible in the diff, not less.
- The staleness test turns "forgot to regenerate" from silent drift into a red CI run.
- `status=` makes the two commit kinds mechanically distinguishable: a mechanism commit may add or
  move a `tuning.*` call but never touches a default or a status; a calibration commit touches a
  default and usually moves its status (`agreed-guess` → `measured`) and nothing else.

### `AA-B5` ordering

**X-T26 Stages 1–3 land first; `AA-B5` next; X-T26 Stage 4 after it.**

`INTER_UTTERANCE_GAP_S` is a body-layer constant *today*, so Stage 2 exposes it as a body-layer key
with no coordination needed. `AA-B5` then moves the gap into the audio path, and **inherits the
loader rather than inventing a mechanism** — its migration becomes one commit that deletes the
body-layer key and adds the audio-adapter one, so the two-gaps-compose risk its own entry calls
"the whole of the migration risk" is visible in a single diff instead of spread across two config
files. Doing Stage 4 first would invert this: `AA-B5` would then have to move a *key* as well as a
constant, across subprojects, with a window in which both files define a gap.

`SPEECH_RATE_WPS` is the same shape and gets the same treatment: exposed now with
`status="uncalibrated"` and a sentence in its `#:` block saying `AC-B6`'s real playback-stopped
signal retires it. A key with a declared end does not outlive its premise.

### Risks & Unknowns

- **`Final` with a non-literal RHS loses literal-type narrowing.** `Final[float] = tuning.real(...)`
  is fine, but an `int` constant used in a `Literal[...]` or overload position may not type-check
  under `mypy --strict`. Mitigation: convert numerics first, and if a site needs the literal type,
  that constant stays OUT (fails test 1 anyway — it is part of a type contract).
- **Import-order correctness is the real hazard, and the env var is the mitigation.** If a future
  change reads the path from `argparse` instead, every override becomes a silent no-op. Put this in
  `tuning.py`'s module docstring as a lapse condition, not just in this plan.
- **`validate_against_defaults()` is the only guard against a misspelled key, and it is one call.**
  If it is omitted from a new entrypoint, that entrypoint accepts typos silently. Mitigation: the
  loader refuses to resolve anything until it has been called — so forgetting it fails loudly at
  startup rather than quietly at tuning time.
- **A developer who exports `PETROBRAIN_TUNING` in their shell changes their own test runs.** No
  implicit path protects CI and fresh clones but not a global export. Note it in `CLAUDE.md`.
- **~111 keys is a file the pilot reads past.** The curated-set recommendation is the mitigation; if
  Stage 3 is taken in full, `defaults.toml` should be split per top-level package so the file he
  opens is the one he wants.
- **Table-valued keys are the least-tested path** and the one where a typo matters most; the
  unrecognised-entry refusal is what makes them safe, so it is a required test, not a nice-to-have.
- **Performance: nil, and stated here so the performance pass is short.** One file read and one dict
  lookup per constant, all at import, zero per-tick cost. No hot path is touched.

### Second-order effect

This **unblocks** the "declared agreed guess" pattern as a first-class thing a sortie can close
without a code commit — `BL-14`'s three gates are the first instance and `BL-B64` (9K113) will
produce more. It makes the acceptance-card loop materially cheaper: a test card can name a key, a
value and an env var instead of a file and a line number, so the user can run two settings in one
evening without a rebuild or a branch. It **complicates** one small thing permanently: every new
constant in a converted module now carries an in/out decision, and the staleness test fails if the
generator is not rerun — a recurring tax that is exactly the price of a file that never drifts.

### Decisions Requiring User Input

1. **Curated ~15 now, or all ~111?** Recommendation: Stages 1–2 only for this feature (~15 keys,
   the ones a sortie actually revises), with Stage 3 available as a follow-up. A 111-key file is
   worse at *"change them easily"* than a 15-key one, and nothing is foreclosed — marking one more
   constant tunable is a one-line edit forever after. **This is the decision that sets whether this
   is one feature or three.**
2. **`PETROBRAIN_TUNING=<path>` in the run command, rather than a `--tuning` flag.** Not a
   preference — a flag is parsed after the constants have already resolved and would fail silently.
   Confirming it means one more variable in the command he types. If he would rather have a flag,
   the mechanism has to change shape (a two-phase import), which is materially more expensive.
3. **world-model's 22 build-pipeline constants stay out of scope** (offline, already CLI arguments,
   acting on one costs a multi-hour theatre rebuild), leaving only ~4 runtime query-path keys.
   Confirm, and it goes into `world-model/CLAUDE.md` as a recorded decision.
4. **Refuse to start on any bad value** — misspelled key, wrong type, out of range. Recommended, and
   low-risk: the affected processes launch from a terminal on the Mac before the sortie, never
   mid-flight, and aircraft-layer on the Windows box gets no config file at all.

---

### How the count was taken

`ast` over each subproject's `src/**/*.py`, collecting module-level `Assign`/`AnnAssign` to
`UPPER_CASE` names, classified by RHS kind (numeric literal / table / derived expression / string /
other), then filtered by the inclusion test's public rule and its interface-contract exclusions.
Scripts in `/tmp`, not committed — rerunnable in ten lines. The per-subproject figures in the
Effort/Value table are the output of that pass, not an estimate; the "survives the inclusion test"
column is a hand classification of the public numeric/table list against the five criteria and is
the one column with judgement in it (±5).
