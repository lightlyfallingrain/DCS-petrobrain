### Review Summary

Reviewed the second half of `fix/taking-fire-visible-shooter`, tip
`9cbd2ace508bd65ba971425fa1a18ca536fe737f` (diff against `b39e5b64`, the first half's own
reviewer-approval commit — `6029f184` → `b39e5b64` → `9cbd2ace` is a clean linear chain, confirmed
via `git merge-base --is-ancestor`). Scope: `docs/acceptance/2026-10-20-sortie-feedback.md` F6
follow-up ("someone shooting is important, especially if they are close -> report") — a unit
Petrovich can see *unaided* (admitted without the emitter bypass) that is firing at someone other
than ownship must now be reported as firing, at whatever tier the ordinary admission already
earned, never raised by the emitter fact.

**Verified, not just read:**

- **Mutation-checked the two load-bearing new branches, both caught:**
  - `naked_eye_source.py`'s `elif member_firing_visible == {True}: provenance = ...` — disabled it
    (`elif False and ...`), reran `-k "firing_visible or firing_at_others"`: both
    `test_a_visible_unit_firing_at_others_gets_the_firing_visible_provenance` and the new genuine
    2-member cluster test `test_two_clustered_visible_units_both_firing_at_others_...` failed red,
    as expected. Restored; `git status --porcelain` clean throughout.
  - `speech.py`'s `if event.firing_visible: return _contact_report_text(...)` — disabled it, reran
    `test_route_event_contact_firing_seen_visible_firing_at_others_says_type_and_range`: fails red
    (falls through to `"Something firing, 12 o'clock, far."`, the bypass-needed wording). Restored;
    clean.
- **End-to-end chain, traced and exercised**: `naked_eye_source.py` provenance fold →
  `belief/percept.py::percept_of` (`_VISIBLE_FIRING_PROVENANCE` closed mapping →
  `Percept.firing_visible`) → `belief/contacts.py::record`/`from_percept`
  (`Contact.firing_visible`, written only alongside `is_firing`, same posture as
  `firing_targets_ownship`) → `belief/events.py` (`Event.firing_visible`) →
  `belief/speech.py::_render_lifecycle_text` (`event.targets_ownship` checked first → "Taking
  fire…"; `event.firing_visible` second → ordinary `_contact_report_text` line with
  `event_clause="firing"`; fallback → "Something firing… far."). The committed test
  (`test_route_event_contact_firing_seen_visible_firing_at_others_says_type_and_range`) exercises
  this whole chain and asserts the rendered text starts with the unit type, contains an o'clock
  bearing, ends `", firing."`, and contains neither "far" nor "taking fire" — matches the spec
  exactly.
- **Callout priority, checked by reading rather than assumed**: `callout_priority` keys its
  `CONTACT_FIRING_SEEN` threat band on `event.kind`/`event.targets_ownship` only
  (`_FIRING_THREAT_BAND` vs. `_FIRING_TARGETS_OWNSHIP_THREAT_BAND`), never on which
  `PROVENANCE_EMITTER_FIRING*` value produced the event — so the new `firing_visible` case
  automatically inherits `_FIRING_THREAT_BAND`, which already unconditionally outranks
  `_DEFAULT_THREAT_BAND` (ordinary contact reports), with `range_m` as the within-band
  tie-breaker. The pre-existing, kind-generic `test_callout_priority_firing_not_targeting_still_
  outranks_default_band` already pins this for any non-targeting `CONTACT_FIRING_SEEN`; confirmed
  by reading its body that it constructs the `Event` directly with no dependency on which provenance
  value produced it. No new callouts test was needed, and none was added — correct. This satisfies
  "a close shooter ranks at least as high as an ordinary contact report" with room to spare (it
  ranks strictly higher, same band as the existing bypass-needed firing wording).
