# BL-B90 — configurable cockpit effector sequences

Precedence: `plans/effector-sequences/explore-notes.md` (user's own words; its **2026-10-23**
section outranks everything below) > `docs/concept/configurable-cockpit-effector.md` ("concept,
not final truth") > `body-layer/ROADMAP/BL-B90.md` > this plan's own text.

**Revision history**

- 2026-10-21, first pass `c741149e`, revised `ca8760d9` (registry = whole Mi-24P, generated from
  ED files; sequenced after BL-B80).
- **2026-10-23, this revision (plan only, no code)** — fitted to the code after `[[BL-B80]]` v2
  merged (`a2ea382c`), and folds in the user's four 2026-10-23 answers. What changed, in one
  place:

| # | Was (2026-10-21) | Now (2026-10-23) | Why |
|---|---|---|---|
| R1 | Stage 4 "remove `GuidanceUnitState`" | **`GuidanceUnitState` stays, slimmed to readback only** (lamps + observed switches). Its sequencing fields move into the engine. | BL-B80's `SightHead`, `home_phase` derivation and `sight_ready()` read it |
| R2 | `sight_ready` refreshed from `is_complete(TAKEOFF)` | **`sight_ready` stays `sight_effector.sight_ready(state)` = the real 960 lamp** | BL-B80 v2 replaced "sequence done" with the lamp |
| R3 | "Guidance unit ready" in the takeoff file's `petrovich-says` | **Stays hard-coded, on a true observed 960 off→on edge**, with a named seam for a future `guidance-unit-ready` trigger | User: *"For now it can be hard coded, but it should really be it's own trigger"* |
| R4 | Takeoff one-shot per mission | **Every takeoff**; the file's row conditions skip what is already on | User: *"per takeoff, the sequence file will then deal with it not being the first takeoff"* |
| R5 | Row conditions read **commanded** state (old D3) | **Conditions read the observed cockpit readback** | Commanded state cannot know a hot start, an air start, or a switch the pilot moved by hand — the very cases R4 makes the file handle |
| R6 | Bad file → refuse to start (explore decision 6, old D2/D3) | **Bad file → log, ignore that file, console banner, one intercom line once the intercom is up** | User decision 3, 2026-10-23 |
| R7 | Stage 3 = generic watched-args readback, needed for parity | **Not needed for this cut**: BL-B80's existing per-frame `cockpit_switch` feed already carries all six switch args. Stage 3 becomes the last, deferrable stage. Stage 2 adds an arg-keyed view of the existing feed (aircraft-layer Python only, no `Export.lua` change). | Measured from the code: `push_cockpit_switch_state` reads 773/761/885/955/886/673 + 898/960/962 |
| R8 | Global vs per-trigger queue open | **Per trigger** | User decision 1 |
| R9 | No acceptance card | **Own short re-flight card** (Stage 3, `/test-card`) | User decision 4 |
| R10 | Stage 0 placement "Implementer's call" | **Settled**: `body-layer/tools/generate_effector_registry.py`, full spec below | User: build the generator next |

Superseded text that a later reader needs is kept in "Superseded (2026-10-21 text)" at the end,
not deleted.

### Goal

Replace BL-B66's hard-coded guidance-unit power-up / OBSERV / weapons-safety-bar switch writes
with a generated Mi-24P effector registry, a small curated registry of friendly names, and
startup-loaded markdown-table sequence files per (aircraft, role, trigger) — so adding or
reordering a cockpit switch sequence is a data edit — while gating/refusals, every readback BL-B80
consumes, the "Guidance unit ready" line (this cut) and the slew/pointing loop stay in code.

---

## What already exists, and what this entry reuses rather than invents

- **The write channel is already generic.** `cockpit_switch` (`Export.lua`
  `handle_cockpit_switch_command`, `aircraft_client.write_cockpit_switch`) writes any
  `(device, cmd, value)`. **Zero `Export.lua` change for this cut.**
- **The readback already exists for every switch this cut touches** (R7). `push_cockpit_switch_state`
  reads the six switch args plus the three BL-B80 lamps every frame, sends on change, and
  `GET /cockpit_switch/latest` serves them. `run_sight_servo` separately reads 886/898 *inside
  Lua* every frame — that is the slew loop and is **not touched, ever**.
- **The "is the intercom up" notion already exists**: aircraft-layer `Spu8Cache.gate_state()` /
  `Spu8Sample.gate_open` (pilot NET-1 377 AND co-pilot ICS power 664), served as
  `GET /spu8/state` → `"gate_open"`, fail-safe-closed when no sample yet. It is consulted by
  `AudioPlaybackSender`, which **drops** a line played while the gate is closed — so it cannot be
  used as a "hold until up" queue by itself. Body-layer does not read it today.
- **The speech funnel already exists**: `CrewConsole._print` (stdout + overlay + TTS, honours
  `silenced`). The one-shot "speak this once when a condition holds" shape already exists too:
  `CrewConsole.drain_guidance_unit_ready(now_sim, *, ready, announced)` — caller passes booleans,
  `CrewConsole` does not hold runner state. The new error line copies that shape exactly.
- **A "system error" spoken-line precedent exists**: `WORLD_MODEL_NOT_LOADED_REFUSAL` ("system
  error, world model not loaded"). The new line follows the same "System error, …" form.
- **The generator convention exists**: `body-layer/tools/generate_defaults.py` — a dev tool under
  `body-layer/tools/`, **static parse, never execute** ("AST, not import"), check mode by default,
  `--write` to regenerate, committed generated file with a DO-NOT-HAND-EDIT header, tested from
  `body-layer/tests/` by loading the tool with `importlib.util.spec_from_file_location`
  (`test_generate_defaults_first_sentence.py`). Stage 0 copies all of this.
- **replace()-only, one-construction-site discipline** for frozen run state, as `GuidanceUnitState`
  already does.
- **The one-shot external-signal shape** `observ_transition` / `weapon_safety_transition` on
  `CrewConsole` is unchanged; the poll loop fires a trigger instead of a hard-coded write.
- **Gating stays in code**: `_handle_observ_on`'s `sight_ready` gate and "Unable, guidance unit not
  ready" are untouched.

**Queries run** (`gq.sh`, `memory-search.py`): no prior plan on this ground beyond explore-notes,
the concept doc and BL-B66/BL-B80. Relevant memory: the four-times-recurring "leaf tested, poll-loop
wiring not" defect (`reviewer/project_terrain_callout_stage5_wiring_gap.md`,
`dod/project_untested_wiring_pattern_caught_at_reviewer_not_dod.md`), and the poll-loop test recipe
(`implementer/feedback_poll_loop_sim_time_integration_tests.md` — note its trap 2: `on_ground`
defaults `True`, so an airborne first sample is a takeoff edge; see Risks).

**No `investigator` pass.** The only DCS-internals unknowns are the exact Lua forms in ED's cockpit
scripts, which no Mac-side role can read (the files exist only on the Windows DCS machine — see
Stage 0). Stage 0 is designed fail-closed so the first real run reports any form it does not
handle, and Stage 0a is a read-only recon step on that machine.

### Finding outside this plan's scope — raise before Flight A

**The merged BL-B80 code does not implement BL-B80's own decision 2** ("Guidance unit ready" only on
an *observed* 960 off→on edge, silent on air starts). `logger.py` calls
`drain_guidance_unit_ready(ready=sight_ready(state), announced=…)` and `drain_guidance_unit_ready`
speaks whenever `ready and not announced`. On an air start the first `cockpit_switch` sample
already has `ready_lamp: true`, so he says "Guidance unit ready" at spawn. Nothing tests the
air-start case (`test_logger.py`'s ready test starts with the lamp unobserved). The latch is also
once per mission, so a power-down/re-power never re-announces. **Flight A is an air start**, so
this will be heard. The fix is small and independent (true edge: previous `ready_observed is False`
and new `is True`; drop the `guidance_unit_ready_announced` latch), and could go on `main` before
Flight A. If it has not landed by the time this plan reaches Stage 2, Stage 2 does it, because the
edge detector is also R3's seam.

---

## Registry scope and source — decided (2026-10-21, unchanged)

The registry is the full Mi-24P clickable-control surface, generated from ED's own
`Mods/aircraft/Mi-24P/Cockpit/Scripts/` files. User: *"ED files is better. Use DCS-bios data as
reference for what they do, if DCS file does not provide info."* So:

- **The generator reads only ED's files.** It never parses, imports or vendors DCS-BIOS (GPL-3.0;
  this project is CC BY-NC-SA 4.0, `LICENSE.md`, and the two cannot be combined).
