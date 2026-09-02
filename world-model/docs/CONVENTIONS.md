# World Model Builder — Conventions

Working conventions specific to the DCS World Model Builder pipeline. Split out of
`world-model/CLAUDE.md` to keep that file to stack/testing/structure essentials; these are
the non-negotiable rules for how this pipeline is built.

- **Reconnaissance before implementation.** DCS internals are incompletely documented and change over versions — verify claims against the installed DCS version and record findings in `research/` (version, theatre, file/API, exact observation, documented-vs-inferred, reproducible test, source). Do not encode forum folklore as fact.
- **Provenance and confidence are first-class.** Any feature derived from mixing DCS + external GIS data must record source and match confidence per-field, not collapse into one undocumented fact.
- **Cross-machine setup**: DCS World runs on a separate Windows PC; primary development is on this Mac. Manual-copy workflow — see `WORKFLOW.md`. Raw extracted data lives under `data/raw/` and is gitignored; never commit it.
- **Read-only against DCS.** Never modify the DCS installation.
- Python 3.11+, type-hinted throughout, `mypy --strict` (see `pyproject.toml`). Spatial library choices are not yet locked — decide during Milestone 1-2 and record the decision + rationale in `research/`.
