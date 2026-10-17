# DoD Check: BL-8 Mission Memory — Stages 1, 2, 3, 5

Branch `feature/bl8-mission-memory`. Verdict scoped to tip **`bddba5e4252d3803af70cf3c8762d9fd73dc6789`**
(worktree HEAD started at `24f217fc`, 44 commits behind; `git merge --ff-only bddba5e4` fast-forwarded
cleanly onto a clean tree — confirmed before any check ran).

## Mechanical checks — all PASS

Run from inside this worktree's `body-layer/`, using the main checkout's venv interpreter (this
worktree has no `.venv`):

```
ruff format --check src tests   -> 152 files already formatted
ruff check src tests            -> All checks passed!
mypy src                        -> Success: no issues found in 68 source files
pytest -q                       -> 2162 passed, 4 xfailed in 15.83s
```

Matches the Reviewer's, Performance Reviewer's and Security's independently reported state exactly.

`git status --porcelain` is empty on the feature tip — clean tree, nothing uncommitted. No debug
`print()`s outside the established disable-once-and-report/CLI-output patterns (checked:
`log.py:40`'s stderr print is the sink's disable-and-report line, not debug output). No `TODO`/
`FIXME` anywhere in `mission_memory/`.

## Reviewer, Performance, Security — all APPROVED, no open required fixes

- `review.md`: APPROVED WITH MINOR FIXES → fix round → **APPROVED**, re-reviewed with two mutation
  tests independently re-run (not just trusted). All three required fixes (untested `seen` output,
  untested `dcs_to_wgs84`/`ValueError` branches, the doc update) discharged.
- `performance-review.md`: **APPROVED — MONITOR**. `store.latest_entry`'s reverse scan is the one
  watch item, explicitly deferred pending real entry volume from Sortie A, not a required fix.
- `security-review.md`: **APPROVED**, one backlog item filed (`BL-B79` — `remember_location`'s
  unbounded `label` parameter, correctly deferred because `TOOL_SET` has no live dispatcher yet,
  independently re-confirmed by grep in this pass too — see below).

## Scope & correctness against the explore notes

Checked the delivered code against the ten numbered decisions in `explore-notes.md`, not just the
plan:

- Append-only with strike-obsolete, not mutation (Decision 1) — confirmed: `Entry` is frozen,
  `store.append()` is the sole construction site (grep-enforced, mutation-tested by the Reviewer),
  `struck_by` is a derived replay.
- Air defence always earns its own entry (Decision 3) — confirmed in `admission.py`, tested
  (`test_air_defence_class_always_writes_its_own_entry`).
- Marks as the only numbered space (Decision 3) — confirmed: `_next_mark_index` is the one counter;
  air-defence/group entries are referred to by position/landmark only.
- Composition at class level in existing granularity words (explore + Decision 2 in plan.md) —
  confirmed: `CompositionItem` carries `OP_*` class plus `cardinality_phrase`'s frozen word, no new
  vocabulary invented.
- `motion.dir` and `attack_run.outcome` nullable from the start (scope decision) — confirmed in
  `entries.py`'s payload dataclasses; both stay legally `None`/`"unknown"`.
- No in-flight visual surface of any kind — confirmed: nothing in this batch renders a kneeboard or
  map view; the store is write-only in flight, as the explore notes' reframe settles.
- The strike chain *being* the per-group history (explore, point 10) — confirmed: no separate
  history structure; `chain_for`/`get_contact_history_with_memory` both replay the chain directly.

No unplanned scope found. Stage 4 (attack-run trigger) and Stage 6 ("safe from") are absent exactly
as the user's 2026-10-17 decisions specify, with reasons recorded in `BL-8.md`.

## Documentation

- `body-layer/CLAUDE.md` — Module map gained the "Mission memory" section; read, matches the code.
- `body-layer/docs/STRUCTURE.md` — per-module detail entries added at the belief/surfaces boundary;
  read, matches the code and carries the *why* (Decisions 1/3/6/8).
- `body-layer/ROADMAP/BL-8.md` — `[~]`/`#status/in-progress`, records Stages 1/2/3/5 landed, Stage
  4/6 deferrals with reasons, Sortie A named outstanding with the write-only-in-flight framing
  stated explicitly.
- `body-layer/ROADMAP.md` — confirmed untouched (`<!-- split-roadmap: see ROADMAP/ -->`, 5 lines,
  pointer intact). Correct.
- Root `ROADMAP.md`'s Body Layer status-table row does **not** yet mention BL-8 Stages 1/2/3/5 —
  expected, since this branch has not merged. Will be updated at merge time (Milestone Completion
  procedure), not before.

## FAIL — found at this gate, not caught by any earlier pass

