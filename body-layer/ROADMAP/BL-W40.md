# BL-W40 — Landmark words, not proper names, in spoken callouts

- [x] **Spoken callouts say "near a village" / "in the town" / "near a road" / "near a river"
  instead of a settlement/water body's proper name plus a bracketed distance figure.**
  #status/done #needs-flight **Merged to `main` 2026-10-20 (`83bf80bc`)**, `feature/landmark-words-no-names`.

  **User, verbatim** (`docs/acceptance/2026-10-20-sortie-feedback.md`, F7): *"I get call outs that
  refer to settlement by it's name. While correct, I notice that's not very usefull actually.
  Instead we could just replace names (that are often foreign and tell me nothing and take time to
  say) with 'village' or 'city'."* Settled the same day: village/town are enough (city folds into
  town), drop the bracketed distance entirely rather than round it, mission memory keeps full
  names, and the same name-free treatment applies to every landmark kind speech can render (road,
  river/water), not settlements alone.

  **What shipped** (`plans/landmark-words-no-names/plan.md`, `feature/landmark-words-no-names`):
  - World-model: `SettlementInfo` gains `area_m2: float | None`, surfaced from a tag
    `_preferred_settlement` already read two functions above — additive, read-only.
  - `belief/enrichment.py`: `_settlement_size_word(subtype, area_m2)` picks "village"/"town"
    (`subtype` for the three named OSM place values, `area_m2` against a new tunable
    `BUILT_UP_VILLAGE_MAX_AREA_M2` — 1 km², `status="judgement"` — for `"built_up"`/unrecognised
    subtypes, defaulting to "village" with no size evidence at all). `SemanticFact.feature_id`
    carries the generic word as an unconditional middle segment for
    `settlement`/`inside_settlement`/`water` facts (`f"settlement:{size_word}:{name}"`, etc.) —
    `SemanticFact.text`/`confidence`/`provenance` themselves are untouched, so the debug console,
    mission memory, and the brain-facing `TOOL_SET` surface all keep the full name by construction,
    not by a separate carve-out.
  - `belief/speech.py`: `_landmark_speech_text` replaces the deleted `_round_enrichment_fragment` —
    switches on `feature_id`'s `kind:` segment to speak the generic word and drop the distance
    figure entirely (never rounds it), at both call sites that render a semantic fact
    (`render_engage_readback`, `_contact_report_text`).

  **Key decision:** the generic word is computed unconditionally now, not only in the pre-existing
  name-absent fallback branches — this is what makes the feature-wide (not just-unnamed-places)
  behaviour possible without a second code path.

  **Review found three real coverage gaps** (not production defects): water and
  `inside_settlement` facts' `feature_id` wiring, and `render_engage_readback`'s semantic branch,
  each had only hand-built-fixture tests that would pass under a mutated producer. Closed with
  end-to-end tests derived from the real `semantic_facts_for` producer, each verified by actual
  mutation (introduce the bug, confirm red, revert, checksum). See
  `notes/fixture-management-and-test-infrastructure.md` and `notes/testing-and-provenance.md` for
  the generalised lessons.

  **Gates:** Security plan review and deep analysis both APPROVED (plan review run retroactively at
  DoD stage — the sequence skipped it the first time around; reconstructing it against the plan as
  written changed no verdict). Performance APPROVED — O(1) string work on an already-cached path, no
  new query. DoD mechanical checks pass in both touched subprojects (body-layer, world-model) at
  tip `34b9f659`, plus the retroactive security-plan-review commit layered on top.

  **`#needs-flight`, not fully closed.** Everything above is fixture-verified; what no fixture
  reaches is whether the wording actually reads right at the controls — "near a village"/"in the
  town" cadence against real terrain, and whether dropping the distance figure (rather than
  rounding it, as speech used to) loses something a pilot actually wanted. Clear this tag once
  flown; if the sortie finds the wording wrong, it is a speech-side wording tweak, not a design
  reopen — the producer/consumer plumbing underneath is the stable part.

  **Second-order effect: none identified beyond the brain-facing/debug boundary already drawn** —
  `describe_our_position`/`TOOL_SET`/`belief.console` keep full names by design; if free-text brain
  replies ever start reading tool results aloud, that boundary needs revisiting there, not here
  (plan's own "Second-order effect" section, confirmed independently by DoD and both Security
  passes).
