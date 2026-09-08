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

## 2026-09-07 iterative-web-recon-to-dated-report
- **Pattern**: Run many narrow WebSearch queries (community wiki/forum/mod terms) plus WebFetch on the most promising hits to triangulate whether an undocumented API/state is exposed, then synthesize into a dated findings file under `world-model/research/` and produce a short verdict summary
- **Count**: 19 WebSearch + 5 WebFetch calls this session (investigator subagent researching Petrovich/Mi-24P detection-state extractability)
- **Benefit**: A dedicated research-recon skill could standardize query fan-out strategy (terminology variants, source prioritization: official docs > wiki > forum > mod source), dedupe overlapping searches, and enforce the dated-report/verdict-summary output format directly — cutting redundant searches and speeding future PB-0-style feasibility investigations

## 2026-09-08 lua-export-syntax-check
- **Pattern**: After editing `win-mac-sync/to-windows/Export.lua`, run `luac -p <path> && echo <ok-marker>` to check Lua syntax before/after each iteration, repeated across successive edits
- **Count**: 5 times this session
- **Benefit**: A small skill/script wrapping the `luac -p` check (with a consistent pass/fail marker and auto-locating the deployed Export.lua path) would save repeated ad hoc invocation and catch typos in the stdlib-only Lua export script faster during PB-1-style live-spike iteration

## 2026-09-08 dcs-debug-log-recon
- **Pattern**: Inline `python3 - <<EOF ... EOF` heredoc scripts (plus paired `grep -c`/`grep -n` calls) to parse `win-mac-sync/from-windows/dcs-logs/*.log` for probe output — deduplicating raw `list_indication(...)` values, counting probe-pattern occurrences, extracting multi-line log entries
- **Count**: 5 python3-heredoc log-parsing invocations (plus several companion grep -c/-n calls) this session, all against the same DCS debug-log recon task
- **Benefit**: A reusable log-recon skill/script (parameterized by probe-pattern name and log path) would standardize DCS export debug-log analysis for live-spike investigations, avoiding rewritten one-off regex/heredoc scripts each iteration
