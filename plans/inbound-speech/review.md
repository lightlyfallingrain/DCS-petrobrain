### Review Summary

Reviewed Stage 2 of `plans/inbound-speech/plan.md` (`feature/stt-command-matcher`, commits
62690ad..86c8f9a) against Decision 1 REVISED, Decision 4 REVISED, Decisions 4-6, the "Stage 1
result: GATE CLEARED" section, and `plans/inbound-speech/implementation.md`.

Scope matches the plan: `srs-adapter/src/command_matcher.py` (new), `body-layer/src/belief/
voice_commands.py` (new), `crew_console.py`'s `handle_transcript`/`!voice` addition, `speech.py`'s
two new renders, plus tests in both subprojects, plus `CLAUDE.md` updates. No scope drift. Module
independence is intact — `body-layer` imports nothing from `srs-adapter` (verified by grep); the
adapter/body split matches the constants split Decision 4 REVISED specifies. All four checked
subprojects' commands (`ruff format --check`, `ruff check`, `mypy --strict`, `pytest`) were re-run
directly (not trusted from the report) and pass: srs-adapter 72 passed/1 skipped, body-layer (mypy
run from inside `body-layer/`, per that subproject's CWD-only config-discovery quirk) 705 passed.

One real, concrete safety gap was found in the verb anchor (below) — this is the mechanism the
plan calls "the single most important line of defence," so it is a required fix despite the rest
of the stage being solid.

### Required Fixes

- **The verb anchor's leak is a real hole, not just excess "say again" noise, and the diff's own
  test suite avoids the case that proves it.** The implementer's own notes flag that `"the"` scores
  0.667 against `"hey"` and false-anchors — true, but the consequence they describe (an ordinary
  sentence gets stopped and asked to "say again") is the *safe* failure mode. Traced one step
  further, the same mechanism produces the *unsafe* one the plan is explicitly trying to prevent:
  `match_transcript("look at that")` → `MatchResult(token='scan_ahead', match_ratio=0.727,
  verb_anchored=True, ambiguous=False)`, and `match_transcript("watch out")` →
  `MatchResult(token='watch_nearest', match_ratio=0.636, ...)` (verified live against the actual
  `command_matcher.py`/`vocabulary.py` on this branch). "look" and "watch" are legitimate members
  of `VERB_ANCHOR_WORDS` (they anchor `scan_left`/`scan_bearing_*` and `watch_nearest`
  respectively) and also ordinary English words a pilot would say without meaning to issue a
  command. `classify_response`'s `combined = stt_confidence * phrase_ratio` only needs a
  confidence of ~0.83 to turn `"look at that"` into an executed `scan_ahead` — well inside Stage
  1's own measured *correct*-answer range (mean 0.82, several points above `ACT_FLOOR`). This is
  not a hypothetical: "look", "watch", "report", "scan", "say", "stop", "cancel", and "full" are
  all both command verbs in this vocabulary and common English words, so any sentence beginning
  with one of them (`"look at that ridge"`, `"watch out"`, `"report says otherwise"`, `"stop,
  wait"`) is a candidate for exactly this failure. The root cause is architectural, not a single
  mistunable constant: whole-string `difflib.SequenceMatcher`/`get_close_matches` scores an
  arbitrary sentence against a table of short 2-3 word phrases with no length/word-count
  qualifier, so any sentence that happens to share enough characters with a phrase can clear
  `MATCH_FLOOR`. The separation check does not save this case, because there is usually only one
  close candidate, not two tied ones.
  This needs a real design fix before Stage 3 wires it to live dispatch — options include scoring
  only a bounded window after the anchored verb rather than the whole transcript, requiring a
  word-count-aware match measure, or narrowing `VERB_ANCHOR_WORDS` away from bare dictionary
  words. Deferring it to "Stage 6 re-tuning" (as the implementer's own note does) is not enough,
  because this isn't a threshold that needs nudging — it's a shape of the matcher that lets
  ordinary sentences resolve to *some* command, which is the exact failure Decision 4's verb
  anchor exists to prevent. At minimum, add a regression test pinning this specific case
  (`"look at that"` / `"watch out"`) so a future fix is provable and the failure mode doesn't
  silently regress again.

- **`ACT_FLOOR`'s comment cites a research doc that does not contain the figures it claims.** The
  comment in `body-layer/src/belief/voice_commands.py` says "Stage 1's measured confidence
  distribution (`srs-adapter/research/2026-09-19-whisper-model-sweep.md` ... correct answers ran
  mean 0.82, min 0.60; the two remaining failures sat at 0.58 and 0.66)". I read that file in
  full: it contains the accuracy/safe-miss/unsafe-error/latency table and prose, but no confidence
  distribution and no 0.82/0.58/0.66 figures anywhere. The only place those numbers exist is prose
  in `plans/inbound-speech/plan.md`'s "Stage 1 result: GATE CLEARED" section — not a committed
  research artifact. This isn't fabricated (the plan text states the numbers came from a real
  bench run), but as currently cited it fails the "verify constants against the measurement, not
  the claim" checklist item: nothing in `srs-adapter/research/` currently lets a reader confirm
  `ACT_FLOOR` against raw data. Fix by either recording the confidence-distribution numbers (ideally
  with the underlying per-clip data or a pointer to it) in a research doc, or correcting the
  comment to cite the plan section rather than implying a research/ doc backs it directly.
  (By contrast, `MATCH_FLOOR`/`VERB_FLOOR` = 0.6 checked out exactly — verified against
  `srs-adapter/tools/stt_bench.py`'s own `_MATCH_CUTOFF = 0.6`, same figure, correctly reused.)

### Optional Refinements

- `body-layer/run-crew-text.sh` has an uncommitted local diff (drops `--overlay`, adds
  `--speech-audio --srs-adapter-url ...`) sitting in the working tree outside this branch's staged
  commits. It's unrelated to Stage 2's matcher/band work — worth committing separately (it looks
  like leftover local wiring from exercising the TTS output slice) or reverting before this branch
  is considered clean, but it isn't part of this review's scope and doesn't block Stage 2.
- Voice-only tokens (`report_all`, `report_bearing_*`, `report_clock_*`, `scan_bearing_deg`,
  `stop_talking`, `say_again`) reaching the `act` disposition currently return `[]` from
  `handle_f10_command`'s defensive `else` branch — total silence, no readback, no error. This is
  consistent with the plan's explicit deferral of routing/dispatch mechanisms to a later architect
  pass, and the implementer documented it plainly rather than hiding it, so it's not a blocker for
  Stage 2. Worth prioritizing `stop_talking` specifically when that pass happens, though: unlike
  `report_bearing_*` (which needs a query capability that doesn't exist yet), the interrupt
  mechanism `stop_talking` would need already exists and works — `aircraft-layer/src/collector/
  audio_sender.py`'s `_interrupt_playback`, reachable today via `push_speech(..., urgent=True)` —
  so wiring it is comparatively cheap relative to the other voice-only tokens grouped with it.
- `classify_yes_no` in `voice_commands.py` was checked against Decision 4 REVISED's "body must not
  gain a vocabulary" constraint and is a legitimate exception, not the start of a third copy: it's
  a fixed 7-word affirm/negative set, consulted only while `_pending_confirmation` is set (i.e.
  it's confirmation-response behaviour, not a command vocabulary), and it holds no overlap with
  `srs-adapter`'s phrase table except the deliberate, documented `"disregard"` context-gated
  overload. No action needed.
- Decision 6's seam table in the plan (`handle_transcript(text, confidence, now_sim)`, 3 args) is
  stale relative to what got built (7 args: `token`, `match_ratio`, `verb_anchored`, `ambiguous`
  added) — the implementer flagged this honestly in `implementation.md` and the added fields are
  well-justified (three behaviourally distinct `token=None` outcomes can't be encoded in two
  fields). Worth folding into the plan doc itself so Decision 6 stops reading as authoritative when
  it no longer is, but this is bookkeeping, not a code fix.

### Verdict (original pass)
NEEDS REVISION

The verb-anchor leak is the load-bearing safety mechanism the plan spends the most words
justifying, and it has a demonstrated path to silently executing the wrong DCS command from
ordinary speech — that has to be closed (or at minimum have its risk consciously accepted by the
user with a concrete example in front of them, which it currently has not been) before this stage
is considered done. The `ACT_FLOOR` citation fix is small. Everything else reviewed clean: checks
pass in both subprojects, tests are substantive (not decorative) and match the plan's required
scenarios, module boundaries and the constants split are correctly honored, and scope matches the
plan's Stage 2 file list exactly.

### Review Confidence (original pass)
Full read of the diff and both subprojects' new/changed files (`command_matcher.py`,
`voice_commands.py`, `crew_console.py`'s new methods, `speech.py`'s new renders, and their test
files), plus the two cited research docs read in full and the plan.md sections named in the task.
Constants were checked by running the actual code (`match_transcript`, `_verb_anchor_ratio`)
against adversarial inputs, not just read. `stt_engine.py`'s large diff (Decision 1 REVISED's
Windows-engine removal) was skimmed only — it's an earlier, already-settled decision in this same
branch, not Stage 2's own change, and the plan's own text already records why it was removed.

---

### Follow-up verification (2026-09-19, `aef7f90`)

Re-reviewed both fixes against the working code, not the commit messages.

**Fix 1 — word-sequence scoring.** Read the rewritten `command_matcher.py` in full
(`_phrase_match_ratio` and the asymmetric `VERB_FLOOR`(0.5) < `MATCH_FLOOR`(0.6) reasoning). Ran
`match_transcript` live against: all 15 of the original session's false-positive fixtures (`"the
tanks are on the ridge"`, `"look at that"`, `"watch out"`, `"full house"`, `"he said cancel"`,
`"report card"`, `"scan me"`, `"stop that"`, etc.) plus the two real-corpus admits
(`"skin bearing 315"` → `scan_bearing_deg`/315, `"walk ahead"` → `scan_ahead`). Every one of the
original false positives now resolves to `token=None` (safe "say again"), and both real corpus
commands resolve correctly — confirms the fix closes the hole without reopening the original
VERB_FLOOR-tightening regression. Went further than re-checking the named cases: ran an 80-sentence
adversarial sweep (every anchor-word verb × ten ordinary continuations, e.g. `"look at that
ridge"`, `"watch out for smoke"`, `"full speed ahead captain"`) — zero unsafe hits (no unambiguous
non-None token). `"the"` was specifically re-checked: it still anchors at 0.667 as before (verb
floor untouched by design — the asymmetry argument is that a false anchor is cheap), but
`"the tanks are on the ridge"` scores 0.083 against its best phrase-table candidate, nowhere near
`MATCH_FLOOR` — confirmed by direct call, not just trusted from the comment. So "`the` anchoring is
harmless now" holds: the claim was that the phrase score is the real defence, and that's what's
actually rejecting it.

**No constant moved quietly to compensate.** Diffed `voice_commands.py` and `command_matcher.py`
against the pre-fix commit: `MATCH_FLOOR` is untouched at 0.6, `SEPARATION_MIN` untouched at 0.05,
`ACT_FLOOR`/`ACT_FLOOR_CANCEL`/`CONFIRM_FLOOR`/`CONFIRM_WINDOW_S` all untouched. Only `VERB_FLOOR`
moved (0.6 → 0.5), and a new `_WORD_REPAIR_FLOOR` (0.5) constant was added as part of the scoring
algorithm itself, not as a compensating knob.

**The `VERB_FLOOR` = 0.5 reasoning holds**, verified rather than taken on faith: the asymmetry claim
(false anchor is cheap because the phrase score rejects it anyway; false rejection is unrecoverable)
is exactly what the 80-sentence sweep and the 15 original fixtures confirm in practice, not just in
prose.

**Fix 2 — the citation.** `srs-adapter/research/2026-09-19-corpus-bench-results.md` (new, committed
in `8070d6e`) was read in full: it records mean 0.82 / min 0.60 correct, failures at 0.58 and 0.66,
under the `--prompt` row specifically — matching `ACT_FLOOR`'s comment exactly, including the new
"holds only under `--prompt`" caveat the comment now carries. `ACT_FLOOR`'s value itself (0.60) is
unchanged; only the citation and surrounding prose moved. I cannot independently verify this doc's
numbers against a raw per-clip log (none is committed), but the citation now points at an actual
dated research artifact recording the claim as data, which is what was missing before — this
resolves the specific "unverifiable citation" defect flagged, not a request for raw-log provenance
that was never asked for.

**Optional items**: both folded in as described — Decision 6's seam table in `plan.md` now carries
a dated correction note with the real 7-argument shape, and `plan.md`'s Stage 3 entry now has a
concrete `stop_talking` → `_interrupt_playback` pointer.

**Checks re-run directly** (not trusted from the report): srs-adapter `ruff format --check`/
`ruff check`/`mypy --strict` (`src` + `tools/stt_bench.py`) all pass, `pytest -q` → 81 passed, 1
skipped (matches reported). body-layer `ruff format --check`/`ruff check`/`mypy --strict` (run from
inside `body-layer/`) all pass, `pytest -q` → 705 passed (matches reported).

### Verdict
APPROVED

Both required fixes verified genuine against the working code and adversarial testing, not just
against the stated diff or passing tests. No constant moved quietly to paper over the fix. Optional
items were folded in as described.

### Review Confidence
Full read of `command_matcher.py`'s rewrite and the new research doc; direct execution of
`match_transcript` against the original 15 false-positive fixtures, the two real-corpus regression
cases, and a fresh 80-case adversarial sweep beyond what either party's fixtures covered; diffed
every touched constant across the fix commits to confirm nothing else moved. Both subprojects' full
check sequences re-run directly.
