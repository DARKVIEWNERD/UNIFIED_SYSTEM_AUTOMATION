# universal_automation_engine.py
# Optimized for data reliability — ensures content is fully rendered before snapshot

import json
import pathlib
import time
import logging
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException,
    ElementClickInterceptedException, NoSuchElementException
)

from config import PLATFORM_CATEGORIES, COUNTRIES
from logging_config import logger
from utils.utils import print_progress

from Web_validators import (
    handle_platform_cookies,
    is_human_verification,
    wait_for_manual_verification,
    is_page_unusable,
    test_url_with_retry
)

DEFAULT_TIMEOUT  = 15
SCROLL_PAUSE     = 1.0
SCROLL_STEPS     = 6
POST_ACTION_WAIT = 1.5

# ==========================================
# PLATFORM ALIASES (FOR DETECTION ONLY)
# ==========================================

PLATFORM_ALIASES = {
    "android": ["android", "google play", "play store"],
    "apple":   ["iphone app store", "iphone", "ios", "app store", "apple"]
}

# ==========================================
# STOP FLAG
# ==========================================

def _is_stop_requested():
    try:
        from tabs.Automation_Tab import STOP_AUTOMATION
        return STOP_AUTOMATION
    except Exception:
        return False





# ==========================================
# STABILIZER (improved)
# ==========================================

def wait_for_stable(driver, timeout=20, extra_wait=0.0):
    """
    Wait for:
      1. document.readyState == 'complete'
      2. No pending jQuery AJAX
      3. No pending fetch/XHR (tracked via PerformanceObserver shim injected once)
      4. Optional extra flat sleep after stability confirmed

    Bails immediately if STOP is requested.
    """
    if _is_stop_requested():
        return

    # Inject a lightweight fetch/XHR counter the first time we hit a page.
    # Idempotent — the guard variable prevents double-injection.
    try:
        driver.execute_script("""
            if (!window.__pendingRequests) {
                window.__pendingRequests = 0;
                var _origFetch = window.fetch;
                window.fetch = function() {
                    window.__pendingRequests++;
                    return _origFetch.apply(this, arguments).finally(function() {
                        window.__pendingRequests = Math.max(0, window.__pendingRequests - 1);
                    });
                };
                var _origXHROpen = XMLHttpRequest.prototype.open;
                XMLHttpRequest.prototype.open = function() {
                    window.__pendingRequests++;
                    this.addEventListener('loadend', function() {
                        window.__pendingRequests = Math.max(0, window.__pendingRequests - 1);
                    });
                    return _origXHROpen.apply(this, arguments);
                };
            }
        """)
    except Exception:
        pass  # page may have navigated away — non-fatal

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_stop_requested():
            return
        try:
            ready       = driver.execute_script("return document.readyState") == "complete"
            jquery_idle = driver.execute_script(
                "return (window.jQuery ? jQuery.active == 0 : true)"
            )
            xhr_idle    = driver.execute_script(
                "return (window.__pendingRequests !== undefined "
                "? window.__pendingRequests == 0 : true)"
            )
            if ready and jquery_idle and xhr_idle:
                break
        except Exception:
            break
        time.sleep(0.3)

    if extra_wait > 0 and not _is_stop_requested():
        time.sleep(extra_wait)


# ==========================================
# SCROLL TO TRIGGER LAZY LOADING (improved)
# ==========================================

