---
name: project_inbound_speech_stage2_matcher_review
description: Stage 2 command_matcher/voice_commands review found the verb anchor's leak goes further than the flagged case; fix verified genuine on re-review, APPROVED at aef7f90.
metadata:
  type: project
---

**Resolution (2026-09-19, `aef7f90`).** Both required fixes verified genuine on re-review, not
just from the fix commit's own claims: reran `match_transcript` against all 15 original
false-positive fixtures plus a fresh 80-case adversarial sweep — zero unsafe hits; diffed every
constant across the fix commits to confirm only `VERB_FLOOR` moved (0.6→0.5) and nothing else
moved quietly to compensate; read the new `research/2026-09-19-corpus-bench-results.md` in full
and confirmed its figures match `ACT_FLOOR`'s comment exactly. Verdict: APPROVED. Re-verifying a
"fixed" safety mechanism with the same adversarial technique that found the original hole (not a
lighter pass) is what closed this loop — see [[feedback_regression_test_empirical_check]].

`plans/inbound-speech/plan.md` Stage 2 (`feature/stt-command-matcher`, `srs-adapter/src/
command_matcher.py` + `body-layer/src/belief/voice_commands.py`/`crew_console.py`). Verdict:
NEEDS REVISION.

**The finding, and the technique that found it.** The implementer's own notable-discovery entry
disclosed that `"the"` scores 0.667 against `"hey"` and false-anchors `VERB_FLOOR` — but framed the
consequence as only "an ordinary sentence gets a spurious say-again," and deferred it to Stage 6
retuning. Tracing the *same* leak one step further (calling `match_transcript` directly with
adversarial inputs, not just reading the flagged case) found the unsafe consequence: `"look at
that"` → `scan_ahead` at ratio 0.727, `"watch out"` → `watch_nearest` at 0.636 — both
`verb_anchored=True, ambiguous=False`, both clearable to the ACT band at STT confidences well
within Stage 1's own measured *correct*-answer range. Root cause: whole-string `difflib` scoring
an arbitrary sentence against a table of 2-3 word phrases, combined with an anchor set that
includes ordinary English words (`look`, `watch`, `report`, `scan`, `say`, `stop`, `cancel`,
`full`) because they're also this vocabulary's command verbs. This is architectural, not a
mistunable constant — reject "defer to Stage 6 retuning" for a leak in a system's *primary safety
mechanism* even when the implementer already disclosed the shallow version of it.

**General lesson**: when an implementer discloses one instance of a class of bug and defers it as
low-severity, don't stop at re-verifying their instance — probe the same mechanism for the worse
member of the class before accepting the severity classification. Related:
[[feedback_bounded_magnitude_isnt_optional_severity]], [[feedback_regression_test_empirical_check]].

**Secondary finding**: `ACT_FLOOR`'s comment cites `srs-adapter/research/2026-09-19-whisper-
model-sweep.md` for its "mean 0.82, min 0.60, failures at 0.58/0.66" grounding — that doc (read in
full) has no such figures; they exist only as prose in `plans/inbound-speech/plan.md`'s "Stage 1
result" section, not in any committed research/ artifact. Not fabricated, but uncitable as
written — same "verify the citation against the actual file" habit as
[[project_vision_calibration_research_doc_error]].

Everything else in the stage was clean: module independence held (grepped body-layer for any
srs-adapter import — none), constants split correctly, `MATCH_FLOOR`/`VERB_FLOOR`=0.6 verified
exactly against `tools/stt_bench.py`'s own `_MATCH_CUTOFF`, all four subprojects' checks
(reran directly, not trusted from the report) passed, tests substantive and matched the plan's
required scenarios.
