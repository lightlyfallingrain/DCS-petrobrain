# X-T26 — Make behaviour-affecting constants configurable

Architect pass, 2026-10-14. Brief: `todo/todo/X-T26.md`. Base: `main` @ `6301ec7`.

**Amendment, 2026-10-15**: the four open decisions resolved. Decisions 1–3 accepted as
recommended (curated ~15, `PETROBRAIN_TUNING` env var, world-model build pipeline out of scope).
**Decision 4 reversed**: bad values warn and continue on the code default rather than refusing to
start — see "Decision 4 REVISED" and the rewritten "Failure behaviour" section. One new open
sub-decision, 4a (missing/unreadable named file).

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
`visibility` tier radii, `SPEECH_RATE_WPS`, `INTER_UTTERANCE_GAP_S`, `FOCUS_DWELL_S`, `SCAN_PLAN`,
`IDENTITY_HALF_LIFE_S`, `POSITION_HALF_LIFE_S`, `LOST_THRESHOLD_S`, `BEARING_SIGMA_DEG` — the exact
list in Stage 2 below, which is the canonical one; this sentence is kept in sync with it rather than
carrying its own enumeration. The remaining ~95 are keys nobody will open the file to change, and
each one is a line he has to read past to find the one he wants. A 111-key file is measurably worse
at the stated purpose — *"so that I can change them easily"* — than a 15-key one.

