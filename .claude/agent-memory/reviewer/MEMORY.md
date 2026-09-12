# Memory Index

- [Rerun mypy, don't trust the log](feedback_rerun_mypy_dont_trust_log.md) — a dependency shipping py.typed stubs post-implementation can make a stale `type:ignore` fail strict mypy; always rerun checks yourself.
- [Verify mypy CWD claims by reproduction](feedback_verify_mypy_cwd_claims_by_reproduction.md) — rerunning fixed code from both cwds looks identical; reintroduce the bug to actually test a CWD-sensitivity claim.
- [MI-3 reviewed/approved](project_mi3_reviewed_approved.md) — Tagged[T] pattern precedent; bar for reviewing MI-4's first INFERENCE/ASSUMPTION-producing code.
- [MI-4 reviewed, minor fixes](project_mi4_reviewed_minor_fixes.md) — Ollama auto-pull needs a fail-closed guard; implementer's decision log misquoted the plan — verify quoted plan text against the file.
- [MI-5 reviewed, approved](project_mi5_reviewed_approved.md) — disclosed "unreachable choice path" gap verified against `_build_ownship`; check deferrals are explicit branches, not accidents.
