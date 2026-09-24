# Position-belief-runaway sortie

Fixes a live defect: Petrovich reported `"couple contacts, 4 o'clock, 87.5 kilometres"` against a
10 km detection cap. Four distinct defects were found and fixed under this one report, plus one
unrelated speech bug caught along the way.

**Branch: `fix/position-belief-runaway`, not yet merged.** DoD (format/lint/type/test, Reviewer,
Security) is complete and clean at the time this card was written; this card is written for the
unmerged branch on purpose. Once merged, this card's branch line will be corrected to `main` — if
you're reading it before that correction lands, check out the branch by name, not `main`:

```sh
git checkout fix/position-belief-runaway && git pull
```

## Where this sits among the outstanding sorties

Three other sorties are already open and unflown, all on `main`: `docs/acceptance/
2026-09-23-eyes-and-voice-sortie.md` (binocular optic, voice command completeness, and the
*original* precise-position-belief merge this fix corrects), `docs/acceptance/
2026-09-24-watch-reporting-sortie.md` (unprompted contact reports, engagement envelopes,
`follow`), and the probe card `docs/acceptance/2026-09-24-damage-and-firing-probes.md`. That's
four sorties of live-acceptance debt, this one included — do not treat this as the only thing
outstanding.

**This one is a precondition for the eyes-and-voice card's position-belief items making sense.**
The eyes-and-voice card was written against the buggy position belief; flying it before this
branch merges risks re-finding the same 87.5 km defect and re-reporting it as new. Once this
branch merges, fly this card first (or fold both into one flight — nothing here needs a separate
setup) before judging eyes-and-voice's position-related items.

## Setup — nothing to redeploy

No Windows-side change. Only `body-layer/` is touched (`git diff --stat main..fix/
position-belief-runaway` confirms it — `Export.lua`, the Hook scripts, and the collector are
untouched). Same processes, same flags as prior sorties:

- Windows: collector, and capture with `--ptt dcs`
- Mac: `run-scripts/run-audio-adapter.sh`, then `run-scripts/run-crew-text.sh` (add
  `--detection-trace ~/dcs-detection-trace.jsonl` if you want the range-gate trace this card's
  hardest-to-verify block references — see block 2 below)

body-layer 1192 tests / 4 xfailed (verified this session against an isolated copy of this
branch's own source, not read off a docstring — main's own baseline is 1177/4, so 15 new tests,
no regressions).

## Not testable, and why — read this before you fly

**The headline symptom is directly observable by ear. Whether the underlying fix is *correct*,
not just *bounded*, is not — and that gap is the point of this card.**

- **"No contact reported beyond ~10 km" is checkable in one flight, by ear alone.** If you ever
  hear a naked-eye range past 10 km again, this branch has a real gap — say exactly what was said
  and roughly how far you actually were.
- **Whether the *believed position* is now the right one, not just a bounded one, is not checkable
  by ear.** A position within the detection cap sounds identical whether it is closely tracking
  the real target or is confidently wrong by a kilometre. If you have any independent way to judge
  distance/bearing to a contact you called out (map markers, a known target's actual location,
  F10 view if you use it for calibration only), that comparison is worth more than anything else
  in this card.
- **Whether a held position recovers in the ~7-10 s the fix's own math predicts is also not
  checkable by ear alone**, short of literally timing a callout against when you know a target
  actually changed course. `--detection-trace` (flag above, reduced with `body-layer/tools/
  summarize_detection_trace.py <path>` after the flight) gives you the per-poll admitted range —
  the closest thing to an instrument for this, but still not a ground-truth position. If a
  reported position looks stuck for what feels like much longer than ~10 seconds while you keep
  the target in view and it's clearly moving, that is exactly the failure mode this fix targeted —
  note the approximate duration.
