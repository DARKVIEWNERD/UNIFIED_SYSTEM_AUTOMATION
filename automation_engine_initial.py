# universal_automation_engine.py
# Integration-ready version (controlled by main.py)

import json
import pathlib
import time
import logging
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from config import PLATFORM_CATEGORIES, COUNTRIES
from logging_config import logger
from utils.utils import print_progress

# 🔥 IMPORT UNIVERSAL VALIDATORS
from Web_validators import (
    handle_platform_cookies,
    is_human_verification,
    wait_for_manual_verification,
    is_page_unusable,
    test_url_with_retry
)

DEFAULT_TIMEOUT = 10

# ==========================================
# PLATFORM ALIASES (FOR DETECTION ONLY)
# ==========================================

PLATFORM_ALIASES = {
    "android": ["android", "google play", "play store"],
    "apple": ["iphone app store","iphone", "ios", "app store", "apple"]
}

# ==========================================
# STABILIZER
# ==========================================

def wait_for_stable(driver, timeout=20):
    wait = WebDriverWait(driver, timeout)

    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

    try:
        wait.until(lambda d: d.execute_script(
            "return (window.jQuery ? jQuery.active == 0 : true)"
        ))
    except Exception:
        pass

    time.sleep(0.5)

# ==========================================
# SAFE PAGE INIT (MAIN-CONTROLLED DRIVER)
# ==========================================

def safe_initialize_page(driver, url, platform_name=None):
    test_url_with_retry(driver, url)
    wait_for_stable(driver)

    handle_platform_cookies(driver, platform_name)

    if is_human_verification(driver):
        wait_for_manual_verification(driver)

    unusable, reason = is_page_unusable(driver, platform_name)
    if unusable:
        logger.warning(f"⚠ Page unusable after load: {reason}")

# ==========================================
# SELECTOR RESOLUTION
# ==========================================

def resolve_selector(selector):
    if selector.startswith("//"):
        return By.XPATH, selector
    elif selector.startswith("#") or selector.startswith(".") or " " in selector:
        return By.CSS_SELECTOR, selector
    else:
        return By.XPATH, f"//*[contains(text(), '{selector}')]"

def safe_find(driver, by, selector):
    wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
    return wait.until(EC.presence_of_element_located((by, selector)))

# ==========================================
# PLATFORM AUTO DETECT
# ==========================================

def auto_detect_and_select_platform(driver, target_platform):
    aliases = PLATFORM_ALIASES.get(target_platform.lower(), [target_platform.lower()])

    logger.info(f"🔎 Auto-detecting platform: {target_platform}")

    candidates = driver.find_elements(
        By.XPATH,
        "//*[self::button or self::a or @role='button' or @role='tab']"
    )

    for el in candidates:
        try:
            if not el.is_displayed():
                continue

            text = el.text.strip().lower()

            if any(alias in text for alias in aliases):
                click(driver, el)
                logger.info(f"✔ Auto-selected platform: {text}")
                return True
        except Exception:
            continue

    logger.info("ℹ No platform toggle found.")
    return False

# ==========================================
# CHECK IF PLATFORM PARAM EXISTS
# ==========================================

def platform_param_exists(platform_config):
    """Check if any step in config has param='platform'"""
    return any(
        step.get("param") == "platform"
        for step in platform_config.get("custom_selectors", [])
    )

# ==========================================
# ACTION HELPERS
# ==========================================

def click(driver, element, wait_after=True):
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)

    if wait_after:
        wait_for_stable(driver)

def handle_input(driver, element, value):
    element.clear()
    if value:
        element.send_keys(value)
        element.send_keys(Keys.RETURN)
        wait_for_stable(driver)

def handle_select(driver, element, value):
    if not value:
        return

    try:
        Select(element).select_by_visible_text(value)
        time.sleep(.5)

        driver.execute_script("""
            var event = new Event('change', { bubbles: true });
            arguments[0].dispatchEvent(event);
        """, element)

        wait_for_stable(driver)
        return
    except Exception:
        pass

    click(driver, element)
    time.sleep(.5)
    option = driver.find_element(By.XPATH, f"//*[contains(text(), '{value}')]")
    click(driver, option)

def handle_list(driver, by, selector, value):
    if not value:
        return False

    elements = driver.find_elements(by, selector)
    aliases = PLATFORM_ALIASES.get(value.lower(), [value.lower()])

    for el in elements:
        try:
            text = el.text.strip().lower()

            
            if text == value.lower() or any(alias in text for alias in aliases):
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.5)
                click(driver, el)
                logger.info(f"✔ Selected: {text}")
                return True  # Make sure to return True when found and clicked
        except Exception:
            continue

    logger.warning(f"⚠ Could not find '{value}' in list")
    return False  # Return False if not found

