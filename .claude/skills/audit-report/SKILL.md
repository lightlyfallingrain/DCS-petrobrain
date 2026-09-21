---
name: audit-report
description: Run the dependency vulnerability audit and policy check, format combined output as a markdown table
type: user-invocable
---

Runs `{{AUDIT_COMMAND}}` and (if configured) `{{DENY_COMMAND}}`, formats combined output as a concise markdown table. The security agent receives structured data rather than raw tool output — no token cost for parsing.

```bash
#!/usr/bin/env bash
cd {{PROJECT_DIR}}

echo "## Dependency Audit"
echo ""

# Check tool availability
if ! {{AUDIT_COMMAND_CHECK}}; then
  echo "WARNING: audit tool not installed."
  echo "Install with: {{AUDIT_INSTALL_COMMAND}}"
  echo ""
fi

# ── Primary audit (JSON output parsed to table) ───────────────────────────────
# Replace the python block below with your tool's JSON parser if needed.
{{AUDIT_COMMAND_JSON}} 2>/dev/null | python3 - <<'PYEOF'
import json, sys

try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f"Could not parse audit output: {e}")
    print("Run the audit command manually to see raw output.")
    sys.exit(0)

# Rust / cargo-audit format
vulns = data.get('vulnerabilities', {}).get('list', [])
warnings_map = data.get('warnings', {})

if not vulns:
    print("| Result | Status |")
    print("|--------|--------|")
    print("| Audit | **CLEAN** — 0 known vulnerabilities |")
else:
    print("| Package | Version | Advisory | Severity | Description | Fixed In |")
    print("|---------|---------|----------|----------|-------------|----------|")
    for v in vulns:
        adv = v.get('advisory', {})
        pkg = v.get('package', {})
        patched = adv.get('patched_versions', [])
        title = adv.get('title', '?')[:55]
        print(f"| {pkg.get('name','?')} | {pkg.get('version','?')} | {adv.get('id','?')} | {adv.get('cvss','?')} | {title} | {patched[0] if patched else 'no fix'} |")

for cat, items in warnings_map.items():
    for w in items:
        adv = w.get('advisory', {}); pkg = w.get('package', {})
        print(f"| {pkg.get('name','?')} | {pkg.get('version','?')} | {adv.get('id','?')} ({cat}) | — | {adv.get('title','')[:40]} | — |")
PYEOF

echo ""

# ── Policy check (if configured) ─────────────────────────────────────────────
if {{DENY_COMMAND_CHECK}} 2>/dev/null; then
  echo "## Policy Check"
  echo ""
  {{DENY_COMMAND}} 2>&1 | grep -E "^(error|warning)" | head -30 || true
  echo ""
fi

echo "## Summary"
VULN_COUNT=$({{AUDIT_COMMAND_JSON}} 2>/dev/null | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(len(d.get('vulnerabilities',{}).get('list',[])))" \
  2>/dev/null || echo "?")
echo "Vulnerabilities found: $VULN_COUNT"
```

<!--
Configuration placeholders:

PROJECT_DIR            — absolute path to project root
AUDIT_COMMAND          — e.g., "cargo audit" or "npm audit"
AUDIT_COMMAND_JSON     — command that outputs JSON, e.g. "cargo audit --json" or "npm audit --json"
AUDIT_COMMAND_CHECK    — check if tool exists, e.g. "cargo audit --version" or "npm audit --version"
AUDIT_INSTALL_COMMAND  — e.g., "cargo install cargo-audit" or "npm install -g npm"
DENY_COMMAND           — optional policy check, e.g. "cargo deny check" or leave empty
DENY_COMMAND_CHECK     — check if deny tool exists, e.g. "cargo deny --version" or "false"

Note: The Python JSON parser above assumes cargo-audit output format.
For npm audit, the format differs — adapt the parser or replace with jq.

npm audit example adaptation:
  npm audit --json | python3 -c "
  import json,sys; d=json.load(sys.stdin)
  vulns = d.get('vulnerabilities', {})
  if not vulns: print('CLEAN')
  else:
    for name, v in vulns.items():
        print(f\"{name} | {v.get('severity','?')} | {v.get('title','?')}\")
  "
-->
