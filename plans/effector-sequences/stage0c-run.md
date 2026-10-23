# Stage 0c — the real generator run, Windows DCS machine

## Rerun needed, 2026-10-23 (switch-reference value ranges)

The generator gained three fields since the original Stage 0c run below: `helper_args`
(verbatim trailing positional parameters), and `values` (settable-value ranges, discrete/
continuous/unknown — user request 2026-10-23, *"Can we get the argument value ranges there too?
I.e. what are the possible values to set be it continuous or steps."*). The already-committed
`body-layer/config/effectors-raw/mi-24p.toml` predates this change and has neither field; every
other field is unchanged, so the parser's own completeness arithmetic and 0d control points still
hold against it — nothing is broken by the old dump staying checked in until this rerun lands,
`render_switch_reference.py`'s new "Values" column simply renders blank for every row until then.

**Rerun exactly the Stage 0c command below** (unchanged — same preconditions, same two-step
report-then-write sequence), from `body-layer/` on the Windows DCS machine, on a checkout that
has this value-ranges commit:

```sh
cd body-layer
python3 tools/generate_effector_registry.py           # report only
python3 tools/generate_effector_registry.py --write   # body-layer/config/effectors-raw/mi-24p.toml
```

Send back exactly what the original run asked for (stdout report, the written
`config/effectors-raw/mi-24p.toml`, the resolved DCS build string). After it lands: commit the
regenerated raw dump, then regenerate `config/sequences/mi-24p/switch-reference.md` with
`python3 tools/render_switch_reference.py --write` (Mac-side — this step needs no DCS install) and
commit that too; `tests/test_render_switch_reference.py` is the staleness guard that confirms the
two are in sync.

**Path moved during Stage 2, 2026-10-23 (plan.md R13)**: every `body-layer/config/
effectors-raw.toml` mention below is the path as it stood for this Stage 0c run and is accurate
for that run; the real dump now lives at `body-layer/config/effectors-raw/mi-24p.toml`, moved
by `git mv` when Stage 2 switched to a per-aircraft directory layout. Not rewritten below —
this card is a record of what was actually run and sent back, per `docs/PROCESS.md`'s "superseded,
not deleted."

Stage 0b (the generator, its fixtures, and its tests) is built and merged onto
`feature/effector-sequences` as of `40641c973ca010605cac2c324722a47ef3f156d9`, DoD-passed
(`plans/effector-sequences/dod-check-stage0.md`). Stage 0c is the one step that must run on the
Windows DCS machine — no Mac-side role produces the real `config/effectors-raw.toml`
(`feedback_full_build_execution`: never run a real DCS extraction yourself; hand the user the
command). Build 2.9.30.28738 was the one Stage 0a read; Stage 0c runs against whatever is actually
installed when this is run, which may be the same build or a later patch.

## Prerequisites

- On the Windows DCS machine, with a checkout of `feature/effector-sequences` at (or past) this
  commit.
- `$DCS_INSTALL_PATH` already set to the DCS installation root (the one containing
  `Mods/aircraft/Mi-24P/Cockpit/Scripts/`) — this is a precondition, not something the command
  sets.

## Command — run exactly as written, from `body-layer/` in that checkout

```sh
cd body-layer

# 1. Report only -- parses the real installed Lua, writes nothing, confirms the completeness
#    count and prints any unhandled elements/statements ignored. Exit 0 = clean, 2 = N unhandled
#    elements (fails closed; investigate before --write), 1 = DCS_INSTALL_PATH unset or an
#    expected .lua file missing/unreadable.
python3 tools/generate_effector_registry.py

# 2. If step 1 exits 0 (no unhandled elements), write the real dump:
python3 tools/generate_effector_registry.py --write
```

Both invocations rely on `$DCS_INSTALL_PATH` already being set in that shell (the tool reads
`Mods/aircraft/Mi-24P/Cockpit/Scripts` under it and `autoupdate.cfg` for the build string — it
never searches for an install and never takes a default path). If step 1 reports any unhandled
element, **stop and send back the full report** rather than re-running with `--allow-unhandled` —
an unhandled element is this tool's fail-closed signal that something in the real file does not
match any of the forms confirmed by Stage 0a's recon, and that is a finding for the Implementer to
look at, not something to wave through from the Windows machine.

`--write`'s default output path is `body-layer/config/effectors-raw.toml`, relative to the tool's
own location — no `--output` override is needed for the real run.

## What to send back

1. **Step 1's full stdout** (the report), even though step 2 also writes it — it is the one place
   the "N unhandled" / "statements ignored" counts and the per-table/per-device numbers are
   printed in full, and confirms whether anything needed `--allow-unhandled`.
2. **The generated `body-layer/config/effectors-raw.toml`** from step 2 (or its content, if easier
   to paste than to transfer a file) — this is the file that gets committed on
   `feature/effector-sequences` and checked against the 0d control points
   (`plans/effector-sequences/plan.md`, "0d control points") before Stage 1 can start.
3. **The resolved DCS build string** the header line shows (`# Source: ..., DCS <build>`) — so the
   commit message and `implementation.md`'s Stage 0c entry can record which build the real dump
   came from, distinct from Stage 0a's 2.9.30.28738 recon build if DCS has patched since.

## Verified (this Mac, not the real DCS install)

Both commands' mechanics were run and their actual output checked before this card was written,
not inferred from the generator's own docstring:

- `DCS_INSTALL_PATH` unset, no `--scripts-dir` → `python3 tools/generate_effector_registry.py`
  prints `DCS_INSTALL_PATH is not set -- not on the DCS machine; pass --scripts-dir to point
  elsewhere.` and exits 1, exactly as this card and `plan.md`'s CLI section say.
- Report mode and `--write` against the `clean` synthetic fixture (standing in for the real
  `Mods/aircraft/Mi-24P/Cockpit/Scripts` tree, which does not exist on this machine) both ran
  clean, and the written file's header matches the shape shown in `plan.md`'s "Output" section
  (source line, per-input sha256, the three-way elements count, the regenerate-after-patch line).
- **Not verified**: the real run against the actual installed Mi-24P module — that needs the
  Windows DCS machine and is exactly what this card asks the user to do. If step 1 of the real run
  prints anything this card does not anticipate (a nonzero exit other than 1/2, an unhandled
  element, a different `elements[` head count than 749), stop and send that back rather than
  guessing past it.

## What happens next (not part of this card)

Once the report and the file are back: a Mac-side pass runs the 0d control points against the
real dump (devices 6/7/16/30/55 present; `asp_commands.Power` = 3014 on arg 529; the six BL-B66
writes present as some element; 738/856 present; arg 664 `seat = "operator"`), and, if they hold,
commits `config/effectors-raw.toml` on `feature/effector-sequences` — unblocking Stage 1.
