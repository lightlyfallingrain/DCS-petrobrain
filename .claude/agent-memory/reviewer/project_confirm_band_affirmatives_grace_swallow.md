---
name: confirm-band-affirmatives-grace-swallow
description: fix/confirm-band-affirmatives — four review rounds, each fix breaking a different real case; "verify against the real adjacent function, not the fix's own test defaults" is the technique that caught every one
metadata:
  type: project
---

Reviewed `fix/confirm-band-affirmatives` (body-layer) across four rounds, fixing the
2026-09-26 "cancel" -> "confirm?" -> "yes"/"confirm" -> "Unable, no such command." sortie defect.
Every round was caught by direct reproduction against the real code (or the real adjacent
subproject function), never by reading the diff or trusting the fix's own tests alone.

**Round 1 (`c33739e`)**: widened `_AFFIRM_WORDS`, added a late-answer grace window.
`classify_yes_no` matched only the first word, so the widened set let an unrelated sentence
("okay watch that truck at three o'clock") get swallowed as a late answer. NEEDS REVISION.

**Round 2 (`2471542`)**: required *every* word to be an answer word. Broke the opposite
direction: "yes do it" etc. became "other", silently discarding a pending command with zero
feedback inside the open window. NEEDS REVISION.

**Round 3 (`a631e7a`)**: used `command_matcher`'s `verb_anchored` as the discriminator, gating
every word on it. `VERB_FLOOR=0.5` fuzzy-matches several answer words against real command verbs
(`roger` 0.55 vs "report", `ok`/`okay`/`negative`/`nope`/`belay` also clear it, `disregard` is a
literal `cancel_nevermind` phrasing at 1.00) — broke bare `roger`/`negative`, which worked before
this whole branch existed. NEEDS REVISION.

**Round 4 (`7126236`)**: made `classify_yes_no` the union of all three rounds' rules in a fixed
order (whole-transcript-is-answer-words first, without consulting the anchor; then anchor; then
first-word+length-cap backstop), with a small filler list restored for rule 1 only. Correctly
fixed bare `roger`/`negative`/`disregard`. Also asserted the cross-subproject fact on *both*
sides without either subproject importing the other (`audio-adapter` pins that these 7 words
anchor; `body-layer` pins what the classifier does given that value) — a good pattern for a fact
that can't be shared by import under this project's module-independence rule.

**But found a fourth real gap, same technique as every round**: the round's own carried-over
test (`test_classify_yes_no_accepts_a_short_elaborated_answer`) asserts `"roger wilco"` and
`"negative hold off"` classify as affirm/negative, but calls `classify_yes_no(answer)` with the
**default** `verb_anchored=False` rather than a real value. Fed the real `match_transcript`
output through the actual `CrewConsole.handle_transcript` round trip: both phrases get
`verb_anchored=True` from the real matcher (their first word still fuzzy-anchors; only the
*trailing* words differ from the bare case round 4 fixed), so they return `"other"` in production
and the pilot gets "Say again?" instead of a commit/discard. Root cause: `verb_anchored` is
computed from the first word alone, independent of anything after it, so rule 3 (the
first-word+length-cap rule built for "yes do it"-style elaboration) is *dead code* for any
opener that both is an answer word and fuzzy-anchors but isn't itself a filler word to the
matcher (`roger`/`negative`/`nope`/`belay`/`disregard` — `ok`/`okay` are exempt because
`audio-adapter`'s own `FILLER_WORDS` strips them before the anchor check, which is *why* "okay do
it" already worked correctly and "roger wilco" didn't).

**Proposed fix, verified before writing it up (learning from rounds 2/3's mistake of proposing
untested rules)**: swap the rejection signal from "did the first word fuzzy-anchor" to "did the
matcher resolve an actual token" (`MatchResult.token is not None`) — data already available at
both `crew_console.py` call sites, no adapter change needed. Simulated this substitution against
every phrase established as a fixed point across all four rounds (`"okay scan left"` still
"other" via its real token match; `"roger wilco"`/`"negative hold off"`/`"nope hold on"`/
`"belay that order"` now correct; nothing else changes) before recommending it.

**The recurring pattern across all four rounds**: each fix correctly solves the exact case that
motivated it, using a signal that turns out to have a blind spot the previous rounds' own tests
never exercised — because each round's tests use hand-picked/default parameter values instead of
the real value the adjacent function would actually produce for that exact phrase. The technique
that caught every single round: **run the phrase through the real adjacent function (or the real
end-to-end call path) rather than trusting a test that supplies its own value for the parameter
under scrutiny.** A test asserting `classify_yes_no("roger wilco") == "affirm"` with an implicit
default parameter looks like coverage; it is not coverage of what production actually sends.

See [[feedback_bounded_magnitude_isnt_optional_severity]] — every finding across all four rounds
was Required because it contradicted the fix's own stated intent or its own shipped test's
assertion, verified by direct reproduction, not because a worst case was large.
