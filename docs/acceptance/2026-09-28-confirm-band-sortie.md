# Confirm-band sortie

**Branch: `fix/confirm-band-affirmatives`**

```sh
git checkout fix/confirm-band-affirmatives && git pull
```

## Why this card exists

Last sortie (2026-09-26): `"cancel"` -> *"Cancel everything, confirm?"* -> `"yes"` / `"confirm"` ->
*"Unable, no such command."* The confirm band could not be answered at all. Three defects behind
that one symptom, all fixed on this branch and checked by five rounds of code review, but none of
it has been flown. Static review cannot settle two things: whether the new timing windows are
actually long enough in the cockpit, and whether the fix genuinely stops a task rather than just
changing what gets said back.

**You may prefer to fly this as part of `docs/acceptance/2026-09-25-crew-behaviour-sortie.md`
instead of a separate sortie** — its block 3 ("Cancel everything") already issues `cancel` and
confirms it, so every `cancel` you speak on that card exercises this fix too. That is your call,
not decided here.

## Setup

Same as the crew-behaviour card: Windows collector with `--ptt dcs`, then from `run-scripts/` on
the Mac:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text-debug-view.sh --brain-client http --brain-url http://127.0.0.1:7796
```

(If you're not testing brain-layer behaviour today, the stub decider is fine — this fix lives
entirely in `body-layer`'s confirm band, not the brain.)

## Test cases

### 1 — Cancel, confirmed three ways

**Do.** Issue any task (e.g. `scan left`), then say `cancel`. When Petrovich asks *"Cancel
everything, confirm?"*, answer with `"confirm"`. Repeat the same sequence twice more, answering
`"yes"` and then `"roger"`.

**Expect.** All three answers are accepted — no *"Unable, no such command"* — and the task
actually stops each time (gaze goes free, ASCII view agrees).

**Record.**
- [ ] Did all three words (`confirm`, `yes`, `roger`) work, not just one?
- [ ] Did the task genuinely stop, not just get acknowledged?

### 2 — Is 15 seconds enough, and does the 20-second grace feel right

**`CONFIRM_WINDOW_S` (15.0s) and `CONFIRM_LATE_ANSWER_GRACE_S` (20.0s) are reasoned budgets, not
measurements.** The only way to check them is to fly with normal PTT habits, not to rush.

**Do.** A few times over the sortie, issue `cancel` and answer normally — however long it
actually takes you to key up and speak once you hear the question, not deliberately fast or slow.

**Expect.** You should never hear *"Say again?"* when you believe you answered promptly. If you
*do* ever get "Say again?" after a normal-paced answer, that is the finding this block exists to
catch — note roughly how long you took to respond.

**Record.**
- [ ] Any case where a prompt answer got "Say again?" instead of being accepted?
- [ ] Does answering within the ~20s grace window (i.e., a beat later than usual) still work, or
  does it feel like it's asking you to rush?

### 3 — A negative answer leaves the task running

**Do.** Issue a task, say `cancel`, and when asked to confirm, answer `"negative"`. Repeat once
with `"no"` and once with `"disregard"`.

**Expect.** The task keeps running in all three cases — nothing stops.

**Record.**
- [ ] Did all three negatives correctly leave the task alone?

### 4 — An ordinary command spoken during an open confirm question still acts as a command

**Do.** Issue `cancel`. While the confirm question is open (don't wait for it to expire), say an
ordinary command that is not an answer word — e.g. `"okay scan left"`.

**Expect.** It should act as the command it is (start scanning left), not get swallowed as if it
were answering the pending confirm question.

**Record.**
- [ ] Did the command fire normally, or did anything about it get eaten/misread as a yes/no?

## Pass criteria

The feature passes if test case 1 works with all three affirmative words and the task genuinely
stops, test case 3 correctly leaves the task running for all three negatives, test case 4's command
is never swallowed, and test case 2 surfaces no unexplained "Say again?" on a normally-paced
answer. Report anything that surprises you even if it's not one of these four blocks.
