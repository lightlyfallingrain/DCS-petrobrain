# Definition of Done — AA-B7 wake-word routing fix

Branch `fix/aa-b7-wake-word-routing`, tip `8c07487f18007d9a78c4f23a2f73920c8e5f9776`
("Reviewer: AA-B7 wake-word routing fix -- APPROVED"). This verdict is scoped to that commit; if
the branch moves, re-run this check.

## Mechanical checks (audio-adapter — the only subproject this branch touches)

```
ruff format --check audio-adapter/src audio-adapter/tests   -> 31 files already formatted
ruff check audio-adapter/src audio-adapter/tests            -> All checks passed!
cd audio-adapter && mypy src                                 -> Success: no issues found in 16 source files
pytest audio-adapter/tests -q                                 -> 371 passed, 2 skipped (pre-existing live-binary skips)
```

All green, matching the figures `plans/aa-b7-wake-word/review.md` already reported.

`git diff --name-only main...HEAD`: `.claude/agent-memory/reviewer/...`,
`audio-adapter/ROADMAP/AA-B7.md`, `audio-adapter/src/command_matcher.py`,
`audio-adapter/tests/test_command_matcher.py`, `body-layer/ROADMAP/BL-B52.md`,
`docs/acceptance/2026-10-20-sortie-feedback.md`, `plans/aa-b7-wake-word/review.md`. Only
`audio-adapter` carries a source change; `body-layer/ROADMAP/BL-B52.md` is a status-only edit
(closing it by decision, no code). No other subproject's commands are owed.

No debug output, no `TODO`/`FIXME`, no `print`/`pdb`/`breakpoint` introduced (grepped the diff
directly). No unhandled errors/panics in the changed path — `opens_with_wake_word` is a pure
boolean function with no I/O.

## Scope & correctness

- Matches `audio-adapter/ROADMAP/AA-B7.md`'s "Fix" section and the user's 2026-10-25 decision
  exactly: an opening `[hey, ]petrovich` returns `verb_anchored=False` before any verb-anchor
  logic runs; no body-layer change. The before/after table in that entry was checked against the
  live matcher (see "Acceptance boundary" below) and holds for every row.
- No unplanned scope. `WAKE_FLOOR`/`_WAKE_WORD`/`_WAKE_GREETING` reuse
  `vocabulary.PHRASES["wake_petrovich"]`'s existing two phrasings — no new spoken word, so the
  "whisper prompt is in sync by construction" rule needs no action (Reviewer confirmed this;
  re-checked, correct).
- `WAKE_FLOOR = 0.8` is a matching constant in `audio-adapter`, same class as `VERB_FLOOR`/
  `MATCH_FLOOR` already in this file — not a body-layer behaviour constant, so `tuning.py`'s
  mechanism does not apply here (correctly not used).
- All new/modified files are committed (fast-forward merge brought them in; nothing left
  unstaged — see `git status --porcelain` below).
- No CLAUDE.md invariant violated: no omniscience boundary touched, no DCS write, single-player
  scope preserved, module independence preserved (audio-adapter stays stdlib-only, no new
  cross-subproject import).

## Testing

- `test_command_matcher.py`'s new parametrized wake-word cases are meaningful, not decorative —
  Reviewer's mutation check (commented out the guard, reran `-k wake_word`, 11/11 failed red,
  restored) is evidence, not assertion, and I did not need to repeat it.
- No existing test broken (371 passed matches pre-fix baseline plus the new cases).

## Documentation

- `plans/aa-b7-wake-word/review.md` exists, **APPROVED**, zero required fixes. Two optional
  refinements noted (a `cancel_nevermind`-interaction test, a `WAKE_FLOOR` voice-sample caveat) —
  neither blocks DoD; the first is preserved in Reviewer's own agent-memory file
  (`.claude/agent-memory/reviewer/project_wake_word_cancel_interaction.md`), carried through the
  fast-forward merge.
- Non-obvious behaviour (why the check runs before verb anchoring, why it reuses
  `vocabulary.PHRASES` rather than a hand-written word) is explained in code comments and in
  `AA-B7.md` itself.

## Security

