# Open flight tests — results, 2026-10-20

Results reported by the user against the "Open Flight Tests" card
(https://claude.ai/artifact/KKM2itxEjKGG7uY6MVCh8c). IDs are the card's.
Recorded as reported, mid-session; log review is still owed.

## Reported

User, verbatim:

> P1-2 done
> A1-A5 ok, pass
> A10, A11, A13, A17 - ok, pass
>
> I'm continuing testing

| ID | card item | result |
|---|---|---|
| P1 | deploy three Hooks | done |
| P2 | start the stack | done (all but brain on Windows; Piper + whisper on Windows) |
| A1 | radio check and greeting (BL-B81) | pass |
| A2 | quiet on the ground (BL-B82) | pass |
| A3 | mission start signal (BL-15) | pass |
| A4 | scanning resumes after lift-off (BL-B82) | pass |
| A5 | kneeboard memory (BL-8) | pass in the cockpit; entry count still to be checked in `mission-memory.jsonl` |
| A10 | attack-run guidance (BL-14, BL-B70) | pass; repeat rate still to be counted from the log |
| A11 | danger from astern (BL-11) | pass |
| A13 | something burning (BL-B72, AC-B7) | pass |
| A17 | restart the same mission (BL-15, BL-B68) | pass |

No per-question answers (A1.1, A10.4, …) were given — "ok, pass" for each.

## Stack deviations from the card

The card's P2 has audio-adapter on the Mac with `say`. This flight ran the
audio-adapter on Windows with Piper (AA-6, `feature/audio-adapter-os-independent`)
and whisper.cpp `b5454` (`whisper-bin-x64.zip`, v1.9.5) for STT; brain on the Mac.

## Later results (same day)

User, verbatim:

> A15 - ok, pass.
> A14 - cannot test, free speech from brain not implemented
> A16 - ok, pass

| ID | card item | result |
|---|---|---|
| A15 | callouts about unseen contacts (BL-W6) | pass |
| A14 | the brain, in his own words (BR-1, BR-B1) | **not testable**: "Petrovich, …" gets "say again" (sortie feedback F2, the wake word anchors as a command verb), so free speech never reaches the brain |
| A16 | FARP landing (BL-B82, BL-B81) | pass |

A8 (9K113) and A12 (gun fire) produced sortie feedback F4–F6, now being built
(`feature/9k113-narrow-search`; `fix/taking-fire-visible-shooter` merged).

User: *"A18 - ok, pass"*.

| A18 | wrong theatre, then back (BL-15) | pass |
|---|---|---|

## Still open

A6, A7, A9, B, C, L.
