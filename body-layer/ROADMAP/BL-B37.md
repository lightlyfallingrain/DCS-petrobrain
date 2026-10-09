# BL-B37 — Four `assert`s doing real runtime work

- [ ] **BL-B37 — Four `assert`s doing real runtime work in `belief/tools.py` and
  `belief/enrichment.py`.** #status/open 2026-10-05 security audit. They vanish under `python -O`, and the
  checks they perform are not developer-only invariants. Convert to explicit raises.
