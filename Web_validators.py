# Web_validators.py
# UNIVERSAL PAGE VALIDATION & PROTECTION LAYER

import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import MAX_RETRIES, DELAYS
from utils.utils import ToastMSG, focus_browser
import utils.utils as utils
from logging_config import logger
    


# ==========================================================
# HUMAN VERIFICATION / CAPTCHA DETECTION
# ==========================================================

def is_human_verification(driver) -> bool:
    """Detect CAPTCHA / bot / verification pages (universal)"""
    try:
        title = driver.title.lower()
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        url = driver.current_url.lower()

        # ── URL-based triggers (very reliable) ───────────────────────────
        url_triggers = [
            "/challenge",
            "/captcha",
        ]
        for trigger in url_triggers:
            if trigger in url:
                return True

        # ── Title-based triggers ──────────────────────────────────────────
        title_triggers = [
            "captcha",
            "verify you are human",
            "human verification",
            "attention required",
            "just a moment",  # ← Cloudflare challenge page title
        ]
        for trigger in title_triggers:
            if trigger in title:
                return True

        # ── Body-based triggers (strict — avoid false positives) ──────────
        body_triggers = [
            "verify you are human",
            "checking your browser",
            "unusual traffic",
            "please complete the security check",
            "prove you are human",
        ]
        for trigger in body_triggers:
            if trigger in body:
                return True

        return False

    except Exception:
        return False
    
def wait_for_manual_verification(driver, timeout=300):
    """Wait for user to manually solve CAPTCHA"""
    logger.warning("⚠ Human verification detected.")
    logger.warning("🧍 Please solve it manually in browser...")
    ToastMSG("Automation Engine", "Human verification detected", "🧍 Please solve it manually in browser...", "long")

    start = time.time()

    while time.time() - start < timeout:
        if not is_human_verification(driver):
            logger.info("✅ Verification cleared.")
            ToastMSG("Automation Engine", "Human verification detected", "✅ Verification cleared.", "short")
            return True
        time.sleep(3)

    logger.error("❌ Verification timeout.")
    ToastMSG("Automation Engine", "Human verification detected", "❌ Verification timeout.", "short")
    return False


# ==========================================================
# UNIVERSAL COOKIE HANDLER
# ==========================================================





def handle_platform_cookies(driver, platform_name: str | None = None) -> bool:
    """
    Universal cookie handler.
    Tries Accept, Reject, Customize, Close.
    Platform name is only informational.
    """
    logger.info(f"🍪 Checking cookies (platform={platform_name})")

    cookie_keywords = [
        "accept",
        "agree",
        "allow",
        "ok",
        "got it",
        "reject",
        "customize",
        "consent"
    ]

    try:
        time.sleep(.5)

        buttons = driver.find_elements(By.XPATH, "//button | //*[@role='button']")

        for button in buttons:
            try:
                if not button.is_displayed():
                    continue

                text = button.text.lower().strip()

                if any(word in text for word in cookie_keywords):
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", button
                    )
                    time.sleep(0.5)

                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(.5)

                    logger.info(f"✔ Cookie interaction: {text}")
                    return True

            except:
                continue

    except Exception as e:
        logger.debug(f"Cookie handler error: {e}")

    return True


# ==========================================================
# PAGE HEALTH VALIDATION (UNIVERSAL)
# ==========================================================

def is_page_unusable(driver, web_platform_type: str) -> tuple[bool, str]:
    """
    Detect 403, blocked, empty, or unavailable pages
    NOW INCLUDES APPTWEAK-SPECIFIC VALIDATIONS
    """
    try:
        title = driver.title.lower()
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        url = driver.current_url.lower()

        # Clean body text for better checking
        body_cleaned = re.sub(r'<[^>]+>', '', body)
        body_cleaned = re.sub(r'http[^\s]+', '', body_cleaned)
        body_cleaned = re.sub(r'\d{3,}', '', body_cleaned)
        
        blocked_indicators = [
            "403",
            "forbidden",
            "access denied",
            "not available",
            "page not found",
            "no data available",
            "temporarily unavailable",
            "error occurred",
            "unable to access",
            "blocked",
            "restricted",
            "not found (404)",
            "the page you requested was not found",
            "this page is not available",
            "404 error",
        ]

        # Check for blocked indicators in CLEANED text
        for word in blocked_indicators:
            if word in body_cleaned or word in title or word in url:
                return True, f"Blocked / unavailable ({word})"

        # SimilarWeb specific checks
        if web_platform_type == "similarweb":
            if "404" in title or "404" in body:
                return True, "SimilarWeb: 404 error page"
            
            if "no ranking data" in body or "no results found" in body:
                return True, "SimilarWeb: no ranking data"
            
            if "we couldn't find any apps" in body:
                return True, "SimilarWeb: no apps found"
            
            if "top apps by category" in title and "/top-apps/" not in url:
                return True, "SimilarWeb: redirected to main page"

        # AppTweak specific checks
        elif web_platform_type == "apptweak":
            # Check for AppTweak error messages
            apptweak_errors = [
                "something went wrong",
                "error loading",
                "failed to load",
                "please try again",
            ]
            
            for error in apptweak_errors:
                if error in body_cleaned:
                    return True, f"AppTweak: {error}"
            
            # Check if top charts page loaded properly
            if "app store top charts" not in title and "top-charts" not in url:
                return True, "AppTweak: not on top charts page"
            
            # Check for modal/dialog elements (should be present)
            try:
                modal_elements = driver.find_elements(By.CSS_SELECTOR, 
                    ".modal, .modal-dialog, .js-change-column")
                if not modal_elements:
                    # Might still be okay if page loaded but no modal
                    pass
            except:
                pass

        # AppFollow specific checks
        elif web_platform_type == "appfollow":
            try:
                content_elements = driver.find_elements(By.CSS_SELECTOR,
                    ".rankings-table, .app-item, .ranking-row, .app-card")
                
                visible_text = re.sub(r'\s+', ' ', body_cleaned).strip()
                word_count = len(visible_text.split())
                
                if len(content_elements) < 1 and word_count < 50:
                    return True, "AppFollow: insufficient content"
            except:
                pass

        # Generic check for very short/empty pages
        if len(body_cleaned) < 50:
            return True, "Page too short - likely blocked or empty"

        # If we get here, page appears valid
        return False, ""

    except Exception as e:
        return True, f"Validation error: {str(e)[:60]}"

# ==========================================================
# URL RETRY WITH AUTO REFRESH
# ==========================================================

def test_url_with_retry(driver, url, max_retries=MAX_RETRIES):

    for attempt in range(max_retries + 1):
        try:
            driver.get(url)
            utils.random_sleep(*DELAYS["page_load"])

            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
            if len(body_text) < 50:
                raise Exception("Page rendered but content too short — still loading")

            return True

        except Exception as e:
            if attempt == max_retries:
                logger.error(f"❌ Failed after {max_retries} retries: {e}")
                try:
                    logger.info("🔄 Attempting auto-refresh...")
                    driver.refresh()
                    utils.random_sleep(*DELAYS["page_load"])
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
                    if len(body_text) >= 50:
                        logger.info("✅ Auto-refresh successful.")
                        return True
                except Exception as refresh_error:
                    logger.error(f"❌ Auto-refresh failed: {refresh_error}")

                return False  # ← stops the retrying

            logger.warning(f"⚠️ Retrying ({attempt + 1}/{max_retries}): {e}")
            utils.random_sleep(*DELAYS["retry"])

    return False