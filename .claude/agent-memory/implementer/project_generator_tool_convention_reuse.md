---
name: project-generator-tool-convention-reuse
description: body-layer/tools/generate_defaults.py's dev-tool conventions (static parse, check-mode default, --write, GENERATED header, staleness test) are the reusable pattern for any new "render committed derived data from source" tool in this subproject -- confirmed working a second time on render_switch_reference.py.
metadata:
  type: project
---

body-layer already has one tool following this shape: `tools/generate_defaults.py` renders
`config/defaults.toml` from `tuning.*` declarations in `src/`, with: stdlib-only static parsing
(never imports/executes the thing it reads), a check-mode default (exit 1 if the committed output
is stale), `--write` to regenerate, a `# GENERATED ... DO NOT HAND-EDIT` header, and a dedicated
`tests/test_<tool>.py` that shells out to the tool in check mode and asserts exit 0 -- the same
staleness-guard shape as `test_tuning_defaults_toml.py`.

On BL-B90 Stage 1, `tools/render_switch_reference.py` (rendering `config/sequences/
switch-reference.md`, a human-readable control reference, from `config/effectors-raw.toml` +
`config/sequences/effectors.toml`) copied this shape exactly and it required no adaptation:
same `argparse` with one `--write` flag, same read-current-vs-rendered comparison, same
`test_render_switch_reference.py` subprocess-based staleness test. Root CLAUDE.md's "do not
reinvent the wheel" rule names exactly this kind of reuse.

One addition this tool needed that `generate_defaults.py` didn't: the GENERATED header names the
*source*'s own build string, parsed out of the raw dump's own header comment (`# Source: ...,
DCS <build>`) rather than hard-coded or passed as a CLI flag -- so the reference's header can
never drift from what dump it was actually rendered against, even across DCS updates. Worth
checking for on the next tool in this family: does the source already carry its own provenance
string that the renderer should quote rather than restate.