**Skipped by explicit user direction for this fix** ("Skip perf and security reviews, this is
small") — not flagged as missing, per the dispatch instructions for this run. No
`security-plan-review.md`/`security-review.md` exists for this plan directory and none is
expected.

## Milestone-completion question

**Does this change what's next, or invalidate a downstream assumption?** Yes, partially, and the
finding below is the reason this check took longer than the mechanical pass alone.

- `[[BL-B52]]` is correctly closed by this decision (verified: `Petrovich, report left` now goes
  to the brain whole via `opens_with_wake_word` firing before the slotted-report branch — no slot
  to drop).
- `[[AA-B4]]` (positional verb anchoring) is genuinely untouched and still open; this fix does not
  fall out of it or require it.
- **`[[BR-2]]`** (the tool-call dispatcher) is not what gates card A14 next, contrary to what a
  quick read of `AA-B7.md`'s "What it blocks" section might suggest. BR-2 is about the brain
  *calling* `TOOL_SET`; the escalation path AA-B7 feeds is BR-1's existing `POST /escalate`, a
  different, already-built mechanism. BR-2 is unaffected by this change either way.
- **New finding, not previously tracked**: running `parse_utterance` directly (not just tracing
  the call chain) against the exact sentences in `AA-B7.md`'s own log evidence shows the routing
  fix is necessary but not sufficient for card A14 as literally scoped. See "Acceptance boundary"
  below and `[[BL-B100]]` (filed this pass, `body-layer/ROADMAP/BL-B100.md` +
  `body-layer/ROADMAP/body-layer-backlog.md`). `AA-B7.md`'s own "Open (flight)" section now
  carries this finding too, so a reader of that entry alone sees it without needing this report.

## Acceptance boundary — what fixtures structurally cannot reach, and what I found by running past them

`test_command_matcher.py` proves `match_transcript` and `opens_with_wake_word` in isolation. It
cannot prove what body-layer's `parse_utterance` — a different module, in a different
subproject, reached only through a live escalation — does with the same string. I ran that
directly rather than trusting the Reviewer's (correct, but narrower) call-chain trace:

```
$ cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python -c "
from belief.contacts import ContactStore
from belief.utterance import parse_utterance
store = ContactStore()
for t in ['Petrovich, where is mark one?', 'Petrovich, where are we?',
          'where is mark one?', 'where are we?']:
    p = parse_utterance(store, t, 0.0)
    print(repr(t), '-> matched_intent=', p.matched_intent)
"
'Petrovich, where is mark one?' -> matched_intent= None
'Petrovich, where are we?'      -> matched_intent= None
'where is mark one?'            -> matched_intent= describe_contact
'where are we?'                 -> matched_intent= None
```

`parse_utterance`'s patterns are start-anchored (`^where(?:'s| is| was)\s+...`). AA-B7 does not
strip the wake-word prefix from the transcript it hands to escalation — it only decides *that*
the transcript escalates, not *what* escalates. So `"Petrovich, where is mark one?"` — the exact
sentence AA-B7.md quotes from the 2026-10-20 speech log — still fails to match, falls to
`structural_unable_reason`'s `NO_SUCH_COMMAND`, and the brain answers `"Unable, no such command."`
Progress over the pre-fix `"say again"` (the defect this entry targets is fixed: it no longer
anchors as a verb), but not the question answered, and not what card A14 is checking for.

Separately, `"Petrovich, where are we?"` has no matching pattern **even unprefixed** — there is no
ownship-position intent in body's deterministic grammar, and brain-layer's own reply vocabulary
(`PICK`/`ASK`/`CONFIRM`/`UNABLE`) is a closed set, never free prose (`decider.py`'s own module
docstring). That gap is bigger than AA-B7 or BL-B100 and is not re-filed here.

**This does not fail AA-B7's own scope** — the Reviewer's approval is correct for what the entry
set out to do, and I am not reopening it. It does mean: **flying card A14 against the literal
sortie-log sentence will still not show "the brain answering in his own words," even once
`--brain-url` is pointed at the Mac.** That expectation gap is now named (`[[BL-B100]]`) instead of
being discovered cold on the next sortie.

## Acceptance Testing Plan: AA-B7 wake-word routing

**Goal:** confirm the routing decision itself — a wake-prefixed transmission no longer anchors as
a command verb and no longer answers "say again" — without requiring a live DCS/brain/Windows
session, since that full chain is `#needs-flight` and explicitly not blocked on here.

