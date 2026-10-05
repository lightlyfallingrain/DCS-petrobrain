---
name: body-layer-full-audit-2026-10-05
description: Mode 3 whole-subproject audit of body-layer — what cleared and why, so the same ground is not re-walked; findings in body-layer/research/2026-10-05-security-audit.md
metadata:
  type: project
---

Full audit of `body-layer/src` (53 files, ~25.8k lines) at `main` `19143fa`. Report:
`body-layer/research/2026-10-05-security-audit.md`. Verdict NEEDS FIXES — but every finding is
provenance/availability, none is an exploitable vulnerability, and that is structural rather than
lucky.

**Cleared, with evidence — do not re-investigate these:**

- **body-layer binds no socket.** No `HTTPServer`/`socket`/`bind`/`listen` in `src/`. It is a pure
  client; the unauthenticated-LAN-listener risk lives in the peers, not here.
- **No prompt-injection path from speech or mission text to behaviour or voice.** `brain_client.py:147`
  `_reply_from_dict` is a structural parse over four literal kinds; `brain_reply.validate_brain_reply`
  enforces D10 (PICK id must be one this payload offered; BECAUSE must appear literally in the
  transcript AND the chosen candidate's `why` AND not in any other's; CONFIRM must be in both
  `OFFERED_CONFIRM_VOCABULARY` and `dispatched_command_tokens`; UNABLE in three reasons). **No free
  model text is ever spoken or printed.** The CONFIRM asymmetry from
  [[project_br1_stage2_ollama_trust_boundary]] is closed.
- **Overlay text is not a Lua-injection surface.** `aircraft-layer/src/collector/text_sender.py:94`
  JSON-encodes and truncates. No string splicing into `net.dostring_in`.
- **Degenerate-geometry guards are present throughout** and deliberately documented —
  `motion.py:150`/`:179` guard `range_m <= 0`, `clustering.py:207` returns `inf`, `estimation.py:91`
  maps Box-Muller's uniform onto `(0,1]` to keep `log` off zero, `position_belief.py` wraps every
  `sqrt` in `max(0.0, …)`. I looked for an unguarded divide-by-external-data and found one
  (`optic_policy.py:960`), unreachable in practice.
- **No path traversal.** Every path is a local CLI argument or a repo data file; none is built from
  feed data. Explicitly unlike
  [[project_mission_theatre_field_unsanitized_into_path_and_sqlite_uri]] in world-model.
- **No secrets, no `eval`/`exec`/`pickle`/`subprocess`/`getenv`.**
- **The five broad `except Exception` handlers are argued and four log with `exc_info`.**
  `logger.py:1439-1446` is the model: it exists because the poll runs on a daemon thread and an
  escaping exception would leave the REPL alive and perception dead — the same unsupervised-thread gap
  flagged in [[project_aircraft_layer_full_audit_2026_09_26]], here correctly handled.
- **Bounded growth re-checked and still as accepted** —
  [[project_body_layer_bounded_growth_accepted_pattern]],
  [[project_bl_b23_contact_store_pruning_security_approved]]. Not re-flagged.
- **Naming trap, not a violation:** `enrichment.py:670` `true_bearing_deg` and `optic_policy.py:956`
  `true_bearing` mean *true-north*, not ground truth; both are computed from `Contact.last_position`.

**Findings:** [[project_los_join_key_unit_name_not_total]] (A1),
silent-fallback-has-no-observable (A2, re-rated from the pre-flight low/low now that the flight shows
77 % of admissions on the fallback), [[project_poll_loop_has_no_5hz_spec]] (A3), both LOS gates
fail open and the admission one into a weaker primitive (A4, carries the user decision), unbounded
cross-sortie-appending trace files at ~50 MB/min (A5).

**Second instance of a known class:** `slots["clock"]` is type-checked but not domain-checked at the
wire, and seven `_CLOCK_REPORT_LABELS[clock]` sites index a nine-key dict (5/6/7 absent, the rear
hours) — exactly [[project_wire_boundary_type_check_not_range_check]] in a different field. Cited,
not re-filed.