- **Dedup/repeat-suppression**: `Contact.firing_visible` rides alongside `is_firing`
  (write-only-when-`is_firing`-is-also-being-set, same posture as `firing_targets_ownship`).
  `ContactStore.tick`'s emission is still gated by `firing_event_kind` (edge-triggered: only fires
  on a not-firing → firing transition) and `EVENT_COOLDOWN_S` (15 s) — both completely unchanged by
  this diff (confirmed via `git diff` — `events.py`'s `firing_event_kind` function body and
  `contacts.py`'s cooldown check are untouched). A stale firing state cannot repeat endlessly; this
  mechanism was already reviewed and approved in the first half and nothing here touches it.
- **Mission-memory semantics, the specific concern flagged in dispatch**: read
  `plans/bl8-mission-memory/plan.md` Decision 2/3 directly rather than trusting the implementer's
  own account. Decision 2's schema table lists `fired_on`'s payload as `{shooter_seq, shooter_ref,
  targets_ownship: bool}` — the boolean field exists specifically so one entry kind can mean either
  case. Decision 3's admission-rule table says `fired_on` writes "a `CONTACT_FIRING_SEEN` event,
  suppressed per shooter" — kind-generic, not conditioned on `targets_ownship`. So `fired_on` was
  always designed to mean "this shooter was observed firing" (at anyone), disambiguated internally
  by its own `targets_ownship` field, not "fired on us" specifically. `_write_fired_on_entries`
  needing no change is therefore correct, not a defect — the implementer's claim holds up against
  the plan's own words, not just against a reading of the current code.
  - One real, intended behaviour change worth naming for the record (not a defect): before this
    fix, a visible firing-at-others unit never set `is_firing=True` (provenance stayed
    `PROVENANCE_VISIBILITY_FILTER_ONLY`), so `fired_on` memory entries were never written for it.
    After this fix, they will be — which is exactly what the schema's `targets_ownship: bool` field
    was provisioned for and is the correct extension of the existing design, not scope creep.
- **Classification never raised**: `classification_raw == "T-72B"` asserted in both the rewritten
  single-member test and the new 2-member cluster test — same hires-tier value whether or not the
  cluster is now also marked firing.
- **Gaze/visibility gates untouched**: `git diff b39e5b64 9cbd2ace --stat` touches only
  `naked_eye_source.py`, `percept.py`, `contacts.py`, `events.py`, `speech.py`, their tests, and
  `implementation.md` — zero changes to `visibility.py`, `gaze.py`, `emitters.py`.
- **Checks, all from inside `body-layer/`** (worktree had no `.venv`, borrowed
  `/mnt/e/DCS-petrobrain/body-layer/.venv/bin/`): `ruff format --check src tests` clean (155
  files), `ruff check src tests` clean, `mypy src` clean (68 files). `pytest -q`: 2247 passed, 1
  failed, 4 xfailed on the first run —
  `test_logger.py::test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop`, the
  documented intermittent flake (a real `ConnectionRefusedError` against a loopback port).  Passed
  alone and on a full rerun. Total (2247 + 1) matches the dispatch's own claimed 2248 passed.
- **No new tunable constants** — the new identifiers are `Final[str]` provenance labels (plain
  attribute docstrings), not `tuning.*` declarations; the tuning-mechanism checklist does not
  apply, same as the first half.
- **Comment pruning**: nothing dated, no verbatim user quote, and no boundary-case comment was
  dropped without a covering replacement or test. The rewritten test
  (`..._gets_the_firing_visible_provenance`) is a justified, well-documented spec flip (the user's
  own words quoted verbatim as the reason), not a weakened test — it still pins the unchanged
  classification tier alongside the new provenance value. The three new cluster-fold tests
  (unanimous-firing-visible, mixed-degrade, targets-ownship-vs-firing-at-others-degrade) close
  exactly the "every fold test is single-member" gap the first half's review flagged as optional,
  and do so for the new branch specifically.

### Required Fixes

- **Seventeen new code-comment/docstring citations across 8 files point at
  `plans/taking-fire-visible-shooter/plan.md`, which does not exist.** This directory holds only
  `debug.md`, `implementation.md`, and `review.md` — there was never an Architect plan for this
  fix (it is a Debugger → Reviewer flow per `docs/acceptance/2026-10-20-sortie-feedback.md` and
  `debug.md`, not an Architect → Implementer one). The first half's own diff (`431b5598` →
  `6029f184`) correctly cites `plans/taking-fire-visible-shooter/debug.md` throughout; the second
  half's new comments invented a `plan.md` reference instead and used it consistently (17 times) —
  not a typo in one spot but the citation convention used for this entire change. A future reader
  who follows any of these citations (including the knowledge-graph corpus, which indexes exactly
  this kind of path reference) finds nothing. Fix: replace every
  `plans/taking-fire-visible-shooter/plan.md` with `plans/taking-fire-visible-shooter/debug.md` in:
  `src/belief/contacts.py`, `src/belief/percept.py`, `src/belief/events.py`, `src/belief/speech.py`,
  `src/perception/naked_eye_source.py`, `tests/test_percept.py`, `tests/test_naked_eye_source.py`,
  `tests/test_speech.py`. Mechanical, no behaviour change — `grep -rl
  "taking-fire-visible-shooter/plan\.md" src/ tests/` finds all eight files directly.

### Optional Refinements

None beyond what the first half's review already logged as optional (the general
`emitter-visibility`/`BL-B72`/`BL-B73` multi-member coverage gap, now partially closed by this
half's own new cluster tests for the `member_firing_visible` branch specifically — the equivalent
gap for the plain `member_emitter_kinds`/`BURNING` branch remains open and pre-existing, not
introduced or worsened here).

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — plus mutation testing on both load-bearing new branches (the cluster-fold provenance
check and the speech-wording check), a direct read of `plans/bl8-mission-memory/plan.md`'s own
Decision 2/3 text (not just the implementer's account of it) to settle the mission-memory-semantics
question, and a full checks run with the one documented flake reproduced and cleared on rerun.
