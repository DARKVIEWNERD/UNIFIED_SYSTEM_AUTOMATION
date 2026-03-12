# extractors/sensortower.py
import re
from pathlib import Path
from bs4 import BeautifulSoup
from scraper_helpers.io import bs_kwargs
from scraper_helpers.text import looks_like_bad_publisher, clean_publisher_text, score_publisher_candidate

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
    Sensor Tower extractor (BS4) with relaxed matching + robust fallbacks for
    link/name/publisher and safer limiting.
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
        """Relaxed find: exact match; then stable class tokens; then any token."""
        if not sel:
            return None
        tag = sel.get("tag", "div")
        sel_type = sel.get("type", "class")
        value = (sel.get("value") or "").strip()

        # exact match first
        try:
            exact = node.find(tag, **bs_kwargs(sel_type, value))
            if exact:
                return exact
        except Exception:
            pass

        # relaxed class matching: drop volatile tokens (e.g., css-xxxxx)
        if sel_type == "class" and value:
            tokens = [t for t in value.split() if t]
            if tokens:
                stable = [t for t in tokens if not t.startswith("css-")]
                # try all-stable combined
                if stable:
                    try:
                        kw = {"class_": stable if len(stable) > 1 else stable[0]}
                        n = node.find(tag, **kw)
                        if n: 
                            return n
                    except Exception:
                        pass
                # then try each token
                for tok in tokens:
                    try:
                        n = node.find(tag, class_=tok)
                        if n: 
                            return n
                    except Exception:
                        pass
        return None

    def find_anchors(row):
        """Return list of all <a href> in row, in DOM order."""
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

    # --- Narrow to Main Container (if provided) ---
    main_sel = sel_for("Main Container")
    if main_sel:
        containers = soup.find_all(main_sel.get("tag", "div"),
                                   **bs_kwargs(main_sel.get("type", "class"), main_sel.get("value", "")))
        if not containers:
            return [], "Main Container not found"
        idx = int(cfg.get("main_container_index", 0))
        if idx < 0 or idx >= len(containers):
            return [], f"Main container index {idx} out of range ({len(containers)} found)"
        soup = containers[idx]

    row_sel = sel_for("Row Container")
    if not row_sel:
        return [], "No Row Container selector"

    row_nodes = soup.find_all(row_sel.get("tag", "div"),
                              **bs_kwargs(row_sel.get("type", "class"), row_sel.get("value", "")))
    if not row_nodes:
        return [], "No rows found for Row Container"

    name_sel = sel_for("App Name")
    pub_sel  = sel_for("Publisher")
    link_sel = sel_for("App Link")

    rows = []
    debug_notes = []
    seen = 0
    parsed = 0
    have_links = 0

    # Process rows; apply limit AFTER successful parse to avoid header/empty rows reducing count
    for row in row_nodes:
        seen += 1
        if cap and parsed >= cap:
            break

        # --- App Link ---
        app_link = ""
        link_node = find_one(row, link_sel) if link_sel else None
        if link_node:
            if hasattr(link_node, "name") and link_node.name == "a" and link_node.has_attr("href"):
                app_link = (link_node.get("href") or "").strip()
            else:
                # If selector hits a container, search inside for anchors
                for a in link_node.find_all("a", href=True):
                    href = (a.get("href") or "").strip()
                    if href:
                        app_link = href
                        break

        if not app_link:
            # Fallback 1: any app store link in this row
            anchors = find_anchors(row)
            # prioritize known stores
            priority = [lambda h: "apps.apple.com" in h,
                        lambda h: "play.google.com" in h,
                        lambda h: "appstore" in h or "itunes.apple.com" in h,
                        lambda h: "play.google" in h]
            found = None
            for a in anchors:
                h = (a.get("href") or "").strip()
                if not h:
                    continue
                if any(p(h) for p in priority):
                    found = h
                    break
            if not found and anchors:
                # fallback: first anchor with any href
                found = (anchors[0].get("href") or "").strip()
            if found:
                app_link = found

        if not app_link:
            # Fallback 2: try data-href / onclick (URL embedded)
            containers = [link_node] if link_node else [row]
            urlish = None
            url_pat = re.compile(r"(https?://[^\s\"')]+)", re.I)
            for cont in containers:
                # data-href style
                try:
                    dh = cont.get("data-href")
                    if dh and dh.strip():
                        urlish = dh.strip(); break
                except Exception:
                    pass
                # onclick javascript
                try:
                    oc = cont.get("onclick")
                    if oc:
                        m = url_pat.search(oc)
                        if m:
                            urlish = m.group(1); break
                except Exception:
                    pass
            if urlish:
                app_link = urlish

        # --- App Name ---
        app_name = ""
        name_node = find_one(row, name_sel) if name_sel else None
        if name_node:
            app_name = name_node.get_text(strip=True)

        if not app_name:
            # If we found an anchor (above), try pulling accessible name from that
            best_a = None
            if link_node and getattr(link_node, "name", None) == "a" and link_node.has_attr("href"):
                best_a = link_node
            else:
                anchors = find_anchors(row)
                if anchors:
                    best_a = anchors[0]
            if best_a:
                app_name = first_nonempty(
                    best_a.get("aria-label"),
                    best_a.get("title"),
                    best_a.text
                )

        if not app_name:
            # Typography fallbacks common in Material UI tables
            for css in [
                ("span", {"class": re.compile(r"MuiTypography-noWrap")}),
                ("h3", {}), ("h4", {}), ("h5", {}),
                ("strong", {}), ("b", {}), ("span", {})
            ]:
                try:
                    el = row.find(css[0], **css[1]) if css[1] else row.find(css[0])
                    if el:
                        txt = (el.get_text() or "").strip()
                        if txt:
                            app_name = txt
                            break
                except Exception:
                    pass

        # --- Publisher ---
        publisher = ""
        cand = []
        pub_node = find_one(row, pub_sel) if pub_sel else None
        if pub_node:
            t = (pub_node.get_text() or "").strip()
            if t:
                cand.append(t)

        if not cand:
            # heuristic scan for small/caption/body text that is NOT the app name
            for css in [
                ("span", {"class": re.compile(r"MuiTypography-(caption|body2)")}),
                ("div", {"class": re.compile(r"MuiTypography-(caption|body2)")}),
                ("small", {}),
                ("span", {}),
                ("div", {}),
            ]:
                try:
                    for el in row.find_all(css[0], **css[1]) if css[1] else row.find_all(css[0]):
                        t = (el.get_text() or "").strip()
                        if not t:
                            continue
                        if app_name and t == app_name:
                            continue
                        cand.append(t)
                except Exception:
                    pass

        # filter + rank candidates
        filtered = []
        BAD_PATTS = re.compile(
            r"(?:\bIn-?App\s+Purchases?\b|\bPrice:\s*\w+|\bFree\b|\bPaid\b|\bGrossing\b|"
            r"[\$€£¥₱]\s*\d|₱\s*\d|€\s*\d|¥\s*\d|£\s*\d|USD|EUR|GBP|JPY|CNY|RMB|HKD|TWD|KRW|INR|PHP|₹|"
            r"[★☆⭐]|/5|/10|\bratings?\b|\breviews?\b)",
            re.IGNORECASE
        )
        def looks_bad(txt: str) -> bool:
            t = (txt or "").strip()
            if not t or len(t) <= 2:
                return True
            if BAD_PATTS.search(t):
                return True
            letters = sum(ch.isalpha() for ch in t)
            return letters / max(1, len(t)) < 0.35

        for t in cand:
            if looks_bad(t):
                continue
            if app_name and t.lower() == app_name.lower():
                continue
            if looks_like_bad_publisher(t):
                continue
            filtered.append(clean_publisher_text(t))

        if filtered:
            ranked = sorted(
                ((score_publisher_candidate(app_name, t), t) for t in set(filtered)),
                key=lambda x: x[0], reverse=True
            )
            if ranked and ranked[0][0] > -10:
                publisher = ranked[0][1]
            else:
                publisher = sorted(set(filtered), key=len)[0]

        # Decide if row is valid enough to keep
        if any([app_name, publisher, app_link]):
            rows.append([publisher, app_name, app_link])
            parsed += 1
            if app_link:
                have_links += 1
        elif debug:
            debug_notes.append(f"Skipped row {seen}: empty parsed result")

    non_empty = any(any(cell for cell in r) for r in rows)
    status = (
        f"ok (bs4-relaxed). scanned={seen}, kept={parsed}, with_links={have_links}"
        if non_empty else
        f"Empty rows. scanned={seen}, kept={parsed}, with_links={have_links}"
    )
    if debug and debug_notes:
        status += " | notes: " + " | ".join(debug_notes[:5])  # avoid overly long status
    return (rows if non_empty else []), status


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

    headless = bool(cfg.get("selenium_headless", True)) if isinstance(cfg, dict) else True
    timeout_sec = int(cfg.get("selenium_timeout_sec", 10)) if isinstance(cfg, dict) else 10
    selectors = (cfg.get("custom_scraper_selectors") or []) if isinstance(cfg, dict) else []
    main_container_index = int(cfg.get("main_container_index", 0)) if isinstance(cfg, dict) else 0

    BAD_PATTS = re.compile(
        r"(?:\bIn-?App\s+Purchases?\b|\bPrice:\s*\w+|\bFree\b|\bPaid\b|\bGrossing\b|"
        r"[\$€£¥₱]\s*\d|₱\s*\d|€\s*\d|¥\s*\d|£\s*\d|USD|EUR|GBP|JPY|CNY|RMB|HKD|TWD|KRW|INR|PHP|₹|"
        r"[★☆⭐]|/5|/10|\bratings?\b|\breviews?\b)",
        re.IGNORECASE
    )

    def is_bad(text: str) -> bool:
        t = (text or "").strip()
        if not t or len(t) <= 2:
            return True
        if BAD_PATTS.search(t):
            return True
        letters = sum(ch.isalpha() for ch in t)
        return letters / max(1, len(t)) < 0.35

    def css_from_sel(sel, mode="exact"):
        tag = (sel.get("tag") or "*").strip()
        stype = (sel.get("type") or "class").strip().lower()
        val = (sel.get("value") or "").strip()
        if stype == "class":
            toks = [t for t in val.split() if t]
            if mode == "exact" and toks:
                return f"{tag}{''.join('.'+t for t in toks)}"
            if mode == "contains" and toks:
                return f"{tag}" + "".join([f"[class*='{t}']" for t in toks])
            return f"{tag}[class]"
        elif stype == "id":
            return f"{tag}#{val}" if val else f"{tag}[id]"
        elif stype == "attr":
            return f"{tag}[{val}]"
        else:
            if val:
                return f"{tag}[{stype}='{val}']"
            return f"{tag}"

    def find_first(node, sel, By=None):
        for mode in ("exact", "contains"):
            css = css_from_sel(sel, mode)
            try:
                return node.find_element(By.CSS_SELECTOR, css)
            except Exception:
                pass
        val = (sel.get("value") or "").strip()
        for tok in [t for t in val.split() if t]:
            try:
                return node.find_element(By.CSS_SELECTOR, f"{(sel.get('tag') or '*').strip()}[class*='{tok}']")
            except Exception:
                continue
        return None

    def find_all(node, sel, By=None):
        tried = set(); out = []
        for mode in ("exact", "contains"):
            css = css_from_sel(sel, mode)
            if css in tried:
                continue
            tried.add(css)
            try:
                els = node.find_elements(By.CSS_SELECTOR, css)
                if els:
                    out.extend(els)
                    break
            except Exception:
                pass
        if not out:
            val = (sel.get("value") or "").strip()
            for tok in [t for t in val.split() if t]:
                css = f"{(sel.get('tag') or '*').strip()}[class*='{tok}']"
                if css in tried:
                    continue
                tried.add(css)
                try:
                    els = node.find_elements(By.CSS_SELECTOR, css)
                    if els:
                        out.extend(els)
                        break
                except Exception:
                    pass
        return out

    def sel_for(role):
        r = (role or "").strip().lower()
        for s in selectors:
            if (s.get("role") or "").strip().lower() == r:
                return s
        return None

    chrome_options = ChromeOptions()
    chrome_options.add_argument("--allow-file-access-from-files")
    if headless:
        chrome_options.add_argument("--headless=new")

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(file_url)
        wait = WebDriverWait(driver, timeout_sec)
        By = type("By", (), {"CSS_SELECTOR": "css selector"})  # defer import

        root = driver
        main_sel = sel_for("Main Container")
        row_sel  = sel_for("Row Container")
        link_sel = sel_for("App Link")
        name_sel = sel_for("App Name")
        pub_sel  = sel_for("Publisher")

        if main_sel:
            wait.until(lambda d: find_first(d, main_sel, By) is not None)
            mains = find_all(driver, main_sel, By)
            if not mains:
                return [], "Main Container not found (selenium)"
            if main_container_index < 0 or main_container_index >= len(mains):
                return [], f"Main container index {main_container_index} out of range ({len(mains)} found)"
            root = mains[main_container_index]

        if not row_sel:
            return [], "No Row Container selector (selenium)"
        wait.until(lambda d: len(find_all(root, row_sel, By)) > 0)
        rows_nodes = find_all(root, row_sel, By)
        if not rows_nodes:
            return [], "No rows found (selenium)"

        cap = max_rows if isinstance(max_rows, int) and max_rows > 0 else int(cfg.get("max_rows", 10))
        out_rows = []
        with_links = 0

        for row_node in rows_nodes:
            if cap and len(out_rows) >= cap:
                break

            # Typical Sensor Tower list tables use tds; but fall back if not present
            tds = row_node.find_elements(By.CSS_SELECTOR, "td")
            free_td = tds[0] if tds else row_node

            # App Link
            app_link = ""
            if link_sel:
                ln = find_first(row_node, link_sel, By)
                if ln and ln.tag_name.lower() == "a":
                    app_link = (ln.get_attribute("href") or "").strip()
                elif ln:
                    # search inside for first <a href>
                    try:
                        a_inside = ln.find_element(By.CSS_SELECTOR, "a[href]")
                        app_link = (a_inside.get_attribute("href") or "").strip()
                    except Exception:
                        txt = (ln.text or "").strip()
                        app_link = txt
            if not app_link:
                # Priority: known stores
                a = None
                cand = free_td.find_elements(By.CSS_SELECTOR, "a[href*='apps.apple.com'], a[href*='play.google.com']")
                if cand: 
                    a = cand[0]
                else:
                    cand = free_td.find_elements(By.CSS_SELECTOR, "a[href]")
                    if cand:
                        a = cand[0]
                if a:
                    app_link = (a.get_attribute("href") or "").strip()

            if not app_link:
                # Try data-href / onclick
                for attr in ("data-href", "onclick"):
                    try:
                        v = free_td.get_attribute(attr)
                        if v:
                            if attr == "data-href" and v.strip().startswith("http"):
                                app_link = v.strip(); break
                            if attr == "onclick":
                                m = re.search(r"(https?://[^\s\"')]+)", v)
                                if m:
                                    app_link = m.group(1); break
                    except Exception:
                        pass

            # App Name
            app_name = ""
            if name_sel:
                nn = find_first(row_node, name_sel, By)
                if nn:
                    app_name = (nn.text or "").strip()
            if not app_name:
                try:
                    if 'a' not in locals() or a is None:
                        a_candidates = free_td.find_elements(By.CSS_SELECTOR, "a[href]")
                        a = a_candidates[0] if a_candidates else None
                    if a:
                        app_name = (
                            (a.get_attribute("aria-label") or "").strip() or
                            (a.get_attribute("title") or "").strip() or
                            (a.text or "").strip()
                        )
                except Exception:
                    pass
            if not app_name:
                for css in [".MuiTypography-noWrap", "h3, h4, h5", "strong, b", "span"]:
                    try:
                        el = free_td.find_element(By.CSS_SELECTOR, css)
                        txt = (el.text or "").strip()
                        if txt:
                            app_name = txt
                            break
                    except Exception:
                        pass

            # Publisher
            candidates = []
            if pub_sel:
                pn = find_first(row_node, pub_sel, By)
                if pn:
                    t = (pn.text or "").strip()
                    if t and not is_bad(t) and (not app_name or t.lower() != app_name.lower()):
                        candidates.append(t)
            if not candidates:
                for css in [
                    ".MuiTypography-root.MuiTypography-caption",
                    ".MuiTypography-root.MuiTypography-body2",
                    ".MuiTypography-small",
                    ".MuiTypography-caption",
                    ".MuiTypography-body2",
                    "span, div"
                ]:
                    try:
                        for el in row_node.find_elements(By.CSS_SELECTOR, css):
                            t = (el.text or "").strip()
                            if not t: continue
                            if app_name and t == app_name: continue
                            if is_bad(t): continue
                            candidates.append(t)
                    except Exception:
                        pass
            publisher = ""
            if candidates:
                ranked = sorted(((score_publisher_candidate(app_name, t), t) for t in set(candidates)),
                                key=lambda x: x[0], reverse=True)
                if ranked and ranked[0][0] > -10:
                    publisher = ranked[0][1]
                else:
                    publisher = sorted(set(candidates), key=len)[0]

            if any([publisher, app_name, app_link]):
                out_rows.append([publisher, app_name, app_link])
                if app_link:
                    with_links += 1

        non_empty = any(any(cell for cell in r) for r in out_rows)
        return (out_rows if non_empty else []), (
            f"ok (selenium+fallbacks) parsed={len(out_rows)}, with_links={with_links}"
            if non_empty else
            "Empty rows"
        )

    except Exception as e:
        return [], f"Selenium exception: {e}"
    finally:
        try:
            if driver is not None:
                driver.quit()
        except Exception:
            pass