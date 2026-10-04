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