# ==========================================
# STEP EXECUTION
# ==========================================

def execute_step(driver, step, country=None, category=None, platform=None, platform_name=None, mode="all"):
    """
    
    Args:
        mode: "setup" (only steps without category param), 
              "category" (only steps with category param),
              "all" (all steps)
    """
    role = step.get("role", "unknown")
    selector = step.get("selector") or step.get("value")
    element_type = step.get("type", "").lower()
    param_type = step.get("param")
    
    # Filter steps based on mode
    if mode == "setup" and param_type == "category":
        # Skip category steps during setup
        return True
    elif mode == "category" and param_type != "category":
        # Only run category steps during category execution
        if param_type not in ["category", None]:
            return True

    if not selector:
        return False

    param_map = {
        "country": country,
        "category": category,
        "platform": platform
    }

    input_value = param_map.get(param_type)
    by, normalized = resolve_selector(selector)

    # --- Normalizations ---
    p_name = (platform_name or "").strip().lower()
    c_val = (country or "").strip().lower()
    is_sensortower = p_name in {"sensortower", "sensor tower"}

    # Common US label variants
    is_us = (
        c_val in {
            "us", "usa", "u.s.", "u.s.a.",
            "united states", "united states of america"
        } or
        c_val.startswith("us ") or
        c_val.startswith("united states")
    )

    # 1) Skip opening the country dropdown button on SensorTower if the target country is US
    if is_sensortower and is_us and role == "button_country":
        logger.info("⏭️ Skipping 'button_country' click (SensorTower + US).")
        return True

    # 2) Skip the country list selection if the country param resolves to US
    if is_sensortower and is_us and param_type == "country":
        logger.info("⏭️ Skipping 'country' list selection (SensorTower + US).")
        return True

    # Track if we've successfully performed the main action
    action_completed = False
    
    for attempt in range(3):
        try:
            wait_for_stable(driver)

            unusable, reason = is_page_unusable(driver, platform_name)
            if unusable:
                logger.warning(f"⚠ Page invalid before '{role}': {reason}")
                driver.refresh()
                wait_for_stable(driver)

            if element_type == "list":
                result = handle_list(driver, by, normalized, input_value)
                if result:
                    logger.info(f"✔ Executed: {role}")
                    return True
                else:
                    logger.warning(f"⚠ Could not find matching item in list for '{role}' with value '{input_value}'")
                    return False

            element = safe_find(driver, by, normalized)

            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            time.sleep(0.5)

            if "input" in element_type:
                handle_input(driver, element, input_value)
                action_completed = True

            elif "select" in element_type:
                handle_select(driver, element, input_value)
                action_completed = True

            elif "dropdown" in element_type:
                # Defensive: don't open dropdown if no value provided
                if not input_value:
                    logger.info(f"⏭️ Skipping dropdown open for '{role}' (no value).")
                    return True
                result = handle_list(driver, By.XPATH, "//*[self::li or self::span]", input_value)
                if not result:
                    logger.warning(f"⚠ Could not find '{input_value}' in dropdown for '{role}'")
                    return False
                action_completed = True
            else:
                click(driver, element)
                action_completed = True

            # If we get here without exceptions, consider it successful
            if is_sensortower and action_completed:
                logger.info(f"✔ Executed (with success marker): {role}")
                return True
            else:
                logger.info(f"✔ Executed: {role}")
                return True

        except Exception as e:
            # For SensorTower, if we've already completed the action, consider it a success despite the exception
            if is_sensortower and action_completed:
                logger.info(f"✔ Action completed for {role} despite subsequent error: {e}")
                return True
                
            logger.warning(f"⚠ Attempt {attempt+1} failed for {role}: {e}")
            time.sleep(0.5)

    logger.error(f"❌ Step permanently failed: {role}")
    return False
    
# ==========================================
# RUN PLATFORM (NEW HELPER FUNCTION)
# ==========================================

def run_platform(driver, platform_config, country=None, category=None, platform=None, mode="all"):
    """Execute all steps for a platform config with given parameters"""
    platform_name = platform_config.get("name", "unknown")
    
    for step in platform_config.get("custom_selectors", []):
        execute_step(
            driver,
            step,
            country=country,
            category=category,
            platform=platform,
            platform_name=platform_name,
            mode=mode
        )
