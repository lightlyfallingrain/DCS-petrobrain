# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [Wire boundary: type-check not range-check](project_wire_boundary_type_check_not_range_check.md) — logger.py validates isinstance only, not value domain, across the audio-adapter<->body-layer wire; check this class of gap on future passes.
- [Elapsed-time inflation, quadratic dt composition](project_elapsed_time_inflation_quadratic_dt_composition.md) — a hold+inflate recovery pattern's time-to-recover scales ~1/poll_interval, not a fixed constant; test continuous polling, not just a single gap.
