### Review Summary

Reviewed `fix/confirm-band-affirmatives` (tip `c33739e`, one commit on `main` @ `8e9282b`) — HEAD
matched the expected tip exactly, reviewed directly in the checkout, no worktree/archive needed.

Touches `body-layer/src/belief/voice_commands.py` (word sets, `CONFIRM_WINDOW_S`, new
`CONFIRM_LATE_ANSWER_GRACE_S`), `body-layer/src/belief/crew_console.py` (new
`_confirmation_expired_sim` field and its two check sites in `handle_transcript`), tests, and
`todo/todo.md`. All commands pass: `ruff format --check` clean, `ruff check` clean, `mypy --strict`
clean (52 files), `pytest` 1307 passed / 4 xfailed.

The lifecycle of `_confirmation_expired_sim` was traced by hand and confirmed correct for the paths
the plan targeted: it is set only on expiry, cleared unconditionally whenever a pending
confirmation is answered in time (whichever of the three places creates that pending confirmation —
the voice band, `_handle_brain_confirm`, or `_handle_brain_ask`), and cleared when a fresh question
is asked. The two brain-reply paths don't explicitly clear it themselves, but this is harmless: any
new `_pending_confirmation` is caught by `handle_transcript`'s top block on the next call, which
clears both fields together before the late-answer branch is ever reached — so there's no window
where a genuine answer to a *new* question gets intercepted by a stale expiry from an *old* one.

One required fix, confirmed by direct reproduction, not by reading alone.

### Required Fixes

- **The late-answer grace branch can swallow an unrelated, fresh utterance, not just a late
  answer — reproduced, not merely suspected.** `classify_yes_no` matches on the transcript's
  *first word only* (`voice_commands.py:216-220`), and the widened `_AFFIRM_WORDS` now includes
  ordinary sentence-openers people actually use on the radio: `ok`, `okay`, `correct`, `yeah`,
  `yep` (plus `confirm`/`confirmed`, which is also plausible as an opener). The new
  `CONFIRM_LATE_ANSWER_GRACE_S` window (20 s) means that for up to 20 seconds after *any* confirm
  question expires — answered or not — the next utterance is checked against this set before it
  ever reaches command classification.

  Reproduced directly: after a confirm question is asked and left to expire, a transcript 5 s
  later reading `"okay watch that truck at three o'clock"` — an ordinary tactical report that has
  nothing to do with the expired question — returns `["Say again?"]` and drops the report
  entirely, rather than reaching `_handle_utterance`/escalation as it would have before this
  change (and as it still does outside the grace window).

  This is exactly the class of regression the fix was trying to avoid introducing elsewhere: it
  trades a bug that fired on *every* cancel for a narrower one that fires whenever a pilot happens
  to open a fresh sentence with a common word within 20 s of a lapsed confirm — which, for exactly
  the kind of clipped tactical speech this project models, is not a rare phrasing.

  It also invalidates a safety claim stated twice in this same commit. `voice_commands.py`'s
  `_AFFIRM_WORDS` docstring says the set "is consulted only inside an open confirm window, so
  widening it cannot collide with any command" — true for literal command-token collisions (there
  is no command token spelled `ok`/`yeah`/etc., confirmed by grep against
  `audio-adapter/src/vocabulary.py`), but the grace window this same commit adds in
  `crew_console.py` now also consults this set for up to 20 s with **no confirm window open at
  all**, which is the exact condition the docstring says doesn't happen. `todo/todo.md`'s entry
  makes the identical claim and needs the same correction.

  Fix suggestion: gate the late-answer branch on more than "first word is in the set" — e.g.
  require the transcript to be short (a real late answer to a yes/no question is one or two
  words; `"okay watch that truck at three o'clock"` is not), or require the *whole* normalised
  transcript to be a member of the word sets rather than just its first token, in that branch
  specifically. Add a test for the swallow case (a multi-word utterance opening with an affirm/
  negative word, arriving within the grace window) alongside the existing expiry/grace tests.

### Optional Refinements

