---
name: extract-plan-deps
description: Surface a plan's own dependency statements next to what each subproject already declares, for the Security plan review
type: user-invocable
---

Usage: `/extract-plan-deps <plan-file>`

Example: `/extract-plan-deps plans/m6-terrain-semantics/plan.md`

Prints every line of a plan that talks about dependencies, alongside what each subproject currently
declares in its `pyproject.toml`. Security's procedure step 1 calls this: if the plan proposes a new
package, the CVE question is scoped to that package; if it says "no new dependency", that claim is
now on screen next to the manifests and can be checked rather than assumed.

**Rewritten from the template 2026-09-27, after the transliteration failed.** The template assumed a
plan quotes manifest lines (`serde = "1.0"`); plans here never do, so pattern-matching manifest
syntax would have reported "none" on every plan forever. The first replacement went the other way —
every backticked identifier as a candidate — and produced 60 lines of `bearing_uncertainty_deg` and
`classify_yes_no` per plan, which is worse: a reviewer skims a list that long and stops reading it.

What actually works is that **this project's plans state their dependency posture in prose**, almost
always to rule one out: "zero new dependency, zero new data source" (`m10-road-junctions`), "stdlib
only — `struct`, `array`, `mmap`" (`m5-first-persistent-model`), "Any of those is a **new
dependency** — do not add it" (`m6-terrain-semantics`). `AGENTS.md` makes a new dependency an
escalation trigger, so the plan almost has to address it. Extracting those sentences is both the
lowest-noise signal available and a check on the claim itself.

```bash
#!/usr/bin/env bash
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

PLAN_FILE="${1:-}"
if [ -z "$PLAN_FILE" ]; then
  echo "Usage: /extract-plan-deps <plan-file>"
  echo "Available plans:"; ls plans/ 2>/dev/null | sed 's/^/  - /'
  exit 1
fi
[ -f "$PLAN_FILE" ] || { echo "ERROR: plan file not found: $PLAN_FILE"; exit 1; }

echo "# Plan dependency review — $PLAN_FILE"
echo ""

# ── 1. What the plan says about dependencies ──────────────────────────────────
DEP_LINES=$(grep -niE 'dependenc|pip install|third.?party|stdlib only|new package|\bwheel\b|pyproject' \
  "$PLAN_FILE" || true)

echo "## The plan's own dependency statements"
echo ""
if [ -z "$DEP_LINES" ]; then
  echo "NONE. The plan does not mention dependencies at all — which is itself worth a"
  echo "moment: AGENTS.md makes a new dependency an escalation trigger, so a plan that"
  echo "adds one and says nothing has skipped that. Read the Affected Modules section."
else
  echo '```'
  echo "$DEP_LINES" | head -30
  n=$(echo "$DEP_LINES" | wc -l | tr -d ' ')
  [ "$n" -gt 30 ] && echo "… $((n - 30)) more line(s)"
  echo '```'
fi
echo ""

# ── 2. What is already declared, per subproject ───────────────────────────────
# Subprojects DISCOVERED, never enumerated. Comment lines inside the array are
# skipped: every declared dependency here carries a paragraph of justification above
# it, and a naive grep reports the prose as a package (it produced "pyproj, Seams").
echo "## Currently declared dependencies"
echo ""
echo "| Subproject | Declared (runtime) |"
echo "|---|---|"
for m in $(git ls-files '*/pyproject.toml' | sort); do
  sub=$(dirname "$m")
  deps=$(awk '
      /^dependencies[[:space:]]*=/ { inside = 1 }
      inside {
        line = $0
        sub(/#.*/, "", line)                  # drop trailing comments
        while (match(line, /"[^"]+"/)) {
          spec = substr(line, RSTART + 1, RLENGTH - 2)
          sub(/[<>=!~;[].*$/, "", spec)
          if (spec != "") print spec
          line = substr(line, RSTART + RLENGTH)
        }
        if ($0 ~ /\]/) inside = 0
      }' "$m" 2>/dev/null | sort -u | paste -sd, - | sed 's/,/, /g')
  printf '| `%s` | %s |\n' "$sub" "${deps:-stdlib only}"
done
echo ""
echo "Dev tooling (\`ruff\`, \`mypy\`, \`pytest\`) is deliberately absent from every manifest: each"
echo "subproject keeps its own \`.venv\` and the tools are installed there, not declared. So"
echo "\"stdlib only\" above means exactly that — at runtime."
echo ""

# ── 3. In-process seams, which are not packages and never appear above ────────
echo "## Not a package, and deliberately so"
echo ""
echo "\`body-layer\` imports world-model's \`query\`/\`coordinates\` **in process** — the sole"
echo "sanctioned cross-subproject import (root CLAUDE.md, \"Module independence\"). It will never"
echo "show up as a declared dependency. Every other subproject boundary is HTTP/JSON. A plan"
echo "proposing a second in-process seam is proposing an architectural change, not a dependency,"
echo "and needs the same escalation."
echo ""
echo "---"
echo "Security: if the plan proposes a third-party package, that is a decision for the user"
echo "(AGENTS.md escalation rules), not an implementation detail — raise what it costs and what"
echo "it replaces, against the dependency policy in docs/PROCESS.md."
```