# ==========================================
# MAIN ENTRY FOR main.py
# ==========================================
def execute_universal_flow(
    driver,
    country_data,
    platform_config,
    execution_folder,
    sequence_counters,
    existing_snapshots
):
    from utils.utils import clean_category_name, get_next_sequence_number
    from file_handlers import create_base_filename, save_mhtml_snapshot

    success_count = 0
    total_attempted = 0

    base_url = platform_config["base_url"]
    platform_name = platform_config.get("name", "unknown")
    country_name = country_data["name"]
    country_code = country_data["code"]

    logger.info(f"\n{'='*60}")
    logger.info(f"🌍 PROCESSING COUNTRY: {country_name} ({country_code})")
    logger.info(f"{'='*60}")

    # ==========================================
    # PROCESS EACH STORE
    # ==========================================

    for store in PLATFORM_ALIASES.keys():

        if (
            platform_name.lower() == "sensortower"
            and store == "android"
            and (country_name == "China" or country_code == "CN")
        ):
            logger.warning(
                f"⚠ SKIPPING: SensorTower Android China combination for {country_name}"
            )
            continue

        categories = PLATFORM_CATEGORIES.get(store, [])
        if not categories:
            continue

        logger.info(f"\n{'─'*40}")
        logger.info(f"📱 STORE: {store.upper()}")
        logger.info(f"{'─'*40}")

        # ==========================================
        # STEP 1: DETECT MISSING SNAPSHOTS FIRST
        # ==========================================

        missing_categories = []

        for category in categories:

            safe_category = clean_category_name(category).lower()

            task_key = (
                country_code,
                platform_name.lower(),
                store.lower(),
                safe_category
            )

            if task_key not in existing_snapshots:
                missing_categories.append(category)
            else:
                logger.info(f"      ⏭️ Existing snapshot detected: {task_key}")

        # ==========================================
        # STEP 2: SKIP STORE IF NOTHING IS MISSING
        # ==========================================

        if not missing_categories:
            logger.info(
                f"      ⏭️ All categories already exist — skipping {platform_name} {store.upper()}"
            )
            continue

        logger.info(
            f"      📌 Categories to process: {len(missing_categories)} / {len(categories)}"
        )

        # ==========================================
        # STEP 3: INITIALIZE PAGE ONLY IF NEEDED
        # ==========================================

        safe_initialize_page(driver, base_url, platform_name=platform_name)

        json_controls_platform = any(
            step.get("param") == "platform"
            for step in platform_config.get("custom_selectors", [])
        )

        if json_controls_platform:
            logger.info("   📌 Platform handled by JSON.")
        else:
            logger.info("   🔎 Attempting auto-detect...")
            auto_detect_and_select_platform(driver, store)

        # ==========================================
        # SETUP PHASE (RUN ONCE PER STORE)
        # ==========================================

        logger.info(f"\n      ⚙️ SETUP PHASE")

        for step in platform_config.get("custom_selectors", []):
            if step.get("param") != "category":

                execute_step(
                    driver,
                    step,
                    country=country_name,
                    platform=store,
                    platform_name=platform_name
                )

        # ==========================================
        # CATEGORY PHASE
        # ==========================================

        logger.info(f"\n      🔄 CATEGORY PHASE")

        for cat_idx, category in enumerate(missing_categories, start=1):

            safe_category = clean_category_name(category).lower()

            task_key = (
                country_code,
                platform_name.lower(),
                store.lower(),
                safe_category
            )

            total_attempted += 1

            print_progress(
                cat_idx,
                len(missing_categories),
                prefix=f"      Processing {platform_name} | {store.upper()} | {category}"
            )

            logger.info(
                f"      🔄 [{cat_idx}/{len(missing_categories)}] Category: {category}"
            )

            results = []

            for step in platform_config.get("custom_selectors", []):
                if step.get("param") == "category":

                    ok = execute_step(
                        driver,
                        step,
                        country=country_name,
                        category=category,
                        platform=store,
                        platform_name=platform_name
                    )

                    results.append(ok)

            if not results or not all(results):
                logger.warning(
                    "      ⏭️ Skipping snapshot: encountered issue during interaction."
                )
                continue

            time.sleep(2)

            # ==========================================
            # SAVE SNAPSHOT
            # ==========================================

            sequence_number = get_next_sequence_number(
                country_data, sequence_counters
            )

            base_filename = create_base_filename(
                country=country_data,
                sequence=sequence_number,
                web_platform=platform_config,
                app_platform=store,
                category=safe_category,
                date_stamp=time.strftime("%Y%m%d")
            )

            success, result = save_mhtml_snapshot(
                driver=driver,
                base_filename=base_filename,
                folder_path=execution_folder
            )

            if success:

                success_count += 1
                existing_snapshots.add(task_key)

                logger.info(f"      💾 Snapshot saved: {result}")

            else:
                logger.warning(f"      ⚠ Snapshot failed: {result}")

        logger.info(f"\n   ✅ Completed store: {store.upper()}")

    # ==========================================
    # COUNTRY SUMMARY
    # ==========================================

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ COMPLETED COUNTRY: {country_code}")
    logger.info(f"   Successful snapshots: {success_count}/{total_attempted}")
    logger.info(f"{'='*60}")

    return success_count, total_attempted