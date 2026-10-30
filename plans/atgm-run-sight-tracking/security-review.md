## Security Deep Analysis: atgm-run-sight-tracking

Reviewed at `5794a105989b462ec52ccda8104e3fa0addde02d` (branch `fix/atgm-run-sight-tracking`),
via literal-sha diff against merge-base `a0e8bf1108123732870bba65554b28ca53806271` — the
worktree's own HEAD (`f7c1e70f`, from `origin/main`) had diverged, not merged, per the
dispatching prompt. Commits reviewed: `b912a081` (fix: belief aim uses remembered target
altitude) and `cc6dafac` (feat: bearing-line depression search + "Tracking." callout),
plus the mechanical `5794a105` review-approval commit.

### Dependency Status

No dependency change. Confirmed by diff — no `pyproject.toml`, `requirements*.txt`, lock file,
or any manifest touched in either commit. The only Python surface touched is
`body-layer/src/belief/{attack_run,crew_console,optic_policy,speech}.py` and `body-layer/src/body.py`,
all pre-existing modules. `remembered_target_alt_m` is a rename (drop leading underscore to make
an existing private helper a second module's sanctioned import) — no new import path, no new
package.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `belief/optic_policy.py` `_bearing_line_search_offsets` | tunable-derived step size (`SIGHT_LOCK_SEARCH_STEP_OVERLAP_FRACTION` → `step_deg`) used as a loop-advance and later a modulo divisor | `step = max(step_deg, 0.01)` floors it before use in the `while n * step <= band_half_width_deg` growth loop, so `step_deg == 0` (overlap fraction → 1.0, or a zero-FOV optic) cannot produce an infinite loop or a stuck index. `SIGHT_LOCK_SEARCH_STEP_S` (the other place a tunable is a divisor, in the `now_sim - search_since_sim) // SIGHT_LOCK_SEARCH_STEP_S` index calc) has a hard `lo=0.3` bound in its `tuning.real(...)` declaration, so it cannot reach `0.0` through the tunable path at all. | None — false positive, verified safe by construction |
| `belief/optic_policy.py` `SIGHT_LOCK_SEARCH_BAND_HALF_DEG` / `SIGHT_LOCK_SEARCH_STEP_OVERLAP_FRACTION` / `SIGHT_LOCK_SEARCH_STEP_S` | new tunables (`#:` doc, `lo`/`hi`, rendered in `defaults.toml`) | All three declared via `tuning.real(...)` with sane `lo`/`hi` bounds (`5.0..35.0`, `0.0..0.8`, `0.3..5.0`); `defaults.toml` rendering checked against source — matches. This is the `X-T26` tunable-constant pattern applied correctly. Bounds are behavioural, not safety-critical for this codebase's own definition (worst case at any bound combination is a wasted dwell cycle — a player-experience question, see below — never a crash or unbounded loop per the floor above). | None |
| `belief/optic_policy.py` `_decide_sighting_locked` | no new external/untrusted input path | Elevation/azimuth here are derived from `found.elevation_deg`/`found.azimuth_deg` (existing `LookTarget` data already sourced from in-process `ContactStore`/DCS telemetry over the existing aircraft-layer channel — not a new network or file surface) plus the tunable offsets above. No new deserialization, no new socket, no new file path. | None |
| `belief.attack_run.remembered_target_alt_m` / `body._look_target_position` | visibility widening (module-private → public) | A pure rename exposing an existing, already-reviewed pure function (`percept.ownship_at_observation.alt_m + relative.up_m`) to a second in-module caller. No new data flow from outside the process; same trust boundary as before. | None |
| `belief.crew_console.drain_sight_lock_tracking` / `belief.speech.render_tracking` | new speech line, no parameterization | `render_tracking()` returns a fixed literal `"Tracking."` — no interpolation of contact names, transcript text, or any model/world-derived string into this line, so no prompt-injection or format-string surface here (unlike, say, a contact-name callout). | None |
| `body.py` `_sight_lock_seen` | new boolean derived from existing in-process state (`SightHead.aim_source`, `atgm_run_state.contact_id`) | Pure read of already-trusted in-process runtime state; no new external input. | None |

No `eval`/`exec`/`subprocess`/`os.system`/`pickle`/`yaml.load`/`__import__`/socket bind-or-listen
patterns appear anywhere in the diff (checked by pattern grep over the full diff, zero hits).
No new listening sockets, no new HTTP endpoints, no new file I/O, no new deserialization of
externally-sourced bytes. The feature is entirely internal belief-state logic operating on data
already flowing through this process's existing trust boundary (DCS telemetry via the existing
aircraft-layer client) — nothing here changes what a LAN port scanner or a malicious dependency
could reach.

**LLM prompt injection:** not applicable. This feature touches no text the model reads (no
transcript, no briefing text, no tool result) — it is deterministic belief/sight-aim arithmetic
and one fixed speech literal.

### Passed to Reviewer (not my verdict — noted only)

- Optional refinement already named in `plans/atgm-run-sight-tracking/review.md`: the bearing-line
  search's resolved elevation steps are not filtered through `within_field_of_regard`, so a step
  beyond the gimbal's mechanical limit parks at the stop for a full dwell rather than being skipped.
  This is a physical-limit/player-experience question (what the sight actually does in the
  cockpit), already surfaced by Reviewer as optional, not a security finding.
- Also already named there: no enforced relationship between `SIGHT_LOCK_SEARCH_STEP_S` and
  `belief.sight_head.SLEW_EL_DPS`, so a future tuning change could set a sweep the sight physically
  cannot keep up with. Behavioural coupling, not a crash/injection/access risk — Reviewer's
  territory, already flagged by Reviewer as optional.

### Verdict
APPROVED

### Required Fixes (if any)
None.

### Findings filed / not filed
No findings rose to a backlog-worthy item — both code findings above were verified false
positives (the `step = max(step_deg, 0.01)` floor and the `lo=0.3` bound on
`SIGHT_LOCK_SEARCH_STEP_S` already prevent the division/infinite-loop case this pass checked
for), and the two player-experience items are Reviewer's own optional refinements, already on
record in `plans/atgm-run-sight-tracking/review.md` — not re-filed here. Nothing in this batch
needs a `BL-B<n>` entry.