**Prerequisites**
- [x] `cd audio-adapter && .venv/bin/mypy src` — clean (see above; actually run against the real
  venv at `/Users/sg/Code/DCS-petrobrain/audio-adapter/.venv`, not a stub)
- [x] `pytest audio-adapter/tests -q` — 371 passed, 2 skipped (run above)

**Test Cases** (all run directly against `audio_adapter.command_matcher.match_transcript`,
executed this pass, not reconstructed — exact transcript, output for each):

```
$ cd audio-adapter && PYTHONPATH=src /Users/sg/Code/DCS-petrobrain/audio-adapter/.venv/bin/python -c "..."
'Petrovich, where are we?'        -> token= None       verb_anchored= False
'Petrovich, scan left'            -> token= None       verb_anchored= False
'Petrovich, report left'          -> token= None       verb_anchored= False
'scan left, Petrovich'            -> token= scan_left   verb_anchored= True
'good morning Petrovich'          -> token= greeting    verb_anchored= True
'hey Petrovich, what do you see'  -> token= None       verb_anchored= False
```

All six match `AA-B7.md`'s own before/after table exactly. `verb_anchored=False` + `token=None` is
confirmed (by reading `voice_commands.classify_response`, line 447) to route to `"fallthrough"`,
which reaches brain escalation rather than "say again" — this part of the chain is pure code with
no DCS dependency, so reading it is sufficient evidence, matching the Reviewer's own confidence
note.

**Edge Cases Probed**
- Filler before the name ("um, Petrovich, ...") — Reviewer covered this; not re-run.
- A wake-prefixed transmission ending in a retraction ("..., never mind") — traced, not tested,
  flagged as an optional refinement by Reviewer and preserved in agent-memory; not required for
  this DoD pass.

**Pass Criteria**
The feature passes if the six cases above match the table, mypy/ruff/pytest stay clean, and no
regression appears in the 371-test suite. **All of this is met.**

**Out of scope for this pass, tracked separately:**
- **Card A14, live flight** — `#needs-flight`, already tagged on `AA-B7.md`. Needs
  `--brain-url` pointed at the Mac (named open item) **and** `[[BL-B100]]` (new finding this
  pass) before it can show "the brain answering in his own words" against the literal sortie-log
  sentence. Not blocking this merge.
- Performance/security review — explicitly skipped by user direction for this fix.

## Notes harvest

`/notes-harvest aa-b7-wake-word` found no candidates in `plans/aa-b7-wake-word/` (no
`implementation.md`/`debug.md`, and `review.md` has no Required Fixes — `review.md`'s content is
narrative, not a checklist this harvester extracts from). One insight I found independently this
pass was added by hand to `notes/voice-recognition-and-command-matching.md` (the topic it fits):
**"fixing where a transcript is routed does not fix what the receiving grammar can do with the
text it still contains"** — the `[[BL-B100]]` finding, generalised. Also saved to
`.claude/agent-memory/dod/feedback_trace_routing_fix_through_the_destinations_own_grammar.md` as a
process memory for future DoD passes on any cross-subproject routing fix.

## Recurring-fix pattern check

Checked `plans/aa-b7-wake-word/review.md`'s Required Fixes against
`.claude/agent-memory/dod/MEMORY.md` (there is no required fix — Reviewer's verdict is APPROVED
with zero required fixes), so there is no recurring-fix category to compare. The real recurrence
risk this pass surfaced is a different one — "a routing-chain trace is not the same claim as
running the destination's own parser" — which is why it is saved as its own memory rather than
folded into a fix-count pattern.

## Verdict

**DoD: PASSED**, scoped to tip `8c07487f`. Mechanical checks clean, scope correct, Reviewer
required fixes: none (none existed). Acceptance testing (the part executable without DCS) passes.
Live acceptance (card A14) remains `#needs-flight`, correctly not blocking, and now carries an
accurate expectation (`[[BL-B100]]` filed) instead of an optimistic one.

Recommend to the user: merge is clear to proceed once they've seen this report — the "answering in
his own words" sortie, when flown, should be read against `[[BL-B100]]`'s finding rather than
against AA-B7.md's original (now corrected) "Open (flight)" wording.
