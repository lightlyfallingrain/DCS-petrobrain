### Review Summary

Reviewed `fix/redundant-group-disclosure` (tip `4d81c43`, fix commit `b09f270`) against
`plans/redundant-group-disclosure/implementation.md`. The fix silences a `Group`'s own first
disclosure when every current member's content already reached the pilot (directly or via
merge-echo suppression), and speaks only the genuinely-new remainder in the partial case —
scoped to the first-disclosure branch only, via a new keyword-only `already_reported_contact_ids`
parameter on `render_group_disclosure` that defaults to `None` (old behaviour unchanged).

All checks pass inside the worktree (fresh venv built from `body-layer/pyproject.toml`):
`ruff format --check`, `ruff check`, `mypy --strict` (53 files, clean), `pytest -q` →
**1414 passed, 4 xfailed**. Independently rebuilt a `main`-tip snapshot via `git archive` and ran
the same suite there: **1409 passed, 4 xfailed** — confirms the claimed baseline and the +5 new
tests with zero regressions.

Empirically disabled the new `already_reported` computation (forced it to always be empty) and
reran the four tests the implementer names as proof of the mechanism
(`test_render_group_disclosure_all_members_already_reported_is_silent`,
`test_render_group_disclosure_one_unreported_member_speaks_only_the_new_part`,
`test_group_of_already_reported_and_merge_echo_suppressed_members_is_silent`,
`test_2c_transcript_fixture_renders_four_lines_not_seven`) — all four failed with the exact
expected diffs, confirming they are real regression tests, not decorative. Restored the files and
reran the full suite to confirm the clean state (1414/4 again).

**Checklist items verified:**

1. **The restated merge-echo predicate** (`CalloutScheduler._already_reported_member_ids`, branch
   2) is character-for-character the same four conditions `_render_event`'s own `CONTACT_DETECTED`
   suppression check uses (`other.id != contact.id`, `other.first_seen_sim < contact.first_seen_sim`,
   `certainty_of(other, now_sim) != "lost"`, `contacts_plausibly_same(...)`) — confirmed by reading
   both sites side by side (`callouts.py:658-660` vs. `callouts.py:732-734`). No shared helper, as
   the implementer disclosed, but the two are a faithful restatement today. See "Optional
   Refinements" for the drift risk this still carries.
2. **Counts-as-reported for a merge-echo-suppressed member** is exercised end-to-end, not just
   unit-level, by `test_group_of_already_reported_and_merge_echo_suppressed_members_is_silent`,
   which drives the real `CalloutScheduler.tick()` sequence (A speaks, C's own founding is
   suppressed, then a directly-constructed `Group{A, C}` is polled four times) rather than
   constructing the "already reported" set by hand. This is the right level of test for a
   timing-sensitive claim and it passed independently in my own run.
3. **Scope to first disclosure only** — confirmed by reading the full `render_group_disclosure`
   body: `never_spoken_fully_covered`/`never_spoken_partially_covered` are both gated on
   `never_spoken`, and the pre-existing leader-change/first-differentiation/arrival-delta/silent
   branches are structurally untouched (the diff only edits branch-1's own conditional and factors
   one already-duplicated delta-clause block into a shared helper). Grepped for the new
   mechanism's own call sites (not the file list) — `already_reported_contact_ids=` appears at
   exactly the two `tick()` call sites named in the implementation doc
   (`callouts.py:827`, `callouts.py:868`, scoring-time and speak-time re-render), and
   `render_group_disclosure`'s only other caller, `crew_console.py`'s on-demand "report" path, is
   confirmed to deliberately call `render_group_full_disclosure` instead (pre-existing, documented
   inline, untouched by this fix).
4. **The partial case** renders crew-speech, not a debug dump: ran
   `test_render_group_disclosure_one_unreported_member_speaks_only_the_new_part` directly — output
   is `"Truck, in the group."`, using the identical `_render_member_delta_clause` helper a later
   tick's own arrival-delta already used pre-fix. Read it aloud mentally against the existing
   `"Shilka, in 2 o'clock group"` worked example in the docstring — same shape, no new vocabulary
   invented.
5. **The `test_2c_transcript_fixture_renders_four_lines_not_seven` expectation change** —
   independently verified by disabling the mechanism (see above): the old expectation
   (`"Three infantry, BTR-70 and truck, 1 o'clock, very close."`) reappears exactly when the fix is
   turned off, and the new one (`"BTR-70 and truck, in 1 o'clock group."`) only appears with the
   fix active. This is the same bug class on a second, pre-existing case, not a quietly-relaxed
   assertion — the implementer's own account held up under an independent check, not just a
   re-read.
