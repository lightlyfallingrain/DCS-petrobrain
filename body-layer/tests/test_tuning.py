"""Tests for `tuning` -- the behaviour-constant loader (`plans/
configurable-constants/plan.md` Stage 1). Every row of the plan's
"Failure behaviour" table gets its own test here, per the plan's own
Implementation Plan ("Every failure case above covered by a test").

Each test calls `tuning.reset_for_testing()` first so the module-level
cache from a previous test (or from this test file's own earlier import of
`belief`/`perception` modules, which already resolved their own constants
against whatever `PETROBRAIN_TUNING` happened to be at collection time)
does not leak in -- the real production code never does this, since a
real process reads the file exactly once."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

import tuning


@pytest.fixture(autouse=True)
def _reset_tuning_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("PETROBRAIN_TUNING", raising=False)
    tuning.reset_for_testing()
    yield
    tuning.reset_for_testing()


def test_env_var_unset_resolves_every_accessor_to_its_default() -> None:
    assert tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement") == 1.0
    assert tuning.whole("a.b.D", 2, lo=0, hi=10, status="judgement") == 2
    assert tuning.fraction("a.b.E", 0.5, status="judgement") == 0.5
    assert tuning.sequence("a.b.F", (1, 2, 3), status="judgement") == (1, 2, 3)
    assert tuning.table("a.b.G", {"x": 1.0}, lo=0.0, hi=10.0, status="judgement") == {
        "x": 1.0
    }

    resolution = tuning.validate_against_defaults()
    assert resolution.file_status == "unset"
    assert resolution.applied == {}
    assert resolution.rejected == {}
    assert "no override file" in tuning.render_startup_block(resolution)


def test_named_file_missing_warns_and_every_accessor_still_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision 4a's resolution: a named-but-missing file is not fatal --
    every constant stays at its code default, and the startup block says
    so plainly, naming the path."""
    monkeypatch.setenv("PETROBRAIN_TUNING", str(tmp_path / "does-not-exist.toml"))

    assert tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement") == 1.0

    resolution = tuning.validate_against_defaults()
    assert resolution.file_status == "missing"
    block = tuning.render_startup_block(resolution)
    assert "does-not-exist.toml" in block
    assert "no overrides are in force" in block


def test_named_file_unreadable_toml_warns_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "tuning.toml"
    bad.write_text("this is [ not valid toml", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(bad))

    assert tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement") == 1.0

    resolution = tuning.validate_against_defaults()
    assert resolution.file_status == "unreadable"
    assert "no overrides are in force" in tuning.render_startup_block(resolution)


def test_key_absent_from_file_is_silently_defaulted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text("[other]\nX = 1.0\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    value = tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement")
    assert value == 1.0

    resolution = tuning.validate_against_defaults()
    assert "a.b.C" in resolution.defaulted
    assert "a.b.C" not in resolution.rejected


def test_applied_override_reaches_the_accessor_return_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text("[a.b]\nC = 5.0\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    value = tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement")
    assert value == 5.0

    resolution = tuning.validate_against_defaults()
    assert resolution.applied["a.b.C"].value == 5.0
    assert resolution.applied["a.b.C"].default == 1.0
    block = tuning.render_startup_block(resolution)
    assert "1.0 -> 5.0" in block


def test_unknown_key_is_rejected_independent_of_whether_anything_claimed_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The typo case -- no accessor is ever called with the misspelled
    key, so only `validate_against_defaults()` (checked against
    `config/defaults.toml`, not against the live registry) can catch it."""
    defaults = tmp_path / "defaults.toml"
    defaults.write_text(
        "[belief.attack_run]\nATTACK_RUN_ELEVATION_GATE_DEG = 12.0\n", encoding="utf-8"
    )
    path = tmp_path / "tuning.toml"
    path.write_text(
        "[belief.attack_run]\nATTACK_RUN_ELEVATIO_GATE_DEG = 7.0\n", encoding="utf-8"
    )
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    resolution = tuning.validate_against_defaults(defaults_path=defaults)
    assert "belief.attack_run.ATTACK_RUN_ELEVATIO_GATE_DEG" in resolution.rejected
    rejection = resolution.rejected["belief.attack_run.ATTACK_RUN_ELEVATIO_GATE_DEG"]
    assert rejection.reason == "unknown key"
    assert "ATTACK_RUN_ELEVATION_GATE_DEG" in rejection.detail
    assert "12.0" in rejection.detail


def test_wrong_type_is_rejected_and_default_stays_in_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text('[a.b]\nC = "not a number"\n', encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    value = tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement")
    assert value == 1.0

    resolution = tuning.validate_against_defaults()
    assert resolution.rejected["a.b.C"].reason == "wrong type"


def test_bool_is_not_accepted_as_a_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`bool` is an `int` subclass in Python -- TOML's `true`/`false` must
    be rejected as a type mismatch, not silently accepted as `0`/`1`."""
    path = tmp_path / "tuning.toml"
    path.write_text("[a.b]\nC = true\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    value = tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement")
    assert value == 1.0

    resolution = tuning.validate_against_defaults()
    assert resolution.rejected["a.b.C"].reason == "wrong type"