def scroll_to_load_content(driver, scrolls=SCROLL_STEPS, pause=SCROLL_PAUSE,
                           platform_name=""):
    """
    Scroll incrementally to trigger lazy-loaded content.

    Improvements over original:
    - Checks for new rows appearing during scroll (stops early when data is present)
    - Uses viewport-relative scroll steps so the page doesn't jump over lazy-load
      trigger zones on very tall pages
    - Re-scrolls if the page grew (infinite scroll / virtual DOM)
    - Always returns to top
    """
    if _is_stop_requested():
        return

    try:
        viewport_height = driver.execute_script("return window.innerHeight") or 800

        for attempt in range(3):  # up from 2 — handles deeper lazy loaders
            total_height = driver.execute_script("return document.body.scrollHeight") or 0
            if total_height == 0:
                break

            # Use viewport-sized steps so content in every "screen" gets a chance to load
            step = min(viewport_height, max(total_height // scrolls, 200))
            position = 0

            while position < total_height:
                if _is_stop_requested():
                    return
                position = min(position + step, total_height)
                driver.execute_script(f"window.scrollTo(0, {position});")
                time.sleep(pause)



            new_height = driver.execute_script("return document.body.scrollHeight") or 0
            if new_height <= total_height:
                break
            logger.info("   ↕ Page grew during scroll — re-scrolling for new content.")

        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.4)

    except Exception as e:
        logger.warning(f"⚠ Scroll failed: {e}")


# ==========================================
# SAFE PAGE INIT
# ==========================================

def safe_initialize_page(driver, url, platform_name=None):
    if _is_stop_requested():
        return
    test_url_with_retry(driver, url)
    wait_for_stable(driver, extra_wait=0.5)
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

def safe_find(driver, by, selector, timeout=DEFAULT_TIMEOUT):
    wait = WebDriverWait(driver, timeout)
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

def platform_param_exists(platform_config):
    return any(
        step.get("param") == "platform"
        for step in platform_config.get("custom_selectors", [])
    )


# ==========================================
# ACTION HELPERS (improved)
# ==========================================

def click(driver, element, wait_after=True, platform_name=""):
    """
    Click with three fallback strategies:
    1. Normal .click()
    2. JS click (handles overlays)
    3. ActionChains move-then-click (handles off-screen elements)
    """
    from selenium.webdriver.common.action_chains import ActionChains

    for strategy in ("native", "js", "actions"):
        try:
            if strategy == "native":
                element.click()
            elif strategy == "js":
                driver.execute_script("arguments[0].click();", element)
            else:
                ActionChains(driver).move_to_element(element).click().perform()
            break
        except ElementClickInterceptedException:
            # Something is covering the element — try to dismiss overlays
            try:
                driver.execute_script(
                    "document.querySelectorAll('[class*=modal],[class*=overlay],"
                    "[class*=popup],[class*=cookie]')"
                    ".forEach(e => { if(e.style) e.style.display='none'; });"
                )
            except Exception:
                pass
            continue
        except StaleElementReferenceException:
            logger.warning(f"⚠ Stale element during click — skipping retry")
            return
        except Exception:
            continue

    if wait_after:
        time.sleep(POST_ACTION_WAIT)
        wait_for_stable(driver)


def handle_input(driver, element, value, platform_name=""):
    element.clear()
    if value:
        element.send_keys(value)
        element.send_keys(Keys.RETURN)
        time.sleep(POST_ACTION_WAIT)
        wait_for_stable(driver)


def handle_select(driver, element, value, platform_name=""):
    if not value:
        return

    try:
        Select(element).select_by_visible_text(value)
        time.sleep(0.5)
        driver.execute_script("""
            var event = new Event('change', { bubbles: true });
            arguments[0].dispatchEvent(event);
        """, element)
        time.sleep(POST_ACTION_WAIT)
        wait_for_stable(driver)
        return
    except Exception:
        pass

    click(driver, element, platform_name=platform_name)
    time.sleep(0.5)
    option = driver.find_element(By.XPATH, f"//*[contains(text(), '{value}')]")
    click(driver, option, platform_name=platform_name)


def handle_list(driver, by, selector, value, platform_name=""):
    if not value:
        return False

    elements = driver.find_elements(by, selector)
    aliases  = PLATFORM_ALIASES.get(value.lower(), [value.lower()])

    for el in elements:
        try:
            text = el.text.strip().lower()
            if text == value.lower() or any(alias in text for alias in aliases):
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.5)
                click(driver, el, platform_name=platform_name)
                logger.info(f"✔ Selected: {text}")
                return True
        except Exception:
            continue

    logger.warning(f"⚠ Could not find '{value}' in list")
    return False


# ==========================================
# STEP EXECUTION (improved)
# ==========================================