6. **The sortie measurement** (1 of 5 group lines confirmed suppressed at 730.9, by exact object
   id; 1 more suspected at 1021.9 but explicitly not claimed as confirmed; 3 unaffected) is honestly
   qualified and consistent with the object-id evidence quoted in the task. No overclaiming found.

### Required Fixes

None.

### Optional Refinements

- **The restated merge-echo predicate (checklist item 1) has no test that fails if the two copies
  diverge.** Today they're identical; if `_render_event`'s `CONTACT_DETECTED` suppression condition
  is ever edited without a matching edit here, nothing catches it — the group-disclosure gate would
  silently start treating members as "already reported" (or not) inconsistently with what was
  actually suppressed. A cheap guard: a test that monkeypatches/parametrizes one shared geometry
  fixture and asserts `_already_reported_member_ids`'s per-contact verdict matches whether
  `_render_event` actually returned `None` for that contact's `CONTACT_DETECTED`, for a few cases
  including one where `contacts_plausibly_same` is on the boundary. Not required now — the
  implementer's stated reason for not sharing one helper (one call site has an event in hand, the
  other doesn't) is reasonable — but worth a backlog note (`BL-B<n>` or equivalent) so the risk is
  tracked rather than just living in the implementation.md prose.
- **`_already_reported_member_ids`'s branch 2 re-evaluates `contacts_plausibly_same`/`certainty_of`
  at the *current* tick, not at the tick the original suppression happened.** If the echo source
  has since gone `lost`, or the two contacts have since drifted apart enough that
  `contacts_plausibly_same` now reads false, a genuinely-already-suppressed member stops counting
  as "already reported" and the group's first disclosure could re-speak content that, strictly,
  already reached the pilot. This pushes in the *opposite* direction from the user's "prioritize
  less speaking" instruction (it risks one extra line, not a missed one), and is bounded to the
  first-disclosure window only — not a correctness risk to the no-omniscience invariant, just a
  residual case where the fix's own goal is imperfectly met. Flagging for awareness, not blocking.