- **DCS-BIOS is read by a person, by hand,** to label a curated entry when ED's own label is
  missing or ambiguous.
- **No ED source is committed.** The generated TOML carries derived facts (names, numbers, ED's
  short English hint strings), the same class of content `aircraft-layer/research/
  mi24p-command-surface.md` §10 already commits. Test fixtures are **synthetic Lua written for this
  project** in ED's forms, never copied excerpts.

---

## Stage 0 — the switch-list generator (build next; implementable as written)

### Where the real files are

- **Only on the Windows DCS machine.** `world-model/data/raw/dcs/2026-09-02/DCS-files.txt` (the
  install listing) confirms, under `Mods/aircraft/Mi-24P/Cockpit/Scripts/`: `devices.lua`,
  `command_defs.lua`, `clickable_defs.lua`, `clickabledata.lua`, plus per-system command files
  (`A036_commands.lua`, `Weap_syst_commands.lua`, `main_panel_commands.lua`,
  `MiscSystems_commands.lua`, `Hydro_system_commands.lua`,
  `FireExtinguishersInterface_commands.lua`, …) and `Macro_sequencies.lua`.
- **Not on this Mac**: `$DCS_INSTALL_PATH` is unset here, and `win-mac-sync/from-windows/` holds
  `elements_defs.lua` and `PKV_init.lua` but none of the four files above.
- **Paths come only from `DCS_INSTALL_PATH` / `DCS_SAVED_GAMES_PATH`** (user direction,
  2026-10-23), set on the Windows DCS machine, the same precondition `dcs-file-investigation` uses
  (`${DCS_INSTALL_PATH:?not on the DCS machine}`). No step, and not the tool, ever searches for
  the install or hard-codes a path.
- `Macro_sequencies.lua` is presumably ED's own cold-start macro (switch sequences). Prior art worth
  a look in Stage 0a, not a parser input.

### Steps, and which machine each runs on

| Step | Where | What |
|---|---|---|
| **0a** (recommended, not blocking 0b) | **Windows DCS machine**: a command given to the user, or relayed by the main loop when a Windows session exists | Read-only recon of the exact Lua forms. Output: a dated note `aircraft-layer/research/2026-10-2x-mi24p-clickabledata-forms.md` answering the questions in "Forms the parser must handle". Short quoted snippets are fine in research; no whole-file copies. |
| **0b** | Mac (Implementer) | Tool, synthetic fixtures, tests. Starts from the forms the research notes already document; folds in 0a's answers when they arrive. |
| **0c** | **Windows DCS machine** (same channel as 0a) | `--write` run against the installed tree. Returns `body-layer/config/effectors-raw.toml` and the run report. This is the real run: no Mac-side role produces the committed dump (execution-boundary rule, `feedback_full_build_execution`). |
| **0d** | Mac | Control-point check of the returned dump (below), then commit it on `feature/effector-sequences`. A failing control point blocks Stage 1. |

### Tool

- **Path**: `body-layer/tools/generate_effector_registry.py`. Stdlib only (`argparse`, `re`,
  `hashlib`, `pathlib`, `json`, `tomllib` for reading the output back in tests). Runs on any
  Python 3.11+, Windows or WSL; nothing from body-layer's `src/` is imported (it is a file-to-file
  transform).
