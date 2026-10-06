# Review round 3 — the two round-2 required fixes

**Branch:** `feature/sortie-refinements` · **Tip reviewed:** `7a10751`, confirmed by
`git rev-parse HEAD` as the first action (AGENTS.md rule 4). The branch was checked out directly in
the worktree — it was free, `main` being the main checkout's branch — so no `git archive` snapshot
was needed and no reset was required. Unlike rounds 1 and 2, the worktree was *on the tip*.

**Scope:** `9b450ca` (keeper eligibility), `1feeda8` (the docstring corrections) and `7a10751`
(implementation log + agent memory), against `review-round2.md`'s two required fixes. Not a
re-review of the feature or of rounds 1–2, except where a round-1/2 claim is restated by text this
round edited (see finding R1).

`main` has moved a long way since the fork (`merge-base` = `896369e`; `main` is now `abdda2b`, two
features merged overnight). **Nothing was rebased or merged** — the branch was reviewed as it
stands, and the merge interaction is reported as a finding below.

## Checks (body-layer only; nothing else is in this diff)

The worktree has no `body-layer/.venv`, so the main checkout's binaries were borrowed by absolute
path with `cwd` inside the worktree's own `body-layer/`. **Imports proven worktree-local first**,
because borrowing an interpreter from another checkout is exactly how a wrong-code verification
happens:

```
belief.speech     -> <worktree>/body-layer/src/belief/speech.py
belief.callouts   -> <worktree>/body-layer/src/belief/callouts.py
belief.contacts   -> <worktree>/body-layer/src/belief/contacts.py
belief.attention  -> <worktree>/body-layer/src/belief/attention.py
query.describe    -> <worktree>/world-model/src/query/describe.py
belief.speech.may_be_callout_keeper present: True
```

| check | result |
|---|---|
| `ruff format --check src tests` | 115 files already formatted |
| `ruff check src tests` | All checks passed |
| `mypy src` | Success: no issues found in 53 source files |
| `pytest tests -q` | **1476 passed, 4 xfailed** — matches the expected count exactly |

All five relevant tests confirmed present **by name in unfiltered `pytest -v`**, not by a `-k`
filter (a `-k` filter silently skipped a brand-new test for an implementer on 2026-10-05):
`test_a_watched_peer_still_speaks_when_the_groups_keeper_is_unwatched`,
`test_group_callout_member_id_names_exactly_one_live_member`,
`test_group_callout_member_id_is_none_when_the_group_has_shrunk`,
`test_a_watched_group_that_starts_moving_speaks_one_line_not_one_per_member`,
`test_an_ungrouped_watched_contacts_motion_callout_is_untouched` — all PASSED.

The implementer's own counterfactual (neutering eligibility fails the new test; `speech.py`
restored byte-identical) was **not repeated** — the orchestrator re-ran it already.

---

## Fix 1 — keeper eligibility. Correct, and every claim in it checked rather than read

### "Agree by construction" — true literally, not just morally

This is the load-bearing claim and it holds in the strongest available sense: the filter's gate and
the election evaluate **the same function, with the same three arguments, taking the same tuple
element, against the same membership tuple**.

- `may_be_callout_keeper` (`speech.py:1428-1432`):
  `effective_attention(contact.attention, contact.last_position, store.areas)` → `[0] in ("watch",
  "priority")`.
- The filter gates on `describe_contact(...)["facts"]["attention"]`
  (`callouts.py:850-853`), and `describe_contact` → `_contact_result` (`tools.py:414-416`) derives
  that fact as `effective_attention(contact.attention, contact.last_position, store.areas)` —
  character-for-character the same call.

So the two cannot diverge without someone editing `tools.py:414`, and `effective_attention` is a
pure function of its three arguments (`attention.py:270-296`: an early return on `"ignore"`, then a
rank-max over `area_contains`, no live state, no I/O). The predicate is **not a restatement that
could drift** — which is the thing that makes this fix right rather than merely effective.

### `_leading_index` on the eligible subset cannot change the leader — proved exhaustively

`_leading_index` (`speech.py:1281-1295`) is a pure first-wins argmax over
`envelope_for(contact.classification).range_max_m`, with the running max reinitialised to `-1.0`
every call and no cross-element state. Argmax restricted to a subset is the subset's own argmax, and
the subset here is built by a list comprehension over the already-`sorted(...)` sequence, so
relative order — and therefore tie-breaking — is preserved.

Checked empirically rather than left at that: **all 63 non-empty subsets** of a six-member sequence
spanning four distinct envelope widths (`2K12 Kub` 35558 m, `ZSU-57-2 Sparka` 3704 m,
`Flakpanzer Gepard` 3704 m — a deliberate tie — `ZSU-23-4 Shilka` 2408 m) plus two members that
resolve no envelope at all (`Ural truck`, `T-72`), compared against an independently written argmax.
**0 mismatches.** The docstring's claim that "an ineligible member can neither become keeper nor
shift which eligible member does" is correct, ties included.

