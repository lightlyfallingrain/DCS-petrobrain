### Implementation Summary

Fixes the second duplicate-report path body-layer still had after `fix/contact-report-flood`
merged: a `belief.groups.Group`'s **first** disclosure used to always speak the group's full
roster the instant two-plus members first clustered -- even when every one of those members had
already been announced individually (directly, or via a merge-echo-suppressed duplicate the
earlier fix already silences). Real sortie-1004 evidence: three ground contacts founded and
spoken individually at `t_sim=699.1`; one of them re-founded under a fresh id at `t_sim=714.5`,
correctly silenced by the merge-echo fix; then at `t_sim=730.9` a brand-new `Group` of those same
contacts still spoke "A couple of contacts, 1 o'clock, 2.5 kilometres." -- telling the pilot, a
second time, about contacts he had already been told about.

User direction (2026-10-05) settles the design question: *"for now, no 'those are together',
prioritize less speaking."* So a group's opening line never announces the fact of grouping on its
own -- it speaks only what is genuinely new relative to what was already said about its current
members, reusing the existing delta taxonomy (`belief.speech.render_group_disclosure`'s branches
2-5) rather than inventing a second rule for "new" at time zero:

- **Every current member already reported**: silent.
- **Some, but not all, already reported**: a delta clause naming only the unreported,
  differentiated members, through the identical "worth-announcing" filter branch 4 already
  applies to a *later* arrival (new classification, or another instance of an already-known
  air-defence class).
- **No member already reported**: full disclosure, unchanged -- a genuinely new group still
  speaks in full.

**Scoped to the first disclosure only.** Everything past branch 1 (leader change, first
differentiation, the arrival delta, "otherwise silent") is untouched -- that taxonomy was already
settled by `plans/group-cohesion-redesign/plan.md` and the user has already judged it.

### Where "already reported" is known

Neither `Contact` nor `Group` tracks anything speech-shaped today, and this fix does not add a
field to either. "Already reported" is a fact about *what `belief.callouts.CalloutScheduler` has
actually said* -- the scheduler already owns exactly the state needed to answer it:

1. **The member's own `CONTACT_DETECTED`/`CONTACT_REACQUIRED` was actually spoken** --
   `contact_id in self._last_spoken_signature`, the same dict `_render_event`'s own singleton gate
   already reads (`plans/group-reporting/plan.md` Stage 1).
2. **It was itself merge-echo-suppressed** (`plans/contact-report-flood/plan.md` Stage 1) -- the
   identical `contacts_plausibly_same`/`first_seen_sim`/`certainty_of` condition `_render_event`'s
   `CONTACT_DETECTED` branch already evaluates to decide whether to suppress that announcement in
   the first place, restated (not factored into one shared helper, since the two call sites differ
   in exactly one respect: one asks about *this* contact's own candidate event, the other asks
   about a member reached by iterating a group's membership with no event in hand). Per that
   branch's own reasoning, this does **not** additionally require the earlier, plausibly-same
   contact to itself appear in `_last_spoken_signature` -- a contact that is not `lost` and
   strictly earlier-founded is, by the same premise the suppression itself relies on, the contact
   whose continuity the newer one is an echo of.

New method `CalloutScheduler._already_reported_member_ids` (`body-layer/src/belief/callouts.py`)
computes this set per group, per tick, and is passed into `render_group_disclosure` as a new
keyword-only parameter, `already_reported_contact_ids: frozenset[str] | None`. `None` (the
default) means "no information available" and preserves the exact pre-existing always-full
behaviour -- every test in `test_speech.py` that does not pass the parameter is unaffected by this
change.

### Files Changed
- `body-layer/src/belief/speech.py` -- `render_group_disclosure` gains the
  `already_reported_contact_ids` parameter and branch 1's three-way split (silent / partial delta
  / full); new shared helper `_render_member_delta_clause` factors the delta-clause rendering out
  of branch 4 so the opening line's partial case and a later arrival's delta compose identically
  (one implementation, not two).
- `body-layer/src/belief/callouts.py` -- new `CalloutScheduler._already_reported_member_ids`
  method; both `tick()` call sites that invoke `render_group_disclosure` (scoring time and
  speak-time re-render) now compute and pass this set. Module docstring extended with the
  mechanism's own section, parallel to the existing merge-echo section it builds on.
- `body-layer/tests/test_speech.py` -- four new tests for `render_group_disclosure`'s new
  three-way branch (see below).
- `body-layer/tests/test_callouts.py` -- one new integration test exercising the scheduler's own
  `_already_reported_member_ids` end to end, built directly on the existing merge-echo fixture;
  one existing test's expected output updated (see "Notable Discoveries").

### Tests Added
- `test_render_group_disclosure_all_members_already_reported_is_silent` -- every member already
  reported -> `None`.
