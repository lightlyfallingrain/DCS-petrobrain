# AC-B5 — A probe Hook left deployed taxes every sortie

- [ ] **AC-B5 — A probe Hook left deployed taxes every sortie and contaminates the measurements the
  sortie was flown to take.** #status/open Found 2026-10-08, by the user, after three hypotheses had been tested
  against it:

  > *"I think the 5s interval micro stutter may have been caused by
  > petrobrain-unit-id-join-probe-hook.lua that I had forgotten to remove. Now that I removed it, no
  > stutter."*

  `dcs-export/` holds roughly a dozen `*probe*.lua` Hook scripts and `Export.probe-*.lua` variants
  alongside the four shipped scripts. Nothing distinguishes a probe from a shipped script once it is
  in `Saved Games/DCS/Scripts/Hooks/`, nothing removes one when its probe is finished, and a probe is
  by nature heavier than production code — this one does a full unit enumeration plus `getObjectID`
  per unit every second.

  **The cost is not just the frame time.** The leftover probe was a confounder in a sortie flown
  specifically to measure the LOS Hook's cost under a tripled candidate population. Three hypotheses
  (reconnect-path stall, LOS poll cost, LOS poll cadence) were raised and refuted against log
  evidence, all while the real cause sat in the Hooks directory. See [[BL-B42]]'s stutter section for
  that record. The reasoning error was assuming the *deployed* set equals the *shipped* set.

  Worth having, roughly in value order:

  - A documented teardown step in `WORKFLOW.md`, paired with each probe's deploy step — a probe's
    deploy instructions are incomplete without its removal.
  - A way to enumerate what is actually deployed, so a sortie can record it alongside the data. A
    sortie log that cannot say which Hooks were loaded cannot be trusted for timing.
  - Consider having probe Hooks announce themselves loudly at `onSimulationStart` (a distinctive
    `log` line), so a `dcs.log` grep answers "what else was running" without filesystem access to
    the DCS box.

  Related: this is the second gap found in the same area — `WORKFLOW.md` has no deploy section for
  `petrobrain-line-of-sight-hook.lua` at all, which is its own item.
