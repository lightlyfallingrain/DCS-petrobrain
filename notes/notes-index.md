# Notes — index

Knowledge harvested from feature work and investigation. Short, factual, one idea per bullet.
Obvious patterns from code or CLAUDE.md belong in CLAUDE.md, not here — these are insights earned
by doing.

**One file per topic, this index lists them all.** Split out of the single root `NOTES.md` on
2026-10-19, mirroring the `ROADMAP/` split (`docs/DOC_CONVENTIONS.md`, "Split notes"). `NOTES.md`
is now a pointer and holds no insights; writing to it puts the bullet where nothing reads it.

**Adding an insight** (the Definition of Done harvest, `.claude/agents/dod.md` Step 5):

- Append the bullet to the topic file it belongs to.
- If no topic fits, create `notes/<kebab-case-topic>.md` with the topic as its `# ` heading, and
  add one line for it below. Check the basename is unused repo-wide first
  (`git ls-files | grep -i '/<name>.md$'`) — Obsidian resolves links by basename.
- Topic files carry no IDs and no status.

## Topics

- [[coordinate-transforms-and-projections]] — Coordinate Transforms & Projections
- [[testing-and-provenance]] — Testing & Provenance
- [[raster-charts-and-registration]] — Raster Charts & Registration
- [[external-binaries-and-cli-utilities]] — External Binaries & CLI Utilities
- [[external-data-and-integration]] — External Data & Integration
- [[dcs-elevation-extraction]] — DCS Elevation Extraction
- [[persistent-storage-and-spatial-indexing]] — Persistent Storage & Spatial Indexing
- [[multi-store-and-modular-storage]] — Multi-Store & Modular Storage
- [[planning-and-process-lessons]] — Planning & Process Lessons
- [[type-checking-and-python-conventions]] — Type Checking & Python Conventions
- [[petrobrain-runtime-and-perception]] — Petrobrain Runtime & Perception
- [[input-interface-and-event-architecture-f10-crew-commands]] — Input Interface & Event Architecture (F10 crew commands)
- [[fixture-management-and-test-infrastructure]] — Fixture Management & Test Infrastructure
- [[dcs-visualization-and-ui-integration]] — DCS Visualization & UI Integration
- [[classification-and-fusion-bl-2-6]] — Classification & Fusion (BL-2.6)
- [[mission-phase-and-relevance-bl-7]] — Mission Phase & Relevance (BL-7)
- [[perception-calibration-and-measurement]] — Perception Calibration & Measurement
- [[osm-multipolygon-assembly-and-simplification-m9]] — OSM Multipolygon Assembly & Simplification (M9)
- [[spatial-gating-and-clustering-group-contact-model-stages-1-2]] — Spatial Gating & Clustering (Group Contact Model, Stages 1–2)
- [[solve-the-problem-in-its-natural-coordinate-space]] — Solve the problem in its natural coordinate space
- [[a-design-written-against-a-stale-test-list-produces-phantom]] — A design written against a stale test list produces phantom expectations
- [[a-predicates-granularity-has-to-match-the-granularity-of]] — A predicate's granularity has to match the granularity of what it governs
- [[a-component-test-can-pass-while-the-sentence-it-builds-is]] — A component test can pass while the sentence it builds is wrong
- [[optics-calibration]] — Optics/Calibration
- [[voice-recognition-and-command-matching]] — Voice Recognition & Command Matching
- [[debugging-and-root-cause-diagnosis]] — Debugging & Root-Cause Diagnosis
- [[model-selection-and-local-llm-serving-brain-layer-br-1]] — Model Selection & Local LLM Serving (brain-layer BR-1)
- [[attack-run-guidance-design-bl-14]] — Attack-run guidance design (BL-14)
- [[the-9k113-sight-bl-b64]] — The 9K113 sight (BL-B64)
- [[mission-memory-bl-8]] — Mission Memory (BL-8)
- [[mission-start-and-reset-patterns-bl-15]] — Mission Start & Reset Patterns (BL-15)
