---
name: reference_srs_source_for_device_args
description: DCS-SimpleRadioStandalone's own GitHub repo is a reliable, fetchable primary source for per-airframe cockpit device/argument numbers (GetDevice/get_argument_value calls), and gh search code/gh api works for it in this environment.
metadata:
  type: reference
---

DCS-SimpleRadioStandalone (github.com/ciribob/DCS-SimpleRadioStandalone) ships one Lua exporter
per supported airframe under Scripts/DCS-SRS/Scripts/DCS-SRS-Modules/<Airframe>.lua (e.g.
Mi24P.lua), each reading real cockpit switches/knobs/triggers via
GetDevice(0):get_argument_value(<arg>) wrapped in small helpers (SR.getButtonPosition,
SR.getSelectorPosition) defined in the sibling core file
Scripts/DCS-SRS/Scripts/DCS-SimpleRadioStandalone.lua. This is a live, actively maintained,
version-controlled primary source for per-airframe device/argument numbers -- useful any time an
investigation needs to know which get_argument_value arg corresponds to a specific cockpit
control (PTT, radio selectors, hot-mic, intercom, etc.), especially for airframes this project has
not yet fully reverse-engineered its own clickabledata dump for.

Tool access that worked this session (contradicts an earlier memory note claiming gh is
unavailable -- that was apparently session/environment-specific, not a durable fact): `gh search
code "<symbol>" --repo ciribob/DCS-SimpleRadioStandalone` finds the right file fast, then `gh api
repos/ciribob/DCS-SimpleRadioStandalone/contents/<path> --jq .content | base64 -d` fetches the raw
file content directly -- faster and more reliable than WebFetch on a github.com/.../blob/...
URL, which returned an AI-summarized paraphrase rather than exact source in this session (usable
for orientation, not for quoting exact code/arg numbers). Try gh first for any GitHub source
fetch where exact text matters.

Cross-validation pattern worth repeating: when SRS's source names an arg number for a project
this repo has already independently reverse-engineered a clickabledata dump for (e.g.
aircraft-layer/research/mi24p-command-surface.md for the Mi-24P), check whether any of SRS's
other arg numbers for the same airframe also appear in that dump. Two independently-sourced files
agreeing on an arg number for the same exact DCS version is much stronger evidence than either
alone -- this caught/confirmed SPU-8 args 455/456 this session (project's own dump) matching SRS's
Mi24P.lua exactly, which then backed confidence in a third, not-independently-confirmed arg
(738, the PTT trigger) from the same file. See
aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md.
