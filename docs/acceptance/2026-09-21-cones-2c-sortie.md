# Cones slice 2C — the o'clock scan loop sortie

**Branch under test:** `feature/cones-2c-scan-loop` (not yet merged — DoD checks passed 2026-09-21,
acceptance is the last gate). Check it out in the main checkout, not a worktree:

```sh
git checkout feature/cones-2c-scan-loop
```

**What changed, in one line:** Petrovich's default gaze stopped being a static forward hemisphere
and became a moving scan — `12 → 11, 10, 9 → 12 → 1, 2, 3 o'clock`, 2 seconds per 30° cone, 16
second full cycle, forward arc swept twice per cycle. A commanded F10 scan now cycles the same way
within its own sector instead of holding a static wedge.

This is the first cones sortie with something genuinely new to hear: 2A/2A.5/2B changed *whether* or
*how far* he sees; 2C changes *when* and *where he is looking*, which is the part a crewman's
presence actually rides on.

---

## Setup

**Windows box** (collector + both Hook scripts — deploy once, skip if already current per
`aircraft-layer/WORKFLOW.md`):

```
set PYTHONPATH=src
python -m collector
```

**Mac — body-layer** (from `body-layer/`; needs its own venv per `body-layer/RUN.md` if not built
yet):

```sh
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<windows-ip>:7791 \
  --theatre Syria \
  --world-model-db <path-to-region.sqlite> \
  --crew-text --overlay --f10-commands \
  --detection-trace ~/cones-2c-sortie.jsonl
```

Every flag here was run against a stub DB and stub aircraft-layer URL during DoD to confirm the
argument combination parses and reaches the poll loop — it fails only at "no DB file"/"no
aircraft-layer", exactly the boundary DCS itself resolves. Not re-verified against a live DCS
session — that is what this flight is for.

**Audio is optional, not under test.** If you want voice, run `audio-adapter/` per its own RUN.md
and add `--speech-audio --speech-input --audio-adapter-url http://127.0.0.1:7795`.

**Mission.** Reuse the calibration setup if you still have it — flat desert, known unit types at
known ranges — but this flight is about *pattern*, not range, so any mission with contacts spread
across your forward arc works. Fly a heading and hold it for at least one full 16 s cycle before
judging anything.

---

## Not testable this flight — read before you fly

- **Peripheral vision has no trigger.** `Optic.peripheral` is wired end to end but nothing generates
  a peripheral stimulus yet. Nothing outside the current 30° focus cone can capture his attention —
  not a flash, not movement, nothing.
- **He will not *find* an 8 or 4 o'clock contact on his own.** The scan loop only covers 9 through 3
  o'clock (nine sectors: 9, 10, 11, 12 ×2, 1, 2, 3). He can still *report* a contact at 8 or 4
  o'clock if you direct him there by bearing or by watch command — that path is unaffected — but
  free scan will never land on it.
- **2D (dwell as an act) does not exist yet.** He does not fix on a contact, check nearby, or glass
  up. This flight's own verdict is what decides whether 2D gets built at all.

---

## Test blocks

### 1 — Does the loop read as attentive, or as neglectful? — THE PRIZE

**Do:** Fly straight and level for at least 2 minutes with no F10 commands issued — free scan only.
Pick a contact near your 3 or 9 o'clock (a flank position) and note when he first reports it, then
listen for how long it takes him to mention it again, or whether he seems to "lose" it between
sweeps.

**Expect:** A flank contact gets revisited roughly every 16 seconds (once per full cycle). No
number here is "correct" — this is the one judgement no test can make. The question is whether a
16 s gap on the flanks feels like a real crewman's attention moving around the cockpit, or like he
keeps forgetting something is there.

**Record:**
- [ ] Does the 16 s flank revisit feel attentive or neglectful?
- [ ] Did any contact seem to "flicker" — reported, dropped, re-reported — in a way that felt wrong
      rather than realistic?
- [ ] Would a faster or slower cycle change your answer?

---

### 2 — Free scan vs. a commanded sector, back to back

**Do:** With a contact visible in, say, your left flank, first let free scan run past it
(uncommanded). Then issue **F10 → Petrovich → Scan → Left** and watch the same contact through a
commanded left-sector scan. Issue **F10 → Petrovich → Cancel Task** to return to free scan.

**Expect:** The commanded sector should visibly narrow and quicken his attention to that side —
this is the free-scan baseline 2B's gaze-as-filter test never had, so this is also 2B's deferred
acceptance item, riding on this flight.

**Record:**
- [ ] Was the difference between free scan and a commanded sector obvious by ear?
- [ ] Did `Cancel Task` cleanly return him to the full loop?

---

### 3 — Held contacts hedge less

**Do:** Get a contact into steady view (ideally near 12 o'clock, revisited most often) and listen
to how he talks about it across several callouts — one right after acquisition, a few more as the
flight continues.

**Expect:** `OBSERVED_WINDOW_S` moved 5 → 16 seconds, so a contact he's held across several sweeps
should sound *more* confident over time, with less hedging language, than the old 5 s window would
have allowed.

**Record:**
- [ ] Did confidence language noticeably firm up the longer a contact stayed observed?

---

### 4 — A dropped sweep sounds abrupt

**Do:** Force a contact to be missed on one sweep — fly a turn that takes it briefly out of the
active cone, or let terrain mask it for a beat, then let the scan come back around to it.

**Expect:** A missed sweep drops a contact two certainty bands at once, not one — this was a
deliberate consequence of the wider window, not a bug. It should sound like a real, audible step
down, not a smooth fade.

**Record:**
- [ ] Did the drop sound like a distinct, abrupt step rather than a gradual fade?

---

## Bring back

- [ ] Block 1's verdict — attentive or neglectful, and why
- [ ] Block 2's free-scan vs. commanded contrast
- [ ] Block 3's hedging trend
- [ ] Block 4's abruptness
- [ ] The `--detection-trace` file (`~/cones-2c-sortie.jsonl`)

**Anything that surprises you is worth more than anything on this list.**

**About the trace file:** the cockpit-mask rejection count will read as close to zero this flight —
that's expected, not a bug. Gaze now runs before the cockpit mask in the gate chain, so most
astern/blocked candidates are rejected by `GAZE` before they'd ever reach `COCKPIT_MASK`. Reduce it
with `python tools/summarize_detection_trace.py ~/cones-2c-sortie.jsonl` from `body-layer/`.
