# Pending-flight audit, 2026-10-15

Audit of every roadmap item and acceptance card carrying a flight-waiting marker (`#needs-flight`,
"unflown", "live acceptance outstanding"), cross-checked against everything flown or decided since
each item's own date: `body-layer/logs/dcs-{speech,belief-truth,detection-trace}-*.jsonl` (sorties
2026-10-08, 10-11, 10-15 ×3), the dated sortie-feedback/direction documents in `docs/acceptance/`,
and later roadmap entries that supersede or absorb an earlier question.

**Method note.** Reading the logs directly settled several items no document had closed explicitly
— e.g. a fresh tick-cost measurement against the 2026-10-15 belief-truth log, and a token-presence
check against the 2026-10-15 speech logs to see whether a given voice path was ever actually used.

**Correction pass.** Three verdicts below were revised after re-reading the cited evidence rather
than trusting the first summary of it — the exact trap the task brief named:

- **`BL-B47`** was first called "ANSWERED"/"PARTLY ANSWERED" on the strength of
  `docs/acceptance/2026-10-10-crew-query-path-sortie.md`. That doc runs an offline Python check
  confirming the *code* resolves class-level SAMs, then says explicitly, in its own words, **"In
  the air — UNVERIFIED."** `body-layer/ROADMAP/BL-B47.md:5` itself still says **"UNFLOWN"** and
  carries `#needs-flight` today. Corrected to **STILL OPEN** throughout this file and moved into
  section A.
- **`BL-W12`** was first called "ANSWERED (flown, with downstream findings)" on the claim that
  `BL-B58`/`BL-B59`/`BL-B60` were found by flying this mechanism. They were not:
  `body-layer/ROADMAP/BL-B59.md` says outright **"Fixture-only — no sortie has exercised this
  path"**, and `BL-B58`'s fix is a DoD-passed plan, not a flight log. Corrected to **STILL OPEN**.
- **`BL-13`** was first called "ANSWERED (mechanism exercised)." Direct replay of
  `dcs-speech-20261015-{150739,164451}.jsonl` confirms the pull-summary path (`"describe left"`,
  `"describe right"`, `"describe at eleven o'clock"`, bare `"describe"`) really was used
  repeatedly and successfully across two real sorties — but no document records the pilot's own
  judgement on whether the summary beats enumeration or runs too long in a hover, which is the
  thing the item is actually waiting on. Softened to **PARTLY ANSWERED**.

Everything else in this file was independently cross-checked (including against the real,
gitignored logs at `/Users/sg/Code/DCS-petrobrain/body-layer/logs/`, not just this worktree's view)
and found sound.

---

## Consolidated status, 2026-10-15 evening — read this first

This document was written by one agent, then corrected by three more running in parallel, which
produced two retracted accusations and one genuine contradiction. **The adjudications below were
made against the primitive sources — the real `.jsonl` logs and the roadmap entries — not by
another dispatched agent**, and they supersede anything later in the file that disagrees.

**Two claims made against this document were checked and are false:**

- **"The merged file accuses a correct figure of being fabricated."** No such text exists in it;
  `grep` finds nothing of the kind.
- **"`BL-11`'s `median=1.018s` is fabricated, because the belief-truth log has no timing field."**
  The log indeed has no duration field — but the figure is not read from one. It is the **median
  gap between consecutive `t_sim` values**, which is what a log reduction of a poll loop means.
  Recomputed directly:

  | sortie | distinct ticks | median gap | p90 |
  |---|---|---|---|
  | 2026-10-15 15:07 | 462 | **1.018 s** | 1.81 s |
  | 2026-10-15 16:44 | 450 | 1.020 s | 4.89 s |
  | 2026-10-15 17:55 | 65 | 1.017 s | 3.05 s |

  **One caveat the original row understated:** this is tick *interval*, not tick *cost*. A 1.018 s
  median against a 1 Hz target says the loop is not stalling, which is the right observable. The
  **p90 of 1.8–4.9 s says long gaps still occur** — a real residual, not a closed question.

**User verdicts given directly, 2026-10-15 evening** — these are acceptance decisions, not
inferences:

| item | verdict |
|---|---|
| Rear-hemisphere silence (`BL-11` Stage 0) | **PASS** on the silence itself — *"seems to work"*. **The Danger-exception half is still unchecked**: a threatening unit going astern should still speak. |
| `describe` pull summary (`BL-13`) | **PASS** — *"initial impression from today is it's good. Refine later if needed."* |

**Corrections that verified and are folded in** (from the second audit pass):

- **`BL-W1`** (contact-report flood suppression) and **`BL-W5`** (`cancel` → `confirm`) are
  **ANSWERED** — both graded *pass* in `docs/acceptance/2026-10-05-sortie-feedback.md`'s own
  pass/fail table from a real flight. The earlier "no log evidence" reasoning was invalid:
  **speech logging only began 2026-10-08**, after that sortie, so its absence from the logs proves
  nothing.
- **`docs/acceptance/2026-10-06-callout-observability-sortie.md` carries a wrong instruction** — it
  tells the pilot to check out `fix/callout-observability-gate`, which merged as `24746f5`.
  Following it today would take him *backwards* off `main` and drop every later fix. The check is
  still owed; it must be flown from `main`.

---

## A. Still-open list (what needs checking, in plain language)

Ordered cheapest/most-valuable first. Items 1–5 and 10–12 all ride on **one ordinary ground-attack
sortie** with a mix of grouped contacts, some scanning/reporting, cancelling a command, and one odd
phrase thrown in — nothing about them needs a special setup. Items 6–7 need a deliberate scenario.
Item 8 is a read of logs you already have, not a flying task. Item 9 needs a specific location
(coastal woods NE of Latakia).

1. **Petrovich's free-text answers have never actually been heard.** Every "report"/"describe" so
   far matched a known voice command. Say something that isn't in the command vocabulary (e.g. ask
   a real question) and confirm he answers in his own words rather than "say again" — this is the
   first real test of the brain layer talking to a live model in the air.
