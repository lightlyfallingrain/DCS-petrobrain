# Voice command sortie — Stages 4 and 5

**Branch: `feature/inbound-speech-stage4`.** Both stages are on it, stacked, plus the spoken-vocabulary
fixes already merged to main.

```sh
git checkout feature/inbound-speech-stage4 && git pull
```

This is the first flight where you talk to Petrovich and he does something about it.

| stage | what it added |
|---|---|
| 4 | capture: hold a control, speak, release, the clip is recognised and dispatched |
| 5 | the talk control is the aircraft's own intercom trigger — arg 738, right press |

163 audio-adapter tests, 175 aircraft-layer, 940 body-layer.

---

## Block 0 — on the ground, before you fly. **DO THIS FIRST**

It needs no DCS, no Windows, no trigger, and it answers the one question everything else assumes:
**does your voice go through this chain at all?** Two terminals on the Mac.

```sh
cd audio-adapter
PYTHONPATH=src .venv/bin/python -m audio_adapter --whisper-model ~/whisper-models/ggml-small.en.bin
```

```sh
cd audio-adapter
PYTHONPATH=src .venv/bin/python -m audio_adapter.capture
```

Space starts, space stops. Say **"scan ahead"**. Then:

```sh
curl http://127.0.0.1:7795/transcripts/poll
```

**Expect** one row, `"token": "scan_ahead"`, confidence around 0.8.

**If this fails, stop here** — nothing in the air will work, and you will have spent a sortie
finding out. The likely causes are all local: macOS has not granted the terminal microphone access,
the adapter was started without `--whisper-model` (every clip then 503s), or sox is picking up the
built-in mic rather than your headset (`--input-device`).

- [ ] Does it come back `scan_ahead`?
- [ ] How long between releasing space and the row appearing?

---

## Setup for the flight

**Deployment — the wire format changed again.** `Export.lua` now publishes the trigger, and the F10
menu gained a Stop submenu, so **both** files are stale on the Windows box:

```
copy "<repo>\aircraft-layer\dcs-export\Export.lua" ^
     "%USERPROFILE%\Saved Games\DCS\Scripts\Export.lua"
copy "<repo>\aircraft-layer\dcs-export\petrobrain-f10-commands-hook.lua" ^
     "%USERPROFILE%\Saved Games\DCS\Scripts\Hooks\"
```

**Watch the collector's first lines after DCS connects:** `wire-format version 2026-09-23a
(matches)`. A `VERSION MISMATCH` means the copy did not take, and the trigger will read as
permanently released.

**Three processes.** Windows — **note the two `cd`s: these are different subprojects**, and
`PYTHONPATH=src` is relative to whichever one you are standing in:

```
cd <repo>\aircraft-layer
set PYTHONPATH=src
python -m collector
```
```
cd <repo>\audio-adapter
set PYTHONPATH=src
python -m audio_adapter.capture --adapter-url http://<mac-ip>:7795 --ptt dcs
```

Capture is stdlib-only, so no venv is needed for it on Windows — but it does need `sox`.

**From WSL, name the sox binary explicitly.** A Windows Python launched from WSL inherits *WSL's*
`PATH`, which Windows cannot use, so sox is installed, working, and invisible:

```bash
cd /mnt/c/<path>/DCS-petrobrain/audio-adapter/src
python.exe -m audio_adapter.capture --adapter-url http://<mac-ip>:7795 --ptt dcs \
  --sox-binary 'C:\Program Files (x86)\sox-14-4-2\sox.exe'
```

Mac, two terminals:

```sh
cd audio-adapter
PYTHONPATH=src .venv/bin/python -m audio_adapter \
  --host 0.0.0.0 \
  --target aircraft-layer --aircraft-layer-url http://<windows-ip>:7791 \
  --whisper-model ~/whisper-models/ggml-small.en.bin
```

**`--target` defaults to `local`,** which plays Petrovich through the Mac's speakers — right for
auditioning a voice at a desk, wrong for a cockpit. Without it you will hear him, just not where
you are flying.

The two URLs point in opposite directions and are easy to cross: `--host 0.0.0.0` is the adapter
*listening* so Windows can reach it, and `--aircraft-layer-url` is the adapter *calling back* to
the collector to play the WAV through `winsound` on the Windows box.

**`--host 0.0.0.0` is not optional for this flight.** The adapter defaults to loopback because it
was built as a Mac-local service; the capture process calling in from Windows is a new role. Without
it the Windows box cannot reach it at all, and the symptom looks like a firewall problem.

macOS will then block the incoming connection until the *resolved* interpreter is allowed — the
venv's `python` is a symlink, and the firewall registers what it points at
(`python -c "import os,sys; print(os.path.realpath(sys.executable))"`). Click **Allow** on the
prompt, or add it with `socketfilterfw --add` / `--unblockapp`. The Homebrew path carries a version
number, so a Python upgrade silently revokes the permission.

Check from Windows before flying: `curl http://<mac-ip>:7795/transcripts/poll` should answer `[]`.

