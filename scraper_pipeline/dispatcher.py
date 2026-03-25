# extractors/custom.py
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
from scraper_extractors.custom import extract_custom_platform, scrape_custom_fallback

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
    
    # APPMAGIC
    if pk in ("appmagic", "app_magic", "app-magic"):
        am_key = None
        for k in ("appmagic", "AppMagic", "app_magic", "app-magic"):
            if k in config and isinstance(config[k], dict):
                am_key = k
                break

        if not am_key:
            return "appmagic", [], "No appmagic config found"

        am_cfg = config[am_key]

        # 1) If config is already a single selector block
        if "custom_scraper_selectors" in am_cfg:
            raw_rows = scrape_custom_fallback(
                source_path,
                am_cfg.get("custom_scraper_selectors", []),
                max_rows=max_rows,
                main_container_index=am_cfg.get("main_container_index", 0),
            )

            # normalize dict → list
            rows = [
                [
                    r.get("publisher", ""),
                    r.get("app_name", ""),
                    r.get("app_link", ""),
                ]
                for r in raw_rows
            ]

            return "appmagic", rows, "ok"

        # 2) Optional: variant detection by filename (store / chart)
        toks = set(filename_tokens_lower(source_path or ""))

        variant_order = ["top_free", "top_paid", "top_grossing"]
        variant = None

        if {"free", "topfree", "top_free"} & toks:
            variant = "top_free"
        elif {"paid", "toppaid", "top_paid"} & toks:
            variant = "top_paid"
        elif {"grossing", "topgrossing", "top_grossing"} & toks:
            variant = "top_grossing"

        tried = []

        if variant:
            sub_cfg = am_cfg.get(variant)
            if isinstance(sub_cfg, dict) and "custom_scraper_selectors" in sub_cfg:
                raw_rows = scrape_custom_fallback(
                    source_path,
                    sub_cfg.get("custom_scraper_selectors", []),
                    max_rows=max_rows,
                    main_container_index=sub_cfg.get("main_container_index", 0),
                )

                rows = [
                    [r.get("publisher", ""), r.get("app_name", ""), r.get("app_link", "")]
                    for r in raw_rows
                ]

                return f"appmagic:{variant}", rows, "ok"

            tried.append(variant)

        # 3) Fallback: try known variants in order
        for key in variant_order:
            if key in tried:
                continue

            sub_cfg = am_cfg.get(key)
            if isinstance(sub_cfg, dict) and "custom_scraper_selectors" in sub_cfg:
                raw_rows = scrape_custom_fallback(
                    source_path,
                    sub_cfg.get("custom_scraper_selectors", []),
                    max_rows=max_rows,
                    main_container_index=sub_cfg.get("main_container_index", 0),
                )

                if raw_rows:
                    rows = [
                        [r.get("publisher", ""), r.get("app_name", ""), r.get("app_link", "")]
                        for r in raw_rows
                    ]
                    return f"appmagic:{key}", rows, "ok"

        return "appmagic", [], "No usable appmagic config (no rows)"

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
    
    
    else:
        
        rows = scrape_custom_fallback(source_path, config.get(platform_key, {}).get("custom_scraper_selectors", []), max_rows=max_rows, main_container_index=config.get("appmagic", {}).get("main_container_index"))
        reason = "custom fallback with no config" if not rows else "custom fallback success"    
        return platform_key, rows, reason

def build_output_rows(platform_name, extracted_rows, country_code, quarter_str, source_label):
    """
    Map platform-specific rows [publisher, app_name, app_link] into the fixed schema.
    Also classify content category so the writer knows the target sheet.
    """
    country_code = country_code if country_code else ""
    source_path = os.path.abspath(source_label) if source_label else ""

    rows_out = []
    for idx, item in enumerate(extracted_rows, start=1):
        publisher = item[0] if len(item) > 0 else ""
        app_name = item[1] if len(item) > 1 else ""
        app_link = item[2] if len(item) > 2 else ""
        store = detect_store(os.path.basename(source_path), app_link)
        row = [
            quarter_str,       # 1 Quarter
            country_code,      # 2 Country
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
