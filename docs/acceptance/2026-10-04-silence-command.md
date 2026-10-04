# `silence` command sortie

**Cockpit card (published):** https://claude.ai/artifact/XJxhmMrmYMfTSHQC3dPS4m — the same content
below, laid out for reading in glances. This file stays the source of truth.

**Branch: `feature/silence-command`** (tip `de6c530` — not merged as of this card; DoD's
mechanical gate, Reviewer and Security have all passed):

```sh
git checkout feature/silence-command && git pull
```

## Why this card exists

You asked for a way to tell Petrovich to go quiet — "there's a lot of units around, like friendly
airbase, I can tell him to be quiet. Or during radio traffic." Any subsequent command ends it. You
chose, when asked: absolute silence, including urgent threat callouts, and one spoken word of
acknowledgement (`"Quiet."`) before he goes quiet.

This has been reviewed and checked statically — the choke point is singular, the ack is provably
spoken before the mute takes effect, and it cannot get stuck on. **None of that answers whether it
works for you in the seat**: whether the recogniser actually hears your phrasing, whether one word
of ack is the right amount, and whether absolute silence is still what you want once a real threat
shows up while you're muted. Only flying it answers those.

## Setup

Three-process pattern, same as recent cards. From `run-scripts/` on the Mac, Windows collector
already running:

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text.sh
```

**Describing what `run-crew-text.sh` does on this branch, not quoting it verbatim** — you have your
own local edits to these scripts, so check your own copy rather than assuming it matches this
description exactly. As committed on this branch, it runs body-layer's `logger.py` with
`--speech-audio --speech-input --crew-text --f10-commands --audio-adapter-url http://127.0.0.1:7795
--brain-client http --brain-url http://127.0.0.1:7796 --speech-log ~/dcs-speech.jsonl`, forwarding
any extra arguments you pass it. If your own copy already sets some of these as defaults, don't
pass them twice. `--speech-log` is worth keeping — it's the only record of what the recogniser
actually heard if a phrase misfires.

## The three phrases — unbenched

- `"silence"`
- `"be quiet"`
- `"shut up"`

**No recordings exist of you actually saying any of these.** Unlike the F10 vocabulary, which went
through a full accent-adapted benchmark, these three were only checked against the matcher's text
logic (collision-tested against the existing command set and a handful of adversarial sentences —
"be careful", "shut the door", "silence is golden", etc. — all come back clean). Recognition
accuracy on your voice, with your accent, is unmeasured. **Report which phrasing the recogniser
actually resolves to `silence`** — that's cheap for you to notice flying and expensive for anyone
else to guess at from a transcript.

## What to expect

1. Say one of the three phrases.
2. **Petrovich says "Quiet." — one word — and then says nothing else until your next command.**
3. This includes danger calls. If a threat appears while you're silenced, **he will not warn you
   about it.** That was your own choice when this was built, and it's worth remembering at the
   exact moment you'd otherwise expect to hear him. The text/overlay readout (if you're running it)
   keeps working throughout — only the spoken audio goes quiet.
4. **Any dispatched command ends silence** — a scan, a watch, a cancel, anything that actually
   does something. Its own response is spoken normally.
5. **Stray speech the recogniser does not resolve into a command does NOT end silence.** This is
   the radio-traffic case the command exists for — talk over him, nothing changes.

## One quirk, so it doesn't read as a bug

`"stop"` (the existing `stop_talking` command) also ends silence, because it's a dispatched
command like any other — even though its own job is a different thing ("stop talking right now"
vs. "say nothing from here on"). Harmless: nothing is queued to interrupt if nothing was ever
spoken while silenced. If you hit `"stop"` while muted and hear him come back, that's expected, not
a defect.

## What is NOT wired

**No DCS F10 radio-menu button for `silence`.** Voice is the only way to reach it today. The
dispatcher already accepts the token generically — adding an F10 entry later is a Hook-script-only
change, no body-layer work needed.

## Pass criteria

The feature passes if all three phrases are reachable in some form, the ack is heard once and only
once per `silence`, nothing is spoken while silenced (including any threat that appears), and any
real command — including an accidental `"stop"` — brings him back.

## Bring back

1. Which of the three phrases did the recogniser actually catch, and did any need repeating?
2. Did one word of acknowledgement (`"Quiet."`) feel like the right amount, too little, or too
   much?
3. Did a threat actually appear while you were silenced, and if so — now that you've felt it in
   the seat — does absolute silence (no exception for danger) still feel like the right call, or
   would you want urgent callouts to break through next time?
4. Anything that surprised you.

Anything that surprises you is worth more than anything on this list.
