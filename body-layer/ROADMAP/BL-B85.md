# BL-B85 — a contact stuck at `presence` forever can fully starve the sight's search cycle

- [ ] **BL-B85 — Found by the `9k113-narrow-search` security re-review
  (`plans/9k113-narrow-search/security-review.md`), empirically, not by inspection: a contact
  whose belief classification never advances past `presence` (a stuck/stalled belief-layer case,
  not modelled behaviour) is repeatedly re-admitted as "worth a look" while `OBSERV` is on, and the
  sight commits to re-looking at it indefinitely instead of ever reaching an idle poll. Measured
  over 900 simulated seconds with three simultaneous close contacts held at `presence` forever: the
  sight was busy on a look 792/900 polls (88%), idle/search-eligible only 27/900 (3%), and
  `sight_search_leg` never advanced past its initial `"wide"` for the whole run — full starvation
  of the new active search cycle (`plans/9k113-narrow-search/plan.md` Stage 3).** #status/open

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

  **Realistic case, for contrast (also measured)**: once each contact's belief level advances a
  tier per completed dwell (what the real classification pipeline is built to do), all three reach
  `type` and exit candidacy by ~t=175s; from there the search cycle runs freely (71.5% idle/search-
  eligible over the remaining ~725s, 33 leg transitions). The pessimistic case above requires
  classification to stall indefinitely despite repeated close-range looks, which should not happen
  if the belief layer is behaving — but nothing currently bounds how long a look may be re-granted
  to a contact that never advances, and this is the first feature to make that absence of a bound
  visible as a full search stall rather than a merely-delayed `GLASSING` dwell.

  **Needs**: a decision on whether to cap retries/dwell time for a contact that fails to advance
  classification after N looks (handing search time back regardless), or whether this is accepted
  as a pre-existing systemic risk that the belief layer is responsible for not triggering. Not
  explored with the user yet — do before Architect, per `AGENTS.md`'s "Explore Before Deciding," if
  this is picked up.
