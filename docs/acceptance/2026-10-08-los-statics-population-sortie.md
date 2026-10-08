# LOS statics — the downstream-join sortie

**Cockpit card (published):** https://claude.ai/artifact/CeF8PB3kbbL2cKFZTRS6JZ — the same content
below, laid out for reading in glances. This file stays the source of truth.

**Rewritten 2026-10-08, after your first flight.** The earlier version of this card had two open
items and pointed at `fix/los-hook-statics`. Item 1 is now answered, the branch is **merged and
deleted**, and the stutter it warned about is explained. What is left is one question.

```sh
git checkout main && git pull
```

---

## The one question

**Does a static's line-of-sight verdict ever actually reach a tracked contact?**

Everything else about the statics change is confirmed. This is not.

It is the last blocker on `BL-11` Stage 4 step 3 — *fail closed*: no live verdict means not
admitted, and world-model's `line_of_sight_clear` stops being called from the live path. That is
your own standing direction (*"world model LOS must not be used… not only because of performance,
but especially for correctness"*). Step 3 cannot be taken on inspection alone, because the cost of
being wrong is Petrovich going blind to things he should see.

**What is already known, so you are not re-flying it:**

| | status |
|---|---|
| Both enumerations run | **confirmed** — `static_enum_failures=0`, `unit_enum_failures=0` all sortie |
| Statics reach the candidate list | **confirmed** — 42 of 49 open terrain, 113 of 152 over the city |
| The city population is contacts, not buildings | **confirmed** — 388 statics in the mission: 120 infantry, 65 tanks, 70 APCs, 8 Shilkas, **zero buildings** |
| Per-poll cost | **confirmed** — ~2 ms open, ~5 ms city, 27 ms max |
| The 128 cap binds over a city | **confirmed** — `cap_hit=1`, 24 farthest dropped → `BL-B42` |
| The 5 s stutter | **explained** — a leftover `petrobrain-unit-id-join-probe-hook.lua`, now removed → `AC-B5` |
| **A static's verdict reaching a contact** | **never observed** ← this flight |

The wire shape and the join key were verified by reading: a static is indistinguishable from a unit
on the wire, and body-layer's join (`perception/naked_eye_source.py`, `_resolve_los_by_unit_name`)
is a pure `unit_name` string match with no unit/static branch. So the mechanism is sound on
inspection and unobserved in flight. Those are not the same thing, which is why this card exists.

---

## Pre-flight

**1 — Confirm no probe Hooks are deployed.** This is the `AC-B5` lesson and it cost three refuted
hypotheses last time. In `Saved Games\DCS\Scripts\Hooks\` there should be **only** these:

```
petrobrain-line-of-sight-hook.lua
petrobrain-f10-commands-hook.lua
petrobrain-overlay-hook.lua   (+ petrobrain-overlay.dlg)
petrobrain-mission-telemetry-hook.lua
```

Anything with `probe` in the name comes out. A probe left in place taxes every frame *and*
contaminates the measurement.

**2 — The Hook script is already the right one** (you flew it today), so no redeploy is needed. If
you do copy a Hook script for any reason: Hook scripts load at DCS **application** startup, not per
mission — restart DCS itself, not just the mission.

**3 — Collector, Windows box:**

```
cd aircraft-layer\src
python -m collector
```

---

## Run it with the trace on

`run-crew-text.sh` passes extra arguments straight through, and `pushd`es into `body-layer/`, so the
path is relative to there:

```sh
cd run-scripts
./run-crew-text.sh --detection-trace logs/dcs-detection-trace.jsonl
```

**The path you pass is not the path written.** Each run stamps its own filename, so you will get
`body-layer/logs/dcs-detection-trace-20261008-204500.jsonl`. That is deliberate (`BL-11` Stage 5 —
logs roll per sortie instead of appending across them). The newest is always:

```sh
ls -t body-layer/logs/dcs-detection-trace-*.jsonl | head -1
```

---

## Fly

**The mission you already used is ideal** — `MI24-outpost-M03.miz`. Its statics are the dense
population this question is about, and you have already flown it, so nothing new to learn.

What matters is *where you look*, not where you fly:

- **Spend time with static vehicles in the gaze wedge.** Petrovich only computes sightlines for the
  commanded look direction, so point him at them: `scan ahead`, or a bearing command toward an
  emplacement you can see.
- **Pick a target you can name** — a T-55, T-72 or Shilka emplacement you can identify from the map
  or briefing, so that afterwards you can tell whether *that* object got a verdict rather than
  guessing from a list.
- **Get close enough that he would plausibly detect it.** The question is about the join, not the
  range gate; a verdict on an object that never passed the size gate tells us nothing.
- **Include a pause.** Pause mid-flight a few seconds, unpause. Standing rule for every Hook-script
  family here (`aircraft-layer/CLAUDE.md`): export-rate bugs have twice been invisible to
  in-flight-only testing.

---

## Bring back

**The one number that decides it.** Run this after landing, from the repo root:

```sh
cd body-layer && .venv/bin/python ../.claude/scripts/los-verdict-coverage.py
```

It prints what fraction of distinct objects in the trace ever received a live verdict.

**Why this is the right metric rather than hunting for one object:** before the statics fix, 323 of
425 admitted objects never received a live verdict once — **76 % had none**, which is exactly what
made "fail closed" unsafe. If that number is now small, the join works for the population that
matters, and step 3 is safe to take. If it is still large, the join is broken somewhere downstream
of the wire and the fix is not finished. One number, and it does not depend on correctly guessing
which objects were statics.

Also useful:

- `body-layer/tools/summarize_detection_trace.py <newest-trace>` — the per-object debrief table
  (first-admitted range per tier, and the in-FOV-but-never-admitted list).
- **Did he actually say anything about a static?** A callout naming a contact that turns out to be a
  mission-placed static is the end-to-end answer in one sentence, better than any log.
- Anything across the pause.
- **Anything that surprised you.** Worth more than everything above — your *"those are buildings"*
  reading was wrong, and chasing it produced the mission-inventory count that settled `BL-B42`; your
  probe-hook catch explained a stutter three of my hypotheses had missed.

---

## Not this flight

- **`BL-B42`'s fix.** The cap binds and the cost says amortise rather than enlarge; that is a design
  conversation (`/explore`) before anything is built, not a mid-flight decision.
- **Filtering the population.** Settled: nothing gets filtered. The statics are contacts and
  `big_smoke` is a landmark, by your own direction.