**Accepted** (user decision, 2026-10-15). See Decision 1.

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
| `belief/position_belief.py` plausible-speed table | **IN**, table-valued, **after promotion** | The canonical behaviour table (BL-12 Stage 2's calibration commit). Fails test 5 today as `_DEFAULT_PLAUSIBLE_SPEED_MPS` + a private per-class map; promoted to public names in the exposing commit. Merges **per entry**; an unrecognised entry key warns and leaves that entry at its code default (Decision 4 REVISED) rather than refusing to start, so a mistyped class name is a reported no-op, not a silent one and not a crash. |
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
  radii. ~6 keys, not 22. **Accepted** (user decision, 2026-10-15). See Decision 3.
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

**Composition.** Scalars: the override replaces the default. Tables: merge **per entry**, an unknown
entry key is rejected (warn, that entry stays at its code default — Decision 4 REVISED). Arrays:
replace wholesale.

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
**Accepted** (user decision, 2026-10-15). See Decision 2.

---

### Failure behaviour

> **REVISED** (user decision, 2026-10-15) — see **Decision 4 REVISED** below. The design in this
> section implements the revision: **every bad *value* warns and continues on the code default; no
> bad value refuses to start.** The original design — *"every bad input refuses to start"* — is kept
> immediately below the table it governed, struck through in effect by this note, because the
> reasoning in it (bounds are sanity bounds, not taste bounds; a mistyped table entry would
> otherwise be a silent no-op) still holds and still shapes *what counts as bad*, even though the
> consequence of being bad has changed.

A silently-ignored bad value is still worse than no feature. What changed is *how* it stops being
silent: not by refusing to start, but by making every rejection impossible to miss at startup and
on demand — see "Making a rejection visible" below. **The one genuinely fatal case is the named
file not existing at all**, and even that is an open sub-decision (4a) rather than settled by this
revision; everything else degrades to the code default and is reported, never silently absorbed.

| case | behaviour | why |
|---|---|---|
| `PETROBRAIN_TUNING` unset | run on code defaults, one INFO line: `tuning: no override file (PETROBRAIN_TUNING unset)` | The normal case — tests, CI, Windows, fresh clone. Unchanged. |
| file named but missing/unreadable | **recommend: still refuse to start**, naming the path — see **Decision 4a**, open | He named a file and none of its overrides can be read, so *100%* of what he meant to tune is silently absent — categorically different from one bad key inside a file that mostly loaded. Named as the one place "warn and continue" produces a worse outcome than refusing: a sortie flown entirely on defaults while he believes he changed something. |
| key absent from the file | code default, silently | Unchanged. The file is *sparse by design* — he copies out the handful of lines he wants. Not an error, never warned, or the normal case is drowned in noise. |
| **key not in `defaults.toml`** (misspelled, renamed, stale) | **warn and continue**: code default stays in force; rejection logged with the key, the file and line, the nearest known key by edit distance, and the value actually in force | Validated against the committed `defaults.toml`, the complete registry — *not* against whatever happens to have been imported, so there is no import-order dependency. A typo means **a knob he set is doing nothing** — the value in force is simply the default, unaffected by whatever he typed. |
| wrong type | **warn and continue**: code default stays in force; rejection logged with key, expected type, got type/value | TOML is typed. An `int` is accepted where a float is wanted (`30` for `30.0`); a float is still a type mismatch for an int key, not truncated — rejected and defaulted, not silently coerced. |
| out of declared `lo`/`hi` | **warn and continue**: code default stays in force; rejection logged with key, the out-of-bounds value, and the bounds | Bounds are *sanity* bounds (an angle in 0–180, a half-life > 0), declared at the constant where the author's knowledge is — not taste bounds. An out-of-range value means **a knob he set is doing something he did not ask for** had it been applied; defaulting instead of clamping avoids silently substituting a third value (the clamped one) that he typed neither. |
| table entry key unrecognised | **warn and continue**: that entry stays at its code default, the rest of the table's valid entries still apply; rejection logged naming the entry and the valid set | Composition is per-entry (unchanged), so one mistyped op-class in the plausible-speed table no longer makes the *whole table* fail — it makes that one entry a no-op, reported as such. |

**The typo/out-of-range distinction is semantic, not procedural — both resolve to "warn and keep
the default," but the rejection *reason* must say which kind it was**, because the two mean
different things to the pilot: a typo means his edit did nothing; an out-of-range value means his
edit was about to do something he probably did not intend. The reason text in every case above
carries that distinction (see "Making a rejection visible").

---

#### Making a rejection visible (this replaces the exit code as the compensating mechanism)

Refusing to start used to be the mechanism that made a bad value impossible to miss. Warn-and-
continue removes that mechanism, so a replacement is not optional — it is what makes this revision
safe rather than merely milder. Two parts, both required, because they answer two different
questions (see "Verifying a changed value took effect" below, which this reuses rather than
duplicates):

1. **One startup block, not interleaved with ordinary log lines.** Printed once, after the loader
   has resolved every tunable module that has been imported and `validate_against_defaults()` has
   checked the file against the full `defaults.toml` registry:

   ```
   === Petrobrain tuning (PETROBRAIN_TUNING=/home/pilot/tuning.toml) ===
   applied (2):
     belief.attack_run.ATTACK_RUN_LINED_UP_AZIMUTH_DEG: 10.0 -> 7.0 (agreed-guess)
     perception.estimation.BEARING_SIGMA_DEG: 3.0 -> 5.0 (judgement)
   rejected (2) -- code default is in force for these:
     belief.attack_run.ATTACK_RUN_ELEVATIO_GATE_DEG: unknown key
       (did you mean belief.attack_run.ATTACK_RUN_ELEVATION_GATE_DEG? default 12.0 in force)
     perception.visibility.HIRES_ANGULAR_RADIUS_RAD: 0.9 out of range [0.0, 0.2]
       (default 0.0021 in force)
   ===============================================================
   ```

   An empty `rejected` line reads as confirmation, not absence of information — he does not have to
   infer "no news is good news" from silence, which was exactly the failure mode a scrolled-past
   warning would have had.

2. **`--print-tuning` dumps the same `applied`/`rejected` classification, plus every key that is
   simply at its default, and exits 0.** This is unchanged from the original design in shape, widened
   in content: it was already specified as the mechanical answer to "did it take effect," and a
   rejection is now itself part of that answer — "it did not, and here is why" is as answerable
   without flying as "it did."

Both read from the same `Resolution` object the loader already has to build to print the startup
block, so there is exactly one place that classifies a key, not two that could disagree.

**Where it is visible.** Same as the original design's reasoning for refusing to start, carried
over unchanged: each affected process is launched from a terminal *before* the sortie —
body-layer's `logger.py` and audio-adapter's server, both on the Mac — in front of the person who
just typed the command. The startup block is the first thing printed after any ordinary startup
logging, not mixed into it. There is still no case where a config error surfaces in the cockpit;
the file is read once, at import, before anything flies. The deliberate non-goal from the original
design stands unchanged: **no warning channel into the cockpit** — `--overlay` and Petrovich's
voice exist, but routing a config complaint through them would make the crew layer report on its
own plumbing, and the pilot cannot act on it while flying anyway.

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
mechanism rather than being inferred from behaviour — and warn-and-continue (Decision 4 REVISED)
makes this section carry *more* weight than it did under refuse-to-start, not less: there is no
longer a non-zero exit to fall back on as evidence that something was wrong.

- **The startup block** (see "Making a rejection visible" above) is the primary mechanism: every
  `applied` key with old → new value and status, and every `rejected` key with its reason and the
  default now in force. An empty `rejected` section is itself informative — confirmation, not
  silence.
- **`--print-tuning`** on each entrypoint dumps the same classification — every registered key's
  resolved value, default, status, source, and (if rejected) the reason — then exits 0. This is the
  mechanical answer to "did it take effect": resolved values, not file contents. The flag is safe as
  a flag (unlike the path) because it only reads the already-resolved registry.
- **Keep two questions apart.** *Was it applied?* is answered by the two mechanisms above and by
  tests — never by a sortie. *Is the new value better?* is the only question a sortie answers.
  Conflating them is how this ships broken: a sortie that shows no change proves nothing unless the
  value is known to have been read. Under warn-and-continue this matters more than it did: a key
  that was rejected and a key that was never touched both produce "the default value is in force,"
  and only the startup block or `--print-tuning` distinguishes them.

**Tests decide**: that an override reaches the constant (a subprocess with `PETROBRAIN_TUNING` set
to a temp file, asserting the module attribute); **that every rejection case (unknown key, wrong
type, out of range, unrecognised table entry) leaves the code default in force at the constant
itself** — not merely that a warning was logged, since the warning and the value are two different
claims and only the second is the one that can silently drift; that each rejection is classified
correctly (typo → nearest-match suggestion, out-of-range → bounds shown) so the pilot is told which
of the two he has, per the distinction in "Failure behaviour"; that the startup block and
`--print-tuning` agree with each other and with the `Resolution` object (one source, two renderings,
asserted equal rather than independently re-derived); that `defaults.toml` is not stale; that no
in-scope constant changed value during conversion (see Stage constraint); and, if Decision 4a keeps
the missing-named-file case fatal, that it alone exits non-zero while every other bad-value case
exits 0.
**A sortie decides only**: whether the exposed set is the right ~15, and the three `attack_run`
gates' real values — which this feature does not touch.

---

### Affected Modules / Files

- `body-layer/src/tuning.py` — **new.** Loader, registry, `real`/`whole`/`fraction`/`table`/
  `sequence` accessors with `lo`/`hi`/`status`, `PETROBRAIN_TUNING` read-once, a `Resolution` object
  (applied/defaulted/rejected, each entry's reason for rejection), the startup block renderer,
  `print_tuning()`. **`validate_against_defaults()` survives unchanged in what it checks** — the
  file against the full `defaults.toml` registry, independent of import order — **but changes
  contract**: it returns classifications into the `Resolution` instead of raising, except for the
  one case Decision 4a leaves open (named file missing/unreadable), where it still raises if that
  decision keeps it fatal.
- `body-layer/tools/generate_defaults.py` — **new.** AST + source scan: registry facts from the
  `tuning.*` call, description from the first sentence of the `#:` block, writes
  `config/defaults.toml`.
- `body-layer/config/defaults.toml` — **new, generated, committed.**
- `body-layer/src/logger.py` — `--print-tuning`; `tuning.validate_against_defaults()` at the top of
  `main()`, printing the startup block from its `Resolution`.
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
3. **Stage 3 — optional, deferred follow-up, not part of this feature's committed scope (Decision
   1): the remaining ~80 body-layer keys, one commit per module, only if he asks for it later.**
   Purely mechanical — one literal → one `tuning.*` call, same shape as Stage 2 — and reviewable in
   chunks; promotes the plausible-speed table to public names. **Stays a stage in this same plan
   rather than a separate plan document**: the mechanism it uses is already built and reviewed by
   Stage 1, the inclusion test it applies is already settled, and a repetitive one-line-per-constant
   conversion does not need its own Architect pass — it needs a module name and a day. A separate
   plan would be overhead with nothing left to decide.
4. **Stage 4 — audio-adapter's ~10.** **Sequenced after `AA-B5`**, and does not depend on whether
   Stage 3 is ever taken (see below).
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

**Still holds under the reduced scope, and the reduction makes the dependency tighter rather than
looser: X-T26 Stages 1–2 land first; `AA-B5` next; X-T26 Stage 4 after it. Stage 3 (now optional,
see above) is irrelevant to this ordering either way, since `INTER_UTTERANCE_GAP_S` is in the
curated 15 and is exposed by Stage 2, not Stage 3.**

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
- **`validate_against_defaults()` is the only guard against a misspelled key, and it is one call —
  and under Decision 4 REVISED, a louder guard matters more, not less, since there is no exit code
  left to notice its absence by.** If it is omitted from a new entrypoint, that entrypoint accepts
  typos *and prints no startup block at all*, so the silence looks identical to "no overrides" and
  "the check never ran" at once. Mitigation unchanged in mechanism, strengthened in consequence: the
  loader refuses to resolve anything until it has been called, so forgetting it still fails loudly
  at startup (an exception on first constant access) — it is only a *bad value inside a file that
  loaded* that now degrades instead of exiting, never the check's own absence.
- **Warn-and-continue's one new hazard: a rejected value and a never-set value are indistinguishable
  at the constant itself**, both being the code default. The startup block and `--print-tuning` are
  the only place the distinction exists, so if either is skipped or not read, "I changed this" and
  "I did not" collapse into the same observed behaviour. This is the risk the original refuse-to-
  start design eliminated structurally and the revision reintroduces deliberately — see Decision 4
  REVISED for why the user chose it anyway.
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

### Decisions

1. **Curated ~15 now, or all ~111? — SETTLED (user decision, 2026-10-15): curated ~15.** Stages 1–2
   only for this feature (~15 keys, the ones a sortie actually revises), with Stage 3 available as
   an optional, deferred follow-up that stays a stage in this plan rather than a separate document.
   A 111-key file is worse at *"change them easily"* than a 15-key one, and nothing is foreclosed —
   marking one more constant tunable is a one-line edit forever after.
2. **`PETROBRAIN_TUNING=<path>` in the run command, rather than a `--tuning` flag — SETTLED (user
   decision, 2026-10-15): the environment variable.** Not a preference — a flag is parsed after the
   constants have already resolved and would fail silently. One more variable in the command he
   types.
3. **world-model's 22 build-pipeline constants stay out of scope — SETTLED (user decision,
   2026-10-15): confirmed out.** Offline, already CLI arguments, acting on one costs a multi-hour
   theatre rebuild; only ~4 runtime query-path keys are in scope. Recorded in `world-model/CLAUDE.md`
   as part of this feature's docs stage.

