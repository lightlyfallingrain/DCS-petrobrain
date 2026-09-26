## Security Deep Analysis: sortie-2026-09-26-fixes

Branch `fix/sortie-2026-09-26`, commit `63684c4` (the fully-reviewed state, including the one
required doc fix from Reviewer's `review.md`), diffed against `main` three-dot
(`git diff main...63684c4`) since both sides merged `main` separately during development. Read
`decisions.md` (binding spec), `plan.md`, `implementation.md`, and `review.md` before reading code.
Scope per project direction (root `CLAUDE.md` "Agents"): single-user, LAN-only, active development —
this is a crash-surface / no-omniscience / unbounded-growth pass over `body-layer`'s new belief-state
bookkeeping, not a hardening audit of a public service. No prior Security pass exists for this
feature (this is the first).

### CVE Status

No new or changed dependencies anywhere in the diff (`git diff main...63684c4 --stat` against every
`pyproject.toml`/lockfile in the repo is empty). `body-layer` stays stdlib-plus-in-process-world-model
per its own `CLAUDE.md`; the new imports (`perception.cockpit_mask`, `perception.geometry.
body_relative_direction`, `perception.gaze.SCAN_CYCLE_PERIOD_S`) are all pre-existing modules in the
same subproject, already exercised by other call sites (detection-time visibility, cockpit-visibility
plan). Nothing to check against an advisory database.

| Package | Version | Advisory | Severity | Affected in This Project |
|---|---|---|---|---|
| (none — no dependency changes) | — | — | — | — |

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/contacts.py`, `_callout_may_speak` (new) | New function on the spontaneous-callout path, computed every tick per contact | Pure computation over already-validated internal state (`ownship`'s fields are runner-owned floats, `contact.last_position` is a property that always returns a `GeoPosition`, never `None`). `body_relative_direction`/`is_visible` are pre-existing, already-tested primitives reused unchanged from the cockpit-visibility feature; `body_relative_direction`'s own docstring documents the degenerate `observer == target` case returns `(0.0, 0.0)` rather than raising. No new exception surface. | None. |
| `body-layer/src/logger.py:1392-1414` (`already_on_target` / carve-out) | New branch in the poll-loop command-lowering glue | Sits entirely inside the pre-existing broad `try/except Exception: logger.exception(...); continue` that wraps the whole crew-text poll cycle (confirmed by reading lines ~1341-1421 — the new block is nested inside that `try`, added by `plans/watch-reporting/`'s security review as the fix for exactly this class of risk). Even a hypothetical defect in the new comparison degrades to "one skipped poll cycle, logged," not a dead poll thread. | None — pre-existing mitigation already covers the new code. |
| `body-layer/src/belief/optic_policy.py` — `pending_attempted_at_range_m`, `attempted_at_time_sim`, `look_contact_id` | Dict-keyed / scalar new `OpticState` fields; task asked specifically whether these can grow unbounded or leak across removed contacts | `pending_attempted_at_range_m` is transient: populated at SCANNING→GLASSING, and unconditionally cleared to `{}` on every path back to SCANNING (`_back_to_scanning`, called by both the interruption and natural-end branches) — bounded by one look's envelope, never accumulates across looks. `attempted_at_time_sim` accumulates per-`contact_id` exactly like the pre-existing `attempted_at_range_m` it is the twin of — same growth shape, already accepted by the codebase's own comment ("Contacts are never removed: the map is bounded by how many distinct contacts one sortie produces"). `look_contact_id` is a single `Optional[str]` scalar, not a collection — no growth risk at all. Contacts themselves are never removed from `ContactStore` (grep confirms no `del`/`.pop()` on the contact dict anywhere in `contacts.py`), so "leaking across removed contacts" does not apply — there is no removal to leak across, for this field or any pre-existing one. This is an existing, accepted design bound (one sortie's worth of distinct contacts), not a new exhaustion surface introduced by this branch. | None — same accepted bound as the pre-existing `attempted_at_range_m`. |
| `body-layer/src/belief/contacts.py` — `Contact.last_observable_sim` (new field) | Per-`Contact` field, not a dict | Grows 1:1 with the number of `Contact` objects — identical lifecycle to every other field already on `Contact` (`los_masked_since_sim`, `last_class_raw`, etc.). Not a new resource-exhaustion class distinct from the object it lives on. | None. |
| `body-layer/src/belief/crew_console.py` — `last_command_target_contact_id` (new field) | Single `Optional[str]` scalar, reset at the top of every `handle_command` dispatch | No growth risk. Verified the reset placement (`self.last_command_target_contact_id = None` before dispatch) is what the plan's own "stale value from an earlier `follow` can't leak into an unrelated later command" claim requires — confirmed by reading the diff, not just the docstring. | None. |
| `body-layer/src/belief/crew_console.py` — `_handle_utterance`'s `_note_player_command()` move | Command-dispatch logic change (Fix C) touching player-utterance-derived control flow | The moved call only changes *when* an interrupt is counted (inside `disposition == "handled"` vs. unconditional); it does not change what data flows where. No new parsing of untrusted transcript content — `parse_utterance` itself is unchanged. `follow`'s resolved `contact_id` (stored into `last_command_target_contact_id`) comes from `_resolve_follow_target`'s existing validated lookup against the contact store, not a raw string echoed from speech. No injection-shaped path exists here (dict keys, not code/SQL/shell). | None. |
| No-omniscience / information-disclosure check (Decision 1 & 3) | Observability gate scope | Confirmed by grep: `route_event`/`_render_lifecycle_text` gained no visibility parameter, and no call from the gate (`_callout_may_speak`) reaches `describe_contact`/`render_contact_report` (the query/answer path). This matters here specifically because a gate implemented in the wrong place could either (a) leak knowledge Petrovich shouldn't have by exempting a path from the check, or (b) suppress a legitimate future query answer by gating too broadly — Decision 3 calls this out explicitly as a requirement, not just a style preference. The diff does the opposite of a disclosure risk: it *closes* a gap where an unvalidated `route_event` call let spontaneous callouts speak about physically-unobservable contacts (the reported defect), and does so without touching the query-answer path at all. This is a fix in the no-omniscience direction, not a new exposure. | None. |

### SBOM

Not regenerated — no dependency manifest changed on this branch (confirmed above; `body-layer`
remains stdlib-plus-in-process-world-model-import, no new third-party package).

### Verdict

APPROVED — NO REQUIRED FIXES.

This is internal, deterministic belief-state logic reached only via the existing LAN HTTP surfaces
(aircraft-layer, audio-adapter) that already carry their own wire validation; nothing in this diff
adds a new external-facing input path. The one thing worth stating plainly: the task asked me to
check whether the five new dict/scalar fields could grow unbounded or leak across removed contacts,
and the honest answer is that the project already accepts unbounded-by-sortie growth for this exact
shape of map (`attempted_at_range_m`, pre-existing, documented as intentional) and contacts are never
removed at all in this codebase today — so there is no new exhaustion class here, only the same
accepted one extended to two more fields of identical shape. If unbounded per-sortie growth of these
maps ever becomes a real concern (e.g. very long sorties), that is a pre-existing design point
affecting `attempted_at_range_m` too, not something introduced by this branch — worth a `todo/todo.md`
note if the user wants it tracked, not a blocker here.

Reviewer's one required fix (the `decay.py` docstring naming the wrong/never-built field) is already
present correctly in `63684c4` — confirmed by reading it directly, not assumed from `review.md`'s
account.

### Required Fixes

None.
