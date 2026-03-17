# detector/country.py
from models.constants import COUNTRIES

_COUNTRY_SYNONYMS = {
    "usa": "US", "u.s.": "US", "u.s": "US", "uae": "AE",
    "ksa": "SA", "uk": "GB", "gbr": "GB", "england": "GB",
    "britain": "GB", "great_britain": "GB", "south_korea": "KR",
    "southkorea": "KR", "korea": "KR",
}

def _country_variants_for_text(c):
    v = set()
    name = (c.get("name") or "").lower()
    slug = (c.get("slug_name") or "").lower()
    v.add(name)
    v.add(slug)

    if name == "united arab emirate":
        v.add("united arab emirates")
    if name == "south korea" or "korea, republic of" in (slug or ""):
        v.update({"korea, republic of", "south korea"})
    if name == "united kingdom":
        v.update({"uk", "great britain"})
    if name == "united states":
        v.update({"usa", "u.s.", "u.s", "us"})

    return {x for x in v if x}


def detect_country_from_filename(path: str) -> str | None:
    """
    Filename-based country detection.

    Returns:
        Country abbreviation (e.g. 'ES', 'US', 'GB') or None
    """
    import os, re

    base = os.path.basename(path or "").lower()
    toks = {t for t in re.split(r"[^a-z0-9]+", base) if t}

    # 1) DIRECT COUNTRY CODE (preferred)
    for c in COUNTRIES:
        code = (c["code"] or "").lower()
        if code in toks:
            return c["code"].upper()

    # 2) COUNTRY NUMBER (fallback)
    for c in COUNTRIES:
        number = (c.get("number") or "").lower()
        if number and number in toks:
            return c["code"].upper()

    # 3) NAME / SLUG VARIANTS (fallback)
    for c in COUNTRIES:
        for v in _country_variants_for_text(c):
            v_norm = v.replace(" ", "_")
            if v in toks or v_norm in toks:
                return c["code"].upper()

    # 4) SYNONYMS (fallback)
    for syn, syn_code in _COUNTRY_SYNONYMS.items():
        if syn in toks or syn.replace(" ", "_") in toks:
            return syn_code.upper()

    return None