- `test_render_group_disclosure_one_unreported_member_speaks_only_the_new_part` -- two members
  already reported, one truck never reported -> `"Truck, in the group."`, not the full roster.
- `test_render_group_disclosure_already_reported_set_ignored_once_group_has_spoken` -- scope check:
  once a group has already spoken (`last_spoken_signature` is not `None`), a later genuine arrival
  still speaks its own delta exactly as before even if the caller passes an already-reported set
  covering the whole group -- the new gate only ever applies to branch 1.
- `test_render_group_disclosure_no_members_already_reported_still_speaks_in_full` -- an explicit
  empty `already_reported_contact_ids` (as opposed to every other pre-existing test's implicit
  `None`) still gets the ordinary full disclosure.
- `test_group_of_already_reported_and_merge_echo_suppressed_members_is_silent`
  (`test_callouts.py`) -- end-to-end through `CalloutScheduler`, built on the existing
  `test_merge_echo_refounding_near_a_live_contact_is_not_spoken` fixture: contact A speaks its own
  `CONTACT_DETECTED` individually, contact C's founding is merge-echo-suppressed against A, and a
  `Group` later persisting both A and C (constructed directly -- they are 500 m apart, inside the
  *contact* association gate this fixture borrows but outside `belief.groups`' own tighter
  cohesion gate, so they never cohere via `GroupStore.reconcile` on their own) never becomes a
  speaking candidate across four subsequent polls.

### Checks (body-layer/)
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (no issues, 53 source files)
- `pytest tests -q`: **1414 passed, 4 xfailed** (baseline on `main` before this change: 1409
  passed, 4 xfailed -- 5 new tests, one existing test's expectation updated to the new, intended
  behaviour, zero regressions elsewhere)

### Sortie replay measurement

**No raw observation/percept stream exists in the `sortie-1004` snapshot** (`belief-truth.jsonl`
is itself an *output* of the original run, logged only when a contact's state changes -- not a
full per-tick snapshot -- so exact group membership at every instant is not always recoverable
from it). This is the same limitation `plans/contact-report-flood/implementation.md` already
documented for this snapshot; what follows is the same kind of retroactive reading, not a claim of
exact reproduction.

Classifying the sortie's 23 `kind: "speech"` lines by rendered shape (the group-disclosure
vocabulary -- "A couple of", "Pair of", a bare composition clause, or "X and something" -- versus
the ordinary singular `_contact_report_text`/classification-change forms) finds **5 group-level
lines** across the whole sortie, not the 3 inside the 52-second window the task's quoted excerpt
covers (699.1-751.2, which does contain exactly 3: 704.4, 730.9, 751.2 -- matching the task's own
count for that window):

| t_sim | text | already-reported? |
|---|---|---|
| 704.407 | "A couple of contacts, 2 o'clock, 3.5 kilometres." | No evidence of prior individual reporting at this bearing/range -- a new sighting, unaffected. |
| **730.885** | **"A couple of contacts, 1 o'clock, 2.5 kilometres."** | **Confirmed suppressed** -- per the task's own verified object-id evidence, `CONTACT_8` held T-72B3 `16844032` and BTR-80 `16845056`, both already inside `CONTACT_3`/`_4`/`_5` founded and spoken at `t_sim=699.073`. Under this fix, both of this group's members are `already_reported` (one directly, one via merge-echo), so the line goes silent. |
| 751.247 | "A couple of contacts, 3 o'clock, 1.5 kilometres." | Different clock/range from every preceding individual line -- treated as a new sighting; not confirmed redundant from this data. |
| 835.713 | "Infantry and something, 11 o'clock, very close." | Only one contact row logged at this tick (sparse logging); insufficient data to confirm either way. |
| 1021.9 | "A couple of contacts, 11 o'clock, 3.5 kilometres." | **Likely also suppressed**, though not independently confirmed by object id the way 730.9 is: the two immediately preceding individual lines, `t_sim=1011.008` and `1016.564`, both read "ground, 11 o'clock, 3.5 kilometres next to a road." -- near-identical wording for what is almost certainly the same two contacts this group then re-announces 5-10 s later. The scene here (`t_sim≈992-1027`) has a large, heavily overlapping cluster of 20+ contact/object ids that this snapshot's logging granularity cannot cleanly disambiguate, so this is reported as a strong suspected case, not a confirmed one. |

**Net measurement: 1 of 5 group lines confirmed suppressed (the named 730.9 line), 1 more strongly
suspected (1021.9), 3 unaffected (704.4, 751.2, 835.7) by the evidence this snapshot can support.**
This is a smaller fraction of the sortie's total chatter than the detection-duplicate fix (which
roughly halved id-churn lines), but it is the entire fix the task named this line for, and the
named acceptance example (730.9) is confirmed gone.

