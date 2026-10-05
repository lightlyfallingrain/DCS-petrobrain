---
name: sortie-log-triage
description: Post-flight triage over body-layer's three sortie logs -- dcs-belief-truth, dcs-detection-trace, dcs-speech (.jsonl). Resolve the filenames first: pre-BL-11-Stage-5 they are single files every sortie appended to, so the flight is a region; once stamped, glob for the newest and take all three from the same stamp. Speech rate, contacts-vs-objects churn, objects carrying several contact ids, contact lifespans, gate-outcome histogram, cluster size by range. Use when the user brings back logs from a flight, instead of writing ad hoc python over them each time.
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

## Resolve the filenames — they may or may not carry a run stamp

**Both forms exist right now, so look before you read.** Per-run stamping is `BL-11` Stage 5, which
is **not on `main` yet** (branch `feature/bl11-tick-cost`, unmerged as of 2026-10-06). An earlier
version of this section stated stamping as current fact; it described an unmerged branch, which is
corrected here. Check which world you are in:

```sh
ls -t ~/dcs-detection-trace*.jsonl logs/dcs-detection-trace*.jsonl 2>/dev/null | head -3
```

- **A stamped name** (`dcs-detection-trace-20261006-143500.jsonl`) means the pilot is running
  `BL-11` Stage 5 or later: one file per run, and the rest of this section applies.
- **A bare name** (`dcs-detection-trace.jsonl`) means the pre-Stage-5 writers: **one file that every
  sortie has appended to since it was created**, so the flight you want is a *region* of it, not the
  whole file. That is why the 2026-10-05 analysis had to locate byte offset 2,448,471,603 in a
  3.55 GB file. Find the region before computing anything, or two sorties get averaged together and
  the result is fiction that looks like a finding.

Note also that Stage 5 moves the files from `~` into `logs/`, so the directory changes with the
name. The logger prints each resolved path to stderr as it starts, and **that line is the
authoritative answer to "where did it go"** in either world.

### Once stamping is in force

**`BL-11` Stage 5: each run writes its own file.** The path passed on the
command line is *not* the path written — the logger stamps the run's start time in before the
suffix, so `--detection-trace logs/dcs-detection-trace.jsonl` actually produces
`logs/dcs-detection-trace-20261006-143500.jsonl`. All three logs of one run share the same stamp,
so the stamp is also how you tell which three files belong to one sortie. The logger prints each
resolved path to stderr as it starts, and that line is the authoritative answer to "where did it
go".

So resolve the newest run rather than naming a file:

```sh
ls -t logs/dcs-detection-trace-*.jsonl | head -1
ls -t logs/dcs-belief-truth-*.jsonl    | head -1
ls -t logs/dcs-speech-*.jsonl          | head -1
```

**Take all three from the same stamp, not three independent newest-matches** — if a run was
restarted, the newest of each can come from different sorties, and a belief log joined against
another flight's trace produces findings that are pure fiction.

Why this changed: all three writers used to open with `"a"` and never roll, so one path accumulated
every sortie ever flown. The 2026-10-05 analysis had to locate byte offset 2,448,471,603 to find
that flight's region in a 3.55 GB file. **Logs from before 2026-10-06 are still single
accumulating files** — for those, the byte-offset approach is still the only way in, and the
unstamped names below are what they are called.

## Read a prefix, not the live file

Each file is read only up to the size it had when triage started. The user is frequently **still
flying** when they hand the logs over, so the files grow while the script runs, and two sections
computed over different amounts of the same file disagree in ways that look like real findings.
`--no-snapshot` lifts the cap and is correct only once the flight has ended.

No copy is made. An earlier version of this procedure copied the files first; the detection trace
is 2+ GB and copying it buys nothing a byte cap does not.

## What each section answers

**Belief vs truth** (`dcs-belief-truth-<stamp>.jsonl`, one row per contact per poll — the sanctioned
ground-truth-plus-belief join):

- *distinct contacts vs distinct objects*, and **objects carrying 2+ contact ids** — the contact
  churn / duplication signature. One real vehicle accumulating six contact ids over a sortie is
  what the pilot hears as the same unit reported again and again.
- *contact lifespan*, with the count alive under 30 s. A population of short-lived contacts means
  association is failing to re-acquire, not that there are many units.
- the four trip-wire flags the writer already computes, and the position-error distribution.

**Detection trace** (`dcs-detection-trace-<stamp>.jsonl`, one row per `check_visibility` call):

- *outcome histogram* — which gate decided each candidate's fate. `player_bubble` dominating is
  normal (it is the cheapest gate and runs first).
- *first-admitted range per object*, nearest ten — the "how close did he have to get" table.
- *objects seen but never admitted* — the "why did Petrovich not see that" list.
- *cluster size binned by range* — resolution clustering's behaviour as geometry changes.

**Speech** (`dcs-speech-<stamp>.jsonl`): disposition counts, then every utterance heard and **not** acted
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
