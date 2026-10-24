## Security Plan Review: BL-B90 Stage 4 — readback by need

Branch `feature/effector-sequences-stage4`, reviewed detached at `83e2835ce5f1be78238ecbc1c602205b013a9ab2`
("Plan: revise BL-B90 Stage 4 to option B"). The worktree's branch (`worktree-agent-a14ec9aa03551db69`,
`1d02e5e1`) had diverged from this tip — not an ancestor either direction (`merge-base` =
`46f6a3ef`) — so per the dispatch instructions I checked out the named tip detached rather than
fast-forwarding; tree was clean before and after.

Scope reviewed: `plans/effector-sequences/plan.md` §"Stage 4 — readback by need (spec, revised
2026-10-24 — option B)" (S4.1–S4.11) plus the still-valid carried-over sections of the first,
superseded Stage 4 spec (§4.2–4.5 mechanism, §4.6 compatibility, §4.8 tests) that the revised spec
explicitly keeps. No code exists for this stage yet — plan-only, as expected for Mode 1.

**Threat model applied (root `CLAUDE.md`, 2026-10-21): single-user, LAN-only. Realistic attackers
are (1) malicious code in a dependency and (2) an infected LAN machine scanning/probing reachable
ports.** The two new routes (`POST /query/read_args`, `POST /command/watch_args`) and the removed
one (`GET /cockpit_switch/latest`) all sit on `aircraft-layer/src/api/server.py`, which binds
`0.0.0.0` (confirmed: `DEFAULT_HOST = "0.0.0.0"`, `aircraft-layer/src/api/server.py:273`) — the
LAN-reachable boundary. Everything behind it (the collector↔Export.lua TCP/UDP sockets) binds
`127.0.0.1` and the TCP listener is `listen(1)` (confirmed: `collector/server.py:130,200-201`,
`collector/command_sender.py:64,258`), so a LAN actor cannot reach Export.lua directly or spoof a
reply on that socket — only the collector process itself ever holds that connection.

### Dependencies Checked

**No new dependency.** Ran `/extract-plan-deps plans/effector-sequences/plan.md`: `aircraft-layer`
is declared stdlib-only, matching the plan's own text (§4.1/S4.2 use `argparse`, `re`, `secrets`,
`threading`, `hashlib` — all stdlib). No `pyproject.toml` change anywhere in the diff tree. The
`ArgReadBroker`'s `secrets.token_hex(6)` for `read_id` generation is the one new stdlib import of
note — correct choice (CSPRNG, not `random`) for a value used as a correlation key, though given
below (Design Findings) it is server-generated and never attacker-influenced, so this is good
practice rather than a requirement.

### Design Findings

