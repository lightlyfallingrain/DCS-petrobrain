### Review Summary

BL-B112 (motion-aware contact certainty), branch `feature/motion-aware-certainty`, tip
`e14ba0ce52b20b447cf509473a8b13660ed82c09` (fast-forwarded cleanly onto this worktree's `main`,
`c4b4454d..e14ba0ce`, 8 commits, tree clean before the merge).

Full read of `plan.md`, `alignment.md` (goal check + plan check), `explore-notes.md`,
`implementation.md`, `test-card.md`, and a stage-by-stage diff of every file the implementer's
report names against `e6a43148` (the plan commit, pre-implementation). Ran body-layer's checks
from a freshly-built `.venv` (none existed in this worktree): `ruff format --check`, `ruff check`,
`mypy --strict`, `pytest -q`, and `tools/generate_defaults.py` (check mode). All green, matching
the implementer's own report exactly: 3173 passed, 4 xfailed (same 4 pre-existing xfails), 0 mypy
errors across 81 source files, defaults.toml up to date.

Stage-by-stage diff against the plan: all seven stages implemented exactly as specified, including
the two explicitly plan-authorized scope departures (fold_motion's founding-case reversal, Q2;
Buk/SA-11 left out, with the plan-check's own correction to the forward note already landed). The
three test files outside the plan's Affected Modules list (`test_mock_flight_chain.py`,
`test_crew_console.py`, `test_body.py`) were genuinely necessary mechanical/behavioural follow-ons,
not scope creep — confirmed by reading each diff, not just the implementer's claim. The silent
"scope/hybrid-only surface contacts skip 'estimated' entirely" consequence the implementer flagged
is not a new defect: it is the direct, already-anticipated consequence of a decision
`explore-notes.md`'s "Open assumptions" and `plan.md` Stage 3 both state explicitly (immobile/
never-observed-moving units crossing the growth threshold only after `LOST_THRESHOLD_S`, so they
go tracked → lost directly). It matches the explore-notes decisions; no action needed beyond what
the implementer already did (surfacing it).

One required fix: `test-card.md` Case 1 states an expectation that contradicts the plan's own
explicit design and the implementation's own passing test
(`test_immobile_contact_still_goes_lost_at_the_lost_threshold`). Since player-facing correctness is
the Reviewer's alone to catch now, and this is the acceptance document the user will fly against,
it needs fixing before the test card is used.

### Required Fixes

- **`test-card.md` Case 1 tells the tester to wait "several minutes (well past the old ~2-minute
  'estimated' window)" and then expects the fixed site to "not have gone silently to 'lost' either
  (it should still be in working memory, reportable)".** That is wrong per this plan's own explicit
  decision: "lost" stays purely elapsed-time for every contact, immobile ones included
  (`plan.md` Stage 3: *"`LOST_THRESHOLD_S` is untouched... A unit whose growth rate implies it
  would cross 500 m only after 120 s (installations: never)... goes tracked → lost directly,
  skipping estimated"*), and the implementation has a passing test proving exactly this
  (`test_decay.py::test_immobile_contact_still_goes_lost_at_the_lost_threshold`:
  `certainty_of(immobile_contact, now_sim=LOST_THRESHOLD_S + 0.1) == "lost"`). A fixed SAM site
  unseen for "several minutes" (i.e. past 120 s) *will* go lost, same as any other contact — it
  just never passes through "estimated" on the way, and the hedge it never gets is "last I saw",
  not "lost" itself. As written, the card sends the pilot into a sortie expecting a site to stay
  in working memory past 2 minutes, which it will not; a tester following the card literally would
  either falsely report "it went silently to lost" as a regression (it is correct, documented
  behaviour) or be confused by the card's own trailing sentence ("if it does eventually go
  lost...") contradicting the primary expectation three sentences earlier. Split Case 1 into two
  distinct checks instead: (a) **within ~2 minutes unseen**, confirm it is still named as fact and
  never hedged "last I saw" — this is the real, novel E1/E4 behaviour this plan adds; (b) **past
  ~2 minutes unseen**, confirm it goes "lost" (same as every contact) and that a mission-memory
  entry now exists recording its last-seen place and time (Stage 5c's write half). Case 5 already
  gets (b) right for an ordinary ground contact — Case 1 just needs to stop claiming the opposite
  for a fixed site.

### Optional Refinements

- `plan.md`'s two flagged, non-blocking Decisions (SA-2's `op_class="OP_LRSAM"`; the opportunistic
  SA-10 `installation_component` fix) were implemented exactly as the plan specified, with no
  further user sign-off sought in this pass — both are explicitly framed in the plan as "flag to
  the user, not a blocking question," so surfacing them at DoD/merge rather than re-litigating here
  is consistent with the plan's own instruction. Worth a one-line mention in the DoD report so the
  user actually sees the flag, not a required fix on this review. (Optional)
- `implementation.md`'s own "Notable Discoveries" section already documents the scope/hybrid-only
  silent-consequence finding in detail. Consider folding one sentence of it into `test-card.md`'s
  existing "A known gap, not a regression to report" section, since a tester glassing a contact
  only via the scope/hybrid channel (no naked-eye motion percept ever) will observe the same
  "tracked → lost, never 'estimated'" behaviour as a stopped mobile unit, which could otherwise
  read as a second surprise during live acceptance. Not blocking — the behaviour is correct and
  already explained in the implementation record; this only helps the live tester recognise it in
  the moment. (Optional)

### Verdict

APPROVED WITH MINOR FIXES

### Review Confidence

Full read. Plan, alignment (goal check + plan check), explore-notes, implementation record, and
test card all read in full; every stage's diff checked against the plan's own prescription
(object_model.py, association_over_time.py, decay.py, tuning.py, motion.py, contacts.py,
entries.py, admission.py, body.py, speech.py, crew_console.py, and every named test file); all
four checks (ruff format, ruff check, mypy --strict, pytest) run fresh in this worktree rather than
trusting the implementer's report, and they match it exactly. Import-direction invariant
(`mission_memory` imported only by `belief/tool_api.py`) and the no-cycle claim
(`association_over_time.py` → `decay.py`) verified directly by grep, not assumed. The
Kub/SA-6 `area_half_width_deg` acceptance table in `implementation.md` was read and is internally
plausible (uses a sigma-scaled covariance formula, not a bare linear one, so the implementer's
reported figures were not independently recomputed by hand) — not re-derived from scratch, since
the implementer states it was measured against the real function rather than assumed.