- `_confirmation_expired_sim` is never reset to `None` once its grace window has fully elapsed
  without a yes/no answer or a fresh question — it just sits at a stale timestamp forever, since
  every later `since_expiry` computation is `> CONFIRM_LATE_ANSWER_GRACE_S` and the branch never
  fires. Functionally inert (the guard makes it dead weight, not a bug), but worth a one-line
  reset for hygiene/debuggability — a `repr=False` field holding a meaningless multi-flight-old
  timestamp is a minor trap for anyone reading state via a debugger later. (Optional.)
- The `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_GRACE_S` reasoning is honestly caveated ("still not
  measured end to end") and the cited numbers check out against real sources: Whisper `small.en`
  p90 1.46 s / max 1.68 s matches `audio-adapter/research/2026-09-19-whisper-model-sweep.md:10`,
  and the TTS "<1s is not laggy" framing matches `audio-adapter/ROADMAP.md:73`. No fix needed here
  — flagging only that this held up under verification, unlike some past latency claims in this
  project.
- The test-file change (`test_handle_transcript_confirm_expires_after_window` changed rather than
  extended) was the right call: the scenario's assertion legitimately changed (expiry now falls
  inside the new grace window, so "Say again?" is the correct new behavior for that exact input),
  and the commit added a *new* test
  (`test_handle_transcript_late_answer_beyond_the_grace_falls_through`) that covers what the old
  test used to guard — silence/no-command-fired once genuinely past the grace. Nothing lost.

### Verdict

NEEDS REVISION — one required fix (the free-speech-swallow window), everything else sound.

### Review Confidence

Full read of both changed source files and the relevant test diffs; lifecycle of the new state
field traced by hand across all three code paths that touch `_pending_confirmation`
(voice band, `_handle_brain_confirm`, `_handle_brain_ask`); the required-fix finding was verified
by direct reproduction (a standalone script exercising `CrewConsole.handle_transcript`), not
inferred from reading; the two cited external latency numbers were checked against their source
research docs rather than trusted from the docstring's citation alone.

---

## Review: fix commit `2471542` (whole-transcript `classify_yes_no`)

HEAD matched the expected tip (`2471542`, one commit on `c33739e`) — verified via `git rev-parse
HEAD` before anything else.

**The requested fix landed correctly, at the right layer.** The implementer rejected my suggested
mitigation (gate only the grace branch on transcript length) in favor of fixing `classify_yes_no`
itself, because the same first-word hole existed *inside* the open confirm window too — a pending
"scan ahead" confirm answered with "okay scan left" would previously have matched first-word
"okay" and committed the stale `scan_ahead`, not been re-evaluated as the new command it actually
is. Fixing the classifier closes both call sites with one change; my suggestion would have left
the in-window half of the same hole standing. Re-ran my exact original repro
(`"okay watch that truck at three o'clock"`, 5 s after an expired confirm) — it now falls through
to `classify_response` instead of being swallowed, matching the new
`test_handle_transcript_grace_window_does_not_swallow_a_real_utterance`. The false "cannot
collide" safety claim is corrected in both places it appeared (`_AFFIRM_WORDS` docstring,
`todo/todo.md`).

Checks: `ruff format --check` / `ruff check` clean, `mypy --strict` clean (52 files), `pytest`
1311 passed / 4 xfailed.

**New required fix, found by direct reproduction, in the direction this fix opens.** The
whole-transcript rule can now *reject* a real answer a plausible pilot would give — not just
mixed answers, which are refused on purpose, but ordinary short affirmations that add one more
word beyond the closed filler list (`{that, sir, copy, please}`):

```
'yes do it'          -> other
'affirm execute'     -> other
'roger wilco'         -> other
'yes go ahead'       -> other
'affirmative sir go' -> other
```

(`confirm that` / `yes copy that` do work — the filler list covers those two-word radio forms.)

