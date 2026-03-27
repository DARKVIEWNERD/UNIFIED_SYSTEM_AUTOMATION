# helpers/io.py
import os
import sys
import json
import email
import re
from pathlib import Path  # ← FIXED: from pathlib import Path

def load_config():
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent.parent
    cfg_path = base_path / "config.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def html_from_mhtml_bytes(mhtml_bytes):
    try:
        msg = email.message_from_bytes(mhtml_bytes)
    except Exception as e:
        return None, f"Failed to parse MHTML bytes: {e}"
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            charset = part.get_content_charset() or "utf-8"
            try:
                return part.get_payload(decode=True).decode(charset, errors="replace"), None
            except Exception as e:
                return None, f"Failed to decode HTML part: {e}"
    return None, "No HTML part found in MHTML."

def bs_kwargs(sel_type, value):
    if sel_type == "class":
        classes = (value or "").split()
        return {"class_": classes if len(classes) > 1 else value}
    elif sel_type == "id":
        return {"id": value}
    else:
        return {sel_type: value}

def safe_filename(name, default="output", ext=".xlsx"):
    if not isinstance(name, str) or not name.strip():
        base = default
    else:
        base = name.strip().lower()
    base = base.replace(" ", "_")
    base = re.sub(r"[^a-z0-9._-]+", "", base).strip("._-")
    if not base:
        base = default
    if not re.search(r"\.(xlsx|xlsm|xltx|xltm)$", base):
        base = f"{base}{ext}"
    return base