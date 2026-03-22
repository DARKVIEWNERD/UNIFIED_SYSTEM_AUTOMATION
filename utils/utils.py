# utils.py - Utility functions
import re
import time
import random
from winotify import Notification,audio

from logging_config import logger


from config import COUNTRIES, WEB_PLATFORMS, APP_PLATFORMS, PLATFORM_CATEGORIES



def slugify(text: str, platform: str) -> str:
    """Convert text to URL-friendly slug"""
    if not text:
        return ""
    
    text = text.lower().strip()

    if platform == "similarweb":
        text = text.replace("&", "-")  # & becomes - for SimilarWeb
    elif platform == "appfollow":
        pass  # & stays as & for AppFollow
    else:
        text = text.replace("&", "-")

    text = re.sub(r"\s+", "-", text)  # spaces become -

    if platform == "appfollow":
        text = re.sub(r"[^a-z0-9&-]", "", text)  # Allows & for AppFollow
    else:
        text = re.sub(r"[^a-z0-9-]", "", text)  # Does NOT allow & for SimilarWeb

    text = re.sub(r"-+", "-", text)
    return text.strip("-")

def get_country_slug(country_dict: dict, web_platform_type: str) -> str:
    """Get country slug based on platform type - FIXED"""
    if web_platform_type == "appfollow":
        return country_dict["code"].lower()  # "us", "kr", "gb"
    
    elif web_platform_type == "similarweb":
        # Get slug_name or fall back to name
        slug_name = country_dict.get("slug_name", country_dict["name"])
        
        # Convert to lowercase
        slug = slug_name.lower()
        
        # Replace spaces and special chars with hyphens
        slug = re.sub(r'[,\s()]+', '-', slug)
        
        # Remove any remaining special characters
        slug = re.sub(r'[^a-z0-9-]', '', slug)
        
        # Clean up multiple hyphens
        slug = re.sub(r'-+', '-', slug)
        
        return slug.strip("-")
    
    else:
        # For other platforms, use a safe default
        name = country_dict.get("slug_name", country_dict["name"])
        return name.lower().replace(" ", "-")
    
    
def get_url_for_platform(base_url: str, web_platform_type: str, app_platform: str, 
                         country_slug: str, category_slug: str, platform_name=None) -> str:
    """
    Generate the correct URL based on web platform and app platform
    """
    # First handle known platforms
    if web_platform_type == "similarweb":
        if app_platform == "android":
            return f"{base_url}/top-apps/google/{country_slug}/{category_slug}/"
        else:  # apple
            return f"{base_url}/top-apps/apple/{country_slug}/{category_slug}/"

    elif web_platform_type == "appfollow":
        if app_platform == "android":
            return f"{base_url}/rankings/android/{country_slug}/{category_slug}/"
        else:  # apple
            return f"{base_url}/rankings/iphone/{country_slug}/{category_slug}/"
    
    elif web_platform_type == "apptweak":
        return f"{base_url}"
    
    # Generic fallback
    return f"{base_url}"


def clean_category_name(category: str) -> str:
    """Clean category name for use in filenames"""
    # Replace problematic characters
    replacements = {
        '&': 'and',
        '/': '_',
        '\\': '_',
        ':': '_',
        '*': '_',
        '?': '_',
        '"': '_',
        '<': '_',
        '>': '_',
        '|': '_'
    }
        
    
    for old, new in replacements.items():
        category = category.replace(old, new)

    # Replace multiple spaces with single underscore
    category = re.sub(r'\s+', '_', category.strip())

    # Remove any remaining non-ASCII characters
    category = re.sub(r'[^\x00-\x7F]+', '', category)

    return category

def get_next_sequence_number(country_data, sequence_counters, used_slots=None):
    """
    Get next sequence number for a country.
    If used_slots is provided, fills gaps first before appending new ones.
    This ensures deleted files get their slot back, no gaps left behind.
    """
    country_number = country_data.get("number", "00")
 
    if used_slots is not None:
        taken = used_slots.get(country_number, set())
        # Find the lowest available gap starting from 1
        seq = 1
        while seq in taken:
            seq += 1
        # Mark this slot as taken
        taken.add(seq)
        used_slots[country_number] = taken
        # Keep counter in sync
        sequence_counters[country_number] = max(
            sequence_counters.get(country_number, 0), seq
        )
        return seq
 
    # Fallback — original behavior (no used_slots passed)
    sequence_number = sequence_counters.get(country_number, 0) + 1
    sequence_counters[country_number] = sequence_number
    return sequence_number
 

def print_progress(current: int, total: int, prefix: str = "", bar_length: int = 50):
    """Print a progress bar"""
    percent = float(current) / total
    arrow = '█' * int(round(percent * bar_length))
    spaces = '░' * (bar_length - len(arrow))
    
    if prefix:
        print(f'\r{prefix}: [{arrow}{spaces}] {current}/{total} ({percent:.1%})', end='')
    else:
        print(f'\rProgress: [{arrow}{spaces}] {current}/{total} ({percent:.1%})', end='')
    
    if current == total:
        print()
        
def calculate_totals():
    """Calculate total URLs to test based on active platforms"""
    total_countries = len(COUNTRIES)
    urls_per_country = 0
    
    # Count URLs for all active web platforms
    for web_platform in WEB_PLATFORMS:
        # Only count if the platform is active
        if not web_platform.get("active", True):  # Default to True if "active" key doesn't exist
            continue
            
        if web_platform["type"] == "apptweak":
            # AppTweak processes both platforms' categories
            # Count Android categories
            urls_per_country += len(PLATFORM_CATEGORIES.get("android", []))
            # Count Apple categories
            urls_per_country += len(PLATFORM_CATEGORIES.get("apple", []))
        else:
            # Other platforms process each platform separately
            for app_platform in APP_PLATFORMS:
                urls_per_country += len(PLATFORM_CATEGORIES.get(app_platform, []))
    
    total_tests = urls_per_country * total_countries
    
    return total_countries, urls_per_country, total_tests, 


def random_sleep(min_seconds: float, max_seconds: float):
    """Sleep for a random duration"""
    time.sleep(random.uniform(min_seconds, max_seconds))
    

def ToastMSG(app_id, title, msg, duration):
   
    toast = Notification(
        app_id=app_id,
        title=title,
        msg=msg,
        duration=duration,
    )
    toast.set_audio(audio.Mail, loop=False)
    toast.show()



def focus_browser(driver):
    try:
        driver.switch_to.window(driver.current_window_handle)
        driver.execute_script("window.focus();")
        logger.info("🔎 Browser brought to front.")
    except Exception as e:
        logger.warning(f"Could not focus browser: {e}")