This matters because of what "other" *does* here, not just that it's the wrong label. Within the
open window, `handle_transcript` clears `_pending_confirmation` unconditionally before checking
the classification, so an "other" result discards the pending command **silently** (Decision 4
Layer 3's designed behavior for stale/ambiguous input, now reached by a wider set of genuine
answers than before this commit). For "cancel everything, confirm?" -> "yes, do it", the cancel
now simply does not happen, with no "Say again?", no "Unable" — nothing. That is a worse pilot
experience than the original defect this whole branch exists to fix: an "Unable, no such command"
at least tells the pilot something went wrong; a silent non-cancel does not. And unlike the
grace-window swallow (which needed an *unrelated* sentence happening to open with a matched
word), this fires on a *directly on-topic* elaboration of the same answer — arguably more likely
in real cockpit speech than the bare single-word answers the existing tests all use.

This is not a hypothetical: it directly contradicts the fix's own stated design intent. The
`classify_yes_no` docstring says "a real answer here is one or two words" — but "yes do it" *is*
a real answer of three words, reinforcing rather than replacing the affirmation, and the closed
filler list is simply too narrow to recognize it as such.

Fix suggestion: don't require every remaining word to be in the closed filler set. A cheaper and
more forgiving rule that still blocks the demonstrated free-speech case: accept as
affirm/negative when the *first* word is an answer word **and** the transcript is short overall
(e.g. word count <= 3-4) — `"okay watch that truck at three o'clock"` (8 words) still fails that
test, while `"yes do it"` / `"roger wilco"` / `"affirm execute"` (2-3 words) pass. Whichever shape
is chosen, add tests for these specific short-elaboration forms alongside the existing
sentence-swallow and mixed-answer tests — the sortie that will validate this feature (still
correctly marked "unflown" in `todo/todo.md`) is exactly where phrasing like this will show up
first, and it's cheaper to test for now than to diagnose from a third live-sortie report later.

**Everything else checked out:**
- In-window fall-through for a genuine new multi-word command while a confirm is pending is still
  correct — `test_handle_transcript_confirm_then_unrelated_answer_discards_and_processes_new`
  (pre-existing, unchanged) still passes, and its mechanism (whole-transcript check on "watch
  nearest" -> "other" -> discard pending, process new command) is unaffected by this commit's
  change in the way that matters: multi-word *unrelated* commands still fall through correctly,
  it's specifically multi-word *elaborated answers* that now misclassify.
- The filler list itself (`that`/`sir`/`copy`/`please`) is a reasonable, conservative starting
  set and not a slippery slope as written — it's closed, small, and each word is inert on its own
  (`"copy"` alone still classifies as `"other"`, unchanged from before this whole branch, since
  `"copy"` was never a member of `_AFFIRM_WORDS` either). The problem isn't the list's contents,
  it's that "every remaining word must be filler" is a stricter bar than "a real answer would
  plausibly clear."
- Mixed-answer refusal (`"yes no"` -> `"other"`) is correct and appropriately conservative —
  no change requested there.
- `plans/confirm-band-affirmatives/review.md` (this file, the prior review round) and the
  reviewer agent-memory note were correctly carried into this commit rather than left unstaged.

### Verdict (this round)

NEEDS REVISION — one required fix (short-elaboration answers silently rejected in-window), same
severity class as the previous round's finding: a real, reproduced case where the confirm band's
own stated goal ("make it answerable") fails for plausible pilot speech, just moved from
over-acceptance to under-acceptance.

### Review Confidence (this round)

Full read of the diff between `c33739e` and `2471542`; re-ran the original repro to confirm the
requested fix actually closes it; the new required-fix finding was verified by direct
reproduction of `classify_yes_no` against several short plausible answers, and by tracing
`handle_transcript`'s in-window discard path to confirm what "other" actually does to a pending
command (silent discard, not a retry prompt) rather than assuming from the docstring.

---

## Review: fix commit `a631e7a` (`verb_anchored` as the discriminator)

HEAD matched the expected tip (`a631e7a`, one commit on `2471542`) — verified via `git rev-parse
HEAD` first.

**The reasoning for rejecting my Round 2 suggestion is correct, and I confirmed it rather than
took it on faith.** My proposed "first word answers AND ≤3-4 words" rule would accept `"okay scan
left"` (3 words, first word an answer word) as an affirm inside an open window — committing a
stale pending command and dropping the genuinely new one, which is exactly the failure Round 1's
own `test_handle_transcript_confirm_then_unrelated_answer_discards_and_processes_new` exists to
prevent. Both of my suggested rules and both of the implementer's tried to decide from the
transcript's text alone, and text alone can't separate `"okay scan left"` from `"yes do it"` —
they're the same shape. Using `verb_anchored`, a signal from *outside* the text (the adapter's own
match attempt), is the right category of fix.

