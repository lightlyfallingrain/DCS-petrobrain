## Security Deep Analysis: taking-fire-visible-shooter

Reviewed `fix/taking-fire-visible-shooter` tip `59eea0854589bd0a340a2f8a07a2bf9cfde83e3b`
(the whole branch, `git diff 431b5598..59eea085`) against
`docs/acceptance/2026-10-20-sortie-feedback.md` F6/F6-follow-up and
`plans/taking-fire-visible-shooter/{debug,implementation,review,review-2}.md`. Batch = both
halves of the fix plus the review-2 citation-cleanup commit.

### Dependency Status
No dependency change. Stdlib-only diff inside `body-layer/`, same posture as the rest of the
subproject.

### Scope of the diff
Two behavioural commits (`6029f184`, `9cbd2ace`) plus one purely mechanical commit (`59eea085`,
confirmed by `git show --stat`/content: every hunk is `plans/taking-fire-visible-shooter/plan.md`
-> `.../debug.md` in comments and docstrings only, zero logic lines touched). Touched source:
`perception/naked_eye_source.py`, `belief/percept.py`, `belief/contacts.py`, `belief/events.py`,
`belief/speech.py`, their tests, and five agent-memory files (debugger/reviewer/implementer, not
this role's). **`perception/visibility.py`, `perception/emitters.py` and `perception/gaze.py` are
untouched** (`git diff --stat` confirms zero changes to any of them) — gaze gating, cockpit mask,
optic FOV, terrain LOS, the tier-clamp bypass, and the collector-wire parsing in `emitters.py` are
all out of scope for this diff and were reviewed previously (Stage A/B, see agent memory
`project_emitter_visibility_stage_a_approved.md` / `_stage_b_approved.md`).

### No-omniscience: verified mechanically, not just read
The dispatch's core question — can this ever add "this unit is firing" to a unit Petrobrain
couldn't perceive — is answered by where the two new/changed dicts are built in
`NakedEyePerceptionSource.poll`:

```python
targets_ownship_by_object_id: dict[int, bool] = {}
for candidate, _result in visible:           # <- only already-gate-admitted candidates
    ...
firing_by_object_id: dict[int, bool] = {}
for candidate, _result in visible:           # <- same source list
    ...
```

Both loop over `visible` only — the list `check_visibility` already filtered through gaze,
cockpit mask, optic FOV and terrain LOS (gates this diff does not touch), with range/size/forest
either passed unaided or passed via the emitter bypass. There is no code path in this diff that
reads `emitter_by_object_id`/`firing_active` for a candidate outside `visible`. So the fix is
exactly what the dispatch asked for: it can only ever add the firing/targets-ownship fact to a
unit already admitted by perception — it does not open a second, bypass-only admission channel.

Classification is likewise never raised by the emitter fact: `_build_observation`'s provenance
fold produces one of the three `PROVENANCE_EMITTER_FIRING*` strings or
`PROVENANCE_VISIBILITY_FILTER_ONLY`; `Cluster.classification_raw`/tier are computed earlier and
untouched by this fold. Verified empirically, not just read: `classification_raw == "T-72B"` is
asserted in `test_a_visible_unit_firing_at_ownship_sets_the_targets_ownship_provenance` and the
new firing-at-others tests, pinning the exact hires tier rather than `DEFAULT_OP_CLASS`.

The bypass-needed, presence-only case (`PROVENANCE_EMITTER_FIRING`, "something firing... far") is
unchanged and still reserved for candidates where `emitter_kind_by_object_id` actually fired — the
new `member_firing_visible` branch explicitly excludes that population
(`emitter_kind_by_object_id.get(member.object_id) is None`), so the two "visible" and "bypass
needed" wordings remain mutually exclusive by construction, matching the project's "achieved_tier
is correctly gated on bypass-fired; don't fix it by analogy" invariant
(`.claude/agent-memory/debugger/project_emitter_kind_bypass_conflation.md`).

### Wire-field input handling (`/firing/latest` → `targets_ownship`, `emitter.kind`)
`perception/emitters.py`'s `firing_emitters` (the function that parses the collector's
`GET /firing/latest` response into `Emitter` objects) is **untouched by this diff** — confirmed by
`git diff --stat`. Its validation, read directly (lines ~200-225), already handles every case the
dispatch asked to check:

- `name`/`object_id` type-checked (`isinstance(name, str)`, `isinstance(object_id, int)`) before
  use, non-conforming entries dropped.
- Non-unique `unit_name` across `raw_objects` drops to unresolved (`name_counts[name] > 1`),
  fail-closed on ambiguous join.
- `entry` type-checked as a `dict` before any key access.
- `entry.get("kind")` compared against the exact expected string constant; anything else is
  dropped, not coerced.
