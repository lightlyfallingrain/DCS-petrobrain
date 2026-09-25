# Eyes and voice sortie

> **FLOWN AND CLOSED, 2026-09-25** (user direction). This sortie produced most of that day's fixes rather than a clean pass: the callout heard while scanning the other way, cancel resurrecting a superseded scan, range crossings indistinguishable from fresh sightings, and the outpost fragmenting into 18 contacts. All merged to `main`. Kept for the record; do not re-fly it.

Two milestones, flown together because they are one loop in the cockpit: **he looks, he tells you
what he sees, you tell him where to look.**

**Branch: `feature/binocular-optic`** (it carries both).

```sh
git checkout feature/binocular-optic && git pull
```

| | what changed |
|---|---|
| **Binoculars** | he raises them at the end of a scan pass to resolve a contact, or to search a commanded sector — and is nearly blind while glassed |
| **Commands** | 20 recognised voice commands that silently did nothing now act; `scan north` finally moves his eyes; o'clock scans exist |

body-layer 1076 tests, audio-adapter 179, aircraft-layer 175.

---

## Setup — nothing to redeploy

**No Windows-side change at all.** `Export.lua`, the Hook scripts and the collector are untouched
by this work, so whatever is already deployed stays. Same processes, same flags as the voice
sortie. Only the Mac side has new code, and only via `git pull`.

Run as before, with `--speech-log` (already in your run script):

- Windows: collector, and capture with `--ptt dcs`
- Mac: the adapter with `--host 0.0.0.0 --target aircraft-layer --whisper-model …`, and the logger
  with `--crew-text --overlay --f10-commands --speech-input --speech-audio --speech-log …`

**Add `--detection-trace ~/eyes-sortie.jsonl` to the logger this time.** With binoculars in play,
"why did he not see that" has a new possible answer — *he was glassing something else* — and the
trace is the only thing that can tell that apart from a detection failure.

---

## Not testable, and why

- **The nine `scan <clock>` tokens are unbenched.** No corpus recording exists for them, so their
  recognition accuracy on your voice is unmeasured. If they mishear, that is a *recognition* gap,
  not a wiring one — the speech log will show which.
- **A binocular search is not triggered by an o'clock scan.** Deliberate: there is no obviously
  correct sweep half-width for a single 30° leg. So "scan 3 o'clock" steers his eyes but will not
  make him glass that sector.
- **Reports answer from live belief only.** No inference, no "it was heading north". That is BL-8's
  memory layer, not built.

---

## 1 — Reports, from a hover. **DO THIS FIRST**

Static, so nothing depends on the optic cycle. If reports are broken, everything later reads as
broken too.

**Do.** Hover in sight of a few units. Then, in order: **"report"** · **"report three o'clock"** ·
**"report north"** · and one direction you are pointing *away* from.

**Expect.** A situation answer; a per-sector answer; **"Three o'clock, clear."** where there is
nothing; and for the direction behind you, **"Can't see south."** — not "clear".

That last distinction is the most important line in the milestone. *Clear* claims a look; behind
the cockpit mask he cannot look, and saying "clear" there would be omniscience wearing a different
hat.

**Record.**
- [ ] Does `report` answer at all
- [ ] Is a sector report about the right sector
- [ ] "clear" where empty, "can't see" where blind — never swapped
- [ ] How long from release to the first word of the answer
- [ ] Does a multi-contact report run too long to sit through

---

## 2 — Telling him where to look

**Do.** **"scan north"** · **"scan one o'clock"** · **"scan bearing three two zero"**.

**Expect.** All three move the gaze cone on the overlay. `scan north` is the one that **never
worked before** — it registered a task, said "Scanning north", and he carried on free-scanning.
The numeric bearing quantises to the nearest compass sector, and **the readback names the sector he
actually adopted**, not the number you said.

**Record.**
- [ ] Does the overlay cone actually move for each of the three
- [ ] Does the numeric readback name a sector, and is it the right one
- [ ] Do the o'clock scans get recognised at all (unbenched — expect some misses)
- [ ] Does a commanded scan still revert to free scan when you cancel

---

## 3 — Binoculars. **THE PRIZE**

The whole point of this milestone, and the part with no measurement behind it.

**Do.** Fly toward a group of units from ~2 km and just watch. Do not command anything.

**Expect.** At the *end* of a scan pass — not the instant he sees something — he raises binoculars,
looks, and goes back to scanning. While glassed he is nearly blind to everything else. He does not
announce it; **the overlay is how you know.**

The band that matters: he glasses a contact he knows only as "ground" when it is between roughly
**500 m and 1750 m** — that is where binoculars change the answer for a vehicle. Closer than that
the naked eye gets there anyway; further, the binoculars cannot either.

**Record.**
- [ ] Does he ever raise them at all
- [ ] Does it happen at a scan boundary, or mid-sweep
- [ ] Roughly how often, and does that feel like a crewman or like a tic
- [ ] Does anything get *missed* while he is glassed — and does that feel like a fair cost
- [ ] Does hard manoeuvring visibly put them down

---

## 4 — The cost, deliberately provoked

**Do.** While he is glassed, do something that should interrupt: speak any command, or bank hard.

**Expect.** Binoculars come down. Any command does it — including free speech he cannot act on,
which is the case that was broken until review caught it.

**Record.**
- [ ] Does a spoken command lower them
- [ ] Does free speech he cannot act on also lower them
- [ ] Does hard manoeuvring lower them

---

## 5 — The logs

```sh
cd body-layer
.venv/bin/python tools/summarize_detection_trace.py ~/eyes-sortie.jsonl
cat ~/dcs-speech.jsonl
```

**Record.**
- [ ] In the speech log: anything with disposition `fallthrough` that you meant as a command
- [ ] Any `act` whose token is not what you said
- [ ] In the trace: contacts never admitted that you could plainly see

---

## Bring back

1. Reports — right answers, right sectors, and "can't see" never swapped for "clear"
2. Whether `scan north` and the o'clock scans actually move his eyes
3. **Binoculars — does raising them feel like a crewman, and is the blindness a fair price**
4. Anything he mis-heard, from the speech log
5. Whether the whole loop — look, report, be told where to look — hangs together

**Anything that surprises you is worth more than anything on this list.** Two milestones landed
together without a flight between them, so the interesting failures are likely to be where they
touch.
