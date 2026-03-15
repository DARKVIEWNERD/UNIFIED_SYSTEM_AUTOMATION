# main.py - Main execution file with synchronized naming across all platforms
import os
import time
import random
from datetime import datetime
from pathlib import Path
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import from our modules
from config import (
    COUNTRIES, PLATFORM_CATEGORIES, WEB_PLATFORMS, APP_PLATFORMS,
    TARGET_DIR, DELAYS, CHROME_OPTIONS, MAX_RETRIES, WEBDRIVER_WAIT, reload_web_platforms
)
from utils.utils import (
    slugify, get_country_slug, get_url_for_platform,
    print_progress, random_sleep, clean_category_name, get_next_sequence_number, calculate_totals
)
from Web_validators import (
    is_human_verification, is_page_unusable, wait_for_manual_verification, test_url_with_retry
)
from file_handlers import (
    ensure_directory_exists, save_mhtml_snapshot, create_base_filename, load_existing_snapshots, initialize_counters_from_files
)
from logging_config import logger

# ✅ AppTweak integration
try:
    from apptweak_integration import AppTweakIntegration
    APPTWEAK_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AppTweakIntegration not available: {e}")
    APPTWEAK_AVAILABLE = False
    # Create a dummy class to avoid errors
    class AppTweakIntegration:
        def __init__(self, *args, **kwargs):
            pass
        def execute_apptweak_flow(self, country_data):
            return 0, 0
try:
    from automation_engine_initial import execute_universal_flow
    UNIVERSAL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Universal engine not available: {e}")
    UNIVERSAL_AVAILABLE = False


# ✅ ADD THIS HELPER FUNCTION
def load_custom_configs():
    """Load custom configurations from custom_patterns.json"""
    config_file = Path(__file__).parent / "custom_patterns.json"
    custom_configs = []
    
    try:
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
                    # Filter only active configurations
                    all_configs = data if isinstance(data, list) else [data]
                    custom_configs = [c for c in all_configs if c.get('active', True)]
    except Exception as e:
        logger.error(f"Error loading custom configs: {e}")
    
    return custom_configs
