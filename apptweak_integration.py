# apptweak_integration.py - Complete version with ALL methods
import time
from pathlib import Path
from selenium.webdriver.common.by import By
from datetime import datetime
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# Import from file_handlers.py
from file_handlers import save_mhtml_snapshot, create_base_filename

from logging_config import logger

# Import progress utilities
try:
    from utils.utils import print_progress, clean_category_name, get_next_sequence_number
    PROGRESS_AVAILABLE = True
    CLEAN_CATEGORY_AVAILABLE = True
except ImportError:
    print("⚠ Could not import print_progress from utils.py")
    PROGRESS_AVAILABLE = False
    CLEAN_CATEGORY_AVAILABLE = False

    def clean_category_name(category: str) -> str:
        return category.replace(' ', '_').replace('&', 'and').replace('/', '_')

try:
    from config import PLATFORM_CATEGORIES, DELAYS, APPTWEAK, COUNTRIES, TARGET_DIR
    CONFIG_AVAILABLE = True
    logger.info(f"✅ Successfully imported config settings")
    logger.info(f"   Found {len(COUNTRIES)} countries in config")
except ImportError as e:
    logger.info(f"⚠ Config import error: {e}")
    CONFIG_AVAILABLE = False
    PLATFORM_CATEGORIES = {"android": [], "apple": []}
    DELAYS = {}
    APPTWEAK = {}
    COUNTRIES = []


# ══════════════════════════════════════════════════════════════════════════════
# STOP FLAG
# ══════════════════════════════════════════════════════════════════════════════

def _is_stop_requested():
    try:
        from tabs.Automation_Tab import STOP_AUTOMATION
        return STOP_AUTOMATION
    except Exception:
        return False


def _sleep(seconds: float) -> bool:
    """
    Interruptible sleep — polls stop flag every 0.1 s.
    Returns True if stop was requested mid-sleep, False if completed fully.
    Usage:  if _sleep(3): return   ← bail immediately on stop
    """
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _is_stop_requested():
            return True
        time.sleep(0.1)
    return False