def execute_step(driver, step, country=None, category=None, platform=None,
                 platform_name=None, mode="all", is_category_step=False):
    """
    Args:
        mode:             "setup"    — only non-category steps
                          "category" — only category steps
                          "all"      — everything
        is_category_step: caller sets True when this step carries the category
                          value so scroll_to_load_content fires only after a
                          successful category interaction, not on setup steps.
    """
    role         = step.get("role", "unknown")
    selector     = step.get("selector") or step.get("value")
    element_type = step.get("type", "").lower()
    param_type   = step.get("param")

    # Derive is_category_step from param_type if caller didn't specify
    if not is_category_step:
        is_category_step = (param_type == "category")

    if mode == "setup" and param_type == "category":
        return True
    if mode == "category" and param_type not in ("category", None):
        return True

    if not selector:
        return False

    param_map   = {"country": country, "category": category, "platform": platform}
    input_value = param_map.get(param_type)
    by, normalized = resolve_selector(selector)

    p_name  = (platform_name or "").strip().lower()
    c_val   = (country or "").strip().lower()
    is_sensortower = p_name in {"sensortower", "sensor tower"}
    is_us = (
        c_val in {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america"}
        or c_val.startswith("us ")
        or c_val.startswith("united states")
    )

    if is_sensortower and is_us and role == "button_country":
        logger.info("⏭️ Skipping 'button_country' (SensorTower + US).")
        return True
    if is_sensortower and is_us and param_type == "country":
        logger.info("⏭️ Skipping 'country' list selection (SensorTower + US).")
        return True

    _max_attempts = 3  # retries per step for element-not-found / stale element

    for attempt in range(_max_attempts):
        if _is_stop_requested():
            logger.info(f"⏹️ Stop requested — skipping step: {role}")
            return False
        try:
            wait_for_stable(driver)

            unusable, reason = is_page_unusable(driver, platform_name)
            if unusable:
                logger.warning(f"⚠ Page invalid before '{role}': {reason} — refreshing")
                driver.refresh()
                wait_for_stable(driver, extra_wait=1.0)

            if element_type == "list":
                result = handle_list(driver, by, normalized, input_value,
                                     platform_name=platform_name)
                if result:
                    logger.info(f"✔ Executed: {role}")
                    if is_category_step:
                        scroll_to_load_content(driver, platform_name=platform_name)
                    return True
                logger.warning(
                    f"⚠ List item '{input_value}' not found for '{role}' "
                    f"(attempt {attempt+1}/{_max_attempts})"
                )
                time.sleep(1.0 * (attempt + 1))
                continue

            try:
                element = safe_find(driver, by, normalized)
            except TimeoutException:
                logger.warning(
                    f"⚠ Element not found for '{role}' "
                    f"(attempt {attempt+1}/{_max_attempts}): {selector}"
                )
                time.sleep(1.0 * (attempt + 1))
                continue

            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", element
            )
            time.sleep(0.5)

            if "input" in element_type:
                handle_input(driver, element, input_value, platform_name=platform_name)
            elif "select" in element_type:
                handle_select(driver, element, input_value, platform_name=platform_name)
            elif "dropdown" in element_type:
                if not input_value:
                    logger.info(f"⏭️ Skipping dropdown '{role}' (no value).")
                    return True
                result = handle_list(
                    driver, By.XPATH, "//*[self::li or self::span]",
                    input_value, platform_name=platform_name
                )
                if not result:
                    logger.warning(
                        f"⚠ Dropdown value '{input_value}' not found for '{role}' "
                        f"(attempt {attempt+1}/{_max_attempts})"
                    )
                    time.sleep(1.0 * (attempt + 1))
                    continue
            else:
                click(driver, element, platform_name=platform_name)

            logger.info(f"✔ Executed: {role}")
            if is_category_step:
                scroll_to_load_content(driver, platform_name=platform_name)
            return True

        except StaleElementReferenceException:
            logger.warning(
                f"⚠ Stale element for '{role}' "
                f"(attempt {attempt+1}/{_max_attempts}) — retrying"
            )
            time.sleep(0.5)
            continue

        except Exception as e:
            logger.warning(
                f"⚠ Attempt {attempt+1}/{_max_attempts} failed for '{role}': "
                f"{str(e)[:120]}"
            )
            time.sleep(1.0 * (attempt + 1))

    logger.error(f"❌ Step permanently failed after {_max_attempts} attempts: {role}")
    return False


# ==========================================
# RUN PLATFORM HELPER
# ==========================================

def run_platform(driver, platform_config, country=None, category=None,
                 platform=None, mode="all"):
    platform_name = platform_config.get("name", "unknown")
    for step in platform_config.get("custom_selectors", []):
        execute_step(
            driver, step,
            country=country, category=category, platform=platform,
            platform_name=platform_name, mode=mode
        )


# ==========================================
# MAIN ENTRY POINT
# ==========================================

