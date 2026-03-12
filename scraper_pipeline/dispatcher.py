# scraper_extractors/custom.py
from bs4 import BeautifulSoup
from scraper_helpers.io import bs_kwargs
from scraper_helpers.text import looks_like_bad_publisher, clean_publisher_text, score_publisher_candidate

def _narrow_by_main_containers(soup, main_selectors, index):
    current = soup
    for sel in main_selectors:
        kwargs = bs_kwargs(sel.get("type", "class"), sel.get("value", ""))
        nodes = current.find_all(sel.get("tag", "div"), **kwargs)
        if not nodes:
            return None, f"Main container not found for {sel}"
        if index < 0 or index >= len(nodes):
            return None, f"Main container index {index} out of range ({len(nodes)} found)"
        current = nodes[index]
    return current, "ok"
# pipeline/dispatcher.py
import os
from scraper_detectors.store import detect_store
from scraper_detectors.category import classify_category_by_content
from scraper_helpers.util import filename_tokens_lower
from scraper_extractors.similarweb import extract_similarweb
from scraper_extractors.appfollow import extract_appfollow
from scraper_extractors.sensortower import extract_sensortower, extract_sensortower_via_selenium
from scraper_extractors.custom import extract_custom_platform

def extract_platform_rows(platform_key: str, html: str, config: dict, *, max_rows=None, source_path=None):
    """
    One dispatcher for all supported platforms.
    Returns (platform_name, rows, reason)
    """
    pk = (platform_key or "").strip().lower()

    # SIMILARWEB
    if pk == "similarweb":
        if "similarweb" in config:
            rows, reason = extract_similarweb(html, config.get("similarweb"), max_rows=max_rows)
            return "similarweb", rows, reason
        sw_cfg = config.get("similar_web") or config.get("Similarweb")
        if isinstance(sw_cfg, dict):
            rows, reason = extract_similarweb(html, sw_cfg, max_rows=max_rows)
            return "similarweb", rows, reason
        return "similarweb", [], "No config for similarweb"

    # APPFOLLOW
    if pk == "appfollow":
        if "appfollow" in config:
            rows, reason = extract_appfollow(html, config.get("appfollow"), max_rows=max_rows)
            return "appfollow", rows, reason
        af_cfg = config.get("Appfollow") or config.get("app_follow")
        if isinstance(af_cfg, dict):
            rows, reason = extract_appfollow(html, af_cfg, max_rows=max_rows)
            return "appfollow", rows, reason
        return "appfollow", [], "No config for appfollow"

    # SENSORTOWER (prefer bs4, fallback selenium if configured & available)
    if pk in ("sensortower", "sensor_tower", "sensor tower"):
        st_key_variants = ["SensorTower", "sensortower", "sensor_tower", "sensor tower"]
        st_key = None
        for k in config.keys():
            if (k or "").strip().lower() in {s.lower() for s in st_key_variants}:
                st_key = k; break
        if not st_key or not isinstance(config.get(st_key), dict):
            return "sensortower", [], "No Sensor Tower config found"
        st_cfg = config.get(st_key)
        bs_rows, bs_reason = extract_sensortower(html, st_cfg, max_rows=max_rows)
        if bs_rows:
            return st_key, bs_rows, bs_reason
        if source_path:
            se_rows, se_reason = extract_sensortower_via_selenium(source_path, st_cfg, max_rows=max_rows)
            return st_key, se_rows, se_reason
        return st_key, bs_rows, bs_reason

    # APPFIGURES (sub-variants)
   # inside extract_platform_rows(...) in the appfigures section

    if pk in ("appfigures", "appfigure", "app_figures", "app-figures"):
        af_key = None
        for k in ("appfigures", "Appfigures", "app_figure", "AppFigures"):
            if k in config and isinstance(config[k], dict):
                af_key = k
                break
        if not af_key:
            return "appfigures", [], "No appfigures config found"

        sub_cfg_all = config[af_key]
        # Three patterns we know
        variant_keys_order = ["top_free", "top_paid", "top_grossing"]

        # 1) If config is already a single selector block (has custom_scraper_selectors at top level)
        if "custom_scraper_selectors" in sub_cfg_all:
            rows, reason = extract_custom_platform(html, sub_cfg_all, max_rows=max_rows)
            return "appfigures", rows, reason

        # 2) Else: pick by filename tokens if present
        toks = set(filename_tokens_lower(source_path or ""))
        variant = None
        if {"free", "topfree", "top_free"} & toks:
            variant = "top_free"
        elif {"paid", "toppaid", "top_paid"} & toks:
            variant = "top_paid"
        elif {"grossing", "topgrossing", "top_grossing"} & toks:
            variant = "top_grossing"

        tried = []
        if variant:
            sub_cfg = sub_cfg_all.get(variant)
            if isinstance(sub_cfg, dict) and "custom_scraper_selectors" in sub_cfg:
                rows, reason = extract_custom_platform(html, sub_cfg, max_rows=max_rows)
                return f"appfigures:{variant}", rows, reason
            tried.append(variant)

        # 3) Fallback: try known variants in order
        for key in variant_keys_order:
            if key in tried:
                continue
            sub_cfg = sub_cfg_all.get(key)
            if isinstance(sub_cfg, dict) and "custom_scraper_selectors" in sub_cfg:
                rows, reason = extract_custom_platform(html, sub_cfg, max_rows=max_rows)
                if rows:
                    return f"appfigures:{key}", rows, reason

        # 4) Final fallback: try ANY first sub-config that has custom_scraper_selectors
        for key, sub_cfg in sub_cfg_all.items():
            if isinstance(sub_cfg, dict) and "custom_scraper_selectors" in sub_cfg:
                rows, reason = extract_custom_platform(html, sub_cfg, max_rows=max_rows)
                if rows:
                    return f"appfigures:{key}", rows, reason

        return "appfigures", [], "No usable sub-config under appfigures (no rows)"

    # APPTWEAK
    if pk in ("apptweak", "app_tweak", "app-tweak"):
        at_key = None
        for k in ("apptweak", "AppTweak"):
            if k in config and isinstance(config[k], dict):
                at_key = k; break
        if not at_key:
            return "apptweak", [], "No apptweak config found"
        at_cfg = config[at_key]
        if "custom_scraper_selectors" in at_cfg:
            rows, reason = extract_custom_platform(html, at_cfg, max_rows=max_rows)
            return "apptweak", rows, reason
        return "apptweak", [], "No custom_scraper_selectors for apptweak"

    # GENERIC CUSTOM (any key with custom_scraper_selectors)
    if platform_key in config and isinstance(config.get(platform_key), dict) and "custom_scraper_selectors" in config.get(platform_key):
        rows, reason = extract_custom_platform(html, config.get(platform_key), max_rows=max_rows)
        return platform_key, rows, reason

    return platform_key or "", [], "No extractor for hinted platform"


