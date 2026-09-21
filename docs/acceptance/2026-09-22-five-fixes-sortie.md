# Five-fix acceptance sortie

Five things merged since the 2026-09-21 flight, four of them from findings on that flight.
**Branch: `feature/movement-detection` is merged — fly `main`.**

| | what changed | from |
|---|---|---|
| 1 | Callouts decided at speech time, not queued | your backlog finding |
| 2 | Repetitive callouts aggregated | your seven-line transcript |
| 3 | Group detectability — resolution vs salience split | your "single dot would be hard to notice" |
| 4 | Watch is a cancellable mode, coexists with Scan | your "watching target and scanning forward" |
| 5 | Movement detection | your 2026-09-20 design |

929 body-layer tests, 159 aircraft-layer.

---

## Setup — deployment first, this flight needs it

**The wire format changed.** Movement detection needs a redeployed `Export.lua` *and* a new Hook
script. Nothing else on this card depends on it, but movement will silently report nothing without
both.

**Windows box:**

```
copy "<repo>\aircraft-layer\dcs-export\Export.lua" ^
     "%USERPROFILE%\Saved Games\DCS\Scripts\Export.lua"
copy "<repo>\aircraft-layer\dcs-export\petrobrain-mission-telemetry-hook.lua" ^
     "%USERPROFILE%\Saved Games\DCS\Scripts\Hooks\"
set PYTHONPATH=src
python -m collector
```

**Watch the collector's first lines after DCS connects.** It now logs the deployed script's version:

- `Export.lua wire-format version 2026-09-22b (matches)` — good.
- `VERSION MISMATCH` — the copy did not take. Everything else still works; movement will not.

**Mac** (from `body-layer/`):

```sh
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<windows-ip>:7791 \
  --theatre Syria \
  --world-model-db <path-to-region.sqlite> \
  --crew-text --overlay --f10-commands \
  --detection-trace ~/five-fix-sortie.jsonl
```

**Mission.** The twelve-unit complex again, and this time **it matters that some units can move** —
blocks 3 and 5 both need it. If you can, give two or three of them a short patrol route and leave
the rest static.

---

## Not testable this flight

- **Attention capture.** `Optic.peripheral` is wired with no triggers. Movement could be the first
  but is deliberately out of scope, so a muzzle flash at 3 o'clock while he looks at 10 still
  produces nothing.
- **Lone-unit detection range is knowingly short.** `LOWRES` was deliberately *not* recalibrated, so
  the group term could be judged uncoupled. An isolated vehicle will still be picked up late —
  expected, not a regression.
- **The 9K113.** Still deferred.

---

## 1 — Are callouts current? **THE PRIZE**

The clearest defect from last flight, and the one that makes everything else legible.

**Do.** Fly past contacts at a decent clip — the failure needs closure rate to show up.

**Expect.** A callout names where a contact **is**, not where it was. Nothing is rendered until the
moment it is spoken, so a bearing cannot be stale by the time you hear it. If a contact stops being
worth mentioning while he is mid-sentence, it is dropped rather than spoken late.

**Record.**
- [ ] Any callout naming a bearing you had already passed
- [ ] Does the *overlay* stay in step with the audio? (Both go through the same scheduler now)
- [ ] Does he ever go oddly quiet — a symptom of the speaking-rate estimate being too slow

---

## 2 — Is the repetition gone?

**Expect.** Last flight's seven lines render as four in the fixture:

```
a couple of infantry, 12 o'clock, 0.5 kilometres.
unit at 1 o'clock, very close is BTR-70.
unit at 12 o'clock, very close is truck.
a couple of infantry, 2 o'clock, very close.
```

**Four, not two** — identification lines are never aggregated, which is what stops a BTR-70
disappearing into "three infantry".

**"A couple of infantry" for three units is a known wart.** He only speaks an exact number when
every member is attended and counted; otherwise he hedges. Tell me if it grates.

**Record.**
- [ ] Same-type, same-range, adjacent-clock contacts spoken as one line
- [ ] Any identification swallowed into a group
- [ ] Does "a couple" for three bother you in the air

---

## 3 — Does he find groups sooner than singles?

The model now separates **resolution** (can the eye register a mark) from **salience** (would you
notice it). A member of a cohesive group of 3+ only has to clear resolution.

**Do.** Approach the complex from distance, then find an **isolated** vehicle well away from it.

**Expect.** The group is picked up noticeably further out than a lone vehicle at the same range.
That asymmetry is the whole point.

**Record.**
- [ ] Range the group is first called
- [ ] Range a lone vehicle is first called
- [ ] Does the difference feel like yours did — group conspicuous, single dot hard to notice

---

## 4 — Watch and scan together

**Do.** In order:

```
F10 -> Petrovich -> Scan -> Ahead
F10 -> Petrovich -> Watch -> Nearest
(fly past, turn back)
F10 -> Petrovich -> Cancel Task
```

**Expect.** He watches the contact **while** scanning ahead — last flight the scan silently reverted
on first contact and the watch was never cancellable. Cancel now ends both and says which:
*"Copy, stopping the scan ahead and the watch."*

**Record.**
- [ ] Does the watch survive flying past and coming back
- [ ] Does scanning continue while watching
- [ ] Does Cancel name what it stopped
- [ ] **Is cancelling both what you wanted?** One F10 item, no way to say "cancel just the watch" —
      easy to change to most-recent-only if you would rather

---

## 5 — Movement

**Do.** Have him observe both a moving and a static unit. Crossing motion shows best; **a unit
driving straight at you will read as stationary** — deliberately, it is the general-aviation blind
spot and the geometry produces it.

**Expect.** Moving units called as moving; a stop reported only after it has held, not instantly.

**Record.**
- [ ] Moving units reported as moving
- [ ] Anything static reported as moving (worse than the reverse)
- [ ] How long a stop takes to be believed
- [ ] The collector's `dostring_in` timing lines — **this is the only way we learn the cost**

---

## 6 — The trace

```sh
cd body-layer
.venv/bin/python tools/summarize_detection_trace.py ~/five-fix-sortie.jsonl
```

**Record.**
- [ ] First-admitted ranges, group versus isolated
- [ ] Anything on the never-admitted list you plainly saw
- [ ] Is ownship still in the candidate list? (Should be gone if the redeploy took)

---

## Bring back

1. Whether callouts are current — **the prize**
2. Whether the repetition is gone, and whether four feels right
3. Group versus lone-vehicle detection ranges
4. Whether watch+scan behaves, and your call on Cancel semantics
5. Movement verdict plus the timing lines
6. The trace output and the overlay log

**Anything that surprises you is worth more than anything on this list.** Every item above came from
you noticing something no test could.
