# Brain layer Stage 2 — the real model, for the first time

**Branch: `feature/brain-layer-stage2`** — not yet merged.

```sh
git checkout feature/brain-layer-stage2 && git pull
```

## Why this flight matters more than most

Nothing in this feature has ever talked to a real model. Every commit on this branch, every
review, every test — all of it ran against a fake HTTP server standing in for Ollama, because the
sandbox these agents run in has no route to `127.0.0.1:11434`. Stage 1 already proved the plumbing
(async handoff, stand-by, staleness) with a canned stub reply. **This flight is the first time
`qwen3:4b-instruct-2507-q4_K_M` actually reads a transcript and decides anything.** Until you fly
it, "Stage 2 works" means "the code that calls the model compiles and the fake server accepted its
shape" — not that a real model's real output survives contact with the validator, or sounds right
in the cockpit.

## Setup

**Ollama must be running locally with the model pulled**, separately from the processes below:

```sh
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama serve   # if not already running as a background service
```

Windows: aircraft-layer collector, capture with `--ptt dcs` — unchanged from prior sorties.

Mac, three processes from `run-scripts/`, same shape as the last brain-layer card but with one
flag changed:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama                              # CHANGED — real model, not the stub
./run-crew-text-debug-view.sh \
    --brain-client http --brain-url http://127.0.0.1:7796
```

`run-brain.sh`'s own default is still `--decider stub` (deliberately — so the script's existing
meaning never changes underneath anyone who forgets this flag). **You must pass `--decider
ollama` explicitly**, exactly as above, or you will silently be testing the stub again.

Startup takes longer than Stage 1's card: the server runs one throwaway warm-up generation against
Ollama before it reports ready, so the first real escalation doesn't pay a cold-load penalty. Watch
`run-brain.sh`'s log for `brain-layer ready (decider=OllamaDecider)` before you fly — if it never
prints that line, Ollama is not reachable at `http://127.0.0.1:11434` (the default; pass
`--ollama-url` if yours runs elsewhere) and the server will have failed its warm-up.

## Not judgeable, and why — read before flying

- **`follow <descriptor>` picking the right contact still cannot work reliably.** The validator
  requires the model's `BECAUSE` evidence to be a literal substring of the candidate's own
  description, worded differently from how you'll say it — so it will correctly **ask** rather than
  silently pick wrong. Being fixed separately (D10's structured-candidate revision, already has its
  own branch). Not a defect to report here.
- **One slow reply can chain-drop several *later* utterances, not just its own.** Ollama serialises
  generation on one daemon — while it's still working through one reply, every utterance that
  arrives in the meantime gets no reply of its own, because each one only gets the client's own
  5-second timeout while Ollama itself keeps grinding through its queue regardless. This is reasoned
  from transport measurements plus a 32.7s worst-case generation time measured for this model against
  this prompt (D6) — it has never been observed live. Test case 4 below is built to surface it if it
  happens; if you hear silence to a rapid run of utterances where you'd expect at least an "unable"
  each, this is the likely cause, not a bug in the wire.
- **Engagement-envelope warnings still fire late** — recognition, not geometry, unchanged from prior
  cards.

## 1 — Say-again, for real. WORTH MOST

**Do.** Say something clearly outside the command vocabulary — *"see if that ridge is clear"*,
*"what's our fuel state"*, anything with no matching verb at all.

**Expect.** A spoken reply a few seconds after you finish speaking — not silence, not the same
canned line every time. This exercises the **classify** prompt: the model should recognize no known
command applies and the reply should render as "unable" / "say again" in the cockpit.

**Record.**
- [ ] Did you hear a reply, and did it arrive within a few seconds?
- [ ] Did anything else in the cockpit (scans, contact reports, other commands) feel delayed while
      it was thinking? They must not — that's the one invariant this whole feature exists to hold.
- [ ] Does the reply sound like it engaged with what you actually said, or generic?

## 2 — A real command, paraphrased

**Do.** Say a known command in unfamiliar wording — not the exact phrase Petrovich's grammar
expects, but close enough a human would understand it. E.g. instead of "watch nearest," try
"keep an eye on the closest one."

**Expect.** Either a `CONFIRM <token>` — "keep an eye on the nearest contact, is that right?" (or
similar), which you then affirm or decline — or, if the model can't match it, the same "say again"
as case 1.

**Record.**
- [ ] Did it recognize the paraphrase and offer to confirm the right command?
- [ ] If you affirmed, did the right thing actually happen?
- [ ] If it declined to guess, did it ask/say-again cleanly, without misfiring a wrong command?

## 3 — Genuinely ambiguous reference

**Do.** With two or more contacts of the same general kind visible (e.g. two tanks), say something
that could mean either — "watch that tank" — with no distinguishing word.

**Expect.** He should **ask** which one, not guess. "Which one — the one near the village, or the
one on the road?" (wording will vary — it's model-generated now, not scripted).

**Record.**
- [ ] Did he ask rather than silently pick? Silently picking one is the specific failure this
      stage's validator exists to prevent, and it is the one thing to escalate immediately if seen.
- [ ] Did the question name a real distinguishing feature, or something vague/hallucinated?

## 4 — Fire several utterances quickly, without waiting. The MONITOR case

**Do.** In under two seconds, say three or four short things in a row — commands, nonsense,
whatever — without pausing for a reply between them. (Easiest: rapid-fire a few of cases 1-3's
utterances back to back.)

**Expect.** Best case: all of them get a reply, maybe with some delay. Possible case, and the thing
this test is built to catch: some of the later ones get **no reply at all** — not "unable," not
"say again," just silence, because Ollama was still working the first one when the rest arrived.
D3's newest-wins is a different, correct behavior (an *older* one silently dropping because a
*newer* one about the *same* thing superseded it) — this is about several *different* utterances
each expecting their own answer.

**Record.**
- [ ] How many of the utterances got a reply?
- [ ] For any that didn't — was there a later reply that might explain it as newest-wins, or does
      it look like a straightforward drop?
- [ ] Roughly how long between speaking and the last reply landing?

This result is the input to whether the MONITOR finding on this becomes a required fix (throttle
or queue escalations rather than firing them all concurrently) or stays accepted as-is.

## The logs

```sh
cat ~/dcs-belief-truth.jsonl | tail -40
```

Same log as prior cards — `kind: "speech"` rows show what he said alongside gaze/optic at that
moment.

## Bring back

1. **Block 1 — did a real model answer at all, and did the cockpit stay responsive.** This is the
   headline: it has never been observed live before this flight.
2. Block 2 — did paraphrase recognition work, or degrade safely.
3. **Block 3 — did ambiguity produce a question, never a silent wrong pick.** Escalate immediately
   if this fails; it's the one safety property the whole D10 validator exists to hold.
4. Block 4 — the chain-drop MONITOR: how many replies survived a rapid-fire burst.
5. **Anything that surprises you.** Especially anything about how the model's own phrasing sounds —
   nobody has heard it yet.
