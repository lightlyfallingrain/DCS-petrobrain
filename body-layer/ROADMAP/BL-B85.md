# BL-B85 — a contact stuck at `presence` forever can fully starve the sight's search cycle

- [~] **BL-B85 — Found by the `9k113-narrow-search` security re-review
  (`plans/9k113-narrow-search/security-review.md`), empirically, not by inspection: a contact
  whose belief classification never advances past `presence` (a stuck/stalled belief-layer case,
  not modelled behaviour) is repeatedly re-admitted as "worth a look" while `OBSERV` is on, and the
  sight commits to re-looking at it indefinitely instead of ever reaching an idle poll. Measured
  over 900 simulated seconds with three simultaneous close contacts held at `presence` forever: the
  sight was busy on a look 792/900 polls (88%), idle/search-eligible only 27/900 (3%), and
  `sight_search_leg` never advanced past its initial `"wide"` for the whole run — full starvation
  of the new active search cycle (`plans/9k113-narrow-search/plan.md` Stage 3).** #status/in-progress

  **Built on `feature/9k113-narrow-search`, not left as backlog** — the user overruled Reviewer/
  Security's non-blocking disposition: *"BL-B85 is required for 9K113, we can't just indefinately
  look at one thing. Needs a timer value or the like that forces moving on"*
  (`docs/acceptance/2026-10-20-sortie-feedback.md` F4). `#needs-flight` — the fix is unflown; the
  measurement below is a 600 s synthetic reproduction of this entry's own pessimistic scenario, not
  a live sortie.

  **Two causes, not one, both fixed together** (`plans/9k113-narrow-search/implementation.md` has
  the full account):
  1. **The real root cause, found only once the obvious fix was tried and didn't move the
     reproduction's numbers**: `_start_glance_away` (the scheduled dwell-boundary break,
     `SIGHT_MAX_DWELL_S`) was dropping an in-progress look's pending marks the same way a genuine
     interruption does, rather than committing them. Because the scheduled break and the per-look
     natural-end timeout share that same constant and `_decide_sighting` checks the scheduled break
     *first*, a contact that never resolves has its look cut off here on *every* cycle — the
     natural-end commit path was structurally unreachable for exactly the stuck contact this entry
     is about, so `attempted_at_range_m`/`attempted_at_time_sim` never recorded an attempt at all
     and the whole pre-existing retry/cooldown mechanism never engaged. Fixed: `_start_glance_away`
     now commits pending marks exactly as the natural-end path does.
  2. **The new tunable**, `belief.optic_policy.SIGHT_STALL_COOLDOWN_S` (default 132.0 s, ~two
     search-cycle laps): once (1) lets an attempt actually commit, `is_worth_a_look` applies this
     longer cooldown instead of the short `OPTIC_RETRY_INTERVAL_S` (64 s) when a contact's
     classification level is unchanged since that commit — sight-only, `GLASSING` keeps the
     pre-existing short interval unchanged.

  **Both halves are load-bearing, measured, not assumed**: with only fix (1) (the commit fix) and
  the pre-existing short `OPTIC_RETRY_INTERVAL_S`, the reproduction below still measures 88% busy —
  the short interval alone does not create enough of a gap for the search cycle between three
  contacts' commits. With both fixes, the same 600 s/three-contact reproduction measures 58% busy,
  every search leg (`wide`/`narrow_near`/`narrow_far`) visited, and every contact re-looked four
  times over the run rather than abandoned forever.

  **Required fix** (`plans/9k113-narrow-search/review.md` "Review — BL-B85"): fix (1) above, as
  first built, committed *every* pending mark on the scheduled dwell boundary unconditionally —
  including a contact whose classification was genuinely advancing, not only a stalled one.
  Measured: a single contact progressing `presence` → `class` mid-dwell was re-looked at ~94 s
  (dwell + `OPTIC_RETRY_INTERVAL_S`) instead of the pre-`BL-B85` ~33 s (`SIGHT_MAX_DWELL_S` +
  `SIGHT_GLANCE_AWAY_S`). Fixed: `_start_glance_away` now commits a pending contact's mark only if
  its classification level is unchanged since the look started — a look during which the level
  advanced is dropped instead, the same treatment a genuine interruption already gives it (Fix B1,
  2026-09-26: "an interrupted look does not mark the target attempted"), so it does not burn the
  retry window. Re-measured end to end
  (`test_a_progressing_contact_is_relooked_near_the_pre_bl_b85_cadence`,
  `tests/test_optic_policy.py`): the same progressing-contact scenario now re-looks at t=34 s (gap
  34 s, against the pre-`BL-B85` ~33 s), not t=94 s — confirmed by mutation (reverting to the
  unconditional commit reproduces exactly 94 s). The three-contact stalled-case reproduction above
  is unaffected by this fix (a genuinely stalled contact's level never changes, so every one of its
  looks still commits and the stall cooldown still applies).

  **Not a blocker for that feature, and not newly introduced by it** — two reasons, both already
  recorded in `plans/9k113-narrow-search/implementation.md`/`review.md`:
  1. "Identification takes priority over search" is this module's own pre-existing, stated rule for
     the `SCANNING`-at-home path too (`_decide_without_guidance`'s own docstring, unchanged by that
     feature) — applying it to the sight's own idle branch is the existing precedent, not a new
     policy.
  2. A mid-range contact stuck at `presence` inside the binocular window could already starve
     `GLASSING` the same way before this feature shipped. What this feature's no-lower-bound
     `sight_can_still_improve` changes is *which* contacts can trigger it (close ones too, where
     `improvement_window_m`'s lower bound previously excluded them) — it widens the trigger
     population, it does not create the failure mode.

  **Why it is worth its own entry rather than folding into `[[BL-B20]]`**: `BL-B20` is a
  selection-*fairness* redesign among several simultaneously worth-a-look contacts in a commanded
  sector (round-robin / least-known-first). This is a different shape — one contact that never
  *finishes* (classification genuinely stalled, not merely slow) can starve the cycle alone, with
  no second contact needed. A fairness redesign among many candidates does not, by itself, bound
  how long any one candidate may be re-selected if it never stops qualifying.

  **Realistic case, for contrast — re-measured against the current code** (the required-fix round
  above; the ~175 s/71.5% figures this paragraph used to carry were measured *before* that fix, on a
  version of the code where `_start_glance_away` never committed anything for `SIGHTING` at all, so
  they described a different mechanism and are superseded, not merely stale — `plans/
  9k113-narrow-search/review.md`'s "Review — BL-B85" flagged exactly this and asked for a re-run).
  Three contacts (50/80/120 m, T-72, presence) each bumped a tier the poll after their own look
  ends (what the real classification pipeline is built to do), driven through `decide()` over
  900 s with the same one-step `wide`/`narrow_near`/`narrow_far` toy search legs the committed
  stuck-case test above uses (not the real multi-step `search_pattern`-built sequences the original
  900 s reproduction used, so leg-transition counts are not comparable across the two and are not
  cited here): all three reach `type` and exit candidacy by t=196 s (CONTACT_1 at 130 s, CONTACT_2
  at 163 s, CONTACT_3 at 196 s), each needing only two look-starts to get there (no progressing look
  is ever throttled by the retry/cooldown mechanism, by construction of the required fix above).
  Overall busy fraction across the full 900 s is 19.4% (175/900 polls) — *lower* than the original
  71.5%-idle figure, i.e. search gets *more* of its time back under the fixed code, not less — every
  search leg (`wide`/`narrow_near`/`narrow_far`) visited, and the search cycle runs with no contact
  left to glass for the remaining 704 s. The pessimistic case above requires classification to stall
  indefinitely despite repeated close-range looks, which should not happen if the belief layer is
  behaving — but nothing currently bounds how long a look may be re-granted to a contact that never
  advances, and this is the first feature to make that absence of a bound visible as a full search
  stall rather than a merely-delayed `GLASSING` dwell.

  **Settled and built** (user, 2026-10-20, F4 above) — a time bound, not a count of looks: handled
  by `SIGHT_STALL_COOLDOWN_S` above rather than an N-looks counter, consistent with the existing
  `OPTIC_RETRY_INTERVAL_S`/`RETRY_RANGE_FRACTION` retry mechanism this extends. Remaining before
  `#status/done`: the live sortie (`#needs-flight`), and a judgement on whether 132.0 s is the right
  default once flown — the whole-encounter timescale a pilot actually experiences this at is not
  something a synthetic 600 s reproduction can validate by itself.

  **GLASSING left unprotected, deliberately, not overlooked**: the pre-existing risk named just
  above (a mid-range contact stuck at `presence` could already starve `GLASSING`) is not fixed by
  this entry — only `_decide_sighting`'s own candidate filter passes `SIGHT_STALL_COOLDOWN_S`;
  `GLASSING`'s call to `is_worth_a_look` does not, by construction. Extending the same cooldown to
  `GLASSING` would be a `GLASSING` behaviour change beyond what F4 asked for (binoculars, not the
  sight); filed as a backlog note rather than built here.
