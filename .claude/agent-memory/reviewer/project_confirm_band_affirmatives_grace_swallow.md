---
name: confirm-band-affirmatives-grace-swallow
description: fix/confirm-band-affirmatives (c33739e) review outcome — NEEDS REVISION on a late-answer grace window that swallows unrelated free speech
metadata:
  type: project
---

Reviewed `fix/confirm-band-affirmatives` (body-layer, tip `c33739e`) — the fix for the 2026-09-26
"cancel" -> "confirm?" -> "yes"/"confirm" -> "Unable, no such command." sortie defect. Widened
`_AFFIRM_WORDS`/`_NEGATIVE_WORDS`, raised `CONFIRM_WINDOW_S` 8.0->15.0, added
`CONFIRM_LATE_ANSWER_GRACE_S` (20.0) + `CrewConsole._confirmation_expired_sim` so a late yes/no
after expiry draws "Say again?" instead of escalating to the brain as free speech.

**Found one required fix by direct reproduction, not by reading alone**: `classify_yes_no`
matches on the transcript's *first word only*. The widened affirm set now includes ordinary
sentence-openers ("ok"/"okay"/"correct"/"yeah"/"yep"), and the new 20s grace window checks *every*
post-expiry transcript against that set before command classification — with no confirm window
open. A standalone repro script fed `"okay watch that truck at three o'clock"` 5s after an
unanswered confirm expired and got back `["Say again?"]`, silently dropping the tactical report.
This also falsifies a safety claim stated twice in the same commit (`voice_commands.py`'s
`_AFFIRM_WORDS` docstring and `todo/todo.md`'s entry): "the set is consulted only inside an open
confirm window, so widening it cannot collide with any command" — true for literal command-token
collisions, false once the grace window (added by this same commit, in a different file) is
counted.

**Technique worth repeating**: when a fix adds a *time-windowed* reinterpretation of a shared
word-classification function (`classify_yes_no` here, used both inside the confirm window and in
the new post-expiry grace window), write a standalone repro exercising the new window with a
plausible *unrelated* multi-word utterance, not just the single-word inputs the implementer's own
tests use. The implementer's tests were all one-word answers ("roger", "confirm"); the swallow
only shows up with a longer sentence that happens to open with a matched word — exactly the shape
real radio speech takes and exactly the shape a same-word single-token test can't catch.

The `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_GRACE_S` docstring math (Whisper `small.en` p90
1.46s, TTS "<1s") was checked against real research docs (`audio-adapter/research/
2026-09-19-whisper-model-sweep.md`, `audio-adapter/ROADMAP.md`) and held up — not fabricated,
unlike some past latency claims in this project. The one existing test that was changed rather
than extended was the right call — its assertion legitimately changed and a new test covers what
it used to guard.

See [[feedback_bounded_magnitude_isnt_optional_severity]] — same axis distinction applies: the
swallow window is narrow (20s, only if the next utterance opens with a matched word), but it
violates a stated invariant (the docstring's "cannot collide" claim), which is what made it a
required fix rather than optional.
