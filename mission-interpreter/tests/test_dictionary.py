from __future__ import annotations

import logging

import pytest

from miz.dictionary import resolve_dict_keys


def test_resolves_dict_key_strings() -> None:
    dictionary = {"DictKey_foo_1": "Foo text"}
    result = resolve_dict_keys("DictKey_foo_1", dictionary)
    assert result == "Foo text"


def test_walks_nested_dicts_and_lists() -> None:
    dictionary = {"DictKey_a_1": "Alpha", "DictKey_b_2": "Beta"}
    tree = {
        "top": "DictKey_a_1",
        "nested": {"inner": "DictKey_b_2", "untouched": "plain string"},
        "list": ["DictKey_a_1", "DictKey_b_2", 42],
    }
    result = resolve_dict_keys(tree, dictionary)
    assert result == {
        "top": "Alpha",
        "nested": {"inner": "Beta", "untouched": "plain string"},
        "list": ["Alpha", "Beta", 42],
    }


def test_non_string_and_plain_string_values_pass_through_unchanged() -> None:
    dictionary: dict[str, str] = {}
    tree = {"n": 1, "b": True, "s": "not a dict key"}
    assert resolve_dict_keys(tree, dictionary) == tree


def test_missing_dict_key_is_left_unchanged_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dictionary: dict[str, str] = {}
    with caplog.at_level(logging.WARNING):
        result = resolve_dict_keys("DictKey_missing_9", dictionary)
    assert result == "DictKey_missing_9"
    assert "DictKey_missing_9" in caplog.text
