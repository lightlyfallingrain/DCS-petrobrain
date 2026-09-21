---
name: visual-smoke-test
description: Run/build the app, capture visual output, and check it against a project checklist. Use when the Reviewer (or any agent) needs to verify the app actually runs and renders correctly, not just that the code compiles.
type: user-invocable
---

Prove the app runs and looks right — not just that it compiles. Two field projects built ad hoc
versions of this (a screenshot binary, a Playwright driver script) because code review alone never
catches a black screen, a crash on launch, or a misplaced element.

Placeholders to fill in before use:
- `{{RUN_APP_COMMAND}}` — command that builds/starts the app (e.g. `cargo run --bin screenshot -- <path>`, `node .claude/skills/visual-smoke-test/run.mjs --ss smoke`)
- `{{SCREENSHOT_OUTPUT_PATH}}` — where the capture lands (e.g. `debug/screenshot.png`, `/tmp/shots/smoke.png`)
- `{{SMOKE_TEST_CHECKLIST}}` — project-specific bullet list of what "looks right" means (expected objects visible, background color, no stray geometry, elements at expected positions, etc.)

## Steps

1. **Run** the app/capture command (cold builds can be slow — use a generous timeout, e.g. 120-180s):
   ```
   {{RUN_APP_COMMAND}}
   ```
2. **Read** the screenshot visually:
   ```
   Read: {{SCREENSHOT_OUTPUT_PATH}}
   ```
3. **Check** against the project checklist:

   {{SMOKE_TEST_CHECKLIST}}

4. **Report** what you see and whether it passes. Treat a failed visual check the same as a failed
   test — block the review, don't just note it.

## Notes

- Use a timestamped or named output path per run to avoid overwriting previous captures.
- If the project is interactive (keypresses, mouse, multi-step flows), extend the run command with
  a scripted driver rather than trying to automate this by hand each time — see the field examples
  this skill generalizes from (a Bevy screenshot binary; a Playwright-driven Electron script) for
  the shape such a driver takes.
