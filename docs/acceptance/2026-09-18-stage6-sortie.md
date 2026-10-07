# Stage 6 acceptance sortie — flight card

<!-- doc-provenance:start -->
**Flight for:** [[AA-1.6]]
<!-- doc-provenance:end -->

> **CLOSED 2026-09-25 by user direction — never flown as written, answered block by block by later
> sorties.** Not a pass and not a skip: every question on this card was eventually answered, but by
> five different flights rather than the one this card planned. The verdicts, in the user's own
> terms:
>
> | # | Block | Verdict |
> |---|---|---|
> | 1 | Voice quality and latency | **Stale.** Tested by other flights and cards; results already recorded. |
> | 2 | Detection ranges | **Pass** — "close enough for current stage". |
> | 3 | Contact separation | **Closed here, moved.** The last flight produced observations; `docs/acceptance/2026-09-25-crew-behaviour-sortie.md` is where this is now answered. |
> | 4 | F10 scan vocabulary | **Tested, adjusted and fixed** by other test flights. |
> | 5 | Attention events and tools | **Answered** by the last test flight. |
>
> **The lesson is about card lifetime, not about any block.** This card was written 2026-09-18 to
> clear five debts in one flight. It went stale before it could be flown — its own setup block still
> names `srs-adapter`, renamed to `audio-adapter` on 2026-09-20 — and in the week it sat unflown the
> debts were cleared piecemeal by sorties aimed at whatever had just merged. That is the same failure
> `2026-09-24-watch-reporting-sortie.md` hit, and the same reason the 2026-09-25 cards were folded
> into one: **a batched card decays at the rate of the fastest-moving thing in it.** A card that
> batches five debts is only cheaper than five cards if it is flown soon.
>
> Block 2's "pass" is the one verdict worth reading narrowly. It clears the calibration for *this*
> stage, not absolutely — the range-by-range numbers this card called "the most valuable data from
> the flight" were never brought back as numbers, so the calibration remains validated against
> screenshots plus one felt judgement in the air, not against measured in-flight arrival ranges.
>
> Everything below is the card as originally written, kept for the record. **Do not fly it.**


**One flight clears five separate debts.** Stage 6 is nominally the TTS slice's acceptance test,
but four other things have been waiting on a real sortie, and one of them — the vision range
calibration — changed perception behaviour substantially and has never been flown at all. Doing
them together is not padding: they share a setup, and several interact.

Nothing here is a correctness gate. The pipelines are proven by tests and by stage 5. This flight
answers questions only a human in the cockpit can answer.

---

## Setup

**Windows box**

```
set PYTHONPATH=src
python -m collector
```

**Mac — srs-adapter** (from `srs-adapter/`)

```sh
PYTHONPATH=src .venv/bin/python -m srs_adapter \
  --target aircraft-layer --aircraft-layer-url http://<windows-ip>:7791
```

**Mac — body-layer** (from `body-layer/`)

```sh
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<windows-ip>:7791 \
  --theatre Syria \
  --world-model-db <path-to-region.sqlite> \
  --crew-text --speech-audio --srs-adapter-url http://127.0.0.1:7795 \
  --overlay --f10-commands
```

`--overlay` runs alongside deliberately: it gives a written record of every line spoken, which
makes "what did he actually say, and when" answerable after landing rather than from memory.

**Mission.** Reuse the calibration setup if it still exists — flat desert, the twelve-unit complex
(SA-3 launcher and TR radar, ZU-23, ZSU-23-x, BMP-1, BTR-70, T-72B, Ural, BM-21, three AK
infantry), clear weather. It gives known target types at measurable ranges, which blocks 2 and 3
depend on. If rebuilding it, park them in a line as before and note the F10 ruler range from your
start position.

---

## The card

Run roughly in this order — it follows a natural approach profile, far to near.

| # | Block | Needs |
|---|---|---|
| 1 | Voice quality and latency | Any point in the flight |
| 2 | **Detection ranges (never flown)** | Long-range approach, 9 km to 500 m |
| 3 | Contact separation | Two targets a few hundred metres apart |
| 4 | F10 scan vocabulary | A heading sweep through north |
| 5 | Attention and events tools | Console access mid-flight |

---

## 1. Voice quality and latency

The nominal stage 6 test. Everything else is a rider.

- **Does the latency read as crew-like?** ~0.6–0.8 s from event to audio. A crew member takes about
  that long to say something anyway, so the question is whether it feels like thinking or like lag.
