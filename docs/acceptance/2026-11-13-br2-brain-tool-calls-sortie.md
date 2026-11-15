# BR-2 brain tool calls — Stages 0–3 acceptance sortie

**Artifact (cockpit-readable card):** https://claude.ai/artifact/5nxfSADuGQScYgZAh1z1w3

**Branch to fly: `main`, after this batch merges.** `git checkout main && git pull` (or however
you normally sync the root checkout) before starting any of the three services below.

**What this covers.** Addressed speech — anything starting with "Petrovich, ..." — now reaches a
real tool-calling loop against a local model instead of silently escalating into nothing, acting
on a stripped phrasebook parse, or (if it ever did reach the old BR-1 decider) answering a
classify/discriminate prompt that never called a tool. This is also the **first time anything in
this project has driven a live Ollama through body-layer's own escalate/poll wire end to end** —
Stage 0's probe measured the model directly, not through this seam, and BR-1 itself has never
flown. So this sortie is simultaneously testing BR-2 Stages 0–3 and the brain seam's first live
flight.

**What this does *not* cover, and cannot by construction** — the acceptance boundary, stated up
front so a pass here is never mistaken for more than it is:
- **No landmark report** ("report south of Gemerek" acts at once and drops the place words — Stage
  4, not built). The test case below for this exact phrase is there to confirm the *honest
  degradation*, not the landmark behaviour.
- **No free-text answers.** Every reply is a template over tool data (D7: `command`, `answer`,
  `ask`, `unable`) — nothing resembling natural prose. Stage 5 (`say`) is gated on this very
  flight's findings.
- **No memory-writing.** `remember_location` is not exposed to the brain yet (Stage 6); "remember
  this spot" style utterances are not in this test set because there is nothing built to answer
  them yet.
- **Latency is real, not simulated.** Expect roughly 2–6 s of model time per answer (Stage 0's own
  measured range), on top of body-layer's own transport. This is a deliberate choice (A4) — a
  wake-word-prefixed utterance trades speed for understanding — not a regression against the
  phrasebook, which is untouched and still answers in under a second when you don't say the wake
  word.
- **No weapons/sight/flight commands from free speech** (U2, accepted) — "arm the weapons" and
  "turn left" are deliberately excluded and should answer "Unable, fixed command only," never act.

## What to restart

All three services need the code on `main`. From the repo root, after merge:

```sh
cd run-scripts
./run-brain.sh --decider tool_loop
```

`run-brain.sh`'s own default is `--decider ollama` (BR-1's classify/discriminate decider) — **you
must pass `--decider tool_loop` explicitly**, or every addressed utterance this sortie is testing
will go through the old BR-1 path instead of BR-2's tool loop. Confirmed by reading
`__main__.py`: `--decider` has three choices (`stub`/`ollama`/`tool_loop`), default `stub`
overridden by the script to `ollama`; nothing in the script passes `tool_loop` for you.

```sh
cd run-scripts
./run-body-layer.sh
```

No flag changes needed — `run-body-layer.sh` already passes `--brain-client http` and
`--brain-url`, confirmed by reading the script (unchanged by this batch).

```sh
cd run-scripts
./run-audio-adapter.sh
```

Also unchanged. The new `addressed` field rides the existing wire additively — nothing to pass.

**Logs worth having open**, so you can read back what actually happened after landing:
- Speech log: `--speech-log` on body-layer (default `logs/speech.jsonl`, stamped per mission
  start, e.g. `dcs-speech-<stamp>.jsonl`) — every line Petrovich actually spoke, with the
  utterance it answered.
- brain-layer's own stdout/stderr at its default `INFO` level — shows each `POST /escalate`
  arriving and (with `--debug`) the raw HTTP exchange. **Round count and prompt-token counts are
  not logged anywhere in this batch** (checked: neither `decider.py` nor `server.py` emits them) —
  if you want to see how many rounds a turn took or how close to `num_ctx=2048` a turn got, that
  needs a follow-up logging pass, not something this sortie can read back. The `--out` JSON from
  Stage 0's own probe is the only place that detail currently exists, and it is offline-only.

## Test cases — the plan's own acceptance set, spoken with the wake word

Say each line to Petrovich as a radio transmission (press the intercom trigger, say it, release).
All twelve lines above were run through the real `command_matcher.match_transcript` on this branch
before writing this card — every one of them returns `token=None, addressed=True`, confirming each
reaches the brain rather than the phrasebook (the wake word is what makes the difference; the same
words without "Petrovich, " at the front would try to match a command instead).

1. **"Petrovich, where's the Shilka?"** (one Shilka in the area) — expect a `where_is_it`-shaped
   readback: clock, range, and a landmark if one is nearby. Same wording as if you'd said "watch"
   after selecting it.
2. **Same scene, two Shilkas, one by a named village** — expect either a direct answer (if the
   model picks the one "by the village" and the readback names it) or **"Which one — ..."** over
   both. Either is a pass; a silent wrong pick is not.
