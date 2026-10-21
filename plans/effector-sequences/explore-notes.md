# Explore notes — configurable cockpit effector sequences (BL-B90)

2026-10-21, main loop with the user. Concept: `docs/concept/configurable-cockpit-effector.md`
(the user's, "concept, not final truth").

## Ordering

- The BL-B66 Stage 5 sortie flies on the **current hard-coded** build — *"I'll test the current
  BL-B66 implementation as it is, that is valuable info already. But the sequences would then be
  moved from hard coded to sequence file."*
- **The slew stays code**: *"The really important part of BL-B66 is the sight slewing and that
  *will not* move to sequence file, that is code only."* Slewing now lives in `[[BL-B80]]` (split
  2026-10-17), so this entry goes before BL-B80.

## Decisions

1. **Named effectors in one registry file** — *"very good, yes"*. Sequence files reference
   effector names and named values (`sight-power` = `on`); device / command / arg numbers live only
   in the registry. Reason: a write needs device + command, a readback needs the arg number, and
   the numbers are positional (an ED patch can shift them) — one file to fix.
2. **First-cut scope: replace BL-B66's hard-coded sequences only** — *"yes, BL-B66 first, expand
   later"*. Triggers `takeoff` (four-switch power-up), `observ-on`/`observ-off`,
   `weapons-arm`/`weapons-safe`; conditions on effector state; `wait_s`. Deferred: OAT, light
   level, `mission-start`, `taxi`, `land`, `guidance-unit-ready`, `atgm-*`, `target-destroyed`.
3. **Gating and refusals stay in code** — *"keep in code. I may put some logic into those files,
   but most such things are dependent on aircraft state at level we better keep in code. Subject to
   change, but that's a much larger scope for later if ever."* So e.g. "Unable, guidance unit not
   ready" stays where it is; files describe switch moves. A failed row condition skips that row.
4. **Overlapping triggers queue** — *"queue. Better keep state integrity as much as we can."* A
   sequence triggered while another runs waits behind it; nothing cancels a running sequence.
5. **Readback is registry-driven, low frequency** — *"yes. Also, low frequency update is enough
   for non-axis effector reads. If there are exceptions, we'll deal with them separately."*
   Export.lua reads the args the registry names (body-layer sends the list), at a low rate, instead
   of the fixed eight per frame. Needs a Windows redeploy.
6. **Load at startup, fail loudly** — *"restarting body layer is acceptable. I'd rather a check at
   startup and error than finding out in middle of flight. These are not meant to be edited all
   the time, but that will happen quite a bit until the sequences stabilize."* Validation covers:
   unknown effector/value names, unknown trigger, duplicate (aircraft, role, trigger), malformed
   rows. No hot reload.

## Carried from the concept, unchanged

- 1 s between effectors (existing tunable `GUIDANCE_UNIT_SWITCH_DELAY_S`); axes excluded.
- Role mismatch → sequence does not run. Only Mi-24P / copilot exist now.
- Triggers are a code enumeration; fire on the transition, not while true.
- Format: proposed TOML registry + markdown-table sequence files (the concept's own shape); user
  accepted the registry, did not object to the markdown sequences. Architect may confirm.
