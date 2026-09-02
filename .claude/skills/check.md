---
name: check
description: Run a fast compilation/syntax check without a full build
type: user-invocable
---

Run `mypy world-model/src` in `/Users/sg/Code/DCS-petrobrain` and report the result.

- If it exits 0: print **PASS** — no errors
- If it exits non-zero: print **FAIL** and show all error output

This is the fast feedback gate (no full build / codegen). Use it after each logical implementation step to catch errors early. Use `/done` only when the full feature is ready for the Definition of Done checklist.