### Notable Discoveries

**`test_2c_transcript_fixture_renders_four_lines_not_seven` (`test_callouts.py`) needed its
expectation updated, not its line count** -- found by running the full suite, not predicted. Its
five-member group's third line used to read "Three infantry, BTR-70 and truck, 1 o'clock, very
close." (full disclosure) even though one of its five members (`CONTACT_2`, the 1-o'clock
infantry) had already been individually announced as the fixture's own line 1. Under this fix,
`OP_INFANTRY` becomes a known class the instant that happens, so the *other* two infantry members
(`CONTACT_1`/`CONTACT_3`, grouped from the instant they were founded and never themselves
individually spoken) are silently folded in rather than re-announced -- the identical "one more of
an already-known class makes no difference" rule branch 4 already applies to a later arrival. The
line becomes "BTR-70 and truck, in 1 o'clock group." -- still 4 total lines for the fixture, just a
shorter third one. This is the fix working as designed on a second, pre-existing case the task did
not name, not a regression; the test's docstring and assertion were updated to document why, per
the Implementer role's own guidance to flag rather than silently work around a plan-vs-reality
mismatch.

**`belief.groups`' cohesion gate is measurably tighter than `belief.association_over_time`'s
contact-founding gate.** The merge-echo fixture's own borrowed geometry (contacts 500 m apart,
bearing 0, ranges 1000/1500) keeps two observations as distinct `Contact`s under the founding gate
but never coheres them into a `Group` via `GroupStore.reconcile` on its own -- the new
`test_callouts.py` integration test had to construct its `Group` directly (mirroring
`test_speech.py`'s existing `stale_group` pattern) rather than relying on natural clustering,
confirmed empirically while writing the test.

**`BL-B24`/`plans/contact-duplication-ambiguity-runaway/plan.md` remain open and untouched** --
this fix only changes what a group's *first disclosure* says about members it already has: the
root "2+ candidates -> always a new contact" policy question, and the duplication-runaway backlog
item, are unaffected.

### Review follow-up (2026-10-05)

Two optional findings from `plans/redundant-group-disclosure/review.md`, actioned:

**Item 1 -- the restated merge-echo predicate, shared rather than guarded.** Reviewer confirmed
`_already_reported_member_ids`'s branch 2 restated `_render_event`'s own `CONTACT_DETECTED`
merge-echo suppression condition character-for-character, with no shared helper and no test that
would catch the two drifting apart. Sharing turned out to fit cleanly despite the two call sites
asking the question in different shapes (one has an `Event`'s own contact in hand, the other
reaches a member by iterating a group's membership with no event at all): both questions reduce to
the same single predicate over `(contact, store, now_sim)` -- "is there a strictly-earlier-founded,
not-`lost`, plausibly-same contact already in the store" -- once the event-specific wrapping is
stripped away. Factored into a new module-level function, `_is_merge_echo_of_earlier_contact`
(`body-layer/src/belief/callouts.py`), and both call sites now call it instead of repeating the
four-condition `any(...)`. The "strictly earlier founding only" rationale comment (why same-poll
foundings must never mutually suppress) moved to the call site that still carries the full
sortie-1004 history behind it, rather than duplicating it into the helper's own docstring. No drift
guard test was needed once there is only one copy of the condition to drift from.

**Item 3 -- the current-tick re-evaluation residual, recorded not fixed.** Filed as `BL-B25`
(`body-layer/BACKLOG.md`): `_already_reported_member_ids` asks the merge-echo question against
*current* belief, not the belief state at the moment the original suppression happened, so a
member that has since gone `lost` or drifted apart from its echo source can stop counting as
reported and cause one extra spoken line. Bounded to the first-disclosure window, pushes toward
speaking rather than silence (the safer direction given a no-omniscience system, though the
opposite of this fix's own "less speaking" goal), not a correctness issue -- recorded for
discoverability per the Reviewer's own recommendation, not actioned.

**Item 2 -- `body-layer/ROADMAP.md`/`body-layer/BACKLOG.md`/`plans/
contact-duplication-ambiguity-runaway/plan.md` bookkeeping**, mirroring `fix/contact-report-flood`'s
own `3884840`: a new Status entry for this fix, and a note on both `BL-B24` and the
duplication-runaway plan that this fix doesn't close them either -- the root `ContactStore.ingest`
ambiguity policy remains untouched by any of these three speech/callout-layer fixes.

Checks after this follow-up, from `body-layer/`: `ruff format --check src tests` pass,
`ruff check src tests` pass, `mypy --strict src` pass (53 files), `pytest tests -q` -> 1414
passed, 4 xfailed (unchanged from the implementer's original figure -- a pure refactor, no test
added or removed).
