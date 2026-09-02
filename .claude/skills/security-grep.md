---
name: security-grep
description: Scan source files for risky patterns — unsafe operations, error suppression, hardcoded secrets, network/fs/process APIs
type: user-invocable
---

Scans all source files for security-relevant patterns and outputs file:line hits grouped by category. The security agent judges the hits — it does not scan source files itself. Empty categories are suppressed.

Customize the grep patterns below to match your language and project conventions.

```bash
#!/usr/bin/env bash
cd {{PROJECT_DIR}}

SRC="{{SOURCE_DIR}}"
EXT="{{SOURCE_EXT}}"
FOUND=0

section() {
  local title="$1" results="$2"
  if [ -n "$results" ]; then
    echo ""
    echo "### $title"
    echo "$results"
    FOUND=1
  fi
}

# ── Language-specific patterns ────────────────────────────────────────────────
# Customize these for your language. Examples shown for Rust and TypeScript.

# 1. Unsafe / raw operations
#   Rust:       unsafe
#   TypeScript: @ts-ignore, @ts-expect-error, as any, any cast
UNSAFE=$(grep -rn "{{UNSAFE_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null)
section "unsafe / type suppression" "$UNSAFE"

# 2. Error suppression (unwrap, force-unwrap, non-null assertions)
#   Rust:       .unwrap() .expect(
#   TypeScript: ! (non-null assertion), as Type
#   Python:     bare except, except Exception: pass
UNWRAP=$(grep -rn "{{ERROR_SUPPRESS_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null \
  | grep -v "{{TEST_FILE_PATTERN}}" || true)
section "error suppression outside tests" "$UNWRAP"

# 3. Hardcoded credential-like patterns (language-agnostic)
SECRETS=$(grep -rn -iE '(password|secret|api.?key|private.?key|auth.?token)\s*[=:]\s*["\x27]' \
  "$SRC" --include="*.$EXT" 2>/dev/null)
section "potential hardcoded credentials" "$SECRETS"

# 4. External command execution
#   Rust:       Command::new, std::process
#   Node/Python: child_process, subprocess, exec, spawn
COMMANDS=$(grep -rn "{{COMMAND_EXEC_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null)
section "external command / process execution" "$COMMANDS"

# 5. Network APIs
#   Rust:       TcpStream, UdpSocket, std::net
#   Node:       net.createServer, fetch, http.request
#   Python:     socket, urllib, requests
NETWORK=$(grep -rn "{{NETWORK_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null)
section "network APIs" "$NETWORK"

# 6. File system access
#   Rust:       std::fs::, File::open
#   Node:       fs.readFile, fs.writeFile, path.join
#   Python:     open(, os.path
FILESYSTEM=$(grep -rn "{{FILESYSTEM_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null)
section "file system access" "$FILESYSTEM"

# 7. Explicit failure / crash paths
#   Rust:       panic!, unreachable!, todo!, unimplemented!
#   Node/Python: throw new Error, raise, assert
PANICS=$(grep -rn "{{PANIC_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null \
  | grep -v "//" || true)
section "explicit failure / crash paths" "$PANICS"

# 8. Debug output left in code
#   Rust:       dbg!, eprintln!
#   Node:       console.log, console.debug
#   Python:     print(, pdb
DEBUG=$(grep -rn "{{DEBUG_OUTPUT_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null \
  | grep -v "{{TEST_FILE_PATTERN}}" || true)
section "debug output in source" "$DEBUG"

echo ""
if [ $FOUND -eq 0 ]; then
  echo "### Result: No risky patterns found."
else
  echo "---"
  echo "Review each hit above. Not all are vulnerabilities — context determines risk."
fi
```

<!--
Configuration placeholders:

PROJECT_DIR             — absolute path to project root
SOURCE_DIR              — directory to scan, e.g. src/
SOURCE_EXT              — file extension without dot, e.g. rs, ts, py
UNSAFE_PATTERN          — regex for unsafe/type-suppression, e.g. "unsafe " or "@ts-ignore|as any"
ERROR_SUPPRESS_PATTERN  — regex for error suppression, e.g. "\.unwrap()\|\.expect(" or "!\." 
TEST_FILE_PATTERN       — pattern to exclude test files, e.g. "mod tests|cfg(test)" or "\.test\."
COMMAND_EXEC_PATTERN    — regex for command execution, e.g. "Command::new|std::process" or "child_process|exec("
NETWORK_PATTERN         — regex for network APIs, e.g. "TcpStream|UdpSocket" or "fetch\(|http\.request"
FILESYSTEM_PATTERN      — regex for file I/O, e.g. "std::fs::|File::open" or "fs\.readFile|fs\.writeFile"
PANIC_PATTERN           — regex for crash paths, e.g. "panic!\|unreachable!" or "throw new Error"
DEBUG_OUTPUT_PATTERN    — regex for debug output, e.g. "dbg!\|eprintln!" or "console\.log\|console\.debug"
-->
