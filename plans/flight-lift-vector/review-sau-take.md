### Review Summary

Reviewed `fix/bl16-flight-epoch-bound` (pushed as `feature/bl16-lift-vector-law`) at tip `796d3804`
(debugger memory) / `15235ea7` (the fix itself) against
`plans/flight-lift-vector/debug-2026-11-28-sau-take.md`, the two sortie logs it cites
(`/Users/sg/Code/DCS-petrobrain-epochfix/docs/acceptance/logs-2026-11-28/lv2-...`/`lv3-...`), and
`body-layer/src/body.py`/`belief/effector_engine.py`/`belief/flight_authority.py`.

Video game add-on (DCS World Mi-24P) review — nothing here controls real hardware.

Mechanically the fix is clean: bounded, correctly gated on `fd_mode`, a true no-op after a write
has already landed (`assumed_writes`), tunable is properly declared and renders correctly in
`defaults.toml`, tests are real (drive the real poll loop, not decorative), and all checks pass.
**But the central question — "does a 10 s retry plausibly fix what was flown?" — the evidence
says no**, and the debug note does not connect its own numbers to say so.

### Required Fixes

- **The chosen `SAU_TAKEOVER_RETRY_WINDOW_S` (10 s) does not cover either flown sortie's own
  evidence, and nobody checked that before shipping it.**
  - Sortie 1 (`lv2-...`): take/edge at `t_sim=23.182` (18:22:56). The debug note's own hypothesis
    is that the run gives up after `EFFECTOR_CONDITION_READBACK_WAIT_S` (5 s), i.e. by
    `t_sim≈28.2`. The SAU-off write actually landed at 18:23:35 — confirmed from the raw log
    (`grep` of `lv2-aircraft_layer_debug.log` lines 2956-2965): two intervening `flight cmd
    kind=set`/`ack` pairs at 18:23:07 (`t=34.148`) and 18:23:30 (`t=57.169`), both still
    `mode=m1`, then the three `cockpit_switch` writes five seconds after the second. **That is
    ~39 s after the edge — ~34 s after the modelled give-up — against a fix whose own window
    closes 10 s after the edge (`t_sim≈33.2`).** Replayed through the patched code, this exact
    sortie's write would **not** land inside the retry window: the window would already be closed
    and `sau_takeover_retry_until_sim` cleared roughly 24 s before the real recovery.
  - Sortie 2 (`lv3-...`): take at 18:39:46 (`t=12.616`). I read the flight trace
    (`lv3-aircraft_layer_flight_trace.log`) end to end: it runs to `t=58.844`, i.e. **~46 s** in
    `mode=m1` with the debug log confirming zero `device=10` cockpit-switch lines anywhere after
    the take. That is itself outside the 10 s window and the log simply ends there (recording
    stopped, not a gap in logging) — so there is no evidence the channel ever recovered in this
    sortie, consistent with the debug note's honest "still lost for that take" caveat, but it
    means **neither of the two cases that motivated this fix is actually closed by it.**
  - The debug note's "Fix Applied"/"What a re-fly should show" sections state the window is bounded
    and may still lose the handover on a long stall, but frame that as a residual risk rather than
    the measured outcome: **the only two data points available both exceed the window**, one by
    ~4x. The number (10 s, "twice the engine's own 5 s give-up budget") was derived from the
    *engine's* internal timeout, not from either flown case's actual duration. Before merging,
    either (a) widen the window to something that could plausibly have covered sortie 1's 39 s
    recovery (with the explicit tradeoff — 2026-11-28's own doc already states a longer window
    risks masking a genuinely dead channel for longer — stated to the user, not silently decided),
    or (b) say explicitly, in the debug note and to the user, that this fix is a stopgap not shown
    to close either flown case, and that a re-fly is needed to find out whether it helps at all.
    Shipping it framed as "the fix" for a bug neither reproduction demonstrates it fixes is the
    required change.