def execute_process():
     # ── Re-read custom_patterns.json so any edits since last run are live ──
    reload_web_platforms()
    total_countries, urls_per_country, total_tests = calculate_totals()
    """Execute the main scraping process for all countries and platforms"""
    logger.info("=" * 60)
    logger.info("AUTOMATED TESTING - MULTIPLE COUNTRIES & PLATFORMS")
    logger.info("=" * 60)

    logger.info(f"📍 Countries to test: {len(COUNTRIES)} countries")
    logger.info(f"Total URLs to test: {total_tests}")
    # List web platforms being tested
    active_platforms = [wp for wp in WEB_PLATFORMS if wp.get("active", True)] 
    platform_names = [wp["name"] for wp in active_platforms]
    logger.info(f"🌐 Web Platforms: {', '.join(platform_names)}")
    
    logger.info("📱 App Platforms: Android & Apple (both automatically)")
    logger.info("🗂️  Categories: Platform-specific (fixed sets)")

    # Calculate total URLs for all countries and web platforms
  


    existing_snapshots = load_existing_snapshots(TARGET_DIR/f"AUTOMATION_{datetime.now().strftime('%Y-%m-%d')}")
    # Setup Chrome options
    options = Options()
    for option in CHROME_OPTIONS:
        options.add_argument(option)

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, WEBDRIVER_WAIT)

    # Ensure main directory exists
    ensure_directory_exists(TARGET_DIR)
    
    # Create timestamped folder for this execution
    timestamp = datetime.now().strftime("%Y-%m-%d")
    execution_folder = TARGET_DIR / f"AUTOMATION_{timestamp}"
    ensure_directory_exists(execution_folder)

    # ==================================================
    # ✅ SHARED SEQUENCE COUNTER FOR ALL PLATFORMS
    # ==================================================
    country_sequence_counters = initialize_counters_from_files(execution_folder, COUNTRIES)
    logger.info(f"🔢 Initialized shared sequence counters for {len(COUNTRIES)} countries")
    
    # ==================================================
    # ✅ Initialize AppTweak Integration with shared counter
    # ==================================================
    if APPTWEAK_AVAILABLE:
        apptweak = AppTweakIntegration(
            driver=driver,
            execution_folder=execution_folder,
            sequence_counters=country_sequence_counters,  # Pass the shared counter
            existing_snapshots=existing_snapshots  # ✅ MUST PASS THIS
        )
        logger.info("✅ AppTweakIntegration initialized")
    else:
        apptweak = None
        logger.warning("⚠ AppTweakIntegration not available, AppTweak functionality will be disabled")
    
    logger.info(f"📁 Files will be saved to: {execution_folder}")

    # Track overall statistics
    all_successful = []
    all_failed = []
    
    try:
        # Process each country
        for country_index, country in enumerate(COUNTRIES, 1):
            logger.info("=" * 60)
            logger.info(f"COUNTRY {country_index}/{total_countries}: {country['name']} ({country['code']})")
            logger.info("=" * 60)

            # Initialize sequence counter for this country if not exists
            if country['number'] not in country_sequence_counters:
                country_sequence_counters[country['number']] = 0
                logger.debug(f"      🔢 Initialized counter for country {country['number']}")

            # Process each web platform for this country
            for web_platform in WEB_PLATFORMS:
                if not web_platform.get("active", True):
                    continue
                logger.info(f"🌐 WEB PLATFORM: {web_platform['name']}")

                # ============================================
                # SPECIAL HANDLING FOR APPTWEAK
                # ============================================
                if web_platform["type"] == "apptweak":
                    if not APPTWEAK_AVAILABLE or apptweak is None:
                        logger.warning("⚠ AppTweak functionality is disabled")
                        continue
                        
                    try:
                        logger.info(f"\n🚀 Starting AppTweak automation for {country['name']}")

                        # Get current sequence number BEFORE AppTweak starts
                        current_sequence_before = country_sequence_counters.get(country['number'], 0)
                        logger.debug(f"      📊 Sequence before AppTweak: {current_sequence_before}")

                        # ✅ FIX: Pass web_platform as second parameter
                        success_count, total_count = apptweak.execute_apptweak_flow(country, web_platform)

                        # Get sequence after AppTweak
                        current_sequence_after = country_sequence_counters.get(country['number'], 0)
                        apptweak_files_created = current_sequence_after - current_sequence_before
                        
                        logger.info(f"      📊 AppTweak created {apptweak_files_created} files")

                        # Add AppTweak results to statistics
                        for i in range(success_count):
                            all_successful.append(
                                (country['name'], web_platform['name'], "apptweak", "apptweak_category", web_platform["base_url"])
                            )
                        
                        for i in range(total_count - success_count):
                            all_failed.append(
                                (country['name'], web_platform['name'], "apptweak", "apptweak_category", web_platform["base_url"], "AppTweak automation failed")
                            )

                        logger.info(
                            f"✅ AppTweak finished for {country['name']}: "
                            f"{success_count}/{total_count} MHTML files saved"
                        )

                        # Delay after AppTweak
                        apptweak_delay = DELAYS.get("apptweak_country_delay", 5)
                        time.sleep(apptweak_delay)
                        
                        continue  # Skip normal URL processing for AppTweak

                    except Exception as e:
                        logger.error(f"❌ AppTweak failed for {country['name']}: {str(e)[:120]}")
                        all_failed.append(
                            (country['name'], web_platform['name'], "apptweak", "apptweak", web_platform["base_url"], f"AppTweak error: {str(e)[:100]}")
                        )
                        continue
                # ============================================
                # UNIVERSAL ENGINE HANDLING
                # ============================================
                if web_platform["type"] == "universal":

                    if not UNIVERSAL_AVAILABLE:
                        logger.warning("⚠ Universal engine disabled")
                        continue

                    logger.info(f"\n🚀 Starting Universal automation for {country['name']}")

                    try:
                        current_sequence_before = country_sequence_counters.get(
                            country['number'], 0
                        )

                        success_count, total_count = execute_universal_flow(
                            driver=driver,
                            country_data=country,
                            platform_config=web_platform,
                            execution_folder=execution_folder,
                            sequence_counters=country_sequence_counters,
                            existing_snapshots=existing_snapshots
                        )

                        current_sequence_after = country_sequence_counters.get(
                            country['number'], 0
                        )

                        files_created = current_sequence_after - current_sequence_before

                        logger.info(f"      📊 Universal created {files_created} files")

                        # Add results to overall statistics
                        for i in range(success_count):
                            all_successful.append(
                                (
                                    country['name'],
                                    web_platform['name'],
                                    "universal",
                                    "universal_category",
                                    web_platform["base_url"]
                                )
                            )

                        for i in range(total_count - success_count):
                            all_failed.append(
                                (
                                    country['name'],
                                    web_platform['name'],
                                    "universal",
                                    "universal_category",
                                    web_platform["base_url"],
                                    "Universal automation failed"
                                )
                            )

                        logger.info(
                            f"✅ Universal finished for {country['name']}: "
                            f"{success_count}/{total_count} MHTML files saved"
                        )

                    except Exception as e:
                        logger.error(
                            f"❌ Universal failed for {country['name']}: {str(e)[:120]}"
                        )

                    continue  # Skip normal URL processing

                # ============================================
                # NORMAL PROCESSING FOR OTHER PLATFORMS
                # ============================================
                urls = []

                # Build URLs for this country and web platform
                logger.info(f"   Building URLs for {web_platform['name']}...")

                for app_platform in APP_PLATFORMS:
                    categories = PLATFORM_CATEGORIES[app_platform]
                    for category in categories:
                        country_slug = get_country_slug(country, web_platform["type"])
                        category_slug = slugify(category, web_platform["type"])

                        # Generate URL based on platform
                        url = get_url_for_platform(
                            web_platform["base_url"],
                            web_platform["type"],
                            app_platform,
                            country_slug,
                            category_slug
                        )

                        urls.append((app_platform, category, url))

                logger.info(f"   ✅ URLs generated: {len(urls)}")
                logger.info(f"   🚀 Starting testing...")

                successful_urls = []
                failed_urls = []

                for i, (app_platform, category, url) in enumerate(urls):

                    safe_category = clean_category_name(category).lower()
                    task_key = (
                        country["code"],
                        web_platform["name"].lower(),
                        app_platform.lower(),
                        safe_category
                    )

                    if task_key in existing_snapshots:
                        logger.info(f"      ⏭️ Skipping already saved: {task_key}")
                        continue

                    print_progress(i + 1, len(urls), f"   Testing {web_platform['name']}")
                    
                    logger.info(f"   [{i + 1}/{len(urls)}] {app_platform.upper()} - {category}")
                    logger.info(f"      URL: {url}")

                    try:
                        # Load URL with retry
                        test_url_with_retry(driver, url)
                        
                        # Detect human verification
                        if is_human_verification(driver):
                            if not wait_for_manual_verification(driver):
                                logger.warning(f"      ⏭️ Skipping due to verification timeout")
                                failed_urls.append((country['name'], web_platform['name'], app_platform, category, url,
                                                    "Verification timeout"))
                                continue

                        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                        time.sleep(2)

                        # ---------- PAGE VALIDATION ----------
                        is_bad, reason = is_page_unusable(driver, web_platform["type"])

                        if is_bad:
                            
                            logger.warning(f"      ⏭️ Skipped: {reason}")
                            failed_urls.append(
                              
                                (country['name'], web_platform['name'], app_platform, category, url, reason)
                               
                            )
                            continue

                    except Exception as e:
                        error_msg = str(e)[:120]
                        logger.error(f"      ❌ Error during page load/validation: {error_msg}")
                        
                        failed_urls.append(
                            (country['name'], web_platform['name'], app_platform, category, url, f"Load/validation error: {error_msg}")
                        )
                        random_sleep(*DELAYS["between_tests"])
                        continue

                    # ---------- VALID PAGE - SAVE FILES ----------
                    logger.info(f"      ✅ Page validated successfully")

                    # Get date for file naming
                    date_stamp = datetime.now().strftime("%Y%m%d")

                    # ✅ GET SYNCHRONIZED SEQUENCE NUMBER
                    sequence_number = get_next_sequence_number(country, country_sequence_counters)

                    # Create safe category name
                    safe_category = clean_category_name(category)

                    # Create base filename using the function (synchronized with AppTweak)
                    base_filename = create_base_filename(
                        country=country,
                        sequence=sequence_number,
                        web_platform=web_platform,
                        app_platform=app_platform,
                        category=safe_category,
                        date_stamp=date_stamp
                    )

                    # Save web snapshot (MHTML) using the same function as AppTweak
                    try:
                        success, result = save_mhtml_snapshot(
                            driver=driver,
                            base_filename=base_filename,
                            folder_path=execution_folder
                        )
                        
                        if success:
                            logger.info(f"      💾 Web snapshot saved: {result}")
                            existing_snapshots.add(task_key)

                            successful_urls.append(
                                (country['name'], web_platform['name'], app_platform, category, url)
                            )
                        else:
                            logger.error(f"      ⚠️ Could not capture web snapshot: {result}")
                            failed_urls.append(
                                (country['name'], web_platform['name'], app_platform, category, url, f"MHTML save error: {result}")
                            )
                        
                    except Exception as e:
                        error_msg = str(e)[:120]
                        logger.error(f"      ❌ Error saving MHTML: {error_msg}")
                        failed_urls.append(
                            (country['name'], web_platform['name'], app_platform, category, url, f"MHTML save error: {error_msg}")
                        )

                    random_sleep(*DELAYS["between_tests"])

                # Update overall statistics
                all_successful.extend(successful_urls)
                all_failed.extend(failed_urls)

                # Platform summary for this country
                logger.info(f"\n   📊 {web_platform['name']} - {country['name']} SUMMARY:")
                logger.info(f"      Total URLs: {len(urls)}")
                logger.info(f"      Successful: {len(successful_urls)}")
                logger.info(f"      Failed: {len(failed_urls)}")
                if len(urls) > 0:
                    success_rate = (len(successful_urls) / len(urls) * 100)
                    logger.info(f"      Success rate: {success_rate:.1f}%")

            # Small pause between countries
            if country_index < total_countries:
                logger.info(f"\n⏳ Preparing for next country...")
                random_sleep(*DELAYS["between_countries"])

    finally:
        driver.quit()
    
    
    # Final summary report
    logger.info("=" * 60)
    logger.info("AUTOMATED TESTING COMPLETE - ALL COUNTRIES")
    logger.info("=" * 60)
    
    total_tests_actual = len(all_successful) + len(all_failed)
    logger.info(f"Total Countries tested: {len(COUNTRIES)}")
    logger.info(f"Total tests performed: {total_tests_actual}")
    logger.info(f"Successful: {len(all_successful)}")
    logger.info(f"Failed: {len(all_failed)}")


    if total_tests_actual > 0:
        overall_rate = (len(all_successful) / total_tests_actual * 100)
        logger.info(f"Overall success rate: {overall_rate:.1f}%")

    # Show sequence counter summary
    logger.info(f"\n🔢 SEQUENCE COUNTER SUMMARY:")
    for country in COUNTRIES:
        final_sequence = country_sequence_counters.get(country['number'], 0)
        logger.info(f"  {country['name']}: {final_sequence} total files created")

    # Country breakdown
    logger.info(f"\n📋 COUNTRY-BY-COUNTRY RESULTS:")
    for country in COUNTRIES:
        country_success = sum(1 for c, _, _, _, _ in all_successful if c == country['name'])
        country_failed = sum(1 for c, _, _, _, _, _ in all_failed if c == country['name'])
        country_total = country_success + country_failed
        if country_total > 0:
            country_rate = (country_success / country_total * 100)
            logger.info(f"  {country['name']}: {country_success}/{country_total} ({country_rate:.1f}%)")

    # Web platform breakdown
    logger.info(f"\n🌐 WEB PLATFORM RESULTS:")
    for web_platform in WEB_PLATFORMS:
        platform_success = sum(1 for _, wp, _, _, _ in all_successful if wp == web_platform['name'])
        platform_failed = sum(1 for _, wp, _, _, _, _ in all_failed if wp == web_platform['name'])
        platform_total = platform_success + platform_failed
        if platform_total > 0:
            platform_rate = (platform_success / platform_total * 100)
            logger.info(f"  {web_platform['name']}: {platform_success}/{platform_total} ({platform_rate:.1f}%)")

    # Show summary of files saved
    logger.info(f"\n💾 FILES SAVED (Synchronized numbering):")
    logger.info(f"   Location: {execution_folder}")
    
    # Count actual files created
    mhtml_files = list(execution_folder.glob("*.mhtml"))
    logger.info(f"   Total MHTML files created: {len(mhtml_files)}")
    
    # Show files grouped by country
    logger.info(f"   Files by country:")
    for country in COUNTRIES:
        country_files = [f for f in mhtml_files if f.name.startswith(country['number'])]
        if country_files:
            logger.info(f"     • {country['name']}: {len(country_files)} files")
            # Show first file as example
            first_file = sorted(country_files)[0].name if country_files else ""
            logger.info(f"       Example: {first_file}")
    
    logger.info("=" * 60)
    
    # Also print to console for immediate visibility
    print(f"\n📁 All files saved in: {execution_folder}")
    print(f"📊 Total files created: {len(mhtml_files)} MHTML files")
    print(f"🔢 Synchronized numbering across all platforms ✓")


