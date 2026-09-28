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

---

## Review: fix commit `7126236` (union of all three rounds' rules)

HEAD matched the expected tip (`7126236`, one commit on `a631e7a`) — verified via `git rev-parse
HEAD` first.

Checks: body-layer ruff/mypy clean, pytest 1313 passed / 4 xfailed. audio-adapter ruff/mypy clean,
pytest 213 passed / 1 skipped — re-ran all four independently rather than trusting the report.

**The two-sided coupling assertion is the right shape.** Judged
`test_several_confirm_band_answer_words_do_anchor_a_verb`
(`audio-adapter/tests/test_command_matcher.py`) against "is this brittle" — no. It pins a fact
about the *current* phrase table (these seven words clear `VERB_FLOOR`), is explicitly labelled as
updatable if the table changes such that one stops anchoring, and its actual job is to make the
*dangerous* direction (a word that starts fuzzy-anchoring and nobody in body-layer notices) visible
where it originates. That's the correct failure mode to guard against for a fact that can't be
shared by import (module independence). No change requested here.

**But the fix's own worked example is where round 4 stops short, and running it end to end finds
a fourth real gap — round 4 verified `"roger"`, `"roger that"`, `"yes do it"`, `"affirmative"` end
to end, but not the two elaborated forms its own carried-over test asserts must also work:**
`"roger wilco"` and `"negative hold off"` (`test_classify_yes_no_accepts_a_short_elaborated_answer`,
inherited from round 2, still calling `classify_yes_no(answer)` with the **default**
`verb_anchored=False` rather than a real value). Fed the real `match_transcript` output for these
two phrases through the same `CrewConsole.handle_transcript` round trip used in every prior round:

| answer to "cancel everything, confirm?" | matcher's real `verb_anchored` | pilot-facing result |
|---|---|---|
| `"roger wilco"` | **`True`** | **"Say again?" — not committed** |
| `"negative hold off"` | **`True`** | **"Say again?" — not discarded** |
| `"nope hold on"` | `True` (same shape) | same failure |
| `"belay that order"` | `True` (same shape) | same failure |
| `"roger that"` | `True` | commits correctly (rule 1 catches it — `"that"` is filler) |
| `"yes do it"` | `False` (real) | commits correctly |
| `"okay do it"` | `False` (real — `"okay"` is one of *audio-adapter's own* `FILLER_WORDS`, stripped before the anchor check) | commits correctly |

**Root cause, confirmed by direct calculation, not guesswork:** `verb_anchored` is computed from
only the transcript's *first word*, independent of anything after it. For a first word that both
(a) is a real answer-set member and (b) is not one of `audio-adapter`'s own filler words (`roger`,
`negative`, `nope`, `belay`, `disregard` — `ok`/`okay` are exempt because they *are* filler there),
the anchor is constant regardless of what follows: any elaboration that isn't itself all
answer-words (rule 1) or made only of body-layer's small filler set gets intercepted by rule 2
before rule 3 (the first-word + length-cap rule built specifically for `"yes do it"`-style
elaboration) is ever reached. Rule 3 is therefore live code for `yes`/`affirm`/`affirmative`/
`confirm`/`confirmed`/`correct`/`yeah`/`yep`/`no`/`ok`/`okay`, and **dead code** for `roger`/
`negative`/`nope`/`belay`/`disregard` whenever they're elaborated with a real (non-filler,
non-answer) word — exactly the five words round 3 found were the ones actually broken by
`verb_anchored` in the first place.

**The fix is small and doesn't require any adapter-side change**, because a better signal than
`verb_anchored` is already flowing through the same seam and unused by `classify_yes_no`: whether
the matcher actually resolved a *token* (`MatchResult.token is not None`), not merely whether the
first word fuzzy-anchored. `"okay scan left"` gets a real token (`scan_left`, ratio 1.0) — a
genuine phrase match, correctly still "other". `"roger wilco"` gets `token=None` — the anchor fired
but nothing in the phrase table matched, which is exactly the "false anchor, no real command"
case `VERB_FLOOR`'s own docstring already describes as expected and common. I simulated the
substitution (`token is not None` in place of `verb_anchored` at rule 2) against every case
established across all four rounds, using the real `match_transcript` output for each:

- `"okay scan left"`, `"okay watch that truck at three o'clock"` → still "other" (correct,
  unaffected — the long-sentence case is still caught by the length cap regardless).
- `"roger wilco"`, `"negative hold off"`, `"nope hold on"`, `"belay that order"` → now "affirm"/
  "negative" correctly.
- `"yes do it"`, `"affirm execute"`, `"yes go ahead"`, `"okay do it"`, `"ok go ahead"` → unaffected,
  still correct.