class AppTweakIntegration:
    def __init__(self, driver, execution_folder, sequence_counters=None, existing_snapshots=None,
                 extract_fn=None, used_slots=None, **kwargs):
        self.driver = driver
        self.execution_folder = execution_folder
        self.date_stamp = time.strftime("%Y%m%d")
        self.sequence_counters = sequence_counters if sequence_counters else {}
        self.existing_snapshots = existing_snapshots if existing_snapshots else set()
        self.extract_fn = extract_fn
        self.on_success = None
        self.on_fail = None
        self.used_slots = used_slots if used_slots is not None else {}

    def _country_key(self, country_data):
        return country_data.get("number", "00")

    def execute_apptweak_flow(self, country_data, web_platform):
        """
        Execute AppTweak automation for a specific country.
        Returns: (success_count, total_attempted)

        NOTE: Skipped (already-saved) categories are NOT included in
        total_attempted, so they never inflate the failed count in the
        caller's all_failed list.
        """
        logger.info(f"\n🎯 Starting AppTweak automation for {country_data['name']}")

        url = web_platform["base_url"]

        success_count   = 0
        total_attempted = 0

        platforms = [
            {"name": "Android", "store_name": "Play Store", "type": "android"},
            {"name": "Apple",   "store_name": "App Store",  "type": "apple"}
        ]

        # ── Pre-check all categories before loading the page ─────────────
        logger.info(f"  🔍 Pre-checking categories...")

        categories_to_process = []
        all_categories        = []

        for platform in platforms:
            if _is_stop_requested():
                logger.warning("⏹️ Stop requested — aborting AppTweak platform loop.")
                break

            platform_type = platform["type"]
            categories    = PLATFORM_CATEGORIES.get(platform_type, [])

            for category_name in categories:
                country_code  = country_data.get('code', '')
                app_platform  = platform_type.lower()
                safe_category = (
                    clean_category_name(category_name).lower()
                    if CLEAN_CATEGORY_AVAILABLE
                    else category_name.lower()
                        .replace(' ', '_').replace('&', 'and').replace('/', '_')
                )

                task_key = (country_code, "apptweak", app_platform, safe_category)
                all_categories.append((platform, platform_type, category_name, task_key))

                if task_key in self.existing_snapshots:
                    logger.info(f"    ⏭️ Skipping already saved: {task_key}")
                else:
                    categories_to_process.append(
                        (platform, platform_type, category_name, task_key)
                    )

        total_categories = len(all_categories)
        to_process_count = len(categories_to_process)
        to_skip_count    = total_categories - to_process_count

        logger.info(f"  📊 Summary:")
        logger.info(f"    Total categories : {total_categories}")
        logger.info(f"    Already saved    : {to_skip_count}")
        logger.info(f"    To process       : {to_process_count}")

        if to_process_count == 0:
            logger.info(f"  ✅ All categories already processed — skipping webpage load")
            # Return (0, 0) — nothing was attempted, nothing failed
            return 0, 0

        if _is_stop_requested():
            logger.warning("⏹️ Stop requested — skipping AppTweak page load.")
            return 0, 0

        logger.info(f"  🌐 Loading AppTweak page ({to_process_count} categories to process)...")
        logger.info(f"  URL: {url}")

        try:
            self.driver.get(url)

            wait_time = APPTWEAK.get("wait_times", {}).get("page_load", 3)
            if _sleep(wait_time): return 0, 0

            from Web_validators import handle_platform_cookies
            handle_platform_cookies(self.driver, "apptweak")
            if _sleep(2): return 0, 0

            logger.info("  🔄 Refreshing page...")
            self.driver.refresh()
            if _sleep(4): return 0, 0

            handle_platform_cookies(self.driver, "apptweak")
            if _sleep(2): return 0, 0

            current_category = 0

            for idx, (platform, platform_type, category_name, task_key) in \
                    enumerate(categories_to_process, 1):

                if _is_stop_requested():
                    logger.warning("⏹️ Stop requested — aborting AppTweak category loop.")
                    break

                current_category += 1
                total_attempted  += 1  # Only incremented for genuinely attempted categories

                if PROGRESS_AVAILABLE:
                    print_progress(idx, len(categories_to_process),
                                   "  Processing AppTweak categories")

                logger.info(
                    f"  [{idx}/{len(categories_to_process)}] "
                    f"{platform_type.upper()} - {category_name}"
                )
                logger.info(f"\n  📱 Processing {platform['name']} - {category_name}")
                logger.info(f"    📂 Category {current_category}/{to_process_count}")

                if not self.click_edit_hyperlink():
                    logger.info("    ⚠ Could not open modal — skipping...")
                    continue

                if _sleep(1): break

                sequence_number = get_next_sequence_number(country_data, self.sequence_counters, self.used_slots)

                if self.configure_modal(
                    platform["store_name"], country_data["name"],
                    category_name, platform_type
                ):
                    if self.click_save_button():
                        base_filename = create_base_filename(
                            country=country_data,
                            sequence=sequence_number,
                            web_platform={"name": "AppTweak"},
                            app_platform=platform_type,
                            category=category_name,
                            date_stamp=self.date_stamp,
                        )

                        success, result = save_mhtml_snapshot(
                            driver=self.driver,
                            base_filename=base_filename,
                            folder_path=self.execution_folder,
                        )

                        if success:
                            success_count += 1
                            self.existing_snapshots.add(task_key)
                            logger.info(f"\n    ✅ Successfully saved: {result}")

                            if self.on_success:
                                self.on_success()

                            if self.extract_fn is not None:
                                try:
                                    _saved_path = str(
                                        self.execution_folder / f"{base_filename}.mhtml"
                                    )
                                    self.extract_fn(
                                        saved_path=_saved_path,
                                        execution_folder=self.execution_folder,
                                    )
                                except Exception as _ex:
                                    logger.warning(
                                        f"    ⚠ Extract failed for {base_filename}: {_ex}"
                                    )
                        else:
                            logger.info(f"\n    ⚠ Failed to save snapshot: {result}")
                            if self.on_fail:
                                self.on_fail("MHTML save failed")
                    else:
                        logger.info(f"\n    ⚠ Failed to save configuration: {category_name}")
                else:
                    logger.info(f"\n    ⚠ Failed to configure modal: {category_name}")

                if current_category < to_process_count:
                    delay = DELAYS.get("apptweak_category_delay", 3)
                    if _sleep(delay): break

            logger.info(f"\n  📊 AppTweak results for {country_data['name']}:")
            logger.info(f"    Total categories : {total_categories}")
            logger.info(f"    Skipped          : {to_skip_count}")
            logger.info(f"    Attempted        : {total_attempted}")
            logger.info(f"    Successful       : {success_count}")

            if total_attempted > 0:
                logger.info(
                    f"    Success rate     : "
                    f"{success_count / total_attempted * 100:.1f}%"
                )

            # Return only attempted counts — skips are invisible to the caller
            return success_count, total_attempted

        except Exception as e:
            logger.error(f"  ❌ Error in AppTweak automation: {e}")
            import traceback
            traceback.print_exc()
            return 0, 0

    # ── Modal interaction helpers ─────────────────────────────────────────

    def click_edit_hyperlink(self):
        """Click the edit hyperlink on AppTweak using config selector."""
        selector = APPTWEAK.get("modal_selectors", {}).get(
            "edit_link", "a.js-change-column[data-column-position='0']"
        )
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
            self.driver.execute_script("arguments[0].click();", element)
            time.sleep(APPTWEAK.get("wait_times", {}).get("modal_open", 2))
            return True
        except Exception:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, "a.js-change-column")
                for element in elements:
                    if element.is_displayed():
                        self.driver.execute_script("arguments[0].click();", element)
                        time.sleep(2)
                        return True
            except Exception:
                pass
            return False

    def configure_modal(self, store_name, country_name, category_name, platform_type):
        """Configure the modal with store, country, and category."""
        try:
            if not self.select_store(store_name, platform_type):
                return False
            time.sleep(0.5)
            if not self.select_country(country_name):
                return False
            time.sleep(0.5)
            if not self.select_category(category_name, platform_type):
                return False
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.info(f"      Error configuring modal: {str(e)[:100]}")
            return False

    def select_store(self, store_name, platform_type):
        """Select store dropdown using config selector."""
        selector = APPTWEAK.get("modal_selectors", {}).get("store_dropdown", ".stores")
        try:
            dropdown = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            dropdown.click()
            time.sleep(0.3)
            select = Select(dropdown)
            try:
                select.select_by_visible_text(store_name)
            except Exception:
                try:
                    select.select_by_value(platform_type)
                except Exception:
                    select.select_by_index(1 if store_name == "Play Store" else 0)
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.info(f"        Error selecting store: {str(e)[:100]}")
            return False

    def select_country(self, country_name):
        """Select a specific country from the countries dropdown."""
        print(f"         🌍 Selecting country: {country_name}")
        try:
            countries_dropdown = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".countries"))
            )
            countries_dropdown.click()
            time.sleep(0.5)
            select = Select(countries_dropdown)

            try:
                select.select_by_visible_text(country_name)
                print(f"            ✅ Country selected: {country_name}")
                time.sleep(0.5)
                return True
            except Exception:
                for option in select.options:
                    if country_name.lower() in option.text.lower():
                        option.click()
                        print(f"            ✅ Country selected (partial): {option.text}")
                        time.sleep(0.5)
                        return True

                variations = {
                    "United Arab Emirate": ["United Arab Emirates", "UAE", "Emirates"],
                    "South Korea":         ["Korea, Republic Of", "Korea Republic", "Korea"],
                    "United Kingdom":      ["UK", "Great Britain", "Britain"],
                    "China":               ["China mainland", "Mainland China", "China (Mainland)"],
                    "Hong Kong":           ["Hong Kong SAR", "Hong Kong SAR China"],
                    "Taiwan":              ["Taiwan, Province of China", "Taiwan Province of China"],
                }
                for variation in variations.get(country_name, []):
                    try:
                        select.select_by_visible_text(variation)
                        print(f"            ✅ Country selected (variation): {variation}")
                        return True
                    except Exception:
                        continue

            logger.info(f"            ❌ Could not find country: {country_name}")
            return False

        except Exception as e:
            logger.info(f"            ❌ Error selecting country: {e}")
            return False

    def select_category(self, category_name, platform_type):
        """Select category dropdown using config selector."""
        selector = APPTWEAK.get("modal_selectors", {}).get(
            "category_dropdown", ".categories"
        )
        try:
            dropdown = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            dropdown.click()
            time.sleep(0.3)
            select = Select(dropdown)
            try:
                select.select_by_visible_text(category_name)
                print(f"        ✅ Selected category: {category_name}")
            except Exception:
                selected = False
                for option in select.options:
                    if category_name.lower() in option.text.lower():
                        option.click()
                        print(f"        ✅ Selected category (partial): {option.text}")
                        selected = True
                        break
                if not selected:
                    logger.info(f"        ❌ Category '{category_name}' not found")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.info(f"    Error selecting category: {str(e)[:100]}")
            return False

    def click_save_button(self):
        """Click save button using config selector."""
        selector = APPTWEAK.get("modal_selectors", {}).get(
            "save_button", ".js-top-charts-change-column-btn.btn"
        )
        try:
            save_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            save_button.click()
            time.sleep(APPTWEAK.get("wait_times", {}).get("after_save", 2))
            return True
        except Exception:
            return False