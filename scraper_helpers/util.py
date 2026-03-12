# helpers/util.py
import os
import re

def filename_tokens_lower(path: str):
    base = os.path.basename(path or "").lower()
    return [t for t in re.split(r"[^a-z0-9]+", base) if t]