**The commanded-mark path (Decision 6: "reachable by voice and by the brain tool only") has no
live voice path at all.** `mark_here`/`mark_target` are correctly wired as `DISPATCHED_COMMAND_TOKENS`
in `body-layer/src/belief/crew_console.py` and dispatch correctly in unit tests via the `!voice`
developer test harness (which *simulates* an already-resolved match). But the real recognition
vocabulary that produces that match — `audio-adapter/src/vocabulary.py`'s `TOKENS`/`PHRASES` — was
never touched by this batch. Verified mechanically, not inferred:

```
$ cd audio-adapter && PYTHONPATH=src .venv/bin/python -c "
from command_matcher import match_transcript
for u in ['mark here', 'mark this', 'mark target', 'remember this location']:
    r = match_transcript(u); print(repr(u), '->', r.token, r.match_ratio)"
'mark here' -> None 0.0
'mark this' -> None 0.0
'mark target' -> None 0.0
'remember this location' -> None 0.0
```

Compare against an existing, working token from the same run: `match_transcript('scan ahead')` →
`scan_ahead 1.0`. The matcher itself works; `mark_here`/`mark_target` simply have no phrase entry.
`grep -n "mark" audio-adapter/src/vocabulary.py` confirms zero hits outside unrelated comment text.

There is also no typed-text path: `CrewConsole.handle_line`'s non-`!`-prefixed branch goes through
`_handle_utterance` → `belief.utterance.parse_utterance`, a different, narrower grammar
(`set_attention`/`describe_contact` only) that has no "mark" entry either (`grep -n "mark"
body-layer/src/belief/utterance.py` — zero hits). The brain-tool path is confirmed separately by
Security as not yet dispatched (`TOOL_SET` has no generic caller anywhere in the repo).

**So, today, a pilot cannot set a mark by any means a pilot would actually use.** The only way to
reach `mark_here`/`mark_target` at all is the `!voice <token> <ratio> <confidence> <verb_anchored>
<ambiguous> <transcript>` developer harness — typing the literal token name into the console, which
is a test tool, not a command surface.

**Why this wasn't caught earlier:** every review pass (Reviewer, Performance, Security) correctly
scoped itself to `body-layer/src/mission_memory/` plus the body-layer files the plan's own
"Affected Modules" section named — and that section never named `audio-adapter/src/vocabulary.py`
at all. The plan's Decision 6 states the voice-reachability *intent* but the Affected Modules list
never lists the one file required to deliver it. Security's point 2 analysis even describes "the
pilot-voice path" by name while reasoning about the dispatch mechanism (`crew_console`'s closures)
without checking whether voice recognition can ever produce the token that reaches it — the same
shape of gap `.claude/agent-memory/dod/feedback_run_the_card_utterances_through_the_matcher.md`
exists to catch, and did catch here.

**This is a real gap against the plan's own stated design (Decision 6), not a cosmetic one** — it
also blocks Sortie A's own "set a mark" test case as dispatched to this gate, since there is no
natural utterance that produces it.

### Recommendation

Small, low-risk, mechanical fix: add `mark_here`/`mark_target` to `audio-adapter/src/
vocabulary.py`'s `VOICE_ONLY_TOKENS` and `PHRASES` (a handful of phrasings — "mark here", "mark
this position", "mark target", "remember this location", "remember target" — following the
existing per-token phrasing density). The file's own `assert set(PHRASES) == set(TOKENS)` will
catch a mismatch mechanically. This is **Implementer work on `audio-adapter`**, followed by
**Reviewer** re-check of just that addition (not a re-review of the whole batch), then DoD re-runs
the `match_transcript` probe above before the card is written. No new architectural decision, no
new dependency — routine vocabulary-table work, but it crosses a subproject boundary the original
plan didn't name, so I am surfacing it rather than quietly fixing it myself.

**Does not need to block the merge of Stages 1, 2, 3, 5's actual code** — the mission-memory store,
admission rules, and query surface are all correct and tested independently of whether voice can
reach the mark command yet. What it blocks is: (a) claiming Decision 6 is actually delivered, and
(b) Sortie A's voice-mark test case as I was asked to write it.

## Milestone Completion — the inspect-and-adapt question

**Does BL-8's completion change what the next milestone should be, or invalidate a downstream
assumption?** Yes, in one direction already named in the plan: it unblocks `X-B20`'s knowledge
gate (previously aspirational, now checkable against a real store) and narrows the
destruction-determination and motion-direction work to fill an existing schema slot rather than
invent their own format. It does **not** make the brain able to use any of this yet — Security's
independent finding that nothing dispatches `TOOL_SET` generically stands, so `recall_memory`/
`remember_location`/the `get_contact_history` fold are each reachable only from body-layer's own
test suite today, not from a running brain. That dispatcher is the real next dependency for this
store to matter to the brain layer, not named as a BL-8 stage and not this gate's problem to
solve, but worth saying plainly: BL-8 built the store; nothing yet calls it from where it would
need to be called from.

