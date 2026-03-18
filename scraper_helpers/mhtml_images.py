# helpers/mhtml_images.py

from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image as PILImage
from email import policy
from email.parser import BytesParser

# ============================================================
# Image transcoding / resizing
# ============================================================

def transcode_to_png(blob: bytes) -> BytesIO:
    """
    Convert arbitrary image bytes (webp/gif/jpg/png/bmp) to PNG in-memory.
    For GIF: takes first frame. Preserves alpha when present.
    """
    bio_in = BytesIO(blob)
    with PILImage.open(bio_in) as im:
        if im.mode in ("P", "LA"):
            im = im.convert("RGBA")
        elif im.mode == "CMYK":
            im = im.convert("RGB")

        try:
            if getattr(im, "is_animated", False):
                im.seek(0)
        except Exception:
            pass

        out = BytesIO()
        im.save(out, format="PNG")
        out.seek(0)
        return out


def fit_image_to_box_png(blob: bytes, max_w_px: int, max_h_px: int) -> BytesIO:
    """
    Convert to PNG and resize to fit within max_w_px x max_h_px
    (keep aspect ratio; no upscaling).
    """
    with PILImage.open(transcode_to_png(blob)) as im:
        w, h = im.size
        scale = min(max_w_px / w, max_h_px / h, 1.0)
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        resized = im.resize(new_size, PILImage.LANCZOS)

        out = BytesIO()
        resized.save(out, format="PNG")
        out.seek(0)
        return out


# ============================================================
# MHTML parsing helpers
# ============================================================

def _extract_html(raw: bytes) -> str | None:
    """
    Extract the text/html part from MHTML bytes.
    """
    try:
        msg = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception:
        return None

    if msg.is_multipart():
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if not payload:
                    return None
                try:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
                except Exception:
                    return payload.decode(errors="replace")

    return None


def _load_mhtml_parts(raw: bytes):
    """
    Parse raw MHTML bytes and return resource parts:
    {
        content_id,
        content_location,
        content_type,
        payload
    }
    """
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    parts = []

    if msg.is_multipart():
        for part in msg.iter_parts():
            ctype = part.get_content_type()

            if ctype == "text/html":
                continue

            payload = part.get_payload(decode=True) or b""
            cid = part.get("Content-ID")
            if cid:
                cid = cid.strip().lstrip("<").rstrip(">")

            loc = part.get("Content-Location")

            parts.append({
                "content_id": cid,
                "content_location": loc,
                "content_type": ctype,
                "payload": payload,
            })

    return parts


def _build_resource_index(parts):
    """
    Build lookup maps for resolving image src by:
    - Content-ID
    - Content-Location
    """
    by_cid = {}
    by_loc = {}

    for p in parts:
        cid = p.get("content_id")
        loc = p.get("content_location")

        if cid:
            by_cid[cid] = p

        if loc:
            by_loc[loc] = p
            # also index basename fallback
            try:
                import posixpath
                base = posixpath.basename(loc)
                if base and base not in by_loc:
                    by_loc[base] = p
            except Exception:
                pass

    return by_cid, by_loc


# ============================================================
# Image src resolution
# ============================================================

def _is_data_uri(src: str) -> bool:
    return bool(src and src.strip().lower().startswith("data:"))


