"""Shared test constants.

`REAL_SAMPLE_MIZ_PATH` points at the real, gitignored sample mission
(`mission-interpreter/research/samples/Mission 02-Bagram.miz` -- see the
repo root `.gitignore`, third-party campaign content not licensed for
redistribution). Tests that depend on it must guard with
`@pytest.mark.skipif(not REAL_SAMPLE_MIZ_PATH.exists(), reason=...)` so the
suite still passes in a checkout that doesn't have this file locally.
"""

from __future__ import annotations

from pathlib import Path

REAL_SAMPLE_MIZ_PATH = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "samples"
    / "Mission 02-Bagram.miz"
)
