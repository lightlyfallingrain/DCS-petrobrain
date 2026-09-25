# Crew behaviour sortie

Everything merged on 2026-09-25, plus the two cards that were still outstanding when it started.
One flight, one checkout.

**Branch: `main`** — all of it is merged.

```sh
git checkout main && git pull
```

**Supersedes** `2026-09-24-watch-reporting-sortie.md`, `2026-09-25-brain-layer-stage1-sortie.md`
and `2026-09-25-brain-layer-stage2-sortie.md` (the last one folded in whole as block 4 once Stage 2
merged — its four tests are below, unchanged in substance).
Both are kept for the record and both are partly stale: the watch-reporting card was written before
`scan` stopped conferring watched-ness, and its engagement-envelope caveat predates today's fixes.
Do not fly those two; fly this.

## What changed, and why it needs your ears

Most of this came out of *your last sortie*. The eyes-and-voice flight did not come back a clean
pass — it produced eight fixes, and the value of this flight is checking whether the fixes are
right rather than whether the features exist.

| | what you should notice |
|---|---|
| **Scan is not watch** | A commanded scan no longer enrols everything it finds into unprompted reporting. This is the big one for noise. |
| **Range crossings say which way** | "Getting closer, …" / "Moving away, …" instead of a bare report that sounded like a fresh sighting |
| **Cancel means cancel** | "Cancel everything" no longer leaves an older, superseded scan running |
| **Watched contacts glassed first** | Binoculars go to what you asked about before what is merely numerous |
| **Groups register five at a time** | Was three; five is the subitizing boundary, so a dense scene lands in ~2 s instead of ~10 |
| **Petrovich answers unparseable speech** | Brain layer Stages 1 *and 2* — a real model now, not the stub. Block 4 |
| **Orange = watched** in the ASCII view | And the view now fits the console |

## Setup

**Ollama must be running locally with the model pulled**, separately from everything below:

```sh
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama serve   # if not already running as a background service
```

Windows: collector, capture with `--ptt dcs` — unchanged.

Mac, **three processes now**, each from `run-scripts/`:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama                             # NEW - real model, NOT the stub
./run-crew-text-debug-view.sh \
    --brain-client http --brain-url http://127.0.0.1:7796
```

**`--decider ollama` is not optional and is not the default.** `run-brain.sh` still defaults to
`--decider stub` deliberately, so the script's existing meaning never changes under anyone who
forgets the flag — but omit it here and you will silently be testing the stub again, and block 4
will tell you nothing.

Startup is slower than it was with the stub: the server runs one throwaway warm-up generation
against Ollama before reporting ready, so your first real utterance doesn't pay a cold load. Wait
for `brain-layer ready (decider=OllamaDecider)` in its log. If that line never prints, Ollama is not
reachable at `http://127.0.0.1:11434` (pass `--ollama-url` if yours lives elsewhere) and the warm-up
failed.

`run-crew-text-debug-view.sh` is your own debug variant — it already carries `--eyesight-view`,
`--eyesight-view-radius-m 5000` and `--belief-truth-log ~/dcs-belief-truth.jsonl`, and passes
anything extra straight through. Both of those flags earned their place last sortie: the log is what
found the 18-contact outpost, the view is what caught the scan/watch conflation. Keep them on.

**`run-brain.sh` was broken on the Mac until just now** — it used `$PETROBRAIN_PATH`, which holds the
WSL path `/mnt/d/…` and does not resolve here. Fixed to `../brain-layer/` like your other scripts.
`--help` verified; the running server was not, so if it fails to bind, say so.

**If you skip `run-brain.sh` or the two flags:** nothing breaks. Unparseable speech produces silence,
exactly as before. Worth doing once on purpose to confirm.

## Not judgeable, and why — read before flying

- **There is now a real model behind the brain** — that changed today (Stage 2 merged). This is the
  first flight where the words you hear are the model's own reasoning rather than a canned stub
  reply, so block 4 is worth more than it was on the last card.
