## Security Deep Analysis: BL-B90 Stage 0 — effector-registry generator

Branch `feature/effector-sequences`, reviewed at `6d49503df7bccc038efad0798bed773a48780b9b`
(fast-forwarded cleanly from `6dfece18`, worktree tree clean before and after).

Scope: `body-layer/tools/generate_effector_registry.py`,
`body-layer/tests/test_generate_effector_registry.py`,
`body-layer/tests/fixtures/effector_registry/{clean,dirty,bad_loop}/`,
`aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md`,
`plans/effector-sequences/{plan.md,implementation.md,review-stage0.md}`.

**Threat model applied (per root `CLAUDE.md`'s security scoping, 2026-10-21): single-user,
LAN-only. Realistic attackers are (1) malicious code in a dependency and (2) an infected LAN
machine port-scanning.** This tool has no network surface at all — it is an offline dev-time
file-to-file transform run by hand on the Windows DCS box — so attacker class (2) does not apply
to it; the review below is therefore about (1) and about whether the tool could itself become an
attack surface (code execution, writes outside its lane) regardless of attacker presence.

### Dependency Status

**No dependency change.** Imports are `argparse`, `hashlib`, `os`, `re`, `sys`,
`dataclasses.dataclass`/`replace`, `pathlib.Path` — all stdlib, confirmed by reading the import
block. No `tomllib` import despite the docstring area implying one (the module only *writes*
TOML, hand-rendered, same posture as `generate_defaults.py`; nothing in this tool reads TOML
back). Nothing added to `pyproject.toml`. DCS-BIOS (GPL-3.0) is referenced only in the module
docstring and in `plan.md`'s "Registry scope and source" as a labelling aid a *human* consults
by hand — grepped the whole diff for any `dcs-bios`/`DCS-BIOS`/`dcsbios` import or file read: none
exists. The plan's own licence reasoning (CC BY-NC-SA 4.0 vs. GPL-3.0, cannot combine) is sound
and the code matches it.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `generate_effector_registry.py` (whole file) | Static text parse, never `exec`/`eval`/`loadstring`/`dostring`/`import` of the Lua it reads | Confirmed by full read: every ED Lua file is only ever passed to `re`-based tokenizing/extraction functions. No `subprocess`, no `os.system`, no dynamic code path of any kind. | None. |
| `main()` L1040-1042 | Reads three ED-shipped files with `Path.read_text()` | Read-only; paths are built from `--scripts-dir`/`$DCS_INSTALL_PATH` + a fixed `_SCRIPTS_SUBPATH`, never from content inside those files. No path-from-parsed-data construction anywhere. | None. |
| `main()` L1121-1122 | `out_path.parent.mkdir(...)`, `out_path.write_text(...)` | The only filesystem write in the tool, and only reached behind `--write`. `out_path` defaults to `_DEFAULT_OUT_PATH = Path(__file__).resolve().parent.parent / "config" / "effectors-raw.toml"` — fixed, derived from the script's own location, never from `$DCS_INSTALL_PATH` or from anything parsed out of ED's files. `--output` can redirect it, but that is an operator-supplied CLI argument on a dev-time tool run by hand, not externally-influenced input — out of this project's stated threat model (LAN/dependency), not a privilege boundary. | None. Confirms the task's "never writes inside `$DCS_INSTALL_PATH`" point: nothing in the write path ever touches the install directory, by construction (no code assembles a path under it). |
| `_toml_string`/`_toml_key` L897-899, L890-894 | Escape `\` and `"` only; do not escape/reject control characters (raw newline, other C0 codepoints) in the two free-text fields sourced from ED's Lua (`label`, `name`) | **Demonstrated** (see below): a label containing a literal `\n` renders a TOML value that spans multiple lines and fails `tomllib.loads` with `Illegal character '\n'`. TOML's own grammar refuses the unescaped newline, so this is a **hard parse failure at body-layer startup**, not a working key injection and not code execution — every numeric field (`device`/`cmds`/`args`) is already regex-constrained to digits before reaching the renderer, so only `label` and the element `name` are exposed at all. Source of both fields is ED's own shipped `clickabledata.lua` on the single user's local install — not network-reachable, not plausibly adversarial under this project's threat model, and not realistic content for an English cockpit hint string. | **Low-severity, not blocking** — filed as `BL-B91` (see below) rather than fixed in this pass. |
| Regex set (`_split_top_level`, `_extract_balanced`, `_ELEMENTS_REF_RE`, `_RAW_HINT_RE`, etc.) | Catastrophic-backtracking check per the task brief | All non-greedy capture groups (`.*?`) are either anchored by a following literal/quote or bounded by hand-rolled depth-tracking helpers (`_extract_balanced`, `_split_top_level`) rather than nested quantifiers (`(a+)+`-shaped patterns). No pattern here has the nested-repetition shape that causes exponential blowup. Input is a fixed, bounded ED file (~2200 lines, not attacker-supplied or network-received) — even a pathological regex here would be a local one-off slowdown on a dev machine, not a remotely triggerable DoS. Ran the full parser against all three fixture directories and the hand-built synthetic fixtures in the test suite without any anomalous runtime. | None. |

### Demonstration run (TOML control-character gap)

```
$ .venv/bin/python3 -c "... label='evil\nlabel = \"INJECTED\"\n[elements.pwn]\nx=1' ..."
PARSE FAILED: Illegal character '\n' (at line 17, column 14)
```

Confirms: fails closed (TOMLDecodeError), does not accept the injected key. Impact is "config
fails to load," not "code runs" or "a key gets forged."

### Other points from the task brief, checked directly

- **Never executes Lua** — confirmed, see table above.
- **No new dependency** — confirmed.
- **No GPL-3.0 material** — confirmed; DCS-BIOS is named only in prose/docstring, never read or
  imported by this tool.
- **No ED source committed in fixtures** — confirmed by reading all nine fixture `.lua` files:
  each carries its own header stating it is synthetic, written for this project, in ED's forms —
  not excerpts. Matches `review-stage0.md`'s own finding on this point.
- **Output path handling** — confirmed fixed default, operator-only override, never
  install-derived (see table).
- **Secrets/credentials** — none present; nothing in this diff reads or writes any credential,
  token, or key material.

### Finding outside this stage's scope — noted, not rated

`plan.md`'s Stage 2+ intends `label` (ED's hint strings) to eventually feed curated friendly names
that reach spoken/brain-facing text. If a later stage pipes `label` into an LLM-visible surface
(a prompt, a tool result) without the no-omniscience/escaping discipline the rest of body-layer
already applies, that would be the point to re-examine this field for prompt-injection risk, not
this one — Stage 0 only writes it into a config file nothing currently reads as instructions.
Flagging for whoever plans that stage; not a Stage 0 finding.

