# Watch reporting sortie

A watched contact now talks back: it reports its own movement, whole-kilometre range crossings, and
believed weapon-envelope entry/exit, unprompted. `follow` becomes both a synonym for `watch` and a
new way to *name* which contact to watch by descriptor/clock/range.

**Branch: `feature/watch-reporting`** — not merged yet.

```sh
git checkout feature/watch-reporting && git pull
```

## Where this sits among the outstanding sorties

Three other milestones are already merged to `main` and unflown, with their own card:
`docs/acceptance/2026-09-23-eyes-and-voice-sortie.md` (binocular optic, voice command
completeness, precise position belief). There is also a separate probe card,
`docs/acceptance/2026-09-24-damage-and-firing-probes.md`, for damage/firing recon questions.

**This branch has not merged**, so it cannot ride the same flight as those three without checking
out `feature/watch-reporting` specifically — the main checkout will not be on `main` while you fly
this card. Two reasonable orders:

- Fly the eyes-and-voice card first on `main` (it has been waiting longest), then check out this
  branch for a second flight once you're ready to look at watch reporting specifically.
- Or fly this branch first, since `feature/watch-reporting` branched from a point that already
  contains all three merged milestones (`3409b66`, after `c398675`) — everything the eyes-and-voice
  card tests is present here too, so one sortie on this branch can plausibly clear both cards at
  once if you're willing to work through both lists in the same flight.

Either way, say which sortie cleared which card when you report back — the roadmap's live-acceptance
debt list tracks that per-item, not per-flight.

## Setup — nothing to redeploy

No Windows-side change. `Export.lua`, the Hook scripts, and the collector are untouched by this
branch (confirmed: the plan's Affected Modules list only body-layer and audio-adapter, and the
security review confirms no new dependencies). Same processes, same flags as the voice sortie:

- Windows: collector, and capture with `--ptt dcs`
- Mac: `run-scripts/run-audio-adapter.sh`, then `run-scripts/run-crew-text.sh` (already carries
  `--speech-audio --speech-input --crew-text --f10-commands --speech-log ~/dcs-speech.jsonl`)

body-layer 1177 tests, audio-adapter 198 (verified this session, not read off a docstring).

## Not testable, and why

- **The engagement-envelope trigger's practical value is gated on an optic that does not exist
  yet.** With only the naked eye and binoculars, class-level recognition of a SHORAD threat (the
  case this trigger targets) resolves at 500 m unaided / 1,750 m through binoculars — both *inside*
  a Shilka-class 3,704 m envelope. So **expect the danger call to fire from inside the envelope, not
  at its edge, for nearly everything it can recognise at all.** That is not a bug in this branch;
  it is the 9K113 sight not being modelled yet (deferred, `todo/todo.md`). The trigger and the data
  are correct; only the warning's lead time is short. Long-range SAMs (S-300-class) cannot be
  recognised at any range this feature reaches, by eye, with or without this branch — no warning
  for those is expected and correct, not a defect.
- **The class-level threat rollup only actually joins 3 of ~19 SAM/AAA rows** (Hoggit-vs-DCS naming
  mismatch, `body-layer/ROADMAP.md` backlog). A class-level classification for most SAM types will
  show **no danger/safe-from call at all** — silence, not a wrong number. Type-level recognition
  (a specific reporting name, not just a class bucket) is unaffected and works for every row.
  If you get a class-level classification on a SAM and hear nothing, this is very likely why —
  check what class it folded to, not whether the trigger is broken.
- **`OP_SRSAM`'s class-level envelope is driven by its longest-reaching member (S-125/SA-3, 25 km)**
  while the same bucket holds SA-8/9/13/15, some under 6 km. A class-level "danger" 4–7x earlier
  than the real member's envelope is expected for that bucket specifically, and tightens once
  type-level recognition resolves which one it actually is.
- **`follow`'s resolver has no live-sortie calibration.** The weights (`W_FOLLOW_CLOCK=0.6`,
  `W_FOLLOW_DESC_WRONG=10.0`, `FOLLOW_MATCH_FLOOR=3.0`) are self-consistent by construction
  (reviewed by hand-executing the arithmetic) but have never resolved a real multi-contact scene
  from your voice. A wrong pick or a refusal that should have matched is exactly what this flight
  is for finding.
- **Reports still answer from live belief only** — no inference, no memory of what a contact was
  doing a minute ago. That is BL-8, not built.

## 1 — Movement reporting. DO THIS FIRST

The cheapest trigger in the milestone (an event that already fired, newly spoken) — if this is
broken, check the simplest thing before anything else.