- `targets_ownship = entry.get("targets_ownship")` is read with `.get` (no `KeyError` on a
  missing key) and coerced via `bool(targets_ownship) if targets_ownship else False` — a missing
  key, `None`, `0`, `""`, or any other falsy value all resolve to `False`; a non-bool truthy value
  (e.g. the string `"true"`) coerces to `True` via `bool()`, which cannot raise. No crash on
  malformed, missing, or non-bool wire data; no unvalidated value reaches a dict index or a system
  call.

This diff's own two new per-object-id dicts (`targets_ownship_by_object_id`,
`firing_by_object_id`) read `Emitter.targets_ownship`/`Emitter.kind` — both already-validated,
already-typed fields of the `Emitter` dataclass produced by the function above, not raw wire
dicts — so no new unvalidated-input surface is introduced. `emitter.kind == EmitterKind.FIRING`
compares against a `str`-backed `Enum`, which cannot raise.

**Unknown unit names**: a `firing_active` entry whose name matches no `raw_objects` candidate (or
matches a non-unique one) is simply never looked up (`emitter_by_object_id.get(...)` returns
`None`, both new dicts default that candidate to `False`/absent) — fails closed, not an exception,
not a crash. Consistent with the pre-existing `emitters.py` contract this diff relies on without
changing.

### New failure modes in the poll loop
None found. Every new code path in `naked_eye_source.py`'s fold is pure-functional set/dict
construction over already-typed data (`visible`, `emitter_by_object_id`, both pre-existing),
reading with `.get(key, False)`/`.get(key)` throughout — no new dict `[]` indexing, no new
exception-raising operation, no new I/O, no new thread/loop state. The downstream
`belief/` fields (`Percept.firing_visible`, `Contact.firing_visible`, `Event.firing_visible`) are
plain `bool = False`-defaulted dataclass fields populated via the same closed-mapping
(`frozenset` membership) pattern `_TARGETS_OWNSHIP_PROVENANCE` already established and this role
previously reviewed as the correct no-omniscience shape (`project_emitter_visibility_stage_a_
approved.md`) — a `dict.get`/frozenset-membership read that cannot raise and cannot be bypassed
by an unregistered provenance string defaulting to `True`.

### Independent verification run (not just reading the reviewer's account)
- `pytest -q tests/test_naked_eye_source.py tests/test_percept.py tests/test_speech.py`: 259
  passed.
- `ruff check src tests`: clean.
- `mypy src` (from inside `body-layer/`, `PYTHONPATH=src:../world-model/src`): clean, 68 files.
- Read the citation-fix commit (`59eea085`) content directly: every changed line is a
  `plan.md`→`debug.md` string swap in a comment/docstring/test-docstring; confirmed zero logic
  diff via `git show 59eea085` line-by-line.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `naked_eye_source.py` (`targets_ownship_by_object_id`/`firing_by_object_id` construction, `poll`) | Reads collector-derived `Emitter` fact unconditionally for gate-admitted candidates | Correct — scoped to `visible` only, cannot leak to an unperceived unit; matches the no-omniscience invariant | None |
| `naked_eye_source.py` (`_build_observation` provenance fold) | New priority-ordered unanimity checks (`member_targets_ownship`, `member_firing_visible`) | Mutually exclusive by construction (condition (c) of `member_firing_visible` excludes the targets-ownship case); classification/tier untouched | None |
| `perception/emitters.py::firing_emitters` | Wire-field validation (`isinstance`, dict-type check, `.get` + `bool()` coercion) | Pre-existing, unchanged by this diff, already fail-closed on malformed/missing/non-bool/unknown-name input | None (out of scope for this diff, previously reviewed) |
| `belief/percept.py`/`contacts.py`/`events.py` (`firing_visible` field) | New `bool = False` fields via closed-mapping (`_VISIBLE_FIRING_PROVENANCE` frozenset) | Same reviewed-safe shape as `_TARGETS_OWNSHIP_PROVENANCE`; no passthrough of a free-form string | None |
| `belief/speech.py` (`event.firing_visible` branch) | Reuses pre-existing `_contact_report_text` with `event_clause="firing"` | No new rendering logic; reuses an already-reviewed, id-less/coalition-less formatter | None |

### Verdict
APPROVED

### Required Fixes (if any)
None.

### Notes carried forward (not new findings, not blocking)
- The Stage-B open item (a literal `;`/`:` in a DCS unit name corrupting the semicolon-delimited
  wire format) is pre-existing in `aircraft-layer`'s firing-event sender, untouched by this diff,
  and already tracked in agent memory (`project_emitter_visibility_stage_b_approved.md`) — not
  re-filed here since it is unchanged and out of this batch's scope.
- Reviewer's own optional refinement (committed multi-member-cluster fold tests) was substantially
  closed by this branch's own second-half tests
  (`test_two_clustered_visible_units_both_firing_at_others_...`,
  `test_a_mixed_firing_cluster_degrades_to_ordinary_provenance`,
  `test_a_cluster_mixing_targets_ownship_and_firing_at_others_degrades`) — no security finding, a
  quality note already owned by Reviewer.
