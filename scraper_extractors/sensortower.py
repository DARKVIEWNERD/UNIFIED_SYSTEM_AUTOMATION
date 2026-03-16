# extractors/sensortower.py
import re
from pathlib import Path
from bs4 import BeautifulSoup
from helpers.io import bs_kwargs
from helpers.text import looks_like_bad_publisher, clean_publisher_text, score_publisher_candidate

# --- Optional Selenium ---
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    HAS_SELENIUM = True
except Exception:
    HAS_SELENIUM = False


def extract_sensortower(html, cfg, max_rows=None):
    """
    Sensor Tower extractor (BS4) — patched to KEEP publisher == app name
    """
    if not cfg:
        return [], "No 'sensortower' config"

    selectors = cfg.get("custom_scraper_selectors") or []
    if not selectors:
        return [], "No custom_scraper_selectors"

    debug = bool(cfg.get("debug", False))
    soup = BeautifulSoup(html or "", "html.parser")
    cap = max_rows if isinstance(max_rows, int) and max_rows > 0 else int(cfg.get("max_rows", 10))

    def sel_for(role: str):
        role_norm = (role or "").strip().lower()
        for s in selectors:
            if (s.get("role") or "").strip().lower() == role_norm:
                return s
        return None

    def find_one(node, sel):
        if not sel:
            return None
        tag = sel.get("tag", "div")
        sel_type = sel.get("type", "class")
        value = (sel.get("value") or "").strip()

        try:
            exact = node.find(tag, **bs_kwargs(sel_type, value))
            if exact:
                return exact
        except Exception:
            pass

        if sel_type == "class" and value:
            tokens = [t for t in value.split() if t]
            stable = [t for t in tokens if not t.startswith("css-")]
            if stable:
                try:
                    n = node.find(tag, class_=stable if len(stable) > 1 else stable[0])
                    if n:
                        return n
                except Exception:
                    pass
            for tok in tokens:
                try:
                    n = node.find(tag, class_=tok)
                    if n:
                        return n
                except Exception:
                    pass
        return None

    def find_anchors(row):
        try:
            return list(row.find_all("a", href=True))
        except Exception:
            return []

    def first_nonempty(*vals):
        for v in vals:
            t = (v or "").strip()
            if t:
                return t
        return ""

    # --- Containers ---
    main_sel = sel_for("Main Container")
    if main_sel:
        containers = soup.find_all(
            main_sel.get("tag", "div"),
            **bs_kwargs(main_sel.get("type", "class"), main_sel.get("value", ""))
        )
        if not containers:
            return [], "Main Container not found"
        idx = int(cfg.get("main_container_index", 0))
        if idx < 0 or idx >= len(containers):
            return [], f"Main container index {idx} out of range"
        soup = containers[idx]

    row_sel = sel_for("Row Container")
    if not row_sel:
        return [], "No Row Container selector"

    row_nodes = soup.find_all(
        row_sel.get("tag", "div"),
        **bs_kwargs(row_sel.get("type", "class"), row_sel.get("value", ""))
    )
    if not row_nodes:
        return [], "No rows found"

    name_sel = sel_for("App Name")
    pub_sel  = sel_for("Publisher")
    link_sel = sel_for("App Link")

    rows = []
    parsed = 0

    for row in row_nodes:
        if cap and parsed >= cap:
            break

        # --- App Link ---
        app_link = ""
        ln = find_one(row, link_sel) if link_sel else None
        if ln:
            if ln.name == "a" and ln.has_attr("href"):
                app_link = (ln.get("href") or "").strip()
            else:
                for a in ln.find_all("a", href=True):
                    app_link = (a.get("href") or "").strip()
                    break

        if not app_link:
            anchors = find_anchors(row)
            if anchors:
                app_link = (anchors[0].get("href") or "").strip()

        # --- App Name ---
        app_name = ""
        nn = find_one(row, name_sel) if name_sel else None
        if nn:
            app_name = nn.get_text(strip=True)

        if not app_name:
            anchors = find_anchors(row)
            if anchors:
                a = anchors[0]
                app_name = first_nonempty(a.get("aria-label"), a.get("title"), a.text)

        # --- Publisher (PATCHED) ---
        cand = []

        pn = find_one(row, pub_sel) if pub_sel else None
        if pn:
            t = (pn.get_text() or "").strip()
            if t:
                cand.append(t)

        if not cand:
            for css in [
                ("span", {"class": re.compile(r"MuiTypography-(caption|body2)")}),
                ("div",  {"class": re.compile(r"MuiTypography-(caption|body2)")}),
                ("small", {}),
                ("span", {}),
                ("div", {})
            ]:
                for el in row.find_all(css[0], **css[1]) if css[1] else row.find_all(css[0]):
                    t = (el.get_text() or "").strip()
                    if t:
                        cand.append(t)

        filtered = []
        for t in cand:
            if looks_like_bad_publisher(t):
                continue
            filtered.append(clean_publisher_text(t))

        publisher = ""
        if filtered:
            ranked = sorted(
                ((score_publisher_candidate(app_name, t), t) for t in set(filtered)),
                key=lambda x: x[0],
                reverse=True
            )

            # ✅ Prefer entity publisher, fallback to identical app name
            non_identical = [t for _, t in ranked if t.lower() != app_name.lower()]
            publisher = non_identical[0] if non_identical else ranked[0][1]

        if any([publisher, app_name, app_link]):
            rows.append([publisher, app_name, app_link])
            parsed += 1

    return rows, f"ok (bs4 patched). kept={parsed}"


