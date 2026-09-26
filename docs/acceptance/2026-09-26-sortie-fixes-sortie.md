# Sortie-fixes acceptance sortie

**Branch: `fix/sortie-2026-09-26`.**

```sh
git checkout fix/sortie-2026-09-26 && git pull
```

Three fixes from your 2026-09-26 flight, all with real in-cockpit observables:

| fix | what changed |
|---|---|
| **A — observability gate** | Crossing/motion callouts stop for a contact he cannot currently see (behind the cockpit mask), with a 10s grace window for a brief occlusion |
| **B1/B2 — binocular retry** | An interrupted look no longer burns the retry attempt; a watched/orbited contact held at constant range becomes eligible for a re-look after ~64s, not just when it closes range |
| **C — command-dependent lowering** | An unrecognised utterance ("say again") no longer lowers the binoculars; `follow <target>` on the contact already being glassed continues instead of lowering and re-raising |

**Not in this branch — do not read as a regression**: sector coverage (every contact in a scanned
sector eventually getting a look) is explicitly staged out as its own follow-on. "All ten units to
my left get identified" is still expected to fail this flight.

## Setup

Windows: collector + capture with `--ptt dcs`, unchanged from your last flight.

Mac, three processes, each from `run-scripts/`:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text-debug-view.sh
```

`./run-crew-text-debug-view.sh` already carries `--speech-audio --speech-input --crew-text
--f10-commands --eyesight-view --eyesight-view-radius-m 5000`, plus two log flags that matter for
this flight specifically (see "What to capture" below): `--speech-log ~/dcs-speech.jsonl` and
`--belief-truth-log ~/dcs-belief-truth.jsonl`.

**`--decider ollama` is not the default** — `run-brain.sh` still defaults to the stub deliberately.
Omit it and block 3 (follow-on-target) still works since it doesn't touch the brain, but you'll be
testing the stub for anything else you say.

## What to capture, and why the belief-truth log won't show everything

Bring back `~/dcs-belief-truth.jsonl`, `~/dcs-speech.jsonl`, and the DCS log, same as last time.

**The belief-truth log only writes a row for a contact the naked-eye channel currently admits** —
confirmed by reading `belief_truth_log.py`'s `write_poll` directly: it skips any detection-trace
entry that isn't `GateOutcome.ADMITTED` this poll. A contact correctly silenced by Fix A (behind the
cockpit mask) is, by construction, never admitted while masked — so **the belief-truth log cannot
show you Fix A working**, it can only ever be silent about a masked contact, which looks the same as
"nothing there." **The speech log and what you hear are the actual evidence for Fix A** — a
crossing/motion callout that does *not* arrive for something you know is behind you or off to the
side is the thing to notice, not a log row.

## Block 1 — crossings and motion callouts respect the cockpit mask

**Do:** Fly so a contact you already know about (spawn it ahead, then turn away, or orbit so it
passes behind you) ends up behind the cockpit mask or off to the side outside any gaze direction can
reach, while it's still moving or changing range.

**Expect:** No crossing ("getting closer"/"moving away") or motion-changed callout while it's
masked. If you glance back within about 10 seconds of it going out of view, a callout for it in that
window is correct (memory grace, not a defect) — only a callout after a longer masked stretch is
wrong.

**Falsifies the fix:** A callout fires for something you can verify was behind the mask for more
than ~10 seconds with no intervening look at it.

**Record:** Did any callout arrive for something you were sure you couldn't see? How long was it
masked before you noticed it was silent?

## Block 2 — binoculars actually get picked for a watched/orbited contact

**Do:** `watch nearest` (or watch a specific contact) and then orbit or hold roughly constant range
on it for at least a couple of minutes, rather than closing on it.

**Expect:** Binoculars get used on it more than once over that time — not just the first look, then
silence for the rest of the orbit. The `--eyesight-view` ASCII display should show the blue
binocular cone re-appearing on it periodically (roughly every ~64s once nothing else has changed,
per `OPTIC_RETRY_INTERVAL_S`, a starting value not a measurement).

**Falsifies the fix:** One look, then binoculars never touch that contact again for the rest of a
long orbit, even though it never closes range and its classification never advances.

**Record:** How many times did binoculars come back to a held-range contact over a few minutes? Did
the interval feel too long, too short, or about right?

## Block 3 — speech no longer interrupts a look it shouldn't

**Do:** While binoculars are actively glassing a contact (watch it and get it into a look), say
something the recognizer won't understand — garbled, off-vocabulary, anything that gets "say again."
Separately, while glassing contact X, say `follow` naming that same contact X.

**Expect:** "Say again" does not lower the binoculars — the look continues uninterrupted. `follow
<X>` on the contact already being glassed does not lower and re-raise; binoculars stay up on it.

**Falsifies the fix:** Binoculars drop after an unrecognised utterance, or `follow <same target>`
visibly lowers and re-raises rather than continuing.

**Record:** Did either interruption happen? If `follow` named a *different* contact while glassing
X, binoculars lowering and re-pointing is correct — don't confuse the two cases.

## Prize block

**Block 1 is the prize.** It's the highest-priority defect from your last sortie and the
no-omniscience invariant is the project's core rule — a false pass here (a callout that shouldn't
have happened) matters more than anything else on this card.

## Bring back

- Did any callout arrive for a masked contact? (Block 1)
- Did binoculars come back to a held-range watched contact, and how often? (Block 2)
- Did an unrecognised utterance or an already-glassed `follow` ever lower binoculars? (Block 3)
- Anything that surprises you is worth more than anything on this list.
