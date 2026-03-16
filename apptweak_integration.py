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

    
    # Fallback clean_category_name
    def clean_category_name(category: str) -> str:
        return category.replace(' ', '_').replace('&', 'and').replace('/', '_')

# ✅ IMPORT DIRECTLY FROM CONFIG - INCLUDING COUNTRIES
try:
    from config import PLATFORM_CATEGORIES, DELAYS, APPTWEAK, COUNTRIES, TARGET_DIR
    CONFIG_AVAILABLE = True
    logger.info(f"✅ Successfully imported config settings")
    logger.info(f"   Found {len(COUNTRIES)} countries in config")
except ImportError as e:
    logger.info(f"⚠ Config import error: {e}")
    CONFIG_AVAILABLE = False
    # Define minimal defaults
    PLATFORM_CATEGORIES = {"android": [], "apple": []}
    DELAYS = {}
    APPTWEAK = {}
    COUNTRIES = []


class AppTweakIntegration:
    def __init__(self, driver, execution_folder, sequence_counters=None, existing_snapshots=None,
                 extract_fn=None, **kwargs):
        """
        Initialize AppTweakIntegration.

        Args:
            extract_fn: Optional callable with signature
                        extract_fn(saved_path, platform_key, country, safe_category, execution_folder)
                        Called immediately after every successful MHTML save so that
                        scraping happens in-line rather than in a post-hoc batch.
        """
        self.driver = driver
        self.execution_folder = execution_folder
        self.date_stamp = time.strftime("%Y%m%d")
        self.sequence_counters = sequence_counters if sequence_counters else {}
        self.existing_snapshots = existing_snapshots if existing_snapshots else set()
        self.extract_fn = extract_fn  # ← scrape hook injected from automation_runner

   
    def _country_key(self, country_data):
        # Use the same key 'number' the main flow uses
        return country_data.get("number", "00")


    def execute_apptweak_flow(self, country_data,web_platform):
        """
        Execute AppTweak automation for a specific country
        Returns: (success_count, total_count)
        """
        logger.info(f"\n🎯 Starting AppTweak automation for {country_data['name']}")
        
        # ✅ Get URL from config
        url = web_platform["base_url"]
        
        success_count = 0
        total_attempted = 0
        
        # Process both platforms for this country
        platforms = [
            {"name": "Android", "store_name": "Play Store", "type": "android"},
            {"name": "Apple", "store_name": "App Store", "type": "apple"}
        ]
        
        # ============================================
        # ✅ STEP 1: PRE-CHECK ALL CATEGORIES FIRST (BEFORE LOADING PAGE)
        # ============================================
        logger.info(f"  🔍 Pre-checking categories...")
        
        categories_to_process = []  # Only these need processing
        all_categories = []  # All categories for this country
        
        for platform in platforms:
            platform_type = platform["type"]
            categories = PLATFORM_CATEGORIES.get(platform_type, [])
            
            for category_name in categories:
                # Create task_key - SAME FORMAT AS MAIN.PY
                country_code = country_data.get('code', '').upper()
                web_platform = "apptweak"
                app_platform = platform_type.lower()
                
                # Use clean_category_name if available
                if CLEAN_CATEGORY_AVAILABLE:
                    safe_category = clean_category_name(category_name).lower()
                else:
                    safe_category = category_name.lower().replace(' ', '_').replace('&', 'and').replace('/', '_')
                
                task_key = (country_code, web_platform, app_platform, safe_category)
                all_categories.append((platform, platform_type, category_name, task_key))
                
                # Check if should skip
                if task_key in self.existing_snapshots:
                    logger.info(f"    ⏭️ Skipping already saved: {task_key}")
                else:
                    categories_to_process.append((platform, platform_type, category_name, task_key))
        
        total_categories = len(all_categories)
        to_process_count = len(categories_to_process)
        to_skip_count = total_categories - to_process_count

        logger.info(f"  📊 Summary:")
        logger.info(f"    Total categories: {total_categories}")
        logger.info(f"    Already saved: {to_skip_count}")
        logger.info(f"    To process: {to_process_count}")
        
        # ============================================
        # ✅ STEP 2: ONLY LOAD WEBPAGE IF THERE'S WORK TO DO
        # ============================================
        if to_process_count == 0:
            logger.info(f"  ✅ All categories already processed, skipping webpage load")
            return 0, total_categories  # No files created, all were already done
        
        logger.info(f"  🌐 Loading AppTweak page (processing {to_process_count} categories)...")
        logger.info(f"  URL: {url}")
        
        try:
            # Load AppTweak page ONLY IF needed
            self.driver.get(url)
            
            # ✅ Use config wait time
            wait_time = APPTWEAK.get("wait_times", {}).get("page_load", 3)
            time.sleep(wait_time)
            
            # Handle cookies
            from Web_validators import handle_platform_cookies
            
            handle_platform_cookies(self.driver, "apptweak")
            time.sleep(2)
            
            # Refresh page once
            logger.info("  🔄 Refreshing page...")
            self.driver.refresh()
            time.sleep(4)
            
            # Handle any cookies that reappear
            handle_platform_cookies(self.driver, "apptweak")
            time.sleep(2)
            
            current_category = 0
            
            # ============================================
            # ✅ STEP 3: PROCESS ONLY WHAT'S NEEDED
            # ============================================
            for idx, (platform, platform_type, category_name, task_key) in enumerate(categories_to_process, 1):
                current_category += 1
                total_attempted += 1
                    
                # ✅ ADD THIS - Progress bar like main.py
                if PROGRESS_AVAILABLE:
                    print_progress(idx, len(categories_to_process), f"  Processing AppTweak categories")
                
                # ✅ CHANGE THIS - Match main.py format
                logger.info(f"  [{idx}/{len(categories_to_process)}] {platform_type.upper()} - {category_name}")
                    
                logger.info(f"\n  📱 Processing {platform['name']} - {category_name}")
                logger.info(f"    📂 Category {current_category}/{to_process_count}")
            
                # Click edit hyperlink using config selector
                if not self.click_edit_hyperlink():
                    logger.info("    ⚠ Could not open modal, skipping...")
                    continue
                
                time.sleep(1)
                
                # ✅ Get sequence number
                sequence_number = get_next_sequence_number(country_data, self.sequence_counters)
                
             
                
                # Configure the modal
                if self.configure_modal(platform["store_name"], country_data["name"], category_name, platform_type):
                    # Save the configuration
                    if self.click_save_button():
                        # Create base filename
                        base_filename = create_base_filename(
                            country=country_data,
                            sequence=sequence_number,
                            web_platform={"name": "AppTweak"},
                            app_platform=platform_type,
                            category=category_name,
                            date_stamp=self.date_stamp
                        )
                        
                        # Save snapshot
                        success, result = save_mhtml_snapshot(
                            driver=self.driver,
                            base_filename=base_filename,
                            folder_path=self.execution_folder
                        )
                        
                        if success:
                            success_count += 1
                            # ✅ ADD TO EXISTING_SNAPSHOTS ON SUCCESS
                            self.existing_snapshots.add(task_key)
                            logger.info(f"\n    ✅ Successfully saved: {result}")

                            # ── Scrape immediately after save ──────────────
                            if self.extract_fn is not None:
                                try:
                                    _saved_path = str(
                                        self.execution_folder / f"{base_filename}.mhtml"
                                    )
                                    # task_key[3] is the safe_category string
                                    self.extract_fn(
                                        saved_path=_saved_path,
                                        platform_key="apptweak",
                                        country=country_data,
                                        safe_category=task_key[3],
                                        execution_folder=self.execution_folder,
                                    )
                                except Exception as _ex:
                                    logger.warning(
                                        f"    ⚠ Scrape step failed for {base_filename}: {_ex}"
                                    )
                        else:
                            logger.info(f"\n    ⚠ Failed to save snapshot: {result}")
                    else:
                        logger.info(f"\n    ⚠ Failed to save configuration: {category_name}")
                else:
                    logger.info(f"\n    ⚠ Failed to configure modal: {category_name}")
                
                # Wait before next category
                if current_category < to_process_count:
                    delay = DELAYS.get("apptweak_category_delay", 3)
                    time.sleep(delay)
            
            logger.info(f"\n  📊 AppTweak results for {country_data['name']}:")
            logger.info(f"    Total categories: {total_categories}")
            logger.info(f"    Skipped: {to_skip_count}")
            logger.info(f"    Attempted: {total_attempted}")
            logger.info(f"    Successful: {success_count}")
            
            if total_attempted > 0:
                success_rate = (success_count / total_attempted) * 100
                logger.info(f"    Success rate: {success_rate:.1f}%")
            
            return success_count, total_categories
            
        except Exception as e:
            logger.info(f"  ❌ Error in AppTweak automation: {str(e)[:100]}")
            import traceback
            traceback.print_exc()
            return 0, total_categories
    
    # ============================================
    # ✅ ALL THE MISSING METHODS - ADD THESE BACK!
    # ============================================
    
    def click_edit_hyperlink(self):
        """Click the edit hyperlink on AppTweak using config selector"""
        selector = APPTWEAK.get("modal_selectors", {}).get(
            "edit_link", 
            "a.js-change-column[data-column-position='0']"
        )
        
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            self.driver.execute_script("arguments[0].click();", element)
            
            wait = APPTWEAK.get("wait_times", {}).get("modal_open", 2)
            time.sleep(wait)
            return True
            
        except:
            # Try fallback
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, "a.js-change-column")
                for element in elements:
                    if element.is_displayed():
                        self.driver.execute_script("arguments[0].click();", element)
                        time.sleep(2)
                        return True
            except:
                pass    
            
            return False
    
    def configure_modal(self, store_name, country_name, category_name, platform_type):
        """Configure the modal with store, country, and category using config selectors"""
        try:
            # Select store
            if not self.select_store(store_name, platform_type):
                return False
            
            time.sleep(0.5)
            
            # Select country
            if not self.select_country(country_name):
                return False
            
            time.sleep(0.5)
            
            # Select category
            if not self.select_category(category_name, platform_type):
                return False
            
            time.sleep(0.5)
            return True
            
        except Exception as e:
            logger.info(f"      Error configuring modal: {str(e)[:100]}")
            return False
    
    def select_store(self, store_name, platform_type):
        """Select store dropdown using config selector"""
        selector = APPTWEAK.get("modal_selectors", {}).get("store_dropdown", ".stores")
        
        try:
            dropdown = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            
            dropdown.click()
            time.sleep(0.3)
            
            select = Select(dropdown)
            
            # Try different ways to select
            try:
                select.select_by_visible_text(store_name)
            except:
                try:
                    select.select_by_value(platform_type)
                except:
                    # Try by index
                    if store_name == "Play Store":
                        select.select_by_index(1)
                    else:
                        select.select_by_index(0)
            
            time.sleep(0.5)
            return True
            
        except Exception as e:
            logger.info(f"        Error selecting store: {str(e)[:100]}")
            return False
    
    def select_country(self, country_name):
        """Select a specific country from the countries dropdown"""
        print(f"         🌍 Selecting country: {country_name}")
        
        try:
            # Wait for countries dropdown to be present
            countries_dropdown = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".countries"))
            )
            
            # Click the dropdown
            countries_dropdown.click()
            time.sleep(0.5)
            
            # Use Select class
            select = Select(countries_dropdown)
            
            # Try exact match first
            try:
                select.select_by_visible_text(country_name)
                print(f"            ✅ Country selected: {country_name}")
                time.sleep(0.5)
                return True
            except:
                # Try partial match
                options = select.options
                for option in options:
                    if country_name.lower() in option.text.lower():
                        option.click()
                        print(f"            ✅ Country selected (partial match): {option.text}")
                        time.sleep(0.5)
                        return True
                
                # Try common variations
                variations = {
                    "United Arab Emirate": ["United Arab Emirates", "UAE", "Emirates"],
                    "South Korea": ["Korea, Republic Of", "Korea Republic", "Korea"],
                    "United Kingdom": ["UK", "Great Britain", "Britain"],
                    "China": ["China mainland", "Mainland China", "China (Mainland)"],
                    "Hong Kong": ["Hong Kong SAR", "Hong Kong SAR China"],
                    "Taiwan": ["Taiwan, Province of China", "Taiwan Province of China"]
                }
                
                if country_name in variations:
                    for variation in variations[country_name]:
                        try:
                            select.select_by_visible_text(variation)
                            print(f"            ✅ Country selected (variation): {variation}")
                            return True
                        except:
                            continue
            
            logger.info(f"            ❌ Could not find country: {country_name}")
            return False
            
        except Exception as e:
            logger.info(f"            ❌ Error selecting country: {e}")
            return False
    
    def select_category(self, category_name, platform_type):
        """Select category dropdown using config selector"""
        selector = APPTWEAK.get("modal_selectors", {}).get("category_dropdown", ".categories")
        
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
            except:
                # Try case-insensitive
                selected = False
                for option in select.options:
                    if category_name.lower() in option.text.lower():
                        option.click()
                        print(f"        ✅ Selected category (case-insensitive): {option.text}")
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
        """Click save button using config selector"""
        selector = APPTWEAK.get("modal_selectors", {}).get("save_button", ".js-top-charts-change-column-btn.btn")
        
        try:
            save_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            
            save_button.click()
            
            wait = APPTWEAK.get("wait_times", {}).get("after_save", 2)
            time.sleep(wait)
            return True
            
        except:
            return False