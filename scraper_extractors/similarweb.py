# extractors/similarweb.py
import re
from bs4 import BeautifulSoup
from scraper_helpers.io import bs_kwargs  # kept for legacy path compatibility

def extract_similarweb(html, cfg, max_rows=None):
    """
    Extract Similarweb top apps with support for:
      - New format: 'custom_scraper_selectors' (role-based selector list)
      - Legacy format: table_class / row_class / app_td_class / name_span_class / publisher_span_class / link_a_class

    Output rows: [publisher, name, app_link]
    """
    if not cfg:
        return [], "No 'similarweb' config"

    soup = BeautifulSoup(html, "html.parser")
    limit = max_rows if max_rows is not None else 10

    if cfg.get("custom_scraper_selectors"):
        return _extract_with_new_format(soup, cfg, limit)
    else:
        return _extract_with_legacy_format(soup, cfg, limit)


# ------------------------------- New-format extractor -------------------------------

def _extract_with_new_format(soup, cfg, limit):
    """
    Expected roles (case-insensitive):
      - "Table"        : the main <table> (or container) node
      - "Row"          : row nodes under Table (e.g., <tr>)
      - "App Cell"     : the cell within a Row that contains app info (e.g., <td>)
      - "App Name"     : element under App Cell that contains the app name
      - "Publisher"    : element under App Cell that contains the publisher name
      - "App Link"     : <a> under App Cell with the app/store URL

    Note: If App Cell is not provided, the code searches directly in the Row.
    """
    sel_map = _parse_selectors(cfg.get("custom_scraper_selectors", []))
    table_sel = sel_map.get("table") or sel_map.get("main container")  # allow either naming
    row_sel = sel_map.get("row") or sel_map.get("row container")
    appcell_sel = sel_map.get("app cell")
    name_sel = sel_map.get("app name")
    publisher_sel = sel_map.get("publisher")
    link_sel = sel_map.get("app link")

    if not table_sel or not row_sel:
        return [], "Missing required selectors: 'Table' and/or 'Row'"

    tables = _find_all_by_selector(soup, table_sel)
    if not tables:
        return [], f"No tables found for selector: {table_sel}"

    table = tables[0]  # Similarweb pages typically have one ranking table
    data_rows = _find_all_by_selector(table, row_sel)
    if not data_rows:
        return [], "Data rows not found under Table/Row selectors"

    rows = []
    for tr in data_rows[:limit]:
        scope = _find_first_by_selector(tr, appcell_sel) if appcell_sel else tr
        publisher = name = app_link = ""

        if scope:
            # Name
            name_tag = _find_first_by_selector(scope, name_sel) if name_sel else None
            if name_tag:
                name = name_tag.get_text(strip=True)

            # Publisher
            pub_tag = _find_first_by_selector(scope, publisher_sel) if publisher_sel else None
            if pub_tag:
                publisher = pub_tag.get_text(strip=True)

            # Link
            link_tag = _find_first_by_selector(scope, link_sel) if link_sel else None
            if link_tag and link_tag.has_attr("href"):
                app_link = link_tag.get("href", "") or ""

        rows.append([publisher, name, app_link])

    non_empty = any(any(cell for cell in r) for r in rows)
    return (rows if non_empty else []), ("ok" if non_empty else "Empty rows")


def _parse_selectors(selector_list):
    """
    Convert list of selector dicts to a role->selector map with lowercased role keys.
    Each selector dict expected keys: role, tag, type, value
    """
    sel_map = {}
    for sel in selector_list:
        role = (sel.get("role") or "").strip().lower()
        if not role:
            continue
        sel_map[role] = {
            "tag": (sel.get("tag") or "").strip() or None,
            "type": (sel.get("type") or "class").strip().lower(),
            "value": (sel.get("value") or "").strip(),
        }
    return sel_map


def _find_all_by_selector(root, sel):
    """
    Support types: 'class', 'id', 'css', 'attrs' (as 'k=v;k2=v2' string). Defaults to CSS if unknown.
    For 'class', supports space-separated multiple classes (all must be present).
    """
    if not sel:
        return []

    tag = sel.get("tag") or True
    typ = (sel.get("type") or "class").lower()
    val = sel.get("value") or ""

    if typ == "css":
        try:
            return root.select(val)
        except Exception:
            return []
    elif typ == "id":
        return root.find_all(tag if tag else True, id=val)
    elif typ == "class":
        classes = _prepare_class_list(val)
        return root.find_all(tag if tag else True, class_=classes)
    elif typ == "attrs":
        attrs = _parse_attrs_string(val)
        return root.find_all(tag if tag else True, attrs=attrs)
    else:
        # Best-effort: treat as CSS if it looks like a selector, otherwise fallback by tag
        try:
            return root.select(val)
        except Exception:
            return root.find_all(tag if tag else True)


def _find_first_by_selector(root, sel):
    items = _find_all_by_selector(root, sel)
    return items[0] if items else None


def _prepare_class_list(value):
    # Split by any whitespace and drop empties
    return [c for c in re.split(r"\s+", value.strip()) if c]


def _parse_attrs_string(s):
    """
    Parse 'k=v;k2=v2' or 'k=v, k2=v2' into a dict usable by BeautifulSoup attrs=...
    """
    attrs = {}
    if not s:
        return attrs
    for part in re.split(r"[;,]\s*", s):
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                attrs[k] = v
    return attrs


# ----------------------------- Legacy-format extractor -----------------------------

def _extract_with_legacy_format(soup, cfg, limit):
    """
    Legacy path using your previous keys:
      - table_class
      - row_class
      - app_td_class
      - name_span_class
      - publisher_span_class
      - link_a_class
    """
    table_class = cfg.get("table_class")
    row_class = cfg.get("row_class")
    app_td_class = cfg.get("app_td_class")
    name_span_class = cfg.get("name_span_class")
    publisher_span_class = cfg.get("publisher_span_class")
    link_a_class = cfg.get("link_a_class")

    if not table_class or not row_class:
        return [], "Missing required class keys in config"

    table = soup.find('table', **bs_kwargs("class", table_class))
    if not table:
        return [], "Table not found"

    data_rows = table.find_all('tr', **bs_kwargs("class", row_class))
    if not data_rows:
        return [], "Data rows not found"

    rows = []
    for tr in data_rows[:limit]:
        app_td = tr.find('td', **bs_kwargs("class", app_td_class)) if app_td_class else tr.find('td')
        publisher = name = app_link = ''
        if app_td:
            name_span = app_td.find('span', **bs_kwargs("class", name_span_class)) if name_span_class else None
            if name_span:
                name = name_span.get_text(strip=True)
            publisher_span = app_td.find('span', **bs_kwargs("class", publisher_span_class)) if publisher_span_class else None
            if publisher_span:
                publisher = publisher_span.get_text(strip=True)
            link_tag = app_td.find('a', **bs_kwargs("class", link_a_class)) if link_a_class else app_td.find('a')
            if link_tag and link_tag.has_attr('href'):
                app_link = link_tag.get('href', '') or ''
        rows.append([publisher, name, app_link])

    non_empty = any(any(cell for cell in r) for r in rows)
    return (rows if non_empty else []), ("ok" if non_empty else "Empty rows")