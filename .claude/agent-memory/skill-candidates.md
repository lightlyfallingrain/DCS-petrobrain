# Skill Candidates

Candidate patterns observed repeatedly in sessions that might warrant a dedicated skill.
Populated automatically by the SubagentStop skill-gap detector hook (see `settings.json`) after
each `dod` agent run. Reviewed and cleared during `merge-skill-review.sh`'s post-merge check —
entries are removed once created or rejected by the user.

## 2026-09-09 dcs-file-investigation
- **Pattern**: Systematic search and inspection of DCS World game mod files (particularly Mi-24P helicopter mods), including checking directory structures, extracting strings from Lua scripts and binary files, and grepping for specific game-related keywords
- **Count**: 40+ combined grep/ls/find/strings calls across DCS mod directories
- **Benefit**: Agents investigating DCS game mechanics or mods repeatedly need to locate Lua files, examine binary strings, check directory layouts, and search for specific game elements—a skill could streamline these queries with simpler high-level operations like "find all PKV indicator files" or "extract strings mentioning contacts from Mi-24P mod"

## 2026-09-09 partial-document-reader
- **Pattern**: Using sed with line ranges (sed -n 'X,Yp') to extract specific sections from documents, often paired with file navigation logic
- **Count**: 18+ sed-based line extraction calls
- **Benefit**: Replace verbose sed syntax with a simpler "read lines X-Y from file" operation; reduces cognitive load and command formulation errors when agents need to iteratively navigate large documents

## 2026-09-09 python-inline-file-transformation
- **Pattern**: Python inline scripts (run via `python3 - <<'PY'...`) that read a file, apply structured transformations (regex, string replacement, regex substitution on specific fields), write back, and optionally git-add the result
- **Count**: 6+ calls (lines 49, 56, 73, 74, 75, 89, 100 of transcript) transforming Markdown plans, Lua probe code, and Python test fixtures
- **Benefit**: Replace boilerplate Python heredoc→open→read→transform→write→commit with a higher-level "apply these regex rules to file" operation, reducing script formulation errors and cognitive load for agents doing doc updates, code generation, and test fixture maintenance

## 2026-09-09 test-and-commit-cycle
- **Pattern**: Update test files with Python inline scripts, validate with pytest/ruff/mypy checks, then create git commits with detailed messages
- **Count**: 3+ cycles of (edit test → run format+lint+type+test → git commit)
- **Benefit**: Streamline the test-verify-commit workflow; a skill could handle the boilerplate of running all three linters and committing on success, reducing verbose multi-step commands into a single higher-level operation
