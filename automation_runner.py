"""automation_runner.py
Core automation logic — called by AutomationTab.run_automation().
Kept separate so the tab stays thin (UI only) and this file
stays focused (business logic only).
"""

import time
import logging
from datetime import datetime
from pathlib import Path
import os


from logging_config import logger
from utils.get_Cur_FY import get_current_year_quarter


# ==========================================
# SHARED EXTRACT HELPER
# ==========================================

def extract_and_append(saved_path, platform_key=None, country_code=None, safe_category=None, execution_folder=None):
    """Extract rows from a saved MHTML and append to All_platforms.xlsx.

    platform_key, country_code, and safe_category are always derived from
    the filename — any passed-in values are ignored. This makes the function
    robust regardless of what the caller passes.
    """
    try:
        from scraper_detectors.platform import detect_platform_from_filename
        from scraper_detectors.country import detect_country_from_filename
        from scraper_detectors.category import detect_category_from_filename
        from scraper_helpers.io import html_from_mhtml_bytes, load_config
        from scraper_pipeline.dispatcher import extract_platform_rows, build_output_rows
        from scraper_helpers.excel import (
            prepare_workbook_for_append,
            append_rows_to_category_sheets,
        )
        from scraper_helpers.console import effective_cap, post_trim_rows
        from scraper_helpers.mhtml_images import build_icon_lookup
        from scraper_models.constants import HEADERS
        from config import TARGET_DIR

        # Always derive from filename — ignores whatever was passed in
        platform_key  = detect_platform_from_filename(saved_path)
        country_code  = detect_country_from_filename(saved_path)
        safe_category = detect_category_from_filename(saved_path)

        if not platform_key:
            logger.warning(f" ⚠️ Extract: could not detect platform from filename: {saved_path}")
            return

        config   = load_config()
        cap      = effective_cap(config.get("max_rows", 10))
        outfile  = str(TARGET_DIR / "All_platforms.xlsx")
        base_url = (config.get("source_base_url") or "").strip()
        quarter  = get_current_year_quarter()

        with open(saved_path, "rb") as f:
            raw_mhtml = f.read()

        html, err = html_from_mhtml_bytes(raw_mhtml)
        if not html or err:
            logger.warning(f" ⚠️ Extract: could not parse MHTML ({err})")
            return

        icon_lookup = build_icon_lookup(raw_mhtml)

        plat_name, rows, reason = extract_platform_rows(
            platform_key,
            html,
            config,
            max_rows=cap,
            source_path=saved_path,
        )

        rows = post_trim_rows(rows, cap)
        if not rows:
            logger.warning(f" ⚠️ Extract: 0 rows from {platform_key} ({reason})")
            return

        final_rows = build_output_rows(
            plat_name,
            rows,
            country_code,
            quarter,
            saved_path,
        )

        wb, ws_map = prepare_workbook_for_append(
            outfile,
            headers=HEADERS,
            category_sheets=("Music", "Navigation", "Messaging"),
        )

        append_rows_to_category_sheets(
            ws_map,
            final_rows,
            safe_category,
            input_dir=str(execution_folder) if execution_folder else str(Path(saved_path).parent),
            base_url=base_url,
            icon_lookup=icon_lookup
        )

        wb.save(outfile)
        logger.info(
            f" 📊 Extracted: {len(final_rows)} rows → {plat_name} [{safe_category}] ({country_code})"
        )

    except Exception as e:
        logger.error(f" ❌ Extract failed: {e}")


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
    is_stopped      = ui_callbacks["get_stop_flag"]
    update_status   = ui_callbacks["update_status"]
    update_progress = ui_callbacks["update_progress"]
    inc_files       = ui_callbacks["increment_files"]
    inc_files_by    = ui_callbacks["increment_files_by"]
    set_counts      = ui_callbacks["set_counts"]

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

    timestamp          = datetime.now().strftime("%Y-%m-%d")
    execution_folder   = TARGET_DIR / f"AUTOMATION_{timestamp}"
    existing_snapshots = load_existing_snapshots(execution_folder)

    options = Options()
    for opt in CHROME_OPTIONS:
        options.add_argument(opt)
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(15)
    wait = WebDriverWait(driver, WEBDRIVER_WAIT)

    ensure_directory_exists(TARGET_DIR)
    ensure_directory_exists(execution_folder)

    country_sequence_counters, used_slots = initialize_counters_from_files(execution_folder, COUNTRIES)
    logger.info(f"🔢 Initialized counters for {len(COUNTRIES)} countries")

    apptweak = None
    if APPTWEAK_AVAILABLE:
        apptweak = AppTweakIntegration(
            driver=driver,
            execution_folder=execution_folder,
            sequence_counters=country_sequence_counters,
            existing_snapshots=existing_snapshots,
            extract_fn=extract_and_append,
            used_slots=used_slots,
        )
        logger.info("✅ AppTweakIntegration initialized")

    logger.info(f"📁 Saving to: {execution_folder}")

    all_successful  = []
    all_failed      = []
    total_pairs     = sum(1 for _ in COUNTRIES for wp in WEB_PLATFORMS if wp.get("active", True))
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
                            # Wire real-time callbacks — fires per file, not at the end
                            apptweak.on_success = lambda: (
                                all_successful.append((country['name'], web_platform['name'],
                                                       "apptweak", "apptweak_category",
                                                       web_platform["base_url"])),
                                set_counts(len(all_successful), len(all_failed)),
                                inc_files(),    
                            )
                            apptweak.on_fail = lambda reason: (
                                all_failed.append((country['name'], web_platform['name'],
                                                   "apptweak", "apptweak_category",
                                                   web_platform["base_url"], reason)),
                                set_counts(len(all_successful), len(all_failed)),
                            )
 
                            apptweak.execute_apptweak_flow(country, web_platform)
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
                            ui_callbacks["on_success"] = lambda: (
                                all_successful.append((country['name'], web_platform['name'],
                                                    "universal", "universal_category",
                                                    web_platform["base_url"])),
                                set_counts(len(all_successful), len(all_failed)),
                                inc_files(),
                            )
                            ui_callbacks["on_fail"] = lambda reason: (
                                all_failed.append((country['name'], web_platform['name'],
                                                "universal", "universal_category",
                                                web_platform["base_url"], reason)),
                                set_counts(len(all_successful), len(all_failed)),
                            )
                            
                            update_status(f"Running: {country['name']} / {web_platform['name']}")
                            execute_universal_flow(
                                driver=driver,
                                country_data=country,
                                platform_config=web_platform,
                                execution_folder=execution_folder,
                                sequence_counters=country_sequence_counters,
                                existing_snapshots=existing_snapshots,
                                extract_fn=extract_and_append,
                                ui_callbacks=ui_callbacks,
                                used_slots=used_slots,
                            )

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
                    sequence_number = get_next_sequence_number(country, country_sequence_counters, used_slots)
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

                            # Extract immediately — platform/country/category derived from filename
                            extract_and_append(
                                saved_path=str(execution_folder / f"{base_filename}.mhtml"),
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


def run_directory_scraping_process(params, ui_callbacks):
    """
    MHTML directory scraping process — no tkinter imports, no self.

    Args:
        params: dict with keys:
                  directory        — path to folder containing MHTML files
                  quarter          — e.g. "2025-Q1"
                  max_rows         — int
                  output_filename  — e.g. "All_platforms.xlsx"
                  category_sheets  — list of sheet names

        ui_callbacks: dict of callables provided by AutomationTab:
                  update_progress(pct)   — set progress bar + label
                  get_stop_flag()        — returns bool
                  set_counts(s, f)       — update success/fail labels

    Returns:
        dict with keys: total, successful, failed, outfile, stopped
    """
    from scraper_helpers.console import iter_mhtml_files
    from scraper_helpers.io import html_from_mhtml_bytes, load_config
    from scraper_detectors.platform import detect_platform_from_filename
    from scraper_detectors.country import detect_country_from_filename
    from scraper_detectors.category import detect_category_from_filename
    from scraper_pipeline.dispatcher import extract_platform_rows, build_output_rows
    from scraper_helpers.excel import prepare_workbook_for_append, append_rows_to_category_sheets
    from scraper_helpers.console import post_trim_rows
    from scraper_helpers.mhtml_images import build_icon_lookup
    from scraper_models.constants import HEADERS
    from config import TARGET_DIR

    dir_path        = params["directory"]
    quarter         = params["quarter"]
    max_rows        = params["max_rows"]
    output_filename = params["output_filename"]
    category_sheets = params.get("category_sheets", ["Music", "Navigation", "Messaging"])

    update_progress = ui_callbacks["update_progress"]
    is_stopped      = ui_callbacks["get_stop_flag"]
    set_counts      = ui_callbacks.get("set_counts", lambda s, f: None)

    files = list(iter_mhtml_files(dir_path))
    files.sort(key=lambda p: os.path.basename(p).lower())

    if not files:
        logger.warning(f"No MHTML files found in: {dir_path}")
        return {"total": 0, "successful": 0, "failed": 0,
                "outfile": "", "stopped": False}

    config   = load_config()
    outfile  = os.path.join(TARGET_DIR, output_filename)
    wb, ws_map = prepare_workbook_for_append(
        outfile, headers=HEADERS,
        category_sheets=tuple(category_sheets) if category_sheets
        else ("Music", "Navigation", "Messaging")
    )
    base_url = (config.get("source_base_url") or "").strip()

    logger.info(f"🔍 Found {len(files)} MHTML files to process")
    total      = len(files)
    successful = 0
    failed     = 0
    stopped    = False

    for idx, file_path in enumerate(files, 1):
        if is_stopped():
            logger.warning("⏹️ Scraping stopped by user")
            logger.info(f"   ✅ Completed: {successful} files successfully")
            logger.info(f"   ⏸️ Stopped at: {os.path.basename(file_path)}")
            stopped = True
            break

        filename = os.path.basename(file_path)
        update_progress((idx / total) * 100)

        try:
            platform_key  = detect_platform_from_filename(file_path)
            country_code  = detect_country_from_filename(file_path)
            file_category = detect_category_from_filename(file_path)

            if not platform_key:
                logger.warning(
                    f"⚠️ [{idx}/{total}] Skipping {filename}: "
                    "No platform hint from filename"
                )
                failed += 1
                set_counts(successful, failed)
                continue

            with open(file_path, "rb") as f:
                raw_mhtml = f.read()

            html, err = html_from_mhtml_bytes(raw_mhtml)
            if err or not html:
                logger.error(
                    f"❌ [{idx}/{total}] Failed: {filename} - "
                    f"{err or 'Failed to parse MHTML'}"
                )
                failed += 1
                set_counts(successful, failed)
                continue

            icon_lookup = build_icon_lookup(raw_mhtml)

            plat_name, rows, reason = extract_platform_rows(
                platform_key, html, config,
                max_rows=max_rows, source_path=file_path
            )
            rows = post_trim_rows(rows, max_rows)

            if not rows:
                logger.warning(
                    f"⚠️ [{idx}/{total}] Skipping {filename}: "
                    f"0 rows from {platform_key} ({reason})"
                )
                failed += 1
                set_counts(successful, failed)
                continue

            final_rows = build_output_rows(
                plat_name, rows, country_code, quarter, file_path
            )
            append_rows_to_category_sheets(
                ws_map,
                final_rows,
                file_category,
                input_dir=dir_path,
                base_url=base_url,
                icon_lookup=icon_lookup,
            )

            country_info  = f" ({country_code})" if country_code else ""
            category_info = f" [{file_category}]" if file_category else ""
            logger.info(
                f"✅ [{idx}/{total}] Processed: {filename} → {len(final_rows)} rows "
                f"from {plat_name}{country_info}{category_info}"
            )
            successful += 1
            set_counts(successful, failed)

        except Exception as e:
            logger.error(f"❌ [{idx}/{total}] Failed: {filename} - {str(e)}")
            failed += 1
            set_counts(successful, failed)

    try:
        wb.save(outfile)
        logger.info(f"📝 Saved workbook: {outfile}")
    except Exception as e:
        logger.error(f"❌ Failed to save workbook: {e}")

    logger.info(f"\n{'=' * 50}")
    logger.info("✅ SCRAPING COMPLETE" if not stopped else "⏹️ SCRAPING STOPPED")
    logger.info(f"   Directory : {dir_path}")
    logger.info(f"   Output    : {outfile}")
    logger.info(f"   Total     : {total}")
    logger.info(f"   Successful: {successful}")
    logger.info(f"   Failed    : {failed}")
    logger.info(f"{'=' * 50}")

    for cat in category_sheets:
        ws = ws_map.get(cat)
        if ws:
            count = max(0, ws.max_row - 1)
            logger.info(f"   - {cat}: {count} row(s)")

    return {
        "total":      total,
        "successful": successful,
        "failed":     failed,
        "outfile":    outfile,
        "stopped":    stopped,
    }