3. **A Shilka not seen for several minutes** — expect the freshness phrase, e.g. "...not seen for
   four minutes," not a present-tense claim about where it is *now*.
4. **"Petrovich, where is it?"** right after he's just called out a contact unprompted — expect
   him to resolve "it" to that contact (`[[BL-B102]]` referent) without you naming it again.
5. **"Petrovich, anything near Gemerek?"** and **"Petrovich, report south of Gemerek"** — expect
   either a real answer about that area, or **"Unable, don't know that place"** if the name isn't
   one `find_place` recognises. What you should **not** get: a bare whole-scene report with the
   place words silently dropped — that's the *old*, pre-BR-2 behaviour this milestone replaces.
6. **"Petrovich, anything near the bridge?"** (a generic, unnamed bridge) — expect **"Which
   bridge?"** or **"Unable, don't know that place"** — never a guessed bridge, never a claim of
   "nothing" that could be mistaken for "confirmed empty."
7. **"Petrovich, where are we?"** — expect `describe_our_position`'s own summary (the same kind of
   answer "where am I" gets today, just reached through the brain this time).
8. **"Petrovich, where's mark one?"** (after marking something earlier in the sortie) — expect the
   mark read back with current relative position, not the position it was marked at.
9. **"Petrovich, what did we mark?"** — expect a short list of this sortie's marks.
10. **"Petrovich, which one's the BMP?"** (two candidates recently mentioned, one a BMP) — expect
    either the BMP named directly (if `describe_contact`'s own text discriminates it) or "which
    one?" — never a silent wrong pick between the two.
11. **"Petrovich, keep an eye on the tank by the village"** — expect the *same* effect as
    selecting that tank and saying "watch": readback, task state, orange marker, all identical to
    the phrasebook path (E3). Follow up with **"Petrovich, cancel"**/drop-target style phrasing and
    confirm it releases exactly as a phrasebook-commanded watch would.
12. **"Petrovich, arm the weapons"** — expect **"Unable, fixed command only"**, never action.
13. **"Petrovich, turn left"** — same, **"Unable, fixed command only."**
14. **"Petrovich, how many rockets left?"** — expect **"Unable, don't know"** (no tool answers
    loadout questions) rather than silence or a guess.

## Wording to listen for (U3)

The five new `unable` lines, verbatim if you hear them:
- **"Unable, no brain."** — brain-layer unreachable or not responding (try this by stopping
  brain-layer mid-sortie and saying any addressed line).
- **"Unable, no answer."** — the turn's budget ran out with no final reply.
- **"Unable, don't know that place."** — `find_place` found nothing.
- **"Unable, don't know."** — nothing in the tool set can answer (loadout, case 14 above).
- **"Unable, fixed command only."** — weapons/sight/flight tokens (cases 12–13), or any excluded
  command.

## What slows down and why (R4)

"Petrovich, where's the Shilka?" is now **slower** than saying "report" and letting the phrasebook
answer — by the pilot's own choice (A4): a wake-word-prefixed utterance always goes to the brain,
command phrasing or not. This is not a regression. If it feels too slow in practice, that is
exactly the kind of judgement this flight exists to collect — say so in your feedback rather than
assuming the implementation is broken.

## What to capture for feedback

- For each test case: did Petrovich answer correctly, degrade honestly (ask/unable), or do
  something wrong (wrong contact, silent guess, acted without evidence)?
- Roughly how long each answer took to arrive, by feel — a stopwatch isn't necessary, but "felt
  like about 3 seconds" vs. "felt like 15" is useful calibration data for Stage 7's tuning pass.
- Whether "stand by" was ever heard, and whether it felt like the right amount of warning before a
  slow answer landed.
- Anything that felt *wrong* even if it technically matched the spec above — this project's own
  worked example (BR-2's F10 precedent) is that the fixture-level pass and the first real flight
  have found different defects every time so far (`Scan` driving the wrong subsystem on a past
  feature; a raw task id spoken aloud on another). Expect this one to surface its own equivalent.

## Pass criteria

The feature passes if the fourteen test cases above produce their expected (or honestly degraded)
result, the five `unable` lines read as written when their conditions fire, phrasebook commands
said *without* the wake word are completely unaffected (same speed, same behaviour as before this
branch), and no threat callout or attack-run guidance is ever delayed or silenced by a brain turn
in progress.

## Marking this flown

This batch's `#needs-flight` tag lives on `brain-layer/ROADMAP/BR-2.md`'s "Stages 0–3 merged"
entry. When this sortie is flown, note which test cases passed/degraded/failed there (or in a
fresh `docs/acceptance/<date>-...-feedback.md` if anything needs the full write-it-down-then-
explore treatment per root `CLAUDE.md`'s "Flight feedback" section), and clear the tag by naming
this sortie.
