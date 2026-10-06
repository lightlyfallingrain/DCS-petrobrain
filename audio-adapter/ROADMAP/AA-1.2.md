# AA-1.2 — Stage 2 — aircraft-layer playback channel

- [x] **Stage 2 — aircraft-layer playback channel.** #status/done `POST /audio/play` on the existing
  collector (JSON body, base64 WAV, matching the shape of `/text/push` rather than adding a
  second request-parsing path) and `AudioPlaybackSender`: one worker thread draining a queue,
  FIFO for routine lines, urgent lines clearing the queue and interrupting in-flight playback.
  The interrupt mechanism is isolated in a single function precisely because it is the part
  stage 5 is most likely to change.
