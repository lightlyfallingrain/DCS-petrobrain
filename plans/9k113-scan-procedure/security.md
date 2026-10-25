## Security Deep Analysis: 9k113-scan-procedure (BL-B89 Stage 1)

Base `main` at `e9fb4a2b`, feature tip `4c9d23212539f4ea89e3a312412f4066c0e1641d`
(`feature/9k113-scan-procedure`). Fast-forwarded this worktree from `e9fb4a2b` to the named tip;
clean ancestor fast-forward, no divergence, no uncommitted changes.

### Dependency Status

No dependency change. Changed files are entirely within `body-layer/src/{belief/optic_policy.py,
body.py}`, `body-layer/src/perception/gaze.py`, and the generated `body-layer/config/defaults.toml`
— no new import, no new package, no new network client, no new file format. `extract-plan-deps`
(already run for the plan review) found nothing, and the actual diff confirms it: no new `import`
line in any changed source file.

### Surface Check

Grepped the diff itself for every in-scope pattern (`eval(`, `exec(`, `subprocess`, `os.system`,
`open(`, `socket`, `requests.`/`urllib`, `pickle`, `__import__`) — zero hits. Consistent with the
plan review's own assessment: this stage is a pure in-process state-machine change over structured
numeric/enum state (ranges, bearings, contact levels, sim time) that was already produced by
reviewed upstream code. No new listener, no new HTTP endpoint, no new file I/O, no text an LLM
reads (nothing here touches voice/speech — Stage 2's voice-command parsing is explicitly deferred,
not built this round). The scope stated in `security-plan.md` ("none" across code execution,
file-system access, network/LAN surface, prompt injection, secrets) holds unchanged against the
actual diff.

### Tunable Bounds

Four tunables touch this stage, three new/changed in `belief/optic_policy.py` and one new in
`perception/gaze.py`:

| key | default | lo | hi | notes |
|---|---|---|---|---|
| `SIGHT_SEARCH_NEAR_M` | 1500.0 | 500.0 | 4000.0 | lowered from 2333.0/1000.0 |
| `SIGHT_SEARCH_WIDE_MID_M` | 4000.0 | 2000.0 | 6000.0 | new, replaces `SIGHT_SEARCH_MID_M` |
| `SIGHT_SEARCH_WIDE_FAR_M` | 8000.0 | 4000.0 | 15000.0 | new, replaces derived `_SIGHT_WIDE_SEARCH_FAR_M` |
| `SIGHT_AHEAD_WINDOW_DWELL_S` | 30.0 | 5.0 | 120.0 | new, `perception.gaze`, standalone (not an implementation.md deviation flagged by the Implementer, no coupling to any other key) |

All four are AST-literal `lo`/`hi` bounds per the `X-T26` convention, correctly rendered in
`body-layer/config/defaults.toml` (checked the rendered file, not the source comment — the
generator's known trap is emitting only the first sentence of a multi-sentence `#:` comment, and
here the full warning, including the cross-key coupling note, is present verbatim at
`optic_policy.py:300-302` and reproduced in the rendered file's own comment for `SIGHT_SEARCH_
NEAR_M`/`SIGHT_SEARCH_WIDE_FAR_M`).

**Cross-key coupling, already flagged by the plan review, confirmed present and confirmed bounded
in consequence.** No per-key bound stops `SIGHT_SEARCH_NEAR_M` being tuned to 4000.0 while
`SIGHT_SEARCH_WIDE_MID_M` is independently tuned down to 2000.0, producing an inverted/empty
`wide_near` band (and the same shape between `WIDE_MID_M`/`WIDE_FAR_M` and `WIDE_FAR_M`/`FAR_M`).
This is the identical shape already accepted for `belief.decay`'s own documented residual coupling,
and the module-level comment at `optic_policy.py:300-302` states it explicitly rather than leaving
it silent. Applying this project's "rate a fallback by how often it fires when nothing is wrong"
lesson rather than taking the "requires a local tuning edit" framing at face value: the trigger
condition is **not externally reachable** — `config/tuning.toml` is edited only by the single local
user, never by network input, mission data, or any untrusted source — and the measured worst case
(`implementation.md`'s "Notable Discoveries", reviewed independently in `review.md`'s
verify-by-mutation section) is a degraded, non-stalling search: at every altitude/attitude
combination actually driven in tests, at least one leg stays non-empty, `_idle_sight_search`'s
existing leg-skip fallback advances past an emptied leg, and the mandatory per-lap naked-eye pause
still fires regardless. There is no path from this coupling to a crash, a hung poll loop, or a
silently-stuck state — only an emptied search band, which is a correctness/tuning concern already
on the record (plan's own "Decisions Requiring User Input": confirm the band placeholders) rather
than a security finding. Not filed as a new backlog item — it is the same item already named in
`security-plan.md` and in the plan's own text, not a new observation.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| — | — | No in-scope pattern found in the diff (no exec/eval, no shell-out, no new fs/socket surface, no deserialization, no secrets) | None |

### Passed to Reviewer

(Already Reviewer's territory, not re-litigated here — noted only for completeness, carries no
verdict from this role): the altitude/attitude edge cases where `wide_near`/`wide_far` go empty
(800 m AGL/10° nose-up; 1500 m level), and `BL-B98` (sight resumes dead-ahead instead of last
position on glance-away) — both already identified, measured, and filed/disposed in
`review.md`/`implementation.md` by Implementer and Reviewer. These are player-experience/
correctness matters, not security.

### Verdict

APPROVED