- **Static parse, never execute ED's Lua** (`generate_defaults.py`'s own principle). A small
  tokenizer (strings incl. `[[…]]`/`[==[…]==]`, numbers, names, punctuation, `--` and `--[[ ]]`
  comments) plus a recursive-descent reader for the Lua subset ED uses: table constructors,
  function calls, dotted/indexed names, `_("…")`, unary minus, and the `counter()` idiom. Anything
  outside that subset inside an `elements[…] =` statement is an **unhandled element**, never
  guessed.
- **CLI**:

  ```
  python tools/generate_effector_registry.py [--scripts-dir <dir>]
         [--dcs-build <string>] [--output <path>] [--write] [--allow-unhandled]
  ```

  - **input location**: by default `$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts`.
    If `DCS_INSTALL_PATH` is unset and `--scripts-dir` is not given, exit 1 with
    "DCS_INSTALL_PATH is not set — not on the DCS machine; pass --scripts-dir to point elsewhere".
    `--scripts-dir` overrides the variable (tests and fixtures always use it). The tool never
    searches for an install.
  - default (no `--write`): parse, print the report to stdout, write nothing. Exit 0 clean,
    2 if any element is unhandled, 1 on an unreadable input.
  - `--write`: also write the TOML (default `body-layer/config/effectors-raw.toml`, relative to
    the tool, `--output` overrides — tests always pass `--output` into `tmp_path`). Refuses to
    write (exit 2) if any element is unhandled, unless `--allow-unhandled`, in which case the
    unhandled list goes into the header.
  - `--dcs-build`: if absent and `DCS_INSTALL_PATH` is set, read the version from
    `$DCS_INSTALL_PATH/autoupdate.cfg` (that exact file, no walking up); otherwise exit 1 with
    "pass --dcs-build".
- **Real-run command** (Windows DCS machine, from the repo checkout's `body-layer/`; both vars
  already set there):

  ```sh
  : "${DCS_INSTALL_PATH:?not on the DCS machine}"
  python tools/generate_effector_registry.py           # report only
  python tools/generate_effector_registry.py --write   # then write config/effectors-raw.toml
  ```

### Forms the parser must handle (from the research notes; 0a confirms or corrects)

1. **`devices.lua`**: `devices["NAME"] = counter()` (or `devices.NAME = counter()`), assigned by
   order of appearance from 1 (`mi24p-command-surface.md` §2/§9). Control points: `WEAP_SYS = 6`,
   `I9K113 = 7`, `ASP_17V = 16`, `HELPER_AI = 30`, `SPU_8 = 55`, 73 devices total in 2.9.29.
2. **Command tables**: `<x>_commands = { Name = counter(), … }`, each table restarting at 3001
   (§9/§10 "all restart at 3001 per device"). **How the restart is written** (a `start_command`
   constant, a reset of a local, a fresh `counter` per table) is question Q1 for 0a; the tool
   implements that exact form and fails closed on any other. If `command_defs.lua` pulls in the
   per-system `*_commands.lua` files (`dofile(LockOn_Options.script_path.."X.lua")` or similar —
   Q2), the tool follows includes **only to files inside `--scripts-dir`**, and an include it
   cannot resolve is an error.
3. **Helper-call elements**: `elements["NAME"] = <helper>(_("hint"), devices.X, x_commands.Y, <arg>, …)`.
   Known helpers (§7): `default_button`, `default_2_position_tumb`, `default_3_position_tumb`,
   `default_2_position_small_tumb`, `default_axis`, `default_animated_lever`,
   `default_blue_cover`, `multiposition_switch`. The tool holds a table
   `helper name → positions of (hint, device, command, arg)`; positions beyond the fourth are kept
   verbatim as `helper_args`. An unknown helper name → unhandled, named in the report. Q3 for 0a:
   each helper's parameter list in `clickable_defs.lua`.
4. **Raw-table-literal elements** — the 13 the 2026-09-11 dump missed
   (`mi24p-command-surface.md` "Known gap"; `2026-09-20-dcs-install-detection-deep-read.md`
   finding 11): `elements["STICK-PTT-PTR"] = { class = {…}, hint = _("…"), device = devices.SPU_8,
   action = {…, …}, arg = {738, 738}, arg_value = {1.0, 0.5}, arg_lim = {{0.0, 1.0}, {0.0, 0.5}}, … }`.
   `action`/`arg` may be scalars or lists; lists are kept as lists. Control points: `STICK-PTT-PTR`
   args `[738, 738]`, `OP-STICK-PTT-PTR` `[856, 856]`, both `arg_value = [1.0, 0.5]`.
5. **Post-assignment fields**: `elements["NAME"].crew_member_access = {1}` and the same form
   inside a literal. Absent → recorded as `seat = "default"` (DCS defaults to pilot,
   `crew_member_access` absent = 0 per the SPU-8 recon) — never silently written as `"pilot"`.
   `{0}` → `"pilot"`, `{1}` → `"operator"`, `{0, 1}` → `"both"`. Control point: arg 664's element
   `crew_member_access = {1}`.
6. **Anything else** at top level of `clickabledata.lua` (loops, locals, function definitions) is
   **not an element**: counted and listed by line in the report as "statements ignored". Q4 for
   0a: does any loop create or mutate elements? If so the tool must handle it before 0c.
7. **Completeness check, fail-closed**: the number of textual `elements[` assignment heads in
   `clickabledata.lua` must equal emitted + unhandled. 749 expected for 2.9.29.27278; a different
   count is reported, not an error (patches add controls).

### Output — `body-layer/config/effectors-raw.toml`

Hand-rendered TOML (stdlib cannot write TOML; same as `generate_defaults.py`), sorted by element
name so a regeneration diffs cleanly:

