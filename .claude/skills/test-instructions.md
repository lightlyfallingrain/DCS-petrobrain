---
name: test-instructions
description: Generate clear, precise live-test instructions for the user after a feature/fix is DoD-passed — what changed, what needs restarting, the exact copy-pasteable run command, and what to verify
type: user-invocable
---

Usage: `/test-instructions [featurename]`. If no `featurename` is given, use the current branch's
plan directory (`plans/<current-branch-derived-name>/`) or ask the user which feature.

This produces the message a user actually needs to go test a change live — not a restatement of
the plan, not a generic checklist. Read before writing anything:

- `plans/<featurename>/plan.md` — what was built and why, its acceptance criteria
- `plans/<featurename>/dod-check.md` — DoD's own Acceptance Testing Plan if one was already written; reuse and tighten it rather than inventing a second, possibly-inconsistent one
- `plans/<featurename>/review.md`/`implementation.md` — anything the Reviewer/Implementer flagged as needing live confirmation
- `git diff main...<branch> --stat` (or the branch's own commit range) — the actual set of changed files, which is more reliable than the plan's prose for determining scope

## What to determine before writing the instructions

**1. Which layers were touched, and what that means for restarting:**

- `world-model/src/**` changed → no running service to restart; `body-layer`/`aircraft-layer` processes import world-model fresh on each launch. Only note a restart if the change requires a *rebuilt region `.sqlite`* (rare — say so explicitly if a rebuild command is needed).
- `aircraft-layer/dcs-export/Export.lua` or Hook scripts (`*.dlg`, `Hooks/*.lua`) changed → **DCS itself must be restarted** (Hook scripts load once at DCS application startup, not per-mission) and the files must be redeployed to `Saved Games\DCS\Scripts\...` per `aircraft-layer/WORKFLOW.md` first.
- `aircraft-layer/src/**` (collector) changed → **the Windows collector process must be restarted** (`python -m collector`); Export.lua/DCS itself does not need restarting unless Export.lua also changed.
- `body-layer/src/**` changed → **no separate restart step** — the user just (re)launches `python -m logger` fresh, which is what they'd do to start a test session anyway. Say this explicitly ("no restart needed beyond relaunching the logger") so the user doesn't waste time restarting DCS or the collector unnecessarily.
- If nothing outside `body-layer/` changed (the common case for belief-layer bug fixes and most BL-x milestones), state plainly: **"Aircraft layer / DCS unaffected — no restart needed there."**

**2. The exact run command, as ONE copy-pasteable line — never multi-line with backslash
continuation.** Base it on `body-layer/CLAUDE.md`'s "Running the live logger" section for the
correct flags (`PYTHONPATH`, `--aircraft-layer-url`, `--theatre`, `--world-model-db`,
`--console`/`--overlay`/`--crew-text`/`--brain-client` as relevant to what's being tested — check
which flags this specific feature needs, don't include ones it doesn't). Use a placeholder only
for the one value the user must fill in themselves (`<windows-box-ip>`); everything else should be
a real, ready-to-paste value already known from this project's conventions (e.g.
`../world-model/data/world-model/syria-full.sqlite`, `--theatre Syria`).

**3. Test cases specific to what changed** — pull from the plan's acceptance criteria and any
Decisions the user made, not generic boilerplate. Each test case: one line for the scenario/action,
one line for what a pass looks like. If the plan or dod-check.md already has a live-acceptance
script, tighten and reuse it rather than reinventing one that might drift from it.

**4. Verification / pass criteria** — a short, unambiguous list the user can check off. Include a
regression spot-check line when the change touches shared machinery (e.g. "confirm classification/
overlay behavior from before is unaffected") — copy the pattern already established in this
project's own DoD acceptance-testing sections.

## Output format

```
## <Feature name> — live test

**Layers affected:** <one line — e.g. "body-layer only, no restart needed beyond relaunching the logger" or "aircraft-layer collector changed, restart it before testing">

**Setup** (only if something needs restarting/redeploying — omit this section entirely if nothing does):
<numbered steps, only the ones actually needed>

**Run:**
```
<single-line copy-pasteable command>
```

**Test cases:**
1. <scenario> — <what a pass looks like>
2. ...

**Pass criteria:** <short unambiguous checklist>
```

Keep it tight — this is meant to be read and acted on in under a minute, not a document. Do not
pad it with restated plan prose; every line should be something the user needs in order to
actually run the test.