def build_output_rows(platform_name, extracted_rows, country_dict, quarter_str, source_label):
    """
    Map platform-specific rows [publisher, app_name, app_link] into the fixed schema.
    Also classify content category so the writer knows the target sheet.
    """
    country_name = country_dict["name"] if country_dict else ""
    source_path = os.path.abspath(source_label) if source_label else ""

    rows_out = []
    for idx, item in enumerate(extracted_rows, start=1):
        publisher = item[0] if len(item) > 0 else ""
        app_name = item[1] if len(item) > 1 else ""
        app_link = item[2] if len(item) > 2 else ""
        store = detect_store(os.path.basename(source_path), app_link)
        row = [
            quarter_str,       # 1 Quarter
            country_name,      # 2 Country
            store,             # 3 Android or Apple
            idx,               # 4 Rank
            publisher,         # 5 Publisher
            app_name,          # 6 App Name
            app_link,          # 7 App Link
            source_path,       # 8 Source
            platform_name      # 9 Platform
        ]
        # Use content-based classification to decide sheet name later
        cat = classify_category_by_content(row)
        # Trick: store the category in row[0] temporarily for excel helper's route (or you can return alongside)
        # But we’ll keep the original schema and pass the sheet name from the caller instead.
        rows_out.append(row)
    return rows_out
