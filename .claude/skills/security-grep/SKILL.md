---
name: security-grep
description: Scan source files for risky patterns — unsafe operations, error suppression, hardcoded secrets, network/fs/process APIs
type: user-invocable
---

Scans the source tree for security-relevant patterns and outputs `file:line` hits grouped by
category. The Security agent judges the hits; it does not scan source itself. Empty categories are
suppressed, so a quiet report means those categories are genuinely empty.

Covers **Python and Lua**. The Lua half is not optional here: `aircraft-layer`'s `Export.lua` hooks
and the F10 command hook run inside the DCS process, are the project's only code with an
unsandboxed host, and appear in no Python scan.

**Adapted from the template 2026-09-27** — it shipped as `{{PLACEHOLDER}}` text with Rust/TS
examples while `security.md` cited it as procedure step 3. Category patterns were checked against
`main` so the Security agent inherits a scan whose noise level is known: the hits in `subprocess`,
`socket`/`http.server` and `open(` are all expected (TTS synthesis, the LAN HTTP peers, the log and
store writers) — this scan exists to make a *new* one visible, not to imply the current ones are
findings.

```bash
#!/usr/bin/env bash
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

# Subprojects DISCOVERED, never enumerated (the enumeration defect has recurred four
# times in this repo -- see commit-quality-gate.sh's own comment).
SUBPROJECTS=$(git ls-files '*/pyproject.toml' | awk -F/ 'NF==2 {print $1}' | sort -u)
PY_DIRS=$(for s in $SUBPROJECTS; do [ -d "$s/src" ] && printf '%s ' "$s/src"; done)
# Lua lives outside src/ (it is deployed into the DCS install, not packaged).
LUA_FILES=$(git ls-files '*.lua')

FOUND=0
section() {
  local title="$1" results
  # Strip blank lines first: the Python+Lua categories below concatenate two command
  # substitutions, so an all-empty category still arrives as a newline and would
  # print an empty heading -- exactly the "suppress empty categories" promise broken.
  results=$(printf '%s' "$2" | sed '/^[[:space:]]*$/d')
  if [ -n "$results" ]; then
    echo ""; echo "### $title"; echo "$results" | head -40; FOUND=1
    local n; n=$(echo "$results" | wc -l | tr -d ' ')
    [ "$n" -gt 40 ] && echo "… $((n - 40)) more"
  fi
}
pygrep() { grep -rnE --include='*.py' "$1" $PY_DIRS 2>/dev/null | grep -v '/_vendor/' || true; }
luagrep() { [ -n "$LUA_FILES" ] && grep -nE "$1" $LUA_FILES 2>/dev/null || true; }

echo "# Security Grep — $(date '+%Y-%m-%d %H:%M')"
echo "Scope: $(echo $PY_DIRS) + $(echo "$LUA_FILES" | wc -l | tr -d ' ') Lua file(s)"

# 1. Type/lint suppression -- the Python analogue of `unsafe`. mypy --strict is
#    enforced at commit time, so each of these is a declared escape from it.
section "type / lint suppression" "$(pygrep 'type:[[:space:]]*ignore|noqa')"

# 2. Error suppression outside tests (tests are excluded by scanning src/ only).
#    `-A1` because the common form spans two lines (`except X:` / `pass`) and a
#    single-line regex silently reports none, which is how this category read as
#    clean on first run while seven sites existed.
section "error suppression" \
  "$(grep -rnE --include='*.py' -A1 'except ' $PY_DIRS 2>/dev/null | grep -E 'pass$|\.\.\.$' || true)"

# 3. Hardcoded credential-like assignments. Requires a quoted literal of some length
#    on the right-hand side and drops interpolated log lines -- without that, a Lua
#    `logi("… token=" .. tostring(token))` reads as a hardcoded credential.
section "potential hardcoded credentials" \
  "$(pygrep '(password|secret|api.?key|private.?key|auth.?token)[[:space:]]*[=:][[:space:]]*["'"'"'][^"'"'"']{6,}' | grep -v 'tostring(' || true)
$(luagrep '(password|secret|api.?key|token)[[:space:]]*=[[:space:]]*["'"'"'][^"'"'"']{6,}' | grep -v 'tostring(' || true)"

# 4. Dynamic code execution in Python. The one category where a hit is a finding by
#    default: nothing on the Python side has a legitimate reason to eval.
section "dynamic code execution (Python — a hit is a finding)" \
  "$(pygrep '\beval\(|\bexec\(|pickle\.loads|yaml\.load\(')
$(luagrep '\bloadstring\(|\bdofile\(')"

# 4b. The DCS mission-scripting bridge, reported separately because it is EXPECTED.
#     `net.dostring_in("scripting", …)` has been in production since 2026-09-13 and
#     is how the F10 command hook and the telemetry hook reach into the mission
#     sandbox; it can run arbitrary mission-scripting Lua, so it is worth seeing on
#     every scan. Hits under aircraft-layer/dcs-export/ are the shipped mechanism;
#     a hit anywhere else, or one whose injected code is built from external input
#     rather than a fixed string, is the finding.
section "DCS mission-scripting bridge (expected in aircraft-layer/dcs-export/)" \
  "$(luagrep 'net\.dostring_in')"

# 5. External command / process execution.
section "external command / process execution" \
  "$(pygrep 'subprocess|os\.system|os\.popen|shell=True')
$(luagrep 'os\.execute|io\.popen')"

# 6. Network APIs -- the LAN HTTP surfaces between subprojects, and the DCS socket.
section "network APIs" \
  "$(pygrep '\bsocket\b|http\.server|HTTPServer|urllib|requests\.|urlopen|BaseHTTPRequestHandler')
$(luagrep 'socket\.|require *\("socket"\)')"

# 7. Unbounded reads on a network boundary -- the shape of the real audio-adapter and
#    aircraft-layer findings (a Content-Length trusted without a bound, a read with no
#    cap). Worth its own category because item 6 is too noisy to spot it inside.
section "reads sized by remote input" "$(pygrep 'Content-Length|rfile\.read|recv\(')"

# 8. File system writes. Read-only DCS access is a hard project rule
#    (world-model/docs/CONVENTIONS.md): never modify the DCS installation.
section "file writes / paths" "$(pygrep "open\([^)]*['\"][wa]|shutil\.|os\.remove|os\.rename|Path\([^)]*\)\.write")"

# 9. Explicit crash paths outside tests.
section "explicit failure paths" "$(pygrep '\braise\b|assert ')"

echo ""
if [ $FOUND -eq 0 ]; then
  echo "### Result: no risky patterns found."
else
  echo "---"
  echo "Review each hit. Not all are vulnerabilities — context determines risk. Categories 1, 2,"
  echo "5, 6, 8 and 9 have expected steady-state hits in this project; category 4 does not, and a"
  echo "hit there is a finding until argued otherwise."
fi
```
