### Implementation Summary

Implemented Stages 1-3 of `plans/group-reporting/plan.md` on top of `main` at `d1f5f89`. Stage 4
(CalloutScheduler integration / retiring `group_candidates`) and Stage 5 (common fate) are out of
scope per the dispatch and were not started.

Four commits, one per logical unit (mechanism/calibration separated per project convention, and
per the plan's own "commit per stage" instruction):

1. Stage 2 core: `belief/groups.py` (new), `ContactStore.tick`'s eighth block, `tools.py`/
   `console.py` exposure.
2. Stage 1: `CalloutScheduler`'s disclosure-signature gate.
3. Stage 3: `belief.speech.render_group_disclosure`.
4. A follow-up test-only commit adding direct `test_contacts.py` coverage of the tick wiring
   (the plan's own test-impact list named that file for this change; the first commit covered it
   indirectly via `test_tools.py`/`test_groups.py` but not directly).

### Files Changed

- `body-layer/src/belief/groups.py` (new) — `Group`, `GroupStore`: relative-gap cohesion
  (union-find over fused `Contact.position`, threshold = `GROUP_PROXIMITY_GAP_RATIO` (3.0) times
  the local median nearest-neighbour gap), `GROUP_MIN_MEMBERS` (3), majority-member-overlap
  split/merge reconciliation. Both constants are stated assumptions with no data behind them,
  documented as such in the module docstring and in comments at their declarations.
- `body-layer/src/belief/contacts.py` — `ContactStore` gains a `GroupStore` field, `groups`/
  `group_for_contact`/`mark_group_spoken` delegating accessors, and `tick()` gains an eighth,
  cross-contact block (after the seven per-contact blocks, so a group's future rendering sees
  each member's already-current attention/engagement state) that calls `GroupStore.reconcile`
  once per `tick()` call.
- `body-layer/src/belief/tools.py` — `_group_facts` (new, private): `{group_id,
  member_contact_ids, member_count}`, absent-not-null when a contact belongs to no group. Wired
  into `_contact_facts` as `facts["group"]`.
- `body-layer/src/belief/console.py` — `_SHOW_FACT_KEYS` gains `"group"`, right after
  `"cardinality"`.
- `body-layer/src/belief/callouts.py` — `CalloutScheduler` gains `_last_spoken_signature: dict[str,
  str]` and a check in `_render_group`'s singleton branch: for `CONTACT_DETECTED`/
  `CONTACT_REACQUIRED`, render the candidate via `render_contact_report` first; if it matches the
  last text actually spoken for that contact, return `None` (suppressed, never acknowledged, same
  "lost, not deferred" treatment already given to an aged-out or vanished candidate) instead of
  calling `route_event` (which would otherwise auto-acknowledge).
- `body-layer/src/belief/speech.py` — `render_group_disclosure(store, group, now_sim,
  enrichment)`, plus a private `_group_composition_clause` helper. See "Notable Discoveries" below
  for the naming decision.
- `body-layer/tests/test_groups.py` (new), plus edits to `test_contacts.py`, `test_tools.py`,
  `test_console.py`, `test_callouts.py`, `test_crew_console.py`, `test_speech.py`.
- `body-layer/ROADMAP.md` — milestone entry (`[~]`, in progress — not yet reviewed/DoD'd, not
  audible).

### Tests Added

- `test_groups.py` (11 tests) — cohesion (below-floor, tight cluster with an outlier, sparse
  desert wide gap, 180-degree bearing span), persistence across an unchanged reconciliation,
  split (majority keeps the id, minority drops below the floor and disappears), merge (higher-
  overlap survivor), disclosure-signature carry-over on `mark_spoken`, and the two constants'
  values.
- `test_contacts.py` — `tick()` reconciles a cohering trio into one group; idempotent at the same
  `now_sim`.
- `test_tools.py` — `"group"` fact absent for an ungrouped contact; present with the right
  membership for a cohering trio.
- `test_console.py` — `show <id>` includes a `group:` line for a grouped contact.
- `test_callouts.py` — a reacquisition with an unchanged render is suppressed; a reacquisition
  with a genuinely refined classification still speaks (via the competing
  `CONTACT_CLASSIFICATION_CHANGED` event, and the still-live `CONTACT_REACQUIRED` once occupancy
  clears); a brand-new contact's first detection is never suppressed (empty signature dict).
- `test_speech.py` (9 tests) — `_group_composition_clause`'s singular-article and exact-count
  behaviour directly; `render_group_disclosure`'s four ladder rows (bare "Group.", composition-led,
  threat-led, watched trailing clause), clock/range from the nearest member, and the
  stale-membership `None` guard.

### Checks

(body-layer/ — the only subproject touched)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (run as `cd body-layer && .venv/bin/python -m mypy src` — see note below on the venv
  path used): pass, 53 source files, no issues
- `pytest tests -q`: **1340 passed, 4 xfailed** (baseline on `d1f5f89` was 1313 passed/4 xfailed;
  +27 net new tests, 0 regressions)

### Notable Discoveries

- **The plan's own prose names two different functions `render_group_report`.** One already
  existed (`belief.speech.render_group_report(facts_list) -> OutgoingSpeech`, imported into
  `belief.callouts` for the pre-existing speech-time, report-space aggregation the plan explicitly
  does *not* retire in this pass — that is Stage 4). Implemented Stage 3's new function as
  `render_group_disclosure` instead of reusing the name, documented at the top of its own
  docstring. This is a naming collision the plan didn't anticipate, not a design disagreement —
  flagging per the "stop and report" instruction rather than silently picking a name with no note.
- **Stage 3 is not wired into any live speech path.** The plan's Implementation Plan section
  explicitly scopes `CalloutScheduler` integration to Stage 4 ("needs the `Event` shape decision
  below... do this as its own short design pass at Stage 4, not assumed now"), which this dispatch
  was told is out of scope. But the same section also describes Stage 3 as "the first stage that
  changes what the pilot hears." Those two statements are in tension: as delivered, `render_group_
  disclosure` is fully built and tested, but nothing calls it during a live poll loop, so the
  disclosure ladder is not yet audible in a running session. I did not improvise a partial Stage 4
  wiring (e.g. into `CrewConsole._handle_report`) to resolve this tension, since the plan's own
  Risks section flags the `Event`/group-id shape as a real open design question that could affect
  how any wiring should work, and inventing an interim wiring risks being redone once that design
  lands. Flagging this rather than silently reaching into Stage 4's scope, or silently declaring
  the "hear the real thing" ask satisfied when it is not yet.
- **The composition clause always speaks exact per-class member counts**, never a
  `_cardinality_phrase`-style hedge, once classification has differentiated past `presence`/
  `unknown` — this diverges from the plan's own worked-example table (which shows a bare,
  count-free "Tanks and trucks" at 3 km, with numbers only appearing at 1 km). The reasoning: a
  group's per-class count is a literal groupby over already-identified `Contact`s with real
  identity, not an estimate of how many objects one unresolved percept/cluster stands for — the
  cardinality-hedging rule exists to prevent manufacturing precision that isn't there, and none of
  that applies here, so hedging it anyway would be *less* honest, not more. Documented in
  `_group_composition_clause`'s own docstring. This is a deliberate divergence from the
  illustrative table, not from any of the plan's actually-binding decisions (mixed-precision
  register, threat-leads-the-line, and "never pair an exact count with a vague class" are all
  preserved).
- **One existing test's expected behaviour changed, and is the exact case Stage 1 targets**:
  `test_crew_console.py::test_scripted_crew_session_reproduces_the_first_useful_success_criterion`
  previously asserted that a `CONTACT_REACQUIRED` at the same believed position/classification
  re-speaks the identical "BMP-2." line already spoken for that contact's original detection. That
  is now suppressed by Stage 1's disclosure-signature gate, so the assertion was updated to expect
  silence there, with a comment explaining why. No other existing test's expected string changed.
- **`.venv` did not exist in this worktree** (agent worktrees are separate checkouts; venvs are
  gitignored per-checkout). Ran every check via the main checkout's `body-layer/.venv/bin/python -m
  <tool>` with `cwd` inside this worktree's `body-layer/` directory — confirmed this resolves
  `mypy_path`/`pytest`'s `pythonpath` correctly (both are relative to the invoking process's CWD,
  not the venv's own location) before relying on it for every subsequent check.