```toml
# Generated by body-layer/tools/generate_effector_registry.py. DO NOT HAND-EDIT.
# Source: Mods/aircraft/Mi-24P/Cockpit/Scripts, DCS 2.9.29.27278
# Inputs (sha256): devices.lua <hex>, command_defs.lua <hex>, clickabledata.lua <hex>, ...
# Elements: 749 emitted, 0 unhandled. Statements ignored: <n> (see the run report).
# Regenerate after any DCS update: device and command numbers are positional.

[elements."WEAP-SIGHT-ON-PFF-PTR"]
device = 16
device_name = "ASP_17V"
cmds = [3014]
cmd_names = ["asp_commands.Power"]
args = [529]
label = "Sight Power ON/OFF"     # ED's own hint string, not a friendly name
shape = "default_2_position_tumb"
seat = "default"

[elements."STICK-PTT-PTR"]
device = 55
device_name = "SPU_8"
cmds = [<n>, <n>]
cmd_names = ["...", "..."]
args = [738, 738]
arg_values = [1.0, 0.5]
label = "..."
shape = "raw"
seat = "default"
```

Lists everywhere (one shape for helper and raw elements; a consumer never branches on type).
`helper_args` (verbatim source text of positions after the fourth) only when present.

### Tests — `body-layer/tests/test_generate_effector_registry.py`

Fixtures in `body-layer/tests/fixtures/effector_registry/` — **synthetic Lua**, a tiny fake module
in ED's forms: `devices.lua` (≥ 3 devices, including one at a position that proves 1-based order),
`command_defs.lua` (two tables, proving the per-table restart at 3001, plus one include if 0a
confirms that form), `clickabledata.lua` covering:

- one element per known helper, including `multiposition_switch` with trailing args;
- a raw literal with list `action`/`arg`/`arg_value`/`arg_lim` (the PTT shape) and one with
  scalars;
- `crew_member_access` absent, `{0}`, `{1}`, and as a post-assignment;
- `_("…")` hints containing a comma, a quote and a `--` (must not be read as a comment);
- a `--[[ … ]]` block comment containing a fake `elements[` line (must not count);
- a top-level `for` loop and a `local` (ignored, listed);
- in a second fixture file set: an unknown helper, and a reference to an undefined device symbol.

Assertions: exact TOML for the good set (parsed back with `tomllib`, not string-compared, plus
one golden-text check of the header/ordering); device/command numbers equal the fixture's
counter positions; unknown helper and undefined symbol each make check mode exit 2 and name the
element; `--write` refuses on unhandled and succeeds with `--allow-unhandled` (list in header);
the completeness count; include outside `--scripts-dir` is refused; `DCS_INSTALL_PATH` unset and
no `--scripts-dir` exits 1 with the "not on the DCS machine" message (`monkeypatch.delenv`);
`DCS_INSTALL_PATH` pointing at a fixture tree resolves the Mi-24P subpath and reads its
`autoupdate.cfg`; `--scripts-dir` with no variable and no `--dcs-build` exits 1. Run with body-layer's normal `pytest`.

### 0d control points (real dump, Mac-side, before commit)

Against `mi24p-command-surface.md` §2/§10 and the live-confirmed BL-B66/BL-B80 values: devices
6/7/16/30/55; `asp_commands.Power` = 3014 on arg 529; the six BL-B66 writes —
`(6, 3028)` arg 773, `(16, 3015)` arg 761 (still UNVERIFIED), `(7, 3001)` arg 885, `(6, 3030)`
arg 955, `(7, 3002)` arg 886, `(6, 3020)` arg 673 — each present as some element; 738/856 present;
664 `seat = "operator"`. A mismatch on a DCS build newer than 2.9.29 is a finding to write up, not
an automatic fail; a mismatch on the same build is a parser bug.