- **Under load**, several callouts land in one poll. Does the queue read as a crew member working
  through what he saw, or as a backlog he is reciting?
- **Volume against a loud cockpit** — engines running, ideally guns firing. Is he intelligible
  without being shouted over? (If not, this is largely answered by the SPU-8 knob once slice 2
  lands, so note it rather than chasing it.)
- **Monotony** — already known, already out of scope. Worth noting *where* it hurts most: whether
  a flat "break right" lands worse than a flat contact report, since that would argue prosody
  before accent.
- **Urgent preempt in real conditions.** `!inject-urgent <contact_id> <text>` at the crew console
  while he is mid-sentence. Stage 5 proved the mechanism on a bench; this is whether it is the
  right *behaviour* when you are busy flying.

## 2. Detection ranges — the untested one

The vision calibration merged 2026-09-17 and moved every recognition threshold. It was derived from
screenshots and validated against screenshots. **No flight has ever exercised it.** For a 7 m
vehicle the constants now claim: presence to ~9.3 km, class from ~2.0 km, type from ~1.0 km.

Approach the complex from roughly 10 km, slowly, and note where callouts actually happen.

- **Does he report anything around 8–9 km?** Before calibration he was silent until ~6.5 km and the
  5 km cap cut him shorter still. If he stays silent now, the presence threshold or the range cap
  did not take effect in the live path — that is a real finding, not a tuning nit.
- **Does he stop over-claiming?** Around 3 km he should say *something is there*, not *a truck*.
  Previously he claimed class out to 3.5 km. Hearing a confident type call at 3 km means the
  achieved-tier path is not using the new constants.
- **Where does class actually arrive?** Expect ~2 km. Where does type arrive? Expect ~1 km.
- **Does it match what you can see?** The invariant: if you can see it, he should too; if you
  cannot, he must not. Both directions are bugs. Note any range where you can plainly see a vehicle
  he has not mentioned.
- **Infantry** specifically — 1.8 m, so presence ~2.4 km and class ~514 m from the formula, but
  those numbers were derived from the vehicle data and never measured directly for infantry.

## 3. Contact separation

A known defect, pinned by a strict xfail and never seen in flight.

Two real objects a few hundred metres apart, first acquired at long range.

- **Do they stay two contacts, or collapse into one?** The defect: at coarse first-sighting range
  their implied positions overlap, the store merges them, and `object_id` continuity then holds
  that merge for the rest of the flight even as you close and they separate visibly.
- If they do merge, **does closing the range ever split them again?** Expected answer is no, and
  confirming that is what makes the fix worth prioritising.
- Watch for the opposite failure too — one object reported as several. That was BL-2.6's bug and
  it should be long dead, but the wider envelope is new stress on the same gate.

## 4. F10 scan vocabulary

Partially cleared 2026-09-16/17; two items were left unexercised.

- **Relative vs bearing scans through north.** `Scan → Ahead/Left/Right` rotate with the nose;
  `Scan → Bearing → <compass>` do not. Fly a heading sweep **through 0/360** with a scan active and
  confirm no discontinuity at the wraparound. This is the specific case never tested.
- **Scan radius and deadline are uncalibrated placeholders** — `F10_SCAN_RADIUS_M` is 3000 m,
  picked arbitrarily, and the deadline likewise. Now that a scan actually steers perception, they
  can be judged: does a scan cover a sensible area, or does it feel absurdly wide or uselessly
  narrow? Does it give up too early or hang around too long? **Bring back a number you would
  prefer**, even a rough one — a felt judgement beats another guess.

## 5. Attention and events tools

BL-4's tools may never have had a live run at all. At the crew console mid-flight:

- `watch <id>` / `unwatch <id>` on a real contact — does attention actually change what he says
  about it, or is it inert?
- `!inject-urgent` (covered in block 1) exercises the bypass-gate path.
- Does anything in the event stream appear that shouldn't — repeated lifecycle events for one
  contact, or events for a contact that never existed?

---

## Bringing it back

Per block, a sentence is enough. The overlay log plus the console output covers the detail, so what
is wanted is the judgement, not the transcript:

1. **Voice** — crew-like or laggy; where monotony hurts most.
2. **Ranges** — the ranges at which presence, class and type actually arrived, and any target you
   could see that he never mentioned. **This is the most valuable data from the flight.**
3. **Separation** — did the two stay separate.
4. **Scans** — any discontinuity through north; a preferred scan radius.
5. **Attention** — did watch/unwatch visibly do anything.

Anything that surprises you is worth more than anything on this list.