## Overall verdict

**NOT YET PASS.** Everything mechanical, scope-wise, and documentation-wise is in order and the
three review passes are each sound within their stated scope. One real, independently-verified gap
found at this gate: the commanded-mark path has no live voice (or any other pilot-usable) input
surface, contradicting Decision 6 and blocking the "set a mark" half of Sortie A as specified.
Recommend a small Implementer fix on `audio-adapter/src/vocabulary.py`, a narrow Reviewer check,
then re-run the `match_transcript` probe before DoD re-issues and the acceptance card is written.

## Re-confirmation — 2026-10-17

Verdict scoped to tip **`40daea7ecf238e58d33a7be64f9a07386bb85ccb`** (worktree HEAD started at
`24f217fc`, a strict ancestor of the named tip; `git merge --ff-only 40daea7e` fast-forwarded
cleanly onto a clean tree — confirmed before any check ran).

Two commits closed the finding above:

- `f6b81f4b` — `mark_here`/`mark_target` added to `audio-adapter/src/vocabulary.py`'s
  `VOICE_ONLY_TOKENS`/`PHRASES` (`mark here` / `mark this position` / `remember this location`;
  `mark target` / `remember target`), plus four new tests in
  `audio-adapter/tests/test_command_matcher.py`. Diff confirmed `audio-adapter`-only (plus a plan
  update and an implementer memory note) — **no `body-layer` file touched**.
- `40daea7e` — Reviewer: APPROVED (third dated section of `review.md`). Re-ran the probe itself,
  added 17 further adversarial/near-miss cases, found no collisions, mutation-tested the new
  tests two ways.

**DoD's own `match_transcript` probe, re-run rather than trusted:**

```
'mark here'                   -> token='mark_here',   match_ratio=1.0
'mark this position'          -> token='mark_here',   match_ratio=1.0
'remember this location'      -> token='mark_here',   match_ratio=1.0
'mark target'                 -> token='mark_target',  match_ratio=1.0
'remember target'              -> token='mark_target',  match_ratio=1.0
'mark the target'              -> token='mark_target',  match_ratio=1.0
'remember the target'          -> token='mark_target',  match_ratio=1.0
'remember this spot'           -> token='mark_here',   match_ratio=0.667  (correct fuzzy hit)
"that's a remarkable sight"    -> token=None,          match_ratio=0.0    (correctly no match)
'Petrovich, mark here'         -> token='mark_here',   match_ratio=0.667
'mark here please'             -> token='mark_here',   match_ratio=1.0
```

All five phrasings resolve; no near-miss or adversarial case collides. The gap DoD found on the
first pass is closed.

**Subproject checks, re-run from inside this worktree, main-checkout venv interpreters (worktree
has none):**

```
audio-adapter: ruff format --check -> 29 files already formatted
audio-adapter: ruff check          -> All checks passed!
audio-adapter: mypy src            -> Success: no issues found in 15 source files
audio-adapter: pytest -q           -> 284 passed, 1 skipped in 28.80s
body-layer:    ruff format --check -> 152 files already formatted
body-layer:    ruff check          -> All checks passed!
body-layer:    mypy src            -> Success: no issues found in 68 source files
body-layer:    pytest -q           -> 2162 passed, 4 xfailed in 16.29s
```

All match the implementer's/Reviewer's claimed counts exactly. `git status --porcelain` is empty —
clean tree, nothing uncommitted, no artifacts committed.

**Milestone Completion question — carried forward, not re-derived:** BL-8's completion unblocks
`X-B20`'s knowledge gate (previously aspirational, now checkable against a real store) and narrows
the destruction-determination and motion-direction work to fill an existing schema slot. It does
**not** make the brain able to use any of this yet — nothing dispatches `TOOL_SET` generically, so
`recall_memory`/`remember_location`/the `get_contact_history` fold are reachable only from
body-layer's own test suite today. That dispatcher is the real next dependency, not a BL-8 stage
and not this gate's problem to solve.

## Overall verdict (re-confirmed)

**PASS, conditional on Sortie A.** The voice-vocabulary gap is closed and independently verified
(probe output above, not taken on trust). All mechanical checks pass on both touched subprojects.
Scope, documentation and the deferred-stage decisions (Stage 4, Stage 6) match the plan and the
user's own 2026-10-17 direction. The feature is write-only in flight by design, so the acceptance
boundary is a post-flight file read — see `docs/acceptance/2026-10-17-bl8-mission-memory-sortie.md`
for what that sortie needs to cover and what "good" looks like reading the file back. Not blocked
on anything further.