def _parse_data_uri(src: str):
    """
    Parse data:image/png;base64,...
    Returns (mime, bytes) or (None, None)
    """
    import base64, re

    m = re.match(
        r'^data:([^;,]+)?(;base64)?,(.*)$',
        src,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not m:
        return None, None

    mime = m.group(1) or "application/octet-stream"
    is_b64 = bool(m.group(2))
    data_part = m.group(3)

    try:
        if is_b64:
            payload = base64.b64decode(data_part)
        else:
            from urllib.parse import unquote_to_bytes
            payload = unquote_to_bytes(data_part)
        return mime, payload
    except Exception:
        return None, None


def _guess_ext_from_mime(mime: str) -> str:
    if not mime:
        return ".png"
    m = mime.lower()
    if "png" in m: return ".png"
    if "jpeg" in m or "jpg" in m: return ".jpg"
    if "gif" in m: return ".gif"
    if "bmp" in m: return ".bmp"
    if "webp" in m: return ".webp"
    return ".png"


def _resolve_img_source(src: str, by_cid, by_loc):
    """
    Resolve image source.

    Returns:
        ("url", url_str)
        ("embed", image_bytes, ext)
        (None, None)
    """
    if not src:
        return None, None

    s = src.strip()

    # ✅ REAL external URL — BEST CASE
    if s.startswith(("http://", "https://")):
        return "url", s

    # ❌ data URI → embedded only
    if _is_data_uri(s):
        mime, payload = _parse_data_uri(s)
        if payload:
            return "embed", payload
        return None, None

    # ❌ cid → embedded only
    if s.lower().startswith("cid:"):
        cid = s[4:]
        part = by_cid.get(cid) or (by_cid.get(cid.split("@", 1)[0]) if "@" in cid else None)
        if part:
            return "embed", part["payload"]
        return None, None

    # ⚠️ Content-Location fallback
    part = by_loc.get(s)
    if not part:
        import posixpath
        part = by_loc.get(posixpath.basename(s))

    if part:
        loc = part.get("content_location", "")
        if loc.startswith(("http://", "https://")):
            return "url", loc
        return "embed", part["payload"]

    return None, None
# ============================================================
# Icon lookup logic
# ============================================================

def _make_icon_lookup(soup, by_cid, by_loc, max_size_px=60):
    import re

    seen_icon_urls = set()  # ✅ track URLs already used in this column

    def nearest_img_from(node):
        steps = 0
        while node and steps < 5:
            img = node.find("img")
            if img and img.get("src"):
                return img
            node = node.parent
            steps += 1
        return None

    def resolve_img(img):
        src = img.get("src") or ""
        kind, val = _resolve_img_source(src, by_cid, by_loc)

        # --------------------------------------------------
        # ✅ URL icon — only allow if NOT seen before
        # --------------------------------------------------
        if kind == "url":
            if val in seen_icon_urls:
                return None, None  # ✅ append blank
            seen_icon_urls.add(val)
            return "url", val

        # --------------------------------------------------
        # ✅ Embedded icon — always allowed
        # --------------------------------------------------
        if kind == "embed":
            try:
                return "embed", fit_image_to_box_png(val, max_size_px, max_size_px)
            except Exception:
                return None, None

        return None, None

    def find_by_link(app_link):
        if not app_link:
            return None, None

        a = soup.find("a", href=app_link)
        if not a:
            try:
                a = soup.find("a", href=re.compile(re.escape(app_link)))
            except Exception:
                return None, None

        img = nearest_img_from(a)
        if img:
            return resolve_img(img)
        return None, None

    def find_by_name(app_name):
        if not app_name or len(app_name) < 2:
            return None, None

        try:
            patt = re.compile(rf"\b{re.escape(app_name)}\b", re.I)
            el = soup.find(lambda t: t and patt.search(t.get_text(" ", strip=True)))
        except Exception:
            return None, None

        img = el.find("img") if el else None
        if img:
            return resolve_img(img)
        return None, None

    def icon_lookup(app_link, app_name):
        return (
            find_by_link(app_link)
            or find_by_name(app_name)
            or (None, None)
        )

    return icon_lookup
# ============================================================
# Public API
# ============================================================

def build_icon_lookup(mhtml_bytes: bytes, max_size_px: int = 60):
    """
    Build and return:
        icon_lookup(app_link: str, app_name: str) -> BytesIO | None
    """
    html = _extract_html(mhtml_bytes)
    if not html:
        return lambda *_: None

    soup = BeautifulSoup(html, "html.parser")
    parts = _load_mhtml_parts(mhtml_bytes)
    by_cid, by_loc = _build_resource_index(parts)

    return _make_icon_lookup(soup, by_cid, by_loc, max_size_px)