- **The doubled unit-type callout fix ("truck ... is KrAZ truck" → should now read "unit ... is
  KrAZ truck") is fully checkable by ear** — it's a pure wording defect, independent of the
  position math.

## 1 — The headline symptom. DO THIS FIRST, WORTH MOST

**Do.** Fly a normal naked-eye scan/watch pattern — the kind of flight that produced the original
87.5 km report. No special setup; ordinary detection and reporting.

**Expect.** No naked-eye range callout ever exceeds 10.0 km (`NAKED_EYE_RANGE_CAP_M`). No scope/
hybrid-channel range callout ever exceeds 5.0 km (`RANGE_CAP_M`). This is the direct fix for the
reported defect and the single most important thing this card checks — everything else is
secondary to this one holding.

**Record.**
- [ ] Did any callout ever report a range beyond its channel's cap (10 km naked-eye / 5 km scope)
- [ ] If yes: the exact wording, your best estimate of true range at that moment, and what you
      were doing (scanning, watching, turning) just before it

## 2 — Believed position vs. real position, over a sustained track

**Do.** Pick one ground contact and keep it in view (watch or repeated scan passes) for at least
a minute, ideally while it or you are moving. If you have any way to independently judge where it
actually is relative to you (a known target placement, map reference), use it.

**Expect.** Reported bearing/range should track the target's real motion — closing as you close,
opening as you open, turning as the target turns — not wander independently of what you can see
happening. A **precise-and-wrong** position (the perception model's deliberate design — see
`precise-position-belief`'s entry in `body-layer/ROADMAP.md`) is expected and correct; a position
that visibly **stops tracking real motion for an extended stretch** while you can see the target
still moving is the failure mode this whole branch exists to fix.

**Record.**
- [ ] Did the reported position track real target motion throughout, or did it visibly stall/drift
      independent of what you could see
- [ ] If it stalled: roughly how long (see block 3 below for the specific timing question)
- [ ] Anything that felt like the range/bearing was "off" by more than a plausible perception error

## 3 — Hold-recovery timing (hardest to judge, name it explicitly if you notice it)

**Do.** No special setup beyond block 2 — this is the same track, watched for the specific
failure shape: a target that changes direction or the geometry between you and it shifts (e.g. a
turn that puts it at a near-parallel bearing to your line of sight), while you keep it in view.

**Expect.** If the belief holds its prior position rather than immediately re-fusing to the new
look (the guard this branch adds), it should recover to tracking the real position again within
roughly 7-10 seconds at a normal ~1 Hz poll rate — not tens of seconds, not minutes. This number
came from the fix's own regression test and a security review's independent measurement; it has
never been checked against a real sortie's actual poll timing and geometry.

**Record.**
- [ ] Did you ever notice a position that seemed "stuck" and then caught back up — roughly how
      long did that take
- [ ] Does ~7-10 seconds feel right, too fast, or too slow for what you experienced (if you
      noticed this at all — it's a subtle effect and may not be perceptible in a normal flight)

## 4 — The doubled unit-type callout (fully checkable, low effort)

**Do.** Get a contact classified specifically enough to produce a compound type name — a KrAZ
truck, or anything else whose reporting name repeats its class word (e.g. "<class> <specific>").

**Expect.** The classification-change callout should read `"unit at <clock> o'clock, <range> km
is <full type name>."` — never `"<class> ... is <full type name>"` with the class word said twice
(the original bug: `"truck ... is KrAZ truck"`).

**Record.**
- [ ] Any classification callout that repeats a word between its lead-in and its type name

## The logs and trace

```sh
cat ~/dcs-speech.jsonl
cd body-layer && .venv/bin/python tools/summarize_detection_trace.py ~/dcs-detection-trace.jsonl
```

(Only if you added `--detection-trace` to the run command — see Setup above.) The trace summary
gives per-object first-admitted range per tier — useful for corroborating block 1's "did anything
exceed the cap" question with the actual gate decisions, not just what got spoken.

## Bring back

1. **Block 1 — did the range cap actually hold.** This is the one thing that must be true for the
   branch to have fixed the reported bug at all.
2. Block 2 — did believed position track real motion, or wander/stall independent of it, over a
   sustained watch.
3. Block 3 — any perceptible "stuck then catches up" timing, and how long it felt like, if you
   noticed it at all (a subtle effect — a clean "didn't notice anything like that" is a useful
   answer too).
4. Block 4 — the doubled-word callout, fixed or not.
5. Anything that surprises you is worth more than anything on this list.
