# Mission Interpreter — desk test and sortie

**Branch:** `feature/binocular-optic` (already checked out)

The Mission Interpreter has been complete since 2026-09-12 (MI-0 through MI-6) and **has never run
against a mission you actually intend to fly**. Every test to date has used the committed synthetic
fixture or the third-party Bagram sample. Body-layer's BL-7 consumes MI-6's compact artifact, and
that path has only ever executed in unit tests.

This card covers both halves: a desk run on the Mac (no DCS needed once the mission exists), then a
sortie flying the mission MI just interpreted.

---

## Before you start: you need a Syria mission

**This is the blocker, and it cannot be worked around.** The only sample mission in the repo is
`research/samples/Mission 02-Bagram.miz`, whose theatre is **Afghanistan**. The only built world
models are Syria (`syria-full.sqlite`) and a Latakia 20 km extract. The world-model server binds to
one theatre per process and refuses a mismatch outright — verified:

```
theatre 'Afghanistan' does not match this server's bound theatre 'Syria'   (HTTP 400)
```

So: **build a small mission in the DCS Mission Editor, on Syria**, and save it somewhere you can
reach from the Mac. It does not need to be elaborate. What it does need:

- A **Mi-24P player or client slot** — MI resolves ownship by scanning for `skill in ("Player",
  "Client")`, and resolves to `UNKNOWN` on zero or two-or-more matches.
- **Three or more waypoints**, far enough apart that phase transitions are observable in flight.
- **Some ground units** along or near the route — these become important locations and threat
  signals.
- **At least one group marked `hidden` or `late activation`.** This is the one that matters most;
  see block A4.

---

## Setup

### 1 — World-model server (Mac)

```sh
cd /Users/sg/Code/DCS-petrobrain/world-model/src
../.venv/bin/python -m api --db ../data/world-model/syria-full.sqlite --theatre Syria --port 7792
```

**VERIFIED** — this exact command was run; the server answers `describe_position` for Syria and
returns HTTP 400 for any other theatre. Leave it running in its own terminal.

### 2 — Ollama

`qwen3:14b` is present locally (confirmed). MI preflights `/api/tags` before calling the model, so
if it is missing you get a clear error rather than a silent multi-gigabyte download.

### 3 — Mission Interpreter (Mac, second terminal)

```sh
cd /Users/sg/Code/DCS-petrobrain/mission-interpreter/src
../.venv/bin/python -m player_intent.main "/path/to/YourMission.miz" \
    --theatre Syria \
    --emit-compact /tmp/mission-understanding.json
```

**Argument shape verified** (`--help` run); **the end-to-end pass is UNVERIFIED** because it needs
the Syria mission that does not exist yet. That is what this card is for.

Note this is an **interactive** run — MI-5 asks you questions on stdin partway through. Do not pipe
it or background it.

---

## Part A — Desk

### A1 · Does it parse and get through the pipeline at all

**Do:** run the MI command above. Watch the whole pass.

**Expect:** it parses the `.miz`, enriches against world-model over HTTP, then pauses at the MI-5
player-question console. The LLM synthesis step (`qwen3:14b`) runs before that and is the slow part —
expect it to take a while, not to hang.

**Record:** Did it complete? If it failed, at which stage, and what was the error text?

---

### A2 · The player questions

**Do:** answer MI-5's questions as you actually would before flying.

**Record:** What did it ask you? Were the questions ones a crew member would sensibly ask, or did it
ask about things it should have been able to read from the mission itself? Was anything it *should*
have asked missing?

---

### A3 · Did it understand your mission — THE PRIZE

**Do:** read the `MissionUnderstanding` JSON it prints to stdout. Look specifically at `purpose`,
`task`, and `known_threats`.

This is the block worth the most. Everything downstream — phase tracking, relevance weighting,
eventually the kneeboard's briefing-sourced notes — inherits this interpretation. If `qwen3:14b`
misreads your mission here, every later layer is confidently wrong in the same direction, and
nothing downstream can detect it.

**Expect:** `purpose` and `task` should read like a crew member's understanding of the mission, not
a restatement of the waypoint list. `epistemic_status` on those fields should be `INFERENCE` or
`ASSUMPTION` (they came from a model), never `FACT`.

**Record:** In your own words — did it understand what the mission is for? Where was it wrong, and
was it wrong in a way that would have mattered in the air? Is the confidence it reports believable?

---

### A4 · The author-only-knowledge boundary

**Do:** search the printed JSON for the name of the hidden or late-activation group you placed.

**Expect:** the group's **name, id, and unit count must appear nowhere.** A coarse threat signal
*may* appear — a type category and a place name — because that is the deliberate design: Petrovich
may have a general sense that air defence exists in an area without knowing the specific group.
Exact coordinates of a hidden group must never appear.

