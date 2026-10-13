## Security Deep Analysis: bounded-fold-displacement (BL-B58 option 2 / BL-B59)

Reviewed on `fix/bl-b59-retention-hysteresis` at `078232b` (Reviewer-approved, no required fixes).
Scope per the orchestrator's instructions: the seven-commit diff (`da15972..078232b`) touching
`body-layer/src/belief/{position_belief.py,contacts.py,groups.py}` plus tests, `STRUCTURE.md`, and
plan documents.

### Dependency Status

No dependency change. `git diff main..HEAD -- '*/pyproject.toml'` is empty across every
subproject.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `position_belief.py:652-701` (`clamp_fold_displacement`) | NaN propagation, not a crash | The function's own "identity when nothing to bound against" promise does not hold for a NaN mean. Demonstrated directly: `clamp_fold_displacement(fused=PositionEstimate(x=nan, z=300, …), prior=PositionEstimate(x=100, z=200, …), max_displacement_m=10.0)` returns `x=nan, z=200.0` — the comparison `displacement_m <= max_displacement_m` is `False` for `displacement_m=nan` (Python NaN-comparison semantics), so it falls into the clamp branch, computes `scale = 0.0` (since `displacement_m > 0.0` is also `False` for NaN), and then `dx * scale = nan * 0.0 = nan`, writing NaN into the adopted mean permanently — unlike `clamp_to_detection_envelope` immediately above it in the same module, whose `range_m(...) <= max_range_m` check *incidentally* catches the same NaN case and holds the clean prior instead (confirmed by the same probe). **Not currently reachable in the real call path**: `Contact.record` always calls `clamp_to_detection_envelope` first and feeds its output into `clamp_fold_displacement`, and I confirmed by direct probe that `clamp_to_detection_envelope` scrubs a NaN mean back to the prior's clean values before `clamp_fold_displacement` ever sees it. The gap is in the function's own contract, not in today's wiring — a future caller (a test fixture, a second call site, a refactor that reorders the two clamps) would reintroduce it silently, since nothing documents or enforces that ordering dependency. | See risk below — not a blocker given current reachability. |
| `contacts.py:1143-1152` (the `fold_displacement_m` budget update) | NaN into `max()` | Confirmed separately: `max(contact.fold_displacement_m, math.hypot(dx_nan, dz))` does **not** poison the budget, because Python's `max(a, b)` returns `a` whenever `b > a` is `False`, which includes `b = nan`. So even if a NaN displacement were computed, the budget field itself (and therefore `fold_budgets` on the group trace) stays clean — only the position mean is at risk, not the diagnostic field. | None. |
| `position_belief.py:686-693` (zero-bound / zero-elapsed path) | Division | `scale = max_displacement_m / displacement_m if displacement_m > 0.0 else 0.0` — the only way to reach the division is `displacement_m > 0.0`, so no divide-by-zero. A negative-elapsed percept (timestamped before the prior's last fuse) is floored at the call site (`contacts.py`'s `max(0.0, percept.t_sim - prior_position.fused_at_sim)`), producing `max_displacement_m = 0.0`; traced through the clamp this correctly pulls the fold fully back onto the prior point rather than erroring or doing nothing unexpected — physically correct (no elapsed time, no plausible travel; plan §2c). | None. |
| `position_belief.py:656-658` (identity branches) | `None`-bound / no-prior correctness | `max_displacement_m is None` (every pre-`BL-B58` call site) and `prior is None` (founding look) both return `fused` unchanged without constructing a new object — confirmed by reading and by the reviewer's own Stage-1 behaviour-neutrality check (1697/1697 passed, byte-identical, before Stage 2 switched the bound on). No path where a bound was intended but silently treated as absent, or vice versa: `ambiguous_fold` is the only thing that computes a non-`None` bound, and it is keyword-only, defaulting `False`. | None. |
| `contacts.py:1143-1152`, `position_belief.py:652-701` | Unbounded growth | `max()` genuinely bounds the field to the worst single unretired fold rather than an accumulating sum — confirmed by the dedicated test (`test_fold_displacement_m_tracks_the_worst_single_fold_not_an_accumulated_sum`) and by the reviewer's own mutation check (reverting to `+=` fails that test). `fold_budgets` on the group trace (`groups.py:1493`) reads `Contact.fold_displacement_m` directly per member, with no separate accumulator of its own — it cannot reintroduce unbounded per-contact state because it holds no state at all, it's a read at reconcile time. | None. |
| `position_belief.py:652-701`, `contacts.py:555-580` | No-omniscience | The clamp's bound is `plausible_speed_mps(contact.last_class_raw via object_model.profile_for) × elapsed-since-last-fuse`, both resolved from the contact's own believed state (`contact_growth_rate_mps`) and percept timestamps — no DCS `object_type`, ground-truth position, or real velocity is read anywhere in this path. Confirmed by reading `position_belief.py`'s own module docstring (explicit design constraint: `PositionEstimate` carries no classification reference) and `clamp_fold_displacement`'s signature, which takes only two `PositionEstimate`s and a float. | None. |
| `groups.py:1493` (`fold_budgets`) | New I/O content, not a new I/O surface | Adds one more field (`[[contact_id, rounded float], ...]`) to the record already written by `--group-trace`'s existing writer (`group_trace_log.py`), whose I/O posture (operator-supplied path, graceful `OSError` degrade, `json.dumps(..., default=str)`, never re-parsed) was established and accepted by `plans/group-contact-identity/security-review.md`. No new write surface, no new trust boundary. | None. |

