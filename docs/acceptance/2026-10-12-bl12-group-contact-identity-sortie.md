# Sortie card — BL-12, group-level contact identity and continuity

**Published as an artifact for reading in the cockpit:**
https://claude.ai/artifact/BKkJWDKBKYiAUgjzZAoMKz — this file stays the source of truth and the
card is generated from it.

**Branch: `feature/bl12-group-contact-identity`** (DoD-PASSED at `a2b761c`, not yet merged — you
merge it yourself from the root when you're satisfied).

```sh
cd /Users/sg/Code/DCS-petrobrain
git checkout feature/bl12-group-contact-identity
```

**What changed, in one sentence:** Petrovich now remembers a *group* across a repositioning — a
column that pops behind a ridge and reappears should stay "that column," not become a new belief
— and a new, unclassified-mistaken-for-known error is now the one the system prefers, per your own
"I can live with that easier than new group beliefs popping up all the time."

**What nobody here could check:** nothing on this branch has ever talked to a live DCS session.
Every command below marked with real output was run on the Mac against this branch's own code.
Anything marked **UNVERIFIED** needs the Windows box, DCS, or your ears, and is written from
reading the code, not from a run — flagged as such rather than guessed.

---

## Before you fly — UNVERIFIED, your own scripts, none of them run here

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh
./run-crew-text.sh --group-trace logs/dcs-group-trace.jsonl
```

That third line is the one change to your normal launch: `--group-trace` is a new, additive flag
(a true no-op if you leave it off). It writes one JSON line per group-reconcile outcome — the only
way to check from a log, rather than from a wrong spoken line in flight, how often continuity holds
versus a new group gets founded. **Confirmed on the Mac** that the flag is accepted and that an
unbuilt/missing world-model path fails with a clear startup error rather than a silent default:

```
$ PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
    --aircraft-layer-url http://127.0.0.1:7791 --theatre Syria \
    --world-model-db /tmp/does-not-exist.sqlite --crew-text \
    --group-trace /tmp/group-trace-test.jsonl
python -m logger: error: world model for Syria not built: /tmp/does-not-exist.sqlite
```

Also confirmed directly: `--group-trace` without `--console`/`--crew-text` fails with exactly
`python -m logger: error: --group-trace requires --console or --crew-text` — so it's safe to add
to the existing `run-crew-text.sh` invocation, which already carries `--crew-text`.

**Like the other three debug logs, the path you pass is not the path written** — it gets a
run-start timestamp stamped into the filename, same as `--speech-log`/`--detection-trace`
(`body-layer/RUN.md`). So after a flight, find it with:

```sh
ls -t body-layer/logs/dcs-group-trace-*.jsonl | head -1
```

---

## What to listen for

1. **A group you keep in sight across a repositioning should stay the same group, spoken as
   continuing** — something like *"that column, now 2 o'clock, three kilometres, still moving
   north"* rather than a fresh sighting line for units you already knew about. Try: spot a group,
   let it go behind a ridge or out of your FOV for under `GROUP_REIDENTIFY_WINDOW_S`, then
   re-acquire it from a different angle. **Pass**: same identity, continuity language. **Fail**:
   it's announced as if new. This is `BL-B24`'s old baseline (554 contacts reported for 444 real
   objects in one 70-minute sortie) coming down — note roughly how many group callouts you hear
   for how many real clusters you can see on the map.

2. **An over-wide, not-yet-classified group (the chained-infantry case) should say only
   `"Group."`** — no bearing, no range, no heading. This was a deliberate judgement call the
   Reviewer flagged and you resolved by keeping current behaviour (A10). **Listen for**: does a
   bare `"Group."` with no other content, repeated, start to feel like noise rather than
   information? That's the thing your own decision accepted the risk of — tell us if it reads
   differently in the cockpit than it did on paper.

3. **Repetition, not silence, is still the thing to listen for** — the project's recurring failure
   shape (`BL-B47`, `BL-B50`). If the same group line repeats every poll, or two contacts entering
   and leaving a group on alternate ticks produce a flood of lines, that's `BL-B50`'s mechanism,
   not newly introduced by this branch but worth confirming it hasn't gotten worse.

4. **An air-defence contact should never go quiet just because it got folded into a group.** This
   is `BL-B59` — known, filed, user-prioritised next, **not fixed on this branch**. If you fly with
   air defence present and notice a SAM/AAA you were tracking stop being mentioned after it joins a
   group, that is exactly this defect; it is expected to still be possible, and worth confirming it
   is rare rather than common.

---

## After the flight

Reduce the group trace and check what actually happened, not what should have:

```sh
cd body-layer
ls -t logs/dcs-group-trace-*.jsonl | head -1
```

Each line's `"phase"` field is `overlap` (matched by shared members), `property` (matched by
remembered properties alone — no shared members, the rarer and more interesting case), `found`
(a new group), or `expired`. **What you're checking**: is `found` rare relative to `overlap`/
`property`, matching D5's "mistaking a new group for existing is the unusual occurrence, and I can
live with that" preference? Or is the group population churning (lots of `found`, or the same
`group_id`'s membership visibly flipping tick-to-tick, which is `BL-B50`'s/`BL-B59`'s territory)?

---

## Pass criteria

Passes if: continuity holds across a repositioning (item 1), nothing sounds like it's repeating
pathologically (item 3), and the group trace shows `found` as the rare case rather than the norm.
Does **not** need to pass on: the bare `"Group."` line being satisfying (item 2 — your call,
already made, just worth a comment), or `BL-B59`'s eviction defect never firing (known, accepted,
next in line).

**Does the feature pass acceptance testing? (yes / no + details)**