- The one existing test this changes the meaning of is
  `test_classify_yes_no_defers_to_the_matchers_verb_anchor_for_a_sentence`'s
  `classify_yes_no("no watch nearest", verb_anchored=True)` — a hand-built input where the real
  matcher would never actually set `verb_anchored=True` for that phrase (it doesn't anchor in
  reality) or find a token either, so under the corrected signal this specific synthetic case
  would need `token_found` supplied directly (`True`) to keep testing the branch, rather than
  relying on `verb_anchored`'s name matching the parameter.

Suggested concrete change: at both call sites in `crew_console.py`, pass `token is not None` (a
value already computed by the caller) instead of the raw `verb_anchored` boolean — either by
renaming the `classify_yes_no` parameter to reflect what it now means, or by computing the
boolean at the call site and keeping the parameter name generic. Either way, add
`"roger wilco"`/`"negative hold off"`-shaped tests that use the *real* `match_transcript` output
(mirroring what `test_classify_yes_no_never_lets_the_anchor_overrule_a_bare_answer` already does
for the bare-word case), not the default/hand-picked boolean the current
`test_classify_yes_no_accepts_a_short_elaborated_answer` still uses for these two phrases.

**Should the end-to-end check become a committed test?** Not as a cross-subproject import — root
`CLAUDE.md` states module independence as a standing rule with `body-layer`↔`world-model` the
*sole* deliberate exception, so a body-layer test importing `audio_adapter.command_matcher` (or
the reverse) would be a second, unjustified instance of exactly the coupling that rule warns
against, even though the fact being tested is real and worth pinning. The two-sided
same-subprojects-own-fact pattern already in this commit (`audio-adapter` pins what anchors,
body-layer pins what the classifier does with a given `verb_anchored` value) is the right shape
for staying inside that rule — it just needs the *values* in body-layer's own tests to be ones
the real matcher would actually produce for the phrases in question (verified against
`match_transcript` once, by hand, when the test is written) rather than assumed. A standalone
script exercising the seam end to end (like the one used for this and the last two rounds'
repros) is worth keeping around as a manual/CI-adjacent check outside either subproject's own
test tree, if this keeps recurring — but that is process, not something this review is blocking
on.

**Answering the two remaining questions:**
- **Is the 4-word cap still defensible?** As a backstop for the cases it's actually reached for
  (the non-anchor-vulnerable openers), yes, unchanged from round 3's judgement. It does not need
  to change for this fix; the fix is about *reaching* rule 3, not about its cap once reached.
- **Anything stale?** `todo/todo.md`'s item 1 (fixed on `fix/confirm-band-affirmatives`) still
  describes round 3's superseded model verbatim — *"The signal that actually decides it was
  already at the seam: `verb_anchored`... 'okay scan left' anchors on a verb and is a command;
  'yes do it' anchors on nothing and is an answer"* — with no mention that round 4 found
  `verb_anchored` alone unsafe for bare answers and built the three-rule union that superseded it.
  It isn't *false* (that was an accurate account of round 3's commit at the time), but it now
  reads as the final explanation of a design that changed twice since. Worth a short addendum
  covering rounds 3 and 4's corrections, the same way item 1 already narrates its own history for
  rounds 1 and 2.

### Verdict (this round)

NEEDS REVISION — one required fix, same standing as every prior round: a phrase the fix's own test
suite asserts must work (`"roger wilco"`, `"negative hold off"`, and by the same shape `"nope hold
on"`/`"belay that order"`) does not, once run against the real matcher rather than the test's
hand-picked default. The fix is well-understood and low-risk this time — swap the rejection
signal from "did the first word fuzzy-anchor" to "did the matcher actually resolve a token,"
using data already available at both call sites — and I verified the substitution against every
case established across all four rounds before recommending it, not only the new one.

### Review Confidence (this round)

Full read of the diff between `a631e7a` and `7126236`, including both subprojects' test diffs.
Re-ran all four check commands (body-layer and audio-adapter, format/lint/type/test) independently
rather than trusting the reported numbers. The required-fix finding was verified end to end
(`CrewConsole.handle_transcript` fed real `command_matcher.match_transcript` output) for the two
specific phrases the current test suite claims work; the suggested fix was not merely proposed but
simulated against every phrase established as a fixed point across all four review rounds before
being written up, specifically to avoid repeating this review's own round-2/round-3 pattern of
recommending a rule that breaks something already known to work.

---

## Review: fix commit `1044bc3` (`matched_command`, the proposed fix as landed)

HEAD matched the expected tip (`1044bc3`, one commit on `7126236`) — verified via `git rev-parse
HEAD` first.

Checks re-run independently: body-layer ruff/mypy clean, pytest 1313 passed / 4 xfailed.
audio-adapter ruff/mypy clean, pytest 213 passed / 1 skipped.

