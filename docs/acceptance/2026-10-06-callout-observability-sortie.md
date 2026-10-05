# Callout observability gate sortie

**Cockpit card (published):** https://claude.ai/artifact/N4CGoNx5xaMdXW8QD3PwMw — the same content
below, laid out for reading in glances. This file stays the source of truth.

**Branch: `fix/callout-observability-gate`** — DoD passed on fixtures 2026-10-06, Reviewer approved
over two rounds, **not merged**. From the main checkout:

```sh
git checkout fix/callout-observability-gate
```

(Verified: the branch exists and its tip is `304a367`. It is not on `main`, so `main` still has the
defect.)

## Why this card exists

From your 2026-10-05 sortie: *"unit 7 o'clock, which is late by definition because Petrovich can't
even see 7 o'clock"*. You read it as lateness. It was not — it was a correctness defect, and it is
the one thing on `BL-11`'s list you could actually hear.

Of 357 spoken lines that flight, **20 named clock hour 5, 6 or 7** — hours his own cockpit mask
(`rear_cutoff_deg = 130°`) declares unviewable — with a classification attached. Three of those 20
were answers to a `report` command you gave, within 4.4 seconds. **So 17 were unprompted**: he
volunteered a position *and* an identification for something he could not see. That is the
no-omniscience invariant broken out loud.

The 2026-09-27 fix built the right gate and put it in a place where it could never be finished: at
event *emission*. Group disclosure mints no event at all, so no emission-site gate could ever have
reached it. The gate now sits at the single point where anything gets spoken, and it asks about the
**contact** rather than the kind of line — so it reaches every kind that arrives there, including
the three nobody had enumerated.

## The observable is an ABSENCE — and one deliberate exception

This is the part worth reading twice before you fly, because it is easy to score backwards.

- **Nothing unprompted should ever name 5, 6 or 7 o'clock again.** You are listening for lines that
  *do not happen*. There is no new sound to notice.
- **`report` will still answer about the rear hemisphere, on purpose.** If you say "report" and hear
  *"unit 7 o'clock, very close is Tigr"*, **that is correct behaviour, not a failure.** Belief
  survives the aircraft turning away, and you asked. That path
  (`CrewConsole._handle_report`) was deliberately left untouched — it is where 3 of the original 20
  lines came from.
- So the test is: **unprompted = never a rear hour. Asked = still answered.** If you hear a rear
  hour, the only question that matters is *did I just ask for it?*

## This silences; it does not re-time

The 17 lines become **unspoken, not spoken later**.

- The contacts are still believed, still decaying normally, still in the debug/eyesight view.
- They are still answerable by `report` at any time.
- A masked candidate is *deferred* rather than consumed, so if the bearing comes back within ten
  seconds he will speak. **Past ten seconds it is dropped**, because the grace window happens to
  equal the candidate's maximum age (both 10.0 s).

**Whether some of those lines should reach you another way is an open product question and nobody
has answered it.** An "I've lost sight of it" marker is the obvious candidate. This pass
deliberately did not decide it. If flying it makes the silence feel like a loss rather than a
relief, that is the single most useful thing you can bring back.

## The one thing to actively provoke

**A watched air-defence contact going astern while its engagement envelope starts covering you.**

That path — `CONTACT_ENGAGEMENT_CHANGED` — is **exempt** from the gate and must still speak
(*"Danger, …"*, and with world enrichment it also speaks the believed hour, range and unit type:
*"Danger, ZU-23-3, six o'clock, 1.0 km."*). It is the riskiest judgement on the branch.

**Do.** `watch nearest air defence` on a AAA/SAM site. Fly past it and put it behind you — hour 5,
6 or 7. Then fly in close enough that you are inside its firing envelope.

**Expect.** He speaks. If he goes silent there, the exemption is not working and that is a bug
worth reporting immediately.

**Why it is exempt, in one line:** an envelope change is a threat cue about something he already saw
and you already asked him to watch, derived from that belief plus your own position — and because
the grace window equals the maximum age, gating it would lose the warning *permanently*, not late.
An astern SAM that starts being able to shoot you would simply go quiet.