2. **A group that pops behind a ridge and reappears should stay the same group**, not become a new
   one. Watch a column or formation go out of sight and come back, and check Petrovich still talks
   about it as the one he already knew.
3. **A dense or tight cluster of contacts (e.g. three+ close together, one air-defence) should not
   silently lose a member when a new contact folds in nearby.** Watch for a group's composition
   suddenly dropping someone it had, especially if that someone was the one flagged as air defence.
   This also covers the group-cohesion rules themselves (`BL-W12`) — a large group shouldn't repeat
   the same roster line every ~11 seconds with only the range changing.
4. **An unprompted callout should never name a clock-hour behind you (5, 6, 7 o'clock)** — except
   that a threatening unit going astern should still get a "Danger" call. Listen specifically for
   silence to your rear, and for the one exception still speaking up.
5. **When a contact is believed to be a SAM only at the general-class level (not yet identified to
   exact type), does Petrovich still treat it as air defence** — same callout behaviour as a
   type-identified one, not silence?
6. **The 9K113 sight has never been turned on in flight at all.** Say "observ on," then check
   whether detection range, position precision, and the handover between naked eye / binoculars /
   sight feel right and natural rather than thrashing.
7. **The attack-run guidance (`engage`/`follow`) has real known bugs from the last two flights**
   and needs the fixes built before it's worth re-flying: the guidance line repeats itself when
   nothing audibly changed, it keeps talking after you fly past or turn away, and "obstructed" gets
   said for a target that's simply too far away rather than actually blocked. Re-fly once those are
   fixed, not before.
8. **(No flying needed — just a look at the Hook's own log next time)**: the live line-of-sight feed
   still misses verdicts on roughly 8% of checks (down from 19% a week ago). Worth deciding whether
   that's good enough now, especially for whatever you're currently aiming at, or whether it needs
   the "always check the thing I'm aiming at first" fix before it matters.

9. **A unit sitting inside forest should not be seen at all, and this has never been tested in the
   air.** Needs a deliberate setup: fly the `--forest-occlusion` flag over the coastal woods
   north-east of Latakia (the densest treed area in the theatre — an ordinary sortie elsewhere
   almost never triggers this gate) with units placed in and at the edge of the treeline. This is
   the same underlying check as item 3's cousin on the backlog side (`BL-B59`/`X-B31`); it rides
   its own dedicated flight, not the ordinary sortie items 1–5 ride on.

10. **Does the pull-summary for `report`/`describe` actually feel right, not just work?** It's
    clearly being used already (confirmed from logs), but nobody has said whether it's shorter/
    better than a plain list, or too long to take in while manoeuvring. Thirty seconds of
    deliberate attention to this the next time you say "describe" would close it.
11. **An old, still-unflown bundle from three weeks back** (callouts stopping correctly when a
    contact is behind the airframe, binoculars getting a retry on a held contact, an unrecognised
    command not lowering the binoculars) and **a second one riding the same unflown card**
    (repeated-contact suppression, and "next valley"/"beyond the ridge" terrain phrasing) — both
    are ordinary flying, no special setup, just overdue. Worth doing on the same flight as items
    1–5.
12. **`"cancel"` then `"confirm"` should actually stop the task** — this exact round trip has not
    been spoken in any flight since the fix (confirmed by checking the logs directly: no "cancel"
    command appears in any of them). One word each way, on any ordinary flight.

**Low priority / skip unless convenient:** the audio-adapter's halved polling rate has no cockpit
effect at all — only worth a look if you happen to run with `--debug` open already.

---

## B. Per-item audit

### Body-layer core milestones

| item | waiting for | verdict | evidence |
|---|---|---|---|
| **BL-11** (tick cost / observability) | Stages 1,2,3b,5: tick median back to ~1.0s, invisible from cockpit, log-reduction only. Stage 4 (live-LOS fail-closed): gate behaves live. Stage 0 (rear-hemisphere callout silence + air-defence exemption): never flown. | **Stages 1/2/3b/5: ANSWERED** — re-ran the same log-reduction against the 2026-10-15 15:07 sortie's own belief-truth log: `median=1.018s` (was 1.424s pre-fix), confirms the fix holds in real flying, not just the 2026-10-06 bench run. **Stage 4 step 2: ANSWERED**, flown 2026-10-08 (roadmap's own "Resolved" note); steps 3-4 needed no separate flight by design. **Stage 0: STILL OPEN** — no sortie feedback mentions rear-hemisphere silence one way or the other. | Measured directly this audit; `body-layer/ROADMAP/BL-11.md` |
| **BL-12** (group contact identity across repositioning) | The specific "column pops behind a ridge, reappears as the same group" scenario. | **STILL OPEN.** Merged 2026-10-12, mechanism has run in every sortie since (10-13, 10-15 ×3) as part of ordinary group handling with no complaint, but no document specifically reports the reposition-and-reappear case being watched for. | `body-layer/ROADMAP/BL-12.md`; no matching mention in any later acceptance/feedback doc |
| **BL-13** (crew query path, `report`/`describe`) | Whether a pull summary beats enumeration, in the cockpit. | **PARTLY ANSWERED** (corrected from ANSWERED — see Correction pass above). The command path itself is clearly working: "describe"/"report" tokens appear repeatedly in the 2026-10-15 15:07 and 16:44 speech logs (`"Describe."`, `"describe left."`, `"describe at eleven o'clock"`, `"What do you see?"` → `report_all`/`report`), used successfully across two real sorties. What remains unconfirmed is the actual thing the item is waiting on: whether the pilot judges the summary as beating enumeration and not too long in a hover — no document records that judgement. | `body-layer/logs/dcs-speech-20261015-{150739,164451}.jsonl` |
| **BL-B47** (air-defence recognised at class level, rides BL-13's card) | Repetition, not silence, for a class-level SAM belief, confirmed in a live callout. | **STILL OPEN** (corrected from PARTLY ANSWERED — see Correction pass above). The cited ground check only verifies the fix offline; its own doc says "In the air — UNVERIFIED," and the roadmap entry itself says "UNFLOWN" with `#needs-flight`. Carried as item 5 in section A. | `body-layer/ROADMAP/BL-B47.md:5`; `docs/acceptance/2026-10-10-crew-query-path-sortie.md` ("In the air — UNVERIFIED") |
| **BL-14** (attack-run guidance) | A combined acceptance sortie covering the guidance register. | **ANSWERED (flown) but found real defects, now its own workstream.** Flown twice 2026-10-15 (16:44 and 17:55). §1 repeat-callout, §2 doesn't stop on flyby, §3→§5 "obstructed" fires for range not obstruction (root-caused to the naked-eye presence threshold, not cockpit mask), §6-§7 optic-ladder direction, §9 LOS-priority-for-target all came out of this flight. The roadmap's own text ("not yet flown") is **stale** — it should say flown-with-findings, not unflown. | `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md`; `body-layer/ROADMAP/BL-14.md` (stale) |
| **BR-1.1 / BR-1.2** (brain layer wire + real Ollama model) | Whether the cockpit stays responsive while the brain "thinks," and whether hearing the model's own language (not a canned line) feels right. | **STILL OPEN.** Checked every transcript across all three 2026-10-15 sorties: every utterance matched a known command token (`report_all`, `engage`, `scan_*`, etc.) — nothing ever fell through to the brain-layer escalation path. The free-text/model path has still never been heard live. | `body-layer/logs/dcs-speech-20261015-*.jsonl` (no unmatched/escalated utterance found) |
| **BR-B1** (wider classify vocabulary) | Whether the narrow 7-token set under-serves real sorties. | **STILL OPEN, blocked on BR-1.2's own flight** — can't judge vocabulary coverage for an escalation path that has never fired. | `body-layer/ROADMAP/BR-B1.md` |

### Body-layer backlog (`BL-B`)

| item | waiting for | verdict | evidence |
|---|---|---|---|
| **BL-B55** (per-optic position error) | Confirming the stated per-optic sigma assumptions. | **STILL OPEN**, closed-as-BL-B64's-own-stage — same flight as BL-B64 clears both. | `body-layer/ROADMAP/BL-B55.md` |
| **BL-B59** (bounded fold displacement) | A real scene dense/ambiguous enough to exercise the fold-displacement bound. | **STILL OPEN.** Merged (`a8551d9`, confirmed in `git log`). No sortie since has reported a group-fold incident one way or the other — the three 2026-10-15 sorties' main group interaction was a single-vehicle attack run, not the dense-cluster case this bound targets. | `body-layer/ROADMAP/BL-B59.md`; checked `git log --oneline` |
| **BL-B64** (9K113 sight, perception) | A real acceptance flight with OBSERV actually turned on. | **STILL OPEN, confirmed by absence.** Searched all three 2026-10-15 speech logs for any "observ" token/transcript — none. The sight has shipped (merged `ec39c0e`) but has never been switched on in a real flight. | `body-layer/logs/dcs-speech-20261015-*.jsonl` (no "observ" occurrence); `docs/acceptance/2026-10-15-9k113-sight-acceptance-card.md` |
| **BL-B47** | — see BL-13 table above. | PARTLY ANSWERED | — |
| **X-B31** (occluder layer — not in the original candidate list, found by this audit) | The trees-only slice's own A/B flight over dense forest. | **STILL OPEN, same check as `BL-B59`'s neighbour, not `BL-B59` itself.** `feature/forest-occlusion` is DoD-passed, merge pending user approval, flag off by default. Its own entry says plainly "no sortie has exercised this path," and blast radius is ~0% at Latakia itself / 1–3% theatre-wide, so no ordinary sortie flown so far (including all three on 2026-10-15) would have exercised it without deliberate placement in the coastal woods NE of Latakia. The buildings half of this item is separately blocked on a LAN-topology decision, not a flight. | `todo/backlog/X-B31.md` |

### Body-layer work items (`BL-W`)

The given list included BL-W3, W4, W7, W13 which do **not** actually carry a `#needs-flight`
marker on inspection — flagging that discrepancy rather than silently dropping them.

| item | waiting for | verdict | evidence |
|---|---|---|---|
| **BL-W1** (contact-report-flood suppression) | Whether the cockpit is quieter without losing a genuine split. | **PARTLY ANSWERED** by continuous use since 2026-10-05 across every later sortie with no complaint resurfacing, but no document explicitly confirms it. | `body-layer/ROADMAP/BL-W1.md` |
| **BL-W3** (describe synonym, watch-group tagging, 11-12-1 scan sweep) | Each of three pilot-reported refinements. | **(2) `describe` synonym: ANSWERED** — used and recognised repeatedly in the 2026-10-15 logs. **(3)/(4): PARTLY ANSWERED** by routine subsequent flying, no explicit confirmation. Correctly does **not** carry `#needs-flight` in the file itself. | `body-layer/logs/dcs-speech-20261015-*.jsonl`; `body-layer/ROADMAP/BL-W3.md` |
| **BL-W4** (terrain qualifier "next valley"/"beyond the ridge") | Whether the qualifier fires where a pilot would say it, and the four shipped constants. | **STILL OPEN** — no sortie feedback doc mentions a terrain/divide qualifier being heard or judged; the only adjacent check (BL-11's tick-cost card) asks the pilot to listen for a *wrong* terrain qualifier but no result was recorded. Does not carry `#needs-flight` in the file. | `body-layer/ROADMAP/BL-W4.md`; `docs/acceptance/2026-10-06-bl11-tick-cost-sortie.md` |
| **BL-W5** (confirm-band affirmatives) | Whether 15s/20s timing is right and cancel→confirm actually stops the task. | **STILL OPEN** — no later doc confirms this specifically; superseded in importance by the `silence` command (BL-W13) which the user later said covers most of the same need. | `body-layer/ROADMAP/BL-W5.md` |
| **BL-W6** (sortie 09-26 fixes A/B1/B2/C) | Three in-cockpit observables (mask/occlusion grace, binoculars on a held contact, no interrupt on in-progress look). | **STILL OPEN** — no later doc confirms or denies. | `body-layer/ROADMAP/BL-W6.md` |
| **BL-W7** (binocular optic / voice completeness / precise position belief) | — | **ANSWERED.** Already marked `[x]` **FLOWN AND CLOSED 2026-09-25** in its own file. The source list's inclusion of this item was a false positive (grep matched leftover "unflown" text from the superseded sub-entry, not current status). | `body-layer/ROADMAP/BL-W7.md` |
| **BL-W12** (group cohesion redesign: size-relative cohesion, infantry EAGER, delta taxonomy) | Real-scene behaviour of the 500m installation cap, air-defence class guess, and the six-branch delta taxonomy "by ear." | **STILL OPEN** (corrected from ANSWERED — see Correction pass above). `BL-B59.md` states plainly "Fixture-only — no sortie has exercised this path," which contradicts the claim that its sibling bugs were found by flying. No document records a real flight exercising this mechanism's cohesion rules and judging the result. | `body-layer/ROADMAP/BL-W12.md`; `body-layer/ROADMAP/BL-B59.md` ("Fixture-only — no sortie has exercised this path") |
| **BL-W13** (`silence` command) | Whether one word of silence is the right amount; the third sub-question (silence vs. a threat appearing while muted) is explicitly separate. | **ANSWERED, with one residual.** User ACCEPTED 2026-10-09 ("silence command / one word, absolute quiet -> accepted"). Residual: whether absolute silence should break for a new threat — explicitly noted as "may simply not have occurred yet," i.e. untested, not forgotten. | `body-layer/ROADMAP/BL-W13.md` |
| **BL-W35** (watch reporting, Stages 1-5) | Movement/range-crossing/follow/engagement-envelope triggers in real flying. | **ANSWERED (flown, superseded card).** Exercised continuously since 2026-09-25 across every later sortie; follow/engage/danger-callout mechanisms are the ones exercised in the 2026-10-15 attack-run flights. | `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` shows `follow`/`engage` working end to end |
| **BL-W36** (group reporting disclosure ladder) | "Group lines stop restating known members," among others. | **ANSWERED.** User ACCEPTED 2026-10-09 ("Group lines stop restating known members -> accepted"). | `docs/acceptance/2026-10-09-four-acceptances-and-the-kola-correction.md` |

### Other subprojects / cross-cutting

| item | waiting for | verdict | evidence |
|---|---|---|---|
| **AC-8** (DCS-driven LOS, aircraft-layer) | A live DCS flight for the Hook's heading convention, building occlusion, socket-poll cost. | **ANSWERED for the core question, doc is self-contradictory and stale.** The file's own `[ ]` entry says "not yet merged, not yet flown" while flagging in its own header that this disagrees with WM-W2's record of the same work as "FLOWN 2026-10-05, 101,091 live verdicts... buildings have never occluded anything before." Merge is mechanically confirmed (`main` history carries the DoD commit). Building occlusion: **confirmed working**. Heading convention / socket-poll stutter: not explicitly re-confirmed, but no bug has ever surfaced for either since. Residual open point is the same as WM-W2 below (feed availability). | `aircraft-layer/ROADMAP/AC-8.md` (self-flagged contradiction); `world-model/ROADMAP/WM-W2.md` |
| **AA-2** (audio-adapter poll-hz default + Content-Length guard) | Optional cockpit confirmation of ~30Hz vs ~60Hz polling; no cockpit observable exists. | **STILL OPEN but trivial** — pure performance change with no in-cockpit effect; the entry itself calls the confirmation optional. Low priority, listed separately in section A. | `audio-adapter/ROADMAP/AA-2.md` |
| **AA-5** (`silence` phrase wiring, audio-adapter half) | Shares one sortie's worth of verification with body-layer's `silence` command. | **ANSWERED** — same acceptance as BL-W13 (2026-10-09, user accepted). | `audio-adapter/ROADMAP/AA-5.md`; `docs/acceptance/2026-10-09-four-acceptances-and-the-kola-correction.md` |
| **WM-W1** (LOS elevation-tolerance fix) | Whether the 12m tolerance behaves correctly live. | **ANSWERED.** User ACCEPTED 2026-10-09 ("LOS tolerance / grid error buried a unit -> accepted"), and separately the tolerance is now offline/fixture-only by construction since BL-11 Stage 4 moved live LOS off this primitive — so there is nothing left for a flight to further confirm. | `world-model/ROADMAP/WM-W1.md` |
| **WM-W2** (`feature/dcs-driven-los`, live feed availability) | Whether the live LOS feed is continuous enough, not just correct when present. | **PARTLY ANSWERED.** Mechanism flown and proven correct (2026-10-05). Availability measured at 19% missing verdicts on that flight; the 2026-10-15 attack-run sortie measured a materially better but still nonzero ~8% miss rate on gate-4 specifically. Improving, not closed — carried forward as a live, currently-being-designed fix (give the attack target LOS priority), not a fresh unknown. | `world-model/ROADMAP/WM-W2.md`; `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` §8-§9 |
| **X-B26** (can DCS elevation be read from files) | — | **Not actually a flight-pending item — list inclusion was wrong.** This is a closed investigation: answered 2026-09-29, then **superseded by a 2026-10-05 user decision rejecting live elevation polling entirely** ("Reject elevation probing from live missions..."). Fully closed, no flight involved at any point. | `todo/backlog/X-B26.md` |

### Acceptance cards

| card | status |
|---|---|
| **2026-10-14-bl14-attack-run-acceptance-card.md** | Flown (see BL-14 above). Superseded in practice by `2026-10-15-attack-run-sortie-feedback.md`'s findings; the three constants it asked the sortie to set (lined-up band, elevation gate, change threshold) were not reported on directly — folded into the "repeats when nothing changed" defect instead. |
| **2026-10-15-9k113-sight-acceptance-card.md** | Confirmed **still open** — see BL-B64 above. Also stale in one respect: it instructs a typed `!voice observ_on` console workaround, but the roadmap says OBSERV shipped as a real voice command ("observ on") — the card predates that and should be re-read, not flown as written. |
| Older cards (2026-09-18 through 2026-09-25) | Several explicitly marked `FLOWN AND CLOSED` or superseded by a later consolidated card in their own text — consistent, no further action. |
| 2026-09-29 / 10-01 / 10-02 / 10-04 / 10-05 / 10-06 / 10-08 cards | Each either explicitly closed by the 2026-10-09 "four acceptances" document, superseded by a later card named in its own text, or folded into the live-acceptance-debt entries audited above under their matching roadmap item — no separate open item found beyond what's already listed. |

---

## Doc defects found (not flight status, but wrong on the page)

- **`body-layer/ROADMAP/BL-14.md`** says "not yet flown" — it has been, twice, on 2026-10-15, and
  produced a feedback document with nine numbered findings. Should be corrected to reflect
  flown-with-findings rather than unflown.
- **`aircraft-layer/ROADMAP/AC-8.md`** already flags its own contradiction with `WM-W2.md` in its
  header (one says unflown, the other says flown 2026-10-05) — confirmed WM-W2's version is correct
  and AC-8's is stale.
- **`docs/acceptance/2026-10-15-9k113-sight-acceptance-card.md`** instructs a typed-console OBSERV
  workaround that the roadmap says has already been superseded by a real voice command.
- The original task's candidate list named **BL-W3, BL-W4, BL-W7, BL-W13** as carrying
  `#needs-flight` — on inspection none of the four currently do (BL-W7 is closed, BL-W13 is
  accepted, BL-W3/W4 never carried the tag to begin with). Likely picked up by the earlier grep
  matching leftover "unflown" wording inside superseded sub-entries.
- **`todo/backlog/X-B26.md`** was named in the task's candidate list but is not a flight-pending
  item at all — it's a closed investigation whose answer was later reversed by a user decision that
  removed the need for any live elevation polling, flight or otherwise.

## Duplicate/overlapping checks

- **BL-B55 and BL-B64** clear on the same flight (BL-B55 is explicitly folded into BL-B64's own
  Stage 1b).
- **BL-W13, BL-W36, WM-W1, AA-5** were all already closed together in the single 2026-10-09 "four
  acceptances" conversation — a genuine batch, already done.
- **AC-8 and WM-W2** are two roadmap entries (different subprojects) describing the *same* piece of
  work and the same residual open question (feed availability) — don't track them as two separate
  things to check.
- **`BL-W5` (confirm-band affirmatives) and `todo/todo/X-T8.md`** describe the *exact same* defect
  and fix (`fix/confirm-band-affirmatives`, merged `583d786`, 2026-09-28) and are both still open —
  confirmed directly against the logs that no "cancel"→"confirm" round trip has been spoken in any
  sortie since. Recommend closing one as a duplicate of the other once flown, so the same flight
  doesn't get recorded as clearing two different backlog items.
- **`BL-B59` and `X-B31`** are not the same item (different mechanisms: bounded fold-displacement
  vs. a forest-occlusion gate on the target's own position) but their flight checks are both
  "dense/forested scene nobody has deliberately flown yet," and a sortie built to exercise one
  (close grouped contacts in or near treed terrain) is a reasonable place to also exercise the
  other. Listed as separate items (3 and 9) in section A because the triggering scenario differs
  in a way that is easy to miss — B59 needs a tight *cluster*, X-B31 needs *tree cover* — but worth
  planning as one flight if convenient.

## Addendum — one item outside the original candidate list

`todo/backlog/X-B31` (the occluder layer, buildings-from-DCS/trees-from-OSM) was not in the task's
given list, but `grep -rl` for `#needs-flight`-equivalent phrasing surfaced it independently: its
own entry states in plain prose that the merged trees-only slice (`feature/forest-occlusion`) is
"fixture-only — no sortie has exercised this path." It earns inclusion by the same `grep`/"verify
rather than trust the list" instruction the task gave for everything else. See item 9 in section A
and its row in the "Other subprojects" table above.

---

## Addendum 2 — second pass, and a correction to this file's own provenance note

A second audit pass covered the same candidate list. It agreed with section B on almost everything.
Below: one correction to this file's provenance note, one factually-wrong card found by neither
pass, two items that can come off section A, and the measurements behind them — each with the
command that reproduces it, so nothing here has to be taken on trust.

### The provenance note's fabrication finding is mistaken, and the reason is worth keeping

This file's own header states that a subagent's log-based claims cited
`body-layer/logs/dcs-speech-20261015-*.jsonl`, "files that do not exist anywhere in this worktree
(confirmed: `body-layer/logs/` is gitignored and absent here)", and concludes the measurements were
fabricated.

**The first half is right and the conclusion does not follow.** The files are gitignored, so they
are absent from *every* worktree — and present in the user's root checkout, which is where they were
read:

```sh
$ git check-ignore -v body-layer/logs/dcs-speech-20261015-150739.jsonl
body-layer/.gitignore:8:logs/	body-layer/logs/dcs-speech-20261015-150739.jsonl
$ ls -l body-layer/logs/dcs-speech-20261015-*.jsonl     # from /Users/sg/Code/DCS-petrobrain
-rw-r--r--  5146  body-layer/logs/dcs-speech-20261015-150739.jsonl
-rw-r--r--  5171  body-layer/logs/dcs-speech-20261015-164451.jsonl
-rw-r--r--   498  body-layer/logs/dcs-speech-20261015-175509.jsonl
```

The headline figure reproduces exactly:

```sh
$ python3 -c "
import json,statistics
f='body-layer/logs/dcs-belief-truth-20261015-150739.jsonl'
t=sorted({json.loads(l)['t_sim'] for l in open(f) if l.strip()})
g=[b-a for a,b in zip(t,t[1:]) if 0<b-a<30]
print(round(statistics.median(g),3))"
1.018
```

**Why this is worth writing down rather than quietly fixing.** The check that produced the finding —
"do the cited files exist where I am standing?" — is the right check, and this repo's own rules are
what make it misfire: `AGENTS.md` requires every agent to work in a worktree, and a worktree cannot
by construction see a gitignored path. So *any* log-derived measurement, from any agent, will look
fabricated to a verifier standing in a worktree. **A file-absence check is only as good as the
checker's own vantage point**, and "absent from my worktree" and "does not exist" are different
claims for anything gitignored. The section-B verdicts resting on real-log reads are sound; so were
the discarded ones.

### A card that would send the pilot off `main` — found by neither pass

**`docs/acceptance/2026-10-06-callout-observability-sortie.md` is wrong in an instruction, not just
in a status.** It reads:

> **Branch: `fix/callout-observability-gate`** — … Reviewer approved over two rounds, **not merged**.
> … `git checkout fix/callout-observability-gate`
> (Verified: the branch exists and its tip is `304a367`. It is not on `main`, so `main` still has
> the defect.)

That branch merged as **`24746f5`** ("Merge fix/callout-observability-gate: no unprompted callout
names a masked hour"), and `git merge-base --is-ancestor 304a367 main` returns true today. Following
this card now would take the user **off** current `main` to test something already on it, dropping
every fix merged since. The parenthesis written to make the card trustworthy is the part that went
stale.

The check itself — no unprompted callout names an hour behind you — is still owed, and belongs on
the ordinary sortie in section A item 1. It just has to be flown on `main`.

### Two items can come off section A: the pilot already graded them

`docs/acceptance/2026-10-05-sortie-feedback.md` carries an explicit verdict table from a flown
sortie: `silence` **pass**, contact-report flood suppression **pass**, confirm band **pass**, plus
*"very good improvements on contact detection and reporting."*

- **`BL-W1`** (contact-report-flood suppression) → **ANSWERED.** Graded *pass* on that flight.
- **`BL-W5`** / the `cancel` → `confirm` round trip → **ANSWERED.** Graded *pass* on that flight.
  The argument against it was that no `cancel` token appears in any speech log. The inference is
  sound and the conclusion is wrong: **speech logging starts 2026-10-08** (and the two 10-08 files
  hold one line each), so the 10-05 flight could not have logged it. Same shape as the provenance
  note above — a log-absence argument is only as good as the log's coverage window, and `ls` settles
  it.

### `WM-W2`'s own clearing condition is met, measured

`WM-W2` clears *"when the feed is continuous and the fallback is the exception rather than the
rule."* Counting only candidates that reached the line-of-sight stage — past the gaze and
player-bubble gates, which reject before LOS is consulted:

| sortie | rows past the gaze gate | carrying a live verdict |
|---|---|---|
| `dcs-detection-trace-20261015-164451.jsonl` | 15,033 | 14,877 — **99.0 %** |
| `dcs-detection-trace-20261015-175509.jsonl` | 559 | 521 — **93.2 %** |

```sh
python3 -c "
import json
for f in ['body-layer/logs/dcs-detection-trace-20261015-164451.jsonl',
          'body-layer/logs/dcs-detection-trace-20261015-175509.jsonl']:
    tot=pres=0
    for l in open(f):
        d=json.loads(l)
        if d.get('outcome') in ('gaze','player_bubble'): continue
        tot+=1; pres += d.get('live_los_clear') is not None
    print(f.split('/')[-1], tot, pres, f'{100*pres/tot:.1f}%')"
```

Terrain-LOS rejections across both: 12 and 3. Against 77 % fallback on 2026-10-05 and 19 % of polls
returning nothing a week ago, **the fallback is now the exception.** Section A item 7 stands but is
narrower than stated: the open question is only what explains the residual 1–7 %, which is a
`dcs.log` counter capture, not a judgement call.

This also bears on the ~8 % figure quoted in `2026-10-15-attack-run-sortie-feedback.md` §8/§9 as the
rate at which `", obstructed"` might fire for *"no answer yet"*: it is the right order of magnitude.
The ~61 % reconstruction sitting beside it in `plans/position-belief-runaway/debug-2026-10-15.md` is
explicitly distrusted by its own author (*"I do not trust my 61 % figure"*), and the count above
supports the 8 % end.

### Confirmations

- **Tick cost.** Median realised tick period over the `t_sim` gaps of four real sortie logs:
  **1.018 s** (10-15 15:07), **1.020 s** (10-15 16:44), **1.030 s** (10-11), **1.029 s** (10-08) —
  against `BL-11`'s 1.000 s bench figure and a 1.33 s pre-branch baseline. The bench number holds in
  the air, so that card's headline measurement no longer needs a flight.
- **`BL-B47`'s scene did occur.** The 2026-10-15 sorties carried real air defence at class level —
  `OP_MRSAM`, `OP_LRSAM`, `OP_SRSAM`, `OP_ZU23`, `OP_SPAAG`, with an `S-300PS 64H6E sr` tracked 75
  times — so the code path ran. Whether he *spoke*, and whether he repeated, is unlogged. STILL OPEN
  is right, and it is purely an ear check.
- **`BR-B1` already has three real misses**, from the 2026-10-15 speech log rather than from the
  `BR-1.2` flight its entry waits on: *"Watch, ground ahead"*, *"attack ground"*, *"attack, run"* —
  all `say_again`.
- **`BL-13`'s mechanism flew.** `describe right`, `describe ten o'clock`, `describe at eleven
  o'clock`, `describe ahead` and bare `describe` all acted across two 2026-10-15 sorties. What is
  unrecorded is the pilot's judgement, which is what section A item 1 asks for.
- **The 533 km position errors** in `dcs-belief-truth-20261015-150739.jsonl` are not a new defect:
  that file holds three concatenated flights, diagnosed and filed as `BL-B68`.
