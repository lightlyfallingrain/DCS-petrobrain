# Definition of Done — sortie-2026-10-05 refinements, items 2/3/4

**Branch:** `feature/sortie-refinements` · **Tip gated:** `06c5f1b`, confirmed by `git rev-parse HEAD`
as the first action (AGENTS.md rule 4). `git checkout feature/sortie-refinements` succeeded — the
branch was free, the main checkout being on `main` — so no `git archive` snapshot was needed.
Fork point (`git merge-base HEAD main`): `896369e`.

**This file was committed as a skeleton before it was complete, and filled in as checks landed.** A
reviewer on this very branch ran seven hours and was stopped with its last line reading *"Everything
verified. Writing and committing the review now"* — the work was done and none of it was
recoverable.

## Verdict

**DoD: PASSED.** All mechanical checks pass in both touched subprojects, every Reviewer / Security /
Performance required fix is accounted for, and the one known behavioural gap is filed as `BL-B41`
with a plain-language statement in the acceptance card.

**Live acceptance: NOT performed, and deliberately not blocking.** The user is awake but has not
flown this. Per the standing direction (2026-09-19), live verification happens in bursts and must
not gate the work. The card is written and published; the debt entry is in
`body-layer/ROADMAP.md`'s "Live acceptance debt" list, and it batches onto the same sortie as the
two other 2026-10-06 cards. This is **deferred, not waived.**

**Do not read this as a merge.** Nothing was merged and nothing is marked merged.

## Imports proven worktree-local before any number was trusted

A DoD run on this project once reported `1177/4` — exactly `main`'s baseline — against a branch's
own `1192/4`. The worktree has no `.venv`, so the main checkout's interpreters were borrowed by
absolute path with `cwd` inside the worktree's own subproject directory, which is exactly the setup
that produced that failure. So resolution was proved first, not assumed:

```
speech         -> <worktree>/body-layer/src/belief/speech.py
callouts       -> <worktree>/body-layer/src/belief/callouts.py
gaze           -> <worktree>/body-layer/src/perception/gaze.py
crew_console   -> <worktree>/body-layer/src/belief/crew_console.py
query.describe -> <worktree>/world-model/src/query/describe.py
vocabulary     -> <worktree>/audio-adapter/src/vocabulary.py
belief.speech.may_be_callout_keeper present: True
```

Every path is inside the worktree, including the world-model seam.

## Which subprojects this diff touches — derived from the diff, not from memory

`git diff --name-only 896369e..HEAD` gives two subprojects with **source** changes:

| subproject | source files touched |
|---|---|
| `body-layer` | `src/belief/{callouts,crew_console,speech}.py`, `src/perception/gaze.py` + 5 test files |
| `audio-adapter` | `src/vocabulary.py` + `tests/test_command_matcher.py` |

Two further subprojects appear in the diff with **documentation only**, so their suites are not
implicated: `world-model/ROADMAP.md` and
`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`.

## Checks