## Two decisions you did not make, and can overrule

Both are in `todo/questions.md`'s "Decided without you" section (commit `156f965`).

1. **The `CONTACT_ENGAGEMENT_CHANGED` exemption above was decided in the review loop, on the
   Reviewer's recommendation. You were not consulted and have not ruled on it either way.** Several
   documents on this branch were corrected today for claiming your authority on it. Reversing it is
   a one-line change (empty the exempt set) — the cost of reversing is that a watched astern threat
   goes silent instead of warning you.
2. **The gate covers every other templated kind, not just the two that misfired.** Five of six
   kinds plus group disclosure; three of those five are newly gated here
   (`CONTACT_CLASSIFICATION_CHANGED` — the measured defect — plus `CONTACT_DETECTED` and
   `CONTACT_REACQUIRED`). The last two are close to a no-op, since both perception channels already
   respect the mask when a contact is first founded. What it does change: **a contact founded ahead
   of you and spoken about several seconds later from astern now goes quiet instead of arriving
   late.** Narrowing the gate back to the two kinds that misfired is a one-line change if you would
   rather hear it late than not at all.

## One number shipped untuned, and it now carries more weight

`CALLOUT_OBSERVABILITY_GRACE_S = 10.0` — ten seconds of grace from the last *confirmed* sighting,
so a believed bearing that has drifted a few degrees past the cutoff while the contact is genuinely
observable does not get silenced. It is an **untuned starting value by its own docstring**, and this
fix makes it load-bearing for three more paths than it was.

**Because it equals `CALLOUT_MAX_AGE_S` (also 10.0), anything masked for over ten seconds is dropped
rather than deferred.** Nobody has changed either number. A sortie can measure them; this one is the
first that would.

## Setup

Same three-process pattern as recent cards. From `run-scripts/` on the Mac, Windows collector
already running:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text-debug-view.sh
```

**Read from this branch's own committed script**, not from memory:
`run-scripts/run-crew-text-debug-view.sh` passes `--speech-audio --speech-input --crew-text
--f10-commands --audio-adapter-url http://127.0.0.1:7795 --speech-log ~/dcs-speech.jsonl
--eyesight-view --eyesight-view-radius-m 5000 --belief-truth-log ~/dcs-belief-truth.jsonl
--detection-trace ~/dcs-detection-trace.jsonl --brain-client http --brain-url
http://127.0.0.1:7796` on its own, with `--theatre Syria` and the `syria-full.sqlite` store. No
extra arguments needed from you. Your own `petrobrain.env` (gitignored) supplies
`$DCS_COLLECTOR_IP`.

**UNVERIFIED — the three processes above were not launched for this card.** They need the Windows
box and a live DCS session. The script's *contents* are quoted from the file as committed on this
branch; whether it starts cleanly tonight is what you will find out.

**Note on the log filenames, because the triage tooling currently disagrees with this branch.** The
per-run stamping (`dcs-speech-<stamp>.jsonl`) is `BL-11` Stage 5 and lives on the unmerged
`feature/bl11-tick-cost`. **On this branch there is no stamping** — checked: nothing in
`body-layer/src` writes a timestamp into a log path — so all three logs **append to the plain
accumulating files** `~/dcs-speech.jsonl`, `~/dcs-belief-truth.jsonl`,
`~/dcs-detection-trace.jsonl`. Note the file sizes before you start, so this flight's region can be
found afterwards.

### If you want to see the gate work without flying

On the Mac, from the repo with this branch checked out. This was run for this card and is the real
output:

```sh
cd body-layer
.venv/bin/pytest tests/test_callouts.py -q -k "masked_bearing or observability or masked"
```

```
.......                                                                  [100%]
7 passed, 50 deselected in 0.13s
```

(The whole suite is `.venv/bin/pytest tests -q` → `1475 passed, 4 xfailed in 12.09s`.)

