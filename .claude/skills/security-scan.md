---
name: security-scan
description: Full security scan — runs audit-report, security-grep, extract-feature-diff, and regenerates the SBOM
type: user-invocable
---

Orchestrates the complete security scan sequence for deep analysis mode. All steps are scripted; the security agent interprets the structured output rather than reading raw source.

```bash
#!/usr/bin/env bash
cd {{PROJECT_DIR}}

echo "# Security Scan — $(date '+%Y-%m-%d %H:%M')"
echo ""

# ── Tool availability check ───────────────────────────────────────────────────
MISSING_TOOLS=()
{{AUDIT_TOOL_CHECK}} &>/dev/null || MISSING_TOOLS+=("{{AUDIT_TOOL_NAME}} ({{AUDIT_INSTALL_COMMAND}})")
{{SBOM_TOOL_CHECK}} &>/dev/null   || MISSING_TOOLS+=("{{SBOM_TOOL_NAME}} ({{SBOM_INSTALL_COMMAND}})")

if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
  echo "## WARNING: Missing security tools"
  for t in "${MISSING_TOOLS[@]}"; do echo "  - $t"; done
  echo ""
  echo "Install missing tools before running a full scan. Continuing with available tools..."
  echo ""
fi

# ── Step 1: CVE Audit ────────────────────────────────────────────────────────
echo "## Step 1: CVE Audit"
echo ""
{{AUDIT_COMMAND_JSON}} 2>/dev/null | python3 - <<'PYEOF'
import json, sys
try:
    data = json.load(sys.stdin)
except:
    print("Audit output could not be parsed — tool may not be installed.")
    sys.exit(0)
# Rust/cargo-audit format — adapt for your tool
vulns = data.get('vulnerabilities', {}).get('list', [])
warnings_map = data.get('warnings', {})
if not vulns:
    print("| Audit | **CLEAN** — 0 vulnerabilities |")
else:
    print("| Package | Version | Advisory | Severity | Fixed In |")
    print("|---------|---------|----------|----------|----------|")
    for v in vulns:
        adv = v.get('advisory', {}); pkg = v.get('package', {})
        patched = adv.get('patched_versions', [])
        print(f"| {pkg.get('name','?')} | {pkg.get('version','?')} | {adv.get('id','?')} | {adv.get('cvss','?')} | {patched[0] if patched else 'no fix'} |")
for cat, items in warnings_map.items():
    for w in items:
        adv = w.get('advisory', {}); pkg = w.get('package', {})
        print(f"| {pkg.get('name','?')} | {pkg.get('version','?')} | {adv.get('id','?')} ({cat}) | — | — |")
PYEOF

# ── Step 2: Risky Pattern Scan ────────────────────────────────────────────────
echo ""
echo "## Step 2: Risky Pattern Scan"
echo ""

SRC="{{SOURCE_DIR}}"
EXT="{{SOURCE_EXT}}"

section() {
  local title="$1"; local results="$2"
  if [ -n "$results" ]; then echo "### $title"; echo "$results"; echo ""; fi
}
section "unsafe / type suppression" "$(grep -rn '{{UNSAFE_PATTERN}}' $SRC --include="*.$EXT" 2>/dev/null)"
section "error suppression outside tests" "$(grep -rn '{{ERROR_SUPPRESS_PATTERN}}' $SRC --include="*.$EXT" 2>/dev/null | grep -v '{{TEST_FILE_PATTERN}}')"
section "potential hardcoded credentials" "$(grep -rn -iE '(password|secret|api.?key|private.?key)\s*[=:]\s*["\x27]' $SRC --include="*.$EXT" 2>/dev/null)"
section "external command execution" "$(grep -rn '{{COMMAND_EXEC_PATTERN}}' $SRC --include="*.$EXT" 2>/dev/null)"
section "network APIs" "$(grep -rn '{{NETWORK_PATTERN}}' $SRC --include="*.$EXT" 2>/dev/null)"
section "file system access" "$(grep -rn '{{FILESYSTEM_PATTERN}}' $SRC --include="*.$EXT" 2>/dev/null)"
section "explicit failure paths" "$(grep -rn '{{PANIC_PATTERN}}' $SRC --include="*.$EXT" 2>/dev/null | grep -v '//')"

# ── Step 3: Feature Diff ──────────────────────────────────────────────────────
echo ""
echo "## Step 3: Feature Diff (changed code only)"
echo ""

CURRENT_BRANCH=$(git branch --show-current)
BASE="master"
git show-ref --verify --quiet refs/heads/main 2>/dev/null && BASE="main"
EXT_FILTER="{{DIFF_EXT_FILTER}}"

if [ "$CURRENT_BRANCH" = "$BASE" ]; then
  echo "(On $BASE — showing last commit diff)"
  eval git diff HEAD~1 HEAD $EXT_FILTER | head -500
else
  COMMIT_COUNT=$(git rev-list --count ${BASE}..HEAD 2>/dev/null || echo "?")
  echo "Branch: $CURRENT_BRANCH ($COMMIT_COUNT commits ahead of $BASE)"
  eval git diff ${BASE}...HEAD $EXT_FILTER | head -500
fi

# ── Step 4: SBOM Regeneration ─────────────────────────────────────────────────
echo ""
echo "## Step 4: SBOM Regeneration"
echo ""

if {{SBOM_TOOL_CHECK}} &>/dev/null; then
  {{SBOM_COMMAND}} && echo "sbom.json regenerated." || echo "WARNING: SBOM generation failed."
else
  echo "{{SBOM_TOOL_NAME}} not installed — SBOM not regenerated."
fi

echo ""
echo "---"
echo "Scan complete. Security agent: interpret the output above."
```

<!--
Configuration placeholders:

PROJECT_DIR            — absolute path to project root
SOURCE_DIR             — source directory, e.g. src/
SOURCE_EXT             — file extension, e.g. rs, ts, py

AUDIT_TOOL_CHECK       — e.g. "cargo audit --version" or "npm audit --version"
AUDIT_TOOL_NAME        — display name, e.g. "cargo-audit"
AUDIT_INSTALL_COMMAND  — e.g. "cargo install cargo-audit"
AUDIT_COMMAND_JSON     — e.g. "cargo audit --json" or "npm audit --json"

SBOM_TOOL_CHECK        — e.g. "cargo cyclonedx --version" or "syft --version"
SBOM_TOOL_NAME         — e.g. "cargo-cyclonedx" or "syft"
SBOM_INSTALL_COMMAND   — e.g. "cargo install cargo-cyclonedx"
SBOM_COMMAND           — e.g. "cargo cyclonedx --format json --output-file sbom.json"
                             or "syft . -o cyclonedx-json=sbom.json"

DIFF_EXT_FILTER        — git diff file filter, e.g. "-- '*.rs' '*.wgsl'" or "-- '*.ts' '*.tsx'"

Pattern placeholders — same as security-grep.md:
UNSAFE_PATTERN, ERROR_SUPPRESS_PATTERN, TEST_FILE_PATTERN,
COMMAND_EXEC_PATTERN, NETWORK_PATTERN, FILESYSTEM_PATTERN, PANIC_PATTERN
-->
