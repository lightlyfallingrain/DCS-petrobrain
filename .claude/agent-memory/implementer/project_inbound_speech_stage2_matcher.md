---
name: inbound-speech-stage2-matcher
description: Stage 2 of plans/inbound-speech/plan.md (command_matcher.py + belief.voice_commands) -- design gaps found and how they were resolved
metadata:
  type: project
---

Implemented on `feature/stt-command-matcher` (2026-09-19): `srs-adapter/src/command_matcher.py`
(normalise -> verb anchor -> bearing slot/phrase match -> separation check) and body-layer's
`belief/voice_commands.py` + `CrewConsole.handle_transcript` (act/confirm/say-again bands, pending
confirmation state). No audio; driven by tests and a `!voice` REPL harness.

**The plan's Decision 6 seam table (`{transcript, confidence, token, match_ratio}`) is
insufficient** to route correctly. Decision 4's own prose requires three distinct behaviours for
`token=None` (not-a-command -> fallthrough to typed-text path; verb-anchored-but-unresolved ->
always say-again; ambiguous -> always confirm on the best candidate), which two fields cannot
encode without a fragile ratio-magnitude convention. Resolved by adding `verb_anchored: bool` and
`ambiguous: bool` to `MatchResult` / `handle_transcript`'s signature. Flag this for Stage 3's real
`GET /transcripts/poll` JSON shape -- it needs these two fields too, not just the two the plan
names.

**`VERB_ANCHOR_WORDS` is derived from `vocabulary.PHRASES` (every phrasing's first word), not
transcribed from Decision 4 REVISED's prose verb-set list.** The derived set is a strict superset
(`full`, `what`, `hey`, `never`, `disregard` also included) -- deliberate, since excluding `never`
would silently break `"never mind"`, the alternate spelling `vocabulary.py` documents specifically
because `base.en` splits a spoken "nevermind" into two words. Same argument for `hey petrovich`.
This is a real, flagged deviation from the plan's literal prose, believed to match its intent.

**Fuzzy verb-anchor matching against short words is loose**: "the" scores 0.667 `SequenceMatcher`
ratio against "hey" verb-anchor word, clearing `VERB_FLOOR` (0.6) and false-anchoring ordinary
sentences. Any 3-4 letter anchor word (`hey`/`say`/`full`) is vulnerable -- short strings have
structurally higher baseline similarity. Not fixed (VERB_FLOOR is explicitly MATCH_FLOOR reused,
not verb-specific), flagged for Stage 6 re-tuning. Had to swap the research doc's own
out-of-vocabulary test probe ("the weather is quite nice today") for a different sentence because
of exactly this.

**Voice-only tokens (report_all/report_bearing_*/report_clock_*/scan_bearing_deg/stop_talking/
say_again-as-command) have no real ACT dispatch** -- `handle_transcript`'s act path reuses
`handle_f10_command` directly (matches the plan's own Tests section wording), so only the 15-token
legacy vocabulary has real behaviour; voice-only tokens match/confirm/say-again fine but "acting"
on them is a graceful no-op via `handle_f10_command`'s defensive `else` branch. Documented gap, not
silent -- building real report-by-bearing dispatch needs a query capability that doesn't exist yet.

See `plans/inbound-speech/implementation.md`'s "Stage 2" section for full detail.

**Review found a real command-execution bug, not just noise (2026-09-19).** Whole-string
`difflib.SequenceMatcher`/`get_close_matches` scoring rewards character/prefix overlap with no
word-count awareness, so `"look at that"` (0.727) and `"watch out"` (0.636) cleared `ACT_FLOOR` and
would have silently executed `scan_ahead`/`watch_nearest`. Fixed with word-sequence scoring
(`_phrase_match_ratio`): `SequenceMatcher` over word *lists*, exact words score 1.0, remaining
equal-length `"replace"` opcode blocks get per-word char-ratio credit only above 0.5, divided by
`max(len(heard), len(phrase))`. Unrestricted best-pairwise-search-across-all-remaining-words (my
first attempt) still let long sentences inflate scores via coincidental short-word overlaps — same
failure class as the bug; restricting credit to same-position pairs within equal-length replace
blocks is what actually fixed it. `MATCH_FLOOR` (0.6) unchanged, still separates the classes.

**A citation for a measured constant needs to point at where the raw data actually lives, not just
where a number was first typed.** `ACT_FLOOR`'s comment cited a research doc that had the model
comparison table but no confidence distribution at all — the real numbers only existed in plan.md
prose until a dedicated research doc was committed. Verify a "measured" comment by opening the
cited file, not by trusting that a number matches.

**Closing the residual (2026-09-19): don't leave a "revisit later" flag on a real-data failure.**
Flagged `VERB_FLOOR` as loose-in-both-directions and deferred to Stage 6 -- but one of the two
over-rejected examples (`"skin bearing 315"`) turned out to be an actual transcript from the
user's real recorded corpus, not a hypothetical, so the deferred gap was silently discarding a
command he really spoke. Fixed by lowering `VERB_FLOOR` to 0.5 (below `MATCH_FLOOR`, not equal to
it) once the phrase score became the real defence: a false anchor only costs one extra
phrase-scoring pass, a false rejection at the anchor is irreversible, so the anchor should now err
toward admitting. Lesson: when a "revisit later" note turns out to touch real measured data rather
than a synthetic edge case, that's a signal to close it now, not defer it further -- and a fix that
changes one constant's relationship to another (here, "no longer equal to `MATCH_FLOOR`") needs the
docstring rewritten to state *why* the two now differ, not just the new number, or someone will
"fix" them back to matching.
