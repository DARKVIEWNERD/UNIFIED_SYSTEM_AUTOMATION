# config.py - Configuration settings

# Define multiple countries for testing with numbers
import json
from pathlib import Path

COUNTRIES = [
   
    {"name": "United States", "code": "US", "slug_name": "United States", "number": "01"},
    {"name": "Canada", "code": "CA", "slug_name": "Canada", "number": "02"},
    {"name": "Australia", "code": "AU", "slug_name": "Australia", "number": "03"},

    {"name": "South Africa", "code": "ZA", "slug_name": "South Africa", "number": "04"},
    {"name": "Egypt", "code": "EG", "slug_name": "Egypt", "number": "05"},
    {"name": "United Arab Emirate", "code": "AE", "slug_name": "United Arab Emirates", "number": "06"},

    {"name": "Saudi Arabia", "code": "SA", "slug_name": "Saudi Arabia", "number": "07"},
    {"name": "Brazil", "code": "BR", "slug_name": "Brazil", "number": "08"},
    {"name": "Mexico", "code": "MX", "slug_name": "Mexico", "number": "09"},

    {"name": "Thailand", "code": "TH", "slug_name": "Thailand", "number": "10"},
    {"name": "India", "code": "IN", "slug_name": "India", "number": "11"},
    {"name": "China", "code": "CN", "slug_name": "China", "number": "12"},
    
    {"name": "Hong Kong", "code": "HK", "slug_name": "Hong Kong", "number": "13"},
    {"name": "Taiwan", "code": "TW", "slug_name": "Taiwan", "number": "14"},
    {"name": "South Korea", "code": "KR", "slug_name": "Korea, Republic Of", "number": "15"},

    {"name": "Japan", "code": "JP", "slug_name": "Japan", "number": "16"},
    {"name": "France", "code": "FR", "slug_name": "France", "number": "17"},
    {"name": "Italy", "code": "IT", "slug_name": "Italy", "number": "18"},

    {"name": "Belgium", "code": "BE", "slug_name": "Belgium", "number": "19"},
    {"name": "United Kingdom", "code": "GB", "slug_name": "United Kingdom", "number": "20"},
    {"name": "Germany", "code": "DE", "slug_name": "Germany", "number": "21"},

    {"name": "Spain", "code": "ES", "slug_name": "Spain", "number": "22"}
   
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
    ]
}


# App platforms to test
APP_PLATFORMS = ["android", "apple"]


WEB_PLATFORMS = [

]

try:
    with open(Path(__file__).parent / 'custom_patterns.json', 'r') as file:
        patterns = json.load(file)

    for site in patterns:
        if not site.get("active", True):
            continue
        if site["name"].lower() in ['appfollow', 'similarweb', 'apptweak']:
            site["type"]=site['name'].lower()
        else:
            site["type"] = "universal"
        WEB_PLATFORMS.append(site)

except FileNotFoundError as e:
    print(f"Error found: {e}")


# Target directory for saving files
import os


TARGET_DIR = Path(__file__).parent / "AUTOMATION FILE"


# Delays and timing configuration
DELAYS = {
    "page_load": (4, 6),           # Random range for page loading
    "between_tests": (5, 8),       # Between URL tests
    "between_countries": (10, 15), # Between countries
    "retry": (5, 10),             # Retry delays
    "verification_check": 3,       # Seconds between verification checks
    
    # AppTweak specific delays
    "apptweak_category_delay": 3,  # Delay between AppTweak categories
    "apptweak_platform_delay": 3,  # Delay between AppTweak platforms
    "apptweak_country_delay": 5,   # Delay between AppTweak countries
    
    # General delays
    "modal_wait": 2,              # Wait for modal to open
    "dropdown_wait": 0.5,         # Wait after dropdown selection
    "save_wait": 2,               # Wait after save button click
    "snapshot_wait": 1,           # Wait after taking snapshot
}
# Selenium options
CHROME_OPTIONS = [
    "--disable-blink-features=AutomationControlled",
    "--start-maximized",
    "--no-sandbox",
    "--disable-dev-shm-usage"
]

# Validation settings
MAX_RETRIES = 2
VERIFICATION_TIMEOUT = 300  # 5 minutes
WEBDRIVER_WAIT = 20

# AppTweak specific settings
APPTWEAK = {
    "modal_selectors": {
        "store_dropdown": ".stores",
        "country_dropdown": ".countries",
        "category_dropdown": ".categories",
        "save_button": ".js-top-charts-change-column-btn.btn",
        "edit_link": "a.js-change-column[data-column-position='0']"
    },
    "wait_times": {
        "page_load": 3,
        "modal_open": 2,
        "after_save": 2,
        "between_categories": 3
    }
}