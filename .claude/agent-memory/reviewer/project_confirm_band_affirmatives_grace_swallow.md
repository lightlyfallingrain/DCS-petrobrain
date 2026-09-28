---
name: confirm-band-affirmatives-grace-swallow
description: fix/confirm-band-affirmatives — five review rounds, APPROVED at round 5; the technique that closed it was always "run the real adjacent function, not the fix's own test defaults"
metadata:
  type: project
---

Reviewed `fix/confirm-band-affirmatives` (body-layer) across five rounds, fixing the 2026-09-26
"cancel" -> "confirm?" -> "yes"/"confirm" -> "Unable, no such command." sortie defect.
**APPROVED at round 5 (`1044bc3`)** after four straight NEEDS REVISION rounds, each caught by
direct reproduction against the real code or the real adjacent-subproject function, never by
reading the diff or trusting a fix's own tests.

**Rounds 1-4, one line each** (full detail in `plans/confirm-band-affirmatives/review.md`, which
has the complete append-only log):
1. First-word-only `classify_yes_no` let a widened answer-word set swallow unrelated free speech
   ("okay watch that truck at three o'clock").
2. Requiring *every* word to be an answer word rejected plausible elaborations ("yes do it"),
   which inside an open window silently discards the pending command with zero feedback.
3. Gating on `command_matcher`'s `verb_anchored` broke bare `"roger"`/`"negative"` — founding
   vocabulary that worked before this branch existed — because `VERB_FLOOR=0.5` fuzzy-matches
   them against real verbs ("roger" vs "report", 0.55).
4. The union-of-three-rules fix still broke elaborated forms of the *same* five anchor-prone
   words ("roger wilco", "negative hold off", "nope hold on", "belay that order"), because
   `verb_anchored` is computed from the first word alone, independent of what follows — rule 3
   (built for exactly this elaborated-answer case) was dead code for these five openers whenever
   non-bare/non-filler.

**Round 5 (`1044bc3`)**: swapped the round-4 rejection signal from `verb_anchored` to
`matched_command` (`token is not None`, already available at both call sites, no adapter-side
change) — this was my own round-4 proposal, verified end to end before it was suggested and again
after landing. Two tests corrected in the same spirit that exposed round 4: they now pass the
value the real matcher actually returns instead of a hand-picked/default one, and one test's
input (`"no watch nearest"`, which the real matcher never anchors) was swapped for one it does
(`"roger scan left"`). I independently ran a full end-to-end sweep (18 affirmative forms, 9
negative forms, 3 in-window-command forms, long-sentence and late-answer cases) through the real
`match_transcript` -> `CrewConsole.handle_transcript` path myself, not just re-reading the
implementer's claimed sweep — no mismatch anywhere.

**One disclosed, judged scope boundary, agreed with**: `"no watch nearest"` (a negative word
immediately followed by an unrelated new command in one breath) reaches body as
`matched_command=False`, classifies as `"negative"`, and the `"watch nearest"` half is lost —
because the negative branch returns immediately rather than falling through to re-evaluate.
Agreed this is not a defect: no docstring/test in this branch claims compound answer+command
utterances are handled, so nothing is contradicted, and building it would be a materially
different, bigger feature (splitting intent *inside* a word) than this branch was ever about.
Judged explicitly as a **theoretical gap, not a defect a pilot would likely notice in a sortie**
— it requires fusing a negative answer and a new command into one breath with no pause, a
narrower and more contrived shape than any of rounds 1-4's findings (which were all plain,
single-intent phrasings, several of them the single most likely words in the whole vocabulary).

**The technique that closed every round, worth reusing verbatim on any future multi-round
classifier fix**: never trust a fix's own test suite to have exercised the real value of a
parameter that comes from an adjacent function or subsystem — always run the actual value that
real function would produce (or the full real end-to-end call path) for the exact phrases the
fix claims to handle, before either finding a new defect or signing off that none remains. Every
one of rounds 1-4's defects was hiding behind a test that supplied its own default/hand-picked
value for the exact parameter under scrutiny; round 5 closed cleanly only once every value in the
test suite was checked against the real matcher by hand.

See [[feedback_bounded_magnitude_isnt_optional_severity]] — every required-fix finding across
rounds 1-4 contradicted a stated invariant or the fix's own shipped test's assertion, verified by
direct reproduction; round 5's one open item was correctly *not* elevated to a required fix
because nothing in the branch claimed to cover it.