**But `verb_anchored` is not reliable for exactly the vocabulary this module depends on, and I
confirmed this against the real matcher, not a mock.** `audio-adapter/src/command_matcher.py`
computes it by fuzzy-matching the transcript's first word against `VERB_ANCHOR_WORDS` at
`VERB_FLOOR = 0.5` — deliberately permissive, "asymmetric" toward false anchors, per that module's
own docstring. I ran every current answer word through `_verb_anchor_ratio` directly:

```
roger      0.55  ANCHORS  (vs "report")
ok         0.67  ANCHORS
okay       0.57  ANCHORS
negative   0.62  ANCHORS
nope       0.50  ANCHORS
belay      0.50  ANCHORS
disregard  1.00  ANCHORS  (it IS a real command phrasing, cancel_nevermind)
yes        0.33
confirm    0.38
correct    0.46
(the rest below floor)
```

Then ran the full path end to end — a real pending confirmation ("cancel everything, confirm?"),
answered with the real `command_matcher.match_transcript()` output fed into
`CrewConsole.handle_transcript`:

| bare answer | matcher's `verb_anchored` | pilot-facing result |
|---|---|---|
| `"yes"` | `False` | commits `cancel_task` — correct |
| `"confirm"` | `False` | commits `cancel_task` — correct |
| `"roger"` | **`True`** | **"Say again?" — command not committed** |
| `"negative"` | **`True`** | **"Say again?" — pending discarded, no negative ack** |
| `"ok"` | **`True`** | **"Say again?"** |
| `"disregard"` | **`True`**, resolves to token `cancel_nevermind`, ratio 1.0 | falls through to `classify_response` instead of the negative-answer branch; currently a no-op only because `cancel_nevermind` has no dispatch handler yet |

`classify_yes_no` returns `"other"` the instant `verb_anchored` is `True`, before it even looks at
the word. For `"roger"` and `"negative"` this is a real regression, not an edge case: both are
founding vocabulary — `_AFFIRM_WORDS`/`_NEGATIVE_WORDS` had exactly `{affirm, affirmative, yes,
roger}` / `{negative, no, disregard}` before any of these three rounds started, per Round 1's own
diagnosis in `todo/todo.md`. This branch has now broken two words that worked correctly before it
touched anything, using the exact single-word phrasing the confirm band is supposed to make
answerable, and it does so silently — the visible symptom ("Say again?") is milder than the
original "Unable, no such command," but the command still does not commit, so the pilot has to
notice and retry rather than being told anything is wrong.

