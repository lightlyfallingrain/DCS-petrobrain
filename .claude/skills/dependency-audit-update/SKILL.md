---
name: dependency-audit-update
description: Check for outdated dependencies and known vulnerabilities, apply safe upgrades, run tests, and commit lockfile changes. Use when the user asks to update dependencies, audit for vulnerabilities, or check for outdated packages.
---

# Dependency Audit & Update

Standard flow for keeping dependencies current without breaking anything.

Placeholders to fill in before use:
- `{{DEPENDENCY_OUTDATED_COMMAND}}` — lists outdated packages (e.g. `npm outdated`, `cargo outdated`)
- `{{DEPENDENCY_AUDIT_COMMAND}}` — vulnerability scan (e.g. `npm audit`, `cargo audit`)
- `{{DEPENDENCY_AUDIT_FIX_COMMAND}}` — safe auto-fix for vulnerabilities (e.g. `npm audit fix`, `cargo update -p <pkg>`)
- `{{DEPENDENCY_UPDATE_COMMAND}}` — upgrade within existing semver range (e.g. `npm update`, `cargo update`)
- `{{LOCKFILE_PATHS}}` — manifest + lockfile to stage (e.g. `package.json package-lock.json`, `Cargo.toml Cargo.lock`)

## Steps

1. **Check outdated packages**

   ```
   {{DEPENDENCY_OUTDATED_COMMAND}}
   ```

   Note current vs wanted vs latest for each package.

2. **Run security audit**

   ```
   {{DEPENDENCY_AUDIT_COMMAND}}
   ```

   Review findings. If vulnerabilities exist:

   ```
   {{DEPENDENCY_AUDIT_FIX_COMMAND}}
   ```

   Do **not** force a fix that pulls in a breaking major version. If the safe fix leaves
   unresolved vulnerabilities requiring a forced/major upgrade, stop and report them to the user
   instead of forcing.

3. **Upgrade within range only**

   For each outdated package, upgrade to the version within the existing semver range, not a
   major bump:

   ```
   {{DEPENDENCY_UPDATE_COMMAND}}
   ```

   Packages where the latest release is a major version bump above the current range are left
   alone — report them to the user as candidates for manual major-version review (breaking API
   changes are common).

4. **Run tests**

   Run the project's full quality gate (`{{FORMAT_COMMAND}}` / `{{LINT_COMMAND}}` / `{{TEST_COMMAND}}` per
   `CLAUDE.md`). Do not proceed to commit if anything fails — stop and report the failure.

5. **Commit**

   Once checks pass, commit the manifest and lockfile:

   ```
   git add {{LOCKFILE_PATHS}}
   git commit -m "chore: update dependencies (in-range) and fix audit vulnerabilities"
   ```

   Use a `Co-Authored-By: Claude` trailer per this project's commit convention.

## Reporting back

At the end, summarize to the user:
- Packages upgraded (old → new version)
- Vulnerabilities fixed
- Any major-version bumps left for manual review, with current vs latest version
- Any unresolved audit findings that would require a forced/breaking upgrade
