# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [Wire boundary: type-check not range-check](project_wire_boundary_type_check_not_range_check.md) — logger.py validates isinstance only, not value domain, across the audio-adapter<->body-layer wire; check this class of gap on future passes.
- [Elapsed-time inflation, quadratic dt composition](project_elapsed_time_inflation_quadratic_dt_composition.md) — a hold+inflate recovery pattern's time-to-recover scales ~1/poll_interval, not a fixed constant; test continuous polling, not just a single gap.
- [brain-layer wide bind, no benefit](project_brain_layer_wide_bind_no_benefit.md) — run-brain.sh overrides server.py's loopback default to 0.0.0.0 though both ends are same-box; flagged non-blocking 2026-09-25.
- [BR-1 Stage 2 Ollama trust boundary](project_br1_stage2_ollama_trust_boundary.md) — D10 CONFIRM validator checks full token set not offered vocabulary (fails safe); PICK got this right, CONFIRM didn't — check for this divergence pattern elsewhere.
- [aircraft-layer full audit 2026-09-26](project_aircraft_layer_full_audit_2026_09_26.md) — dostring_in call sites all clean (fixed literals only); recurring gap is unsupervised daemon threads, no REQUIRED FIX this pass.
- [audio-adapter full audit 2026-09-26](project_audio_adapter_full_audit_2026_09_26.md) — genuinely stdlib-only, no shell=True, no logged mic/transcript text; APPROVED, 3 RECOMMENDED (no request-size cap, unguarded Content-Length, mkstemp-reopen TOCTOU).
- [Claude setup audit 2026-09-27](project_claude_setup_audit_2026_09_27.md) — demonstrated deny-list bypasses (`rm -fr`, `git worktree remove -f`, `git -C reset --hard`) and a `..`-traversal gap in agent-memory-path-gate.sh; full report in reviews/claude-setup-security.md.
- [body-layer bounded-growth accepted pattern](project_body_layer_bounded_growth_accepted_pattern.md) — Contacts/optic-policy maps never shrink but are sortie-bounded by design; don't re-flag per-contact dict growth as new exhaustion risk.
- [LOS terrain tolerance accepted omniscience trade](project_los_terrain_tolerance_accepted_omniscience_trade.md) — 12.0 m LOS tolerance is a reviewed, user-approved relaxation; lapse condition is a pop-up-and-shoot airframe (Ka-50/Apache), not a re-flag target as-is.