def test_whole_rejects_a_float_override_rather_than_truncating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text("[a.b]\nD = 30.0\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    value = tuning.whole("a.b.D", 2, lo=0, hi=10, status="judgement")
    assert value == 2

    resolution = tuning.validate_against_defaults()
    assert resolution.rejected["a.b.D"].reason == "wrong type"


def test_out_of_range_is_rejected_and_default_stays_in_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text("[a.b]\nC = 99.0\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    value = tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement")
    assert value == 1.0

    resolution = tuning.validate_against_defaults()
    rejection = resolution.rejected["a.b.C"]
    assert rejection.reason == "out of range"
    assert "99.0" in rejection.detail


def test_sequence_replaces_wholesale() -> None:
    assert tuning.sequence("a.b.F", (1, 2, 3), status="judgement") == (1, 2, 3)


def test_sequence_applied_and_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text("[a.b]\nF = [9, 8, 7]\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    value = tuning.sequence("a.b.F", (1, 2, 3), status="judgement")
    assert value == (9, 8, 7)

    tuning.reset_for_testing()
    path.write_text('[a.b]\nF = "not a sequence"\n', encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))
    value2 = tuning.sequence("a.b.F", (1, 2, 3), status="judgement")
    assert value2 == (1, 2, 3)
    resolution = tuning.validate_against_defaults()
    assert resolution.rejected["a.b.F"].reason == "wrong type"


def test_table_merges_per_entry_unknown_entry_rejected_rest_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text(
        "[a.b.G]\nx = 5.0\nz = 1.0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    result = tuning.table(
        "a.b.G", {"x": 1.0, "y": 2.0}, lo=0.0, hi=10.0, status="judgement"
    )
    assert result == {"x": 5.0, "y": 2.0}  # x applied, y untouched (default)

    resolution = tuning.validate_against_defaults()
    assert resolution.applied["a.b.G.x"].value == 5.0
    assert "a.b.G.y" in resolution.defaulted
    rejection = resolution.rejected["a.b.G.z"]
    assert rejection.reason == "unrecognised table entry"
    assert "x" in rejection.detail and "y" in rejection.detail


def test_table_entry_out_of_range_and_wrong_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text('[a.b.G]\nx = 99.0\ny = "nope"\n', encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    result = tuning.table(
        "a.b.G", {"x": 1.0, "y": 2.0}, lo=0.0, hi=10.0, status="judgement"
    )
    assert result == {"x": 1.0, "y": 2.0}

    resolution = tuning.validate_against_defaults()
    assert resolution.rejected["a.b.G.x"].reason == "out of range"
    assert resolution.rejected["a.b.G.y"].reason == "wrong type"


def test_table_whole_key_wrong_type_defaults_every_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole table key is given a scalar instead of a table."""
    path = tmp_path / "tuning.toml"
    path.write_text("[a.b]\nG = 5.0\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    result = tuning.table("a.b.G", {"x": 1.0}, lo=0.0, hi=10.0, status="judgement")
    assert result == {"x": 1.0}

    resolution = tuning.validate_against_defaults()
    assert resolution.rejected["a.b.G"].reason == "wrong type"
    assert "a.b.G.x" in resolution.defaulted


def test_startup_block_and_print_tuning_agree_with_the_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text("[a.b]\nC = 5.0\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement")
    tuning.real("a.b.H", 2.0, lo=0.0, hi=10.0, status="judgement")  # left at default
    resolution = tuning.validate_against_defaults()

    startup = tuning.render_startup_block(resolution)
    full = tuning.render_print_tuning(resolution)
    assert startup in full
    assert "a.b.C" in startup
    assert "a.b.H" not in startup  # defaulted keys only show in --print-tuning
    assert "a.b.H" in full


def test_empty_rejected_section_reads_as_confirmation() -> None:
    resolution = tuning.validate_against_defaults()
    # file_status "unset": no block with a rejected section is rendered at
    # all, which is itself the plan's "no override file" case, distinct
    # from "loaded, zero rejections".
    assert resolution.file_status == "unset"


def test_empty_rejected_section_when_file_loaded_with_no_bad_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text("[a.b]\nC = 5.0\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    tuning.real("a.b.C", 1.0, lo=0.0, hi=10.0, status="judgement")
    resolution = tuning.validate_against_defaults()
    block = tuning.render_startup_block(resolution)
    assert "rejected (0)" in block


def test_cross_key_coupling_rejects_both_overrides_and_falls_back_to_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's Required Fix 1 reproduction (`plans/
    configurable-constants/review.md`), exercised directly against
    `tuning.py`'s own accessors -- FOCUS_DWELL_S at its own `hi` (5.0) and
    POSITION_HALF_LIFE_S at its own `lo` (20.0) used to raise an uncaught
    `AssertionError` at import, a disguised refusal to start on two
    individually-valid overrides. See
    `test_reviewer_repro_scan_decay_coupling_does_not_crash_the_process`
    below for the full-process pin."""
    path = tmp_path / "tuning.toml"
    path.write_text(
        "[perception.gaze]\nFOCUS_DWELL_S = 5.0\n"
        "[belief.decay]\nPOSITION_HALF_LIFE_S = 20.0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    focus = tuning.real(
        "perception.gaze.FOCUS_DWELL_S", 2.0, lo=0.5, hi=5.0, status="judgement"
    )
    half_life = tuning.real(
        "belief.decay.POSITION_HALF_LIFE_S",
        30.0,
        lo=20.0,
        hi=120.0,
        status="judgement",
    )
    assert focus == 2.0
    assert half_life == 30.0

    resolution = tuning.validate_against_defaults()
    focus_rej = resolution.rejected["perception.gaze.FOCUS_DWELL_S"]
    half_life_rej = resolution.rejected["belief.decay.POSITION_HALF_LIFE_S"]
    assert focus_rej.reason == "invariant violation"
    assert half_life_rej.reason == "invariant violation"
    assert "POSITION_HALF_LIFE_S" in focus_rej.detail
    assert "FOCUS_DWELL_S" in half_life_rej.detail
    block = tuning.render_startup_block(resolution)
    assert "perception.gaze.FOCUS_DWELL_S" in block
    assert "belief.decay.POSITION_HALF_LIFE_S" in block


def test_cross_key_coupling_trips_from_a_single_overridden_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`FOCUS_DWELL_S` alone, against the code default `POSITION_HALF_LIFE_S`
    (30.0) and the code default `SCAN_PLAN` (8 legs), already violates the
    invariant (8 * 5.0 = 40.0 >= 30.0) -- only the one key actually in the
    file is rejected; `POSITION_HALF_LIFE_S`, never overridden, was never
    going to be anything but its own default anyway."""
    path = tmp_path / "tuning.toml"
    path.write_text("[perception.gaze]\nFOCUS_DWELL_S = 5.0\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    focus = tuning.real(
        "perception.gaze.FOCUS_DWELL_S", 2.0, lo=0.5, hi=5.0, status="judgement"
    )
    assert focus == 2.0

    resolution = tuning.validate_against_defaults()
    assert (
        resolution.rejected["perception.gaze.FOCUS_DWELL_S"].reason
        == "invariant violation"
    )
    assert "belief.decay.POSITION_HALF_LIFE_S" not in resolution.rejected


def test_cross_key_coupling_does_not_fire_for_a_safe_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tuning.toml"
    path.write_text("[belief.decay]\nPOSITION_HALF_LIFE_S = 100.0\n", encoding="utf-8")
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    half_life = tuning.real(
        "belief.decay.POSITION_HALF_LIFE_S",
        30.0,
        lo=20.0,
        hi=120.0,
        status="judgement",
    )
    assert half_life == 100.0

    resolution = tuning.validate_against_defaults()
    assert resolution.applied["belief.decay.POSITION_HALF_LIFE_S"].value == 100.0
    assert "belief.decay.POSITION_HALF_LIFE_S" not in resolution.rejected


def test_cross_key_coupling_does_not_override_a_more_specific_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key that is independently wrong-typed keeps that more specific
    classification -- the coupling check only has an opinion about a value
    that would otherwise have been accepted."""
    path = tmp_path / "tuning.toml"
    path.write_text(
        '[perception.gaze]\nFOCUS_DWELL_S = "nope"\n'
        "[belief.decay]\nPOSITION_HALF_LIFE_S = 20.0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PETROBRAIN_TUNING", str(path))

    focus = tuning.real(
        "perception.gaze.FOCUS_DWELL_S", 2.0, lo=0.5, hi=5.0, status="judgement"
    )
    assert focus == 2.0

    resolution = tuning.validate_against_defaults()
    assert resolution.rejected["perception.gaze.FOCUS_DWELL_S"].reason == "wrong type"


def test_reviewer_repro_scan_decay_coupling_does_not_crash_the_process(
    tmp_path: Path,
) -> None:
    """Pins the reviewer's exact reproduction end to end, in a fresh
    process, importing the real production modules
    (`perception.gaze`/`belief.decay`) rather than synthetic keys: must
    start, leave both constants at their code defaults, and surface the
    rejection in the startup output."""
    tuning_file = tmp_path / "tuning.toml"
    tuning_file.write_text(
        "[perception.gaze]\nFOCUS_DWELL_S = 5.0\n"
        "[belief.decay]\nPOSITION_HALF_LIFE_S = 20.0\n",
        encoding="utf-8",
    )

    body_layer_src = Path(__file__).resolve().parent.parent / "src"
    world_model_src = (
        Path(__file__).resolve().parent.parent.parent / "world-model" / "src"
    )
    env = {
        "PETROBRAIN_TUNING": str(tuning_file),
        "PYTHONPATH": f"{body_layer_src}:{world_model_src}",
        "PATH": "/usr/bin:/bin",
    }
    script = (
        "import tuning\n"
        "from perception.gaze import FOCUS_DWELL_S\n"
        "from belief.decay import OBSERVED_WINDOW_S, POSITION_HALF_LIFE_S\n"
        "assert FOCUS_DWELL_S == 2.0, FOCUS_DWELL_S\n"
        "assert POSITION_HALF_LIFE_S == 30.0, POSITION_HALF_LIFE_S\n"
        "assert OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S\n"
        "resolution = tuning.validate_against_defaults()\n"
        "print(tuning.render_startup_block(resolution))\n"
    )
    # `check=True` is the point: this call must not raise -- a regression
    # of the bug being fixed here is an uncaught AssertionError at import,
    # which `subprocess.run` surfaces as a non-zero exit and this would
    # turn into a CalledProcessError.
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "invariant" in result.stdout
    assert "perception.gaze.FOCUS_DWELL_S" in result.stdout
    assert "belief.decay.POSITION_HALF_LIFE_S" in result.stdout


def test_a_real_constant_resolves_an_override_in_a_fresh_process(
    tmp_path: Path,
) -> None:
    """Subprocess, not an in-process reimport: `BEARING_SIGMA_DEG` has
    already been bound at module import by the time this test file's own
    `import tuning` ran (transitively, via other tests in this suite), so
    only a fresh interpreter actually exercises 'resolves at import, from
    the environment' end to end -- plans/configurable-constants/plan.md,
    'Verifying a changed value took effect'."""
    tuning_file = tmp_path / "tuning.toml"
    tuning_file.write_text(
        "[perception.estimation]\nBEARING_SIGMA_DEG = 5.0\n", encoding="utf-8"
    )

    body_layer_src = Path(__file__).resolve().parent.parent / "src"
    world_model_src = (
        Path(__file__).resolve().parent.parent.parent / "world-model" / "src"
    )
    env = {
        "PETROBRAIN_TUNING": str(tuning_file),
        "PYTHONPATH": f"{body_layer_src}:{world_model_src}",
        "PATH": "/usr/bin:/bin",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from perception.estimation import BEARING_SIGMA_DEG; print(BEARING_SIGMA_DEG)",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "5.0"


def test_a_rejected_value_in_a_fresh_process_leaves_the_code_default_in_force(
    tmp_path: Path,
) -> None:
    tuning_file = tmp_path / "tuning.toml"
    tuning_file.write_text(
        "[perception.estimation]\nBEARING_SIGMA_DEG = 999.0\n", encoding="utf-8"
    )

    body_layer_src = Path(__file__).resolve().parent.parent / "src"
    world_model_src = (
        Path(__file__).resolve().parent.parent.parent / "world-model" / "src"
    )
    env = {
        "PETROBRAIN_TUNING": str(tuning_file),
        "PYTHONPATH": f"{body_layer_src}:{world_model_src}",
        "PATH": "/usr/bin:/bin",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from perception.estimation import BEARING_SIGMA_DEG; print(BEARING_SIGMA_DEG)",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "3.0"