| Area | Assessment | Severity |
|---|---|---|
| Inbound validation, both paths | `parse_arg_list` (Lua) and the `api/server.py` POST validators share the same bounds — non-bool ints, 0..4095, deduped, ≤64, whole-op reject on any bad token — stated once and enforced on **three** sides (Lua, collector API, and `SequenceFile.read_args`'s load-time ≤64 check, S4.3) rather than copied ad hoc. `read_id`/`watch_id` are bounded `[%w_]{1,16}` on the Lua side. This is the correct shape and nothing here needs a change. | None |
| Per-frame bound on reads | `MAX_READS_PER_FRAME = 4` caps what a flood of `read_args` ops can make one DCS frame spend; `watch_args` installs are O(1) state writes with no device read, so leaving that op uncapped in the per-frame drain loop is reasoned, not an oversight (matches the existing unbounded-but-cheap posture of `cockpit_switch` writes in the same loop). | None |
| `read_id` correlation / spoofing | **Not exploitable as asked.** `read_id` is minted by the collector's broker itself (`secrets.token_hex(6)`), never taken from the LAN-facing POST body, so a LAN caller cannot choose or predict it to collide with another outstanding request. The only channel that can reply with a `read_id` line is the single loopback TCP connection Export.lua holds (`listen(1)`), which a LAN actor cannot open a second connection to. A late reply (slot already removed on timeout) is explicitly dropped. | None |
| Broker resource exhaustion | The 8-outstanding cap plus instant `503` on a 9th prevents unbounded slot growth from a request flood; a `0.25 s` wait bounds how long one HTTP worker thread blocks per call. `threading.Event.wait(timeout)` does not raise, so the two paths the Co-moving Fields table lists (reply arrives / timeout elapses) are the only paths a slot can exit through — no third, exception-driven path that would leak a slot was found. No change needed. | None |
| `POST /query/read_args`, `POST /command/watch_args` body size | Both inherit the existing unbounded-`Content-Length`-read shape (`AC-B11`'s family). The plan explicitly names both for addition to `AC-B11`'s list (S4.5, S4.4) rather than forking a one-off cap — consistent with how `BL-B66`'s `/command/cockpit_switch` was handled, and `AC-B11` itself rates this low/low under this project's threat model. Not blocking, per that precedent. | Low, not blocking (tracked via `AC-B11`) |
| **One-shot `read_args` response is not validated for finiteness/type before use** | `AircraftLayerClient.read_args(args) -> dict[str, float]` (S4.2) is specified only as "raises `AircraftLayerError` on any non-200" — no validation step is described before its return value becomes `cursor.snapshot = values` (S4.3), which R12's self-check and D3's condition evaluation then compare directly against row targets. **This is the exact recurring category this codebase has already hit three times in one day** (`dod/project_recurring_unguarded_nonfinite_float_before_conversion.md`, confirmed in agent memory): a raw float crossing a trust boundary with no `math.isfinite`/non-bool guard, either raising downstream or silently corrupting a comparison (`NaN != target` is `True` in Python, so a corrupted "unknown" value would read as "differs" and trigger a write). The plan already specifies exactly this guard for the *continuous* feed (`WatchedArgsState.from_dict`, S4.4/§4.4: "Every value must be a finite, non-bool number") — it is simply missing from the parallel one-shot path this revision adds. Under this project's threat model the realistic source of a bad value is attacker class (1) (a compromised aircraft-layer/collector dependency) or a plain bug in Export.lua/the collector forwarding path, not a LAN actor directly (the HTTP response is not attacker-supplied input in the usual sense) — so impact is bounded (worst case: an absolute-position effector gets written when it shouldn't, or a row skips that shouldn't — never an escape from the curated registry's finite device/cmd/value set, per `security-stage1-2.md`'s already-accepted posture). Probability and impact are both low-to-moderate, but the fix is cheap and the pattern is exactly the one this project keeps re-discovering at Reviewer/Security instead of at plan stage. | **Required change** |

### Verdict

CHANGES REQUIRED

### Required Changes

1. **Specify finiteness/type validation on the one-shot read response before Stage 4 is
   implemented.** `AircraftLayerClient.read_args`'s `dict[str, float]` (S4.2) must be validated the
   same way `WatchedArgsState.from_dict` already is (S4.4/§4.4): every value a finite
   (`math.isfinite`), non-bool number, every key a decimal string in 0..4095, count ≤64 — reject
   (raise `AircraftLayerError`, the same posture the rest of this call already uses) rather than
   pass a NaN/Inf/bool straight into `cursor.snapshot`. Add this as an explicit line in S4.2 or
   S4.3, and an explicit test case alongside E1/E2 (S4.7) mirroring the existing `isfinite`
   mutation test already specified for the continuous feed (plan.md:1284, "a value that is
   NaN/`inf`/bool... *Mutation*: drop `isfinite`").

Nothing else in this stage's design needs to change. The validation story elsewhere (shared
per-op bounds in three places, the `read_id` correlation design, the broker's slot lifecycle, and
the deliberate choice to leave `watch_args` installs uncapped per-frame while capping `read_args`
reads) is sound and matches this project's existing LAN-boundary conventions; once Required Change
1 is folded into the spec, this plan is ready for Implementer.
