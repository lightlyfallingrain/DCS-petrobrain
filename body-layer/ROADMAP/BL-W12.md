# BL-W12 — Group cohesion redesign

- [~] **Group cohesion redesign: size-relative/kind-coherence cohesion, infantry `EAGER` release,
  and the delta taxonomy. Merged to `main` 2026-10-01 as `ff7934e` (branch was
  `fix/group-undermerging` @ `6d6ea3f`); flight outstanding. Reviewer (round 2), Security
  (deep analysis), and Performance (APPROVED — MONITOR, `BL-B23` filed) all passed; DoD's
  mechanical gate (format/lint/type/test) passed 2026-10-01 at this tip (1367 passed/4 xfailed,
  `ruff format`/`ruff check`/`mypy --strict` clean). Not merged as of this entry — pending the
  user's acceptance call, per the live-acceptance-debt entry below (which the project's own
  "never block a merge on live acceptance the user cannot currently perform" posture means the
  user may choose to merge ahead of the flight rather than wait, tracking the flight as debt).** #status/in-progress #needs-flight
  `plans/
  group-cohesion-redesign/plan.md`, built on `plans/group-undermerging/debug.md`'s 2026-10-01
  sortie debug (the re-trigger fix already merged) and three Explore rounds the same day. **Stage
  1** — `belief.groups.CohesionBackstop` (`STRICT`/`EAGER`), `_OP_CLASS_COHESION_BACKSTOP` makes
  `OP_INFANTRY` `EAGER` (no backstop at all for a pair where either member is infantry) — user
  direction: *"Ok to merge infantry too eagerly."* **Stage 2** — `perception.object_model.
  ObjectTypeProfile.installation_component: bool`, `True` only for `"s-125"`/`"kub "` (a real
  finding mid-revision: `op_class="OP_SRSAM"` alone would have conflated the genuine fixed S-125
  site with four single-vehicle systems — Osa/Strela-10/Strela-1/Tor — that must stay excluded);
  `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M = 500.0` (down from a discredited 1000 m guess,
  grounded in `body-layer/research/2026-10-01-sam-site-geometry.md`'s real S-75/S-125 doctrine).
  **Stage 3** — the delta taxonomy: `Group` gains `last_spoken_member_contact_ids`/`.
  last_spoken_leading_contact_id`/`.last_spoken_differentiated`; `belief.speech.render_group_
  disclosure` now decides full/delta/silent per tick (leader change -> a short "Now leading: X."
  delta, never a full restatement; first differentiation -> full, once; a new or repeat-air-
  defence arrival -> a delta naming just the new member(s); a repeat non-air-defence arrival or a
  departure with no new arrivals -> silent). **A real design gap found and fixed while wiring
  this in**: `belief.crew_console.CrewConsole._handle_report`'s pull-based "report" command used
  to call `render_group_disclosure` directly and relied on it always returning the full
  composition (its own comment: "a report is pull-based, so it always speaks fresh"); the new
  taxonomy breaks that assumption (a post-taxonomy call can return a delta or `None`), so a new
  `render_group_full_disclosure` (taxonomy-free, always full) was added for the pull path, and
  `_handle_report` now calls that instead — confirmed against the delta taxonomy's own worked
  "report" roll-up example, which always names the full current roster.

  **Verified against real sortie data, not only hand-built fixtures**: the real S-300 battery's
  ground-truth emplacement geometry (`/Users/sg/dcs-belief-truth.jsonl`, 2026-10-01 trace,
  `true_x`/`true_z` for object ids 16785152/16784640/16784896/16785408) forms a 3-member cluster
  under the settled `installation_component` assignment (S-300/`OP_LRSAM` is explicitly NOT
  flagged — only `"s-125"`/`"kub "` are), with the fourth component ("64H6E sr") isolated —
  `tests/test_groups.py::test_real_s300_site_ground_truth_geometry_forms_a_three_member_cluster`.
  **This does not match the plan's own Stage 2 acceptance wording** ("confirmed to form one
  four-member group") — that wording is stale, inherited from before this revision's own §1
  finding narrowed the installation flag off `OP_LRSAM`; flagged in the implementation report
  rather than silently worked around.

  **`tests/test_callouts.py::test_2c_transcript_fixture_renders_four_lines_not_seven` rewritten**
  (AGENTS.md escalation, user-confirmed) — and the actual result is wider than "the infantry pair
  now merges": single-link chaining through an infantry member (no backstop at all) bridges the
  BTR-70 and truck into the *same* five-member group even though their own direct pairwise gap
  does not clear the ordinary backstop, a real and now-pinned consequence of the `EAGER` release
  (`tests/test_groups.py::test_infantry_eager_policy_bridges_a_non_infantry_pair_that_would_not_
  merge_alone`).

  1366 passed/4 xfailed (up from the branch's 1351/4 baseline), `ruff format`/`ruff check`/`mypy
  --strict` clean; two further rounds (indefinite-article removal, undifferentiated-member
  aggregation) brought this to 1367/4 at the merged tip. **Milestone completion question**:
  unblocks `BL-B11` (threat-based report prioritisation) once cohesion correctly reflects
  installation structure, per the plan's own "Second-Order Effect" section — otherwise does not
  change what is next, pending the first sortie to exercise the installation cap/delta taxonomy
  for real (tracked below).

  **Acceptance boundary, stated up front rather than left implicit**: every check above is a
  fixture/unit-test pass. It cannot observe whether the *right* contacts merge in a real,
  continuously-moving scene, whether the 500 m installation cap or the `AIR_DEFENSE_OP_CLASSES`
  membership guess holds up against a real Cold War-era mission's unit placement, or whether the
  delta taxonomy's rendered lines land correctly *by ear*, in the cockpit, under task load — the
  F10 vocabulary precedent (`Scan` driving the wrong sight; `Cancel Task` speaking a raw id) is
  the standing reminder that a fixture pass and a flight pass are different claims.


**OPEN** — this entry's own text contradicts itself about merge status: its lead sentence says "Merged to main 2026-10-01 as `ff7934e`", and later in the same paragraph says "**Not merged as of this entry** — pending the user's acceptance call". Both sentences are reproduced verbatim above, unedited, per this conversion's instruction not to silently resolve a disagreement found in the source. Mechanically checkable and not actually a judgement call: `git merge-base --is-ancestor ff7934e HEAD` on this repo confirms `ff7934e` **is** merged into the current history, so "Not merged as of this entry" is stale text left over from before the merge landed, not a live uncertainty. Recorded here rather than corrected in place, per the conversion task's own instruction; a later edit may remove the stale sentence once someone other than this conversion makes that call.

**Live-acceptance debt entry, folded in from the roadmap's former debt list (overlaps with the above):**

- [ ] **Group cohesion redesign — merged to `main` 2026-10-01 (`ff7934e`), still unflown.**
  DoD's mechanical gate passed at `6d6ea3f`; the merge followed on the user's instruction, with
  live acceptance tracked as debt rather than blocking it. Reviewer (round 2),
  Security, and Performance (MONITOR, `BL-B23` filed — see Backlog) all approved; 1367 passed/4
  xfailed, `ruff`/`mypy --strict` clean at the tip. Card: `docs/acceptance/
  2026-10-01-group-cohesion-sortie.md` (and its artifact). What the flight has to settle and
  static review cannot: whether the 500 m installation cap and the `AIR_DEFENSE_OP_CLASSES`
  membership guess (both one-source-of-evidence per the plan's own "Risks & Unknowns") hold up
  against real unit placement; whether the delta taxonomy's six branches land correctly by ear
  (new class speaks, repeat non-air-defence member silent, repeat air-defence member always
  speaks, leader change speaks a short delta not a restatement, pure departure silent); and
  whether the two user-approved but still-surprising behaviours (infantry `EAGER` bridging a
  non-infantry pair into one group; S-300 not flagged `installation_component` so its own
  components do not single-merge) read as intended in the cockpit rather than as noise or a
  miss. Clear this entry only once a real sortie exercises it, and say which one.

