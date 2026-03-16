"""automation_runner.py
Core automation logic — called by AutomationTab.run_automation().
Kept separate so the tab stays thin (UI only) and this file
stays focused (business logic only).
"""

import time
import logging
from datetime import datetime
from pathlib import Path

from logging_config import logger
from utils.get_Cur_FY import get_current_year_quarter


# ==========================================
# SHARED EXTRACT HELPER
# ==========================================

def extract_and_append(saved_path, platform_key, country, safe_category, execution_folder):
    """Extract rows from a saved MHTML and append to All_platforms.xlsx.
    Called immediately after every MHTML save across all three platform paths
    (normal URL, apptweak, universal) so no end-of-run batch scrape is needed."""
    try:
        from scraper_helpers.io import html_from_mhtml_bytes, load_config
        from scraper_pipeline.dispatcher import extract_platform_rows, build_output_rows
        from scraper_helpers.excel import prepare_workbook_for_append, append_rows_to_category_sheets
        from scraper_helpers.console import effective_cap, post_trim_rows
        from scraper_models.constants import HEADERS
        from config import TARGET_DIR

        _config   = load_config()
        _cap      = effective_cap(_config.get("max_rows", 10))
        _outfile  = str(TARGET_DIR / "All_platforms.xlsx")
        _base_url = (_config.get("source_base_url") or "").strip()
        _quarter  = get_current_year_quarter()

        _country_dict = {"name": country["name"], "code": country["code"]}

        with open(saved_path, "rb") as _f:
            _html, _err = html_from_mhtml_bytes(_f.read())

        if not _html or _err:
            logger.warning(f"      ⚠️ Extract: could not parse MHTML ({_err})")
            return

        _plat_name, _rows, _reason = extract_platform_rows(
            platform_key, _html, _config,
            max_rows=_cap, source_path=saved_path
        )
        _rows = post_trim_rows(_rows, _cap)

        if not _rows:
            logger.warning(f"      ⚠️ Extract: 0 rows from {platform_key} ({_reason})")
            return

        _final_rows = build_output_rows(
            _plat_name, _rows, _country_dict, _quarter, saved_path
        )
        _wb, _ws_map = prepare_workbook_for_append(
            _outfile, headers=HEADERS,
            category_sheets=("Music", "Navigation", "Messaging")
        )
        append_rows_to_category_sheets(
            _ws_map, _final_rows, safe_category,
            input_dir=str(execution_folder),
            base_url=_base_url
        )
        _wb.save(_outfile)
        logger.info(f"      📊 Extracted: {len(_final_rows)} rows → {_plat_name} [{safe_category}]")

    except Exception as e:
        logger.error(f"      ❌ Extract failed: {e}")


# ==========================================
# MAIN AUTOMATION ENTRY POINT
# ==========================================