`"disregard"` is worse in kind: it isn't merely misclassified, it now falls all the way through to
being treated as an attempted *command* (the adapter resolves it to `cancel_nevermind` at
`match_ratio=1.0`), bypassing the intended negative-answer branch entirely. `_NEGATIVE_WORDS`'s own
docstring in `voice_commands.py` claims this is safe by construction: *"the two meanings never
compete, because this set is consulted only inside \[the confirm] window and `cancel_nevermind` is
matched by the adapter outside it."* That was true when `classify_yes_no` only looked at the
transcript's text — it is no longer true now that `verb_anchored` (the adapter's own match
verdict) is threaded into the same function the docstring is describing. The two meanings *do*
compete now, and the command-meaning wins whenever the fuzzy anchor fires, which for `"disregard"`
is always (ratio 1.0, it's an exact phrasing). It happens to be inert today only because
`cancel_nevermind` has "no dispatch behaviour" yet (confirmed via the repro's own stderr) — the
moment that token gets a real handler, a bare "disregard" answer to *any* pending confirm question
will run that handler instead of discarding the pending command, and nothing in this change's
tests would catch it.

**Answering the four specific judgment questions:**

1. **Is `verb_anchored` reliable here?** No — demonstrated above. It can be `True` for a bare
   answer word a pilot plausibly says alone (`"roger"`, `"negative"`, `"ok"`, `"okay"`, `"nope"`,
   `"belay"`, `"disregard"`), because `VERB_ANCHOR_WORDS`' fuzzy floor (0.5) was tuned for a
   different asymmetry (a false verb rejection is worse than a false verb anchor, per that
   module's own docstring) with no awareness that its output would later gate a *different*
   module's yes/no vocabulary. It is reliable in the direction the commit message argues (a real
   command like `"okay scan left"` does anchor, correctly), just not reliably *absent* for the
   bare answer words it needs to stay absent for.
2. **The `verb_anchored=False` default** does not hide a real production path — both call sites in
   `crew_console.py` pass `handle_transcript`'s own required (non-optional) `verb_anchored`
   parameter through explicitly, and the `!voice` harness's own syntax requires the operator to
   type a `0|1` for it (`crew_console.py:1882`). Every direct call using the default is a test.
   This part is sound.
3. **Is 4 words defensible?** As a backstop behind a discriminator that actually worked, yes —
   it's honestly labelled "a round number, not a measurement," and it correctly rejects the
   original 8-word free-speech case even in the (hypothetical) situation where verb-anchoring
   fails to fire on a short non-answer opener. Given finding 1, though, it is now carrying more
   weight than "belt to its braces" implies, since the primary buckle is failing for several real
   words.
4. **Stale docstring left by an earlier round**: yes — `_NEGATIVE_WORDS`'s "the two meanings never
   compete" claim, quoted above, is the one that matters; it was accurate through Rounds 1-2 and
   is falsified by this round's own change. `todo/todo.md`'s Round 3 summary doesn't repeat the
   false claim but also doesn't mention this collision at all, so it isn't stale, just incomplete
   once this is fixed.

Fix suggestion: don't gate on `VERB_ANCHOR_WORDS`' general-purpose fuzzy floor for this. Either
(a) check word-set membership *before* consulting `verb_anchored` — if the first word is an exact
member of `_AFFIRM_WORDS`/`_NEGATIVE_WORDS`, decide from the text as before and only fall back to
`verb_anchored` for the ambiguous multi-word cases the word-only rules got wrong; or (b) exclude
`_AFFIRM_WORDS`/`_NEGATIVE_WORDS` members from ever fuzzy-anchoring in `command_matcher.py` itself
(a cross-subproject change, and a bigger one — audio-adapter has no reason today to know
body-layer's answer vocabulary, so this would introduce the coupling explicitly rather than
leave it implicit and untested). (a) is the smaller, more local fix and keeps the coupling inside
body-layer where the confirm band already lives. Either way, add a regression test that runs the
*real* `command_matcher.match_transcript` (or a small fixture mirroring its verb-anchor floor)
against every word in `_AFFIRM_WORDS | _NEGATIVE_WORDS` and asserts none of them anchors — that is
the test this round's own suite is missing, and it's exactly the kind of cross-subproject
assumption this project's "module independence" note warns can drift silently.

### Verdict (this round)

NEEDS REVISION — the chosen discriminator is right in kind but is demonstrably wrong for at least
three specific words already in this module's own vocabulary, two of which predate this whole
three-round fix. `"roger"` and `"negative"` — plausibly the two most likely words a pilot actually
says — no longer commit or discard a pending confirmation; `"disregard"` no longer discards one
either and is one future dispatch-table entry away from doing something unrelated instead.

### Review Confidence (this round)

Full read of the diff between `2471542` and `a631e7a`. The required-fix finding was verified two
ways, neither by inference: `_verb_anchor_ratio` was run directly against every current answer
word to find the collisions, and then the real `command_matcher.match_transcript` output was fed
through an actual `CrewConsole.handle_transcript` call (a full pending-confirmation round trip) to
confirm the pilot-facing outcome, not just the classifier's internal return value.
