# World Model Builder — Conventions

Working conventions specific to the DCS World Model Builder pipeline. Split out of
`world-model/CLAUDE.md` to keep that file to stack/testing/structure essentials; these are
the non-negotiable rules for how this pipeline is built.

- **Reconnaissance before implementation.** DCS internals are incompletely documented and change over versions — verify claims against the installed DCS version and record findings in `research/` (version, theatre, file/API, exact observation, documented-vs-inferred, reproducible test, source). Do not encode forum folklore as fact.
- **Provenance and confidence are first-class.** Any feature derived from mixing DCS + external GIS data must record source and match confidence per-field, not collapse into one undocumented fact.
- **Cross-machine setup**: DCS World runs on a separate Windows PC; primary development is on this Mac. Manual-copy workflow — see `WORKFLOW.md`. Raw extracted data lives under `data/raw/` and is gitignored; never commit it.
- **Read-only against DCS.** Never modify the DCS installation.
- Python 3.11+, type-hinted throughout, `mypy --strict` (see `pyproject.toml`). Spatial library choices are not yet locked — decide during Milestone 1-2 and record the decision + rationale in `research/`.
- **Every build operation that can run longer than ~30s at `syria-full` scale must report progress through the shared `progress` module** (`src/progress.py`: `ThrottledProgress` for a loop that returns to Python regularly, `Heartbeat` for a single call with no Python callback for long stretches, e.g. pyosmium's `apply_file`). A stage that logs nothing for minutes is indistinguishable from a hang — this has recurred three times against real builds (Stage 5 junctions, then Stage 3 OSM overlay twice) with a different ad hoc fix each time before `progress.py` unified it; see `plans/osm-landcover-optimization/progress-logging.md` for the audit and root-cause. When adding a new pipeline stage or a new loop inside an existing one, check whether it can exceed ~30s at full-theatre scale (measure, don't assume) and wire it onto `progress.py` if so — do not add another one-off timer/counter.