**Record:** Did the group name leak anywhere? Did a coarse threat signal appear instead, and does
its wording read like something a crew would plausibly have been briefed on — or like a mission
editor readout?

---

### A5 · The compact artifact

**Do:** read `/tmp/mission-understanding.json` — the MI-6 output body-layer actually consumes.

**Expect:** a `phases` list (ordered boundaries, not a "current phase" — computing that needs live
aircraft position, which is body-layer's job) and `key_locations` keyed by location id.

**Record:** Are the phases sensible boundaries for the mission you built? Anything in
`key_locations` you would not have considered key, or anything key that is missing?

---

## Part B — Sortie · BLOCKED, do not attempt

**B1–B3 cannot be run today.** Loading the artifact works, but mission phase reaches no
pilot-reachable code path — there is no crew command that surfaces it, and phase does not feed
attention or callout ordering. Flying this half would measure nothing. Kept below for when that
gap closes.

### B1 · Start body-layer with the mission

Windows collector and the aircraft layer as usual, then on the Mac:

```sh
cd /Users/sg/Code/DCS-petrobrain/body-layer
.venv/bin/python src/logger.py --crew-text \
    --mission-understanding /tmp/mission-understanding.json \
    [your usual flags]
```

**UNVERIFIED** — needs DCS.

**CORRECTED 2026-09-24 (this card was wrong).** An earlier version called the flag's
"only meaningful with `--console`" help text stale, on the grounds that the phase tracker is passed
into the `--crew-text` paths. It is passed — and nothing there reads it. `mission_phase` appears in
four body-layer files and none of them is `attention.py`, `callouts.py` or `crew_console.py`. The
help text is effectively correct. See `body-layer/ROADMAP.md`'s open BL-7 entry.

### B2 · Does phase tracking follow the flight

**Do:** fly the route. Cross waypoints in order.

**Expect:** mission phase advances monotonically as you pass waypoints. It should not oscillate
between phases when you loiter near a boundary.

**Record:** Did the phase follow where you actually were? Did it ever jump backwards or flicker?

### B3 · Ask for the situation

**Do:** ask Petrovich for the situation (the `situation` command).

**Record:** Did the mission phase show up in what he said? Did having mission context change what he
chose to report — did it feel like he knew what the flight was for?

---

## Not testable on this card

- **Free-text mission questions.** The brain layer is a stub (`NullBrainClient`). Anything you say
  that is not a recognised command reaches it and nothing happens. Do not spend flight time on it.
- **Kneeboard / mission memory.** BL-8 is planned, not built. He cannot write anything down.
- **Briefing-sourced kneeboard notes.** Blocked on the above, and on a known gap: `CompactLocation`
  has no position field, so briefed notes would carry a place name and no coordinates.

---

## Bring back

1. Did the MI pass complete, and where did it fail if not? (A1)
2. What did MI-5 ask, and what should it have asked? (A2)
3. **Did it understand the mission — and where was it wrong in a way that would matter?** (A3)
4. Did the hidden group leak, and how did the coarse threat signal read? (A4)
5. Are the phases and key locations sensible? (A5)
6. Did phase tracking follow the flight without flickering? (B2)
7. Did mission context change what he reported? (B3)

**Anything that surprises you is worth more than anything on this list.**

---

## Results — 2026-09-24

Run against three real missions: `MI24-outpost-M03.miz`, `M04`, `M06` (Syria, built for this test).

| Block | Verdict |
|---|---|
| A1 · gets through | **pass** |
| A2 · player questions | **kinda pass** — asked threat confirmations only (*"is this threat &lt;description&gt; real?"*), accepted yes/no. *"Will do for now, needs further work."* |
| A3 · did it understand the mission | **pass** — *"well enough for first iteration implementation"* |
| A4 · author-only boundary | **pass** — no hidden-group leak against real content |
| A5 · compact artifact | **pass with a wart** — unicode in place names; likely already fixed in the world-model builder and simply not rebuilt into the store being served. Unconfirmed. |
| B1–B3 | **not run** — nothing pilot-reachable consumes the artifact (see above) |

**Wall-clock:** 1:12 with `qwen3:14b` already resident · 3:19 cold · 2:28 warm-ish. The first run of
a session pays roughly two extra minutes for model load alone. MI is a minutes-scale pre-mission
pass, not an interactive one.

**What came out of it:**
- MI-5's question set is threat-confirmation only in practice — ownship, purpose and task
  ambiguities produced no questions on any of the three missions. Backlog, `mission-interpreter/ROADMAP.md`.
- BL-7 is complete as designed and unreachable in flight. New open item in `body-layer/ROADMAP.md`.
