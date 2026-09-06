"""The one place mapping a base-store path to its probe-store sibling, so
no consumer hardcodes the `-probe` suffix convention.
"""

from pathlib import Path


def probe_store_path(base_db_path: Path) -> Path:
    """`data/world-model/<region>.sqlite` -> `data/world-model/<region>-probe.sqlite`."""
    return base_db_path.with_name(f"{base_db_path.stem}-probe{base_db_path.suffix}")