**`body-layer`** (`cwd` = worktree's `body-layer/`):

| check | result |
|---|---|
| `ruff format --check src tests` | 115 files already formatted |
| `ruff check src tests` | All checks passed! |
| `mypy src` | Success: no issues found in 53 source files |
| `pytest tests -q` | **1476 passed, 4 xfailed** in 12.79s |

**`audio-adapter`** (`cwd` = worktree's `audio-adapter/`):

| check | result |
|---|---|
| `ruff format --check src tests` | 29 files already formatted |
| `ruff check src tests` | All checks passed! |
| `mypy src` | Success: no issues found in 15 source files |
| `pytest tests -q` | **222 passed, 1 skipped** in 28.67s |

**`1476/4` is this branch's own baseline and is not a regression.** `main` is now `1530/4` because
two features merged overnight; the branch forked at `896369e`, before both.

**The named tests were confirmed in an unfiltered `pytest -v` run, not by a `-k` filter** (a `-k`
filter silently skipped a brand-new test for an implementer on 2026-10-05). The verbose run's own
tail reads `1476 passed, 4 xfailed` — the same invocation the names below were grepped out of, not a
full-suite result pasted under a filtered command:

```
tests/test_callouts.py::test_a_watched_group_that_starts_moving_speaks_one_line_not_one_per_member PASSED
tests/test_callouts.py::test_group_callout_member_id_names_exactly_one_live_member PASSED
tests/test_callouts.py::test_group_callout_member_id_is_none_when_the_group_has_shrunk PASSED
tests/test_crew_console.py::test_watch_nearest_tags_every_group_member_watched PASSED
tests/test_crew_console.py::test_follow_tags_every_group_member_watched PASSED
tests/test_crew_console.py::test_watch_nearest_a_single_ungrouped_contact_is_unaffected_by_group_tagging PASSED
tests/test_crew_console.py::test_a_unit_that_joins_the_group_later_is_not_retroactively_watched PASSED
tests/test_gaze.py::test_commanded_ahead_cycles_its_own_11_12_1_legs_from_command_time PASSED
tests/test_command_matcher.py::TestDescribeSynonym::test_both_phrasings_resolve_to_report_all PASSED
tests/test_command_matcher.py::TestDescribeSynonym::test_is_separable_from_everything_else PASSED
tests/test_command_matcher.py::TestDescribeSynonym::test_adversarial_sentences_do_not_falsely_fire PASSED
```

## DoD criteria

| criterion | result |
|---|---|
| Each touched subproject's own format/lint/type/test commands pass | **PASS** — both, table above |
| No unhandled errors or panics in data paths | **PASS** |
| No debug output left in committed code | **PASS** — `+` lines of the src diff grepped for `print(`, `breakpoint`, `pdb`: no hits |
| No leftover debug code or TODO/FIXME introduced | **PASS** — same grep, no hits |
| No error suppression introduced | **PASS** — no added `except …: pass`, `# type: ignore` or `noqa` in the src diff |
| Implementation matches the plan | **PASS** — items 2/3/4 as planned; item 1 correctly absent, it is its own branch |
| No unplanned scope added silently | **PASS with a note** — see "Scope note" below |
| No CLAUDE.md invariants violated | **PASS** — reviewer round 3 traced the no-omniscience boundary (`envelope_for` untouched, `may_be_callout_keeper` reads only believed fields); mechanism (`9b450ca`) and documentation (`1feeda8`) are separate commits per body-layer's own invariant |
| All new files staged | **PASS** — clean `git status --porcelain` |
| Core logic covered by tests | **PASS** — 8 new body-layer tests, 3 new audio-adapter tests |
| Tests are meaningful | **PASS** — each item has a stated failing counterfactual, and round 3 re-pinned the shrunken-group test by mutating the coherence guard (exactly one failure, then a byte-identical restore) |
| No existing tests broken | **PASS** — two fixtures were updated because they silently depended on `ahead` being static (`test_mock_flight_chain.py`'s count `32`→`23`, `test_emission_pipeline.py`'s `_PERSISTENT_AHEAD_SCAN` re-pointed to `commanded_legs=(12,)`); both are extensions of intent, not rewrites |
| Reviewer findings addressed | **PASS** — review, round 2 and round 3 all accounted for; see below |
| Non-obvious behaviour explained | **PASS** — `NOTES.md` gained the granularity insight; the `BL-B41` limitation is in the card in plain language |
| Security review exists and is resolved | **PASS** — `security-review.md` APPROVED WITH REQUIRED FIXES, the one finding fixed in `41e7495` |
| `security-plan-review.md` exists | **N/A, expected** — under the cadence set 2026-09-24, Security runs **once per feature immediately before DoD**; there is no plan-review stage to produce this file |

### Review chain, closed out

| review | verdict | where its fixes landed |
|---|---|---|
| `review.md` | APPROVED | — |
| `security-review.md` | APPROVED WITH REQUIRED FIXES (1) | `41e7495` — the watch readback now speaks the count it actually marked, not the count it meant to |
| `performance-review.md` | change request (1 NOW, 2 MONITOR, 1 no-action) | `726af61` — one watched-only line per group rather than one per member, removing the ~820 ms `describe_position` amplification |
| `review-round2.md` | APPROVED WITH REQUIRED FIXES (2) | `9b450ca` (keeper elected among eligible members), `1feeda8` (two docstring claims the suppression falsified) |
| `review-round3.md` | APPROVED WITH REQUIRED FIXES (2, both doc-only) | `06c5f1b` — says "at most one", and withdraws the extend-this-predicate instruction |

Round 3's own verdict — *"Ready for DoD? **Yes** — once R1 and R2 land, which is one short
implementer pass, not another design round"* — is satisfied by `06c5f1b`, the branch tip.

### Reviewer confidence

Round 3 reports **full read**, with the load-bearing claims verified by execution rather than
reading: all four body-layer checks with imports proven worktree-local, the shrunken-group test's
subject by mutation, `_leading_index`'s subset-invariance exhaustively over all 63 subsets against an
independently written argmax (including a deliberate envelope-width tie), `BL-B41`'s silence by
constructing the state and reading `spoken == []` off a real `CalloutScheduler` across three ticks,
and the merge interaction by `git merge-tree` against current `main`. One item was explicitly not
re-run (the implementer's own eligibility counterfactual) because the orchestrator had already run
it. No spot-check substituted for a read.

### Scope note — not a FAIL, and it costs nothing at merge

Four commits of **cross-cutting bookkeeping** rode this feature branch rather than being committed
on `main`, which root `CLAUDE.md`'s Workflow rule asks for: `0de048a` (the flight-feedback hooks,
`CLAUDE.md`, `.claude/settings.json`, `.gitignore`) and `51b587c`/`b8f4b9f`/`0ed08f6` (the DCS-LOS
first-sortie research note and `world-model/ROADMAP.md`).

**Checked rather than assumed: every one of those paths is byte-identical on `main` already** — none
of them appears in `git diff --name-only main..HEAD`. So the drift has no merge consequence and
nothing needs undoing. Recorded because the habit is what matters, not this instance.

### Known limitation shipped knowingly — `BL-B41`

The watched-group callout keeper is elected per *contact* while the suppression it drives is per
*event*, so a watched group whose keeper has no event of a given kind on a tick loses that kind's
report for the whole group. Eligibility cannot close it — a `(store, contact)` predicate cannot
express a per-event question — which is why round 3's fix is correct within its remit.

Filed on `main` as **`BL-B41`** (commit `ea96d4e`), together with `BL-B39` and `BL-B40`. **Not
re-filed here**, and `body-layer/BACKLOG.md` was deliberately left untouched on this branch so the
merge does not have to reconcile a duplicate against those three additions.

Severity is bounded and stated in the card: range crossings self-correct, and the widest-envelope
member — the most dangerous — is always the keeper, so engagement calls are largely self-protecting.
The genuinely exposed case is a partial motion transition in a co-located cluster. **The scoring
refinement that matters: the observable is not silence** — a group line may still fire for an
unrelated reason, so "the group said something" is not evidence the movement report survived.

## Merge interaction with `main` — reported, deliberately not resolved

Re-run here rather than taken from round 3: `git merge-tree --write-tree --name-only main HEAD`
exits 1 with **eight conflicting files** — the seven round 3 predicted, plus
`.claude/agent-memory/dod/MEMORY.md`, which **this DoD pass itself added** (see the correction
below).

| file | shape | who resolves how |
|---|---|---|
| **`body-layer/tests/test_callouts.py`** | **both branches add test blocks** | **Needs eyes. Must be resolved by reading, not by taking a side.** |
| `body-layer/BACKLOG.md` | append | append-shaped; `main` carries `BL-B39`/`BL-B40`/`BL-B41` |
| `docs/acceptance/2026-10-05-sortie-feedback.md` | add/add | append-shaped |
| `.claude/agent-memory/{implementer,performance-reviewer,reviewer,security,dod}/MEMORY.md` | append (5 files) | append-shaped index lines |

**`body-layer/src/belief/callouts.py` auto-merges cleanly**, and `speech.py` does not conflict at
all — `main` never touched it.

This DoD pass's own edits were placed to avoid adding an eighth conflict, and that was verified by
re-running `merge-tree` after each: `body-layer/ROADMAP.md` **auto-merges** (the debt entry was
inserted mid-list, before `feature/terrain-callout-stages-345`, because two other branches inserted
at the head of that list overnight and a third top-insert would have conflicted on the exact line
they both rewrote), and `NOTES.md` **auto-merges**.

**One correction, because the first draft of this report got it wrong and re-running caught it.**
This pass's two index lines in `.claude/agent-memory/dod/MEMORY.md` *do* add an eighth conflict —
`main` appended to that same index earlier tonight. The draft asserted the opposite from
plausibility (the file was not in round 3's list of four) rather than from a re-run. It is
append-shaped and resolves exactly like the other four index files, so the cost is nil — but the
claim was wrong before it was checked, which is the failure mode this project names most often.

**A post-merge silence mode is predicted and survives into merged `main`** (round 3's finding, kept
here because whoever merges should know): `fix/callout-observability-gate` skips an unobservable
keeper with a bare `continue` while its peers are already permanently consumed — the identical
silence mode by a second trigger. The `engaged=True` exemption spares the danger call; motion and
range crossing are not spared. This is the same redesign `BL-B41` needs and is filed with it.

## Milestone-completion question

**Does this change what the next milestone should be, or invalidate a downstream assumption?**

It does not change what is next. It **sharpens one downstream assumption**: `BL-B41` and the merged
observability gate's matching silence mode are **one** piece of work, not two — both are the same
per-contact-vs-per-event granularity mismatch in the same election, so designing them separately
means designing the per-event election twice. They are already filed together on `BL-B41`, and that
is the right call. Nothing else downstream is invalidated: items 2 and 4 are self-contained
table/constant changes, and item 3 adds no new state (the watch tag is a one-time snapshot, with no
watch-to-group identity binding to maintain).

## Process signal — a recurring-fix pattern, for the orchestrator not the branch

**All of round 2's and round 3's required fixes were of one shape: prose asserting a guarantee the
code does not make.** "N lines about one group becomes one" — it can become zero. "Must always name
one … or suppression would silence the whole group" — it names one and the group is silenced anyway.
"Extend this predicate rather than adding a second gate" — the named next gate cannot go in that
predicate at all.

That is adjacent to an already-recorded category (a prose count or enumeration of a set that lives
in code being wrong, now 5th+ occurrence, filed on `main` in this role's own memory from
`fix/callout-observability-gate` earlier tonight). **But the cause underneath is different and is
new, so it is filed separately** (`project_recurring_predicate_granularity_mismatch.md`, 2nd
occurrence counting the observability gate): three rounds each made the predicate *stronger*, each
correctly, while the hole was that the predicate is one granularity coarser than what it governs.
The tell was available from round 1 and read as a strength — the predicate's own parameter list.

**This is process debt, not code debt.** The granularity question — *what is the unit of the thing
this gate governs, and does the gate take it as an argument?* — belongs at **Architect**, where the
quantifier is chosen, not at Reviewer, where only the condition is visible. Catching it at Reviewer
three times for one feature is the cost. A third independent occurrence would be the argument for
making it an explicit Architect-stage check rather than a memory.

## The acceptance boundary — what this feature's fixtures structurally cannot reach

Stated up front so a fixture pass is never mistaken for a flight pass. The 2026-09-16 precedent is
why: the F10 command vocabulary passed DoD on fixtures and the next day's sortie found two real
defects — `Scan` driving the 9K113 sight instead of this project's own naked-eye perception, which
did exactly what it said against the wrong subsystem and which no fixture can detect; and
`Cancel Task` speaking a raw task id aloud, which is only a defect when a human *hears* it and looks
correct as text in a log.

What no fixture here could have caught:

- **Whether `describe` survives this speaker's accent through Whisper.** The phrase table and the
  matcher are proven by execution; the recogniser is not. Both phrasings were added 2026-10-05, so
  the recorded corpus predates them — they are unbenched. A phrase that matches perfectly from text
  can still never arrive.
- **Whether real in-flight watched groups are the size this was reasoned about.** The amplification
  fix and the readback's usefulness both scale with group size, and the real distribution is
  unmeasured — the performance pass used 8 as a stated assumption, not an observation.
- **Whether a 6 s revisit interval on `ahead` is right.** It is arithmetic from two constants
  (3 legs × 2.0 s), not a judgement about what a gunner should do. Only the cockpit says whether it
  reads as scanning or as dithering.
- **Whether the 2.0 s HTTP tail actually bites over the LAN.** Measured over loopback only; the
  figure that matters is p99 on the real network.
- **`BL-B41`'s real frequency.** Reproduced in a constructed state. How often a co-located watched
  cluster has a quiet keeper in flight is unknown — and that number is what decides whether the
  per-event redesign is urgent. It is the card's marked prize for exactly that reason.
- **The whole class the 2026-09-16 sortie found**: code doing exactly what it says against the wrong
  subsystem, and text that is only wrong once spoken. Neither has a fixture-shaped signature.

## Deliverables written by this pass

| file | what |
|---|---|
| `plans/sortie-2026-10-05-refinements/dod-check.md` | this report |
| `docs/acceptance/2026-10-06-sortie-refinements-sortie.md` | acceptance card, source of truth |
| `docs/acceptance/2026-10-06-sortie-refinements-sortie-card.html` | the cockpit card, published at https://claude.ai/artifact/RueFQ6R3BZB7vZgfEugorQ |
| `body-layer/ROADMAP.md` | what shipped + live-acceptance-debt entry (mid-list) + milestone-completion answer |
| `NOTES.md` | "A predicate's granularity has to match the granularity of what it governs" |
| `.claude/agent-memory/dod/feedback_voice_card_never_prefix_a_command_with_the_wake_word.md` | the wake-word routing trap, found by running the matcher |
| `.claude/agent-memory/dod/project_recurring_predicate_granularity_mismatch.md` | the recurring pattern above |
| `.claude/agent-memory/dod/MEMORY.md` | two index lines |

`body-layer/BACKLOG.md` deliberately **not** touched — see `BL-B41` above.
