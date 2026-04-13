# config.py - Configuration settings

import json
import os
from pathlib import Path
import sys

# ─────────────────────────────────────────────────────────────────────────────
# BASE DIR 
# ─────────────────────────────────────────────────────────────────────────────

def get_base_dir() -> Path:
    """Works both in development and when frozen as .exe"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

BASE_DIR = get_base_dir()

# ─────────────────────────────────────────────────────────────────────────────
# STATIC CONFIG 
# ─────────────────────────────────────────────────────────────────────────────

COUNTRIES = [
    {"name": "United Arab Emirates", "code": "AE", "slug_name": "United Arab Emirates",    "number": "06"},

    {"name": "Saudi Arabia",        "code": "SA", "slug_name": "Saudi Arabia",            "number": "07"},
    {"name": "Brazil",              "code": "BR", "slug_name": "Brazil",                  "number": "08"},
    {"name": "Mexico",              "code": "MX", "slug_name": "Mexico",                  "number": "09"},

    {"name": "Thailand",            "code": "TH", "slug_name": "Thailand",                "number": "10"},
    {"name": "India",               "code": "IN", "slug_name": "India",                   "number": "11"},
    {"name": "China",               "code": "CN", "slug_name": "China",                   "number": "12"},

    {"name": "Hong Kong",           "code": "HK", "slug_name": "Hong Kong",               "number": "13"},
    {"name": "Taiwan",              "code": "TW", "slug_name": "Taiwan",                  "number": "14"},
    {"name": "South Korea",         "code": "KR", "slug_name": "Korea, Republic Of",      "number": "15"},

    {"name": "Japan",               "code": "JP", "slug_name": "Japan",                   "number": "16"},
    {"name": "France",              "code": "FR", "slug_name": "France",                  "number": "17"},
    {"name": "Italy",               "code": "IT", "slug_name": "Italy",                   "number": "18"},

    {"name": "Belgium",             "code": "BE", "slug_name": "Belgium",                 "number": "19"},
    {"name": "United Kingdom",      "code": "GB", "slug_name": "United Kingdom",          "number": "20"},
    {"name": "Germany",             "code": "DE", "slug_name": "Germany",                 "number": "21"},

    {"name": "Spain",               "code": "ES", "slug_name": "Spain",                   "number": "22"},
]

# Platform-specific categories
PLATFORM_CATEGORIES = {
    "android": [
        "Music & Audio",
        "Maps & Navigation",
        "Social",
        "Communication",
    ],
    "apple": [
        "Music",
        "Navigation",
        "Social Networking",
    ],
}

# App platforms to test
APP_PLATFORMS = ["android", "apple"]


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC CONFIG  — loaded from custom_patterns.json
# ─────────────────────────────────────────────────────────────────────────────

_JSON_PATH = BASE_DIR / "custom_patterns.json"  


_NAMED_TYPES = {"appfollow", "similarweb", "apptweak"}


def reload_web_platforms() -> list:
    """
    Read custom_patterns.json from disk RIGHT NOW and return the active
    platform list.
      made to the JSON between runs — or while the GUI is open — are picked up
      immediately without restarting the application.

    Returns a fresh list; also mutates the module-level WEB_PLATFORMS in-place
    so all existing `from config import WEB_PLATFORMS` references stay valid.
    """
    global WEB_PLATFORMS

    fresh: list = []

    try:
        with open(_JSON_PATH, "r", encoding="utf-8") as fh:
            patterns = json.load(fh)

        for site in patterns:
            # Skip inactive entries
            if not site.get("active", True):
                continue

            # Stamp the type field
            name_lower = site["name"].lower()
            site["type"] = name_lower if name_lower in _NAMED_TYPES else "universal"

            fresh.append(site)

    except FileNotFoundError:
        print(f"[config] WARNING: {_JSON_PATH} not found — WEB_PLATFORMS will be empty.")
    except json.JSONDecodeError as exc:
        print(f"[config] ERROR: Could not parse {_JSON_PATH}: {exc} — keeping previous platforms.")
        return WEB_PLATFORMS   # keep whatever was loaded before; don't wipe it

    # Mutate in-place so every module that did `from config import WEB_PLATFORMS`
    # sees the updated contents through the same list object.
    WEB_PLATFORMS.clear()
    WEB_PLATFORMS.extend(fresh)

    return WEB_PLATFORMS


# ── Initial load at import time (keeps backward-compat with existing code) ──
WEB_PLATFORMS: list = []
reload_web_platforms()


# ─────────────────────────────────────────────────────────────────────────────
# OTHER SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

TARGET_DIR = BASE_DIR / "AUTOMATION FILE"

DELAYS = {
    "page_load":             (4, 6),
    "between_tests":         (5, 8),
    "between_countries":     (10, 15),
    "retry":                 (5, 10),
    "verification_check":    3,

    # AppTweak specific
    "apptweak_category_delay": 3,
    "apptweak_platform_delay": 3,
    "apptweak_country_delay":  5,
}

CHROME_OPTIONS = [
    "--disable-blink-features=AutomationControlled",
    "--start-maximized",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

MAX_RETRIES          = 2
VERIFICATION_TIMEOUT = 300   # 5 minutes
WEBDRIVER_WAIT       = 20

APPTWEAK = {
    "modal_selectors": {
        "store_dropdown":    ".stores",
        "country_dropdown":  ".countries",
        "category_dropdown": ".categories",
        "save_button":       ".js-top-charts-change-column-btn.btn",
        "edit_link":         "a.js-change-column[data-column-position='0']",
    },
}