def extract_custom_platform(html, platform_cfg, max_rows=None):
    selectors = platform_cfg.get("custom_scraper_selectors") if platform_cfg else None
    if not selectors:
        return [], "No custom_scraper_selectors"
    soup = BeautifulSoup(html, "html.parser")
    main_container_index = platform_cfg.get("main_container_index", 0)

    main_selectors = [s for s in selectors if s.get("role") == "Main Container"]
    if main_selectors:
        narrowed, reason = _narrow_by_main_containers(soup, main_selectors, main_container_index)
        if not narrowed:
            return [], reason
        soup = narrowed

    row_selectors = [s for s in selectors if s.get("role") == "Row Container"]
    if not row_selectors:
        return [], "No Row Container selector"

    limit = max_rows if max_rows is not None else 10
    def selectors_for(role: str):
        return [s for s in selectors if s.get("role") == role]

    def find_role_text(row_node, role: str, avoid_node=None, prefer_non_anchor=False):
        for sel in selectors_for(role):
            kwargs = bs_kwargs(sel.get("type", "class"), sel.get("value", ""))
            tag_name = sel.get("tag", "div")
            tag = row_node.find(tag_name, **kwargs)
            if not tag:
                continue
            if avoid_node is not None and tag is avoid_node:
                continue
            if prefer_non_anchor and tag.name == "a":
                sib = tag.find_next_sibling()
                while sib and sib.name == "a":
                    sib = sib.find_next_sibling()
                if sib and sib.get_text(strip=True):
                    return sib.get_text(strip=True), sib
                non_a = tag.find(lambda t: t.name not in ("a",) and (t.get_text(strip=True) if t else ""))
                if non_a and non_a.get_text(strip=True):
                    return non_a.get_text(strip=True), non_a
                txt = tag.get_text(strip=True)
                if txt:
                    return txt, tag
                continue
            txt = tag.get_text(strip=True)
            if txt:
                return txt, tag
        return "", None

    def find_role_link(row_node, role: str, avoid_node=None):
        for sel in selectors_for(role):
            kwargs = bs_kwargs(sel.get("type", "class"), sel.get("value", ""))
            tag_name = sel.get("tag", "a")
            tag = row_node.find(tag_name, **kwargs)
            if not tag:
                continue
            if avoid_node is not None and tag is avoid_node:
                continue
            if tag.name == "a" and tag.has_attr("href"):
                href = tag.get("href", "").strip()
                if href:
                    return href
            txt = tag.get_text(strip=True)
            if txt:
                return txt
        return ""

    for row_sel in row_selectors:
        row_kwargs = bs_kwargs(row_sel.get("type", "class"), row_sel.get("value", ""))
        row_tag = row_sel.get("tag", "div")
        row_nodes = soup.find_all(row_tag, **row_kwargs)
        if not row_nodes:
            continue

        rows = []
        for row in row_nodes[:limit]:
            app_name, app_name_node = find_role_text(row, "App Name", avoid_node=None, prefer_non_anchor=False)
            publisher, publisher_node = find_role_text(row, "Publisher", avoid_node=app_name_node, prefer_non_anchor=True)
            publisher = clean_publisher_text(publisher)

            need_fallback = (
                not publisher or
                (app_name and publisher.strip().lower() == (app_name or "").strip().lower()) or
                looks_like_bad_publisher(publisher)
            )
            if need_fallback:
                raw_texts = []
                for i, t in enumerate(row.stripped_strings):
                    if i > 40: break
                    t = (t or "").strip()
                    if not (3 <= len(t) <= 60): continue
                    raw_texts.append((i, t))
                scored = []
                seen = set()
                for _, txt in raw_texts:
                    cand = clean_publisher_text(txt)
                    if not cand: continue
                    if cand in seen: continue
                    seen.add(cand)
                    sc = score_publisher_candidate(app_name or "", cand)
                    if sc > -20:
                        scored.append((sc, cand))
                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    publisher = scored[0][1]
                elif app_name and not publisher:
                    publisher = app_name

            app_link = find_role_link(row, "App Link", avoid_node=None)
            rows.append([publisher, app_name, app_link])

        if any(any(cell for cell in r) for r in rows):
            return rows, "ok"

    return [], "No data rows found with provided selectors"