- **Nothing in either brain stage has ever talked to a real Ollama before this flight.** Every agent
  that built and reviewed it ran in a sandbox with no route to `127.0.0.1:11434`, so all of it is
  verified against fake HTTP servers. You are the first real-model run.
- **`follow <descriptor>` picking the right contact still cannot work.** The validator requires the
  model's evidence to be a literal substring of the candidate's own description, and the pilot's
  words and that description are worded differently — so he will correctly **ask** rather than pick.
  That is being fixed (D10's structured-candidate revision, already on its own branch); do not
  report it as a defect.
- **One slow reply can chain-drop several *later* utterances, not just its own.** Ollama serialises
  generation on one daemon, so while it grinds through one reply, utterances arriving meanwhile can
  each time out with no answer. Reasoned from transport measurements plus a 32.7 s worst-case
  generation measured for this model against this prompt — **never observed live**. Block 4d is
  built to surface it.
- **The engagement-envelope warning still fires late**, and that is recognition, not geometry: with
  the naked eye and binoculars, class-level recognition of a SHORAD threat resolves well inside its
  weapon envelope. Unchanged from the last card. The 9K113 optic is what closes it.
- **Fire/damage reporting is not built yet.** The probes answered how it *will* work; nothing says
  "it's burning" in the air today.

## 1 — Scan noise. WORTH MOST

The single biggest change to what you hear, and the fix for your own complaint.

**Do.** Command a scan over a populated area — `scan right`, or a compass sector with several
vehicles in it. Then just fly and listen for a minute without watching anything.

**Expect.** Detection reports for what he finds, and then **quiet**. No unprompted movement
callouts, no kilometre crossings, no danger/safe-from calls for contacts that were merely *scanned*.
Those belong to contacts you explicitly watched.

**Record.**
- [ ] After a scan finds things, does he go quiet, or keep reporting about them?
- [ ] Anything that still feels like noise — name the wording, it identifies the callout kind
- [ ] Did the scan itself still work (gaze moved, contacts found)? The fix narrowed the area's
      attention level, and scan-task completion and gaze steering were supposed to be untouched

## 2 — Watch, and the three things a watched contact now says

**Do.** `watch nearest`, or `follow armor`, on something moving. Keep it watched for a minute while
your range to it changes.

**Expect.**
- an unprompted callout when its **motion** changes — "…, moving" / "…, stopped"
- **"Getting closer, …"** or **"Moving away, …"** as it crosses a whole kilometre inside 5 km
- **"Danger, …"** / **"Safe from …"** on weapon-envelope entry and exit, with the lateness caveat above
- in the ASCII view, that contact drawn in **orange** while everything else is yellow

**Record.**
- [ ] Do "getting closer" / "moving away" fire in the right direction? This is new wording — the
      bare form used to sound like a fresh sighting, which is what sent you looking for a bug
- [ ] Is orange visibly distinguishable from yellow on your terminal?
- [ ] Does watched-ness feel like it is on the right things — and only those?

## 3 — Cancel everything

**Do.** Issue **two** scans in sequence — e.g. `scan south`, then `scan left` — and a watch. Then
`cancel`, confirm it.

**Expect.** Everything stops. The readback names the current modes ("stop scan left and watch"), but
the *earlier* `scan south` must stop too. Last sortie it survived and took over the gaze once the
newer scan was cancelled.

**Record.**
- [ ] After cancelling, is his gaze free-scanning, or still steering to an older command?
- [ ] Does the ASCII view agree with what you expect the gaze to be doing?

## 4 — The brain, with a real model behind it

Folded in from the Stage 2 card when Stage 2 merged. Four parts; **4a is worth most**, and 4d is
the one that exists to catch something nobody has ever seen.

### 4a — Say-again, for real. WORTH MOST

**Do.** Say something clearly outside the command vocabulary — *"see if that ridge is clear"*,
*"what's our fuel state"*, anything with no matching verb at all.

**Expect.** A spoken reply a few seconds after you finish — not silence, and not the same canned
line every time, which is what the stub gave you. This exercises the classify prompt: the model
should work out that no known command applies, and it should reach you as "unable" / "say again".

**Record.**
- [ ] Did you hear a reply, and within a few seconds?
- [ ] Did anything else — scans, contact reports, other commands — feel delayed while it was
      thinking? **They must not.** That is the one invariant this whole feature exists to hold.
- [ ] Does the reply sound like it engaged with what you said, or generic?

### 4b — A real command, paraphrased

**Do.** Say a known command in unfamiliar wording — not the phrase the grammar expects, but close
enough that a person would understand. Instead of "watch nearest", try *"keep an eye on the closest
one"*.

**Expect.** Either a confirm — "keep an eye on the nearest contact, is that right?" — which you
affirm or decline, or the same say-again as 4a if it can't match.

**Record.**
- [ ] Did it recognise the paraphrase and offer the right command?
- [ ] If you affirmed, did the right thing actually happen?
- [ ] If it declined, did it ask cleanly without misfiring a wrong command?

### 4c — Genuinely ambiguous reference

**Do.** With two contacts of the same kind visible, say something that could mean either —
*"watch that tank"* — with no distinguishing word.

**Expect.** He should **ask** which one, not guess. The wording will vary; it is the model's now,
not a script.

**Record.**
- [ ] Did he ask rather than silently pick? **Silently picking is the specific failure the
      validator exists to prevent — escalate that immediately if you see it.**
- [ ] Did the question name a real distinguishing feature, or something vague or invented?

### 4d — Several utterances fast, without waiting. The MONITOR case

**Do.** In under two seconds, say three or four short things back to back without pausing for
replies. Rapid-firing 4a–4c's utterances is fine.

**Expect.** Best case, all get a reply. The case this is built to catch: some later ones get **no
reply at all** — not "unable", not "say again", just silence, because Ollama was still working the
first when the rest arrived. Note that an *older* utterance dropping because a *newer* one about the
same thing superseded it is correct behaviour and a different thing.

**Record.**
- [ ] How many got a reply?
- [ ] For any that didn't — could a later reply explain it as newest-wins, or is it a plain drop?
- [ ] Roughly how long from speaking to the last reply landing?

This answer decides whether the chain-drop MONITOR becomes a required fix (throttle or queue
escalations instead of firing them concurrently) or stays accepted.

## 5 — The dense scene

**Do.** Approach a populated outpost from a few kilometres out. Let him work it.

**Expect.** Groups registering ~5 per second rather than 3, so a dense scene lands in about two
seconds. And **fewer duplicate reports of the same thing** — last sortie an outpost fragmented into
18 contacts and he said "ground, 11 o'clock, 1 kilometre" four times. That fix is partial and
deliberately so: it attacks how fast contacts get founded, not the deeper ambiguity rule.

**Record.**
- [ ] Repeated identical callouts — still happening, or gone?
- [ ] Roughly how many distinct contacts does the ASCII view show for one group of vehicles?
- [ ] This is the one to check the log for afterwards

## The logs

```sh
cat ~/dcs-belief-truth.jsonl | tail -40
```

Rows are `kind: "belief_truth"` (or no `kind` on older files) and `kind: "speech"` — **what he said,
with the gaze and optic at the moment he said it.** That pairing is new, and it is what makes
"he called 10 o'clock while scanning right" a single line instead of a two-file correlation.

## Bring back

1. **Block 1 — is the scan noise gone.** The biggest behavioural change and your own complaint.
2. Block 2 — do the new range-crossing words fire in the right direction, and is orange legible.
3. Block 3 — does cancel really cancel.
4. Block 4 — did the brain answer, and did anything stall while it did.
5. Block 5 — repeated callouts and contact counts for one group; plus the log.
6. **Anything that surprises you.** Last sortie that was worth more than every planned item on the
   card put together.