### Diagnosability (the specific question asked)

`fold_budgets` lets an operator read, per cluster-trace record, each member contact's own
worst-unretired-fold magnitude (post-clamp, rounded to 0.1 m) — which contact in a cluster carried
a large recent fold, and roughly how large. That is useful and matches the existing `--group-trace`
pattern BL-12's security pass already judged "visible, partially bounded."

It is **not** a self-labelling signal. The record carries only the clamped value, not the
unclamped fuse distance or a boolean "this fold hit its bound." An operator reading `fold_budgets`
alone cannot distinguish "this fold was large and got capped at its class-speed bound" from "this
fold was large and the bound happened not to bind" — they'd have to separately reconstruct
`plausible_speed_mps(class) × elapsed-since-last-fuse` for that contact and compare it against the
logged value by hand. So: a *clamped* position is diagnosable as "unusually large, worth a second
look," but *whether the clamp specifically fired* is not directly readable — the same shape of
partial visibility BL-12 already accepted for the analogous eviction case, not a regression from
it.

### Verification

`body-layer`: `pytest tests -q` — 1702 passed, 4 xfailed (matches the stated state at `078232b`).
`git diff main..HEAD -- '*/pyproject.toml'` — empty (no new dependency, any subproject).
`audio-adapter` unaffected by this diff (no files touched there).

### Verdict

**APPROVED.**

No exploitable vulnerability in the feature diff, and no in-scope defect reachable through the
real call path. One low-risk design-contract gap is worth recording (and fixing cheaply) rather
than blocking on:

**Finding:** `clamp_fold_displacement` is not actually identity-safe under a NaN mean, despite its
docstring's identity claim — it silently writes NaN into the adopted position rather than holding
or raising. It is saved today only because its one real caller always routes through
`clamp_to_detection_envelope` first, which happens to scrub NaN via comparison semantics (not by
documented design).
**Location:** `body-layer/src/belief/position_belief.py:652-701` (and the `contacts.py:555-580`
call site that establishes the ordering that currently protects it).
**Probability:** low — reaching a NaN mean requires a degenerate `PositionEstimate` upstream (e.g.
a zero/NaN declared sigma in `PositionUncertainty`), which this project's own perception layer does
not produce under normal operation; this is single-player, LAN-only, DCS-sourced telemetry, not
externally-untrusted input.
**Impact:** low-medium if it ever fires — not a crash, but a permanently corrupted believed
position for that contact (every subsequent fold's `prior.x` stays NaN), silently, with no
exception and no log line pointing at the cause.
**Recommended action:** add an explicit `math.isfinite` guard at the top of
`clamp_fold_displacement` that returns `prior` (held, matching `clamp_to_detection_envelope`'s own
posture) when `fused.x`/`fused.z` is not finite, so the function's identity/safety claim is true on
its own terms rather than borrowed from caller ordering. One function, one guard clause, one
acceptance test (NaN mean in, prior out) — implementable as a small follow-up, not a reason to
re-open this review.

Options:
  (A) Ignore — document acceptance of this risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — implementer makes the one-line guard change, re-enters Implementer → Reviewer → DoD
  (D) Stop — do not proceed until resolved

My recommendation: (B) or (C) — cheap to fix, not urgent given current unreachability, but worth
closing before any future refactor reorders the two clamps.
