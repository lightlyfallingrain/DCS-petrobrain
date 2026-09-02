---
name: extract-plan-deps
description: Extract new or changed dependencies from a plan file by diffing against the current package manifest
type: user-invocable
---

Usage: `/extract-plan-deps <plan-file>`

Example: `/extract-plan-deps plans/star-rendering/plan.md`

Extracts package dependency lines from a plan markdown file and reports only those that are new or version-changed relative to the current manifest file (Cargo.toml, package.json, pyproject.toml, etc.). Zero LLM token cost — pure shell comparison.

The security agent calls this first; if output is non-empty, it runs CVE checks only on the new packages.

```bash
#!/usr/bin/env bash
cd {{PROJECT_DIR}}

PLAN_FILE="${1:-}"
MANIFEST="{{MANIFEST_FILE}}"
# e.g. Cargo.toml, package.json, requirements.txt, pyproject.toml

if [ -z "$PLAN_FILE" ]; then
  echo "Usage: /extract-plan-deps <plan-file>"
  exit 1
fi

if [ ! -f "$PLAN_FILE" ]; then
  echo "ERROR: plan file not found: $PLAN_FILE"
  exit 1
fi

# Extract dependency lines from the plan markdown.
# Matches lines that look like package manifest entries.
# Customize the pattern for your package format:
#
#   Cargo.toml style:   crate-name = "1.2.3"  or  crate-name = { version = "..." }
#   npm package.json:   "package-name": "^1.2.3"
#   requirements.txt:   package-name==1.2.3 or package-name>=1.2.3
#   pyproject.toml:     package-name = "^1.2.3"
#
PLAN_DEPS=$(grep -E "{{DEP_LINE_PATTERN}}" "$PLAN_FILE" \
  | sed 's/^[[:space:]]*//' \
  | sort)

# Extract current deps from manifest
CURRENT_DEPS=$({{MANIFEST_DEP_EXTRACT_COMMAND}} | sort)

if [ -z "$PLAN_DEPS" ]; then
  echo "No dependency lines matching '{{DEP_LINE_PATTERN}}' found in plan."
  echo "Check plan manually if it describes new deps in prose."
  exit 0
fi

NEW_DEPS=$(comm -23 <(echo "$PLAN_DEPS") <(echo "$CURRENT_DEPS"))

if [ -z "$NEW_DEPS" ]; then
  echo "NEW DEPS: none"
  echo "All dependency lines in plan match existing manifest."
else
  echo "NEW OR CHANGED DEPS:"
  echo "$NEW_DEPS"
fi
```

<!--
Configuration placeholders:

PROJECT_DIR                — absolute path to project root
MANIFEST_FILE              — your package manifest, e.g.:
                             Cargo.toml | package.json | requirements.txt | pyproject.toml

DEP_LINE_PATTERN           — regex matching dep lines in plan markdown, e.g.:
  Cargo:       ^\s*[a-zA-Z0-9_-]+ = (\{[^}]*version|"[0-9])
  npm:         "[a-z@][a-z0-9/@_-]*":\s*"[\^~]?[0-9]
  pip:         ^[a-zA-Z0-9_-]+(==|>=|~=)[0-9]

MANIFEST_DEP_EXTRACT_COMMAND — shell command to extract dep lines from current manifest, e.g.:
  Cargo:  awk '/^\[dependencies\]/,/^\[/' Cargo.toml | grep -E '^[a-zA-Z0-9_-]+ ='
  npm:    python3 -c "import json; d=json.load(open('package.json')); [print(f'\"{k}\": \"{v}\"') for k,v in {**d.get('dependencies',{}),**d.get('devDependencies',{})}.items()]"
  pip:    cat requirements.txt | grep -v "^#"
-->
