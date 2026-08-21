"""
Safe JSON loading, validation, and serialization utilities.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def safe_load_json(filepath: Path) -> tuple[bool, Any, str | None]:
    """
    Safely load and parse a JSON file.
    Returns (success, parsed_data, error_message).
    """
    if not filepath.exists():
        return False, None, f"File does not exist: {filepath}"
    
    try:
        content = filepath.read_text(encoding="utf-8")
        if not content.strip():
            return True, {}, None
        data = json.loads(content)
        return True, data, None
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON syntax in {filepath}: line {e.lineno}, col {e.colno} ({e.msg})"
    except Exception as e:
        return False, None, f"Error reading {filepath}: {e}"


def safe_validate_json_string(content: str) -> tuple[bool, Any, str | None]:
    """
    Safely validate and parse a JSON string.
    Returns (success, parsed_data, error_message).
    """
    try:
        if not content.strip():
            return True, {}, None
        data = json.loads(content)
        return True, data, None
    except json.JSONDecodeError as e:
        return False, None, f"JSON syntax error: line {e.lineno}, col {e.colno} ({e.msg})"
    except Exception as e:
        return False, None, f"JSON error: {e}"


def format_json(data: Any, indent: int = 2) -> str:
    """Format data as indented JSON string with trailing newline."""
    return json.dumps(data, indent=indent, ensure_ascii=False) + "\n"
