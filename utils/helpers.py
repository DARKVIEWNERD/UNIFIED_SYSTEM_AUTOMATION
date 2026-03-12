"""Helper utility functions"""
import hashlib
from pathlib import Path
from typing import Optional, Union


def file_md5(path: Path) -> str:
    """Return MD5 hex-digest of a file, or '' if it doesn't exist."""
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def parse_int_index(value_str: str) -> Optional[int]:
    """
    Parse string into single integer index.
    Returns None if empty or invalid.
    """
    if not value_str or not value_str.strip():
        return None
        
    try:
        return int(value_str.strip())
    except ValueError:
        return None