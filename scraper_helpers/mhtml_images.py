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
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    parts = []

    if msg.is_multipart():
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                continue

            payload = part.get_payload(decode=True) or b""
            cid = part.get("Content-ID")
            if cid:
                cid = cid.strip().lstrip("<").rstrip(">")

            parts.append({
                "content_id": cid,
                "content_location": part.get("Content-Location"),
                "content_type": part.get_content_type(),
                "payload": payload,
            })

    return parts


def _build_resource_index(parts):
    by_cid = {}
    by_loc = {}

    for p in parts:
        if p.get("content_id"):
            by_cid[p["content_id"]] = p

        loc = p.get("content_location")
        if loc:
            by_loc[loc] = p
            try:
                import posixpath
                by_loc.setdefault(posixpath.basename(loc), p)
            except Exception:
                pass

    return by_cid, by_loc


# ============================================================
# Image resolution helpers
# ============================================================

def _is_data_uri(src: str) -> bool:
    return bool(src and src.strip().lower().startswith("data:"))


def _parse_data_uri(src: str):
    import base64, re
    m = re.match(r'^data:([^;,]+)?(;base64)?,(.*)$', src, flags=re.I | re.S)
    if not m:
        return None, None

    mime = m.group(1) or "application/octet-stream"
    try:
        if m.group(2):
            return mime, base64.b64decode(m.group(3))
        from urllib.parse import unquote_to_bytes
        return mime, unquote_to_bytes(m.group(3))
    except Exception:
        return None, None


def _resolve_img_source(src: str, by_cid, by_loc):
    """
    Returns:
        ("url", url)
        ("embed", bytes)
        (None, None)
    """
    if not src:
        return None, None

    s = src.strip()

    # ✅ Real URL
    if s.startswith(("http://", "https://")):
        return "url", s

    # ❌ data:
    if _is_data_uri(s):
        _, payload = _parse_data_uri(s)
        if payload:
            return "embed", payload
        return None, None

    # ❌ cid:
    if s.lower().startswith("cid:"):
        cid = s[4:]
        part = by_cid.get(cid) or by_cid.get(cid.split("@", 1)[0])
        if part:
            return "embed", part["payload"]
        return None, None

    # ⚠ Content-Location
    part = by_loc.get(s)
    if not part:
        import posixpath
        part = by_loc.get(posixpath.basename(s))

    if part:
        loc = part.get("content_location")
        if loc and loc.startswith(("http://", "https://")):
            return "url", loc
        return "embed", part["payload"]

    return None, None


# ============================================================
# Icon lookup logic
# ============================================================

def _make_icon_lookup(soup, by_cid, by_loc, max_size_px=60):
    import re

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
        kind, value = _resolve_img_source(img.get("src") or "", by_cid, by_loc)
        if kind == "url":
            return "url", value
        if kind == "embed":
            try:
                return "embed", fit_image_to_box_png(value, max_size_px, max_size_px)
            except Exception:
                return None, None
        return None, None

    def find_by_link(app_link):
        if not app_link:
            return None, None
        a = soup.find("a", href=re.compile(re.escape(app_link)))
        if not a:
            return None, None
        img = nearest_img_from(a)
        return resolve_img(img) if img else (None, None)

    def find_by_name(app_name):
        if not app_name or len(app_name) < 2:
            return None, None
        patt = re.compile(rf"\b{re.escape(app_name)}\b", re.I)
        el = soup.find(lambda t: t and patt.search(t.get_text(" ", strip=True)))
        if not el:
            return None, None
        img = el.find("img") or nearest_img_from(el)
        return resolve_img(img) if img else (None, None)

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
    html = _extract_html(mhtml_bytes)
    if not html:
        return lambda *_: (None, None)

    soup = BeautifulSoup(html, "html.parser")
    parts = _load_mhtml_parts(mhtml_bytes)
    by_cid, by_loc = _build_resource_index(parts)

    return _make_icon_lookup(soup, by_cid, by_loc, max_size_px)