**Stage 0 is its own batch** (dev tool, no runtime dependency; performance/security passes per
root `CLAUDE.md`'s batch rule — one each, after 0b).

---

## File formats (Stages 1–2)

**Curated registry — `body-layer/config/effectors.toml`.** Hand-written, small. Each entry: a
friendly name, `source_element` (join key into the raw dump), optional `index` (which entry of a
multi-action element's lists, default 0), named `values`. **Never repeats device/cmd/arg.**

```toml
[effectors.missile_power]
source_element = "<ED name for arg 773>"     # filled from the Stage 0 dump
values = { on = 1.0, off = 0.0 }

[effectors.cplr_distr]
source_element = "<ED name for arg 761>"
values = { on = 1.0, off = 0.0 }
unverified = true   # docs/acceptance/2026-10-17-9k113-procedures-direction.md

[effectors.sight_power]
source_element = "<ED name for arg 885>"     # NOT WEAP-SIGHT-ON-PFF-PTR/529 (the ASP-17's)
values = { on = 1.0, off = 0.0 }

[effectors.scho_pwr_b1]
source_element = "<ED name for arg 955>"
values = { on = 1.0, off = 0.0 }

[effectors.observ]
source_element = "<ED name for arg 886>"
values = { on = 1.0, off = 0.0 }

[effectors.weapon_safety]
source_element = "<ED name for arg 673>"
values = { armed = 1.0, safe = 0.0 }
```

**Sequence files — `body-layer/config/effector-sequences/*.md`.** Two tables per file:

1. Header (`file-param | for`) with exactly `aircraft`, `petrovich-role`, `run-on-trigger` — the
   key for duplicate detection (not the filename).
2. Data table `condition | effector | value | petrovich-says | comment`. Each row is one of:
   - **switch row**: `effector`/`value` name a registry entry and one of its `values`.
     `condition`, if present, is `<effector> = <value>` or `<effector> != <value>`, evaluated
     **against the observed readback at the moment the row is reached** (R5, D3). A false condition
     skips the row: no write, no delay, **no speech**.
   - **wait row**: `condition` = `wait_s(<n>)`, every other cell blank — the gap before the next
     row is `<n>` s instead of the default.
   - **say-only row** (effector blank, `petrovich-says` set) is **reserved, rejected this cut**
     with the message "say-only rows arrive with the guidance-unit-ready trigger" (seam, D7).

Takeoff, as it ships (R4 — a second takeoff, or a warm air start, skips every row):

```markdown
| file-param | for |
| --- | --- |
| aircraft | Mi-24P |
| petrovich-role | copilot |
| run-on-trigger | takeoff |

| condition | effector | value | petrovich-says | comment |
| --- | --- | --- | --- | --- |
| missile_power != on | missile_power | on | | MISSILE POWER |
| cplr_distr != on | cplr_distr | on | | CPLR DISTR -- unverified, see registry |
| sight_power != on | sight_power | on | | Sight Power (GUID.UNIT POWER) |
| scho_pwr_b1 != on | scho_pwr_b1 | on | | SHCHO PWR B1 |
```

OBSERV on/off and weapons arm/safe: one unconditional row each (parity with today).

**Readback value matching.** An observed raw value `r` matches named value `v` iff
`|r − v| <` half the smallest gap between that effector's named values (two-position → the
existing `>= 0.5` threshold; works for 3-position). Absent readback is **unknown**, never a value.

---

## Settled design decisions

- **D1 — Queues per trigger** (user, 2026-10-23). Each trigger has at most one *running* run and
  one *pending* run. Firing a trigger whose run is idle starts it this poll; firing while it runs
  marks it pending; firing while already pending is a logged no-op (a re-run only re-evaluates
  conditions, so a second pending copy adds nothing). Different triggers run independently.
- **D2 — Takeoff fires on every takeoff** (user, 2026-10-23): on every `on_ground` True→False
  transition, using the existing `ON_GROUND_AGL_THRESHOLD_M` signal (the concept's "bind to that
  value"). The `takeoff_seen` latch is deleted.
- **D3 — Conditions read observed readback; unknown waits, then skips.** *Supersedes old D3
  (commanded state)* — reason R5. If a condition's effector has no readback yet, the row waits
  (does not advance, does not write) up to `EFFECTOR_CONDITION_READBACK_WAIT_S` (new tunable,
  default 5.0, lo 1.0, hi 30.0), then skips with a WARNING naming the effector and arg. Never
  "unknown → true": a row like `observ = on → weapon_safety armed` must not fire on missing data.
  In the poll block, readback is refreshed **before** the engine advances (today it is after), so
  a row reached this poll sees this poll's sample.
- **D4 — Re-runs never re-speak.** Speech comes only from a row that actually wrote. The takeoff
  file has no `petrovich-says` at all this cut; "Guidance unit ready" is hard-coded on the 960
  **edge** (prior observed `False` → `True`), so a second takeoff with the unit already up says
  nothing, a power-down/re-power announces again, and an air start with the lamp already lit is
  silent.
- **D5 — A bad file is not fatal** (user, 2026-10-23; *supersedes explore decision 6 and old
  D2/D3*). At load:
  - each sequence file is validated alone; a bad one is ignored and every error is collected
    (file, line, reason);
  - **registry, recommended posture — same, at the finest grain that is honest**: a bad curated
    *entry* (unresolved `source_element`, two entries resolving to the same `(device, cmd, arg)`,
    bad `values`) drops that entry, and any sequence file using it becomes a bad file in turn;
    a curated or raw file that cannot be read or parsed as TOML at all disables **every** sequence
    (all depend on it). Same banner, same one audio line. *Why not fatal for the registry*: the
    user's principle — "Petrobrain will continue, but some functionality may not work" — applies
    exactly; a refusal here would reinstate the failure mode they just overruled, and everything
    outside effectors (detection, callouts, voice) does not depend on the registry at all;
  - **console**: `logger.error` per error, plus one unmissable multi-line banner on stderr at
    startup listing every bad file and reason;
  - **audio**: exactly one line per body-layer process, however many files are bad:
    *"System error, bad sequence file, see the logs. Petrobrain will continue, but some
    functionality may not work."* — held until the intercom is up (D6);
  - a trigger with no loaded file fires into nothing (DEBUG log). The pilot's own command readback
    (e.g. "Observ on") is unchanged — see Risks.
- **D6 — "Once the intercom is up" = aircraft-layer's existing SPU-8 gate.** New
  `AircraftLayerClient.get_spu8_state_latest()` (`GET /spu8/state`, swallow-to-`None` like every
  other getter). `CrewConsole` gains `config_error_pending: bool` (set at startup from D5) and
  `drain_config_error(now_sim, *, intercom_open: bool) -> None`, the `drain_guidance_unit_ready`
  shape: speaks once through `_print` when `config_error_pending and intercom_open and not
  self.silenced`, then clears the flag. `intercom_open` is `gate_open is True`; `None` (no SPU-8
  sample, or an old `Export.lua`) never opens it — the banner already went to the console. Not
  cleared by a mission restart (it describes the process, not the mission): `_reset_mission_state`
  must not touch it.
- **D7 — `guidance-unit-ready` trigger: seam now, trigger later** (user default). Seam: the
  hard-coded announce sits on the single line that detects the 960 edge, and the trigger enum is a
  code enum. Moving it later costs: one `EffectorTrigger` member, replacing that `_print` with
  `fire_trigger(GUIDANCE_UNIT_READY)`, un-reserving the say-only row form, one file
  (`| | | | Guidance unit ready. | |`) and tests — about half a day, and it carries a parity
  question (a sequence-file line would be spoken via the engine, one poll later). **Cheap, but not
  free, and not needed for this cut's value: recommend not in this cut.**
- **D8 — Wait rows** override (not add to) the default gap for that one gap (unchanged from
  2026-10-21).
- **D9 — Write failure**: the row is retried every poll (parity with today's power-up), never
  skipped. To keep the per-trigger queues from reordering writes to one switch: each poll, due rows
  across all triggers run **in fire order**, and once a write to effector *E* fails this poll, no
  later row writing *E* is attempted this poll. So "Observ on" stuck behind a dropped write cannot
  land after a later "Observ off". (Today's OBSERV/safety writes are dropped on failure; retrying
  is a small behaviour change, toward the pilot's intent.)
- **D10 — The inter-row delay** `GUIDANCE_UNIT_SWITCH_DELAY_S` is renamed
  `belief.effector_engine.EFFECTOR_SEQUENCE_STEP_DELAY_S` (same 1.0, `lo=0.5`, `hi=5.0`), and
  `config/defaults.toml` regenerated. A user `tuning.toml` with the old key will warn "unknown key"
  — say so in the commit and the card.
- **D11 — Mission (re)start** re-runs the runner `__init__`: engine and `GuidanceUnitState` fresh,
  running/pending runs dropped. Unchanged mechanism.

---

## What moves, what stays

| Concern | Today | After |
|---|---|---|
| Which switches, order, values | `_POWER_UP_SWITCHES` + two single writes in `sight_effector.py` | `effectors-raw.toml` + `effectors.toml` + `effector-sequences/*.md` |
| Sequencing state: `takeoff_seen`, `power_up_stage`, `next_switch_due_sim` | `GuidanceUnitState` | **deleted** / `EffectorRunState` |
| `observ_commanded`, `weapon_safety_commanded` | `GuidanceUnitState` | `EffectorRunState.commanded_values` (written on a successful write). `sight_trace_writer`'s `observ_commanded` column keeps its name and meaning, sourced from there (`None` → `False`, today's default) — Flight A's triage reads it |
| `observ_observed`, `weapon_safety_observed`, `align_observed`, `ready_observed`, `launch_perm_observed` | `GuidanceUnitState` | **stay** on `GuidanceUnitState` (renaming it is churn with no gain; it is the guidance unit's observed state). `refresh_readback` unchanged |
| `guidance_unit_ready_announced` | `GuidanceUnitState` latch | **deleted** — replaced by the edge (D4) |
| `sight_ready` | `sight_ready(state)` = 960 lamp | **unchanged** (R2) |
| "Guidance unit ready" | `drain_guidance_unit_ready`, first-lit latch | hard-coded on the observed edge (D4, D7) |
| Condition readback | none | existing `cockpit_switch` feed, arg-keyed view (Stage 2) |
| `write_sight_target`, slew, `SightHead`, `run_sight_servo` | — | **untouched** |

---

## Co-moving Fields

Trigger fires: `EffectorRunState` (internal) and `GuidanceUnitState` readback / `on_ground` /
`observ_transition` / `weapon_safety_transition` / SPU-8 gate (external) all describe "what the
switches are and what he is doing about it", and `home_phase` is derived from one of them.

**Construction sites, grepped 2026-10-23 at `147a057d`**: `GuidanceUnitState(` — one, the
`field(default_factory=GuidanceUnitState)` on `ConsolePerceptionRunner` (`logger.py:492`), re-run by
mission reset; every other change is `replace()` (`sight_effector.py`, `logger.py` 3285–3436).
Tests construct it directly (`test_sight_effector.py`, `test_logger.py`, `test_sight_trace_writer.py`)
— they must be updated, not left constructing removed fields. **`EffectorRunState(` must end up with
exactly the same one site.** The Implementer re-runs `grep -rn 'EffectorRunState(\|GuidanceUnitState(' body-layer/src`
after Stage 2 and pastes the result into the review handoff; a helper that builds a "fresh run
state for trigger X" is the `BL-B71` failure shape and is not allowed.

| Field | Written by | Transition | Must hold true immediately after |
|---|---|---|---|
| `EffectorRunState.runs[T]` (running cursor: row index, `next_due_sim`, `waiting_since_sim`) | internal | `fire_trigger(T)` while idle | cursor at row 0, due now; same poll's `advance` may execute it |
| `EffectorRunState.pending[T]` | internal | `fire_trigger(T)` while running | `True`; a second fire leaves it `True` and logs (D1) |
| `runs[T]` / `pending[T]` | internal | last row of `T` done | if `pending[T]`: new cursor at row 0, `pending[T] = False`; else `runs[T] = None` |
| `runs[T]` | internal | row reached, condition effector readback `None` | cursor unchanged, `waiting_since_sim` set once; after `EFFECTOR_CONDITION_READBACK_WAIT_S` the row is skipped (D3) |
| `commanded_values[E]` | internal | successful write of `E` | equals that row's value name; failed write leaves it unchanged (D9) |
| `GuidanceUnitState.*_observed` | **external** (`cockpit_switch` feed) | any sample | refreshed **before** `advance` this poll (D3); `None` leaves prior value (unchanged posture) |
| `crew_console.on_ground` | **external** (AGL) | True→False | `fire_trigger(TAKEOFF)` called exactly once this poll; no latch (D2) |
| `crew_console.sight_ready` | derived | any 960 sample | `== sight_ready(guidance_unit_state)`; unchanged source (R2) |
| (no field — local in poll block) ready edge | derived | `ready_observed` `False`→`True` | "Guidance unit ready." spoken once; `None`→`True` (air start) speaks nothing (D4) |
| `OpticState.home_phase` | derived in `run_once` from `observ_observed` | 886 edge | unchanged BL-B80 rule; this plan adds no branch to it |
| `observ_transition` / `weapon_safety_transition` | **external** (`crew_console` handlers) | pilot command / `_handle_engage` | drained into exactly one `fire_trigger(...)` and set `None` the same poll; the hands-busy `optic_state` update stays where it is |
| `crew_console.config_error_pending` | startup (D5); internal drain | SPU-8 `gate_open` observed `True` and not silenced | spoken once, flag `False`; mission reset leaves it alone (D6) |
| all of `EffectorRunState` | runner `__init__` | mission (re)start | fresh; nothing carried (D11) |

---

## Affected Modules / Files

**Stage 0** — `body-layer/tools/generate_effector_registry.py` (new),
`body-layer/tests/test_generate_effector_registry.py` (new),
`body-layer/tests/fixtures/effector_registry/**` (new, synthetic),
`body-layer/config/effectors-raw.toml` (new, generated on the Windows DCS machine),
`aircraft-layer/research/2026-10-2x-mi24p-clickabledata-forms.md` (0a).

**Stage 1 (pure, no wiring)**
- `body-layer/src/belief/effector_registry.py` (new) — loads both TOML files, resolves
  `source_element`, returns `(registry, errors)`; never raises on bad content (D5).
- `body-layer/src/belief/effector_sequences.py` (new) — parses `*.md`, returns
  `(sequences_by_key, errors)`.
- `body-layer/config/effectors.toml`, `body-layer/config/effector-sequences/mi-24p-copilot-{takeoff,observ-on,observ-off,weapons-arm,weapons-safe}.md` (new).

**Stage 2 (engine + wiring)**
- `body-layer/src/belief/effector_engine.py` (new) — `EffectorTrigger` (TAKEOFF, OBSERV_ON,
  OBSERV_OFF, WEAPONS_ARM, WEAPONS_SAFE), `EffectorRunState`, `fire_trigger`,
  `advance(state, now_sim, readback, client) -> state`, the two new/renamed tunables.
- `body-layer/src/belief/sight_effector.py` — delete the sequencing half (`_POWER_UP_SWITCHES`,
  device/cmd constants, `start_power_up`, `advance_power_up`, `write_observ`,
  `write_weapon_safety`, `GUIDANCE_UNIT_SWITCH_DELAY_S`) and the removed fields; keep
  `GuidanceUnitState` (readback), `sight_ready`, `refresh_readback`, `write_sight_target`.
- `body-layer/src/logger.py` — load config at startup (before the poll loop; banner; set
  `config_error_pending`); `ConsolePerceptionRunner.effector_state`; poll block: refresh readback →
  takeoff edge fires → transitions fire → `advance` → ready edge → `drain_config_error`.
- `body-layer/src/belief/crew_console.py` — `config_error_pending`, `drain_config_error`; remove
  or narrow `drain_guidance_unit_ready` to the edge (D4).
- `body-layer/src/aircraft_client.py` — `get_spu8_state_latest()`.
- `body-layer/src/sight_trace_writer.py` — `observ_commanded` sourced from the engine.
- `body-layer/src/tuning.py` consumers / `config/defaults.toml` regenerated.
- `aircraft-layer/src/schema/cockpit_switch.py` — `to_api_dict` gains
  `"args": {"773": <raw>, "761": …, "885": …, "955": …, "886": …, "673": …}`; nothing removed
  (BL-B80 fields and the six named fields stay). Test in `tests/test_cockpit_switch.py`.
  **Needs a collector restart on the Windows DCS machine, no `Export.lua` redeploy.** Body-layer
  against an older collector: no `args` key → readback unknown → D3 waits then skips; log one
  WARNING "cockpit_switch feed has no args map — update the collector".

**Stage 4 (deferred)** — the generic `watch_args` readback (2026-10-21 Stage 3, kept below).

---

## Implementation Plan

0. **Stage 0 — generator** (spec above). Own batch.
1. **Stage 1 — curated registry + sequence loader, pure.** Every D5 error case has a test that
   asserts it is *collected, not raised*, and that the other files still load: unknown effector,
   unknown value, unknown trigger, malformed row, say-only row (reserved), duplicate
   `(aircraft, role, trigger)` (both files rejected — neither silently wins), unresolved
   `source_element`, duplicate triple collision, unreadable TOML (all sequences off), plus a
   round-trip of each shipped file. Curated entries are filled from the committed Stage 0 dump.
2. **Stage 2 — engine, wiring, error surfacing.** Pure tests for D1/D3/D4/D8/D9 transitions, and
   **real-poll-loop tests** (`_run_crew_text_poll_loop` on a thread, per
   `feedback_poll_loop_sim_time_integration_tests`), each written to fail under a named mutation:
   (a) cold takeoff writes the four switches in order with the 1.0 s spacing BL-B66's tests pin
   — byte-identical `cockpit_switch_writes`; (b) second takeoff with readback all-on writes
   nothing and says nothing; (c) warm air start (first sample airborne, lamp lit): no "Guidance unit
   ready", no writes; (d) lamp off→on speaks once, on→off→on speaks twice; (e) readback absent at
   takeoff waits, then writes once it arrives; (f) "Observ on"/"off" and "weapons armed"/"safe"
   write exactly as today; (g) a bad sequence file at startup: banner printed, other triggers work,
   error line spoken only after `spu8` `gate_open` turns true and only once, held while silenced,
   survives a mission restart; (h) D9 ordering: failed "on" then "off" ends "off". Plus the
   aircraft-layer `args` map test. Batch with Stage 1 (built back to back): one performance pass,
   one security pass after Stage 2.
3. **Stage 3 — short re-flight card** (`/test-card`), branch named on the card. Windows DCS
   machine: pull the branch, restart the collector (no `Export.lua` redeploy, no Hook change).
   Items: cold start on the ground → take off → hear the four switches move, then "Guidance unit
   ready" when the lamp lights; land, take off again → nothing re-run, nothing re-spoken; "Observ
   on"/"Observ off"; "weapons armed"/"weapons safe"; one air start → no "Guidance unit ready" at
   spawn; one deliberately broken sequence file (typo in an effector name) → console banner at
   start, the error line once the intercom is on, everything else still works. ~10 minutes.
4. **Stage 4 — generic low-rate readback (deferred).** Build when the first sequence names an
   effector outside the six args the existing feed carries; until then the loader and D3's
   WARNING say exactly which effector needs it. Design as 2026-10-21 (below), **additive**: the
   existing `cockpit_switch` line and its BL-B80 fields are not reduced. Needs an `Export.lua`
   redeploy on the Windows DCS machine.

---

## Invariants checked

- **DCS authoritative; code owns factual state.** Conditions now read DCS's own readback (R5) —
  more faithful than commanded state, and "unknown" is never turned into a value (D3). Gating
  stays in code.
- **Never modify the DCS installation.** The generator only reads it; writes stay
  `performClickableAction` via the existing op.
- **Module independence.** aircraft-layer ↔ body-layer stays HTTP/JSON (`/cockpit_switch/latest`
  `args`, `/spu8/state`). The generator imports nothing across subprojects.
- **No new abstraction without removed duplication.** Engine + data replace five hand-written
  write blocks; the error line reuses `_print`, the drain shape and the SPU-8 gate.
- **Provenance.** The raw dump records DCS build and input hashes; curated entries never copy a
  number.
- **No GPL dependency; no ED source committed.**
- **Single-player only.**

---

## Risks & Unknowns

- **The parser's Lua forms are unverified until 0a/0c** (counter restart form, include form,
  helper parameter lists, loops). Fail-closed design means the cost of a wrong guess is one more
  0c round-trip, not a wrong number — provided the completeness count and control points are
  enforced, which is why both are in the tests and 0d.
- **Per-trigger queues allow interleaving across triggers.** D9 keeps writes to one switch in
  order; two different multi-row sequences can still interleave rows. None of this cut's
  sequences has more than one row except takeoff, whose switches no other sequence touches.
- **A pilot command whose sequence file is bad still gets its normal readback** ("Observ on") while
  no switch moves. The startup line warned. A cheap follow-up would answer "Unable, system error"
  for a trigger with no loaded file — gating in code, not in this cut.
- **`on_ground` jitter near 10 m AGL** (hover-taxi) now fires TAKEOFF repeatedly. Harmless —
  D1 coalesces and conditions skip — but it means the takeoff file must stay idempotent. A
  hysteresis on `on_ground` is out of scope (it is shared with the look-refusal gate).
- **An airborne first sample is a takeoff edge** (`on_ground` defaults `True`). Intended here: it
  is what powers a cold unit on an air start; on a warm air start every row skips.
- **Silenced or intercom never on**: the error line may never be voiced. The console banner is the
  primary channel; the line is a reminder.
- **761 (`cplr_distr`) stays UNVERIFIED**, carried as `unverified = true`. The user: *"If we get the
  wrong one, the change is trivial."*
- **Element-name collision across systems** (the ASP-17's "Sight Power" 529 vs the 9K113's 885):
  joining by ED element name protects the machine, not the curator. No mechanical check catches a
  wrong-but-resolvable `source_element`; the 0d control points cover the six that ship.
- **BL-B80 is merged, not flown.** If Flight A finds 960 is not the READY lamp, `sight_ready` and
  D4's edge move with it — a BL-B80 fix, but this plan's tests encode 960 by name only through
  `GuidanceUnitState.ready_observed`, so nothing here hard-codes the number.

---

## Second-order effect

The generated whole-aircraft dump makes every later cockpit write (`BL-B67`'s launch-station
selector, a pilot-role sequence, a Mi-8 registry) a lookup rather than a research round, and the
non-fatal loader with an intercom-announced error is a pattern any later startup-loaded config
can reuse. It also leaves `guidance-unit-ready` one small step away (D7), which is the natural
first consumer of the say-only row and of event-driven (not pilot-driven) triggers like
`atgm-launch`.

---

## Decisions Requiring User Input

1. **Stage 4 (generic watched-args readback): defer until a sequence needs it?** Recommend
   **defer** — the existing feed covers every switch this cut touches, Stage 4 is the only part
   needing an `Export.lua` redeploy, and the loader names the first effector that would need it.
   (Your 2026-10-21 "readback is registry-driven, low frequency" stands as the design for when it
   is built.)
2. **`guidance-unit-ready` trigger in this cut?** Recommend **no** (your default) — ~half a day,
   seam is in place (D7).
3. **The BL-B80 air-start "Guidance unit ready" divergence** (above): fix it on `main` before
   Flight A, or let it ride to this plan's Stage 2? Recommend **fix before Flight A** — it is a
   few lines and Flight A is an air start.

---

## Superseded (2026-10-21 text), kept for the record

- **Old Decision 2/3 (fatal at startup)** — *"Startup-fatal validation is a deliberate, stated
  departure from `tuning.py`'s 'never refuses to start' posture … by explicit user direction ('I'd
  rather a check at startup and error than finding out in middle of flight')."* **Superseded by
  D5** (user, 2026-10-23: *"bad file: log error and ignore file …"*). The validation rules
  themselves are unchanged; only what happens on failure changed.
- **Old Decision 3 (conditions on commanded state)** — chosen to keep "code owns truth" by never
  letting a file read live aircraft state. **Superseded by D3/R5**: with takeoff on every takeoff,
  commanded state is wrong exactly when it matters (hot/air start, pilot hand-moved a switch).
  Reading DCS's own readback is the more truthful source, and gating still stays in code.
- **Old Decision 1 (queue scope open, recommend per-trigger)** — resolved as recommended (D1).
- **Old Decision 2 in the Decisions list (TAKEOFF one-shot, recommended)** — **overturned** by
  the user (D2).
- **Old Decision 4 (no card)** — **overturned**: Stage 3 card.
- **Old Stage 3 (generic readback, needed for this cut)** — design kept for Stage 4: new
  `"watch_args"` op on `Export.lua`'s command listener; `push_watched_args_state` at ~1 Hz reading
  `GetDevice(0):get_argument_value(arg)` for each watched arg, change-epsilon
  `COCKPIT_SWITCH_EPSILON`; aircraft-layer `schema/watched_args.py`, `WatchedArgsCache`,
  `send_watch_args`, `POST /command/watch_args`, `GET /watched_args/latest`; body-layer
  `set_watch_args` (raises) / `get_watched_args_latest` (swallows), re-sent after every mission
  (re)start. **Changed**: it no longer removes the six named fields from `CockpitSwitchState` —
  BL-B80 consumes that line, and removal buys nothing.
- **Old Stage 4 ("remove `GuidanceUnitState`")** — **superseded by R1**; parity check folded into
  Stage 2 test (a).
- **Old co-moving row "`is_complete(TAKEOFF)` via `sight_ready`"** and **"`home_phase` set by the
  command"** — both stale after BL-B80 (R2; `home_phase` follows observed 886).
- **Old "no `LICENSE` file exists yet"** — `LICENSE.md` (CC BY-NC-SA 4.0) now exists, which makes
  the no-GPL rule a hard constraint rather than a precaution.
