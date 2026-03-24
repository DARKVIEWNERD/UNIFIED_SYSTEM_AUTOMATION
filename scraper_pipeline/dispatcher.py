# pipeline/dispatcher.py
import os

from scraper_detectors.store import detect_store
from scraper_detectors.category import classify_category_by_content
from scraper_helpers.util import filename_tokens_lower

from scraper_extractors.similarweb import extract_similarweb
from scraper_extractors.appfollow import extract_appfollow
from scraper_extractors.sensortower import (
    extract_sensortower,
    extract_sensortower_via_selenium,
)
from scraper_extractors.custom import (
    extract_custom_platform,
    extract_custom_legacy,
)


# -----------------------------
# Helper: run custom with fallback
# -----------------------------
def _run_custom_with_fallback(platform_name, html, cfg, *, max_rows):
    """
    Try strict custom extractor first.
    Fallback to legacy custom extractor if needed.
    """
    rows, reason = extract_custom_platform(html, cfg, max_rows=max_rows)
    if rows:
        return platform_name, rows, reason

    legacy_rows, legacy_reason = extract_custom_legacy(html, cfg, max_rows=max_rows)
    if legacy_rows:
        return platform_name, legacy_rows, f"fallback:{legacy_reason}"

    return platform_name, [], f"custom_failed ({reason}); legacy_failed ({legacy_reason})"


# -----------------------------
# Main dispatcher
# -----------------------------
def extract_platform_rows(
    platform_key: str,
    html: str,
    config: dict,
    *,
    max_rows=None,
    source_path=None,
):
    """
    One dispatcher for all supported platforms.
    Returns (platform_name, rows, reason)
    """
    pk = (platform_key or "").strip().lower()

    # -----------------------------
    # SIMILARWEB
    # -----------------------------
    if pk == "similarweb":
        cfg = (
            config.get("similarweb")
            or config.get("similar_web")
            or config.get("Similarweb")
        )
        if isinstance(cfg, dict):
            rows, reason = extract_similarweb(html, cfg, max_rows=max_rows)
            return "similarweb", rows, reason
        return "similarweb", [], "No config for similarweb"

    # -----------------------------
    # APPFOLLOW
    # -----------------------------
    if pk == "appfollow":
        cfg = (
            config.get("appfollow")
            or config.get("Appfollow")
            or config.get("app_follow")
        )
        if isinstance(cfg, dict):
            rows, reason = extract_appfollow(html, cfg, max_rows=max_rows)
            return "appfollow", rows, reason
        return "appfollow", [], "No config for appfollow"

    # -----------------------------
    # SENSORTOWER
    # -----------------------------
    if pk in ("sensortower", "sensor_tower", "sensor tower"):
        st_key = next(
            (
                k
                for k in config
                if (k or "").strip().lower()
                in {
                    "sensortower",
                    "sensor_tower",
                    "sensor tower",
                }
            ),
            None,
        )
        if not st_key or not isinstance(config.get(st_key), dict):
            return "sensortower", [], "No Sensor Tower config found"

        cfg = config[st_key]
        rows, reason = extract_sensortower(html, cfg, max_rows=max_rows)
        if rows:
            return st_key, rows, reason

        if source_path:
            rows, reason = extract_sensortower_via_selenium(
                source_path, cfg, max_rows=max_rows
            )
            return st_key, rows, reason

        return st_key, [], reason

    # -----------------------------
    # APPFIGURES (variants)
    # -----------------------------
    if pk in ("appfigures", "appfigure", "app_figures", "app-figures"):
        af_key = next(
            (
                k
                for k in ("appfigures", "Appfigures", "AppFigures", "app_figure")
                if k in config and isinstance(config[k], dict)
            ),
            None,
        )
        if not af_key:
            return "appfigures", [], "No appfigures config found"

        sub_cfg_all = config[af_key]

        # Case 1: flat custom config
        if "custom_scraper_selectors" in sub_cfg_all:
            return _run_custom_with_fallback(
                af_key, html, sub_cfg_all, max_rows=max_rows
            )

        # Case 2: filename-based variant
        toks = set(filename_tokens_lower(source_path or ""))
        variant = None
        if toks & {"free", "topfree", "top_free"}:
            variant = "top_free"
        elif toks & {"paid", "toppaid", "top_paid"}:
            variant = "top_paid"
        elif toks & {"grossing", "topgrossing", "top_grossing"}:
            variant = "top_grossing"

        tried = set()
        if variant:
            tried.add(variant)
            sub_cfg = sub_cfg_all.get(variant)
            if isinstance(sub_cfg, dict) and "custom_scraper_selectors" in sub_cfg:
                return _run_custom_with_fallback(
                    f"{af_key}:{variant}", html, sub_cfg, max_rows=max_rows
                )

        # Case 3: known variants fallback
        for key in ("top_free", "top_paid", "top_grossing"):
            if key in tried:
                continue
            sub_cfg = sub_cfg_all.get(key)
            if isinstance(sub_cfg, dict) and "custom_scraper_selectors" in sub_cfg:
                name, rows, reason = _run_custom_with_fallback(
                    f"{af_key}:{key}", html, sub_cfg, max_rows=max_rows
                )
                if rows:
                    return name, rows, reason

        # Case 4: any remaining custom block
        for key, sub_cfg in sub_cfg_all.items():
            if isinstance(sub_cfg, dict) and "custom_scraper_selectors" in sub_cfg:
                name, rows, reason = _run_custom_with_fallback(
                    f"{af_key}:{key}", html, sub_cfg, max_rows=max_rows
                )
                if rows:
                    return name, rows, reason

        return "appfigures", [], "No usable appfigures layout"

    # -----------------------------
    # APPTWEAK
    # -----------------------------
    if pk in ("apptweak", "app_tweak", "app-tweak"):
        at_key = next(
            (k for k in ("apptweak", "AppTweak") if k in config),
            None,
        )
        if not at_key:
            return "apptweak", [], "No apptweak config found"

        cfg = config[at_key]
        if "custom_scraper_selectors" in cfg:
            return _run_custom_with_fallback(
                at_key, html, cfg, max_rows=max_rows
            )

        return "apptweak", [], "No custom_scraper_selectors for apptweak"

    # -----------------------------
    # GENERIC CUSTOM (any key)
    # -----------------------------
    if (
        platform_key in config
        and isinstance(config.get(platform_key), dict)
        and "custom_scraper_selectors" in config[platform_key]
    ):
        return _run_custom_with_fallback(
            platform_key, html, config[platform_key], max_rows=max_rows
        )

    return platform_key or "", [], "No extractor for hinted platform"
# -----------------------------
# Output mapping
# -----------------------------
def build_output_rows(
    platform_name,
    extracted_rows,
    country_code,
    quarter_str,
    source_label,
):
    """
    Map platform-specific rows [publisher, app_name, app_link]
    into the fixed schema used by the Excel writer.
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
            quarter_str,     # 1 Quarter
            country_code,    # 2 Country
            store,           # 3 Store
            idx,             # 4 Rank
            publisher,       # 5 Publisher
            app_name,        # 6 App Name
            app_link,        # 7 App Link
            source_path,     # 8 Source
            platform_name,   # 9 Platform
        ]

        # Category classification happens later
        classify_category_by_content(row)
        rows_out.append(row)

    return rows_out