### Zero `describe_contact` on the suppression path — confirmed, and the saving is intact

Traced in the merged control flow, not assumed. The `self._consumed.add(event.id)` / `continue` is
at `callouts.py:845-846`; the filter's `describe_contact` is at `:847`, and a consumed peer never
reaches `live`, so the scoring `describe_contact` at `:872` is skipped too. The election itself
costs `store.contact` (a `dict.get`), `effective_attention` (pure arithmetic over `store.areas`),
and `envelope_for` (table lookup) — **no `describe_contact`, no `describe_position`, no
enrichment** — and is memoised once per group per tick (`group_keeper`, `callouts.py:792-794`). The
measured 2N→2 result is preserved by the fix, which was the explicit condition on it.

### The two `None` causes are maintainable

They are now separately named in the docstring, separately motivated, and they answer different
questions — group coherence (is there still a cluster to speak for?) versus eligibility (is there a
member we are allowed to keep?). Keeping the `< 2` guard counted over **all** resolving members
rather than only eligible ones is the right call and is argued in place.

One note on the implementation log's reasoning for that choice, which is muddled even though the
choice is right: it says counting only eligible members "would let a watched pair inside a larger
mostly unwatched group fall below the threshold and lose its suppression, which is a different bug
in the flood direction." That does not follow — a watched *pair* gives `len(eligible) == 2`, which
clears the threshold either way. The real reason the guard belongs over all members is the one the
docstring gives (it is a question about the group's own coherence), and the docstring is correct.
Log-only, no code consequence; listed as optional.

### The mutation check the round turned on — the shrunken-group test still pins its own subject

`test_group_callout_member_id_is_none_when_the_group_has_shrunk` now has two possible reasons to
return `None`, and its entire purpose is to pin one of them. **Checked by mutation, not by
reading**: with the coherence guard neutered in place (`if False and len(member_contacts) < 2:`),
the suite reports

```
FAILED tests/test_callouts.py::test_group_callout_member_id_is_none_when_the_group_has_shrunk
E   AssertionError: assert 'CONTACT_1' is None
1 failed, 1475 passed, 4 xfailed
```

**Exactly one test fails, and it is the right one.** The two `set_attention` calls the test gained
are what make this work: both surviving members are watched, so ineligibility cannot be supplying
the `None`, and the guard is the only thing left holding the assertion up. `speech.py` was then
restored from a pre-mutation copy and `git status --porcelain` came back empty — a byte-identical
restore, not a re-edit.

Extending the two tests rather than rewriting them was the correct call (AGENTS.md's escalation rule
covers rewrites, not one-line extensions), and the implementer flagged them rather than quietly
fixing them, which is the behaviour this project wants when a review's impact list turns out to be
short.

---

## Fix 2 — the docstring corrections. All three read literally, all three correct

| claim | literal reading |
|---|---|
| `callouts.py:227-229` — *"Filtered by group membership since the performance review below, but **never folded into the group's own line**"* | **True.** It is now filtered by membership, and nothing folds these kinds into `render_group_disclosure`. "the performance review below" resolves — the next paragraph cites it. |
| `callouts.py:51-55` — *"…and every remaining kind still competes and speaks exactly as it does today, grouped contact or not"* | **True.** `_TEMPLATED_KINDS` minus `{DETECTED, REACQUIRED}` minus `_WATCHED_ONLY_KINDS` leaves exactly `{CONTACT_CLASSIFICATION_CHANGED}`, which no group filter touches. Checked against the frozenset, not assumed from the prose. |
| `callouts.py:240-241` (the unprompted third) — *"That is the no-folding **half** of the paragraph above, which the suppression leaves intact"* | **True, and genuinely needed.** The paragraph above now has two halves, and editing it would have made the old *"That is the paragraph above, unchanged"* false. Catching that unprompted is the right instinct — this repo's `project_bl26_stage10_docs_confidence_decay_gap` is exactly the failure it avoids. |

The new closing sentence — *"always one whose own effective attention passes the gate above, or the
group's whole set of these kinds would be silenced by a keeper this filter then refuses to speak
for"* — is accurate and states the failure mode rather than just the rule.

---

## Required fixes

### R1 — "N lines about one group becomes one" is still false, and both docstrings edited this round assert it

**Proved by running the code, not by reading it.** Three cohering members, **all three watched and
all three eligible**, where the keeper simply has no event of that kind this tick:

```
keeper: CONTACT_1
motion events: ['CONTACT_2', 'CONTACT_3']     # the keeper did not transition
spoken: []                                     # ticks at 1.0, 5.0, 9.0
```

Both peers' events are `_consumed` — **permanently, "lost not deferred"** — because their
`contact_id != keeper_id`, while the keeper contributes nothing. The group's own disclosure line
does not cover the gap either: it is signature-gated on composition, not motion, and the probe
confirms it stayed silent across all three ticks.

The eligibility predicate cannot close this. Eligibility asks *"may this contact be keeper?"*; the
gap is *"does this contact have an event?"* — a per-**event** question that a `(store, contact)`
predicate cannot express. So this is not a defect in fix 1; fix 1 is correct within its own remit.

It is nonetheless a **required fix**, because it falsifies statements the code makes about itself,
including two that this round edited and left asserting it:

- `callouts.py:52` (module docstring, **edited this round**) — *"suppressed down to **one member's**
  line"*. It can be zero.
- `callouts.py:245-246` (`_WATCHED_ONLY_KINDS`, **edited this round**) — *"The suppression fixes the
  cardinality (**N lines about one group becomes one**)"*. It can become zero.
- `speech.py:1457-1459` — *"must always name one once there is an eligible member at all, **or
  suppression would silence the whole group**"*. It always names one, and the group is silenced
  anyway by the route above, so the stated purpose is not achieved.

Severity is bounded and worth stating plainly so this is not read as an emergency: `CONTACT_RANGE_
CROSSED` self-corrects (co-located members straddling a kilometre mark means the keeper crosses it a
poll or two later and speaks then), and where envelopes exist the widest-envelope member — the most
dangerous one, and the one most likely to generate `CONTACT_ENGAGEMENT_CHANGED` — is always the
keeper, so the engagement case is largely self-protecting. What is genuinely lost is a partial
motion transition in a co-located cluster, and a narrower-envelope member's engagement transition
while a wider-envelope keeper is quiet. **This is narrower than both the flood it replaced and the
round-2 silence it fixed**, so it is not a reason to hold the branch.

**Recommended fix, and it is the cheap half:** correct the three statements so they describe what
the code does (*"at most one"*, and name the keeper-has-no-event case as a known limitation), and
record the behavioural fix as a `BL-B<n>` backlog item. I have not edited `BACKLOG.md` — out of my
remit for this round.

The behavioural fix, for whoever picks the backlog item up, is **not** a predicate extension: it is
making the election per-*(group, kind)* and conditional on the elected member actually having a live
unconsumed event of that kind, falling back to the first eligible member that does. That keeps "at
most one line" while making zero unreachable, still needs no `describe_contact`, and is a real
design change that should not be rushed into a third-round branch.

### R2 — `may_be_callout_keeper`'s "extend this predicate" instruction is wrong for the one gate it names

The docstring says: *"**Extend this predicate rather than adding a second gate beside it.** Any
further reason the filter can drop an event — an observability gate being the one already in flight
(`fix/callout-observability-gate`) — reproduces the identical silence mode with a new trigger, and
the fix is `and <the new condition>` here."*

The intent is right and the generalisation is valuable. But `and observable` **cannot** go in this
predicate, and a later agent following the instruction literally would build the wrong shape:

- `store.callout_observable(contact, now_sim)` needs `now_sim`, which `may_be_callout_keeper(store,
  contact)` does not take.
- The gate's exemption is **per-event, not per-contact**: on `main` it reads
  `event.kind in _OBSERVABILITY_EXEMPT_KINDS and event.engaged is True`. A contact-only predicate
  cannot see `event.engaged`, so electing on observability alone would wrongly rule out a keeper
  whose `engaged=True` danger call is explicitly exempt — i.e. it would suppress the one line the
  sibling branch went out of its way to protect.

One sentence, in the same docstring, saying that the next gate may need the election to become
per-event rather than per-contact. Same class of defect as R1 — a docstring asserting something the
code cannot do — and the same cost to fix.

---

## Merge interaction with `main` as it now is

`fix/callout-observability-gate` merged to `main` overnight (`24746f5`). Re-verified against
**current** `main` (`abdda2b`), not against round 2's snapshot:

- **`body-layer/src/belief/callouts.py` auto-merges cleanly**, and `body-layer/src/belief/speech.py`
  does not conflict at all — round 3's code changes live there and `main` never touched it. Round
  2's independence finding still holds.
- In the merged tree the observability gate sits at the end of the filter loop (just before
  `live.append(event)`), well after the `_WATCHED_ONLY_KINDS` suppression block, with the
  `WATCH_REPORT_MIN_GAP_S` and `CALLOUT_MAX_AGE_S` blocks between them. Semantically coherent.
- **Seven files conflict**, one more than round 2 reported (round 2's own `reviewer/MEMORY.md` entry
  is the addition): `body-layer/tests/test_callouts.py`, `body-layer/BACKLOG.md`,
  `docs/acceptance/2026-10-05-sortie-feedback.md` (add/add), and the `implementer`,
  `performance-reviewer`, `security` and `reviewer` `MEMORY.md` files. All append-shaped except
  `test_callouts.py`, which both branches add test blocks to and which must be **read**, not
  resolved by taking a side. The implementation log's corrected paragraph names six — worth updating
  to seven, but it correctly refuses to license blind resolution, which was the point.

**Round 2's predicted post-merge silence mode is real and survives this round.** A watched, eligible
keeper that is *unobservable* has its event skipped by the gate (a bare `continue`, so deferred, not
consumed) while its peers are already permanently `_consumed` — nothing speaks for the group until
the keeper becomes observable, or ever, if `CALLOUT_MAX_AGE_S` retires it first. The `engaged=True`
exemption spares the danger call; motion and range-crossing are not spared.

**Does extending the predicate belong in this branch?** No — as a follow-up after the merge, and
per R2 not as a predicate extension at all. Three reasons: the gate does not exist in this branch,
so there is nothing here to extend against and no test could be written that exercises both; the
correct shape (per-event election) is the same change R1's backlog item needs, so doing them
separately means doing the same redesign twice; and this branch has already had three rounds for a
flood the pilot actually reported. Merge this, then do R1 and the observability extension as one
follow-up on top of merged `main`.

---

## Invariants

No omniscience boundary moved: `may_be_callout_keeper` reads `Contact.attention`/`last_position`
(both believed) and `store.areas`; `envelope_for` is the explicit no-omniscience line and is
untouched. No DCS write, no coordinate math added or scattered, no provenance/confidence field
involved, no `world-model/data/` path, no new dependency, no debug leftovers, no TODOs in the diff.
Mechanism (`9b450ca`) and documentation (`1feeda8`) are separate commits, as the body-layer
invariant requires — and the docstring commit is docs-only, verified by its diffstat.

The implementer's agent-memory file is at the **repo-root** path
(`.claude/agent-memory/implementer/project_keeper_eligibility_predicate.md`), not under
`body-layer/`, and `MEMORY.md` was **appended** to (one line, +1/-0) rather than rewritten — the
failure mode that orphaned 73 files on 2026-09-20. Both correct.

Working tree clean apart from this review document.

---

### Verdict

**APPROVED WITH REQUIRED FIXES**

**Round 3's two required fixes are approved as delivered — there is nothing in them to redo.** Fix 1
is correct, the "agree by construction" claim is true in the strongest sense available, the subset
argument is proved exhaustively, the 2N→2 saving is intact, and the extended test still pins its own
subject under mutation. Fix 2's three docstring corrections all read correctly literally, including
the unprompted third, which was genuinely necessary.

The two required fixes above (**R1**, **R2**) are **documentation-only and total roughly four
sentences**, plus one backlog entry I did not write because `BACKLOG.md` is outside my remit. Neither
requires touching `src/` logic.

### Ready for DoD?

**Yes — once R1 and R2 land, which is one short implementer pass, not another design round.**

Stating it without hedging, since three rounds have gone by: the code on this branch is correct for
what it claims minus two sentences of over-claim, and it is a clear net improvement for the pilot —
the flood is gone, the round-2 total silence is gone, and the residual silence I found is strictly
narrower than either. **Do not hold the branch for the per-event election redesign**; it is the same
change the post-merge observability extension needs and belongs on top of merged `main` as one
follow-up.

Branch for the pilot to fly: **`feature/sortie-refinements`**. The acceptance card is DoD's to write,
and the live-sortie observable for this round is specifically a *watched group that starts moving* —
one line, not one per member, and **not zero**.

### Review Confidence

**Full read**, with the following verified by execution rather than by reading:

- all four body-layer checks, in the worktree, with imports proven worktree-local first;
- the shrunken-group test's subject, by mutating the coherence guard and confirming exactly one
  failure, then restoring `speech.py` byte-identically;
- `_leading_index`'s subset-invariance, exhaustively over 63 subsets against an independent argmax,
  with a deliberate envelope-width tie;
- R1's silence, by constructing the state and reading `spoken == []` off a real `CalloutScheduler`
  across three ticks;
- the merge interaction, by `git merge-tree` against current `main` and by reading the merged
  `callouts.py` out of the resulting tree object;
- the "agree by construction" claim, by reading both call sites' source rather than trusting either
  docstring.

Not independently re-run: the implementer's own eligibility counterfactual, which the orchestrator
had already re-run and reported.
