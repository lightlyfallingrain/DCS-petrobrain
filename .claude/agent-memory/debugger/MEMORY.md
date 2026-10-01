# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [roadnet resync validation](project_roadnet_resync_validation.md) — container.py's envelope check missed denormalized-float garbage; fixed but resync isn't proven exhaustively safe.
- [world_objects ownship echo](project_worldobjects_ownship_echo.md) — LoGetWorldObjects includes own aircraft; new consumers must call exclude_ownship() or get a phantom contact.
- [sqlite thread affinity](project_sqlite_thread_affinity_bodylayer.md) — world-model sqlite conn is thread-affine; open+use on the same thread, and don't monkeypatch past sample_grid in tests.
- [association gate uncertainty](project_bodylayer_association_gate_uncertainty.md) — spatial gate must budget both incoming AND contact's stored position uncertainty; one-sided budgeting caused a duplicate-contact snowball via the ambiguity rule.
- [REPL thread sqlite reuse](project_repl_thread_sqlite_reuse.md) — logger.py's REPL thread must build its own sqlite3.Connection/EnrichmentContext, never reuse the poll thread's; recurred once after Stage 6's fix (BL-3's `enrichment` field, same bug class).
- [Association gate fragility](project_association_gate_fragility.md) — spatial gate sizing vs. ContactStore ambiguity policy: fixing one duplicate-contact failure mode reopens another.
- [Escalate gate policy changes](feedback_escalate_gate_policy_changes.md) — don't patch association_over_time.py gate sizing or ContactStore ambiguity rule as Debugger; escalate to Architect.
- [Stale backlog already fixed](project_stale_backlog_already_fixed.md) — reproduce against current code first; a milestone Stage fix can leave the standalone backlog entry stale/open.
- [Position-belief fusion pitfalls](project_position_belief_fusion_pitfalls.md) — bearing-only ill-conditioning guards break repeated-same-bearing looks; determinant-floor mis-scaling now fixed, see next entry.
- [Covariance2D determinant floor scale](project_covariance2d_determinant_floor_scale.md) — an absolute determinant floor is wrong for a function inverting matrices at two different scales; use `RATIO * trace**2` instead (scale-invariant under `.inverse()`).
- [Watch-report sounds like live sighting](project_watch_report_sounds_live.md) — CONTACT_RANGE_CROSSED has no gaze/freshness marker; a watched-contact update can sound like a fresh off-gaze sighting, by design.
- [Naked-eye gaze gate is correct](project_naked_eye_gaze_gate_is_correct.md) — verified 2026-09-25: Gate 0 + o'clock legs correctly restrict detection to the commanded cone; not the source of an off-gaze callout.
- [scan_area/watch conflation](project_scan_area_watch_conflation.md) — scan_area used to register a "watch"-level AttentionArea; fixed to "normal". Check `.level` consumers before touching either.
- [test_callouts dwp docstring stale](project_test_callouts_dwp_docstring_stale.md) — `_observation`'s dwp_x/dwp_z do NOT drive Contact.last_position (percept_of strips it); use bearing_deg/range_m.
- [Optic policy interrupted-look retry burn](project_optic_policy_interrupted_look_burns_retry.md) — lower_binoculars (any player command) ends a look early but still marks the target attempted; a stalled-range watched contact never gets another look.
- [Belief-truth log undersamples](project_belief_truth_log_undersamples.md) — dcs-belief-truth.jsonl only logs on a fresh naked-eye ADMITTED re-detection; a contact absent from it can still be very much alive in store.contacts/eyesight_view.
- [Terrain LOS grid error causes permanent miss](project_terrain_los_grid_error_permanent_miss.md) — SRTM elevation grid (1000m, syria-full) can overestimate terrain at a unit's own (x,z), burying it under the model permanently; +11.5m (M7's own measured stddev) already flips a close attack-pass geometry to false-blocked. Escalated to Architect, not patched.
- [Group disclosure range-retrigger](project_group_disclosure_range_retrigger.md) — a group's spoken line re-triggers on range/clock drift alone since the dedup compared the full rendered text; fixed via a separate content_signature that strips position out.
- [Groups cohesion uncertainty-budget reverted](project_groups_cohesion_uncertainty_budget_reverted.md) — budgeting Contact.position.radius_m() into belief.groups' pairwise test over-merges (one look is ~300m RMS even at 500m); the real "better closer" symptom needed no mechanism fix here.
- [Belief-truth log undersamples — update](project_belief_truth_log_undersamples.md) — also logs `kind:"speech"` rows per spoken line, and concatenates many separate logger runs (t_sim resets) — split by reset before analysing.
