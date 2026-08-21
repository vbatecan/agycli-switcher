"""
Diff generator for profile configuration comparison.
"""

from __future__ import annotations

import difflib
import json
from typing import Any


def format_value_brief(val: Any) -> str:
    """Format a value briefly for diff display."""
    if isinstance(val, (dict, list)):
        dumped = json.dumps(val, ensure_ascii=False)
        if len(dumped) > 60:
            return dumped[:57] + "..."
        return dumped
    return str(val)


def generate_dict_diff(old_dict: dict[str, Any], new_dict: dict[str, Any], prefix: str = "") -> list[str]:
    """
    Generate readable diff lines between two dictionaries.
    """
    diff_lines: list[str] = []
    all_keys = sorted(set(old_dict.keys()) | set(new_dict.keys()))

    for key in all_keys:
        full_key = f"{prefix}.{key}" if prefix else key
        
        if key not in old_dict:
            diff_lines.append(f"+ {full_key}: {format_value_brief(new_dict[key])}")
        elif key not in new_dict:
            diff_lines.append(f"- {full_key}: {format_value_brief(old_dict[key])}")
        else:
            old_val = old_dict[key]
            new_val = new_dict[key]
            
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                nested_diff = generate_dict_diff(old_val, new_val, prefix=full_key)
                diff_lines.extend(nested_diff)
            elif old_val != new_val:
                diff_lines.append(
                    f"~ {full_key}: {format_value_brief(old_val)} -> {format_value_brief(new_val)}"
                )

    return diff_lines


def generate_unified_diff(
    old_content: str, new_content: str, from_label: str = "current", to_label: str = "target"
) -> list[str]:
    """Generate standard unified diff lines."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    diff = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
        )
    )
    return diff
