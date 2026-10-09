# 2026-10-09 — four acceptances cleared, and a false claim of mine corrected

User's words, verbatim, reviewing the status page. Captured before anything was changed, per root
`CLAUDE.md`'s "Flight feedback is captured, then explored, then planned".

---

## Four acceptances

> * **10 km player bubble** — built, no cockpit observable → *"seems to work, though I can't verify
>   by flying. Accepted."*
> * **LOS tolerance** — grid error buried a unit → *"accepted"*
> * **Group lines stop restating known members** → *"accepted"*
> * **`silence` command** — one word, absolute quiet → *"accepted"*

These clear live-acceptance debt that had been accumulating since 2026-09-29. Note what the first
one means precisely: the player bubble had **no in-cockpit observable by design** (its DoD recorded a
waiver, not deferred debt), so "seems to work, can't verify by flying" is the strongest acceptance
that item can ever receive. It is accepted on that basis rather than left open for a confirmation
that cannot exist until the 9K113 sight's 20 km cone makes the bubble radius diverge from the
naked-eye cap.

## The correction — and the claim was mine, not the roadmap's

> *"**Multi-theatre** — Kola has no SRTM above 60°N → **Not true.** There a branch for Kola and
> Caucasus. Required SRTM files for both are present in Windows box."*

**Both halves of that are right, and the second half is the part I did not know.**

### The elevation claim was already corrected in the roadmap, and only my page still asserted it

`world-model/ROADMAP.md:1325` has carried the correct answer since 2026-10-04:

> *"viewfinderpanoramas.org DEM3 covers the Kola area (user-checked), same `.hgt` format the SRTM
> ingest already reads, **so Kola needs no new elevation source**."*

And `world-model/research/2026-10-04-multi-theatre-afghanistan-caucasus-recon.md:340` records the
user settling it mid-investigation: *"Answered and confirmed by the user mid-investigation: yes, it
covers Kola — treat the SRTM >60°N gap as resolved for Kola and do not re-investigate."*

So the source of truth was right. **`docs/status/petrobrain-status.html` asserted the superseded
version in four separate places** — a subsystem card, a graph node, an open-work row and a drawer —
and I regenerated that page hours earlier without catching any of them. That is precisely the failure
the page's own contract names: *"If the page and a roadmap disagree, the page is wrong — fix the page,
never the roadmap."* The page was repeating a claim the repo had already retired, which is worse than
a gap, because it arrives with the authority of a rendered dashboard.

**Why it survived my regeneration.** I updated the sections I expected this cycle's work to touch and
treated the rest as still-current. The roadmap text I would have needed was four days old, not new —
so "what changed recently" was the wrong filter. A derived page needs its claims re-derived, not
diffed against the last cycle.

### The branch I did not know existed

`origin/feature/multi-theatre-caucasus-kola` (`d5d0540`), **on `origin` only, never fetched to a
local branch**, three commits:

- `45bac42` — register Caucasus and Kola theatres: `coordinates/projections.py`, `build/region.py`,
  `dcs_data/beacons.py`, `dcs_data/towns.py`, `tests/test_coordinates.py`, plus `RUN.md` build steps.
- `865da91` — **Reviewer APPROVED**.
- `d5d0540` — roadmap updated, build steps marked user-run.

359 insertions across 10 files. So multi-theatre is not "backlog, not yet scoped" — it is implemented
and reviewed for both remaining theatres, waiting on user-run builds.

**This is the Session Start check paying for itself, having been skipped.** `CLAUDE.md` step 4 says to
run `git branch -v --sort=-committerdate` and read the matching plan directory before starting work,
because "a branch whose name matches the milestone you are about to start means the work exists". I
had been describing multi-theatre as open backlog all session. The branch was invisible to me because
it exists only as a **remote** ref, and my branch listings were local-only — `git branch -a` or a
`git fetch` was the missing step, and one fetch earlier this session had in fact printed both branch
names without my registering them.

---

## What was changed as a result

- Four debt entries cleared with the user's own words attached:
  `world-model/ROADMAP.md` (`fix/los-elevation-tolerance`), `body-layer/ROADMAP.md`
  (`fix/redundant-group-disclosure`, `silence` command), and the player-bubble entry's waiver
  converted into a positive acceptance.
- The Kola/SRTM claim removed from all four places in `docs/status/petrobrain-status.html`.
- Root `ROADMAP.md`'s "Caucasus/Kola themselves remain backlog" corrected — they are implemented and
  reviewer-approved on an unmerged remote branch.

## Open, for the user

The Caucasus/Kola branch is **approved but unmerged**, and its builds are user-run. Nothing blocks
merging it; it simply has not been. That is a decision, not a task — flagged rather than taken.
