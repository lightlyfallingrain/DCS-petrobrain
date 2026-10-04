# Contact-report flood sortie

**Cockpit card (published):** https://claude.ai/artifact/VJZnmdF3aqxhVGZea3iKN4 — the same content
below, laid out for reading in glances. This file stays the source of truth.

**Branch: `fix/contact-report-flood`** (not merged as of this card — Reviewer and Security have
both approved; it is not yet on `main`):

```sh
git checkout fix/contact-report-flood && git pull
```

## Why this card exists

Mid-flight, 2026-10-04, your own words: *"when there are units around, I hear a near constant
stream of contact reports. It becomes noise, there is no signal. It also feels like many of those
reports were about the same units."* You were right about the same units — the naked-eye gaze
sweep's merge logic abandons the contact identities it doesn't inherit when several already-known
contacts cluster into one supercluster; those abandoned identities decay to `lost`, and the same
vehicles get re-founded under fresh ids shortly after, each earning its own "contact detected"
line. On the sortie that found this, 50 real objects had produced 34 distinct contact ids.

This branch suppresses the *speech* for a freshly-founded contact when an existing, still-tracked
contact is spatially and classification-plausibly the same real thing — it changes nothing about
what Petrovich believes or remembers, only whether a re-founding gets spoken aloud.

## What should sound different tonight, in your own terms

- **Roughly half the first-sighting chatter should be gone.** On the real sortie reconstruction
  this fix is measured against, 17 of the 34 contact-id foundings would now be suppressed.
- **Genuinely simultaneous distinct sightings are unaffected.** In the sortie's own six-vehicle
  cluster, the four vehicles that founded together each still speak once — the fix never silences
  two things that showed up at the same moment.
- **A re-founding of something you already heard about should go quiet.** The one later
  re-founding echo in that same cluster is now silenced.

## What is deliberately unchanged

- **Group lines are untouched.** "A couple of contacts, eleven o'clock" is a different event from
  an individual contact's first-sighting line and this branch does not touch it.
- **A contact genuinely coming back is still announced.** `CONTACT_REACQUIRED` — the same contact
  id, gone fully quiet, then showing up again — is never suppressed by this fix. If something you
  already lost returns, you should still hear it.

## The known cost, so you can judge it in the air

**A genuine split can look exactly like a merge-echo at this layer, and the fix cannot tell them
apart.** If a cluster that was never merged simply resolves into two separate things a moment
later, that split's own "contact detected" line can also go quiet — not because it's wrong to
speak, but because the mechanism that silences a merge-echo has no way to distinguish the two
cases. This is a known, accepted tradeoff, not a bug: the alternative (building per-member
identity tracking to tell them apart) has been priced and rejected twice already for unrelated
reasons.

**Suppression is one-shot and permanent for the sortie.** Once a re-founding is suppressed, it is
never retried or spoken later that flight — though the contact itself is still tracked, and you can
always ask "report" to hear about it directly.

## Setup

Same three-process pattern as recent cards. From `run-scripts/` on the Mac, Windows collector
already running. **This branch's own `run-crew-text-debug-view.sh` already carries
`--detection-trace` and `--belief-truth-log` built in** — you do not need to add them on the command
line this time:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text-debug-view.sh
```

**Checked against this branch's actual committed script** (`run-scripts/run-crew-text-debug-view.sh`
as it exists on `fix/contact-report-flood`): it passes `--speech-audio --speech-input --crew-text
--f10-commands --audio-adapter-url http://127.0.0.1:7795 --speech-log ~/dcs-speech.jsonl
--eyesight-view --eyesight-view-radius-m 5000 --belief-truth-log ~/dcs-belief-truth.jsonl
--detection-trace ~/dcs-detection-trace.jsonl --brain-client http --brain-url
http://127.0.0.1:7796` on its own, with no extra arguments needed from you. **Your own local copy
of `petrobrain.env` (gitignored, not checked into this branch) supplies `$DCS_COLLECTOR_IP` and is
assumed already set up the way your other recent sorties have used it** — this card describes what
the committed script does, not your own env file's contents, since that's yours and this card
can't see it.

**`feature/silence-command` is also on `main` and flyable tonight.** It's the manual half of
quieting the cockpit — say "silence" to stop a specific line of chatter yourself — while this
branch is the automatic half. Worth trying both together: this fix should mean you reach for
"silence" less often in the first place.

## What to listen for

### 1 — A busy area sounds less repetitive

**Do.** Fly into an area with several ground units close together — the kind of scene that
produced the near-constant stream you described.

**Expect.** Fewer "contact detected" lines overall for the same scene, without obviously losing
track of anything that's actually there.

**Record.**
- [ ] Did the chatter in a busy area feel noticeably reduced?

### 2 — A cluster's first sighting(s) still speak

**Do.** Watch a group of vehicles as they're first detected together.

**Expect.** Each genuinely distinct vehicle spotted in that first moment should still earn its own
line — the fix should not swallow a real, simultaneous sighting.

**Record.**
- [ ] Did the first sighting(s) of a cluster still come through?

### 3 — A re-founding near a still-tracked contact goes quiet

**Do.** Watch for a contact's naked-eye detection to blink in and out (a dropped/re-founded id) near
other contacts that are still being tracked.

**Expect.** Silence on the re-founding — no fresh "contact detected" for what is really the same
vehicle you already heard about.

**Record.**
- [ ] Did you notice any case where something seemed to be re-announced that you were sure you'd
  already heard about — and if so, did suppressing or not-suppressing feel right?

### 4 — A contact that actually goes away and comes back is still announced

**Do.** Watch a contact go fully `lost` (out of view/range long enough) and then come back under
what should be the same tracked identity.

**Expect.** You should still hear it announced as returning — this path (`CONTACT_REACQUIRED`) is
untouched by this fix.

**Record.**
- [ ] Did a genuine reacquisition after a real gap still get announced?

### 5 — Listen for a missed split

**Do.** Watch for any moment where a group you thought was one thing turns out, on later
inspection (binoculars, `report`, closing range) to actually have been two distinct things the
whole time — and that second thing never got its own "contact detected" line.

**Expect.** This is the known, accepted cost above — it may happen occasionally. You're listening
for *how often*, not for whether it's "wrong."

**Record.**
- [ ] Did you ever catch a case where a real second contact seemed to go unannounced?

## Pass criteria

The feature passes if the busy-area chatter is noticeably reduced, genuinely simultaneous sightings
and true reacquisitions are unaffected, and any missed-split cases you notice feel occasional
rather than routine.

## Ask for the trace afterwards

The 17-of-34 figure above is a retrospective reconstruction built from this sortie's own recorded
belief states, not a byte-for-byte replay of the raw detections — **your next flight is the first
real measurement of this fix, not a repeat of one already taken.** Please keep
`--detection-trace`/`--belief-truth-log` running (they already are, per the setup above) and bring
back `~/dcs-detection-trace.jsonl` and `~/dcs-belief-truth.jsonl` afterwards so the actual
suppression count from this flight can be checked against the 17/34 estimate.

## Bring back

1. Did the busy-area chatter actually feel quieter, or did it not change much?
2. Any specific moment that sounded wrong — either a report you were sure was a repeat, or a case
   where something felt like it went unannounced that shouldn't have?
3. How did flying with both this fix and "silence" (already on `main`) together feel — did you
   reach for "silence" less than usual?
4. The detection-trace and belief-truth logs from this flight, so the real suppression count can be
   measured against the 17/34 estimate above.

Anything that surprises you is worth more than anything on this list.
