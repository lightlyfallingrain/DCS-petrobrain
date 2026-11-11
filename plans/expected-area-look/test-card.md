# Test card — expected-area look (`BL-B111`), flight acceptance

**Branch to check out: `main`, after this feature merges.** **Air start**, straight and level,
**50–800 m AGL** (the aircraft's normal operating envelope — `docs/concept/PETROBRAIN_RUNTIME.md`/
project convention; do not test above a couple of km, Petrovich's behaviour there is out of
scope). `#needs-flight` — this feature has not yet been flown.

## What this is testing

Today, a sighting that lands on or beside a group Petrovich remembers but cannot currently see is
always called out as a brand-new contact, even when it is really the same group seen again. This
feature makes him hold that sighting, put the binoculars on the remembered group's expected place,
and only then decide: is this a second group, or the one he already knows about?

**Run with `--expected-area-log logs/expected-area.jsonl`** (or let it default-stamp — see
`body-layer/CLAUDE.md`'s `--expected-area-log` paragraph) so the check-open/verdict log is
captured for `sortie-log-triage` afterward; also useful: `--eyesight-view` to watch the binoculars
swing onto the remembered place rather than the new sighting.

## Case 1 — the ridge case (ties the check to something you can see)

Set up or find a scene with **one group glassed and confirmed on the far side of a ridge**, and a
**second, different group nearer to you, on your side of the same ridge** roughly on the same
bearing. Fly so the far group drops out of view (behind the ridge) for more than a couple of
seconds, then let the nearer group come into gate range on a similar bearing.

**Expect:**
- The binoculars swing onto the **far group's last known place** (visible in `--eyesight-view` as
  a look target there, not on the new sighting) — this is the check opening and looking, not him
  reporting the new one yet.
- A short pause, then *"new contact"* for the **nearer** group specifically — the far one is
  confirmed still there and is not re-announced.

## Case 2 — long-gap re-sighting of a parked group

Find or place a stationary group, glass it once so Petrovich has it in memory, then **leave the
area for 10+ minutes** (fly far enough that it drops out of gate range and goes quiet), and
**return** to roughly the same bearing/range.

**Expect:**
- **No** *"new contact"* call for that group.
- **No** *"that group, now ..."* line either, **unless** the place he would call it at has
  genuinely changed (a different clock-hour or 0.5 km range bucket, by at least 500 m or 30°) —
  if the group hasn't moved and your own return approach doesn't shift the bucket, silence is
  correct, not a miss.

## Case 3 — a SAM site re-seen after ten minutes

Same as Case 2, but specifically with an **air-defence** group (SAM site). Leave for ten minutes,
return.

**Expect:** at most **one** threat line total across the whole sequence — either the original
detection, or (if it re-triggers for any reason) the relocation line, never both, and never a
second *"new contact"* for the same site. This is the SAM vignette the plan's harness specifically
measured against a naive "anything seen nearby" rule that would have called it different.

## Case 4 — a group in a town

Find or place a group **parked inside or very near a settlement** (a mapped town/village, not
open countryside), let it go quiet the same way as Case 2, and return.

**Expect:** *"new contact"* — this is the **honest cost** of the feature, not a bug. A town
always reads "cannot look" (buildings are not what `land.isVisible` checks, and the forest/
settlement occlusion mask treats a mapped settlement polygon the same as a wood), so Petrovich
cannot confirm the place is empty and falls back to calling the sighting new. If this instead
comes back silent or as a relocation line, that is worth reporting — it means the settlement mask
isn't engaging.

## Case 5 — a busy scene

Fly a scene with several contacts active at once (a mixed engagement, or simply several groups in
range together) for a few minutes. No specific expected line here — the point is to **count** how
often the hold/look actually happens against the shared 12 s glass budget.

**After landing**, reduce the sortie's logs:

```sh
python3 .claude/skills/sortie-log-triage/scripts/triage.py --expected-area <path-to-the-stamped-expected-area-log>
```

**Look at:**
- how many distinct checks opened, and the verdict histogram — does the trigger rate feel
  proportionate to what you saw/heard, or did it fire far more (or less) than expected?
- whether a busy scene ever crowds a check out of the glass budget (a "cannot_look" verdict with
  cause `look_not_completed`, meaning the look itself never got its turn) — the plan's own
  top-listed open risk.
- the merge-echo-suppressed count and `CONTACT_RELOCATED` count, as a sanity check against what
  you actually heard.

## General things to listen for across every case

- *"That group, now ..."* should sound neutral (a position update), never claim the group moved —
  Petrovich cannot tell a real move from a misjudged range.
- A held sighting must **never** go silently missing — if you see a contact appear briefly in
  `--eyesight-view` and then nothing is ever said about it (not "new contact", not folded in with
  a relocation line, not silence you'd expect from the cannot-look cases above), that is a bug,
  not an acceptable cost.
- Report anything that sounds wrong even if it doesn't match one of the five cases above —
  the harness numbers in `plans/expected-area-look/plan.md` are a model and a production replay,
  not a guarantee about every real scene.
