import os
import sys
import json


def get_resource_path(filename: str) -> str:
    """Returns the correct absolute path whether running from source or .exe"""
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS                                # inside the .exe
    else:
        base = os.path.dirname(os.path.abspath(__file__)) # in VS Code
    return os.path.join(base, filename)


def load_config() -> dict:
    """Load config.json — works in both VS Code and .exe"""
    path = get_resource_path('config.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_custom_patterns() -> list:
    """Load custom_patterns.json — works in both VS Code and .exe"""
    path = get_resource_path('custom_patterns.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)