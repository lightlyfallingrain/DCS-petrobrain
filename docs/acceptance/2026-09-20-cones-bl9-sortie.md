# Cones slice 1 + BL-9 acceptance sortie

**One flight, two merges, and the first honest measurement of how far Petrovich can see.**

Merged 2026-09-20: `ce9baea` (cones slice 1) and `1553eb9` (BL-9 detection trace). Neither has been
flown. They were merged back to back deliberately so a single sortie serves both — BL-9 is the
instrument that makes slice 1's question answerable at all.

**What changed, in one line:** the naked eye replaced binoculars as the default optic, so default
detection range dropped roughly 4×. Petrovich was previously modelled as permanently glassed-up.

Nothing here is a correctness gate — 745 tests pass. This flight answers what only a human in the
seat can answer: whether the numbers feel like a crewman.

---

## Setup

**Windows box**

```
set PYTHONPATH=src
python -m collector
```

**Mac — body-layer** (from `body-layer/`)

```sh
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<windows-ip>:7791 \
  --theatre Syria \
  --world-model-db <path-to-region.sqlite> \
  --crew-text --overlay --f10-commands \
  --detection-trace ~/cones-sortie.jsonl
```

`--detection-trace` is the whole point of flying now rather than later: it records, per poll and per
object, which gate decided each candidate's fate and at what true range. `--overlay` gives a written
record of every spoken line, so "what did he say, and when" is answerable after landing instead of
from memory.

**Audio adapter is optional and not under test.** If you want voice, run it from `audio-adapter/`:

```sh
PYTHONPATH=src .venv/bin/python -m audio_adapter --whisper-model /path/to/ggml-small.en.bin
```

and add `--speech-audio --speech-input --audio-adapter-url http://127.0.0.1:7795` to the logger.
Note the rename: this was `srs-adapter` and the older flight card's commands are stale.

**Mission.** Reuse the calibration setup — flat desert, the twelve-unit complex, clear weather.
Known types at measurable ranges is what blocks 1–3 depend on. Note the F10 ruler range from your
start position.

---

## Not testable on this flight — read before planning it

- **Binoculars.** `BINOCULAR_OPTIC` exists with a real 4.25° field of view, but **nothing can select
  it.** Optic selection is cones slice 2. Everything you see this flight is the naked eye.
- **The 9K113.** Deferred out of slice 1 entirely (`todo/todo.md`).
- **Movement.** Designed, not built. No behaviour-change channel exists.
- **The PTT probe** needs its own session — `Export.probe-ptt.lua` replaces the production
  `Export.lua` and kills the collector. Do not ride it on this flight.
- **The ambient-detection A/B** (`aircraft-layer/WORKFLOW.md`) is a separate protocol with its own
  probe. Not this sortie.

---

## Block 1 — Detection ranges. **THIS IS THE PRIZE.**

Never flown. Several downstream milestones are waiting on it, and this flight is the first time the
naked-eye model meets reality.

**Do.** Start well outside 3 km. Close slowly and straight toward the complex. Say aloud — or note —
the range at which you personally first make out each unit, and separately when Petrovich calls it.

**Expect.** Computed naked-eye ranges (verified by running the model, 2026-09-20):

| Unit | size | presence | class | type |
|---|---|---|---|---|
| Infantry | 1.8 m | 600 m | 129 m | 64 m |
| Ural truck | 6.0 m | 2000 m | 429 m | 214 m |
| BTR-70 / BMP-1 / T-72B | 7.0 m | 2333 m | 500 m | 250 m |
| ZU-23 | 5.0 m | 1667 m | 357 m | 179 m |
| ZSU-23-4 Shilka | 6.0 m | 2000 m | 429 m | 214 m |

**BM-21 and SA-3 have no profile entry** — they fall back to a 5.0 m generic, so treat their numbers
as the ZU-23 row and do not read anything into them. Worth reporting if their behaviour looks wrong;
it is a known gap, not a bug.

**Record.**
- [ ] First-call range per unit type, against the table
- [ ] Does he call things *you* cannot see yet? (still too hawk-eyed)
- [ ] Does he miss things obvious to you? (over-corrected)
- [ ] Which direction the error runs, if any — consistently early or consistently late

---

## Block 2 — The trace agrees with the cockpit

**Do.** After landing, reduce the trace:

```sh
cd body-layer
.venv/bin/python tools/summarize_detection_trace.py ~/cones-sortie.jsonl
```

**Expect.** A per-object table: the range at which presence/class/type were first admitted, and a
list of objects that cleared the cockpit mask but never reached `ADMITTED`.

**Record.**
- [ ] Do the first-admitted ranges match block 1's table?
- [ ] Do they match what you actually saw?
- [ ] Anything admitted that you never saw at all

---

## Block 3 — The misses list

The second half of the reducer's output is the interesting half: objects plausibly on your screen
that never became contacts.

**Expect.** Its own output labels this an approximation — code can confirm an object cleared the
geometric gates, not that your monitor rendered it large enough to notice. Judge it against what you
remember seeing.

**Record.**
- [ ] Anything on the never-admitted list that was plainly visible to you
- [ ] Anything absent from it that you expected to be there

---

## Block 4 — Bearings and clock positions

**Do.** For each callout, note the clock position he gives and check it against where the unit
actually is.

**Expect.** Accurate to the hour, within the 8–4 forward envelope. Nothing should ever be reported
behind ±130°.

**Record.**
- [ ] Clock positions correct
- [ ] Anything reported from behind the rear cutoff (would be a real bug)

---

## Bring back

1. First-call range per unit type — **the prize**
2. Whether he is early, late, or about right, and consistently
3. The reducer's output, both halves
4. Any clock-position error
5. The overlay log

**Anything that surprises you is worth more than anything on this list.** Several of this project's
most important corrections arrived that way rather than in answer to a question.