- **No `ROADMAP.md`/`BACKLOG.md` bookkeeping commit yet** noting this fix and what it does/doesn't
  close (`BL-B24`/`contact-duplication-ambiguity-runaway` stays open and untouched, per
  implementation.md's own "Notable Discoveries"). `fix/contact-report-flood` got exactly this as a
  separate commit (`3884840`) after Reviewer/Security/DoD. Worth the same treatment before merge,
  not a Reviewer blocker.

### Verdict
APPROVED

### Review Confidence
Full read of both diffs (`speech.py`, `callouts.py`), the full `render_group_disclosure` function
body post-patch, and the module docstring additions. All five new tests plus the one changed
expectation independently re-verified by disabling the mechanism and confirming failure, then
restoring and confirming the clean 1414/4 pass. Baseline (1409/4) independently reproduced from a
`git archive` snapshot of `main`, not taken on the implementer's word. Did not independently
re-derive the sortie-1004 object-id evidence (699.1/714.5/730.9) from the raw log — relied on the
task's own pre-verified numbers, which the implementation.md measurement is consistent with.

---

## Round 2 — follow-up review (2026-10-05)

Reviewed `fix/redundant-group-disclosure` tip `9adaccf` (one commit over round 1's `4d81c43`,
range `a2aeda8..9adaccf`), checked out directly in a fresh worktree (`git rev-parse HEAD` confirmed
`9adaccf` before anything else). Scope: the single follow-up commit actioning round 1's three
Optional Refinements.

**Item 1 — shared predicate, read against both former copies.** New module-level
`_is_merge_echo_of_earlier_contact(contact, store, now_sim)` (`callouts.py`) extracts the
four-condition `any(...)` both call sites previously restated. Read all three sites side by side
against the commit's parent:

- `_already_reported_member_ids` previously tested `other.id != contact_id` (the dict key) where
  `contact = store.contact(contact_id)`; the helper tests `other.id != contact.id`. Since
  `ContactStore.contact` looks a contact up by its own id, `contact.id == contact_id` always holds
  here — no semantic shift.
- `_render_event`'s call site previously tested `other.id != this_contact.id`; the helper's
  `contact.id` is the same object passed in as `this_contact`. Identical.
- Both remaining three conditions (`first_seen_sim` ordering, `certainty_of(...) != "lost"`,
  `contacts_plausibly_same(...)`) are copied verbatim into the helper, argument order and all.

The refactor is behaviour-preserving, not merely claimed so — confirmed by argument-level
comparison, not just diff-reading, and independently by the unchanged 1414/4 test count (a pure
extraction has no reason to move it, and it didn't).

**Call sites still differ where they should.** `_render_event` still does its own
`event.kind in (CONTACT_DETECTED, ...)` gating, its own `store.contact(event.contact_id)` lookup
and `None` check, and its own post-hoc `route_event`/`_last_spoken_signature` bookkeeping — none of
that moved into the helper. `_already_reported_member_ids` still does its own membership iteration
and its own `_last_spoken_signature` branch-1 check before ever reaching the helper. Only the one
condition both sites literally restated character-for-character moved; nothing specific to either
caller was hoisted in with it.

**The "strictly earlier founding only" rationale comment** stayed at the `_render_event` call site,
not the helper — confirmed by reading the current file (`callouts.py`, around the `CONTACT_DETECTED`
branch). The helper's own docstring states the condition itself and names both call sites and the
plan/review item it comes from, but not the sortie-1004 "why strictly earlier, not same-poll"
reasoning. A reader arriving at the helper from the group-disclosure path (`_already_reported_
member_ids`) sees *that* the condition requires strict earlier founding but not *why* same-poll
foundings must never mutually suppress — they'd have to follow the docstring's pointer back to
`_render_event` to find it. This is a real asymmetry, but a minor one: the docstring does link the
two sites together by name, and the condition is unchanged either way (not a case where a reader
could act on wrong reasoning, just slower to find the right reasoning). Optional, not a blocker.

**No drift guard, because no duplication — agree.** Round 1 flagged the missing guard test as a
risk specifically *because* there were two copies that could diverge silently. There is now exactly
one definition; a future edit to the condition edits one function, and both callers see it change
together by construction. The two call sites could in principle need to diverge (e.g. if
group-disclosure ever needed a different staleness tolerance than event-time suppression), but
nothing in this fix or its plan suggests that's coming, and if it ever does, the helper would be the
first place to look, not a silent trap — a reviewer reading `grep -rn _is_merge_echo_of_earlier_
contact` would immediately find both callers. Agreed that a guard test is no longer owed.

**`BL-B25`** — `body-layer/BACKLOG.md`'s highest prior id was `BL-B24`; `BL-B25` is the next unused
number (verified by listing every `BL-B<n>` in the file and sorting numerically, not by eyeballing
the tail). The entry accurately restates the residual (current-tick re-evaluation vs.
suppression-time state) and explicitly says it "pushes in the opposite direction from the user's
'prioritize less speaking' instruction... it risks one extra spoken line, never a missed one" —
correctly flagged as the less-preferred direction, not glossed over or minimized.

**Bookkeeping landed in all three files as claimed:**
- `body-layer/ROADMAP.md` Status list gains the fix's entry (Reviewer-approved, not yet DoD'd),
  including the BL-B25 residual and a "does not change what's next" milestone-completion line.
- `body-layer/BACKLOG.md`'s `BL-B24` entry gains a note that this fix doesn't close it either
  (speech-layer symptom, root `ContactStore.ingest` policy untouched).
- `plans/contact-duplication-ambiguity-runaway/plan.md` gains the equivalent note.

All three read consistently with each other and with `implementation.md`'s own addendum (one minor
cosmetic mismatch: `implementation.md` labels the bookkeeping note "Item 2" and the residual "Item
3", while `review.md`'s own Optional Refinements list them in the reverse order — content maps
correctly regardless, this is a numbering-label slip only, not a required fix).

**Verification, inside `body-layer/` (fresh `.venv` built from `pyproject.toml`):**
`ruff format --check src tests` — 114 files already formatted. `ruff check src tests` — all checks
passed. `mypy src` — success, 53 source files. `pytest tests -q` — **1414 passed, 4 xfailed**,
unchanged from round 1, as expected for a pure refactor plus doc-only bookkeeping.

### Round 2 Required Fixes
None.

### Round 2 Optional Refinements
- The sortie-1004 "strictly earlier founding only" rationale lives only at the `_render_event` call
  site, not the shared helper's docstring — a reader reaching the helper via the group-disclosure
  path has to follow a pointer rather than find the reasoning in place (optional).
- `implementation.md`'s "Item 2"/"Item 3" labels don't match `review.md`'s own ordering of the two
  findings they refer to — content is correct, labels are swapped (cosmetic only).

### Round 2 Verdict
APPROVED

### Round 2 Review Confidence
Full read of the one commit's diff (`callouts.py`, `BACKLOG.md`, `ROADMAP.md`,
`contact-duplication-ambiguity-runaway/plan.md`, `implementation.md`), both former call sites
against the parent commit, and the full numeric `BL-B<n>` sequence in `BACKLOG.md`. All four
verification commands run directly, not taken on the commit message's word.