def run_automation_process(ui_callbacks):
    """
    Full automation loop — country × platform × category.

    Args:
        ui_callbacks: dict of callables provided by AutomationTab so this
                      module never imports tkinter directly.

                      Expected keys:
                        update_status(text)          — set status label text
                        update_progress(pct)         — set progress bar + label
                        increment_files()            — bump files_count by 1
                        increment_files_by(n)        — bump files_count by n
                        set_counts(success, failed)  — update both stat labels
                        get_stop_flag()              — returns bool STOP_AUTOMATION

    Returns:
        dict with keys: all_successful, all_failed, mhtml_files, execution_folder
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from config import (
        COUNTRIES, PLATFORM_CATEGORIES, WEB_PLATFORMS, APP_PLATFORMS,
        TARGET_DIR, DELAYS, CHROME_OPTIONS, WEBDRIVER_WAIT, reload_web_platforms
    )
    from utils.utils import (
        slugify, get_country_slug, get_url_for_platform,
        print_progress, random_sleep, clean_category_name,
        get_next_sequence_number, calculate_totals
    )
    from Web_validators import (
        is_human_verification, is_page_unusable,
        wait_for_manual_verification, test_url_with_retry
    )
    from file_handlers import (
        ensure_directory_exists, save_mhtml_snapshot,
        create_base_filename, load_existing_snapshots,
        initialize_counters_from_files
    )
    from scraper_detectors.category import detect_category_from_filename

    try:
        from apptweak_integration import AppTweakIntegration
        APPTWEAK_AVAILABLE = True
    except ImportError:
        APPTWEAK_AVAILABLE = False
        class AppTweakIntegration:
            def __init__(self, *a, **kw): pass
            def execute_apptweak_flow(self, *a, **kw): return 0, 0

    try:
        from automation_engine_initial import execute_universal_flow
        UNIVERSAL_AVAILABLE = True
    except ImportError:
        UNIVERSAL_AVAILABLE = False

    # Shorthand helpers so the loop stays readable
    is_stopped       = ui_callbacks["get_stop_flag"]
    update_status    = ui_callbacks["update_status"]
    update_progress  = ui_callbacks["update_progress"]
    inc_files        = ui_callbacks["increment_files"]
    inc_files_by     = ui_callbacks["increment_files_by"]
    set_counts       = ui_callbacks["set_counts"]

    # ── Setup ─────────────────────────────────────────────────────────────
    reload_web_platforms()
    total_countries, _, total_tests = calculate_totals()

    logger.info("=" * 60)
    logger.info("AUTOMATED TESTING - MULTIPLE COUNTRIES & PLATFORMS")
    logger.info("=" * 60)
    logger.info(f"📍 Countries to test: {len(COUNTRIES)}")
    logger.info(f"Total URLs to test: {total_tests}")

    active_platforms = [wp for wp in WEB_PLATFORMS if wp.get("active", True)]
    logger.info(f"🌐 Web Platforms: {', '.join(wp['name'] for wp in active_platforms)}")
    logger.info("📱 App Platforms: Android & Apple (both automatically)")

    timestamp         = datetime.now().strftime("%Y-%m-%d")
    execution_folder  = TARGET_DIR / f"AUTOMATION_{timestamp}"
    existing_snapshots = load_existing_snapshots(execution_folder)

    options = Options()
    for opt in CHROME_OPTIONS:
        options.add_argument(opt)
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(15)
    wait = WebDriverWait(driver, WEBDRIVER_WAIT)

    ensure_directory_exists(TARGET_DIR)
    ensure_directory_exists(execution_folder)

    country_sequence_counters = initialize_counters_from_files(execution_folder, COUNTRIES)
    logger.info(f"🔢 Initialized counters for {len(COUNTRIES)} countries")

    apptweak = None
    if APPTWEAK_AVAILABLE:
        apptweak = AppTweakIntegration(
            driver=driver,
            execution_folder=execution_folder,
            sequence_counters=country_sequence_counters,
            existing_snapshots=existing_snapshots,
            extract_fn=extract_and_append,   # ← scrape every key inline
        )
        logger.info("✅ AppTweakIntegration initialized")

    logger.info(f"📁 Saving to: {execution_folder}")

    all_successful = []
    all_failed     = []
    total_pairs    = sum(1 for _ in COUNTRIES for wp in WEB_PLATFORMS if wp.get("active", True))
    completed_pairs = 0

    try:
        for country_index, country in enumerate(COUNTRIES, 1):

            if is_stopped():
                logger.warning("⏹️ Stopped before next country.")
                break

            logger.info("=" * 60)
            logger.info(f"COUNTRY {country_index}/{total_countries}: "
                        f"{country['name']} ({country['code']})")
            logger.info("=" * 60)
            update_status(f"Running: {country['name']}")

            if country['number'] not in country_sequence_counters:
                country_sequence_counters[country['number']] = 0

            for web_platform in WEB_PLATFORMS:
                if not web_platform.get("active", True):
                    continue

                if is_stopped():
                    logger.warning("⏹️ Stopped before next platform.")
                    break

                logger.info(f"🌐 WEB PLATFORM: {web_platform['name']}")
                update_status(f"Running: {country['name']} / {web_platform['name']}")

                # ── AppTweak ──────────────────────────────────────────────
                if web_platform["type"] == "apptweak":
                    if not APPTWEAK_AVAILABLE or apptweak is None:
                        logger.warning("⚠ AppTweak disabled")
                    else:
                        try:
                            seq_before = country_sequence_counters.get(country['number'], 0)
                            success_count, total_count = apptweak.execute_apptweak_flow(
                                country, web_platform
                            )
                            seq_after  = country_sequence_counters.get(country['number'], 0)
                            files_made = seq_after - seq_before
                            logger.info(f"      📊 AppTweak created {files_made} files")
                            # Scraping is handled inline inside AppTweakIntegration
                            # (extract_fn fires immediately after each MHTML save)

                            for _ in range(success_count):
                                all_successful.append((country['name'], web_platform['name'],
                                                       "apptweak", "apptweak_category",
                                                       web_platform["base_url"]))
                            for _ in range(total_count - success_count):
                                all_failed.append((country['name'], web_platform['name'],
                                                   "apptweak", "apptweak_category",
                                                   web_platform["base_url"],
                                                   "AppTweak automation failed"))

                            set_counts(len(all_successful), len(all_failed))
                            inc_files_by(files_made)
                            time.sleep(DELAYS.get("apptweak_country_delay", 5))

                        except Exception as e:
                            logger.error(f"❌ AppTweak failed: {str(e)[:120]}")
                            all_failed.append((country['name'], web_platform['name'],
                                               "apptweak", "apptweak", web_platform["base_url"],
                                               f"AppTweak error: {str(e)[:100]}"))

                    completed_pairs += 1
                    update_progress(completed_pairs / total_pairs * 100)
                    continue

                # ── Universal engine ──────────────────────────────────────
                if web_platform["type"] == "universal":
                    if not UNIVERSAL_AVAILABLE:
                        logger.warning("⚠ Universal engine disabled")
                    else:
                        try:
                            seq_before = country_sequence_counters.get(country['number'], 0)
                            success_count, total_count = execute_universal_flow(
                                driver=driver,
                                country_data=country,
                                platform_config=web_platform,
                                execution_folder=execution_folder,
                                sequence_counters=country_sequence_counters,
                                existing_snapshots=existing_snapshots,
                                extract_fn=extract_and_append,  # ← scrape every key inline
                            )
                            seq_after  = country_sequence_counters.get(country['number'], 0)
                            files_made = seq_after - seq_before
                            logger.info(f"      📊 Universal created {files_made} files")
                            # Scraping is handled inline inside execute_universal_flow
                            # (extract_fn fires immediately after each MHTML save)

                            for _ in range(success_count):
                                all_successful.append((country['name'], web_platform['name'],
                                                       "universal", "universal_category",
                                                       web_platform["base_url"]))
                            for _ in range(total_count - success_count):
                                all_failed.append((country['name'], web_platform['name'],
                                                   "universal", "universal_category",
                                                   web_platform["base_url"],
                                                   "Universal automation failed"))

                            set_counts(len(all_successful), len(all_failed))
                            inc_files_by(files_made)

                        except Exception as e:
                            logger.error(f"❌ Universal failed: {str(e)[:120]}")
                            all_failed.append((country['name'], web_platform['name'],
                                               "universal", "universal_category",
                                               web_platform["base_url"],
                                               f"Universal error: {str(e)[:100]}"))

                    completed_pairs += 1
                    update_progress(completed_pairs / total_pairs * 100)
                    continue

                # ── Normal URL processing ─────────────────────────────────
                urls = []
                for app_platform in APP_PLATFORMS:
                    for category in PLATFORM_CATEGORIES[app_platform]:
                        country_slug  = get_country_slug(country, web_platform["type"])
                        category_slug = slugify(category, web_platform["type"])
                        url = get_url_for_platform(
                            web_platform["base_url"], web_platform["type"],
                            app_platform, country_slug, category_slug
                        )
                        urls.append((app_platform, category, url))

                logger.info(f"   ✅ URLs generated: {len(urls)}")
                successful_urls = []
                failed_urls     = []

                for i, (app_platform, category, url) in enumerate(urls):

                    if is_stopped():
                        logger.warning("⏹️ Stopped mid-URL loop.")
                        break

                    safe_category = clean_category_name(category).lower()
                    task_key = (
                        country["code"],
                        web_platform["name"].lower(),
                        app_platform.lower(),
                        safe_category
                    )

                    if task_key in existing_snapshots:
                        logger.info(f"      ⏭️ Already saved: {task_key}")
                        continue

                    print_progress(i + 1, len(urls), f"   Testing {web_platform['name']}")
                    logger.info(f"   [{i+1}/{len(urls)}] {app_platform.upper()} - {category}")
                    logger.info(f"      URL: {url}")

                    try:
                        test_url_with_retry(driver, url)

                        if is_human_verification(driver):
                            if not wait_for_manual_verification(driver):
                                logger.warning("      ⏭️ Verification timeout")
                                failed_urls.append((country['name'], web_platform['name'],
                                                    app_platform, category, url,
                                                    "Verification timeout"))
                                continue

                        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                        time.sleep(2)

                        is_bad, reason = is_page_unusable(driver, web_platform["type"])
                        if is_bad:
                            logger.warning(f"      ⏭️ Skipped: {reason}")
                            failed_urls.append((country['name'], web_platform['name'],
                                                app_platform, category, url, reason))
                            continue

                    except Exception as e:
                        logger.error(f"      ❌ Load error: {str(e)[:120]}")
                        failed_urls.append((country['name'], web_platform['name'],
                                            app_platform, category, url,
                                            f"Load error: {str(e)[:120]}"))
                        random_sleep(*DELAYS["between_tests"])
                        continue

                    logger.info("      ✅ Page validated")

                    date_stamp      = datetime.now().strftime("%Y%m%d")
                    sequence_number = get_next_sequence_number(country, country_sequence_counters)
                    base_filename   = create_base_filename(
                        country=country,
                        sequence=sequence_number,
                        web_platform=web_platform,
                        app_platform=app_platform,
                        category=clean_category_name(category),
                        date_stamp=date_stamp
                    )

                    try:
                        success, result = save_mhtml_snapshot(
                            driver=driver,
                            base_filename=base_filename,
                            folder_path=execution_folder
                        )
                        if success:
                            logger.info(f"      💾 Saved: {result}")
                            existing_snapshots.add(task_key)
                            successful_urls.append((country['name'], web_platform['name'],
                                                    app_platform, category, url))
                            inc_files()

                            # Extract this MHTML immediately
                            extract_and_append(
                                saved_path=str(execution_folder / f"{base_filename}.mhtml"),
                                platform_key=web_platform["type"],
                                country=country,
                                safe_category=safe_category,
                                execution_folder=execution_folder
                            )
                        else:
                            logger.error(f"      ⚠️ Snapshot error: {result}")
                            failed_urls.append((country['name'], web_platform['name'],
                                                app_platform, category, url,
                                                f"MHTML save error: {result}"))

                    except Exception as e:
                        failed_urls.append((country['name'], web_platform['name'],
                                            app_platform, category, url,
                                            f"MHTML save error: {str(e)[:120]}"))

                    all_successful.extend(successful_urls[-1:])
                    all_failed.extend(failed_urls[-1:])
                    set_counts(len(all_successful), len(all_failed))
                    random_sleep(*DELAYS["between_tests"])

                completed_pairs += 1
                update_progress(completed_pairs / total_pairs * 100)
                logger.info(f"\n   📊 {web_platform['name']} - {country['name']}:")
                logger.info(f"      Successful: {len(successful_urls)} / Failed: {len(failed_urls)}")

            if is_stopped():
                break

            if country_index < total_countries:
                logger.info("\n⏳ Next country...")
                random_sleep(*DELAYS["between_countries"])

    finally:
        driver.quit()

    # ── Final summary ──────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("AUTOMATED TESTING COMPLETE" if not is_stopped()
                else "AUTOMATED TESTING STOPPED BY USER")
    logger.info("=" * 60)
    total_actual = len(all_successful) + len(all_failed)
    logger.info(f"Successful: {len(all_successful)} / Failed: {len(all_failed)}")
    if total_actual:
        logger.info(f"Overall success rate: {len(all_successful)/total_actual*100:.1f}%")

    mhtml_files = list(execution_folder.glob("*.mhtml"))
    logger.info(f"💾 Total MHTML files: {len(mhtml_files)} → {execution_folder}")

    return {
        "all_successful":   all_successful,
        "all_failed":       all_failed,
        "mhtml_files":      mhtml_files,
        "execution_folder": execution_folder,
    }