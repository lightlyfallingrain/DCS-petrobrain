## Security Deep Analysis: redundant-group-disclosure

### Dependency Status
No dependency change (`body-layer/pyproject.toml` untouched in this diff).

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/callouts.py` `_is_merge_echo_of_earlier_contact` | Shared predicate, extracted verbatim from the prior flood fix | Byte-identical logic to the already-approved `_render_event` branch; factoring removes drift risk rather than introducing it | None |
| `body-layer/src/belief/callouts.py` `CalloutScheduler._already_reported_member_ids` | Reads `self._last_spoken_signature` (what was actually said) + `store.contacts` (believed state) | No ground truth read; "already reported" is a fact about speech history, not about what exists. Satisfies no-omniscience invariant | None |
| `body-layer/src/belief/speech.py` `render_group_disclosure` branch 1 | New partial/full/none split on first disclosure | Caller-supplied `already_reported_contact_ids`; `None` default preserves old always-full-disclosure behaviour for any caller that doesn't opt in | None |
| Composition of flood-fix + this fix (point 2 in the brief) | Chain risk: A suppresses B, B "reported", group {B,C} could go silent on C | Verified directly: `unreported_ids = current_member_ids - already_reported_now` is computed per-member, so C (never spoken, never merge-echoed) is never in `already_reported_now` and is evaluated independently against the worth-announcing filter. Full-silence only occurs when *every* member, individually, satisfies the reported predicate. Test `test_group_of_already_reported_and_merge_echo_suppressed_members_is_silent` and the 2C fixture change both confirm empirically (C still speaks in the 2C fixture; here A and C are *both* independently reported so correct full silence) | None — no cycle/starvation path found |
| Per-tick cost | `_already_reported_member_ids` called once per group-disclosure candidate (two call sites: already-persisted groups and newly-reconciled candidates), each member scanned against `store.contacts` via `_is_merge_echo_of_earlier_contact` | O(members × store size) per *candidate*, not per tick — identical shape to the flood fix's own per-event `_render_event` check, which Security already priced as O(n) per event. No set persists across ticks; `reported` is a local `set[str]` rebuilt from scratch each call | None |

### Verification run (from `body-layer/`, fresh venv built from `pyproject.toml`, no new deps needed)
- `ruff format --check src tests` — pass (114 files)
- `ruff check src tests` — pass
- `mypy src` — Success, no issues, 53 source files
- `pytest tests -q` — **1414 passed, 4 xfailed** (matches expected delta over `main`'s 1409/4)

### Verdict
APPROVED

No security-relevant change beyond what the brief already anticipated and the test suite now
pins: the new mechanism reads only speech history and believed contact state (no omniscience),
composes correctly with the merge-echo suppression (no silencing cycle — verified by a test built
on the exact fixture chain), carries no new dependency, and runs per-candidate rather than per-tick
(same cost shape already priced for the flood fix). The one genuine new risk this class of fix
creates — fully silencing a group that still has something unreported to say — is the thing the
partial-disclosure branch exists to prevent, and it is independently tested on live-derived
(sortie-1004-pattern) fixture data.