The two tests that carry the judgement by name:

- `test_classification_change_is_silent_about_a_cockpit_masked_bearing` — the defect, now silent.
- `test_engagement_change_speaks_about_a_cockpit_masked_bearing` — the exemption, still speaking.
  Emptying the exempt set makes this one fail with
  `assert [] == ['Danger, ZU-23-3 Sergey.']`, which was run rather than assumed.

## What to listen for

### 1 — No unprompted rear-hemisphere callout, all flight

**Do.** Fly normally through populated areas. Let units pass behind you — overfly a convoy, turn
away from a position you just passed.

**Expect.** Silence about them once they are behind you. No *"unit 7 o'clock, very close is …"*
unless you asked.

**Record.**
- [ ] Did you hear **any** unprompted line naming 5, 6 or 7 o'clock? (If yes: what was it, and were
  you sure you had not just said "report"?)

### 2 — `report` still answers about what is behind you

**Do.** Pass a unit, put it clearly astern, then say "report".

**Expect.** He answers, including about the rear hemisphere. This is deliberate.

**Record.**
- [ ] Did `report` still tell you about things behind you?
- [ ] Did that feel right, or did it feel like a contradiction with his new silence?

### 3 — The exemption: an astern threat still warns you

**Do.** `watch nearest air defence`, fly past it so it sits at 5/6/7 o'clock, then close until you
are inside its envelope.

**Expect.** *"Danger, …"*, spoken, with the hour and range.

**Record.**
- [ ] Did he warn you? (Silence here is the single most important failure on this card.)
- [ ] Hearing a *"Danger, ZU-23-3, six o'clock"* about something he cannot see — does that feel
  right to you, or does it feel like the same omniscience you asked to be fixed? **This is the
  decision you are being asked to ratify or overrule.**

### 4 — Does the new silence cost you anything?

**Do.** Nothing extra. Notice whether a scene ever feels emptier than it is — something you knew
was back there and expected him to mention.

**Expect.** This is the open product question, not a bug. The contact is still believed and
`report` still knows about it.

**Record.**
- [ ] Any moment where the silence felt like a loss rather than a relief?
- [ ] Would an "I've lost sight of it" marker have helped there, or would it just be more chatter?

### 5 — The overflight case, which is new behaviour

**Do.** Watch for a contact he spots ahead of you that you then fly straight over.

**Expect.** Previously he might have announced it several seconds later, from astern. Now that
announcement goes **quiet** instead of arriving late.

**Record.**
- [ ] Did you notice first sightings going missing on overflight — and would you rather have heard
  them late?

### 6 — The ten-second window

**Do.** Nothing deliberate. Notice whether lines ever arrive *just* after something slipped behind
you.

**Expect.** Within ten seconds of his last confirmed look he will still speak; past that it is
dropped. Both numbers are first guesses.

**Record.**
- [ ] Across the flight, did the silence feel too eager, too slow, or about right?

## Pass criteria

It passes if **no unprompted callout names hour 5, 6 or 7 all flight**, `report` still answers about
the rear hemisphere, and a watched air-defence contact astern still says *"Danger"* when you enter
its envelope. Item 4's answer is product input, not a pass/fail.

## Bring back

1. Any unprompted 5/6/7 o'clock line at all — that is a straight failure, so the exact words and
   whether you had just asked for a report.
2. Whether the astern *"Danger"* warning fired. And whether you want to keep that exemption, or have
   the gate cover it too.
3. Whether the gate should stay broad or narrow back to the two kinds that misfired (decision 2
   above) — did a missing overflight callout bother you?
4. Whether the new silence ever felt like a loss, and whether a "lost sight of it" marker would
   earn its place.
5. The three logs (`~/dcs-speech.jsonl`, `~/dcs-belief-truth.jsonl`, `~/dcs-detection-trace.jsonl`,
   plus the byte offsets you noted at start) so the 17-lines-to-zero claim can actually be measured
   rather than assumed.

Anything that surprises you is worth more than anything on this list.
