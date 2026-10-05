---
name: sortie-log-triage
description: Post-flight triage over body-layer's three sortie logs -- dcs-belief-truth.jsonl, dcs-detection-trace.jsonl, dcs-speech.jsonl. Speech rate, contacts-vs-objects churn, objects carrying several contact ids, contact lifespans, gate-outcome histogram, cluster size by range. Use when the user brings back logs from a flight, instead of writing ad hoc python over them each time.
type: user-invocable
---

Triage one sortie's logs. Usage: `/sortie-log-triage`, or point it at specific files.

```sh
python3 .claude/skills/sortie-log-triage/scripts/triage.py           # the three default paths
python3 .../triage.py --skip-trace                                   # fast pass, skips the GBs
python3 .../triage.py --belief PATH --trace PATH --speech PATH
python3 .../triage.py --no-snapshot                                  # only after the flight ended
```

Stdlib only — no subproject venv needed. The detection trace is gigabytes and is streamed
line-by-line, never loaded whole.

## This is not `dcs-log-recon`

`dcs-log-recon` parses `aircraft_layer_debug.log` — Export.lua probe output from the DCS side.
This skill reads the three JSONL files **body-layer** writes on the Mac side. Different files,
different producers, no overlap.

## Read a prefix, not the live file

Each file is read only up to the size it had when triage started. The user is frequently **still
flying** when they hand the logs over, so the files grow while the script runs, and two sections
computed over different amounts of the same file disagree in ways that look like real findings.
`--no-snapshot` lifts the cap and is correct only once the flight has ended.

No copy is made. An earlier version of this procedure copied the files first; the detection trace
is 2+ GB and copying it buys nothing a byte cap does not.

## What each section answers

**Belief vs truth** (`dcs-belief-truth.jsonl`, one row per contact per poll — the sanctioned
ground-truth-plus-belief join):

- *distinct contacts vs distinct objects*, and **objects carrying 2+ contact ids** — the contact
  churn / duplication signature. One real vehicle accumulating six contact ids over a sortie is
  what the pilot hears as the same unit reported again and again.
- *contact lifespan*, with the count alive under 30 s. A population of short-lived contacts means
  association is failing to re-acquire, not that there are many units.
- the four trip-wire flags the writer already computes, and the position-error distribution.

**Detection trace** (`dcs-detection-trace.jsonl`, one row per `check_visibility` call):

- *outcome histogram* — which gate decided each candidate's fate. `player_bubble` dominating is
  normal (it is the cheapest gate and runs first).
- *first-admitted range per object*, nearest ten — the "how close did he have to get" table.
- *objects seen but never admitted* — the "why did Petrovich not see that" list.
- *cluster size binned by range* — resolution clustering's behaviour as geometry changes.

**Speech** (`dcs-speech.jsonl`): disposition counts, then every utterance heard and **not** acted
on, with confidence and match ratio. That list is the single most useful one for recognition bugs,
because an utterance matching no command is otherwise unobservable.

## What it deliberately does not do

**It does not read what Petrovich actually said.** There is no spoken-line log — the callouts go
to stdout (and to the overlay / TTS sinks). When the question is about *speech rate* or a specific
line the pilot heard, that text has to come from the user's paste or the captured stdout; the
logs here answer who was *known*, not what was *said*. Join them by `t_sim`.

## Both 2026-10-04 defects came out of these queries

The grouping under-merge and the contact churn were both found this way, and the script reproduces
them on that sortie: 102 of 258 objects carried 2+ contact ids, and 163 of 247 contacts lived
under 30 s. Those two numbers are the house style for "is this a perception problem or a policy
problem" — high churn with low per-object range error points at association/policy, not at the
gates.
