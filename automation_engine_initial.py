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
# STOP FLAG REFERENCE
# ==========================================
# Automation_Tab sets this to True when the user clicks STOP.
# All blocking waits check it so they bail out immediately
# instead of waiting for their full timeout to expire.

def _is_stop_requested():
    """Check the tab's STOP_AUTOMATION flag without a hard import dependency."""
    try:
        from tabs.Automation_Tab import STOP_AUTOMATION
        return STOP_AUTOMATION
    except Exception:
        return False


# ==========================================
# STABILIZER
# ==========================================

def wait_for_stable(driver, timeout=20):
    """Wait for page readyState + jQuery idle.
    Bails out immediately if STOP_AUTOMATION is set."""
    if _is_stop_requested():
        return

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_stop_requested():
            return
        try:
            ready = driver.execute_script("return document.readyState") == "complete"
            jquery_idle = driver.execute_script(
                "return (window.jQuery ? jQuery.active == 0 : true)"
            )
            if ready and jquery_idle:
                break
        except Exception:
            break
        time.sleep(0.3)

    if not _is_stop_requested():
        time.sleep(0.5)


# ==========================================
# SCROLL TO TRIGGER LAZY LOADING
# ==========================================

def scroll_to_load_content(driver, scrolls=4, pause=0.8):
    """
    Scroll down incrementally to trigger lazy-loaded content (icons, images, charts).
    Called after every interaction that may cause new content to render.
    Scrolls back to top so the next interaction or snapshot starts from the beginning.
    """
    if _is_stop_requested():
        return
    try:
        for attempt in range(2):  # retry once if height changes mid-scroll
            total_height = driver.execute_script("return document.body.scrollHeight")
            if total_height == 0:
                break

            step = max(total_height // scrolls, 200)

            for i in range(1, scrolls + 1):
                if _is_stop_requested():
                    return
                driver.execute_script(f"window.scrollTo(0, {step * i});")
                time.sleep(pause)

            # Check if page grew during scroll (infinite scroll / dynamic content)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height <= total_height:
                break  # no new content loaded, no need to re-scroll

            logger.info("   ↕ Page grew during scroll — re-scrolling to capture new content.")

        # Always return to top so snapshot / next step starts from beginning
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.4)

    except Exception as e:
        logger.warning(f"⚠ Scroll failed: {e}")


# ==========================================
# SAFE PAGE INIT (MAIN-CONTROLLED DRIVER)
# ==========================================

def safe_initialize_page(driver, url, platform_name=None):
    if _is_stop_requested():
        return
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
        # Scroll after click so any newly rendered content
        # (panels, dropdowns, chart icons) is fully loaded into the DOM

def handle_input(driver, element, value):
    element.clear()
    if value:
        element.send_keys(value)
        element.send_keys(Keys.RETURN)
        wait_for_stable(driver)
        # Input submissions often trigger a full page/panel re-render
        scroll_to_load_content(driver)

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
        # Fire scroll after select — dropdowns often swap content panels
        # that only render icons/charts once they enter the viewport
        scroll_to_load_content(driver)
        return
    except Exception:
        pass

    click(driver, element)
    time.sleep(.5)
    option = driver.find_element(By.XPATH, f"//*[contains(text(), '{value}')]")
    click(driver, option)
    # click() already calls scroll_to_load_content internally

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
                return True
        except Exception:
            continue

    logger.warning(f"⚠ Could not find '{value}' in list")
    return False

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

    if mode == "setup" and param_type == "category":
        return True
    elif mode == "category" and param_type != "category":
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

    p_name = (platform_name or "").strip().lower()
    c_val = (country or "").strip().lower()
    is_sensortower = p_name in {"sensortower", "sensor tower"}

    is_us = (
        c_val in {
            "us", "usa", "u.s.", "u.s.a.",
            "united states", "united states of america"
        } or
        c_val.startswith("us ") or
        c_val.startswith("united states")
    )

    if is_sensortower and is_us and role == "button_country":
        logger.info("⏭️ Skipping 'button_country' click (SensorTower + US).")
        return True

    if is_sensortower and is_us and param_type == "country":
        logger.info("⏭️ Skipping 'country' list selection (SensorTower + US).")
        return True

    action_completed = False

    for attempt in range(1):
        if _is_stop_requested():
            logger.info(f"⏹️ Stop requested — skipping step: {role}")
            return False
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

            if is_sensortower and action_completed:
                logger.info(f"✔ Executed (with success marker): {role}")
                return True
            else:
                logger.info(f"✔ Executed: {role}")
                return True

        except Exception as e:
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
    existing_snapshots,
    extract_fn=None,
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

    for store in PLATFORM_ALIASES.keys():

        if _is_stop_requested():
            logger.warning("⏹️ Stop requested — aborting store loop.")
            break

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

        # ── Detect missing snapshots ──────────────────────────────────────
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

        if not missing_categories:
            logger.info(
                f"      ⏭️ All categories already exist — skipping {platform_name} {store.upper()}"
            )
            continue

        logger.info(
            f"      📌 Categories to process: {len(missing_categories)} / {len(categories)}"
        )

        # ── Initialize page ───────────────────────────────────────────────
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

        # ── Setup phase (once per store) ──────────────────────────────────
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

        # ── Category phase ────────────────────────────────────────────────
        logger.info(f"\n      🔄 CATEGORY PHASE")

        for cat_idx, category in enumerate(missing_categories, start=1):

            if _is_stop_requested():
                logger.warning("⏹️ Stop requested — aborting category loop.")
                break

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

            wait_for_stable(driver)

            # ── Save snapshot ─────────────────────────────────────────────
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

                # ── Scrape immediately after save ──────────────────────────
                if extract_fn is not None:
                    try:
                        _saved_path = str(execution_folder / f"{base_filename}.mhtml")
                        extract_fn(
                            saved_path=_saved_path,
                            platform_key=platform_config.get("name", platform_name.lower()),
                            country=country_data,
                            safe_category=safe_category,
                            execution_folder=execution_folder,
                        )
                    except Exception as _ex:
                        logger.warning(f"      ⚠ Scrape step failed for {base_filename}: {_ex}")
            else:
                logger.warning(f"      ⚠ Snapshot failed: {result}")

        logger.info(f"\n   ✅ Completed store: {store.upper()}")

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ COMPLETED COUNTRY: {country_code}")
    logger.info(f"   Successful snapshots: {success_count}/{total_attempted}")
    logger.info(f"{'='*60}")

    return success_count, total_attempted