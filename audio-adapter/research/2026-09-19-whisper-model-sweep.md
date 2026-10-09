# How light can the whisper model go?

<!-- doc-provenance:start -->
**Topics:** #speech-recognition #push-to-talk
**Evidence for:** [[AA-4.1]]
<!-- doc-provenance:end -->

**Date:** 2026-09-19 · whisper.cpp 1.9.4, Apple Silicon (Metal) · corpus: 252 clips, the user's own
voice, headset, Windows-recorded · all rows use `--prompt` (`vocabulary.to_prompt()`)

| model | size | accuracy | **safe misses** | **unsafe wrong commands** | latency med / p90 / max | verbatim |
|---|---|---|---|---|---|---|
| `tiny.en` | 74 MB | 95.2% | 4 | **7** | 0.23 / 0.65 / 0.74 s | 208/240 |
| `base.en` | 141 MB | 97.6% | 4 | **2** | 0.28 / 0.29 / 0.84 s | 216/246 |
| `small.en` | 465 MB | 99.2% | 2 | **0** | 0.50 / 1.46 / 1.68 s | 231/250 |
| `medium.en` | 1.4 GB | 99.6% | 1 | **0** | 1.07 / 1.14 / 3.20 s | 236/251 |

> **FLAG 2026-09-21 — the `tiny.en` row does not balance, by one.** 95.2% of 252 is 240 correct
> (and the verbatim column's own denominator agrees: `208/240`), which leaves **12** errors — but
> the row lists 4 safe + 7 unsafe = **11**. Every other row balances exactly: `base.en`
> 246 + 4 + 2 = 252, `small.en` 250 + 2 + 0 = 252, `medium.en` 251 + 1 + 0 = 252. So either the
> accuracy or one of `tiny.en`'s two error counts is off by one.
>
> **Which one is wrong cannot be determined from this repository** — the 252-clip corpus is not
> committed, so the bench cannot be re-run. Recorded as unresolved rather than guessed.
>
> **Nothing in this note's conclusions depends on it.** The argument is that unsafe errors are the
> column that matters and that `tiny.en`'s 7 (or 6, or 8) of them is disqualifying against
> `small.en`'s 0 — a one-count difference in either direction leaves that untouched, as it does
> the "roughly one every 36 transmissions" figure downstream.

## Accuracy is the wrong column to read

Errors are not interchangeable, and the split matters more than the total.

A **safe miss** returns no match, so Petrovich asks the player to say again. It costs a repeat and
the player knows it happened.

An **unsafe error** returns a *different valid command*. Petrovich does the wrong thing, confidently,
with nothing to flag it — the player finds out by watching the aircraft do something they did not
ask for. On a two-tier design one of these is worse still: a command misheard as the wake word (or
the reverse) routes the whole transmission to the wrong interpreter.

`tiny.en` produces exactly that class:

```
'scan all around' -> scan_bearing_n    wrong sector scanned
'what do you see' -> wake_petrovich    wrong TIER, free speech vs command
'repeat that'     -> scan_bearing_se   confidence 0.81
```

Seven unsafe errors in 252 is roughly one every 36 transmissions. Its 95.2% headline is only 4
points below `small.en`, which is why the headline is misleading: the difference between them is
not 4% of accuracy, it is seven wrong actions against none.

## The latency argument does not favour the small models either

`base.en` is the surprise: a **tighter tail than `small.en`** (p90 0.29 s against 1.46 s) despite
`small.en` having the better median-to-p90 story on paper. For a push-to-talk path the tail is what
the player feels — one long wait reads as an unresponsive crew, while a good average hides it.

But the absolute numbers are all small. `small.en` at a 1.46 s p90 and `medium.en` at 1.14 s are
both inside what a real crew member takes to answer; `docs/acceptance/2026-09-18-stage6-sortie.md`
already judged ~0.6–0.8 s as reading like thinking rather than lag, and a second is not far outside
it. **Nothing here is fast enough or slow enough to override the safety column.** Dropping from
`small.en` to `base.en` buys roughly 0.2 s of median latency and costs two wrong actions per 252
transmissions.

## Recommendation

**`small.en`.** It is the lightest model with zero unsafe errors on this corpus, and the 465 MB
sits on the Mac that already hosts the brain layer, where neither disk nor memory is contended.

`medium.en` buys one additional safe miss recovered (99.2% to 99.6%) for 3x the size and 2x the
median latency — not worth it, though worth remembering as the escape hatch if live conditions
prove harder than a recording session.

`base.en` becomes interesting only if this ever has to run on the Windows box alongside DCS, where
memory is genuinely contended. Its two unsafe errors would need mitigating another way first — the
confidence-band reject is the obvious candidate, since one of them (`'scan bearing T15'` at 0.70)
sits below the correct-answer mean.

## Caveat

One speaker, one headset, one quiet room, 252 clips. The unsafe-error counts are small integers, so
the ordering between `tiny` and `base` is solid but the gap between `small` and `medium` is within
noise.

**Simulator noise is not a factor, and assuming otherwise would send someone chasing a
non-problem** (user correction, 2026-09-19): engine, rotor and cockpit audio go to the player's
headphones, not into the room, so a boom mic never captures them. This is a materially easier
acoustic environment than a real cockpit, and the corpus is representative of it rather than
optimistic about it.

What genuinely differs in flight is narrower and worth naming precisely: the player is speaking
while flying, so transmissions come faster, more clipped, and sometimes mid-manoeuvre, where a
recording session invites careful delivery. Ordinary room noise — fans, keyboard, a headset
knocked — also remains. The sortie tests those; it does not need to test cockpit audio.
