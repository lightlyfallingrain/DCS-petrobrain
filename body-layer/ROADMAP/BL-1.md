# BL-1 — Observation ingestion (≈ PB-1)

- [x] **BL-1 — Observation ingestion (≈ PB-1, done 2026-09-08).** #status/done `feature/pb1-perception-logger`.
  Hybrid HelperAI perception source + association + text logger. Live acceptance on a real Mi-24P
  sortie with manually-placed ground targets; plausible bearing/range in an ambiguous-candidate
  scenario (4 clustered Ural trucks). Original two-tier architecture falsified by a live spike and
  pivoted to a single hybrid implementation (HelperAI text as detection gate, `LoGetWorldObjects`
  geometry via association). Full history: `plans/pb1-perception-logger/`.

