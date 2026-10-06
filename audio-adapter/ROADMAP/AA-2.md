# AA-2 — Hardening: per-source `--poll-hz` default + `Content-Length` guard

- [x] **Hardening: per-source `--poll-hz` default + `Content-Length` guard — done 2026-09-26, merged `1a8795d`** #status/done #needs-flight
(`fix/audio-adapter-review-findings`, no `plan.md` — scoped directly from the 2026-09-26
whole-subproject performance and security reviews, `docs/reviews/`). `--ptt dcs` now defaults to
30 Hz (`ptt_source.DEFAULT_DCS_POLL_HZ`, which the perf review found defined but wired to
nothing) instead of the undifferentiated 60 Hz; `/speak` and `/transcribe` reject a
missing/non-numeric/negative `Content-Length` with a clean 400 before any body read.

Two review rounds, and the second one is the part worth remembering: round 1's negative-length
regression tests passed against the pre-fix code too, because a pre-existing
`read(length) if length > 0 else b""` already prevented the hang the security audit claimed —
so they proved nothing. Round 2 asserted the specific rejection-path error message instead, and
the wrong claim was corrected in place in `docs/reviews/security-audit-audio-adapter.md` rather
than deleted. The real defect was the unhandled `ValueError` on a non-numeric value.

**Live-acceptance debt:** the poll-rate halving has no in-cockpit observable and no CPU or
frame-time measurement was ever taken, so nothing was gated on a sortie. Optional confirmation
whenever the collector next runs with `--debug`: count `GET /ptt/state` lines over a fixed
window, expect ~30/s rather than ~60/s.