```sh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<windows-ip>:7791 \
  --theatre Syria \
  --world-model-db <path-to-region.sqlite> \
  --crew-text --overlay --f10-commands --speech-input \
  --speech-audio --audio-adapter-url http://127.0.0.1:7795
```

`--audio-adapter-url` stays on loopback — the logger and the adapter are both on the Mac. It is
`--speech-audio` that makes Petrovich audible at all; `--speech-input` is the other direction.

**`--speech-input` is the one that makes this flight different.** Without it the logger never polls
for transcripts and every command you speak lands in a queue nobody drains.

**What you can say** — the same vocabulary the F10 menu already has:

`scan ahead` · `scan left` · `scan right` · `scan full` · `scan north` (and the seven other compass
points) · `watch nearest` · `watch nearest air defence` · `cancel task` · `report` · `report north`
(and the rest) · `stop` · `say again` · `nevermind`

---

## Not testable this flight

- **"stop scan" and "stop watch" by voice.** They exist on the F10 menu only. The adapter's
  vocabulary is a hand-synced third copy whose 99.2% gate was measured on a recorded corpus, and
  that corpus has no phrases for the two new tokens — adding them unbenched would put unmeasured
  tokens into the one part of the chain established by measurement. Spoken `cancel task` still
  cancels everything.
- **The intercom switch does not gate anything.** Petrovich hears you with the SPU-8 off. That work
  is deferred at your direction.
- **Barge-in, free speech, wake-word listening.** None of it is built.

---

## 1 — Does the real trigger work? **THE PRIZE**

**Do.** Right-press the stick trigger to the intercom stop, hold, say **"scan left"**, release.

**Expect.** A readback — *"Scanning left."* — and his gaze actually going left.

**Record.**
- [ ] Does a right-press-and-hold produce a command at all
- [ ] Time from release to readback, roughly
- [ ] Any press that produced nothing
- [ ] **Does a press feel like it starts capturing immediately**, or do you have to wait a beat

---

## 2 — Does a radio call stay out of it?

The sharpest thing in this stage, and the one you cannot check any other way.

**Do.** Three things in order:
1. A **full press**, speak a command, release. ("scan right", so you can see whether it took.)
2. A **quick full press** — a normal radio call, no dwell at the half stop.
3. A **slow full press** — squeeze deliberately through the intercom stop to the radio stop.

**Expect.** None of the three reaches Petrovich. (1) and (3) should show a `dropped: radio press`
line in the capture terminal; (2) should produce **nothing at all**, not even a dropped line.

That difference is the whole design: the debounce stops a capture ever starting on a fast press,
and the radio-stop latch catches a slow one that dwells past it. A full press transits the intercom
stop for 19–32 ms — measured on your own probe — so without both, every ATC call would open a
recording.

**Record.**
- [ ] Did a full press ever execute a command
- [ ] Case 2 — silent, or a dropped line?
- [ ] Case 3 — dropped for the radio reason?
- [ ] Does the two-stage trigger feel natural to use this way, or is the half stop fiddly under load

---

## 3 — The first syllable

**Do.** Deliberately both ways: press **then** speak, and press **while already speaking**.

**Expect.** Press-then-speak works. Speaking into the press may lose the verb — ~0.14 s of the
front of every clip is the audio device opening, measured and not yet corrected.

**Record.**
- [ ] Does press-while-speaking actually fail, or does it survive
- [ ] Does press-then-speak feel like a natural gesture or an imposition
- [ ] Any transcript that looks like a beheaded word (`"an east"` for `"scan east"`)

**This decides whether the hot-mic fix gets built.** It costs continuous recording and file
rotation, so it should be paid for by evidence, not by caution.

---

## 4 — Does it hold up over a sortie?

**Do.** Use voice as the command surface for the whole flight. Mix commands with normal radio use.

**Record.**
- [ ] False fires — anything executing that you did not say
- [ ] Misses — anything you said that produced nothing
- [ ] `say again` frequency: useful, or nagging
- [ ] Does F10 remain more convenient for anything, and if so which

---

## 5 — Fallback, if the DCS trigger misbehaves

The joystick path still exists and is independent of DCS entirely:

```
python -m audio_adapter.capture --adapter-url http://<mac-ip>:7795 ^
    --ptt joystick --joystick-device 2 --joystick-button 0
```

Worth trying if block 1 fails, because it separates *"capture is broken"* from *"the trigger feed
is broken"* — two different fixes.

- [ ] Does the joystick path work where the DCS one did not

---

## Bring back

1. Whether the real trigger works — **the prize**
2. Whether radio calls stay out, all three cases
3. Whether the first syllable survives, and your call on the hot-mic fix
4. False fires and misses over the sortie
5. The capture terminal's output — it names every drop and its reason

**Anything that surprises you is worth more than anything on this list.**
