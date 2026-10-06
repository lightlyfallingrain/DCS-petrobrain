# AA-1.5 — Stage 5 — live Windows verification

- [x] **Stage 5 — live Windows verification. Passed 2026-09-18** #status/done, after one real failure and a
  fix.
  - **Playback works.** `winsound` plays audio on the Windows box, cross-machine, end to end.
  - **Urgent preemption failed first time round.** A long routine line played stubbornly to its
    end, *then* the urgent line was heard, though the queue behind it was correctly discarded.
    Cause — and it is the exact bet the plan flagged: synchronous
    `PlaySound(path, SND_FILENAME)` blocks *inside* the Win32 call, and `SND_PURGE` from another
    thread cannot reach it, because Windows only purges sounds started asynchronously. The
    queue-clear appeared to work because it is pure Python and never touches the audio device,
    which is why the failure presented as partial rather than total.
  - **Fixed and re-tested green** (`fix/audio-urgent-interrupt`): the player starts the sound
    with `SND_ASYNC` and blocks on an interruptible `threading.Event` for the file's own duration
    (parsed from the WAV header) plus a margin; `stop` purges *and* sets that event. An urgent
    line now cuts a routine one off mid-word. The change stayed inside `_WinsoundPlayer` — no
    queue logic moved, which is the plan's decision to isolate the interrupt mechanism in one
    named function paying off exactly as intended.
  - ~~**Still unobserved:** whether the audio ducks or competes against other sound on the
    box.~~ **ANSWERED 2026-09-26 (user): it behaves well — "no, this is good."** Judged in the
    air, not on a bench, which is the only place the question was ever answerable. No work
    follows, and the Stage 6 card need not carry it.