# ============================================================
# ✅ SELENIUM PATH — PATCHED
# ============================================================

def extract_sensortower_via_selenium(file_path, cfg, max_rows=None):
    if not HAS_SELENIUM:
        return [], "Selenium not available"

    try:
        p = Path(file_path)
        if not p.exists():
            return [], f"File not found: {file_path}"
        file_url = p.resolve().as_uri()
    except Exception as e:
        return [], f"Invalid file path: {e}"

    headless = bool(cfg.get("selenium_headless", True))
    selectors = cfg.get("custom_scraper_selectors") or []
    cap = max_rows if isinstance(max_rows, int) and max_rows > 0 else int(cfg.get("max_rows", 10))

    chrome_options = ChromeOptions()
    chrome_options.add_argument("--allow-file-access-from-files")
    if headless:
        chrome_options.add_argument("--headless=new")

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(file_url)
        wait = WebDriverWait(driver, 10)

        def sel_for(role):
            r = (role or "").strip().lower()
            for s in selectors:
                if (s.get("role") or "").strip().lower() == r:
                    return s
            return None

        row_sel = sel_for("Row Container")
        name_sel = sel_for("App Name")
        pub_sel  = sel_for("Publisher")

        rows = driver.find_elements(By.CSS_SELECTOR, row_sel["value"])
        out = []

        for row in rows:
            if cap and len(out) >= cap:
                break

            app_name = ""
            pn = row.find_elements(By.CSS_SELECTOR, name_sel["value"]) if name_sel else []
            if pn:
                app_name = pn[0].text.strip()

            candidates = []
            pub_nodes = row.find_elements(By.CSS_SELECTOR, pub_sel["value"]) if pub_sel else []
            for el in pub_nodes:
                t = el.text.strip()
                if t:
                    candidates.append(t)

            publisher = ""
            if candidates:
                ranked = sorted(
                    ((score_publisher_candidate(app_name, t), t) for t in set(candidates)),
                    key=lambda x: x[0],
                    reverse=True
                )
                non_identical = [t for _, t in ranked if t.lower() != app_name.lower()]
                publisher = non_identical[0] if non_identical else ranked[0][1]

            if publisher or app_name:
                out.append([publisher, app_name, ""])

        return out, f"ok (selenium patched). kept={len(out)}"

    except Exception as e:
        return [], f"Selenium exception: {e}"
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass