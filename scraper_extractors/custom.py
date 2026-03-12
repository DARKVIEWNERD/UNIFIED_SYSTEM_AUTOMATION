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