**The landed fix is exactly the one proposed in the previous round** — rule 2 now gates on
`token is not None` (renamed `matched_command`, a real improvement: the old `verb_anchored` name
no longer described what the parameter meant once round 3's signal was replaced) at both
`crew_console.py` call sites, no adapter-side change. Confirmed both test corrections are honest
about the real matcher rather than asserting a hand-picked value: I ran `match_transcript`
directly against every phrase in both corrected tests and every value matches what the real
matcher actually returns (`"roger scan left"` really does resolve `scan_left`; `"no watch
nearest"` really does resolve nothing, so the old test's `verb_anchored=True` for it asserted a
state the matcher can never produce — the exact bug class this whole sequence of rounds has been
about, now removed from the test suite that would have hidden the next one).

**Independent end-to-end sweep, not just re-reading the diff.** Ran every phrase this branch has
ever cited as a fixed point — 18 affirmative forms, 9 negative forms, 3 in-window command forms,
plus the long-sentence and late-answer expiry cases — through the real `match_transcript` →
`CrewConsole.handle_transcript` round trip myself:

- All 18 affirmative forms (`yes`, `confirm`, `confirmed`, `correct`, `ok`, `okay`, `roger`,
  `yeah`, `yep`, `affirm`, `affirmative`, `roger that`, `yes sir`, `yes do it`, `affirm execute`,
  `yes go ahead`, `okay do it`, `ok go ahead`) commit the pending command.
- All 9 negative forms (`negative`, `no`, `nope`, `disregard`, `belay`, `negative hold off`,
  `nope hold on`, `belay that order`, `negative that`) discard it silently, as designed.
- `"okay scan left"` / `"scan left"` / `"roger scan left"` while a confirm is pending all act as
  the command they are (blocked only by an unrelated harness limitation — no world-model
  connection in this standalone script — not swallowed as an answer).
- The long unrelated sentence and a late bare `"yes"` past the grace window both still draw
  "Say again?".

No mismatch anywhere in that sweep. This closes every defect found across rounds 1-4 with no
regression on any of them.

**On the deliberate scope decision (`"no watch nearest"` losing the command half):** agreed, this
is the right call and not a defect to fix. Verified the mechanism directly: the real matcher gives
`token=None`/`matched_command=False` for that exact phrase, so `classify_yes_no` reaches rule 3,
sees first word `"no"` in `_NEGATIVE_WORDS`, and returns `"negative"` — the pending command is
discarded and `"watch nearest"` is never re-evaluated, because the negative branch returns
immediately rather than falling through the way an `"other"` result would. This is a genuinely
different case from every prior round's findings: no docstring, test, or stated design intent in
this branch claims combined answer-plus-new-command-in-one-breath is handled, so there's no
contradicted invariant here, only an unhandled input class the implementer chose not to build
machinery for. Building it would mean parsing intent *inside* an answer word rather than
classifying the word itself — a materially different, bigger feature (compound-utterance
splitting) than this branch has ever been about, and four rounds have already gone into just the
single-intent case. I'd note explicitly: this is a **theoretical gap, not a defect a pilot is
likely to notice in a sortie** — it requires the pilot to fuse a negative answer and an unrelated
new command into one breath with no pause, which is a narrower and more contrived utterance shape
than any of the previous four rounds' findings (all of which were plain single-answer phrasings a
pilot would plausibly use verbatim, one of them — `"roger"`/`"negative"`, another — the two most
likely words in the entire vocabulary). No fix requested; worth a one-line note next to the mixed-
answer docstring so a future round doesn't rediscover it as a bug (optional, not blocking).

**No new defect found this round.** This is the first round of five where the sweep came back
clean.

### Verdict (this round)

**APPROVED.** All four prior rounds' findings are fixed and reverified end to end; no new defect
found despite an independent full sweep across every phrase this branch has ever touched. The one
open item (`"no watch nearest"`-shaped compound utterances) is a disclosed, reasoned scope
boundary, not a contradicted invariant, and is small enough in likelihood and consequence that
it does not belong in this branch. The item in `todo/todo.md` is accurate, current, and correctly
still marked unflown — the remaining open question (do `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_
GRACE_S` actually hold up, does "cancel" → "confirm" → the task stop in a real cockpit) is a
question a sortie answers, not a further round of static review.

### Review Confidence (this round)

Full read of the diff between `7126236` and `1044bc3`. All four check commands re-run
independently for both touched subprojects. Every value in both corrected tests was checked
against the real `command_matcher.match_transcript` output, not taken on the commit message's
word. An independent end-to-end sweep (not merely a re-run of the implementer's own claimed
sweep) was executed across every phrase cited as a fixed point in all five rounds combined,
covering affirmative, negative, in-window-command, long-sentence, and late-answer cases, before
concluding no further defect exists.
