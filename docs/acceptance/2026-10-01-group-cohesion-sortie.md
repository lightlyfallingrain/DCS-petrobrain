# Group cohesion redesign sortie

**Cockpit card (published):** https://claude.ai/artifact/Vxm6wiGGoP9stQQEYRpXRu — the same content
below, laid out for reading in glances. This file stays the source of truth.

**Branch: `fix/group-undermerging`** (not merged as of this card — DoD's mechanical gate, Reviewer,
Security and Performance have all passed; it is not yet on `main`):

```sh
git checkout fix/group-undermerging && git pull
```

## Why this card exists

The 2026-10-01 sortie produced the same eleven-unit group callout six times in a row, ~11 seconds
apart, changing only in the range clause — a dedup bug (fixed earlier the same day, already in
this branch) comparing the whole spoken sentence instead of its content. Fixing that exposed the
real question underneath it: *when* should a group's roster be re-spoken at all? This branch
answers that with a size-relative/kind-coherence cohesion rule (so the right contacts merge into
one group in the first place) and a delta taxonomy (so a re-disclosure says only what changed,
never the whole roster again).

## What should sound different tonight, in your own terms

- **The six-identical-lines defect is gone.** Dedup no longer keys on the range clause, so range
  drift alone will not re-trigger a full re-announcement.
- **Group composition says what changed, not the whole roster again.** A group you've already
  heard reported should go quiet unless something in the list below actually happened.
- **Articles are gone from class nouns.** "Armor and truck", not "An armor and a truck." If you
  hear "a armor" or "an armor," that's a regression — flag it specifically.

## Setup

Same three-process pattern as recent cards. From `run-scripts/` on the Mac, Windows collector
already running:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text-debug-view.sh --brain-client http --brain-url http://127.0.0.1:7796 \
    --detection-trace ~/dcs-detection-trace.jsonl
```

**Checked against this branch's actual committed script** (`run-scripts/run-crew-text-debug-view.sh`
as it exists on `fix/group-undermerging`, not copied from an older card): it already passes
`--speech-audio --speech-input --crew-text --f10-commands --audio-adapter-url
http://127.0.0.1:7795 --speech-log ~/dcs-speech.jsonl --eyesight-view --eyesight-view-radius-m
5000 --belief-truth-log ~/dcs-belief-truth.jsonl` on top of the invocation above — those are
already in the script, you don't need to add them. **It does not, as committed, pass
`--brain-client`/`--brain-url`/`--detection-trace` itself** — those three are added on the command
line above, as `$@` arguments the script forwards. (Your own working copy of this script may
already have local edits adding some of these as defaults — if so, drop whichever ones are
already there from the command above rather than passing them twice.) `--detection-trace` plus the
belief-truth log (already in the script) is what made today's diagnosis possible; without the
trace flag, the next report is anecdote, not evidence.

## What to listen for

### 1 — A new class joining is spoken

**Do.** Watch a group you've already heard reported (composition known) until a genuinely new
class of unit joins it — e.g. an armor group that a truck now joins.

**Expect.** A short delta naming just the new class, not a restatement of the whole group —
e.g. "Truck, in the group."

**Record.**
- [ ] Did the new-class arrival get spoken, and only the new part — not the full roster again?

### 2 — Another instance of a class already reported is silent

**Do.** Watch a group with, say, one truck already reported, until a second truck joins it.

**Expect.** Silence. "One more truck makes no difference" — your own worked rule.

**Record.**
- [ ] Did a second same-class, non-air-defence member join without triggering any new line?

### 3 — Another air-defence unit is always spoken

**Do.** Watch a group that already has one air-defence member (Shilka, SAM, etc.) until a second
one of that family joins — even a different type.

**Expect.** A delta is spoken, unlike case 2. "More air defence is always news," by your own
rule — even though it's "just another instance of a class already reported."

**Record.**
- [ ] Did the second air-defence arrival speak, where the equivalent truck/armor arrival in case 2
  did not?

### 4 — A leading-threat change speaks a short delta, not a restatement

**Do.** Watch a group where the leading (most dangerous) member changes — a new, more dangerous
unit joins, or the current leader is lost.

**Expect.** A short "Now leading: X" clause, not the full composition re-spoken.

**Record.**
- [ ] Did a leader change produce a short delta, or did it (wrongly) restate the whole group?

### 5 — A departure with nothing else changing is silent

**Do.** Watch a group lose a member (destroyed, lost from view) with no new arrivals and no leader
change.

**Expect.** Silence at the group level. (If the departure was a kill, you should still hear it from
that unit's own callout — just not a second mention from the group.)

**Record.**
- [ ] Did a pure departure stay silent at the group level?

## What is deliberately NOT in this build

**Damage/destruction narration** ("smoking", "burning") and **landmark anchoring** ("south of the
village") are both scoped to their own later plans — not here. You asked for both in conversation
today; they are real, wanted features, just not this branch. Do not fly listening for either —
their absence tonight is not a defect.

## Two approved behaviours that may still sound surprising in the air

- **Infantry merge eagerly, and can bridge non-infantry units into one group.** A BTR and a truck
  can end up in the same group as three infantry, because infantry has no distance backstop at
  all (your own direction: "ok to merge infantry too eagerly"). If a group looks like it's pulled
  in units that don't obviously belong together, check whether infantry is the bridge before
  calling it a miss.
- **The S-300 is not flagged as a single installation, so its own components do not all merge.**
  Only the S-125 and Kub sites get the flat 500 m installation cap; an S-300 battery's launcher
  and radar vehicles cohere (or not) under the ordinary size-relative rule instead, which may
  split a real S-300 site into more than one group.

## Pass criteria

The feature passes if cases 1-5 above each produce the expected sound (delta/silent as specified),
no "a armor"/"an armor" grammar defect is heard, and the two approved-but-surprising behaviours
read as expected rather than as noise once you know what to listen for.

## Bring back

1. Did each of the five taxonomy branches (new class, repeat non-air-defence, repeat air-defence,
   leader change, pure departure) sound the way this card says it should?
2. Any case where a group felt wrong — merged too eagerly, split too eagerly, or said too much or
   too little?
3. How did the infantry-bridging and S-300-not-merging behaviours actually read in the air?
4. The 500 m installation cap and the air-defence-class list are both one-source-of-evidence
   guesses — any read on whether either looks wrong against what you actually saw?

Anything that surprises you is worth more than anything on this list.
