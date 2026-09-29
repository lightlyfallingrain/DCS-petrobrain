## Security Deep Analysis: group-reporting

Reviewed against an isolated snapshot of `feature/group-reporting` @ `b92c7a7`
(`git archive feature/group-reporting | tar -x`), since this worktree's own
branch (`worktree-agent-a3bee731b97b852c5`) is not that branch. All commands
below were run with `cwd` inside that snapshot's `body-layer/`.

### Dependency Status
No dependency change.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| body-layer/src/belief/groups.py:reconcile, _cluster_contacts | Clustering reads `Contact.position` (fused belief, `PositionEstimate.x/z`) and `Contact.last_class_raw` (believed classification) only | No omniscience violation — never reads an `object_id`, DCS-truth position, or anything routed through `detection_trace_writer` | None |
| body-layer/src/belief/speech.py:1131-1244 `render_group_disclosure` | Threat-leads-the-line uses `envelope_for(contact.classification)` per member; composition/clock/range built per-member from that member's own `describe_contact` facts | Correct attribution — no cross-member leakage found; nearest-member clock/range and per-class composition counts are computed from each member's own facts, not borrowed from another | None |
| body-layer/src/belief/callouts.py:640-682 `tick` | Group candidate re-rendered fresh at speak-time (not scoring-time text), signature-gated against `last_spoken_signature` | Prevents speaking a stale/already-spoken claim; falls through cleanly if belief changed between scoring and speaking | None |
| body-layer/src/belief/contacts.py:reconcile call site | `reconcile(list(self._contacts.values()), now_sim)` — clusters computed strictly from the live per-tick contact set | A stale/removed contact cannot be resurrected into group membership; groups with no matching cluster are dropped, not carried forward | None |
| body-layer/src/belief/groups.py `GroupStore.reconcile` | `self._groups = new_groups` replaces membership wholesale every tick | Bounded — no accumulation beyond the current contact count; consistent with the project's already-accepted bounded-growth pattern (Contacts never shrink but are sortie-bounded) | None (pre-existing pattern, not new) |
| body-layer/src/belief/groups.py `_representative_size_m` | Falls back to `GROUP_REPORTING_UNKNOWN_SIZE_M` (7 m) keyed off `object_model.DEFAULT_OP_CLASS`, never a real DCS size | Cannot reach real object size — fallback triggers exactly when belief holds no resolvable classification | None |
| plans/group-reporting/review.md n>=3 finding | Old flat-metre backstop only guarded the n=2 tautology; unit-width backstop (`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS`) now applies to every pair at every n | Confirmed closed, not merely renamed — `test_2c_transcript_fixture_renders_four_lines_not_seven` was updated (not skipped) and asserts the corrected mixed grouping; `test_two_distant_contacts_do_not_form_a_group` pins the original 500 km n=2 defect as fixed | None |

### Verdict
APPROVED

No security-relevant risk found beyond what the project already treats as an accepted pattern (bounded-but-never-shrinking contact/group state). The core invariant — group membership and spoken disclosure derive strictly from persisted belief (`Contact.position`, `Contact.last_class_raw`, `Contact.classification`), never from ground truth, an `object_id`, or the trace-writer path — holds throughout the diff. Aggregation cannot leak one member's fact onto another (composition, clock/range, and threat-leading are all computed per-member and combined by exact groupby, not estimate). Persistence across ticks recomputes cluster membership from the live contact set every call, so a group cannot resurrect a departed contact.

All findings above are informational/confirmatory; none require a fix. Both findings the review flagged as needing verification (n>=3 backstop closure, per-member fact attribution) were independently traced through the code and tests rather than taken on the plan's word.

### Checks run (isolated snapshot, `feature/group-reporting` @ `b92c7a7`)
- `ruff format --check src tests` — 113 files already formatted
- `ruff check src tests` — All checks passed
- `mypy src` — Success: no issues found in 53 source files
- `pytest tests -q` — 1349 passed, 4 xfailed (matches expected exactly)