### Verdict

**APPROVED.**

One low-severity, non-blocking finding (TOML control-character escaping gap, demonstrated but not
exploitable beyond a clean parse failure) is filed as `[[BL-B91]]` rather than fixed in this pass —
risk communication below. Everything else in this stage's scope (no code execution of parsed Lua,
no writes outside the intended config path or inside `$DCS_INSTALL_PATH`, no new dependency, no
licence contamination, no committed ED source, no catastrophic-backtracking surface, no secrets)
checks out clean on direct inspection and, where practical, by running the code against adversarial
input myself rather than reading only.

### Risk Communication — BL-B91

**Finding:** `_toml_string`/`_toml_key` do not escape/reject control characters (raw newline and
other C0 codepoints) in the two ED-sourced free-text fields (`label`, element `name`); a literal
control character in either breaks the generated TOML, confirmed to fail `tomllib.loads` rather
than silently forging a new key.
**Location:** `body-layer/tools/generate_effector_registry.py:890-899`
**Probability:** low — requires ED's own shipped `clickabledata.lua` to contain a raw control
character in an English UI hint string or element name; not observed in any of the recon notes,
and not attacker-influenced under this project's LAN-only/dependency threat model.
**Impact:** low — a hard config-load failure at body-layer startup (a loud, visible error), not
code execution, not an arbitrary write, not a forged key (TOML's grammar refuses the unescaped
newline).
**Recommended action:** have `_toml_string`/`_toml_key` escape or, matching the parser's existing
fail-closed posture for every other field, mark the owning element `unhandled` rather than emit a
string the renderer cannot make syntactically valid.

Options:
  (A) Ignore — document acceptance of this risk.
  (B) Add to backlog — filed as `[[BL-B91]]` (`body-layer/ROADMAP/BL-B91.md`), done.
  (C) Fix now — I'll address it before continuing.
  (D) Stop — do not proceed until this is resolved.

Not yet decided by the user; `BL-B91` is `[ ]` open pending that call. This is the only finding
from this pass with no tracked item of its own before filing — see "Closing step" below.

### Closing step — every finding filed

This pass's one finding (the TOML control-character gap) is filed as `[[BL-B91]]`
(`body-layer/ROADMAP/BL-B91.md`, indexed in `body-layer/ROADMAP/body-layer-backlog.md`). No other
finding in this report carries an unfiled risk-matrix block.

### Memory queries run

`python3 .claude/scripts/memory-search.py` — no prior memory on this generator, TOML escaping, or
regex backtracking in this codebase ("not indexed yet," checked, nothing found to contradict or
build on). `.claude/scripts/gq.sh "Does the effector registry generator execute any Lua it parses,
or write outside the project?"` returned the BL-B90/DCS-BIOS community cluster (confirmed the
GPL-3.0/reference-only decision already documented in `aircraft-layer/research/
2026-10-21-dcs-bios-mi24p-9k113-controls.md`, read in full) — no hit contradicts anything found by
direct code reading in this pass.

A new memory file is not warranted from this pass alone: no recurring pattern yet (one occurrence),
no false positive to record, and the one real finding is already captured as a filed backlog item
rather than a lesson about *how* to review. If a second generator tool in this codebase is found
with the same unescaped-free-text-field gap, that would be the point to promote this into a
general `security` memory.