- **Sortie 1's eventual recovery is not actually explained, and the unexplained part matters to
  whether the diagnosis is even right.** The debug note states the give-up is *permanent* "until
  the next genuine `fd_mode` edge," and separately states no further `fd_mode` edge was logged
  between the take and the late write. Both can't be true if the engine's documented contract is
  accurate — something resolved it. I checked `controls_to_petrovich_edge` (`belief/
  flight_authority.py`): it compares `fd_mode` by value every poll (`GET /flight_desired/latest`),
  independent of the throttled command-channel `flight cmd`/`ack` lines the debug log actually
  shows. The debug log **only logs acks for body-layer's own outbound seq'd commands**, not every
  raw sample of `fd_mode` — so a transient flicker off `"m1"` and back (a genuine edge, which
  *would* legitimately re-fire the trigger with no fix needed) is invisible in this log and was not
  ruled out, only "not provable from the two sorties' logs alone" per the note's own "Hypothesis"
  section. This is a real fork: if sortie 1 recovered via an actual edge, the give-up hypothesis
  may be describing a problem that didn't happen that way, and the fix is solving a different
  (also real, per sortie 2) but not identical failure. This isn't fatal to merging a stopgap, but
  it should be said plainly rather than left as "could not be pinned down further" — the Reviewer
  checklist's instruction to flag this as a required fix if found applies here in the weaker form:
  *the uncertainty itself, and what it means for whether 10 s is even the right kind of number,
  should be stated to the user before they fly on this fix expecting it to be the fix.*

### Optional Refinements

- The debug note's own "Recommended testing aid for the next sortie" (a `read_args`/
  `write_cockpit_switch` latency log) is the right next step and would resolve both required
  fixes above empirically instead of by inference. Worth doing before the next SAU-related sortie,
  not instead of stating the above to the user now (optional only in the sense that it's already
  correctly flagged as a testing aid, not scope creep for this fix).
- `SAU_TAKEOVER_RETRY_WINDOW_S`'s `hi=30.0` bound is itself below sortie 1's observed 39 s — if the
  window is widened per the required fix above, the bound needs raising too, not just the default.

### Checks run

- `ruff format --check src tests`: clean (236 files).
- `ruff check src tests`: clean.
- `cd body-layer && .venv/bin/mypy src`: clean, 96 files.
- `pytest tests/test_body.py -q -m "not slow"`: 265 passed. (`effector_engine.py` itself is
  untouched by this commit, so its own test file was not re-run separately — the three new tests
  exercise the real engine through the poll loop, which is the right level for this fix.)
- Tests are meaningful, not decorative: they drive the real poll loop with a synthetic
  non-absolute effector matching the real SAU buttons' shape (correctly rejecting `observ`, the
  pre-existing absolute stand-in, as the wrong fixture — explained in its own docstring), and cover
  the three load-bearing properties: recovers within the window, never fires past the window, and
  never fires after the handover reverses, plus the no-duplicate-write case via `assumed_writes`.
- Tunable: `SAU_TAKEOVER_RETRY_WINDOW_S` declared via `tuning.real` with `lo=5.0, hi=30.0`, status
  `judgement`; checked the **rendered** `config/defaults.toml` (not just the `#:` comment) — the
  generator correctly emitted the first sentence in full (no truncation/markup defect found this
  pass); the dropped second sentence (pointer to the field's own docstring, plus a line about not
  masking a genuinely dead channel) is elaboration, not a warning this convention requires to
  survive, so no defect there.
- Bounded/no-interaction correctness: confirmed by reading the `elif` branch in `body.py` (clears
  on window elapse or on `fd_mode` leaving `"m1"`, never re-fires past either) and by the
  `assumed_writes` mechanism in `effector_engine.py` (a re-fire after an already-successful write
  reads the fresh value and self-check-skips, never double-writes) — matches the three new tests'
  own assertions.
- Debug note read in full; its own evidence section was independently re-checked against the raw
  logs rather than taken on faith (see Required Fixes above for where that re-check disagreed with
  the note's framing, not its facts).

### Verdict
NEEDS REVISION

The mechanism is sound and well-tested for what it claims to do; the problem is what it claims to
do does not match the only evidence available. Before this merges, the user should hear plainly
that the 10 s window does not cover either flown sortie, and either the window gets widened with
that tradeoff stated, or the fix proceeds as an explicitly-labeled stopgap awaiting a re-fly with
better instrumentation — not as a closed bug.

### Review Confidence
Full read — debug note, `body.py`'s diff in full, `effector_engine.py`'s and
`flight_authority.py`'s relevant sections, both sortie debug logs' take/ack/write windows (grepped
and read in context), sortie 2's flight-trace file end-to-end for the ~46 s duration claim, the
three new tests in full, and the rendered `defaults.toml` entry.
