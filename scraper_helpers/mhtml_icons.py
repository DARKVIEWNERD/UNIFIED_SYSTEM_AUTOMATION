# helpers/mhtml_icons.py
import base64
import re
from io import BytesIO
from email import policy
from email.parser import BytesParser
from typing import Tuple, Dict, Any, Optional
from PIL import Image as PILImage

_DATA_URI_RE = re.compile(r"^data:([^;,]+)?(?:;base64)?,", re.IGNORECASE)
_DATA_URI_FULL_RE = re.compile(r"^data:([^;,]+)?(;base64)?,(.*)$", re.IGNORECASE | re.DOTALL)

def load_mhtml_return_html_and_parts(path: str) -> Tuple[bytes, list]:
    """
    Parse MHTML file into (html_bytes, parts).
    Each part is: {"content_id", "content_location", "content_type", "payload"}
    """
    with open(path, "rb") as f:
        raw = f.read()

    msg = BytesParser(policy=policy.default).parsebytes(raw)
    html_bytes = None
    parts = []

    if msg.is_multipart():
        for part in msg.iter_parts():
            ctype = part.get_content_type()
            payload = part.get_payload(decode=True) or b""
            content_id = part.get("Content-ID")
            if content_id:
                content_id = content_id.strip().lstrip("<").rstrip(">")

            content_location = part.get("Content-Location")

            if ctype == "text/html" and html_bytes is None:
                html_bytes = payload
            else:
                parts.append({
                    "content_id": content_id,
                    "content_location": content_location,
                    "content_type": ctype,
                    "payload": payload,
                })
    else:
        if msg.get_content_type() == "text/html":
            html_bytes = msg.get_payload(decode=True)

    return html_bytes or b"", parts

def build_mhtml_index(parts: list) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build lookups: by Content-ID and by Content-Location (plus basename).
    """
    by_cid, by_loc = {}, {}
    for p in parts:
        cid = p.get("content_id")
        loc = p.get("content_location")
        if cid:
            by_cid[cid] = p
        if loc:
            by_loc[loc] = p
            # basename fallback
            try:
                import posixpath
                base = posixpath.basename(loc)
                if base and base not in by_loc:
                    by_loc[base] = p
            except Exception:
                pass
    return by_cid, by_loc

def _parse_data_uri(src: str) -> Tuple[Optional[str], Optional[bytes]]:
    m = _DATA_URI_FULL_RE.match(src or "")
    if not m:
        return None, None
    mime = m.group(1) or "application/octet-stream"
    is_b64 = bool(m.group(2))
    data_part = m.group(3) or ""
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
    ml = mime.lower()
    if "png" in ml: return ".png"
    if "jpeg" in ml or "jpg" in ml: return ".jpg"
    if "gif" in ml: return ".gif"
    if "bmp" in ml: return ".bmp"
    if "webp" in ml: return ".webp"
    return ".png"

def _transcode_to_png(blob: bytes) -> BytesIO:
    """
    Convert any common format (webp/gif/jpg/png) to PNG in-memory.
    For GIF: first frame only.
    """
    bio = BytesIO(blob)
    with PILImage.open(bio) as im:
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

def _fit_png(blob: bytes, max_w_px: int, max_h_px: int) -> BytesIO:
    with PILImage.open(_transcode_to_png(blob)) as im:
        w, h = im.size
        scale = min(max_w_px / max(w, 1), max_h_px / max(h, 1), 1.0)
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        resized = im.resize(new_size, PILImage.LANCZOS)
        out = BytesIO()
        resized.save(out, format="PNG")
        out.seek(0)
        return out

def resolve_icon_png_from_mhtml_src(src: str,
                                    by_cid: Dict[str, Any],
                                    by_loc: Dict[str, Any],
                                    size_px: int = 32) -> Optional[BytesIO]:
    """
    Given an <img src> string from HTML inside an MHTML, return a resized PNG BytesIO,
    resolved via data: / cid: / Content-Location in the MHTML. Returns None if not resolvable.
    """
    if not src:
        return None

    s = (src or "").strip()

    # 1) data:image/...
    if s.lower().startswith("data:"):
        mime, payload = _parse_data_uri(s)
        if payload:
            return _fit_png(payload, size_px, size_px)
        return None

    # 2) cid:...
    if s.lower().startswith("cid:"):
        cid = s[4:]  # remove 'cid:'
        part = by_cid.get(cid) or (by_cid.get(cid.split("@", 1)[0]) if "@" in cid else None)
        if part and part.get("payload"):
            return _fit_png(part["payload"], size_px, size_px)
        return None

    # 3) Content-Location (exact or basename match)
    part = by_loc.get(s)
    if not part:
        try:
            import posixpath
            base = posixpath.basename(s)
            part = by_loc.get(base)
        except Exception:
            part = None
    if part and part.get("payload"):
        return _fit_png(part["payload"], size_px, size_px)

    # 4) Not resolvable from MHTML (likely an external http(s) URL)
    return None