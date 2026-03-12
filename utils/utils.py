# utils.py - Utility functions
import re
import time
import random
from winotify import Notification,audio


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

def get_next_sequence_number(country_data, sequence_counters):
    """Get and increment sequence number for a country - SYNCHRONIZED ACROSS ALL PLATFORMS"""
    country_number = country_data.get("number", "00")
    
    # Get current sequence for this country
    if country_number in sequence_counters:
        sequence_number = sequence_counters[country_number]+1
    else:
        # Initialize if not exists
        sequence_number = 1

    # Update the counter
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



# ============================================================================
# CUSTOM URL PATTERN SYSTEM - USER FRIENDLY
# ============================================================================

import json
from pathlib import Path
from logging_config import logger

# File to store custom patterns
CUSTOM_PATTERNS_FILE = Path("custom_patterns.json")

def setup_custom_pattern():
    """Interactive setup for custom URL patterns"""
    print("\n" + "="*60)
    print("🎯 CUSTOM URL PATTERN SETUP")
    print("="*60)
    
    # Get platform name
    print("\n1️⃣  What should we call this custom platform?")
    print("   (This name will appear in your results)")
    platform_name = input("   Platform name: ").strip()
    
    # Explain placeholders
    print("\n" + "="*60)
    print("2️⃣  UNDERSTAND PLACEHOLDERS")
    print("="*60)
    print("   Use these in your URL:")
    print("   • {country}      → 'united-states' (auto-converted)")
    print("   • {category}     → 'music-audio' (auto-converted)")
    print("   • {platform}     → 'android' or 'apple'")
    print("   • {platform_short} → 'android' or 'ios'")
    print("   • {country_code} → 'US' (auto-uppercased)")
    print("\n   Examples:")
    print("   • https://example.com/{platform_short}/{country}/{category}")
    print("   • https://sensortower.com/{platform_short}/top-charts/{country}/{category}")
    print("   • https://api.example.com/v1/{country_code}/{platform}/{category}")
    
    # Get URL pattern
    print("\n" + "="*60)
    print("3️⃣  ENTER YOUR URL PATTERN")
    print("="*60)
    url_template = input("   URL pattern: ").strip()
    
    # Show examples
    print("\n" + "="*60)
    print("4️⃣  EXAMPLE URLs")
    print("="*60)
    
    example_country = "united-states"
    example_category = "music"
    
    for platform in ["android", "apple"]:
        platform_short = "android" if platform == "android" else "ios"
        url = url_template
        url = url.replace("{country}", example_country)
        url = url.replace("{category}", example_category)
        url = url.replace("{platform}", platform)
        url = url.replace("{platform_short}", platform_short)
        url = url.replace("{country_code}", "US")
        print(f"   📱 {platform.upper()}: {url}")
    
    # Confirm
    print("\n" + "="*60)
    print("5️⃣  CONFIRM AND SAVE")
    print("="*60)
    
    confirm = input(f"\n✅ Save '{platform_name}' with this URL pattern? (y/n): ").lower().strip()
    
    if confirm != 'y':
        print("❌ Setup cancelled.")
        return False
    
    # Load existing patterns
    try:
        if CUSTOM_PATTERNS_FILE.exists():
            with open(CUSTOM_PATTERNS_FILE, 'r') as f:
                patterns = json.load(f)
        else:
            patterns = []
    except:
        patterns = []
    
    # Check if exists
    for i, pattern in enumerate(patterns):
        if pattern.get("name") == platform_name:
            overwrite = input(f"⚠  '{platform_name}' already exists. Overwrite? (y/n): ").lower().strip()
            if overwrite != 'y':
                print("❌ Cancelled.")
                return False
            patterns[i] = {"name": platform_name, "url": url_template, "active": True}
            break
    else:
        patterns.append({"name": platform_name, "url": url_template, "active": True})
    
    # Save
    with open(CUSTOM_PATTERNS_FILE, 'w') as f:
        json.dump(patterns, f, indent=2)
    
    print(f"\n✅ Pattern '{platform_name}' saved to {CUSTOM_PATTERNS_FILE}")
    
    # Ask to add to config.py
    print("\n" + "="*60)
    print("6️⃣  UPDATE CONFIG.PY")
    print("="*60)
    
    add_to_config = input("\nAdd this platform to config.py for automation? (y/n): ").lower().strip()
    
    if add_to_config == 'y':
        try:
            # Read config.py
            with open("config.py", 'r') as f:
                lines = f.readlines()
            
            # Find WEB_PLATFORMS line
            for i, line in enumerate(lines):
                if line.strip().startswith("WEB_PLATFORMS = ["):
                    # Insert after this line
                    new_line = f'    {{"name": "{platform_name}", "base_url": "", "type": "custom"}},\n'
                    lines.insert(i + 1, new_line)
                    
                    # Write back
                    with open("config.py", 'w') as f:
                        f.writelines(lines)
                    
                    print(f"✅ Added '{platform_name}' to config.py")
                    break
            else:
                print("⚠  Could not find WEB_PLATFORMS in config.py")
                print(f"   Manually add: {{\"name\": \"{platform_name}\", \"base_url\": \"\", \"type\": \"custom\"}}")
                
        except Exception as e:
            print(f"⚠  Error updating config.py: {e}")
    
    print("\n" + "="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print(f"\nPlatform '{platform_name}' is ready to use.")
    print("Run your automation as usual.")
    
    return True

def focus_browser(driver):
    try:
        driver.switch_to.window(driver.current_window_handle)
        driver.execute_script("window.focus();")
        logger.info("🔎 Browser brought to front.")
    except Exception as e:
        logger.warning(f"Could not focus browser: {e}")