4. ~~**Refuse to start on any bad value** — misspelled key, wrong type, out of range. Recommended,
   and low-risk: the affected processes launch from a terminal on the Mac before the sortie, never
   mid-flight, and aircraft-layer on the Windows box gets no config file at all.~~
   **→ Superseded by Decision 4 REVISED, below.**

### Decision 4 REVISED (user decision, 2026-10-15)

**Bad values warn and continue on the code default. They do not refuse to start.** This reverses
the architect's recommendation directly above, which was sound on its own terms — the affected
processes launch from a terminal before the sortie, never mid-flight, so a refusal was always going
to be seen by someone who could act on it immediately — but the user's own priority is different:
a tuning loop that refuses to start on the first typo is a tuning loop he stops trusting, and the
cost of a silently-defaulted value is one he judged smaller than the cost of a process that will
not come up.

**This does not reopen the risk the original recommendation was written to close** — a silently-
ignored bad value — because the failure mode specifically guarded against is *silence*, and the
revision's compensating mechanism (the startup block, `--print-tuning`; see "Making a rejection
visible" in Failure behaviour) makes every rejection as visible as a refusal was, without stopping
the process. What the revision gives up is the *forcing function*: a refusal makes the rejection
impossible to not notice before the sortie; a warning makes it possible to miss if the startup
block scrolls past unread. That is the residual risk recorded two paragraphs above in Risks &
Unknowns, and it is accepted, not eliminated.

