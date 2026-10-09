# AA-4.4 — Stage 4 — capture

<!-- doc-provenance:start -->
**Topics:** #push-to-talk
<!-- doc-provenance:end -->

- [x] **Stage 4 — capture. FLOWN AND ACCEPTED 2026-09-23.** #status/done Built 2026-09-22
  (`feature/inbound-speech-stage4`). Voice through the live path works: the clip is captured,
  recognised, dispatched and read back.

  `ptt_source.py` (`PTTSource` protocol, `JoystickPTT` over winmm, `KeyTogglePTT` for the Mac),
  `audio_capture.py` (`SoxRecorder`, `ClipGate`), `capture_loop.py` (`CaptureLoop`),
  `transcribe_client.py`, and `python -m audio_adapter.capture`.

  **Two deviations from the plan, both narrowing it:**
  - **sox, not `ffmpeg -f dshow`.** Part of Stage 4's stated job was discovering the dshow device
    name for the user's headset — but `tools/record_corpus.py` already recorded 252 corpus clips
    through that exact headset with sox, so the driver name, input-argument order, buffer size
    and truncation repair are all already settled against the hardware that matters. A second
    audio binary would have re-learned them and added a dependency.
  - **A real PTT, not the planned manual `--capture-window-s` trigger.** The stub existed to
    avoid a DCS dependency; a joystick button avoids it just as completely while being the
    actual gesture, so the trigger never has to be replaced — only the source behind the
    protocol, which is what Stage 5 does.

  **The joystick doubt is closed — probed on the Windows box 2026-09-23.** `joyGetPosEx` reports
  **four devices (ids 0-3)**, so a multi-device pit does appear under legacy ids rather than only
  the first controller, and a real press-and-hold on **device 2, button 0** was read cleanly at
  **613 ms held**. Both halves of the doubt answered at once: the API sees the hardware, and it
  reports a *held* state rather than an edge. Windows therefore gets the real gesture — hold to
  talk — where the Mac's keyboard source can only offer press-to-start/press-to-stop.

  Capture on that box is `--ptt joystick --joystick-device 2 --joystick-button 0`. Note the button
  is 0-based as the API and the probe report it; DCS's own binding UI numbers from 1, so this is
  "JOY_BTN1" there.

  **The finding worth carrying forward: the first ~0.14 s after a press is not captured.** sox
  returns from `Popen` in ~2 ms but the audio device is not open yet, and the loss is a fixed
  open cost, not a proportional one — four runs at holds from 0.6 s to 2.0 s lost 0.134-0.144 s
  every time. `record_corpus.py` solved the same thing with a 0.35 s preroll before prompting,
  which a PTT gate cannot do because the press *is* the prompt. Left uncorrected on purpose: the
  natural press-then-speak gesture leaves more than that, and the fix (a permanently hot mic with
  the pressed interval trimmed out of a rolling recording) costs continuous capture and file
  rotation to buy something no evidence yet says is needed. If Stage 6 shows first words clipped,
  that is the fix, and the measurement is recorded so it is not re-derived.
