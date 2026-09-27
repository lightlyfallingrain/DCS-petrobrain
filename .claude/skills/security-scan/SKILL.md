---
name: security-scan
description: Full security scan — pattern scan plus the changed-code diff, for the Security agent's deep analysis
type: user-invocable
---

Orchestrates the deep-analysis scan: the risky-pattern sweep and the changed-code diff, in one pass,
so the Security agent reads structured output rather than raw source.

```bash
#!/usr/bin/env bash
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

echo "# Security Scan — $(date '+%Y-%m-%d %H:%M')"
echo ""
echo "Branch: $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)"
echo ""
echo "## Step 1 — risky-pattern sweep"
echo ""
echo "Run \`/security-grep\`. It covers Python across every discovered subproject plus the Lua that"
echo "runs inside DCS, and states which categories have expected steady-state hits."
echo ""
echo "## Step 2 — changed code only"
echo ""
echo "Run \`/extract-feature-diff\`. Scopes review to \`*.py\` and \`*.lua\` changed against \`main\`."
echo ""
echo "## Step 3 — dependency posture"
echo ""
echo "Run \`/extract-plan-deps plans/<feature>/plan.md\` when a plan exists."
echo ""
echo "---"
echo "Security agent: interpret the output of those three, then write the findings."
```

## What this no longer does, and why

**Rewritten 2026-09-27.** It shipped as template text — `{{AUDIT_COMMAND_JSON}}`,
`{{SBOM_COMMAND}}`, a `cargo-audit` JSON parser — and was cited as step 1 of Security's deep
analysis while unable to run at all. Two of its four steps were dropped rather than translated:

- **The CVE audit is gone.** It required `cargo audit`'s JSON shape; the Python equivalent
  (`pip-audit`) is installed in none of the six venvs, and the surface it would scan is three
  declared packages in total — `pyproj`, `pillow`, `osmium`. A CVE table over three well-known
  packages, regenerated per feature, is cost without signal. If the dependency surface grows,
  `/audit-report` is the skill to bring back (it was deleted the same day, and its template form is
  in the `claude-template` repo).
- **SBOM regeneration is gone.** Same reason, plus nothing consumed `sbom.json`: it was listed as an
  artifact in `security.md` while no such file had ever existed in the repo.

What remains is what actually finds things here. Every real security finding on this project came
from reading code on a boundary — an unbounded `Content-Length`, an unguarded poll loop that could
die silently, a `net.dostring_in` bridge — not from a dependency database.
