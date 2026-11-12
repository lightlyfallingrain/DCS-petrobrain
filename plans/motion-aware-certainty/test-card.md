# Test card — motion-aware contact certainty (`BL-B112`), flight acceptance

**Branch to check out: `main`, after this feature merges.** **Air start**, straight and level,
**50–800 m AGL** (the aircraft's normal operating envelope — `docs/concept/PETROBRAIN_RUNTIME.md`/
project convention; do not test above a couple of km). `#needs-flight` — this feature has not yet
been flown.

## What this is testing

How long since a look should change Petrovich's wording based on whether the unit could actually
have moved, not on the clock alone. A fixed SAM site he saw ten minutes ago should still be stated
as fact ("there's a SAM at ..."), never hedged. A unit he watched park should stay "parked" until
observed otherwise. A truck last glimpsed half a minute ago should get "last I saw it ..." once its
plausible drift crosses about half a kilometre. And when a contact finally drops out of working
memory (goes "lost"), it should now show up in mission memory with its last-seen place and time —
Petrovich should be able to recall it later even though he no longer tracks it live.

**Run with `--mission-memory logs/mission-memory.jsonl`** (or let it default-stamp) so the written
entries are inspectable afterward, and `--speech-log` (on by default) to check the exact wording
heard.

## Case 1 — a fixed SAM site, unseen for several minutes, stated as fact

Find or place a fixed SAM site (S-125/SA-3, S-300/SA-10, or SA-2 if the theatre has one — **not**
Kub/SA-6, which is deliberately treated as mobile by this feature, see Case 2). Glass it once so
Petrovich has it in belief, then fly away so it drops out of gate range and stays unseen for
**several minutes** (well past the old ~2-minute "estimated" window).

**Expect:** if asked (`report`, or a threat question), the site is still named as fact — **no**
"last I saw" hedge, and it should **not** have gone silently to "lost" either (it should still be
in working memory, reportable). If it does eventually go lost (past ~2 minutes with no re-look),
check the mission-memory log afterward — there should be an entry for it recording its last-seen
place and time.

## Case 2 — Kub/SA-6 is mobile: a long-unwatched Kub should eventually hedge

If the theatre has a Kub/SA-6 available, glass it once, then leave it alone for several minutes
(longer than Case 1 — this is the one place this feature *widens* a hedge rather than narrowing
it). **Expect:** unlike Case 1's fixed sites, a Kub *can* eventually get "last I saw" treatment
once enough time has passed that it could plausibly have relocated — this is intended, not a bug.
If Kub instead behaves exactly like a fixed site (never hedged, ever), report that — it would mean
the mobile override isn't taking effect.

## Case 3 — a parked unit watched, then left

Find a mobile ground unit (a truck, an Osa/SA-8, anything not fixed) that is currently stationary.
**Watch it for at least 5 seconds continuously** (don't glance and look away) so Petrovich actually
confirms it stopped, then stop looking at it and leave it alone for 30+ seconds.

**Expect:** it should be described as parked/stopped, not "moving," for that whole stretch — a
single glance should **not** be enough to call it stopped (if you only glance once and it's
immediately reported "stopped," that's the single-glance regression this feature specifically
fixes: it should take the full watch).

## Case 4 — a moving truck gets "last I saw" at a plausible distance

Find a truck or similar fast mobile unit, glass it once while it's moving (so Petrovich has
registered it as moving, not just present), then let it go out of sight for **roughly 30 seconds**.

**Expect:** when asked about it, it should now be hedged — *"last I saw it ..."* — since a truck
moving at a believable road speed could plausibly have travelled past the half-kilometre threshold
by then. If it's still spoken as flat present-tense fact at 30+ seconds unseen, report that.

## Case 5 — a lost contact appears in mission memory

Pick any ordinary ground contact, glass it enough times to get at least one mission-memory entry
written for it (any group/air-defence contact that clears the usual confidence floor), then leave
it alone long enough to go fully "lost" (no re-look for ~2 minutes).

**After landing**, check the mission-memory log:

```sh
python3 .claude/skills/sortie-log-triage/scripts/triage.py --mission-memory <path-to-the-stamped-mission-memory-log>
```

**Expect:** a final entry for that contact, written around the time it went lost, carrying its
last-known place and time — not just the entries from while it was still being actively tracked.

## A known gap, not a regression to report

**A site still drops from "any SAMs?"/threat-recall answers after about 2 minutes of no re-look,
until `[[BL-B115]]` lands.** This feature (`BL-B112`) only writes the lost-contact note to mission
memory — it does **not** yet make Petrovich consult mission memory when answering a live question
about what's out there. So even though Case 1's fixed SAM site will have a correct lost-write entry
in the log, a live in-cockpit question asked *after* it has gone lost may still come back as "no
threats" rather than recalling the noted position. That is expected for this feature; `[[BL-B115]]`
(the kneeboard read-back, a separate pass) is what closes it.

## General things to listen for across every case

- **Never** "last I saw" for a unit that could not plausibly have moved (any fixed site named in
  Case 1) — that is the one hedge this feature must never produce.
- The watch requirement (Case 3) should not make Petrovich slow to notice real motion — a unit that
  *is* actually moving should still be called moving promptly (promotion to "moving" is unchanged,
  instant on one above-threshold reading; only the "stopped" side now needs the watch).
- Report anything that sounds wrong even if it doesn't match one of the five cases above — the
  thresholds in `plans/motion-aware-certainty/plan.md` (500 m displacement, the existing 5 s watch,
  the existing ~2-minute lost threshold) are stated assumptions, not measured certainties.
