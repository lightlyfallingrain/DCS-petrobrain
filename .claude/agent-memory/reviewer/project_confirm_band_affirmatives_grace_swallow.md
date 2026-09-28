---
name: confirm-band-affirmatives-grace-swallow
description: fix/confirm-band-affirmatives (c33739e, 2471542, a631e7a) — three review rounds, each fix breaking a different, real case; cross-subproject signal coupling as the recurring root cause
metadata:
  type: project
---

Reviewed `fix/confirm-band-affirmatives` (body-layer) across three rounds, fixing the
2026-09-26 "cancel" -> "confirm?" -> "yes"/"confirm" -> "Unable, no such command." sortie defect.
Every round was caught by direct reproduction against the real code (or, in round 3, the real
adjacent-subproject function), never by reading the diff alone.

**Round 1 (`c33739e`)**: widened `_AFFIRM_WORDS`, raised `CONFIRM_WINDOW_S`, added a
`CONFIRM_LATE_ANSWER_GRACE_S` late-answer window. `classify_yes_no` matched only the first word,
so the widened set let an unrelated sentence ("okay watch that truck at three o'clock") get
swallowed as a late answer. NEEDS REVISION.

**Round 2 (`2471542`)**: fixed by requiring *every* word to be an answer word (plus a closed
filler list). Broke the opposite direction: "yes do it", "roger wilco", "affirm execute" all
became "other", which inside an open window silently discards the pending command with zero
feedback. NEEDS REVISION.

**Round 3 (`a631e7a`)**: dropped the filler list, used `command_matcher`'s own `verb_anchored`
verdict (threaded through `handle_transcript`'s existing seam) as the discriminator, plus a
4-word length backstop. Right category of fix — my own round-2 suggestion (first-word + length)
was correctly rejected because it would have accepted `"okay scan left"` as an answer, breaking
round 1's own regression test. But `verb_anchored` comes from `audio-adapter`'s fuzzy verb-anchor
match (`VERB_FLOOR = 0.5`, deliberately permissive, tuned for a different asymmetry — a false
verb-rejection is worse than a false anchor, per that module's own docstring), and several answer
words fuzzy-collide with it: `_verb_anchor_ratio` gives `roger` 0.55, `ok` 0.67, `okay` 0.57,
`negative` 0.62, `nope`/`belay` 0.50, `disregard` 1.00 (it's a real command phrasing,
`cancel_nevermind`). Fed the real `command_matcher.match_transcript()` output through an actual
`CrewConsole.handle_transcript` pending-confirmation round trip: bare `"roger"`/`"negative"`/`"ok"`
now get `verb_anchored=True` and return "Say again?" instead of committing/discarding — breaking
two words (`roger`, `negative`) that were correct *before this entire three-round fix started*.
`"disregard"` falls through to being treated as an attempted command instead of a negative
answer, currently inert only because `cancel_nevermind` has no dispatch handler yet — a latent
landmine for whenever it gets one. This also falsified `_NEGATIVE_WORDS`'s own docstring claim
that "the two meanings never compete" for `disregard`'s dual role as both an answer word and a
real command phrasing — true before `verb_anchored` was threaded in, false after. NEEDS REVISION.

**The recurring root cause across all three rounds is the same shape**: each fix tried to add one
more signal/rule to solve the previous round's failure, and each new signal turned out to have its
own blind spot the previous rounds' tests never exercised, because each round's own tests were
written to cover exactly the case that round was fixing. Round 3's specific version of this is a
**cross-subproject coupling with no test enforcing it**: `body-layer`'s answer-word vocabulary is
now implicitly dependent on `audio-adapter`'s `VERB_ANCHOR_WORDS`/`VERB_FLOOR` fuzzy-matching
behavior staying disjoint from it, and nothing in either subproject's test suite checks that.
Recommended: a regression test that runs the real `command_matcher.match_transcript` (or a small
fixture mirroring its verb-anchor floor) against every word in `_AFFIRM_WORDS | _NEGATIVE_WORDS`
and asserts none of them anchors.

**Technique that caught all three**: don't trust a classifier's own test suite to have exercised
the input that matters — construct a direct repro against the real function (round 1-2: the
classifier itself with hand-picked plausible phrases; round 3: the *adjacent subproject's real
function*, `_verb_anchor_ratio`/`match_transcript`, not a mock or an assumption from its
docstring) and, where the finding is about pilot-facing behavior, run it through the actual
`CrewConsole.handle_transcript` round trip rather than stopping at the classifier's return value.

See [[feedback_bounded_magnitude_isnt_optional_severity]] — all three findings were Required
because each contradicted a stated invariant/design intent (a safety claim in a docstring, or the
implementer's own "a real answer is one or two words" model), not merely because a worst case was
large.
