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

**1. Which layers were touched, and what that means for restarting.** Work out the restart set from
the diff, against the subproject list in root `ROADMAP.md`'s status table — not from a list written
here, which would quietly omit a subproject added since and tell the user nothing needs restarting
when something does. For each touched subproject, its own `CLAUDE.md` says what process runs it and
how it is launched; that is where the current answer lives.

The rules that are *not* derivable from the diff, and are the ones worth stating explicitly:

- **A library imported in-process needs no restart of its own** — whatever imports it picks up the
  change on its next launch. Only call for a restart or rebuild if the change invalidates a *built
  artifact* (e.g. a region `.sqlite` that must be regenerated); say so explicitly, with the rebuild
  command, when it does.
- **A change to a deployed DCS-side script means DCS itself must be restarted**, not just the
  mission — Hook scripts load once at DCS application startup. Those files also have to be
  redeployed into `Saved Games\DCS\Scripts\...` first, per `aircraft-layer/WORKFLOW.md`.
- **A change to a long-running process means that process restarts, and only that one.** Do not
  escalate to restarting DCS unless a DCS-side file changed too.
- **Say what does *not* need restarting, explicitly.** "Aircraft layer / DCS unaffected — no restart
  needed there" saves the user real time; leaving it unsaid costs them a DCS restart they did not
  need. Naming the unaffected layers is as much the point of this section as naming the affected ones.

**2. The exact run command, as ONE copy-pasteable line — never multi-line with backslash
continuation.** **Read the flags off the subproject's own `CLAUDE.md` run section at the time you
write the card** (for the live logger, `body-layer/CLAUDE.md`'s "Running the live logger") — flags
get added, renamed and defaulted, so a flag list copied into this file would be wrong at the moment
it matters most. Include only the flags this specific feature needs, not every flag available.
Use a placeholder for the one value the user must supply themselves (`<windows-box-ip>`);
everything else should be a real, ready-to-paste value, taken from that run section and the
theatre/database the test actually uses rather than from an example.

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
