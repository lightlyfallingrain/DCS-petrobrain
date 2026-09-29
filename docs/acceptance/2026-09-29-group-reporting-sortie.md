# Group reporting sortie

**Cockpit card (published):** https://claude.ai/artifact/WXTSUmzmQrzpSueEVh4K2B — the same content
below, laid out for reading in glances. This file stays the source of truth.

**Branch: `feature/group-reporting`** (this becomes `main` once merged — you fly from the main
checkout, and it will be sitting on `main` by the time you read this if the merge has already
happened):

```sh
git checkout feature/group-reporting && git pull
```

## Why this card exists — and what it is really testing

The 2026-09-28 sortie produced ~5 contact reports per minute for 25 minutes, the same sentence
verbatim up to 7 times, because 52 individually-resolvable contacts each got their own callout
(`plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md`). This branch replaces
one-callout-per-contact with **one line per perceptual group**, escalating detail with range and
threat, speaking only on refinement. That is the headline test. Everything else below is either
confirming the mechanism works as designed, or riding the same flight because it is also unflown
and this is the next chance.

**This is not the only thing on the branch.** Also merged here: the confirm band (`cancel` ->
"confirm" -> the task actually stops, previously unanswerable in the air), and this branch is built
on top of the 2026-09-26 sortie fixes (the observability gate for crossing/motion callouts,
binocular optic retry timing, command lowercasing). Separately, **already on `main`** and worth
flying the same sortie: the LOS elevation-tolerance fix
(`docs/acceptance/2026-09-29-los-tolerance-sortie.md`) — the missed insurgent AAA should now be
detected. If this branch has merged by the time you fly, all of it is in one checkout; if not, fly
`feature/group-reporting` for everything below and `main` separately for the LOS card.

**Fly with `--detection-trace <path>.jsonl` enabled** (see Setup) so any miss tonight — a group that
should have formed and didn't, or the reverse — is evidenced in the trace rather than remembered
anecdotally after landing.

## Setup

Three processes, same as the recent crew-behaviour cards. From `run-scripts/` on the Mac, with the
Windows collector already running (`--ptt dcs`):

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text-debug-view.sh --brain-client http --brain-url http://127.0.0.1:7796 --detection-trace ~/dcs-group-reporting-trace.jsonl
```

(`--decider stub` is fine if you are not testing brain-layer behaviour today — group reporting
lives entirely in body-layer's disclosure/scheduler, not the brain.)

## Test cases

### 1 — The headline: is it quieter, and still informative?

**Do.** Fly a normal patrol leg past whatever's out there — a convoy, an outpost, scattered armor.
Just listen to what Petrovich says over several minutes, the way you would on any sortie.

**Expect.** One line per group rather than a line per vehicle. No repeated near-identical
sentences the way last sortie had.

**Record.**
- [ ] Does it actually feel quieter than the 2026-09-28 sortie?
- [ ] When he does speak about a group, does the line tell you *more* than the old one-line-per-
  contact chatter did, or does it feel like it's hiding something you'd want to know? This is the
  one judgment call in this card only you can make — the whole point of the feature rests on it.

### 2 — The disclosure ladder: silence, then refinement, then threat-led

**Do.** Approach a group of vehicles from range and watch it develop, don't cancel/re-scan to force
it.

**Expect**, roughly in this order as the group is watched over time (exact wording confirmed
against the branch's own tests, not guessed):
- Far out, undifferentiated: **`"Group."`** — bare, no composition detail yet.
- Once classification refines past presence, still no threat member: **`"Two armor and a
  truck."`** — composition leads.
- If a member resolves a real threat envelope: **`"Danger, ZSU-23-4 Shilka. Also two armor."`** —
  the threat leads, the rest follows as composition.
- With clock/range attached (enrichment on): starts **`"Group, "`** and ends **`"...o'clock,
  <range>."`**
- **Silence** in between refinements — no update means no new sentence, that is deliberate.

**Record.**
- [ ] Did you hear the ladder actually escalate as a group closed or resolved, rather than
  repeating the same line?
- [ ] Any case where it should have said more (e.g. a threat member present) but didn't, or said
  less than it should have known?

### 3 — "Pair" vs. "a couple of"

**Do.** Notice any two-member group Petrovich reports.

**Expect.** If the pair shares one real, exact classification: **`"Pair of T-72."`** (exact form).
If still undifferentiated (nothing resolved yet): **`"A couple of contacts."`** (hedged form,
deliberately the same hedge already used for an uncertain count *within* one contact). If the pair
is two *different*, resolved things: it skips both words and names each — e.g. **`"A armor and a
truck."`**

**Record.**
- [ ] Does "pair" vs. "a couple of" sound natural in the air, or does either form read wrong when
  you actually hear it?

### 4 — Group boundaries: do the things you'd call one group get reported as one?

**`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS = 20.0`** (roughly 140 m between neighbouring 7 m
vehicles, single-link so a convoy chains member-to-member) is **a stated assumption, not a
measurement** — your own words going into this design were *"I have no definitive answer. Pick
something, we'll refine it later."* Tonight is the first real evidence on whether 20 is right.

**Do.** Fly past anything with more than 2-3 units — a convoy, an outpost, a scattered patrol — and
judge whether Petrovich's grouping matches your own read of "that's one thing" vs. "those are two
separate things."

**Record.**
- [ ] Any case where units that felt like one group to you got split into separate callouts?
- [ ] Any case where units that felt like clearly separate things (e.g. a convoy on the road vs. a
  static checkpoint it's passing) got merged into one report?
- [ ] If you have a rough sense of the actual spacing in either case, note it — that is the number
  this backstop gets tuned against next.

### 5 — What is knowingly NOT fixed yet

**Common-fate cohesion (Stage 5) is deliberately deferred.** A moving convoy passing a static
checkpoint may still merge into one group in this build, because the mechanism only looks at
current spacing, not who is moving together. This is not a bug to report as new — it's the exact
case Stage 5 exists to fix, and this flight's evidence (test case 4 above) is what that design will
be built from. If you see this specific failure mode, it's expected; still worth recording under
test case 4 rather than as a separate defect.

## Riders on this flight, in one place

- **Confirm band** (`fix/confirm-band-affirmatives`, merged into this branch): `cancel` -> *"Cancel
  everything, confirm?"* -> `"confirm"`/`"yes"`/`"roger"` all now work, and the task actually stops.
  See `docs/acceptance/2026-09-28-confirm-band-sortie.md` for the full dedicated card if you want to
  probe the timing windows specifically; a normal `cancel` during this flight already exercises the
  fix.
- **2026-09-26 sortie fixes** (this branch is built on top of them): crossing/motion callouts now
  pass an observability gate before being spoken; an interrupted look no longer burns a contact's
  retry budget; commands are lowercased before matching.
- **LOS elevation-tolerance fix** (already on `main`, separate branch): the missed insurgent AAA
  should now be detected. See `docs/acceptance/2026-09-29-los-tolerance-sortie.md`.

## Pass criteria

The feature passes if test case 1's judgment call comes back positive (quieter and still
informative), the disclosure ladder in test case 2 escalates correctly, "pair"/"a couple of" sound
right in test case 3, and any group-boundary misses in test case 4 are recorded as evidence for the
20.0 figure rather than treated as a blocking defect (that number is expected to move). A miss in
test case 5's specific shape is not a failure — it's already known and deferred.
