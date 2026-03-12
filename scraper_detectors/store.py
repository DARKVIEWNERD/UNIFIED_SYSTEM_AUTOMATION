# detector/store.py
import re
from urllib.parse import urlparse, parse_qs, unquote

APPLE_HOSTS = {"apps.apple.com", "itunes.apple.com"}
ANDROID_HOSTS = {"play.google.com"}
EMBEDDED_STORE_URL_RE = re.compile(
    r"https?://(?:apps\.apple\.com|itunes\.apple\.com|play\.google\.com)[^\s'\"<>]+",
    re.IGNORECASE
)

def _host_is_apple(host: str) -> bool:
    host = (host or "").lower()
    return any(host == h or host.endswith("." + h) for h in APPLE_HOSTS)

def _host_is_android(host: str) -> bool:
    host = (host or "").lower()
    return any(host == h or host.endswith("." + h) for h in ANDROID_HOSTS)

def _extract_embedded_store_url(s: str) -> str:
    if not s:
        return ""
    m = EMBEDDED_STORE_URL_RE.search(s)
    if m:
        return m.group(0)
    s_dec = unquote(s)
    if s_dec and s_dec != s:
        m = EMBEDDED_STORE_URL_RE.search(s_dec)
        if m:
            return m.group(0)
    return ""

def detect_store_from_filename(source_label: str) -> str:
    if not source_label:
        return ""
    base = source_label.lower()
    if "android" in base:
        return "Android"
    if "apple" in base:
        return "Apple"
    return ""

def detect_store_from_url(app_link: str) -> str:
    if not app_link:
        return ""
    raw = (app_link or "").strip()
    embedded = _extract_embedded_store_url(raw)
    candidate = embedded if embedded else raw
    parsed = urlparse(candidate)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if _host_is_android(host):
        return "Android"
    if _host_is_apple(host):
        return "Apple"

    if host.endswith("apps.appfollow.io"):
        if "/android/" in path:
            return "Android"
        if "/ios/" in path or "/iphone/" in path or "/ipad/" in path:
            return "Apple"

    qs = parse_qs(parsed.query or "")
    for key in ("url", "target", "u", "redirect", "dest", "destination"):
        for v in qs.get(key, []):
            inner = _extract_embedded_store_url(v) or v
            inner_parsed = urlparse(inner)
            if _host_is_android(inner_parsed.netloc):
                return "Android"
            if _host_is_apple(inner_parsed.netloc):
                return "Apple"

    last_try = _extract_embedded_store_url(unquote(raw))
    if last_try:
        host2 = urlparse(last_try).netloc
        if _host_is_android(host2):
            return "Android"
        if _host_is_apple(host2):
            return "Apple"
    return ""

def detect_store(source_label: str, app_link: str) -> str:
    return detect_store_from_filename(source_label) or detect_store_from_url(app_link)