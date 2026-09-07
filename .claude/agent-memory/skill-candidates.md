# Skill Candidates

Candidate patterns observed repeatedly in sessions that might warrant a dedicated skill.
Populated automatically by the SubagentStop skill-gap detector hook (see `settings.json`) after
each `dod` agent run. Reviewed and cleared during `merge-skill-review.sh`'s post-merge check —
entries are removed once created or rejected by the user.

## 2026-09-06 memory-update-cycle
- **Pattern**: Read existing memory file (e.g., `project_*.md`) → edit structured fields (Why/How-to-apply/links) → update parent index file (MEMORY.md) → commit with message
- **Count**: 3 times this session (project_compute_topology.md, project_wm_gate_lifted_aircraft_layer_next.md, CLAUDE.md/todo.md priority edits)
- **Benefit**: Ensures consistent metadata structure, auto-updates index/backlinks, reduces manual index management, speeds up future decision logging

## 2026-09-06 canonical-to-scratch-sync
- **Pattern**: Copy (never edit in-place) source files from canonical repo path (e.g., `aircraft-layer/src/...`, `aircraft-layer/dcs-export/Export.lua`) to gitignored scratch path (`win-mac-sync/aircraft-layer/...`) via `cp`, verify gitignore match, document sync convention
- **Count**: 6 files copied this session; pattern applied once but would repeat for every build/test cycle involving native-Windows deployment
- **Benefit**: Formalizes native-Windows deployment workflow (currently by analogy from wsl-probe-sync); ensures canonical truth stays in repo; establishes cross-platform sync SOP beyond WSL-specific tooling
