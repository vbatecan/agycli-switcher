"""
Tests for diff generation utilities.
"""

from agy_multiprofile.utils.diff_utils import generate_dict_diff, generate_unified_diff


def test_dict_diff_added_and_removed():
    old = {"a": 1, "b": 2}
    new = {"b": 2, "c": 3}
    diff = generate_dict_diff(old, new)
    assert "- a: 1" in diff
    assert "+ c: 3" in diff


def test_dict_diff_modified_nested():
    old = {"mcp": {"tool_a": {"cmd": "run"}}}
    new = {"mcp": {"tool_a": {"cmd": "execute"}}}
    diff = generate_dict_diff(old, new)
    assert any("tool_a.cmd: run -> execute" in d for d in diff)


def test_unified_diff():
    text1 = "line1\nline2\n"
    text2 = "line1\nline_modified\n"
    udiff = generate_unified_diff(text1, text2)
    assert any("-line2" in line for line in udiff)
    assert any("+line_modified" in line for line in udiff)
