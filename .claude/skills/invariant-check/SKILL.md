---
name: invariant-check
description: Scan source files for violations of project invariants defined in CLAUDE.md
type: user-invocable
---

Scans the source tree for the project invariants that are actually **greppable**, and reports a
pass/fail table with `file:line` evidence. Used by the Reviewer (procedure step 2) and DoD as the
mechanical foundation for invariant verification — it does not replace reading the invariant lists
in root `CLAUDE.md` and `body-layer/CLAUDE.md` ("Invariants — break these and the failure is
silent"), most of which are semantic and cannot be grepped for at all.

**Adapted from the template 2026-09-27** (it shipped as `{{PLACEHOLDER}}` text with Rust examples,
and was cited as a Reviewer step for weeks while unable to run). Two rules governed the adaptation,
both learned from this repo's own history:

- **Every check below was run against `main` before being included**, and each either passes today
  or reports a real finding. A check that is permanently red trains people to skip the whole report
  — which is why there is no blanket "no `print()` in source" check: this project's product *is*
  printed crew text, and such a check would report 37 violations forever.
- **Checks are patterns that would catch a real regression this project has had**, not generic
  hygiene. `BINOCULAR_RANGE_MULTIPLIER` is checked because modelling Petrovich as permanently
  glassed-up was the single biggest source of over-detection; the `derived_world_position` check is
  the no-omniscience invariant in its one mechanical form.

```bash
#!/usr/bin/env bash
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

PASS="✓ PASS"
FAIL="✗ FAIL"
WARN="⚠ WARN"

# Subprojects are DISCOVERED, never enumerated -- the same rule the commit gate and
# the push gate now follow, after the enumeration defect recurred four times here.
SUBPROJECTS=$(git ls-files '*/pyproject.toml' | awk -F/ 'NF==2 {print $1}' | sort -u)
SRC_DIRS=$(for s in $SUBPROJECTS; do [ -d "$s/src" ] && printf '%s ' "$s/src"; done)

echo "# Invariant Check"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M')  ·  Subprojects: $(echo $SUBPROJECTS | tr '\n' ' ')"
echo ""
echo "| Invariant | Status | Findings |"
echo "|-----------|--------|---------|"

row() {  # row <title> <status> <findings-or-empty>
  if [ -z "$3" ]; then echo "| $1 | $2 | — |"
  else echo "| $1 | $2 | $(echo "$3" | wc -l | tr -d ' ') occurrence(s) |"; fi
}

# ── 1. No omniscience: the Percept boundary ───────────────────────────────────
# body-layer/CLAUDE.md: "belief code never sees Observation.derived_world_position
# or a DCS object id." percept.py is the boundary and documents the field by name;
# perception/source.py declares it. Anything else reading it is the violation --
# and it HAS happened: perception/hybrid_source.py was writing ground-truth-derived
# positions into belief behind a cosmetic uncertainty band until 2026-09-24.
OMNI=$(grep -rn --include='*.py' '\.derived_world_position' $SRC_DIRS 2>/dev/null \
  | grep -v 'belief/percept\.py' | grep -v 'perception/source\.py' || true)
row "No omniscience — \`derived_world_position\` outside the Percept boundary" \
    "$([ -z "$OMNI" ] && echo "$PASS" || echo "$FAIL")" "$OMNI"

# ── 2. Module independence ────────────────────────────────────────────────────
# Root CLAUDE.md: each subproject runs standalone; body-layer -> world-model
# (query/coordinates, in-process) is the SOLE sanctioned exception. Any other
# subproject importing another's top-level package is the violation.
#
# Two false-positive traps, both hit while writing this and both worth keeping in
# mind if the check is ever widened: a subproject importing its OWN top-level
# packages looks identical to a cross-import (world-model's `from store.models
# import ...`), and package names collide across subprojects (aircraft-layer has its
# own `api` package, as does world-model). So each subproject's own package names are
# subtracted from the pattern before it is applied to that subproject.
list_pkgs() { ls "$1/src" 2>/dev/null | grep -vE '^(__pycache__|_vendor|.*\.egg-info)$'; }
WM_PKGS=$(list_pkgs world-model)
CROSS=""
for s in $SUBPROJECTS; do
  [ -d "$s/src" ] || continue
  [ "$s" = "body-layer" ] && continue          # the one sanctioned seam
  [ "$s" = "world-model" ] && continue         # its own packages are not cross-imports
  own=$(list_pkgs "$s")
  pat=$(comm -23 <(echo "$WM_PKGS" | sort) <(echo "$own" | sort) | paste -sd'|' -)
  [ -n "$pat" ] || continue
  hits=$(grep -rnE --include='*.py' "^[[:space:]]*(from|import) (${pat})([. ]|$)" \
    "$s/src" 2>/dev/null || true)
  [ -n "$hits" ] && CROSS="$CROSS$hits"$'\n'
done
CROSS=$(printf '%s' "$CROSS" | sed '/^$/d')
row "Module independence — no unsanctioned cross-subproject import" \
    "$([ -z "$CROSS" ] && echo "$PASS" || echo "$FAIL")" "$CROSS"

# ── 3. No sys.path smuggling ──────────────────────────────────────────────────
# The route by which check 2 gets bypassed without an import statement to find.
SYSPATH=$(grep -rn --include='*.py' 'sys\.path\.\(append\|insert\)' $SRC_DIRS 2>/dev/null || true)
row "No \`sys.path\` manipulation in \`src/\`" \
    "$([ -z "$SYSPATH" ] && echo "$PASS" || echo "$FAIL")" "$SYSPATH"

# ── 4. The naked eye is the default optic ─────────────────────────────────────
# BINOCULAR_RANGE_MULTIPLIER was retired in cones slice 2A: a flat range multiplier
# is exactly the "permanently glassed-up" model the user removed (2026-09-20), and
# deleting it also dissolved a real circular import. Prose references are fine --
# an assignment means it came back.
BINO=$(grep -rn --include='*.py' '^[[:space:]]*BINOCULAR_RANGE_MULTIPLIER[[:space:]]*[:=]' \
  $SRC_DIRS 2>/dev/null || true)
row "Retired \`BINOCULAR_RANGE_MULTIPLIER\` has not returned" \
    "$([ -z "$BINO" ] && echo "$PASS" || echo "$FAIL")" "$BINO"

# ── 5. No stray printing in the belief/perception core ────────────────────────
# Scoped deliberately: console.py / crew_console.py ARE the printing surfaces, and
# escalation.py's NullBrainClient prints to an injected stream. Everything else in
# perception/ and belief/ returns values and lets a surface render them.
STRAY=$(grep -rn --include='*.py' 'print(' body-layer/src/perception body-layer/src/belief 2>/dev/null \
  | grep -vE 'belief/(console|crew_console|escalation)\.py' || true)
row "No stray \`print()\` in \`perception/\` or \`belief/\` core" \
    "$([ -z "$STRAY" ] && echo "$PASS" || echo "$FAIL")" "$STRAY"

# ── 6. No bare except ────────────────────────────────────────────────────────
BARE=$(grep -rnE --include='*.py' 'except[[:space:]]*:' $SRC_DIRS 2>/dev/null || true)
row "No bare \`except:\`" "$([ -z "$BARE" ] && echo "$PASS" || echo "$FAIL")" "$BARE"

# ── 7. Swallowed exceptions (WARN) ───────────────────────────────────────────
# Legitimate in shutdown paths (all current sites are entrypoints or log teardown).
# Reported so a new one in a decision path gets a human look, never auto-failed.
SWALLOW=$(grep -rn --include='*.py' -A1 'except ' $SRC_DIRS 2>/dev/null | grep 'pass$' || true)
row "Swallowed exceptions (\`except …: pass\`)" \
    "$([ -z "$SWALLOW" ] && echo "$PASS" || echo "$WARN")" "$SWALLOW"

# ── 8. Type suppressions (WARN) ──────────────────────────────────────────────
# mypy --strict is enforced at commit time, so these are the declared escapes.
IGNORES=$(grep -rn --include='*.py' 'type: ignore' $SRC_DIRS 2>/dev/null || true)
row "\`# type: ignore\` suppressions" \
    "$([ -z "$IGNORES" ] && echo "$PASS" || echo "$WARN")" "$IGNORES"

# ── 9. TODO/FIXME markers (WARN) ─────────────────────────────────────────────
# This repo records open work in ROADMAP/BACKLOG files with stable IDs, not in code.
MARKERS=$(grep -rnE --include='*.py' 'TODO|FIXME|HACK|XXX' $SRC_DIRS 2>/dev/null || true)
row "No TODO/FIXME in committed source (backlog IDs instead)" \
    "$([ -z "$MARKERS" ] && echo "$PASS" || echo "$WARN")" "$MARKERS"

echo ""

print_detail() {
  if [ -n "$2" ]; then
    echo "## $1"; echo '```'; echo "$2" | head -20; echo '```'; echo ""
  fi
}
print_detail "Ground truth outside the Percept boundary" "$OMNI"
print_detail "Cross-subproject imports" "$CROSS"
print_detail "sys.path manipulation" "$SYSPATH"
print_detail "BINOCULAR_RANGE_MULTIPLIER assignments" "$BINO"
print_detail "Stray print() in core" "$STRAY"
print_detail "Bare except" "$BARE"
print_detail "Swallowed exceptions" "$SWALLOW"
print_detail "Type suppressions" "$IGNORES"
print_detail "TODO/FIXME markers" "$MARKERS"

echo "---"
echo "FAIL items must be fixed before merge. WARN items need a human look, not an automatic block."
echo ""
echo "NOT COVERED HERE, and not coverable: most of this project's invariants are semantic --"
echo "mechanism and calibration never sharing a commit, a classification's level never decaying,"
echo "two Observations sharing (source, t_sim) never resolving to one contact, everything being"
echo "testable without a live DCS session. Read body-layer/CLAUDE.md's \"Invariants\" section and"
echo "root CLAUDE.md; a PASS here is not a claim that those hold."
```