**Sub-decision needed — Decision 4a, open:** does the one case that is not "a bad value inside a
file that mostly loaded" — **the named file itself missing or unreadable** — still refuse to start?
**Recommendation: yes.** A misspelled key or an out-of-range value leaves the rest of a working file
in force; a missing file leaves *nothing* in force, so continuing on 100% defaults is a materially
different outcome from continuing on "all but one default." The two kinds of bad value inside a
loaded file are also not identical to each other and the rejection reason says which is which: a
**misspelled/unknown key** means a knob he set is doing nothing (his edit was never read); an
**out-of-range value** means a knob he set would have done something he did not ask for, had it
been applied (his edit was read and rejected). Both still resolve to "use the code default," but the
startup block's reason text distinguishes them for exactly that reason — "unknown key" and
"out of range" read differently to the pilot, even though the constant ends up the same.
**This is a recommendation, not a decision** — if he would rather have the missing-file case also
warn-and-run-on-all-defaults, the mechanism supports it with no structural change, only a different
answer at one `if`.

---

### How the count was taken

`ast` over each subproject's `src/**/*.py`, collecting module-level `Assign`/`AnnAssign` to
`UPPER_CASE` names, classified by RHS kind (numeric literal / table / derived expression / string /
other), then filtered by the inclusion test's public rule and its interface-contract exclusions.
Scripts in `/tmp`, not committed — rerunnable in ten lines. The per-subproject figures in the
Effort/Value table are the output of that pass, not an estimate; the "survives the inclusion test"
column is a hand classification of the public numeric/table list against the five criteria and is
the one column with judgement in it (±5).