**Do.** Pick a moving ground contact. Say **"watch nearest"** (or **"follow nearest"** — they
should behave identically). Keep it in view while it changes direction, speeds up, or stops.

**Expect.** An unprompted callout naming the contact when its motion state changes — you did not
ask for a report, it volunteers one. `WATCH_REPORT_MIN_GAP_S` (8 s, uncalibrated) should keep it
from interrupting itself repeatedly for the same contact.

**Record.**
- [ ] Does watching a contact via `follow nearest` behave identically to `watch nearest`
- [ ] Does a motion change actually get spoken, unprompted, without asking for a report
- [ ] Does it ever repeat itself for the same contact faster than roughly every 8 seconds
- [ ] Does a contact watched *after* it already started moving still eventually report (it should
      speak on the *next* motion change, not the one it missed)

## 2 — Kilometre range crossings

**Do.** Watch a contact and either close on it or let it move, crossing a whole-kilometre mark
(5, 4, 3, 2, 1 km) while inside 5 km.

**Expect.** An unprompted callout as it crosses each kilometre boundary — not flapping back and
forth if it lingers near the boundary (a deadband derived from position uncertainty should prevent
that). A contact should **not** report a crossing for a boundary it was already inside of when you
started watching it — the first evaluation seeds silently.

**Record.**
- [ ] Do kilometre crossings actually get called out as the contact closes/opens
- [ ] Does it flap (announce the same boundary twice in quick succession) near a crossing point —
      it should not
- [ ] Does watching a contact already at, say, 2.3 km produce a spurious "crossed 3 km" callout —
      it should not

## 3 — Engagement envelope — THE PART WITH THE CAVEAT ABOVE

**Do.** Watch a SHORAD-class contact (Shilka/ZU-23-class AAA, or a short-range SAM) and approach it
from outside its envelope, or watch one already recognised at close range.

**Expect**, per the caveat above: **"Danger, &lt;unit&gt;..."** likely from well inside its actual
weapon envelope, not at the edge — because recognition, not geometry, is usually the limiting
factor with the optics that exist today. If you back away past 1.5x the envelope range, expect
**"Safe from &lt;unit&gt;..."** — the 1.5x margin is deliberate hysteresis, not a bug if the safe
call feels "late."

**Record.**
- [ ] Does a danger call ever fire at all, for anything
- [ ] Roughly how far inside the envelope was it when it fired — does that match "recognition-
      limited, not geometry-limited" or does it feel wrong even accounting for that
- [ ] Does "safe from" fire on retreat, and does the 1.5x margin feel reasonable or annoyingly late
- [ ] For a SAM class you expect danger from, does anything actually get said — silence may mean
      the class-join gap above, not a broken trigger (note the classification level/value you saw)

## 4 — `follow` as a targeting phrase — worth the most, least measured

**Do.** With two or more contacts in view of different types/bearings/ranges, try naming one:
**"follow armor"** · **"follow two o'clock"** · **"follow tank three km"** · a combination like
**"follow armor two o'clock three km"**. Also try the bare forms: **"follow nearest"**,
**"stop following"**, **"cancel follow"**.

**Expect.** It should watch the contact that best matches what you said, or (if nothing scores well
enough) say it cannot find a match rather than guessing — refusal is the correct behaviour when the
qualifiers don't clearly point at one contact. `"follow two o'clock"` alone (no descriptor) should
usually refuse rather than commit, since a bearing alone rarely narrows enough.

**Record.**
- [ ] Does `follow <descriptor>` with only one plausible match actually watch it
- [ ] With several plausible contacts, does the resolver pick a sensible one, or a wrong one
- [ ] Does an under-specified `follow` (e.g. just a clock position) correctly refuse rather than
      guess
- [ ] Does the confirm-band round trip work — if it asks you to confirm, does saying yes commit to
      the right contact

## 5 — The logs

```sh
cat ~/dcs-speech.jsonl
```

**Record.**
- [ ] Any `follow` utterance that fell through or mismatched
- [ ] Anything with disposition `fallthrough` you meant as a `follow`/`watch` command

## Bring back

1. Movement and range-crossing reports — do they actually interrupt unprompted, and at the right
   moments
2. Engagement envelope — does the recognition-limited short lead time (see caveat) match what
   fired, and does the class-join silence show up for any SAM you expected a call from
3. **`follow` as a targeting phrase — right pick, wrong pick, or correct refusal — this is the
   part with the least prior measurement and the most value in finding out**
4. Anything misheard or mismatched, from the speech log
5. Whether reporting a watched contact ever felt like noise rather than useful crew chatter

**Anything that surprises you is worth more than anything on this list.**