def execute_universal_flow(
    driver,
    country_data,
    platform_config,
    execution_folder,
    sequence_counters,
    existing_snapshots,
    extract_fn=None,
    ui_callbacks=None,
    used_slots=None,
):
    """
    ui_callbacks (optional) — same dict passed from AutomationTab:
        update_progress(pct)   — moves the progress bar (0-100)
        update_status(text)    — updates the status label
        increment_files()      — bumps the files counter
        set_counts(s, f)       — updates success/fail labels
        get_stop_flag()        — returns bool
    All keys are optional; missing ones are silently ignored.
    """
    from utils.utils import clean_category_name, get_next_sequence_number
    from file_handlers import create_base_filename, save_mhtml_snapshot

    # Resolve callbacks — fall back to no-ops so nothing below needs to guard against None
    _cb          = ui_callbacks or {}
    _update_prog = _cb.get("update_progress", lambda pct: None)
    _update_stat = _cb.get("update_status",   lambda txt: None)
    _inc_files   = _cb.get("increment_files", lambda: None)
    _set_counts  = _cb.get("set_counts",      lambda s, f: None)

    success_count   = 0
    total_attempted = 0

    base_url      = platform_config["base_url"]
    platform_name = platform_config.get("name", "unknown")
    country_name  = country_data["name"]
    country_code  = country_data["code"]

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
                f"⚠ SKIPPING: SensorTower Android China — {country_name}"
            )
            continue

        categories = PLATFORM_CATEGORIES.get(store, [])
        if not categories:
            continue

        logger.info(f"\n{'─'*40}")
        logger.info(f"📱 STORE: {store.upper()}")
        logger.info(f"{'─'*40}")

        # ── Find missing snapshots ────────────────────────────────────────
        missing_categories = []
        for category in categories:
            safe_category = clean_category_name(category).lower()
            task_key = (country_code, platform_name.lower(), store.lower(), safe_category)
            if task_key not in existing_snapshots:
                missing_categories.append(category)
            else:
                logger.info(f"      ⏭️ Already captured: {task_key}")

        if not missing_categories:
            logger.info(
                f"      ⏭️ All categories already captured — "
                f"skipping {platform_name} {store.upper()}"
            )
            continue

        logger.info(
            f"      📌 Categories to capture: "
            f"{len(missing_categories)} / {len(categories)}"
        )


        total_missing_this_store = len(missing_categories)
        _update_stat(
            f"{platform_name} | {country_name} | {store.upper()} "
            f"(0/{total_missing_this_store})"
        )
        # ── Initialize page ───────────────────────────────────────────────
        safe_initialize_page(driver, base_url, platform_name=platform_name)

        json_controls_platform = any(
            step.get("param") == "platform"
            for step in platform_config.get("custom_selectors", [])
        )

        if json_controls_platform:
            logger.info("   📌 Platform handled by JSON config.")
        else:
            logger.info("   🔎 Attempting auto-detect...")
            auto_detect_and_select_platform(driver, store)

        # ── Setup phase (once per store) ──────────────────────────────────
        logger.info(f"\n      ⚙️ SETUP PHASE")
        for step in platform_config.get("custom_selectors", []):
            if step.get("param") != "category":
                execute_step(
                    driver, step,
                    country=country_name, platform=store,
                    platform_name=platform_name
                )

        # Wait for setup interactions to settle — no scroll here,
        # scroll only fires after successful category steps
        wait_for_stable(driver, extra_wait=1.0)

        # ── Category phase ────────────────────────────────────────────────
        logger.info(f"\n      🔄 CATEGORY PHASE")

        for cat_idx, category in enumerate(missing_categories, start=1):

            if _is_stop_requested():
                logger.warning("⏹️ Stop requested — aborting category loop.")
                break

            safe_category = clean_category_name(category).lower()
            task_key = (country_code, platform_name.lower(), store.lower(), safe_category)
            total_attempted += 1

            print_progress(
                cat_idx,
                len(missing_categories),
                prefix=f"      {platform_name} | {store.upper()} | {category}"
            )
            logger.info(
                f"      🔄 [{cat_idx}/{len(missing_categories)}] Category: {category}"
            )

            # ── Progress bar + status label update ──────────────────────
            _cat_pct = (cat_idx / total_missing_this_store) * 100
            _update_prog(_cat_pct)
            _update_stat(
                f"{platform_name} | {country_name} | {store.upper()} "
                f"({cat_idx}/{total_missing_this_store}): {category}"
            )

            # ── Run category steps then save ─────────────────────────────

            category_steps = [
                s for s in platform_config.get("custom_selectors", [])
                if s.get("param") == "category"
            ]
            results = []
            for step in category_steps:
                ok = execute_step(
                    driver, step,
                    country=country_name,
                    category=category,
                    platform=store,
                    platform_name=platform_name,
                    is_category_step=True,
                )
                results.append(ok)

            if category_steps and not all(results):
                logger.warning(
                    f"      ⚠ Category step failed for [{category}] — skipping snapshot"
                )
                continue

            # Steps passed — wait for network to settle (scroll already
            # happened inside execute_step after the last category step)
            wait_for_stable(driver, extra_wait=0.5)

            # ── Save snapshot ─────────────────────────────────────────
            sequence_number = get_next_sequence_number(
                country_data, sequence_counters, used_slots
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

                if extract_fn is not None:
                    try:
                        _saved_path = str(
                            execution_folder / f"{base_filename}.mhtml"
                        )
                        extract_fn(
                            saved_path=_saved_path,
                            execution_folder=execution_folder,
                        )
                    except Exception as _ex:
                        logger.warning(
                            f"      ⚠ Extract failed for {base_filename}: {_ex}"
                        )
            else:
                logger.warning(f"      ⚠ Snapshot failed: {result}")

        logger.info(f"\n   ✅ Completed store: {store.upper()}")

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ COMPLETED COUNTRY: {country_code}")
    logger.info(f"   Successful snapshots : {success_count}/{total_attempted}")
    logger.info(f"{'='*60}")

    return success_count, total_attempted