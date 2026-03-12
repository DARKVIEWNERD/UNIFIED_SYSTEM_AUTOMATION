# d:\WIP\extractors\appfollow.py
import re
from bs4 import BeautifulSoup
from scraper_helpers.io import bs_kwargs  # kept for compatibility with your codebase (legacy path)

def extract_appfollow(html, cfg, max_rows=None):
    if not cfg:
        return [], "No 'appfollow' config"

    soup = BeautifulSoup(html, "html.parser")
    limit = max_rows if max_rows is not None else 10

    if cfg.get("custom_scraper_selectors"):
        return _extract_with_new_format(soup, cfg, limit)
    else:
        # Backward compatibility with your legacy config (container_selector/row_class/etc.)
        return _extract_with_legacy_format(soup, cfg, limit)


# ------------------------------- New-format extractor -------------------------------

def _extract_with_new_format(soup, cfg, limit):
    sel_map = _parse_selectors(cfg.get("custom_scraper_selectors", []))
    main_sel = sel_map.get("main container")
    row_sel = sel_map.get("row container")
    name_sel = sel_map.get("app name")
    link_sel = sel_map.get("app link") or name_sel  # often the same
    publisher_sel = sel_map.get("publisher")

    if not main_sel or not row_sel:
        return [], "Missing required selectors: 'Main Container' and/or 'Row Container'"

    containers = _find_all_by_selector(soup, main_sel)
    if not containers:
        return [], f"No containers found for Main Container selector: {main_sel}"

    # 1) Honor explicit index if provided and valid
    cfg_idx = cfg.get("main_container_index", None)
    chosen_idx = cfg_idx if isinstance(cfg_idx, int) and 0 <= cfg_idx < len(containers) else None

    # 2) Dynamic rule by container count (only if no explicit index)
    forced_reason = None
    if chosen_idx is None:
        if len(containers) == 3:
            chosen_idx = 1
            forced_reason = "forced_second_of_three"
        elif len(containers) == 2:
            chosen_idx = 0
            forced_reason = "forced_first_of_two"

    # 3) Otherwise, auto-pick likely Top Free container if preferred
    if chosen_idx is None:
        prefer_topfree = bool(cfg.get("prefer_topfree", True))
        if prefer_topfree:
            topfree_patterns = cfg.get("topfree_header_patterns") or [
                r"\bTop\s*Free\b",
                r"\bTop\s*Free\s*(Apps|Applications|iPhone|Android)?\b",
                r"\bFree\b",
            ]
            non_topfree_patterns = cfg.get("non_topfree_header_patterns") or [
                r"\bGrossing\b",
                r"\bPaid\b",
                r"\bRevenue\b",
            ]
            topfree_res = [re.compile(p, re.IGNORECASE) for p in topfree_patterns]
            non_topfree_res = [re.compile(p, re.IGNORECASE) for p in non_topfree_patterns]
            currency_re = re.compile(r"[\$\£\€\¥₱]|USD|EUR|GBP|JPY|CNY|RMB|HKD|TWD|KRW|INR|₹", re.IGNORECASE)

            def score_container(node):
                score = 0
                # Look backward for a section header near this container
                head = node.find_previous(
                    lambda tag: tag.name in ("h1", "h2", "h3", "h4", "h5", "h6")
                    and (tag.get_text(strip=True) or "")
                )
                if head:
                    ht = head.get_text(" ", strip=True)
                    if any(r.search(ht) for r in topfree_res): score += 6
                    if any(r.search(ht) for r in non_topfree_res): score -= 5

                # Sample some internal text
                texts = []
                for i, s in enumerate(node.stripped_strings):
                    if i > 80:
                        break
                    texts.append(s)
                internal_text = " ".join(texts)

                if any(r.search(internal_text) for r in topfree_res): score += 3
                if any(r.search(internal_text) for r in non_topfree_res): score -= 2
                if currency_re.search(internal_text): score -= 3
                if re.search(r"\bGrossing\b", internal_text, re.IGNORECASE): score -= 4
                if re.search(r"\bFree\b", internal_text, re.IGNORECASE): score += 4
                return score

            scores = [score_container(c) for c in containers]
            chosen_idx = max(range(len(containers)), key=lambda i: (scores[i], -i))

            # If all scores equal, fall back
            if len(set(scores)) == 1 and chosen_idx is None:
                chosen_idx = 0
        else:
            # Non-topfree fallback
            chosen_idx = 1 if len(containers) >= 3 else 0

    # Safety fallback
    if chosen_idx is None:
        chosen_idx = 0

    main_container = containers[chosen_idx]
    app_rows = _find_all_by_selector(main_container, row_sel)
    if not app_rows:
        return [], f"No app rows found in container idx={chosen_idx} (Row Container selector: {row_sel})"

    rows = []
    for app in app_rows[:limit]:
        name = publisher = app_link = ""
        name_tag = _find_first_by_selector(app, name_sel) if name_sel else app.find("a")
        if name_tag:
            name = name_tag.get_text(strip=True)
        link_tag = _find_first_by_selector(app, link_sel) if link_sel else name_tag
        if link_tag:
            app_link = link_tag.get("href", "") or ""
        pub_tag = _find_first_by_selector(app, publisher_sel) if publisher_sel else app.find("p")
        if pub_tag:
            publisher = pub_tag.get_text(strip=True)
        rows.append([publisher, name, app_link])

    non_empty = any(any(cell for cell in r) for r in rows)
    suffix = f", rule={forced_reason}" if forced_reason else ""
    detail = f"ok (container_idx={chosen_idx}{suffix}, rows={len(rows)})" if non_empty else "Empty rows"
    return (rows if non_empty else []), detail


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
    Legacy path for old config:
      container_selector / row_class / name_a_class / publisher_p_class
      with dynamic 2-vs-3 container rule and Top Free auto-selection.
    """
    container_selector = cfg.get("container_selector")
    row_class = cfg.get("row_class")
    publisher_p_class = cfg.get("publisher_p_class")
    name_a_class = cfg.get("name_a_class")

    if not container_selector or not row_class:
        return [], "Missing required keys in legacy config"

    containers = soup.select(container_selector)
    if not containers:
        return [], f"No containers found for selector: {container_selector}"

    # 1) Honor explicit index if provided
    cfg_idx = cfg.get("container_index", None)
    chosen_idx = cfg_idx if isinstance(cfg_idx, int) and 0 <= cfg_idx < len(containers) else None

    # 2) Dynamic rule by container count (only if no explicit index)
    forced_reason = None
    if chosen_idx is None:
        if len(containers) == 3:
            chosen_idx = 1
            forced_reason = "forced_second_of_three"
        elif len(containers) == 2:
            chosen_idx = 0
            forced_reason = "forced_first_of_two"

    # 3) Otherwise auto-pick the likely Top Free container
    if chosen_idx is None:
        prefer_topfree = bool(cfg.get("prefer_topfree", True))
        if prefer_topfree:
            topfree_patterns = cfg.get("topfree_header_patterns") or [
                r"\bTop\s*Free\b",
                r"\bTop\s*Free\s*(Apps|Applications|iPhone|Android)?\b",
                r"\bFree\b",
            ]
            non_topfree_patterns = cfg.get("non_topfree_header_patterns") or [
                r"\bGrossing\b",
                r"\bPaid\b",
                r"\bRevenue\b",
            ]
            topfree_res = [re.compile(p, re.IGNORECASE) for p in topfree_patterns]
            non_topfree_res = [re.compile(p, re.IGNORECASE) for p in non_topfree_patterns]
            currency_re = re.compile(r"[\$\£\€\¥₱]|USD|EUR|GBP|JPY|CNY|RMB|HKD|TWD|KRW|INR|₹", re.IGNORECASE)

            def score_container(node):
                score = 0
                head = node.find_previous(lambda tag: tag.name in ("h1","h2","h3","h4","h5","h6") and (tag.get_text(strip=True) or ""))
                if head:
                    ht = head.get_text(" ", strip=True)
                    if any(r.search(ht) for r in topfree_res): score += 6
                    if any(r.search(ht) for r in non_topfree_res): score -= 5

                texts = []
                for i, s in enumerate(node.stripped_strings):
                    if i > 80: break
                    texts.append(s)
                internal_text = " ".join(texts)
                if any(r.search(internal_text) for r in topfree_res): score += 3
                if any(r.search(internal_text) for r in non_topfree_res): score -= 2
                if currency_re.search(internal_text): score -= 3
                if re.search(r"\bGrossing\b", internal_text, re.IGNORECASE): score -= 4
                if re.search(r"\bFree\b", internal_text, re.IGNORECASE): score += 4
                return score

            scores = [score_container(c) for c in containers]
            chosen_idx = max(range(len(containers)), key=lambda i: (scores[i], -i))
            if len(set(scores)) == 1 and chosen_idx is None:
                chosen_idx = 0
        else:
            chosen_idx = 1 if len(containers) >= 3 else 0

    # Safety fallback
    if chosen_idx is None:
        chosen_idx = 0

    main_container = containers[chosen_idx]
    app_rows = main_container.find_all('div', **bs_kwargs("class", row_class))
    if not app_rows:
        return [], f"No app rows found in container idx={chosen_idx} (class={row_class})"

    rows = []
    for app in app_rows[:limit]:
        name = publisher = app_link = ''
        name_tag = app.find('a', **bs_kwargs("class", name_a_class)) if name_a_class else app.find('a')
        if name_tag:
            name = name_tag.get_text(strip=True)
            app_link = name_tag.get('href', '') or ''
        publisher_tag = app.find('p', **bs_kwargs("class", publisher_p_class)) if publisher_p_class else app.find('p')
        if publisher_tag:
            publisher = publisher_tag.get_text(strip=True)
        rows.append([publisher, name, app_link])

    non_empty = any(any(cell for cell in r) for r in rows)
    suffix = f", rule={forced_reason}" if forced_reason else ""
    detail = f"ok (container_idx={chosen_idx}{suffix}, rows={len(rows)})" if non_empty else "Empty rows"
    return (rows if non_empty else []), detail